"""Per-frame simulation step and multiverse mechanics.

Frame order per universe (matches the historical update_simulation_state exactly):
  barrier deformation → cloud gravity → collisions/entity updates/events → barrier
  gravity+containment → tracer spin → merger pulses → black-hole pass (attract/decay/rip/
  evaporate) → neutron-star pass (gravity/pulses/spin-down/decay) → magnetar pass (gravity/
  magnetism/flares/field decay→settle into NS) → white-dwarf pass (cooling/Type Ia) →
  kilonova mergers → pulse collisions → removals & spawns → integration.
Captured clouds stay in the arrays until the end-of-step removal (the neutron-star pass sees
them, as it always did); streamed clouds get their position rewritten at capture and the row
moves to the child universe at the end of the step — visible before the child steps.
"""
import math
import random

import numpy as np

from sim.config import *
from sim.fields import CloudField, pick_element, blend_abundance
from sim.barrier import Barrier
from sim.entities import BlackHole, NeutronStar, Magnetar, WhiteDwarf
from sim.rng import EntropyPool
from sim import gravity

try:
    from sim import fastphysics as _fastphysics  # compiled hot loops (build: python setup_fastphysics.py build_ext --inplace)
except Exception:
    _fastphysics = None


class LocalPhysics:
    """Per-universe physical constants, as multipliers on the global dials. Root (Big-Bang)
    universes are born at baseline 1.0; a child ripped from a parent inherits the parent's
    values with a small log-normal mutation, clamped to [UNIVERSE_DIAL_MIN, UNIVERSE_DIAL_MAX].
    Selection does the rest: universes whose physics makes more black holes rip more children
    under the multiverse's carrying capacity — cosmological natural selection, with the
    variation the clonal version lacked. Scope is deliberately narrow (the star-formation
    pipeline only): BH gravity/disk dynamics stay globally tuned — see the galaxy-swirl
    couplings — so mutation can change how MANY holes form, never how disks behave."""
    __slots__ = ('g', 'fusion', 'collapse')

    def __init__(self, g=1.0, fusion=1.0, collapse=1.0):
        self.g = g                # x cloud/star self-gravity (force is linear in G, so this scales the summed output)
        self.fusion = fusion      # x cloud merge chance, ambient and shock-triggered
        self.collapse = collapse  # x core-collapse chance at the mass threshold

    def mutated(self):
        def drift(v):
            return min(UNIVERSE_DIAL_MAX,
                       max(UNIVERSE_DIAL_MIN, v * math.exp(random.gauss(0.0, UNIVERSE_MUTATION_SCALE))))
        return LocalPhysics(drift(self.g), drift(self.fusion), drift(self.collapse))


class Universe:
    """One self-contained world: a barrier plus the matter inside it."""
    def __init__(self, barrier):
        self.barrier = barrier
        self.clouds = CloudField()
        self.black_holes = []
        self.neutron_stars = []
        self.magnetars = []
        self.white_dwarfs = []
        self.black_hole_pulses = []
        self.pending_rip_bhs = []  # black holes in this universe that reached rip mass this step
        self.metallicity = 0.0  # Z in [0,1]: chemical age, ratcheted up by enrichment events
        self.local = LocalPhysics()  # this universe's own constants (mutated at rip, see class)
        self.event_log = []     # astrophysical events this step, drained into the HUD ticker

    def star_formation_efficiency(self):
        """Quenching: merge chances scale by (1-Z)^exponent, so the metallicity ratchet
        doubles as a thermodynamic age. Chemically completed gas stops making stars and a
        universe can die quietly of exhaustion — the arrow of time points at heat death."""
        return (1.0 - self.metallicity) ** STAR_FORMATION_QUENCH_EXPONENT


class SimulationState:
    """The multiverse: a list of Universes. Universes never interact gravitationally — only
    their barriers push/deform each other."""
    def __init__(self):
        self.universes = []
        self.entropy_pool = EntropyPool()

    def entity_count(self):
        return sum(u.clouds.n + len(u.black_holes) + len(u.neutron_stars) + len(u.magnetars)
                   + len(u.white_dwarfs)
                   for u in self.universes)

    def total_mass(self):
        return sum(float(u.clouds.M.sum())
                   + sum(bh.mass for bh in u.black_holes)
                   + sum(ns.mass for ns in u.neutron_stars)
                   + sum(m.mass for m in u.magnetars)
                   + sum(wd.mass for wd in u.white_dwarfs)
                   for u in self.universes)

    def mean_metallicity(self):
        if not self.universes:
            return 0.0
        return sum(u.metallicity for u in self.universes) / len(self.universes)


def _spawn_size(mass):
    return max(MOLECULAR_CLOUD_MIN_SIZE,
               MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))


def handle_collisions(universe):
    """Cloud-cloud merge pass. The compiled path reads/writes the field arrays directly.
    The merge chance carries this universe's fusion dial and its quenching factor."""
    clouds = universe.clouds
    n = clouds.n
    if n < 2:
        return
    merge_chance = (MOLECULAR_CLOUD_MERGE_CHANCE * universe.local.fusion
                    * universe.star_formation_efficiency())
    removed = np.zeros(n, dtype=np.uint8)
    if _fastphysics is not None:
        _fastphysics.collide(clouds.X, clouds.Y, clouds.SIZE, clouds.M, clouds.VX, clouds.VY,
                             clouds.ELEM, removed, n,
                             merge_chance, PROTOSTAR_THRESHOLD, MOLECULAR_CLOUD_MAX_MASS,
                             MOLECULAR_CLOUD_START_SIZE, MOLECULAR_CLOUD_MIN_SIZE,
                             MOLECULAR_CLOUD_START_MASS, MOLECULAR_CLOUD_GROWTH_RATE)
    else:
        _collide_python(clouds, removed, n, merge_chance)
    if removed.any():
        clouds.keep(removed == 0)


