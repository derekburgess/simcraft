"""Compact objects: black holes, neutron stars, and white dwarfs. There are at most a handful
of each, so they stay ordinary Python objects — but every interaction with the cloud field is
vectorized over the field arrays in place (the arrays are the truth; there is no scatter step).
"""
import math
import random

import numpy as np

from sim.config import *

entity_id_counter = 0


def generate_unique_id():
    global entity_id_counter
    entity_id_counter += 1
    return entity_id_counter


def check_swept_collision(entity, target_x, target_y, target_radius, delta_time):
    """Scalar swept-capture check (used for neutron stars; the cloud version is vectorized)."""
    dx = entity.vx * delta_time
    dy = entity.vy * delta_time
    move_dist_sq = dx * dx + dy * dy
    if move_dist_sq < 0.01:
        return False
    fx = target_x - entity.x
    fy = target_y - entity.y
    t = max(0.0, min(1.0, (fx * dx + fy * dy) / move_dist_sq))
    closest_x = entity.x + t * dx
    closest_y = entity.y + t * dy
    return (target_x - closest_x) ** 2 + (target_y - closest_y) ** 2 < target_radius * target_radius


class BlackHole:
    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mass = min(mass, BLACK_HOLE_MAX_MASS)
        self.accretion_mass = 0.0
        self.border_radius = int(self.mass // BLACK_HOLE_RADIUS)
        self.tracer_angle = random.uniform(0, 2 * math.pi)
        self.angular_momentum = 0.0  # Spin from off-center accretion
        self.child_universe = None  # the universe this hole ripped open and streams matter into (None until it rips)
        self.flare_length = 0.0  # Quasar flare swing amplitude (pixels) — spikes per meal, decays back down
        self.flare_dir_x = 0.0   # Cosmetic: mass-weighted direction of recent meals (decays; newest dominates)
        self.flare_dir_y = 0.0
        self.is_flaring = False
        self._prev_accretion_mass = 0.0  # last frame's post-drain backlog, to detect fresh captures

    def attract(self, universe, delta_time, alive, stream_moves, ns_to_remove, bh_to_remove):
        # Event horizon: the radius at which matter is actually consumed. Smaller than the
        # drawn disk so clouds can skim the surface and slingshot away instead of being eaten.
        capture_radius = max(BLACK_HOLE_MIN_CAPTURE_RADIUS, self.border_radius * BLACK_HOLE_EVENT_HORIZON_FACTOR)
        # Disk/influence radius scales with mass, so massive holes organize entities from much farther out.
        swirl_radius = BLACK_HOLE_SWIRL_RADIUS * (self.mass / BLACK_HOLE_SWIRL_REFERENCE_MASS)

        for black_hole in universe.black_holes:
            if black_hole is not self and black_hole not in bh_to_remove:
                dx = self.x - black_hole.x
                dy = self.y - black_hole.y
                distance = max(math.hypot(dx, dy), 1)

                other_capture = max(BLACK_HOLE_MIN_CAPTURE_RADIUS, black_hole.border_radius * BLACK_HOLE_EVENT_HORIZON_FACTOR)
                merge_distance = capture_radius + other_capture
                if self.mass >= black_hole.mass and distance < merge_distance and (self.mass > black_hole.mass or self.id > black_hole.id):
                    bh_to_remove.add(black_hole)
                    # Transfer angular momentum from merger
                    rel_vx = black_hole.vx - self.vx
                    rel_vy = black_hole.vy - self.vy
                    self.angular_momentum += (dx * rel_vy - dy * rel_vx) * black_hole.mass
                    self.angular_momentum += black_hole.angular_momentum
                    # Conserve momentum during BH merger
                    total_mass = self.mass + black_hole.mass
                    if total_mass > 0:
                        self.vx = (self.mass * self.vx + black_hole.mass * black_hole.vx) / total_mass
                        self.vy = (self.mass * self.vy + black_hole.mass * black_hole.vy) / total_mass
                    # The eaten hole's undigested backlog comes along too, not just its mass.
                    self.accretion_mass += black_hole.mass + black_hole.accretion_mass
                    # Cosmetic: the flare glow points where the meal came from.
                    self.flare_dir_x += (-dx / distance) * black_hole.mass
                    self.flare_dir_y += (-dy / distance) * black_hole.mass
                    universe.black_hole_pulses.append([self.x, self.y, 0, black_hole.mass])
                    universe.event_log.append("BLACK HOLE MERGER — gravitational waves ripple out")
                else:
                    soft_dist = math.sqrt(distance * distance + BLACK_HOLE_GRAVITY_SOFTENING * BLACK_HOLE_GRAVITY_SOFTENING)
                    force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * black_hole.mass) / (soft_dist ** 2)
                    black_hole.vx += (dx / soft_dist) * force * delta_time
                    black_hole.vy += (dy / soft_dist) * force * delta_time

        self._attract_clouds(universe, delta_time, alive, stream_moves, capture_radius, swirl_radius)

        # Neutron stars, magnetars, and white dwarfs all fall in and get eaten the same way;
        # ns_to_remove is the shared removal set for every small compact object.
        for entity in (*universe.neutron_stars, *universe.magnetars, *universe.white_dwarfs):
            if entity in ns_to_remove:
                continue
            dx = self.x - entity.x
            dy = self.y - entity.y
            distance = max(math.hypot(dx, dy), 1)
            captured = distance < capture_radius or check_swept_collision(entity, self.x, self.y, capture_radius, delta_time)
            if captured:
                ns_to_remove.add(entity)
                # Transfer angular momentum from off-center accretion
                rel_vx = entity.vx - self.vx
                rel_vy = entity.vy - self.vy
                self.angular_momentum += (dx * rel_vy - dy * rel_vx) * entity.mass
                # Conserve momentum during NS accretion
                total_mass = self.mass + entity.mass
                if total_mass > 0:
                    self.vx = (self.mass * self.vx + entity.mass * entity.vx) / total_mass
                    self.vy = (self.mass * self.vy + entity.mass * entity.vy) / total_mass
                self.accretion_mass += entity.mass
                # Cosmetic: the flare glow points where the meal came from.
                self.flare_dir_x += (-dx / distance) * entity.mass
                self.flare_dir_y += (-dy / distance) * entity.mass
            else:
                soft_dist = math.sqrt(distance * distance + BLACK_HOLE_GRAVITY_SOFTENING * BLACK_HOLE_GRAVITY_SOFTENING)
                force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * entity.mass) / (soft_dist ** 2)
                # Newton's 3rd law with inertia: NS takes the full kick, BH recoil scaled by mass ratio.
                ux, uy = dx / soft_dist, dy / soft_dist
                kick = force * delta_time
                entity.vx += ux * kick
                entity.vy += uy * kick
                recoil = kick * (entity.mass / self.mass)
                self.vx -= ux * recoil
                self.vy -= uy * recoil

    def _attract_clouds(self, universe, delta_time, alive, stream_moves, capture_radius, swirl_radius):
        """Vectorized cloud interaction: same capture/stream/accrete rules and force/swirl formulas
        as the historical per-cloud loop. The prefix-sum recoil frame reproduces the sequential
        hole-velocity drift the scalar loop had, so capture-free passes match it exactly."""
        clouds = universe.clouds
        if clouds.n == 0:
            return
        X, Y, VX, VY, M = clouds.X, clouds.Y, clouds.VX, clouds.VY, clouds.M
        dx = self.x - X
        dy = self.y - Y
        dist = np.maximum(np.hypot(dx, dy), 1.0)
        # Swept-trajectory capture (tunneling prevention), vectorized
        mvx = VX * delta_time
        mvy = VY * delta_time
        move2 = mvx * mvx + mvy * mvy
        t = np.clip((dx * mvx + dy * mvy) / np.where(move2 > 0.0, move2, 1.0), 0.0, 1.0)
        closest2 = (dx - t * mvx) ** 2 + (dy - t * mvy) ** 2
        swept = (move2 >= 0.01) & (closest2 < capture_radius * capture_radius)
        captured = alive & ((dist < capture_radius) | swept)
        for k in np.nonzero(captured)[0]:
            alive[k] = False
            if self.child_universe is not None and random.random() < UNIVERSE_STREAM_FRACTION:
                # Wormhole: matter falling in emerges in the child universe instead of being
                # consumed. Position is rewritten now (the row moves to the child after the pass).
                ccx, ccy = self.child_universe.barrier.center
                rr = self.child_universe.barrier.rest_radius
                ang = random.uniform(0, 2 * math.pi)
                rad = math.sqrt(random.random()) * rr
                X[k] = ccx + rad * math.cos(ang)
                Y[k] = ccy + rad * math.sin(ang)
                VX[k] = 0.0
                VY[k] = 0.0
                stream_moves.append((int(k), self.child_universe))
            else:
                # Transfer angular momentum from off-center accretion: L = r x p
                rel_vx = VX[k] - self.vx
                rel_vy = VY[k] - self.vy
                self.angular_momentum += (dx[k] * rel_vy - dy[k] * rel_vx) * M[k]
                # Conserve momentum during accretion
                total_mass = self.mass + M[k]
                if total_mass > 0:
                    self.vx = (self.mass * self.vx + M[k] * VX[k]) / total_mass
                    self.vy = (self.mass * self.vy + M[k] * VY[k]) / total_mass
                self.accretion_mass += M[k]
                # Cosmetic: the flare glow points where the meal came from.
                self.flare_dir_x += (-dx[k] / dist[k]) * M[k]
                self.flare_dir_y += (-dy[k] / dist[k]) * M[k]
        if not alive.any():
            return
        soft_dist = np.sqrt(dist * dist + BLACK_HOLE_GRAVITY_SOFTENING * BLACK_HOLE_GRAVITY_SOFTENING)
        force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * M) / (soft_dist * soft_dist)
        ux = dx / soft_dist
        uy = dy / soft_dist
        kick = np.where(alive, force * delta_time, 0.0)
        # Newton's 3rd law recoil, per cloud; the exclusive prefix sum gives each cloud the same
        # sequentially-drifting hole velocity the old loop produced.
        rec_x = ux * kick * M / self.mass
        rec_y = uy * kick * M / self.mass
        frame_vx = self.vx - (np.cumsum(rec_x) - rec_x)
        frame_vy = self.vy - (np.cumsum(rec_y) - rec_y)
        VX += ux * kick
        VY += uy * kick
        # Frame-dragging swirl: drive tangential velocity toward circular-orbit speed inside the disk.
        in_swirl = alive & (dist < swirl_radius)
        if in_swirl.any():
            swirl_dir = 1.0 if self.angular_momentum >= 0 else -1.0
            tx, ty = -uy, ux
            cur_t = (VX - frame_vx) * tx + (VY - frame_vy) * ty
            target_t = swirl_dir * np.sqrt(force * dist)
            blend = np.minimum(1.0, BLACK_HOLE_SWIRL_RATE * (1.0 - dist / swirl_radius) * delta_time)
            dvt = np.where(in_swirl, (target_t - cur_t) * blend, 0.0)
            VX += dvt * tx
            VY += dvt * ty
            # Disk circularization: viscously damp the RADIAL component so disk clouds settle
            # into persistent orbits instead of plunging through in one pass — swirl sets the
            # rotation, this makes it last. Damping is partial: the residual inward drift is
            # the viscous accretion that keeps the hole fed.
            cur_r = (VX - frame_vx) * ux + (VY - frame_vy) * uy
            circ = np.minimum(1.0, BLACK_HOLE_DISK_CIRCULARIZATION
                              * (1.0 - dist / swirl_radius) * delta_time)
            dvr = np.where(in_swirl, -cur_r * circ, 0.0)
            VX += dvr * ux
            VY += dvr * uy
        self.vx -= float(rec_x.sum())
        self.vy -= float(rec_y.sum())

    def decay(self, delta_time, universe):
        # Eddington-style throttle: accretion chokes as the hole nears the mass cap (radiation
        # pressure, in the real version). A continuously fed hole settles just under the cap
        # instead of pinning AT it; once feeding stops, the 1/m^2 Hawking curve below takes
        # over and evaporation can finally win.
        throttle = max(0.0, 1.0 - (self.mass / BLACK_HOLE_MAX_MASS) ** BLACK_HOLE_EDDINGTON_EXPONENT)

        # Flares are an impulse per meal, not a static reading of the backlog: whatever landed
        # in accretion_mass since last frame (weighted by how hard the throttle is choking right
        # now, so it's near-zero far from the cap) kicks the jets out, then they shrink back down
        # on their own clock — a big capture flares bright and fades instead of holding a length.
        captured_this_frame = max(0.0, self.accretion_mass - self._prev_accretion_mass)
        self.flare_length = max(0.0, self.flare_length - BLACK_HOLE_FLARE_DECAY_PER_SEC * delta_time)
        self.flare_length = min(BLACK_HOLE_FLARE_MAX_LENGTH, self.flare_length
                                 + captured_this_frame * (1.0 - throttle) * BLACK_HOLE_FLARE_PX_PER_MASS)
        # The meal-direction vector fades so the glow tracks the newest feeding side.
        dir_keep = BLACK_HOLE_FLARE_DIR_DECAY ** delta_time
        self.flare_dir_x *= dir_keep
        self.flare_dir_y *= dir_keep

        was_flaring = self.is_flaring
        self.is_flaring = self.flare_length >= BLACK_HOLE_FLARE_THRESHOLD
        if self.is_flaring and not was_flaring:
            universe.event_log.append("QUASAR FLARE — Eddington-choked accretion lights the disk")

        if self.accretion_mass > 0:
            growth = min(BLACK_HOLE_GROWTH_RATE * throttle * delta_time, self.accretion_mass)
            self.mass = min(self.mass + growth, BLACK_HOLE_MAX_MASS)
            self.accretion_mass = max(0.0, self.accretion_mass - growth)
        rate = BLACK_HOLE_DECAY_RATE * (BLACK_HOLE_DECAY_THRESHOLD / self.mass) ** 2
        self.mass -= rate * delta_time
        self.accretion_mass = max(0.0, self.accretion_mass - rate * delta_time)
        self._prev_accretion_mass = self.accretion_mass
        # Refreshed here, in physics, so the capture radius (attract reads border_radius) never
        # depends on whether this hole's universe was drawn this frame — the renderer culls
        # off-view universes, and a draw-time refresh would freeze culled holes' capture ranges.
        self.border_radius = int(self.mass // BLACK_HOLE_RADIUS)


class NeutronStar:
    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mass = mass
        self.radius = NEUTRON_STAR_RADIUS
        self.angular_momentum = 0.0  # Spin from formation/interactions
        self.age = 0.0               # Seconds since birth — drives spin-down
        self.is_dead = False         # True once the pulse period crosses the death line
        self.pulse_rate = NEUTRON_STAR_PULSE_RATE
        self.pulse_strength = NEUTRON_STAR_PULSE_STRENGTH
        self.time_since_last_pulse = 0
        self.active_pulses = []
        self.pulse_color_state = 0  # 0: normal color, 1: white during pulse
        self.pulse_color_duration = NEUTRON_STAR_PULSE_COLOR_DURATION  # Duration of white color in seconds

    def apply_gravity(self, universe, delta_time):
        clouds = universe.clouds
        if clouds.n:
            # Same neighborhood the spatial hash gave: clouds within the 3x3 grid-cell block.
            cell = SPATIAL_HASH_CELL_SIZE
            ncx = int(self.x // cell)
            ncy = int(self.y // cell)
            ccx = np.floor(clouds.X / cell).astype(np.int64)
            ccy = np.floor(clouds.Y / cell).astype(np.int64)
            dx = clouds.X - self.x
            dy = clouds.Y - self.y
            dist_sq = dx * dx + dy * dy
            near = (np.abs(ccx - ncx) <= 1) & (np.abs(ccy - ncy) <= 1) & (dist_sq >= 1.0)
            if near.any():
                d2 = np.where(near, dist_sq, 1.0)
                distance = np.sqrt(d2)
                force = np.where(near, NEUTRON_STAR_GRAVITY_CONSTANT * (self.mass * clouds.M) / d2, 0.0)
                fx = (dx / distance) * force * delta_time
                fy = (dy / distance) * force * delta_time
                clouds.VX -= fx
                clouds.VY -= fy
                # Newton's 3rd law with inertia (same convention as BlackHole._attract_clouds):
                # recoil scaled by mass ratio, so the dense star anchors while clouds fall in.
                self.vx += float((fx * clouds.M).sum()) / self.mass
                self.vy += float((fy * clouds.M).sum()) / self.mass

        for black_hole in universe.black_holes:
            # Second half of a double-applied pair: BlackHole.attract already pulled this star
            # (softened, at the much stronger BH constant) and took its recoil; this pass adds
            # a further ~7% at the NS constant, unsoftened. Both halves are baked into the
            # orbit/anchoring tuning, so neither can be removed without shifting every NS
            # trajectory near a hole. (White dwarfs get only the BH-side pass.)
            dx = black_hole.x - self.x
            dy = black_hole.y - self.y
            distance = max(math.hypot(dx, dy), 1)

            force = NEUTRON_STAR_GRAVITY_CONSTANT * (self.mass * black_hole.mass) / (distance**2)

            # Newton's 3rd law with inertia: NS takes the full kick, BH recoil scaled by mass ratio.
            ux, uy = dx / distance, dy / distance
            kick = force * delta_time
            self.vx += ux * kick
            self.vy += uy * kick
            recoil = kick * (self.mass / black_hole.mass)
            black_hole.vx -= ux * recoil
            black_hole.vy -= uy * recoil

    def update_pulse(self, universe, ring, delta_time):
        self.time_since_last_pulse += delta_time

        # Spin-down: rotational energy leaves with every pulse, so the period grows with age
        # (the real P–Pdot track). Past the death line the pulsar goes dark and quiet — real
        # pulsars end silent, not in an explosion.
        self.age += delta_time
        self.pulse_rate = NEUTRON_STAR_PULSE_RATE * (1.0 + self.age * NEUTRON_STAR_SPINDOWN_RATE)
        if not self.is_dead and self.pulse_rate >= NEUTRON_STAR_DEATH_LINE_PERIOD:
            self.is_dead = True
            universe.event_log.append("PULSAR DEATH LINE — spin-down silences the beacon")

        if self.pulse_color_state == 1:
            self.pulse_color_duration -= delta_time
            if self.pulse_color_duration <= 0:
                self.pulse_color_state = 0
                self.pulse_color_duration = NEUTRON_STAR_PULSE_COLOR_DURATION

        clouds = universe.clouds
        pulses_to_remove = []
        # active_pulses holds one radius per ring: pulses stay fully visible all the way to
        # the barrier (only their physical effect fades, below), so there is no per-pulse
        # fade or age state to carry.
        for i, radius in enumerate(self.active_pulses):
            new_radius = radius + (NEUTRON_STAR_RIPPLE_SPEED * delta_time)
            effect_fade_start = ring.rest_radius * 0.75
            effect_fade = max(0.0, 1.0 - max(0.0, new_radius - effect_fade_start) / (ring.rest_radius * 0.25))

            self.active_pulses[i] = new_radius

            # Barrier ring: flash and push the vertices the wavefront is crossing.
            cx, cy = ring.center
            bx = cx + ring.radii * ring.cos_a
            by = cy + ring.radii * ring.sin_a
            dist_to_star = np.hypot(bx - self.x, by - self.y)
            hit = np.abs(dist_to_star - new_radius) < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2
            if hit.any():
                ring.flash[hit] = np.maximum(ring.flash[hit], effect_fade * 0.4)
                ring.radii_vel[hit] += BARRIER_WAVE_PUSH * 0.3 * effect_fade * delta_time

            # Clouds in the ripple band get pushed outward.
            if clouds.n:
                dx = clouds.X - self.x
                dy = clouds.Y - self.y
                dist_sq = dx * dx + dy * dy
                r_inner = max(0, new_radius - NEUTRON_STAR_RIPPLE_EFFECT_WIDTH)
                r_outer = new_radius + NEUTRON_STAR_RIPPLE_EFFECT_WIDTH
                in_annulus = (dist_sq >= r_inner * r_inner) & (dist_sq <= r_outer * r_outer)
                if in_annulus.any():
                    distance = np.sqrt(np.where(in_annulus, dist_sq, 1.0))
                    ripple = np.abs(distance - new_radius)
                    apply = in_annulus & (ripple < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH) & (distance > 0)
                    if apply.any():
                        effect = 1.0 - ripple / NEUTRON_STAR_RIPPLE_EFFECT_WIDTH
                        force = np.where(apply, self.pulse_strength * effect / ((ripple + 1) ** 0.8), 0.0)
                        clouds.VX += (dx / distance) * force * delta_time
                        clouds.VY += (dy / distance) * force * delta_time
                        # The wavefront also compresses what it passes: mark these clouds
                        # shocked so they merge readily (triggered star formation).
                        clouds.SHOCK = np.where(apply, SHOCK_DURATION, clouds.SHOCK)

            for black_hole in universe.black_holes:
                dx = black_hole.x - self.x
                dy = black_hole.y - self.y
                distance = math.hypot(dx, dy)

                ripple_dist = abs(distance - new_radius)
                if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH:
                    effect_factor = (1.0 - (ripple_dist / NEUTRON_STAR_RIPPLE_EFFECT_WIDTH)) * 0.3
                    force = self.pulse_strength * effect_factor / ((ripple_dist + 1) ** 1.2)

                    if distance > 0:
                        black_hole.vx += (dx / distance) * force * delta_time * 0.2
                        black_hole.vy += (dy / distance) * force * delta_time * 0.2

            if new_radius > float(ring.radii.max()):
                pulses_to_remove.append(i)

        for i in sorted(pulses_to_remove, reverse=True):
            if i < len(self.active_pulses):
                self.active_pulses.pop(i)

        if not self.is_dead and self.time_since_last_pulse >= self.pulse_rate and len(self.active_pulses) == 0:
            self.active_pulses.append(0.0)
            self.time_since_last_pulse = 0
            self.pulse_color_state = 1  # Set to white during pulse
            self.pulse_color_duration = NEUTRON_STAR_PULSE_COLOR_DURATION  # Reset duration

    def decay(self, delta_time):
        # Active pulsars barely lose mass (death comes from spin-down, not evaporation); dead
        # ones dissipate slowly to feed their mass back into the cloud cycle.
        rate = NEUTRON_STAR_DEAD_DECAY_RATE if self.is_dead else NEUTRON_STAR_ACTIVE_DECAY_RATE
        self.mass -= rate * delta_time


class Magnetar(NeutronStar):
    """A neutron star born with an extreme magnetic field. Gravity is ordinary NS gravity
    (inherited), but ferromagnetic clouds (iron/cobalt/nickel) inside the field radius are
    pulled in hard — a selective attractor, so it never competes with black holes for
    organizing the bulk (hydrogen/helium) matter. Instead of the steady pulsar pulses it
    erupts in rare giant flares, and when the field dies it settles into a plain NeutronStar."""

    def __init__(self, x, y, mass):
        super().__init__(x, y, mass)
        self.radius = MAGNETAR_RADIUS
        self.field_time = MAGNETAR_FIELD_LIFETIME
        self.color_phase = random.uniform(0, 2 * math.pi)
        self.latched = False  # gripping the barrier (set each frame by Barrier.update_deformation)

    def apply_magnetism(self, universe, delta_time):
        clouds = universe.clouds
        if clouds.n == 0:
            return
        ferro = np.isin(clouds.ELEM, FERROMAGNETIC_ELEMENTS)
        if not ferro.any():
            return
        dx = clouds.X - self.x
        dy = clouds.Y - self.y
        dist_sq = dx * dx + dy * dy
        near = ferro & (dist_sq < MAGNETAR_FIELD_RADIUS ** 2) & (dist_sq >= 1.0)
        if not near.any():
            return
        d2 = np.where(near, dist_sq, 1.0)
        distance = np.sqrt(d2)
        # 1/d falloff (not 1/d^2): a magnet-like grip that stays strong out to the field edge.
        force = np.where(near, MAGNETAR_MAGNETIC_CONSTANT * (self.mass * clouds.M) / distance, 0.0)
        fx = (dx / distance) * force * delta_time
        fy = (dy / distance) * force * delta_time
        clouds.VX -= fx
        clouds.VY -= fy
        # Newton's 3rd law with inertia: mass-scaled recoil — the magnet holds its ground
        # and reels the iron in, rather than lunging at it.
        self.vx += float((fx * clouds.M).sum()) / self.mass
        self.vy += float((fy * clouds.M).sum()) / self.mass

    def update_field(self, universe, delta_time):
        """Advance the color oscillation, tick down the field lifetime, and roll for a
        giant flare: an outward pulse on the shared BH-merger pulse list, paid for in mass."""
        self.color_phase += MAGNETAR_COLOR_CYCLE_RATE * delta_time
        self.field_time -= delta_time

        if self.pulse_color_state == 1:
            self.pulse_color_duration -= delta_time
            if self.pulse_color_duration <= 0:
                self.pulse_color_state = 0
                self.pulse_color_duration = NEUTRON_STAR_PULSE_COLOR_DURATION

        # No flares while latched onto the barrier: the field's energy goes into the grip.
        # (A point-blank flare's barrier wave-push would blow the ring outward far faster
        # than the grip reels it in.) A flare also needs enough mass to pay its cost — a
        # nearly-dissipated magnetar (light kilonova remnants decay fast) must not flare
        # itself into negative mass.
        if (not self.latched and self.mass > MAGNETAR_FLARE_MASS_COST
                and random.random() < MAGNETAR_FLARE_CHANCE):
            universe.black_hole_pulses.append([self.x, self.y, 0, MAGNETAR_FLARE_ENERGY])
            self.mass -= MAGNETAR_FLARE_MASS_COST
            self.pulse_color_state = 1
            self.pulse_color_duration = NEUTRON_STAR_PULSE_COLOR_DURATION
            universe.event_log.append("MAGNETAR GIANT FLARE — magnetic field snaps and reconnects")

    def decay(self, delta_time):
        self.mass -= MAGNETAR_DECAY_RATE * delta_time


class WhiteDwarf:
    """The quiet endpoint of most stars: the exposed core left after a sub-massive star sheds
    its envelope as a planetary nebula. Otherwise it just cools — white-hot to dim red to
    invisible (a black dwarf), at which point physics.step removes it. Black holes can still
    eat one, and two colliding white dwarfs detonate as a Type Ia supernova."""

    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mass = mass
        self.age = 0.0

    def cooling(self):
        """0.0 fresh and white-hot → 1.0 fully cooled (black dwarf)."""
        return min(self.age / WHITE_DWARF_COOL_TIME, 1.0)

    def apply_gravity(self, universe, delta_time):
        clouds = universe.clouds
        if not clouds.n:
            return
        cell = SPATIAL_HASH_CELL_SIZE
        ncx = int(self.x // cell)
        ncy = int(self.y // cell)
        ccx = np.floor(clouds.X / cell).astype(np.int64)
        ccy = np.floor(clouds.Y / cell).astype(np.int64)
        dx = clouds.X - self.x
        dy = clouds.Y - self.y
        dist_sq = dx * dx + dy * dy
        near = (np.abs(ccx - ncx) <= 1) & (np.abs(ccy - ncy) <= 1) & (dist_sq >= 1.0)
        if not near.any():
            return
        d2 = np.where(near, dist_sq, 1.0)
        distance = np.sqrt(d2)
        force = np.where(near, WHITE_DWARF_GRAVITY_CONSTANT * (self.mass * clouds.M) / d2, 0.0)
        fx = (dx / distance) * force * delta_time
        fy = (dy / distance) * force * delta_time
        clouds.VX -= fx
        clouds.VY -= fy
        self.vx += float((fx * clouds.M).sum()) / self.mass
        self.vy += float((fy * clouds.M).sum()) / self.mass