def _collide_python(clouds, removed, n, merge_chance):
    """Pure-Python port of fastphysics.collide (fallback when the extension isn't built)."""
    x, y, size, mass = clouds.X, clouds.Y, clouds.SIZE, clouds.M
    vx, vy, elem = clouds.VX, clouds.VY, clouds.ELEM
    for i in range(n):
        if removed[i]:
            continue
        for j in range(n):
            if j == i or removed[j]:
                continue
            is_proto = mass[i] >= PROTOSTAR_THRESHOLD or mass[j] >= PROTOSTAR_THRESHOLD
            if not (is_proto or abs(int(elem[i]) - int(elem[j])) <= 1):
                continue
            if not (x[i] < x[j] + size[j] and x[i] + size[i] > x[j]
                    and y[i] < y[j] + size[j] and y[i] + size[i] > y[j]):
                continue
            if random.random() >= merge_chance:
                continue
            surv, cons = (j, i) if elem[j] > elem[i] else (i, j)
            merged = mass[surv] + mass[cons]
            if merged > 0:
                vx[surv] = (mass[surv] * vx[surv] + mass[cons] * vx[cons]) / merged
                vy[surv] = (mass[surv] * vy[surv] + mass[cons] * vy[cons]) / merged
            mass[surv] = min(merged, MOLECULAR_CLOUD_MAX_MASS)
            size[surv] = _spawn_size(mass[surv])
            removed[cons] = 1
            if cons == i:
                break


def _triggered_mergers(universe):
    """Shock-triggered star formation: clouds a wavefront just compressed (shock timer > 0)
    merge at a much higher rate than the ambient pass — supernova shocks beget the next
    generation of stars. Same overlap/element rules as the base collide, boosted chance,
    restricted to shocked-shocked pairs (a small set, so the scalar pair loop stays cheap)."""
    clouds = universe.clouds
    n = clouds.n
    if n < 2:
        return
    shocked = np.nonzero(clouds.SHOCK > 0.0)[0]
    if len(shocked) < 2:
        return
    merge_chance = SHOCK_MERGE_CHANCE * universe.local.fusion * universe.star_formation_efficiency()
    if _fastphysics is not None and hasattr(_fastphysics, 'collide_shocked'):
        # Compiled path: same upper-triangle/one-roll-per-pair statistics as the loop below,
        # which stays as the semantic reference. Sustained pulse activity can shock hundreds
        # of clouds at once, and the Python pair loop was the multiverse frame-time leader.
        removed_u8 = np.zeros(n, dtype=np.uint8)
        _fastphysics.collide_shocked(
            np.ascontiguousarray(shocked), clouds.X, clouds.Y, clouds.SIZE, clouds.M,
            clouds.VX, clouds.VY, clouds.ELEM, removed_u8, len(shocked),
            merge_chance, PROTOSTAR_THRESHOLD, MOLECULAR_CLOUD_MAX_MASS,
            MOLECULAR_CLOUD_START_SIZE, MOLECULAR_CLOUD_MIN_SIZE,
            MOLECULAR_CLOUD_START_MASS, MOLECULAR_CLOUD_GROWTH_RATE)
        if removed_u8.any():
            clouds.keep(removed_u8 == 0)
        return
    x, y, size, mass = clouds.x, clouds.y, clouds.size, clouds.mass
    vx, vy, elem = clouds.vx, clouds.vy, clouds.elem
    removed = np.zeros(n, dtype=bool)
    for a in range(len(shocked)):
        i = shocked[a]
        if removed[i]:
            continue
        for b in range(a + 1, len(shocked)):
            j = shocked[b]
            if removed[j]:
                continue
            is_proto = mass[i] >= PROTOSTAR_THRESHOLD or mass[j] >= PROTOSTAR_THRESHOLD
            if not (is_proto or abs(int(elem[i]) - int(elem[j])) <= 1):
                continue
            if not (x[i] < x[j] + size[j] and x[i] + size[i] > x[j]
                    and y[i] < y[j] + size[j] and y[i] + size[i] > y[j]):
                continue
            if random.random() >= merge_chance:
                continue
            surv, cons = (j, i) if elem[j] > elem[i] else (i, j)
            merged = mass[surv] + mass[cons]
            if merged > 0:
                vx[surv] = (mass[surv] * vx[surv] + mass[cons] * vx[cons]) / merged
                vy[surv] = (mass[surv] * vy[surv] + mass[cons] * vy[cons]) / merged
            mass[surv] = min(merged, MOLECULAR_CLOUD_MAX_MASS)
            size[surv] = _spawn_size(mass[surv])
            removed[cons] = True
            if cons == i:
                break
    if removed.any():
        clouds.keep(~removed[:n])


def update_entities(universe):
    """Collisions, star transitions, and the per-cloud random events (collapse to BH/NS,
    supernova, white-dwarf retirement, emission). Fate follows MASS, as in reality: only
    stars above BLACK_HOLE_THRESHOLD can die violently; everything below quietly becomes a
    white dwarf. The event loop stays scalar: events are rare and branchy."""
    handle_collisions(universe)
    _triggered_mergers(universe)
    clouds = universe.clouds
    clouds.refresh()

    # The old scalar loop rolled `random.random()` per cloud per frame. Restructured into
    # three candidate passes with the same per-cloud Bernoulli statistics: heavy stars stay
    # scalar in row order (the BH cap check is sequential), while the every-star WD roll and
    # the every-eligible-cloud emission roll become single vectorized draws whose HITS take
    # the branchy path. Only the draw stream changes — statistics, not physics.
    to_remove = np.zeros(clouds.n, dtype=bool)
    spawns = []  # (x, y, mass, elem_index, vx, vy) — batch-applied via spawn_batch
    n = clouds.n
    mass = clouds.mass
    elem = clouds.elem

    # ── Heavy stars: collapse or supernova (scalar, row order — cap fills sequentially) ──
    a_entered = np.zeros(n, dtype=bool)
    for k in np.nonzero(mass[:n] > BLACK_HOLE_THRESHOLD)[0]:
        if len(universe.black_holes) >= BLACK_HOLE_MAX_COUNT:
            continue  # cap full: this cloud falls through to the emission pass, as the old elif chain did
        a_entered[k] = True
        # Fate is a steep function of mass: the heaviest stars collapse soonest.
        mass_ratio = mass[k] / BLACK_HOLE_THRESHOLD
        if random.random() < BLACK_HOLE_CHANCE * universe.local.collapse * mass_ratio ** COLLAPSE_MASS_EXPONENT:
            # The star's own metallicity biases the remnant: metal-rich stars shed mass
            # in winds and tend to leave neutron stars; metal-poor ones collapse to holes.
            bias = COLLAPSE_NS_METALLICITY_BIAS if elem[k] >= STAR_ENRICHED_ELEMENT_MIN else -COLLAPSE_NS_METALLICITY_BIAS
            if random.random() < NEUTRON_STAR_CHANCE + bias:
                # A small fraction of neutron-star births come out as magnetars, so the
                # black-hole formation rate (which drives the matter cycle) is untouched.
                if random.random() < MAGNETAR_CHANCE:
                    universe.magnetars.append(Magnetar(clouds.x[k], clouds.y[k], mass[k]))
                    universe.event_log.append("CORE COLLAPSE — a magnetar is born")
                else:
                    universe.neutron_stars.append(NeutronStar(clouds.x[k], clouds.y[k], mass[k]))
                    universe.event_log.append("CORE COLLAPSE — a pulsar is born")
            else:
                universe.black_holes.append(BlackHole(clouds.x[k], clouds.y[k], mass[k]))
                universe.event_log.append("CORE COLLAPSE — star implodes into a black hole")
            to_remove[k] = True
        elif random.random() < MOLECULAR_CLOUD_DEFAULT_STATE_CHANCE * mass_ratio ** SUPERNOVA_LIFETIME_MASS_EXPONENT:
            # Core-collapse supernova: the star resets to a light gas cloud and ejects
            # material whose composition reflects the universe's chemical age.
            ejecta_count = SUPERNOVA_EJECTA_COUNT_BASE + int((mass[k] - BLACK_HOLE_THRESHOLD) * SUPERNOVA_EJECTA_COUNT_PER_MASS)
            sn_abundance = blend_abundance(EJECTA_ELEMENTAL_ABUNDANCE,
                                           BLACK_HOLE_DECAY_ELEMENTAL_ABUNDANCE, universe.metallicity)
            for _ in range(ejecta_count):
                offset_angle = random.uniform(0, 2 * math.pi)
                offset_dist = random.uniform(5, SUPERNOVA_EJECTA_SPREAD)
                ex = clouds.x[k] + offset_dist * math.cos(offset_angle)
                ey = clouds.y[k] + offset_dist * math.sin(offset_angle)
                emass = random.uniform(MOLECULAR_CLOUD_START_MASS, PROTOSTAR_THRESHOLD * SUPERNOVA_EJECTA_MAX_MASS_FRACTION)
                child_elem = pick_element(sn_abundance)
                spawns.append((ex, ey, emass, child_elem,
                               math.cos(offset_angle) * offset_dist * 0.5,
                               math.sin(offset_angle) * offset_dist * 0.5))
            mass[k] = MOLECULAR_CLOUD_START_MASS
            clouds.is_star[k] = False
            clouds.size[k] = MOLECULAR_CLOUD_START_SIZE
            universe.metallicity = min(1.0, universe.metallicity + METALLICITY_PER_SUPERNOVA)
            universe.event_log.append("SUPERNOVA (TYPE II) — massive star explodes, seeding metals")

    # ── Sub-massive stars: white-dwarf retirement (one vectorized roll over all stars) ──
    star_idx = np.nonzero(clouds.IS_STAR & (clouds.M < STAR_TIER_HIGH_MASS))[0]
    if len(star_idx):
        wd_chance = (WHITE_DWARF_CHANCE
                     * (clouds.M[star_idx] / STAR_TIER_HIGH_MASS) ** WHITE_DWARF_LIFETIME_MASS_EXPONENT)
        star_idx = star_idx[np.random.random(len(star_idx)) < wd_chance]
    for k in star_idx:
        # The common stellar ending: no explosion. The star sheds its envelope as a
        # planetary nebula (light elements drift back to the cloud sea) and the core
        # remains as a white dwarf that will spend a long time cooling.
        for _ in range(PLANETARY_NEBULA_EJECTA_COUNT):
            offset_angle = random.uniform(0, 2 * math.pi)
            offset_dist = random.uniform(4, PLANETARY_NEBULA_SPREAD)
            ex = clouds.x[k] + offset_dist * math.cos(offset_angle)
            ey = clouds.y[k] + offset_dist * math.sin(offset_angle)
            emass = random.uniform(MOLECULAR_CLOUD_START_MASS,
                                   mass[k] * (1.0 - WHITE_DWARF_MASS_FRACTION) / PLANETARY_NEBULA_EJECTA_COUNT * 2)
            child_elem = pick_element(EJECTA_ELEMENTAL_ABUNDANCE)
            spawns.append((ex, ey, emass, child_elem,
                           math.cos(offset_angle) * offset_dist * 0.4,
                           math.sin(offset_angle) * offset_dist * 0.4))
        wd = WhiteDwarf(clouds.x[k], clouds.y[k], mass[k] * WHITE_DWARF_MASS_FRACTION)
        wd.vx, wd.vy = clouds.vx[k], clouds.vy[k]
        universe.white_dwarfs.append(wd)
        to_remove[k] = True
        universe.metallicity = min(1.0, universe.metallicity + METALLICITY_PER_NEBULA)
        universe.event_log.append("PLANETARY NEBULA — a star retires as a white dwarf")

    # ── Emission: clouds shed small daughter clouds (one vectorized roll over eligibles) ──
    eligible = ((clouds.M >= MOLECULAR_CLOUD_EMISSION_MIN_PARENT_MASS)
                & (clouds.emission_count[:n] < MOLECULAR_CLOUD_EMISSION_COUNT)
                & ~to_remove & ~a_entered)
    c_idx = np.nonzero(eligible)[0]
    if len(c_idx):
        c_idx = c_idx[np.random.random(len(c_idx)) < MOLECULAR_CLOUD_EMISSION_CHANCE]
    for k in c_idx:
        emit_mass = random.uniform(MOLECULAR_CLOUD_EMISSION_MASS_MIN, MOLECULAR_CLOUD_EMISSION_MASS_MAX)
        offset_angle = random.uniform(0, 2 * math.pi)
        offset_dist = random.uniform(2, MOLECULAR_CLOUD_EMISSION_SPREAD)
        spawns.append((clouds.x[k] + offset_dist * math.cos(offset_angle),
                       clouds.y[k] + offset_dist * math.sin(offset_angle),
                       emit_mass, int(elem[k]),
                       clouds.vx[k] + math.cos(offset_angle) * MOLECULAR_CLOUD_EMISSION_VELOCITY,
                       clouds.vy[k] + math.sin(offset_angle) * MOLECULAR_CLOUD_EMISSION_VELOCITY))
        clouds.emission_count[k] += 1

    if to_remove.any():
        clouds.keep(~to_remove)
    clouds.spawn_batch(spawns)

    # Hard cap on clouds per universe: bounds per-frame physics + rendering cost. Trim the
    # lowest-mass clouds when over the cap (rows end up mass-sorted, as the old list.sort did).
    if clouds.n > MOLECULAR_CLOUD_MAX_PER_UNIVERSE:
        order = np.argsort(-clouds.M, kind='stable')[:MOLECULAR_CLOUD_MAX_PER_UNIVERSE]
        clouds.select(order)


def _update_bh_pulses(universe, ring, delta_time):
    """Expanding gravitational-wave pulses from BH mergers / kilonovae: push matter in the
    wavefront band, draining a shared per-pulse energy budget in row order (prefix-sum
    reproduces the sequential drain exactly), then ripple the barrier."""
    clouds = universe.clouds
    pulses_to_remove = []
    for i, pulse in enumerate(universe.black_hole_pulses):
        x, y, radius, consumed_mass = pulse
        new_radius = radius + (NEUTRON_STAR_RIPPLE_SPEED * delta_time * BLACK_HOLE_PULSE_SPEED_MULTIPLIER)
        universe.black_hole_pulses[i] = [x, y, new_radius, consumed_mass]

        energy_budget = consumed_mass
        mass_scale = consumed_mass / BLACK_HOLE_PULSE_MASS_SCALE
        entity_mass_scale = mass_scale * BLACK_HOLE_PULSE_ENTITY_FACTOR
        bh_ew = NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3

        if clouds.n and energy_budget > 0:
            dx = clouds.X - x
            dy = clouds.Y - y
            dist_sq = dx * dx + dy * dy
            r_inner = max(0, radius - bh_ew)
            r_outer = radius + bh_ew
            in_annulus = (dist_sq >= r_inner * r_inner) & (dist_sq <= r_outer * r_outer)
            distance = np.sqrt(np.where(in_annulus, dist_sq, 1.0))
            ripple = np.abs(distance - radius)
            band = in_annulus & (ripple < bh_ew) & (distance > 0)
            force = np.where(band,
                             NEUTRON_STAR_PULSE_STRENGTH * 3 * (1.0 - ripple / bh_ew) * entity_mass_scale
                             / ((ripple + 1) ** 1.5), 0.0)
            spent = force * delta_time * 0.01
            budget_before = energy_budget - (np.cumsum(spent) - spent)
            apply = band & (budget_before > 0)
            if apply.any():
                push = np.where(apply, force * delta_time, 0.0)
                clouds.VX += (dx / distance) * push
                clouds.VY += (dy / distance) * push
                energy_budget -= float(spent[apply].sum())
                # Compression in the wavefront triggers star formation (see _triggered_mergers).
                clouds.SHOCK = np.where(apply, SHOCK_DURATION, clouds.SHOCK)

        for black_hole in universe.black_holes:
            if energy_budget <= 0:
                break
            dx = black_hole.x - x
            dy = black_hole.y - y
            distance = math.hypot(dx, dy)
            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 4:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 4))
                force = NEUTRON_STAR_PULSE_STRENGTH * 2 * effect_factor * entity_mass_scale / ((ripple_dist + 1) ** 2)
                if distance > 0:
                    black_hole.vx += (dx / distance) * force * delta_time
                    black_hole.vy += (dy / distance) * force * delta_time
                    energy_budget -= force * delta_time * 0.01

        for neutron_star in (*universe.neutron_stars, *universe.magnetars):
            if energy_budget <= 0:
                break
            dx = neutron_star.x - x
            dy = neutron_star.y - y
            distance = math.hypot(dx, dy)
            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3))
                force = NEUTRON_STAR_PULSE_STRENGTH * 2.5 * effect_factor * entity_mass_scale / ((ripple_dist + 1) ** 1.8)
                if distance > 0:
                    neutron_star.vx += (dx / distance) * force * delta_time
                    neutron_star.vy += (dy / distance) * force * delta_time
                    energy_budget -= force * delta_time * 0.01

        universe.black_hole_pulses[i][3] = max(0, energy_budget)

        # Barrier ripple where the wavefront crosses the ring.
        cx, cy = ring.center
        pulse_fade = max(0.0, 1.0 - new_radius / ring.rest_radius)
        bx = cx + ring.radii * ring.cos_a
        by = cy + ring.radii * ring.sin_a
        hit = np.abs(np.hypot(bx - x, by - y) - new_radius) < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 4
        if hit.any():
            ring.flash[hit] = np.maximum(ring.flash[hit], pulse_fade * 0.9)
            ring.radii_vel[hit] += BARRIER_WAVE_PUSH * 2.0 * mass_scale * pulse_fade * delta_time

        if new_radius > float(ring.radii.max()):
            pulses_to_remove.append(i)

    for i in sorted(pulses_to_remove, reverse=True):
        if i < len(universe.black_hole_pulses):
            universe.black_hole_pulses.pop(i)


def resolve_pulse_collisions(universe, delta_time):
    all_pulses = []
    for ns in universe.neutron_stars:
        for i, pulse in enumerate(ns.active_pulses):
            all_pulses.append((ns, i))

    for a in range(len(all_pulses)):
        ns_a, idx_a = all_pulses[a]
        pulse_a = ns_a.active_pulses[idx_a]
        r_a = pulse_a[0]
        for b in range(a + 1, len(all_pulses)):
            ns_b, idx_b = all_pulses[b]
            pulse_b = ns_b.active_pulses[idx_b]
            r_b = pulse_b[0]
            d = math.hypot(ns_a.x - ns_b.x, ns_a.y - ns_b.y)
            wavefront_gap = d - r_a - r_b
            if wavefront_gap < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2:
                overlap = 1.0 - max(wavefront_gap, 0) / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2)
                fade_rate = PULSE_COLLISION_FADE_RATE * overlap
                pulse_a[2] -= fade_rate * delta_time
                pulse_b[2] -= fade_rate * delta_time


def step(universe, ring, delta_time):
    """One physics step for one universe (the old update_simulation_state)."""
    clouds = universe.clouds

    # Cloud/star mutual gravity (backend-dispatched: GPU / Barnes-Hut / brute / local).
    # Force is linear in G, so this universe's local gravity dial scales the summed output —
    # no backend needs to know about it.
    if clouds.n >= 2:
        fx, fy = gravity.cloud_forces(clouds.X, clouds.Y, clouds.M, clouds.IS_STAR)
        clouds.VX += fx * (universe.local.g * delta_time)
        clouds.VY += fy * (universe.local.g * delta_time)

    update_entities(universe)

    ring.apply_gravity(universe, delta_time)
    ring.enforce(universe, delta_time)

    for black_hole in universe.black_holes:
        # Tracer rotation driven by angular momentum (with base rotation)
        spin_rate = BLACK_HOLE_DISK_ROTATION + black_hole.angular_momentum / max(black_hole.mass, 1.0)
        black_hole.tracer_angle += spin_rate * delta_time
        # Gradually dissipate angular momentum
        black_hole.angular_momentum *= BLACK_HOLE_ANGULAR_MOMENTUM_DISSIPATION ** delta_time

    _update_bh_pulses(universe, ring, delta_time)

    # ── Black-hole pass ──
    alive = np.ones(clouds.n, dtype=bool)
    stream_moves = []
    ns_to_remove = set()
    bh_to_remove = set()
    spawns = []

    for black_hole in universe.black_holes:
        if black_hole in bh_to_remove:
            continue
        black_hole.attract(universe, delta_time, alive, stream_moves, ns_to_remove, bh_to_remove)
        black_hole.decay(delta_time)
        # A hole that grows to near-max "rips" open a new universe and then streams matter into it.
        # It only rips once (while it has a child); if that child later dies, it can rip again.
        rip_mass = BLACK_HOLE_RIP_MASS_FACTOR * BLACK_HOLE_MAX_MASS
        if black_hole.child_universe is None and black_hole.mass >= rip_mass:
            universe.pending_rip_bhs.append(black_hole)
        if black_hole.mass <= BLACK_HOLE_DECAY_THRESHOLD:
            bh_to_remove.add(black_hole)
            universe.event_log.append("BLACK HOLE EVAPORATED — Hawking radiation wins in the end")
            for _ in range(BLACK_HOLE_DECAY_CLOUD_COUNT):
                offset_angle = random.uniform(0, 2 * math.pi)
                offset_dist = random.uniform(5, BLACK_HOLE_DECAY_EJECTA_SPREAD)
                ex = black_hole.x + offset_dist * math.cos(offset_angle)
                ey = black_hole.y + offset_dist * math.sin(offset_angle)
                emass = random.uniform(BLACK_HOLE_DECAY_CLOUD_MASS_MIN, BLACK_HOLE_DECAY_CLOUD_MASS_MAX)
                child_elem = pick_element(BLACK_HOLE_DECAY_ELEMENTAL_ABUNDANCE)
                spawns.append((ex, ey, emass, child_elem,
                               math.cos(offset_angle) * offset_dist * 0.5,
                               math.sin(offset_angle) * offset_dist * 0.5))

    # ── Neutron-star pass (sees captured clouds, as the object version did) ──
    for neutron_star in universe.neutron_stars:
        if neutron_star in ns_to_remove:
            continue
        neutron_star.apply_gravity(universe, delta_time)
        neutron_star.update_pulse(universe, ring, delta_time)
        neutron_star.decay(delta_time)
        if neutron_star.mass <= NEUTRON_STAR_DECAY_THRESHOLD:
            # A dead pulsar dissipates QUIETLY — a few cold clouds, no pulse, no fireworks.
            # (Kilonovae are exclusively mergers now, as in reality; this slow crumble is the
            # matter-cycle concession that returns locked-up neutron-star mass to the gas.)
            ns_to_remove.add(neutron_star)
            remnant_abundance = blend_abundance(EJECTA_ELEMENTAL_ABUNDANCE,
                                                BLACK_HOLE_DECAY_ELEMENTAL_ABUNDANCE, universe.metallicity)
            for _ in range(PULSAR_REMNANT_CLOUD_COUNT):
                offset_angle = random.uniform(0, 2 * math.pi)
                offset_dist = random.uniform(4, PULSAR_REMNANT_SPREAD)
                ex = neutron_star.x + offset_dist * math.cos(offset_angle)
                ey = neutron_star.y + offset_dist * math.sin(offset_angle)
                emass = random.uniform(2, 8)
                child_elem = pick_element(remnant_abundance)
                spawns.append((ex, ey, emass, child_elem,
                               math.cos(offset_angle) * offset_dist * 0.3,
                               math.sin(offset_angle) * offset_dist * 0.3))

    # ── Magnetar pass ──
    for magnetar in universe.magnetars:
        if magnetar in ns_to_remove:
            continue
        magnetar.apply_gravity(universe, delta_time)
        magnetar.apply_magnetism(universe, delta_time)
        magnetar.update_field(universe, delta_time)
        magnetar.decay(delta_time)
        if magnetar.field_time <= 0 or magnetar.mass <= NEUTRON_STAR_DECAY_THRESHOLD:
            # The field dies: the magnetar settles into a plain neutron star. (If mass is
            # already below the NS decay threshold, the NS pass turns it into a kilonova
            # next frame — no duplicated ejecta path here.)
            ns_to_remove.add(magnetar)
            settled = NeutronStar(magnetar.x, magnetar.y, magnetar.mass)
            settled.vx, settled.vy = magnetar.vx, magnetar.vy
            universe.neutron_stars.append(settled)

    # ── White-dwarf pass ──
    # White dwarfs only cool. Once fully cooled they are black dwarfs — invisible against
    # space — and are removed. Two that collide detonate as a Type Ia supernova: total
    # thermonuclear destruction, no remnant, and a spray of iron-peak elements.
    for wd in universe.white_dwarfs:
        if wd in ns_to_remove:
            continue
        wd.age += delta_time
        if wd.age >= WHITE_DWARF_COOL_TIME:
            ns_to_remove.add(wd)
            universe.event_log.append("BLACK DWARF — a white dwarf finishes cooling, fades from view")
    alive_wd = [wd for wd in universe.white_dwarfs if wd not in ns_to_remove]
    for i in range(len(alive_wd)):
        if alive_wd[i] in ns_to_remove:
            continue
        for j in range(i + 1, len(alive_wd)):
            if alive_wd[j] in ns_to_remove:
                continue
            wd_a, wd_b = alive_wd[i], alive_wd[j]
            if math.hypot(wd_a.x - wd_b.x, wd_a.y - wd_b.y) < TYPE_IA_COLLISION_DISTANCE:
                ns_to_remove.add(wd_a)
                ns_to_remove.add(wd_b)
                cx = (wd_a.x + wd_b.x) / 2
                cy = (wd_a.y + wd_b.y) / 2
                for _ in range(TYPE_IA_EJECTA_COUNT):
                    offset_angle = random.uniform(0, 2 * math.pi)
                    offset_dist = random.uniform(5, TYPE_IA_EJECTA_SPREAD)
                    ex = cx + offset_dist * math.cos(offset_angle)
                    ey = cy + offset_dist * math.sin(offset_angle)
                    emass = random.uniform(MOLECULAR_CLOUD_START_MASS, PROTOSTAR_THRESHOLD * SUPERNOVA_EJECTA_MAX_MASS_FRACTION)
                    child_elem = pick_element(TYPE_IA_ELEMENTAL_ABUNDANCE)
                    spawns.append((ex, ey, emass, child_elem,
                                   math.cos(offset_angle) * offset_dist * 0.5,
                                   math.sin(offset_angle) * offset_dist * 0.5))
                universe.black_hole_pulses.append([cx, cy, 0, wd_a.mass + wd_b.mass])
                universe.metallicity = min(1.0, universe.metallicity + METALLICITY_PER_TYPE_IA)
                universe.event_log.append("SUPERNOVA (TYPE IA) — white dwarfs detonate, forging iron")
                break

    # NS-NS Kilonova mergers (magnetars merge like any neutron star)
    alive_ns = [ns for ns in (*universe.neutron_stars, *universe.magnetars) if ns not in ns_to_remove]
    merged_ns = set()
    for i in range(len(alive_ns)):
        if alive_ns[i] in merged_ns:
            continue
        for j in range(i + 1, len(alive_ns)):
            if alive_ns[j] in merged_ns:
                continue
            dx = alive_ns[i].x - alive_ns[j].x
            dy = alive_ns[i].y - alive_ns[j].y
            if math.hypot(dx, dy) < KILONOVA_COLLISION_DISTANCE:
                ns_a, ns_b = alive_ns[i], alive_ns[j]
                merged_ns.add(ns_a)
                merged_ns.add(ns_b)
                ns_to_remove.add(ns_a)
                ns_to_remove.add(ns_b)
                cx = (ns_a.x + ns_b.x) / 2
                cy = (ns_a.y + ns_b.y) / 2
                combined_mass = ns_a.mass + ns_b.mass
                for _ in range(KILONOVA_EJECTA_COUNT):
                    offset_angle = random.uniform(0, 2 * math.pi)
                    offset_dist = random.uniform(5, KILONOVA_EJECTA_SPREAD)
                    ex = cx + offset_dist * math.cos(offset_angle)
                    ey = cy + offset_dist * math.sin(offset_angle)
                    emass = random.uniform(MOLECULAR_CLOUD_START_MASS, PROTOSTAR_THRESHOLD * SUPERNOVA_EJECTA_MAX_MASS_FRACTION)
                    child_elem = pick_element(KILONOVA_ELEMENTAL_ABUNDANCE)
                    spawns.append((ex, ey, emass, child_elem,
                                   math.cos(offset_angle) * offset_dist * 0.5,
                                   math.sin(offset_angle) * offset_dist * 0.5))
                universe.black_hole_pulses.append([cx, cy, 0, combined_mass])
                universe.metallicity = min(1.0, universe.metallicity + METALLICITY_PER_KILONOVA)
                # The remnant depends on the combined mass (the GW170817 lesson): light pairs
                # leave a hypermassive magnetar, heavy pairs collapse straight to a black hole.
                rem_vx = (ns_a.mass * ns_a.vx + ns_b.mass * ns_b.vx) / combined_mass
                rem_vy = (ns_a.mass * ns_a.vy + ns_b.mass * ns_b.vy) / combined_mass
                if combined_mass < KILONOVA_MAGNETAR_REMNANT_MAX:
                    remnant = Magnetar(cx, cy, combined_mass)
                    remnant.vx, remnant.vy = rem_vx, rem_vy
                    universe.magnetars.append(remnant)
                    universe.event_log.append("KILONOVA — neutron stars merge; gold forged, magnetar left")
                else:
                    new_bh = BlackHole(cx, cy, combined_mass)
                    new_bh.vx, new_bh.vy = rem_vx, rem_vy
                    universe.black_holes.append(new_bh)
                    universe.event_log.append("KILONOVA — neutron stars merge; gold forged, black hole left")
                break

    resolve_pulse_collisions(universe, delta_time)

    # ── Removals, wormhole streams, event spawns ──
    if stream_moves:
        # Streamed rows already carry their child-universe position: copy them to their
        # destinations first (indices still valid), then one compaction drops all captured
        # rows — accreted and streamed alike (alive is False for both).
        by_dst = {}
        for row, dst in stream_moves:
            by_dst.setdefault(id(dst), (dst, []))[1].append(row)
        for _, (dst, rows) in by_dst.items():
            clouds.copy_rows(dst.clouds, rows)
    if not alive.all():
        clouds.keep(alive)
    if bh_to_remove:
        universe.black_holes = [bh for bh in universe.black_holes if bh not in bh_to_remove]
    if ns_to_remove:
        universe.neutron_stars = [ns for ns in universe.neutron_stars if ns not in ns_to_remove]
        universe.magnetars = [m for m in universe.magnetars if m not in ns_to_remove]
        universe.white_dwarfs = [wd for wd in universe.white_dwarfs if wd not in ns_to_remove]
    clouds.spawn_batch(spawns)

    # ── Integration (semi-implicit Euler, kick→drift: damp velocity, then move with the new
    # velocity). Not symplectic — that's a property of Hamiltonian systems and this one is
    # dissipative by design: structure comes from damping and attractors, not conserved energy. ──
    damping = VELOCITY_DAMPING ** delta_time
    clouds.VX *= damping
    clouds.VY *= damping
    clouds.X += clouds.VX * delta_time
    clouds.Y += clouds.VY * delta_time
    clouds.SHOCK = np.maximum(clouds.SHOCK - delta_time, 0.0)  # shock compression relaxes
    # Absolute anchoring: strong velocity damping so holes act as fixed galactic centers.
    bh_damping = BLACK_HOLE_VELOCITY_DAMPING ** delta_time
    for bh in universe.black_holes:
        bh.vx *= bh_damping * damping
        bh.vy *= bh_damping * damping
        bh.x += bh.vx * delta_time
        bh.y += bh.vy * delta_time
    # Dense compact objects get heavy dynamical friction too — anchored like black holes,
    # just less strongly — so BH kicks and cloud-pull recoil don't fling them across the ring.
    ns_damping = NEUTRON_STAR_VELOCITY_DAMPING ** delta_time
    for ns in (*universe.neutron_stars, *universe.magnetars, *universe.white_dwarfs):
        ns.vx *= ns_damping * damping
        ns.vy *= ns_damping * damping
        ns.x += ns.vx * delta_time
        ns.y += ns.vy * delta_time


# ── Multiverse mechanics ────────────────────────────────────────────────────────────────────

def spawn_universe(center):
    """Create a fresh universe: a tiny barrier at `center` seeded with a Big-Bang of clouds."""
    cx, cy = center
    ring = Barrier(center, (BARRIER_INITIAL_SIZE, BARRIER_INITIAL_SIZE), BARRIER_POINT_COUNT)
    universe = Universe(ring)

    # Scalar running sums on purpose: bit-identical to the historical init (np.sum's pairwise
    # accumulation differs in the last ulp, enough to flip which weight bucket a draw lands in).
    density_weights = [max(0.0, 1.0 - CMB_DENSITY_CONTRAST * float(p)) for p in ring.perturbation]
    total_weight = sum(density_weights)
    density_weights = [w / total_weight for w in density_weights]
    cumulative = []
    running_sum = 0.0
    for w in density_weights:
        running_sum += w
        cumulative.append(running_sum)
    cumulative = np.array(cumulative)

    step_a = 2 * math.pi / ring.num_points
    for _ in range(MOLECULAR_CLOUD_COUNT):
        r = random.random()
        idx = min(int(np.searchsorted(cumulative, r, side='left')), ring.num_points - 1)
        angle = ring.angles[idx] + random.uniform(0, step_a)
        local_radius = ring.get_radius_at_angle(angle)
        radius = math.sqrt(random.uniform(0, 1)) * local_radius
        universe.clouds.spawn(cx + radius * math.cos(angle), cy + radius * math.sin(angle),
                              MOLECULAR_CLOUD_START_MASS, abundance=SEED_ELEMENTAL_ABUNDANCE)
    return universe


def _clear_of_all(state, x, y, new_radius):
    """Clear if the new barrier keeps UNIVERSE_SPAWN_GAP to each existing barrier's LOCAL
    edge (its radius toward the candidate point, not the global max — a bulge on the far
    side of a deformed neighbour shouldn't push spawns away from this side), so newborn
    universes can nestle into the contours of the cluster."""
    for u in state.universes:
        ucx, ucy = u.barrier.center
        dx, dy = x - ucx, y - ucy
        dist = math.hypot(dx, dy)
        local_r = u.barrier.get_radius_at_angle(math.atan2(dy, dx) % (2 * math.pi))
        if dist <= local_r + new_radius + UNIVERSE_SPAWN_GAP:
            return False
    return True


def _find_spawn_center(state, new_radius, source=None, bh=None):
    """Find a point for a new barrier that doesn't overlap any existing one. Preferred spot: just
    outside the SOURCE barrier in the direction of the ripping black hole."""
    if source is not None and bh is not None:
        scx, scy = source.barrier.center
        angle = math.atan2(bh.y - scy, bh.x - scx)
        edge = source.barrier.get_radius_at_angle(angle % (2 * math.pi))
        for extra in range(0, 800, 10):
            dist = edge + new_radius + UNIVERSE_SPAWN_GAP + extra
            x = scx + dist * math.cos(angle)
            y = scy + dist * math.sin(angle)
            if _clear_of_all(state, x, y, new_radius):
                return (x, y)
    if state.universes:
        cx = sum(u.barrier.center[0] for u in state.universes) / len(state.universes)
        cy = sum(u.barrier.center[1] for u in state.universes) / len(state.universes)
    else:
        cx, cy = SCREEN_WIDTH / 2.0, SCREEN_HEIGHT / 2.0
    for attempt in range(400):
        angle = random.uniform(0, 2 * math.pi)
        dist = 40 + attempt * 8
        x = cx + dist * math.cos(angle)
        y = cy + dist * math.sin(angle)
        if _clear_of_all(state, x, y, new_radius):
            return (x, y)
    return (x, y)  # fallback: accept the last candidate even if tight


def _rip_universe(source, center):
    """Rip open a new universe by pulling a chunk of the SOURCE universe's clouds through into
    it, keeping the multiverse's total entity count bounded."""
    cx, cy = center
    ring = Barrier(center, (BARRIER_INITIAL_SIZE, BARRIER_INITIAL_SIZE), BARRIER_POINT_COUNT)
    new_u = Universe(ring)
    # The child is built from the parent's matter, so it inherits the parent's chemical age —
    # and the parent's physics, with a small mutation (see LocalPhysics: heredity + variation).
    new_u.metallicity = source.metallicity
    new_u.local = source.local.mutated()
    clouds = source.clouds
    move_count = int(clouds.n * UNIVERSE_RIP_TRANSFER_FRACTION)
    if move_count <= 0:
        return new_u
    order = list(range(clouds.n))
    random.shuffle(order)  # same draw count as shuffling the old object list
    clouds.select(np.asarray(order))
    moved_rows = list(range(move_count))
    rr = ring.rest_radius
    dst_rows = clouds.move_rows(new_u.clouds, moved_rows)
    for k in dst_rows:
        ang = random.uniform(0, 2 * math.pi)
        rad = math.sqrt(random.random()) * rr
        new_u.clouds.x[k] = cx + rad * math.cos(ang)
        new_u.clouds.y[k] = cy + rad * math.sin(ang)
        new_u.clouds.vx[k] = 0.0
        new_u.clouds.vy[k] = 0.0
    return new_u


def process_universe_spawns(state):
    """For each hole that reached rip mass this step, open a new universe (up to the cap) by
    pulling matter from its source universe, and link the hole to that child."""
    new_radius = BARRIER_INITIAL_SIZE / 2.0
    for src in list(state.universes):
        ripping = src.pending_rip_bhs
        src.pending_rip_bhs = []
        for bh in ripping:
            if bh.child_universe is not None:
                continue
            if len(state.universes) >= UNIVERSE_MAX_COUNT:
                break
            child = _rip_universe(src, _find_spawn_center(state, new_radius, src, bh))
            bh.child_universe = child
            state.universes.append(child)
            src.event_log.append(
                f"SPACETIME RIP — a child universe opens; its constants drift "
                f"(G x{child.local.g:.2f}, fusion x{child.local.fusion:.2f}, collapse x{child.local.collapse:.2f})")


def _translate_universe(u, dx, dy):
    """Move a whole universe rigidly — barrier center and every entity/pulse."""
    bx, by = u.barrier.center
    u.barrier.center = (bx + dx, by + dy)
    u.clouds.X += dx
    u.clouds.Y += dy
    for e in u.black_holes:
        e.x += dx
        e.y += dy
    for e in (*u.neutron_stars, *u.magnetars, *u.white_dwarfs):
        e.x += dx
        e.y += dy
    for p in u.black_hole_pulses:
        p[0] += dx
        p[1] += dy


def _dent_barrier_toward(barrier, tx, ty, amount):
    """Push the barrier's vertices that face point (tx,ty) inward, flattening that side."""
    contact_angle = math.atan2(ty - barrier.center[1], tx - barrier.center[0])
    align = np.cos(barrier.angles - contact_angle)
    facing = align > 0
    barrier.radii[facing] = np.maximum(2.0, barrier.radii[facing] - amount * align[facing])


def resolve_barrier_overlaps(state, delta_time):
    """Soft-body contact between universes: where two barriers press together they FLATTEN and
    get pushed apart, so they touch and deform but never overlap."""
    universes = state.universes
    if len(universes) < 2:
        return
    means = [float(u.barrier.radii.mean()) for u in universes]
    relax = min(0.9, BARRIER_REPULSION_RATE * delta_time)
    for _ in range(BARRIER_RESOLVE_ITERATIONS):
        for i in range(len(universes)):
            A = universes[i]
            ax, ay = A.barrier.center
            wA = means[i]
            for j in range(i + 1, len(universes)):
                B = universes[j]
                bx, by = B.barrier.center
                wB = means[j]
                dx = bx - ax
                dy = by - ay
                dist = math.hypot(dx, dy)
                if dist < 0.01:
                    dx, dy, dist = random.uniform(-1, 1), random.uniform(-1, 1), 1.0  # unstick coincident
                ang = math.atan2(dy, dx)
                rA_c = A.barrier.get_radius_at_angle(ang % (2 * math.pi))
                rB_c = B.barrier.get_radius_at_angle((ang + math.pi) % (2 * math.pi))
                penetration = (rA_c + rB_c) - dist
                if penetration <= 0:
                    continue
                ux, uy = dx / dist, dy / dist
                total = wA + wB
                # Push apart (smaller universe moves more) resolves part of the penetration...
                push = penetration * BARRIER_SEPARATION_SHARE * relax
                _translate_universe(A, -ux * push * (wB / total), -uy * push * (wB / total))
                _translate_universe(B, ux * push * (wA / total), uy * push * (wA / total))
                ax -= ux * push * (wB / total)
                ay -= uy * push * (wB / total)
                # ...the rest flattens both contact faces (smaller deforms more).
                d = penetration * BARRIER_CONTACT_DEFORM * relax
                _dent_barrier_toward(A.barrier, bx, by, d * (wB / total))
                _dent_barrier_toward(B.barrier, ax, ay, d * (wA / total))


def apply_dark_flow(state, delta_time):
    """Dark flow: every universe drifts toward the multiverse's mass-weighted centroid —
    motion whose cause lies entirely outside any one universe's boundary, which is what the
    real (conjectured) dark flow is. The centroid includes each universe's own mass, so the
    dominant universe barely moves (the centroid already sits near it) while lighter ones
    stream toward it: Great Attractor semantics for free. The rate is weak — barrier contact
    resolution easily absorbs it, so the cluster huddles and flattens instead of overlapping."""
    universes = state.universes
    if len(universes) < 2:
        return
    weights = []
    for u in universes:
        m = float(u.clouds.M.sum()) if u.clouds.n else 0.0
        m += sum(bh.mass for bh in u.black_holes)
        m += sum(ns.mass for ns in u.neutron_stars)
        m += sum(mg.mass for mg in u.magnetars)
        m += sum(wd.mass for wd in u.white_dwarfs)
        weights.append(m)
    total = sum(weights)
    if total <= 0:
        return
    cx = sum(w * u.barrier.center[0] for w, u in zip(weights, universes)) / total
    cy = sum(w * u.barrier.center[1] for w, u in zip(weights, universes)) / total
    pull = min(1.0, DARK_FLOW_RATE * delta_time)
    for u in universes:
        ux, uy = u.barrier.center
        _translate_universe(u, (cx - ux) * pull, (cy - uy) * pull)


def _universe_alive(universe):
    return bool(universe.clouds.n or universe.black_holes or universe.neutron_stars
                or universe.magnetars or universe.white_dwarfs)


def reap_dead_universes(state):
    """Remove universes whose last matter is gone, passing their final events — plus an
    epitaph — to a surviving universe's log so the ticker still tells their ending. A
    universe that dies chemically complete (Z >= HEAT_DEATH_Z) died of heat death; one that
    empties young was lost. The last universe is never reaped: multiverse-wide heat death
    lingers and resets in the main loop, as before."""
    if len(state.universes) < 2:
        return
    dead = [u for u in state.universes if not _universe_alive(u)]
    if not dead:
        return
    state.universes = [u for u in state.universes if _universe_alive(u)]
    keeper = state.universes[0] if state.universes else None
    if keeper is None:
        return  # everything died at once; the main loop's heat-death reset takes it from here
    for u in dead:
        keeper.event_log.extend(u.event_log)
        if u.metallicity >= HEAT_DEATH_Z:
            keeper.event_log.append(
                f"HEAT DEATH — a universe completes its chemistry (Z {u.metallicity:.2f}) and goes dark")
        else:
            keeper.event_log.append(
                f"UNIVERSE LOST — the last of its matter is gone (Z {u.metallicity:.2f})")


def enforce_total_cloud_cap(state):
    """Trim the lowest-mass clouds across the whole multiverse when over the global cap
    (within-universe row order is preserved, as the old identity-filter did)."""
    total = sum(u.clouds.n for u in state.universes)
    if total <= MULTIVERSE_MAX_CLOUDS:
        return
    all_mass = np.concatenate([u.clouds.M for u in state.universes])
    order = np.argsort(-all_mass, kind='stable')
    keep_flat = np.zeros(total, dtype=bool)
    keep_flat[order[:MULTIVERSE_MAX_CLOUDS]] = True
    pos = 0
    for u in state.universes:
        n0 = u.clouds.n
        u.clouds.keep(keep_flat[pos:pos + n0])
        pos += n0


def prune_child_links(state):
    """Close a hole's wormhole if its child universe no longer exists, freeing the hole to rip
    a new one later."""
    live = set(id(u) for u in state.universes)
    for u in state.universes:
        for bh in u.black_holes:
            if bh.child_universe is not None and id(bh.child_universe) not in live:
                bh.child_universe = None


def initialize_state():
    state = SimulationState()
    state.universes.append(spawn_universe((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
    return state
