"""All drawing. Reads the simulation state (arrays + compact objects) and never mutates
physics.

The world surface is sized to the view plus a margin (capped by MULTIVERSE_RENDER_MAX), never
to the full extent of the multiverse, and universes fully outside the view are culled.
"""
import math
import time

import numpy as np
import pygame

from sim.config import *
from sim.rng import MAX as RNG_MAX

RNG_DIGITS = len(str(RNG_MAX))  # HUD cell width follows the actual output range

_START_COLOR_LUT = np.array(MOLECULAR_CLOUD_START_COLORS, dtype=float)
_END_COLOR = np.array(MOLECULAR_CLOUD_END_COLOR, dtype=float)
# Spectral-class LUTs from config.STAR_CLASSES (descending mass_min order preserved).
_CLASS_BOUNDS = [c[0] for c in STAR_CLASSES]
_CLASS_COLORS = np.array([c[2] for c in STAR_CLASSES], dtype=float)
_CLASS_DRAW_SIZES = np.array([c[3] for c in STAR_CLASSES], dtype=np.int64)
_CEPHEID_LEVELS = np.array(CEPHEID_LEVELS, dtype=float)


def interpolate_color(start_color, end_color, factor):
    r = start_color[0] + factor * (end_color[0] - start_color[0])
    g = start_color[1] + factor * (end_color[1] - start_color[1])
    b = start_color[2] + factor * (end_color[2] - start_color[2])
    return int(r), int(g), int(b)


# ── Barrier ─────────────────────────────────────────────────────────────────────────────────

def draw_barrier(screen, barrier, offset_x=0, offset_y=0):
    cx = barrier.center[0] + offset_x
    cy = barrier.center[1] + offset_y
    half_w = BARRIER_SMOOTHING_WINDOW // 2
    smoothed = barrier.radii.astype(float)
    for _ in range(BARRIER_SMOOTHING_PASSES):
        acc = np.roll(smoothed, half_w)
        for k in range(-half_w + 1, half_w + 1):
            acc = acc + np.roll(smoothed, -k)
        smoothed = acc / BARRIER_SMOOTHING_WINDOW

    px = (cx + smoothed * barrier.cos_a).astype(int)
    py = (cy + smoothed * barrier.sin_a).astype(int)
    points = list(zip(px.tolist(), py.tolist()))

    # The alpha surface only needs to cover the barrier itself, not the whole world surface.
    pad = BARRIER_LINE_WIDTH + 1
    min_x = int(px.min()) - pad
    min_y = int(py.min()) - pad
    w = int(px.max()) + pad - min_x
    h = int(py.max()) + pad - min_y
    if w <= 0 or h <= 0:
        return
    barrier_surface = pygame.Surface((w, h), pygame.SRCALPHA)
    local_points = [(p[0] - min_x, p[1] - min_y) for p in points]

    base_color = BARRIER_COLOR + (BARRIER_BASE_OPACITY,)
    pygame.draw.polygon(barrier_surface, base_color, local_points, BARRIER_LINE_WIDTH)

    flash = barrier.flash
    n = barrier.num_points
    seg_flash = np.maximum(flash, np.roll(flash, -1))
    for i in np.nonzero(seg_flash > 0.01)[0]:
        flash_val = seg_flash[i]
        opacity = int(BARRIER_BASE_OPACITY + flash_val * (BARRIER_FLASH_OPACITY - BARRIER_BASE_OPACITY))
        r = int(BARRIER_COLOR[0] + flash_val * (BARRIER_FLASH_COLOR[0] - BARRIER_COLOR[0]))
        g = int(BARRIER_COLOR[1] + flash_val * (BARRIER_FLASH_COLOR[1] - BARRIER_COLOR[1]))
        b = int(BARRIER_COLOR[2] + flash_val * (BARRIER_FLASH_COLOR[2] - BARRIER_COLOR[2]))
        color = (r, g, b, min(255, opacity))
        pygame.draw.line(barrier_surface, color, local_points[i], local_points[(i + 1) % n], BARRIER_LINE_WIDTH)

    screen.blit(barrier_surface, (min_x, min_y))


# ── Clouds ──────────────────────────────────────────────────────────────────────────────────

def _cloud_visuals(clouds):
    """Vectorized draw-size/color/opacity. The returned size is the DRAW size: for clouds it
    equals the collision size (as always), for stars it comes from the STAR_CLASSES display
    table and is deliberately decoupled from the 2/4/6 collision AABB the merge pass uses —
    richer visuals with bit-identical physics."""
    n = clouds.n
    mass = clouds.M
    size = clouds.SIZE.astype(np.int64)
    elem = clouds.ELEM
    is_star = clouds.IS_STAR

    factor = np.clip((mass - MOLECULAR_CLOUD_START_MASS) / (PROTOSTAR_THRESHOLD - MOLECULAR_CLOUD_START_MASS), 0.0, 1.0)
    opacity = (MOLECULAR_CLOUD_MIN_OPACITY + factor * (MOLECULAR_CLOUD_OPACITY - MOLECULAR_CLOUD_MIN_OPACITY)).astype(np.int64)
    opacity = np.where(is_star, 255, opacity)

    start = _START_COLOR_LUT[elem]
    f2 = (1.0 - (size - 4) / (MOLECULAR_CLOUD_START_SIZE - 4))[:, None]
    color = np.where((size <= 4)[:, None], _END_COLOR, start + f2 * (_END_COLOR - start))
    # Brown dwarfs: heavy not-quite-stars (incl. the whole BH-evaporation cloud band) glow as
    # dim maroon embers instead of element colors — failed stars, visibly so.
    ember = ~is_star & (mass >= BROWN_DWARF_MASS_MIN) & (mass < PROTOSTAR_THRESHOLD)
    color = np.where(ember[:, None], np.array(BROWN_DWARF_COLOR, dtype=float), color)

    # Star color/draw-size follow MASS through the spectral-class ladder (M→K→G→F→A→B→O),
    # the real temperature sequence at finer grain than the three fate tiers.
    cls = np.select([mass >= b for b in _CLASS_BOUNDS[:-1]],
                    list(range(len(_CLASS_BOUNDS) - 1)), len(_CLASS_BOUNDS) - 1)
    star_color = _CLASS_COLORS[cls]
    star_draw = _CLASS_DRAW_SIZES[cls]
    # Carbon stars: cool M/K stars made of carbon read far redder than their temperature.
    carbon = is_star & (mass < STAR_TIER_MEDIUM_MASS) & (elem == CARBON_STAR_ELEMENT)
    star_color = np.where(carbon[:, None], np.array(CARBON_STAR_COLOR, dtype=float), star_color)
    # Cepheids: F-band stars ride a stepped three-level light curve (stateless, like the civ
    # flicker: row-index phase + wall-clock bucket; quantized so the sprite cache stays small).
    cepheid = is_star & (mass >= CEPHEID_MASS_MIN) & (mass < CEPHEID_MASS_MAX)
    if cepheid.any():
        bucket = int(time.time() / CEPHEID_STEP)
        level = _CEPHEID_LEVELS[(np.arange(n) * 7 + bucket) % len(_CEPHEID_LEVELS)]
        star_color = np.where(cepheid[:, None], star_color * level[:, None], star_color)
    # Red giants override everything: a retiring star swells huge and deep orange-red.
    giant = clouds.GIANT > 0.0
    star_color = np.where(giant[:, None], np.array(RED_GIANT_COLOR, dtype=float), star_color)
    star_draw = np.where(giant, RED_GIANT_DRAW_SIZE, star_draw)

    color = np.where(is_star[:, None], star_color, color).astype(np.int64)
    draw_size = np.where(is_star, star_draw, size)
    return draw_size, color, opacity


# Stars are solid squares: tiny (size, color) cardinality, so their surfaces are shared from
# one module-level cache instead of built per row.
_STAR_SPRITE_CACHE = {}


def _star_sprite(s, col):
    surf = _STAR_SPRITE_CACHE.get((s, col))
    if surf is None:
        surf = pygame.Surface((s, s))
        surf.fill(col)
        _STAR_SPRITE_CACHE[(s, col)] = surf
    return surf


def draw_clouds(screen, clouds, offset_x=0, offset_y=0):
    """One batched Surface.blits in row order (z-order preserved). The per-cloud Python loop
    runs only over STALE rows — visuals are diffed against the cached keys in one vector op —
    so a settled field costs one numpy compare plus the blits call, not n blit calls."""
    n = clouds.n
    if n == 0:
        return
    size, color, opacity = _cloud_visuals(clouds)
    keys = np.empty((n, 5), dtype=np.int64)
    keys[:, 0] = size
    keys[:, 1:4] = color
    keys[:, 4] = opacity
    stale = (keys != clouds.sprite_keys[:n]).any(axis=1)
    is_star = clouds.IS_STAR
    sprites = clouds.sprites
    offsets = clouds.offsets
    for k in np.nonzero(stale)[0]:
        s = int(size[k])
        col = (int(color[k, 0]), int(color[k, 1]), int(color[k, 2]))
        if is_star[k]:
            sprites[k] = _star_sprite(s, col)
            continue
        # Translucent block-cluster sprite, rebuilt only when size/color/opacity change.
        surf = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
        num_blocks = 3 + (MOLECULAR_CLOUD_START_SIZE - s) // 4
        block_r = max(1, int(s * 0.3))
        rgba = col + (int(opacity[k]),)
        for bi in range(min(num_blocks, 7)):
            ox, oy = offsets[k, bi]
            bx = int(s + ox * s)
            by = int(s + oy * s)
            pygame.draw.rect(surf, rgba, (bx - block_r, by - block_r, block_r * 2, block_r * 2))
        sprites[k] = surf
    clouds.sprite_keys[:n] = keys
    # Stars blit at their rect corner; clouds center their 2s x 2s sprite as the old path did.
    X = clouds.X
    Y = clouds.Y
    px = np.where(is_star, X + offset_x, (X + size * 0.5 + offset_x).astype(np.int64) - size)
    py = np.where(is_star, Y + offset_y, (Y + size * 0.5 + offset_y).astype(np.int64) - size)
    screen.blits(zip(sprites[:n], zip(px.astype(np.int64).tolist(), py.astype(np.int64).tolist())),
                 doreturn=False)

    # Civilizations: a ring of small orbiting swarm segments (steady — the structure itself
    # doesn't blink) around a star whose own light flickers in and out like an irregular light
    # curve (transits/gaps), rather than a smooth pulse that would read as a pulsar.
    civ_idx = np.nonzero(is_star & clouds.HAS_CIV)[0]
    if len(civ_idx):
        time_bucket = int(time.time() / CIVILIZATION_FLICKER_STEP)
        for k in civ_idx:
            cx = int(px[k] + size[k] * 0.5)
            cy = int(py[k] + size[k] * 0.5)
            # Ring of dots (the swarm's segments) — always present, doesn't flicker.
            ring_radius = int(size[k] * 0.5) + CIVILIZATION_RING_PADDING
            for i in range(CIVILIZATION_RING_DOT_COUNT):
                angle = (2 * math.pi / CIVILIZATION_RING_DOT_COUNT) * i
                dx = int(cx + ring_radius * math.cos(angle))
                dy = int(cy + ring_radius * math.sin(angle))
                pygame.draw.circle(screen, CIVILIZATION_RING_COLOR, (dx, dy), CIVILIZATION_RING_DOT_RADIUS)
            if hash((int(k), time_bucket)) % CIVILIZATION_FLICKER_GAP_CHANCE == 0:
                continue
            # Opaque disc (cold white, solid like the magnetar's core) sits above the star's
            # own sprite and covers it — the swarm blocking its star, not just haloing it.
            # This is the piece that flickers.
            disc_radius = int(size[k] * 0.5) + CIVILIZATION_DISC_PADDING
            pygame.draw.circle(screen, CIVILIZATION_DISC_COLOR, (cx, cy), disc_radius)

    # Wolf-Rayet shells: enriched top-band stars shedding their envelope as a continuously
    # expanding ring — stateless (wall clock + row phase), fading as it grows, then wrapping:
    # perpetual shedding. Foreshadowing, not physics. Only a stable 1-in-N subset renders the
    # shell (see config): the tag hashes the star's own sprite offsets, which are random at
    # spawn and travel with the row through every compaction — so it's the SAME stars shelled
    # frame to frame, unlike a row-index hash, which would reshuffle on every keep()/select().
    wr_mask = (is_star & (clouds.M >= WOLF_RAYET_MASS)
               & (clouds.ELEM >= STAR_ENRICHED_ELEMENT_MIN) & (clouds.GIANT <= 0.0))
    if wr_mask.any():
        tag = (np.abs(clouds.offsets[:n, :, 0]).sum(axis=1) * 1e4).astype(np.int64)
        wr_mask &= (tag % WOLF_RAYET_FRACTION) == 0
    wr_idx = np.nonzero(wr_mask)[0]
    if len(wr_idx):
        t = time.time()
        for k in wr_idx:
            cx = int(px[k] + size[k] * 0.5)
            cy = int(py[k] + size[k] * 0.5)
            frac = ((t * WOLF_RAYET_SHED_SPEED + int(k) * 1.7) % WOLF_RAYET_SHELL_RANGE) / WOLF_RAYET_SHELL_RANGE
            r = int(size[k] * 0.5) + 2 + int(frac * WOLF_RAYET_SHELL_RANGE)
            alpha = int(200 * (1.0 - frac))
            if alpha <= 0:
                continue
            shell = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(shell, (*WOLF_RAYET_SHELL_COLOR, alpha), (r + 1, r + 1), r, 1)
            screen.blit(shell, (cx - r - 1, cy - r - 1))


# ── Pulses / compact objects ────────────────────────────────────────────────────────────────

def _clip_pulse_points(origin_x, origin_y, pulse_radius, ring, num_pts=PULSE_RENDER_POINT_COUNT, offset_x=0, offset_y=0):
    """Ring polygon clipped against the barrier only. Waves superpose: rings pass through
    each other unchanged (gravitational waves are linear — interference adds, it never
    deflects a wavefront), so there is no ring-vs-ring pass. That pass was also the frame
    cost that scaled quadratically with ring count once pulse trains made storms dense."""
    cx = ring.center[0] + offset_x
    cy = ring.center[1] + offset_y
    theta = (2 * math.pi / num_pts) * np.arange(num_pts)
    px = origin_x + pulse_radius * np.cos(theta)
    py = origin_y + pulse_radius * np.sin(theta)

    dxc = px - cx
    dyc = py - cy
    dist_from_center = np.hypot(dxc, dyc)
    barrier_angle = np.arctan2(dyc, dxc) % (2 * math.pi)
    barrier_r = ring.radius_at(barrier_angle)
    out = (dist_from_center > 0) & (dist_from_center > barrier_r - PULSE_BARRIER_CLIP_MARGIN)
    if out.any():
        clip_r = barrier_r[out] - PULSE_BARRIER_CLIP_MARGIN
        px[out] = cx + clip_r * np.cos(barrier_angle[out])
        py[out] = cy + clip_r * np.sin(barrier_angle[out])

    return list(zip(px.astype(np.int64).tolist(), py.astype(np.int64).tolist()))


def draw_black_hole(screen, bh, offset_x=0, offset_y=0):
    draw_x = int(bh.x + offset_x)
    draw_y = int(bh.y + offset_y)
    radius = bh.border_radius  # refreshed by BlackHole.decay — physics owns it, draw only reads

    # The horizon ring IS the flare readout: dark red when quiescent, heated toward hot
    # white-yellow by feeding (flare_length), seething with a stateless wall-clock pulse.
    # Direction rides in the ring's light as a crescent — hottest at the meal angle, floored
    # ember opposite — never as a separate bead/dot, which the strobing tracer camouflaged.
    # Whole-ring color is the only accretion signal big enough to read at these hole sizes.
    heat = min(1.0, bh.flare_length / BLACK_HOLE_FLARE_MAX_LENGTH)
    if heat > 0.0:
        osc = 0.5 - 0.5 * math.cos(time.time() * BLACK_HOLE_FLARE_OSC_RATE + bh.id)
        heat *= 1.0 - BLACK_HOLE_FLARE_PULSE_DEPTH * osc
    if heat <= 0.0 or radius < 2:
        # Quiescent (or too small to subdivide): the classic one-circle dark ring.
        pygame.draw.circle(screen, BLACK_HOLE_BORDER_COLOR, (draw_x, draw_y), radius)
    else:
        # Crescent sharpness follows the meal-direction vector's magnitude: consistent
        # one-sided feeding focuses a tight arc, chaotic feeding smears toward uniform.
        dir_mag = math.hypot(bh.flare_dir_x, bh.flare_dir_y)
        sharp = min(1.0, dir_mag / BLACK_HOLE_FLARE_DIR_REFERENCE)
        meal_ang = math.atan2(bh.flare_dir_y, bh.flare_dir_x)
        floor = BLACK_HOLE_FLARE_FAR_SIDE_FLOOR
        # Underfill at the ring's coolest (far-side) color so no background speckles leak
        # between the segment lines and the black interior.
        base_heat = heat * ((1.0 - sharp) + sharp * floor)
        pygame.draw.circle(screen, interpolate_color(BLACK_HOLE_BORDER_COLOR, BLACK_HOLE_FLARE_COLOR, base_heat),
                           (draw_x, draw_y), radius)
        step = 2.0 * math.pi / BLACK_HOLE_RING_SEGMENTS
        # Beaming concentrates rather than redistributes: normalize the crescent profile so
        # its ring-average equals the heat — the meal side then runs HOTTER than a uniform
        # blaze would (~1.7x at full sharpness), so direction stays legible even at low heat.
        mids = [i * step + step * 0.5 for i in range(BLACK_HOLE_RING_SEGMENTS)]
        profile = [floor + (1.0 - floor) * (0.5 + 0.5 * math.cos(m - meal_ang)) ** BLACK_HOLE_FLARE_CRESCENT_POWER
                   for m in mids]
        mean_p = sum(profile) / len(profile)
        for i in range(BLACK_HOLE_RING_SEGMENTS):
            a0 = i * step
            a1 = a0 + step
            seg_heat = min(1.0, heat * ((1.0 - sharp) + sharp * profile[i] / mean_p))
            seg_color = interpolate_color(BLACK_HOLE_BORDER_COLOR, BLACK_HOLE_FLARE_COLOR, seg_heat)
            pygame.draw.line(screen, seg_color,
                             (draw_x + radius * math.cos(a0), draw_y + radius * math.sin(a0)),
                             (draw_x + radius * math.cos(a1), draw_y + radius * math.sin(a1)), 3)
    pygame.draw.circle(screen, BLACK_HOLE_COLOR, (draw_x, draw_y), radius - 2)

    tracer_x = draw_x + bh.border_radius * math.cos(bh.tracer_angle)
    tracer_y = draw_y + bh.border_radius * math.sin(bh.tracer_angle)
    pygame.draw.circle(screen, BLACK_HOLE_DISK_COLOR, (int(tracer_x), int(tracer_y)), BLACK_HOLE_DISK_SIZE)


def draw_white_dwarf(screen, wd, offset_x=0, offset_y=0):
    # A white dwarf only cools: white-hot → dim ember → gone (the color runs toward the
    # background so a fully cooled black dwarf literally disappears into space).
    t = wd.cooling()
    if t < 0.7:
        color = interpolate_color(WHITE_DWARF_COLOR, WHITE_DWARF_COOL_COLOR, t / 0.7)
    else:
        color = interpolate_color(WHITE_DWARF_COOL_COLOR, BACKGROUND_COLOR, (t - 0.7) / 0.3)
    pygame.draw.circle(screen, color, (int(wd.x + offset_x), int(wd.y + offset_y)), WHITE_DWARF_RADIUS)


def _crowd_dim(all_pulses):
    """Loudness normalization for wave rings: full brightness up to PULSE_CROWD_REFERENCE
    coexisting rings, then alpha scales by sqrt(reference/count) so storms don't stack to glare."""
    return math.sqrt(min(1.0, PULSE_CROWD_REFERENCE / max(1, len(all_pulses))))


def draw_neutron_star(screen, ns, ring, all_pulses, offset_x=0, offset_y=0,
                      pulse_layer=None, layer_x=0, layer_y=0):
    draw_x = int(ns.x + offset_x)
    draw_y = int(ns.y + offset_y)
    pulse_ox = ns.x + offset_x
    pulse_oy = ns.y + offset_y
    current_color = NEUTRON_STAR_DEAD_COLOR if ns.is_dead else NEUTRON_STAR_COLOR

    if not ns.is_dead:  # jets are the beam that dies with the pulsar, not a separate fade
        flashing = ns.pulse_color_state == 1
        jet_color = (255, 255, 255) if flashing else NEUTRON_STAR_COLOR
        jet_length = NEUTRON_STAR_JET_FLASH_LENGTH if flashing else NEUTRON_STAR_JET_LENGTH
        # Single polar beam line through the center at the star's wobble tilt (flipped once
        # per flash in update_pulse), so the beam rocks side to side as the pulsar spins.
        ux = math.sin(ns.jet_angle)
        uy = -math.cos(ns.jet_angle)
        pygame.draw.line(screen, jet_color,
                         (draw_x - ux * jet_length, draw_y - uy * jet_length),
                         (draw_x + ux * jet_length, draw_y + uy * jet_length),
                         NEUTRON_STAR_JET_WIDTH)

    # pygame.draw.circle at radius 1 rasterizes as a 2px blob offset from (draw_x, draw_y),
    # which would visibly throw off the jet's alignment through the core — a symmetric square
    # keeps a true center pixel at (draw_x, draw_y) for the jet line to line up with.
    core_size = ns.radius * 2 + 1
    pygame.draw.rect(screen, current_color, (draw_x - ns.radius, draw_y - ns.radius, core_size, core_size))

    if pulse_layer is None:  # gravity waves hidden this frame
        return
    base_alpha = NEUTRON_STAR_PULSE_COLOR[3] * _crowd_dim(all_pulses)
    if base_alpha < 1:
        return
    for pulse_radius in ns.active_pulses:
        if pulse_radius <= 1:
            continue
        # Dissipation: alpha ramps to zero over the last 30% of the ripple's range, so the
        # ring melts away instead of popping out where physics removes it.
        fade = min(1.0, (NEUTRON_STAR_PULSE_RANGE - pulse_radius) / (NEUTRON_STAR_PULSE_RANGE * 0.3))
        alpha = max(0, min(255, int(base_alpha * fade)))
        if alpha == 0:
            continue
        color = (NEUTRON_STAR_PULSE_COLOR[0], NEUTRON_STAR_PULSE_COLOR[1], NEUTRON_STAR_PULSE_COLOR[2], alpha)
        points = _clip_pulse_points(pulse_ox, pulse_oy, pulse_radius, ring, offset_x=offset_x, offset_y=offset_y)
        local_points = [(p[0] - layer_x, p[1] - layer_y) for p in points]
        pygame.draw.polygon(pulse_layer, color, local_points, NEUTRON_STAR_PULSE_WIDTH)


def draw_magnetar(screen, mag, offset_x=0, offset_y=0):
    draw_x = int(mag.x + offset_x)
    draw_y = int(mag.y + offset_y)
    t = 0.5 * (1.0 + math.sin(mag.color_phase))
    color = interpolate_color(MAGNETAR_COLOR_A, MAGNETAR_COLOR_B, t)
    if mag.pulse_color_state == 1:  # white flash during a giant flare
        color = (255, 255, 255)
    # Translucent aura that breathes with the color phase, then the solid core on top.
    glow_r = MAGNETAR_GLOW_RADIUS + int(2 * math.sin(mag.color_phase * 0.5))
    surf_size = glow_r * 2 + 2
    glow = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
    pygame.draw.circle(glow, color + (MAGNETAR_GLOW_ALPHA,), (surf_size // 2, surf_size // 2), glow_r)
    screen.blit(glow, (draw_x - surf_size // 2, draw_y - surf_size // 2))
    pygame.draw.circle(screen, color, (draw_x, draw_y), mag.radius)


def draw_universe(screen, universe, offset_x=0, offset_y=0, show_barrier=True, show_gravity_waves=True):
    ring = universe.barrier
    if show_barrier:
        draw_barrier(screen, ring, offset_x, offset_y)
    draw_clouds(screen, universe.clouds, offset_x, offset_y)

    all_pulses = []
    for ns in universe.neutron_stars:
        for pulse_radius in ns.active_pulses:
            all_pulses.append((ns.x + offset_x, ns.y + offset_y, pulse_radius))
    for pulse in universe.black_hole_pulses:
        all_pulses.append((pulse[0] + offset_x, pulse[1] + offset_y, pulse[2]))

    # All wave rings paint one shared per-universe alpha layer (blitted once at the end)
    # instead of allocating a surface per ring — the per-ring churn was the top render cost
    # in wave storms. Within the layer, polygon pixels overwrite rather than blend, so ring
    # crossings no longer double-brighten; _crowd_dim owns storm loudness.
    pulse_layer = None
    layer_x = layer_y = 0
    if show_gravity_waves and all_pulses:
        reach = float(ring.radii.max()) + PULSE_RENDER_MARGIN
        layer_x = int(ring.center[0] + offset_x - reach)
        layer_y = int(ring.center[1] + offset_y - reach)
        side = int(2 * reach) + 2
        pulse_layer = pygame.Surface((side, side), pygame.SRCALPHA)
        for pulse in universe.black_hole_pulses:
            x, y, pulse_radius, consumed_mass = pulse
            if pulse_radius > 1:
                pulse_width = max(2, int(consumed_mass / 20))
                points = _clip_pulse_points(x + offset_x, y + offset_y, pulse_radius, ring, offset_x=offset_x, offset_y=offset_y)
                local_points = [(p[0] - layer_x, p[1] - layer_y) for p in points]
                merge_color = (*BLACK_HOLE_MERGE_COLOR[:3],
                               int(BLACK_HOLE_MERGE_COLOR[3] * _crowd_dim(all_pulses)))
                pygame.draw.polygon(pulse_layer, merge_color, local_points, pulse_width)

    for white_dwarf in universe.white_dwarfs:
        draw_white_dwarf(screen, white_dwarf, offset_x, offset_y)
    for black_hole in universe.black_holes:
        draw_black_hole(screen, black_hole, offset_x, offset_y)
    for neutron_star in universe.neutron_stars:
        draw_neutron_star(screen, neutron_star, ring, all_pulses, offset_x, offset_y,
                          pulse_layer, layer_x, layer_y)
    for magnetar in universe.magnetars:
        draw_magnetar(screen, magnetar, offset_x, offset_y)

    if pulse_layer is not None:
        screen.blit(pulse_layer, (layer_x, layer_y))


# ── World renderer (bounded surface + culling + visible-rect blit) ──────────────────────────

class WorldRenderer:
    def __init__(self):
        self.world_surface = None
        self.w = 0
        self.h = 0

    def render(self, screen, state, zoom, view_center_x, view_center_y, show_barrier=True, show_gravity_waves=True):
        screen_w, screen_h = screen.get_size()
        view_w = int(screen_w / zoom)
        view_h = int(screen_h / zoom)
        # Only the visible rect is ever blitted and the view can't pan past the start center,
        # so the world surface never needs to grow with the multiverse.
        needed_w = min(view_w + screen_w, MULTIVERSE_RENDER_MAX)
        needed_h = min(view_h + screen_h, MULTIVERSE_RENDER_MAX)
        if needed_w > self.w or needed_h > self.h:
            self.w = max(self.w, needed_w)
            self.h = max(self.h, needed_h)
            self.world_surface = pygame.Surface((self.w, self.h))

        # view_w/h can exceed the world surface when the window is wide enough (or zoomed out
        # far enough) that screen_w/zoom + screen_w blows past MULTIVERSE_RENDER_MAX — needed_w
        # then clamps below view_w, and an unclamped view_w here would build a visible_rect
        # wider than the surface, which subsurface() below rejects.
        view_w = min(view_w, self.w)
        view_h = min(view_h, self.h)

        wox = (self.w - screen_w) // 2
        woy = (self.h - screen_h) // 2
        ws_cx = wox + view_center_x
        ws_cy = woy + view_center_y
        view_left = max(0, min(self.w - view_w, int(ws_cx - view_w / 2)))
        view_top = max(0, min(self.h - view_h, int(ws_cy - view_h / 2)))
        visible_rect = pygame.Rect(view_left, view_top, view_w, view_h)

        self.world_surface.fill(BACKGROUND_COLOR)
        # LOD: below this zoom a 2px ring line downscales to under a pixel, so wave rings are
        # invisible noise that still costs full-size clipping and polygons on the world
        # surface. Skip them; everything else still draws.
        draw_waves = show_gravity_waves and zoom >= PULSE_LOD_MIN_ZOOM
        for universe in state.universes:
            # Cull universes entirely outside the view — off-screen universes cost nothing.
            bcx = universe.barrier.center[0] + wox
            bcy = universe.barrier.center[1] + woy
            reach = float(universe.barrier.radii.max()) + UNIVERSE_CULL_MARGIN
            if (bcx + reach < view_left or bcx - reach > view_left + view_w or
                    bcy + reach < view_top or bcy - reach > view_top + view_h):
                continue
            draw_universe(self.world_surface, universe, wox, woy, show_barrier, draw_waves)

        if zoom == 1.0:
            screen.blit(self.world_surface, (0, 0), area=visible_rect)
        else:
            visible_area = self.world_surface.subsurface(visible_rect)
            scaled = pygame.transform.scale(visible_area, (screen_w, screen_h))
            screen.blit(scaled, (0, 0))


# ── HUD ─────────────────────────────────────────────────────────────────────────────────────

def format_years(years):
    """Humanize a literal year count: 950 → '950', 1.2e3 → '1.2K', 3.4e6 → '3.4M',
    5.6e9 → '5.6B', 7.8e12 → '7.8T'; past the suffixes, cosmological-decade notation
    (2.5e15 → '10^15.4'), the way deep time is actually written."""
    if years >= 1e15:
        return f"10^{math.log10(years):.1f}"
    for divisor, suffix in ((1e12, 'T'), (1e9, 'B'), (1e6, 'M'), (1e3, 'K')):
        value = round(years / divisor, 1)
        if value >= 1:
            return f"{value:.1f}{suffix}"
    return f"{int(years)}"


_stats_font = None
_stats_rng_font = None

def _get_stats_fonts():
    global _stats_font, _stats_rng_font
    if _stats_font is None:
        _stats_font = pygame.font.SysFont(UI_STATS_FONT, UI_STATS_FONT_SIZE)
        _stats_rng_font = pygame.font.SysFont(UI_STATS_FONT, UI_STATS_RNG_FONT_SIZE)
    return _stats_font, _stats_rng_font


# Hit-test rect for the RNG cell, refreshed each draw — clicking it copies the number.
RNG_CELL_RECT = None

# FPS, YEAR, UNIVERSES, ENTITIES, METALLICITY — kept in sync with draw_stats's stat_cells.
_NUM_STAT_CELLS = 5


def _stats_columns(screen):
    """Column geometry for the stats table, shared with the ticker panel above it so the
    panel's width can lock to the first two columns (FPS, YEAR) instead of the full table."""
    font, rng_font = _get_stats_fonts()
    table_left = UI_LABEL_X
    table_w = screen.get_width() - 2 * UI_LABEL_X
    rng_w = rng_font.size("0" * RNG_DIGITS)[0] + 2 * UI_STATS_CELL_PAD_X
    stat_w = (table_w - rng_w) // _NUM_STAT_CELLS
    return table_left, table_w, stat_w


def draw_stats(screen, fps, current_year, universe_count, entity_count, rng_number,
               metallicity=0.0, rng_flash=0.0):
    """Full-width single-row table along the bottom of the screen, bordered, with
    UI_LABEL_X margins at the sides. The RNG output is the final cell in a larger
    font, sized to its 20-digit content; the leftover width is split evenly among
    the stat cells so the columns don't jitter as values change. METALLICITY (Z) is
    how chemically aged the multiverse is (0 = pristine Big-Bang gas).
    `rng_flash` (1→0) flashes the RNG cell white as copied-to-clipboard feedback."""
    global RNG_CELL_RECT
    font, rng_font = _get_stats_fonts()
    stat_cells = [
        f"FPS: {fps:.0f}",
        f"YEAR: {format_years(current_year)}",
        f"UNIVERSES: {universe_count}",
        f"ENTITIES: {entity_count}",
        f"METALLICITY (Z): {metallicity:.3f}",
    ]
    rng_text = f"{rng_number}" if rng_number is not None else "..."

    row_h = rng_font.get_height() + 2 * UI_STATS_CELL_PAD_Y
    row_top = screen.get_height() - UI_STATS_BOTTOM_MARGIN - row_h
    row_bottom = row_top + row_h
    table_left, table_w, stat_w = _stats_columns(screen)

    x = table_left
    for text in stat_cells:
        surf = font.render(text, True, UI_STATS_COLOR)
        screen.blit(surf, (x + UI_STATS_CELL_PAD_X,
                           row_top + (row_h - surf.get_height()) // 2))
        x += stat_w
        pygame.draw.line(screen, UI_STATS_GRID_COLOR, (x, row_top), (x, row_bottom))
    RNG_CELL_RECT = pygame.Rect(x, row_top, table_left + table_w - x, row_h)
    rng_color = interpolate_color(UI_STATS_COLOR, (255, 255, 255), max(0.0, min(1.0, rng_flash)))
    surf = rng_font.render(rng_text, True, rng_color)
    screen.blit(surf, (x + UI_STATS_CELL_PAD_X,
                       row_top + (row_h - surf.get_height()) // 2))
    pygame.draw.rect(screen, UI_STATS_GRID_COLOR, (table_left, row_top, table_w, row_h), 1)


# ── Event ticker (readout row of the stats table) ───────────────────────────────────────────

def _ticker_layout(screen):
    """Panel geometry for draw_ticker: spans from UI_TICKER_TOP_MARGIN down to the stats row,
    so the number of lines that fit follows the window height."""
    font, rng_font = _get_stats_fonts()
    stats_row_h = rng_font.get_height() + 2 * UI_STATS_CELL_PAD_Y
    stats_row_top = screen.get_height() - UI_STATS_BOTTOM_MARGIN - stats_row_h
    line_h = font.get_height() + 2
    panel_top = UI_TICKER_TOP_MARGIN
    panel_h = max(line_h, stats_row_top - panel_top)
    max_lines = max(1, (panel_h - 2 * UI_STATS_CELL_PAD_Y) // line_h)
    return line_h, stats_row_top, max_lines, UI_LABEL_X


def draw_ticker(screen, ticker):
    """Event readout panel: a live feed of the most recent events, newest at the bottom,
    fading out with age — once an entry fades it's gone for good, no scrollback. Each entry is
    a [text, age, count] triple maintained by the sim loop; repeats within a beat are coalesced
    there, so a line appears once no matter how many identical events fired (the count is
    tracked but not displayed)."""
    font, rng_font = _get_stats_fonts()
    line_h, stats_row_top, max_lines, table_left = _ticker_layout(screen)
    lines = [e for e in ticker if e[1] < UI_TICKER_LIFETIME][-max_lines:]

    y = stats_row_top - UI_STATS_CELL_PAD_Y - line_h * len(lines)  # stack anchored to the bottom
    for text, age, count in lines:
        fade = max(0.0, 1.0 - age / UI_TICKER_LIFETIME)
        color = interpolate_color(BACKGROUND_COLOR, UI_STATS_COLOR, fade)
        screen.blit(font.render(text, True, color), (table_left + UI_STATS_CELL_PAD_X, y))
        y += line_h


_elements_font = None

def _get_elements_font():
    global _elements_font
    if _elements_font is None:
        _elements_font = pygame.font.SysFont(UI_STATS_FONT, UI_ELEMENTS_FONT_SIZE, bold=True)
    return _elements_font


def draw_elements(screen, present_elements, alpha=1.0):
    """Element inventory row: one color block per element currently present anywhere in the
    multiverse, sitting directly above the stats table (the ticker's fixed-height panel floats
    higher and is ignored here, so this row stays pinned to the table regardless of how many
    log lines are actually showing). Blocks are laid out right to left, starting flush with
    the table's right edge, so the row grows leftward as the chemistry of the universe
    diversifies. Shown with the help panel and fades with its `alpha`."""
    if not present_elements or alpha <= 0:
        return
    font = _get_elements_font()
    stats_row_h = _get_stats_fonts()[1].get_height() + 2 * UI_STATS_CELL_PAD_Y
    stats_row_top = screen.get_height() - UI_STATS_BOTTOM_MARGIN - stats_row_h
    row_bottom = stats_row_top - UI_ELEMENTS_MARGIN_BOTTOM
    row_top = row_bottom - UI_ELEMENTS_BLOCK_SIZE
    table_right = screen.get_width() - UI_LABEL_X

    row_w = (UI_ELEMENTS_BLOCK_SIZE + UI_ELEMENTS_BLOCK_GAP) * len(present_elements)
    row = pygame.Surface((row_w, UI_ELEMENTS_BLOCK_SIZE), pygame.SRCALPHA)
    x = row_w - UI_ELEMENTS_BLOCK_SIZE
    for elem in reversed(present_elements):
        color = MOLECULAR_CLOUD_START_COLORS[elem]
        rect = pygame.Rect(x, 0, UI_ELEMENTS_BLOCK_SIZE, UI_ELEMENTS_BLOCK_SIZE)
        pygame.draw.rect(row, color, rect)
        # Contrast the symbol against its own block: light text on dark blocks, dark on light.
        luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        text_color = (20, 20, 20) if luminance > 140 else (235, 235, 235)
        surf = font.render(ELEMENT_SYMBOLS[elem], True, text_color)
        row.blit(surf, (rect.centerx - surf.get_width() // 2,
                        rect.centery - surf.get_height() // 2))
        x -= UI_ELEMENTS_BLOCK_SIZE + UI_ELEMENTS_BLOCK_GAP
    if alpha < 1.0:
        row.fill((255, 255, 255, int(255 * alpha)), special_flags=pygame.BLEND_RGBA_MULT)
    screen.blit(row, (table_right - row_w, row_top))


# ── Hotkey cheat sheet (top-right corner, shown on start, toggled with [H]) ─────────────────

_hotkeys_font = None

def _get_hotkeys_font():
    global _hotkeys_font
    if _hotkeys_font is None:
        _hotkeys_font = pygame.font.SysFont(UI_STATS_FONT, UI_HOTKEYS_FONT_SIZE)
    return _hotkeys_font


# (key label, description) rows.
_HOTKEY_ROWS = [
    ("H", "Toggle this help"),
    ("Q", "Quit the simulation"),
    ("R", "Reset the simulation"),
    ("L", "Toggle event log"),
    ("B", "Toggle universe barriers"),
    ("G", "Toggle gravitational waves"),
    ("SCROLL", "Zoom in and out"),
    ("CLICK", "Copy RNG output"),
]

# Entity key shown under the hotkeys: (tag, label). Each tag draws a native-size miniature
# of the entity in _draw_entity_mini, built from the same config constants as the real
# renderers so the key can't drift out of sync with what's on screen.
_ENTITY_KEY_ROWS = [
    ("clouds", "Molecular clouds"),
    ("stars", "Stars (M to O)"),
    ("red_giant", "Red giant"),
    ("carbon", "Carbon star"),
    ("brown", "Brown dwarf"),
    ("wr", "Wolf-Rayet"),
    ("wd", "White dwarf"),
    ("pulsar", "Pulsar"),
    ("dead", "Dead pulsar"),
    ("magnetar", "Magnetar"),
    ("bh", "Black hole"),
    ("civ", "Dyson Sphere"),
]


def _draw_entity_mini(panel, tag, cx, cy, a):
    """Miniature recreation of an entity at native sim scale, centered at (cx, cy), with
    per-pixel alpha `a` so it fades with the help panel. Each mini follows the entity's real
    draw recipe (same constants), just without the live state behind it."""
    if tag == "clouds":
        # Three overlapping block-cluster clouds at different sizes, same recipe as
        # draw_clouds (block count grows as size shrinks, translucent element colors) with
        # fixed offsets standing in for the per-cloud random block layout.
        cloud_specs = [  # (size, element index, center dx, dy, fixed block offsets)
            (12, 0, -5, -1, [(0.0, -0.14), (0.18, 0.08), (-0.16, 0.10), (0.08, 0.20), (-0.06, -0.06)]),
            (8, 1, 3, 2,    [(-0.12, -0.16), (0.16, 0.0), (0.0, 0.18), (-0.18, 0.08), (0.10, 0.12)]),
            (5, 3, 9, -3,   [(0.14, -0.10), (-0.12, -0.04), (0.04, 0.16), (0.18, 0.10), (-0.06, 0.20), (0.0, 0.0)]),
        ]
        for s, elem, dx, dy, offs in cloud_specs:
            col = MOLECULAR_CLOUD_START_COLORS[elem]
            block_r = max(1, int(s * 0.3))
            rgba = (*col, int(MOLECULAR_CLOUD_OPACITY * a / 255))
            num_blocks = min(3 + (MOLECULAR_CLOUD_START_SIZE - s) // 4, len(offs))
            for ox, oy in offs[:num_blocks]:
                bx = int(cx + dx + ox * s)
                by = int(cy + dy + oy * s)
                pygame.draw.rect(panel, rgba, (bx - block_r, by - block_r, block_r * 2, block_r * 2))
    elif tag == "stars":
        sizes = [s for _m, _n, _c, s in reversed(STAR_CLASSES)]
        colors = [c for _m, _n, c, _s in reversed(STAR_CLASSES)]
        total_w = sum(sizes) + 2 * (len(sizes) - 1)
        x = cx - total_w // 2
        for size, color in zip(sizes, colors):  # bottom-aligned ladder, M up to O
            pygame.draw.rect(panel, (*color, a), (x, cy + 3 - size, size, size))
            x += size + 2
    elif tag == "red_giant":
        s = RED_GIANT_DRAW_SIZE
        pygame.draw.rect(panel, (*RED_GIANT_COLOR, a), (cx - s // 2, cy - s // 2, s, s))
    elif tag == "carbon":
        pygame.draw.rect(panel, (*CARBON_STAR_COLOR, a), (cx - 1, cy - 1, 3, 3))
    elif tag == "brown":
        pygame.draw.rect(panel, (*BROWN_DWARF_COLOR, a), (cx - 1, cy - 1, 3, 3))
    elif tag == "wr":
        size = STAR_CLASSES[0][3]  # the O-class square the shell sheds from
        pygame.draw.rect(panel, (*STAR_CLASSES[0][2], a), (cx - size // 2, cy - size // 2, size, size))
        pygame.draw.circle(panel, (*WOLF_RAYET_SHELL_COLOR, a), (cx, cy), size + 2, 1)
    elif tag == "wd":
        pygame.draw.circle(panel, (*WHITE_DWARF_COLOR, a), (cx, cy), WHITE_DWARF_RADIUS)
    elif tag in ("pulsar", "dead"):
        color = NEUTRON_STAR_COLOR if tag == "pulsar" else NEUTRON_STAR_DEAD_COLOR
        if tag == "pulsar":  # mid-flash, as drawn on a live pulsar: white stretched beam at the wobble tilt
            jl = NEUTRON_STAR_JET_FLASH_LENGTH
            ux = math.sin(math.radians(NEUTRON_STAR_JET_WOBBLE))
            uy = -math.cos(math.radians(NEUTRON_STAR_JET_WOBBLE))
            pygame.draw.line(panel, (255, 255, 255, a), (cx - ux * jl, cy - uy * jl),
                             (cx + ux * jl, cy + uy * jl), NEUTRON_STAR_JET_WIDTH)
        core = NEUTRON_STAR_RADIUS * 2 + 1
        pygame.draw.rect(panel, (*color, a),
                         (cx - NEUTRON_STAR_RADIUS, cy - NEUTRON_STAR_RADIUS, core, core))
    elif tag == "magnetar":
        pygame.draw.circle(panel, (*MAGNETAR_COLOR_A, min(a, int(MAGNETAR_GLOW_ALPHA))),
                           (cx, cy), MAGNETAR_RADIUS + 3)
        pygame.draw.circle(panel, (*MAGNETAR_COLOR_A, a), (cx, cy), MAGNETAR_RADIUS)
    elif tag == "bh":
        # Feeding state: the heated-horizon crescent from draw_black_hole, frozen at a strong
        # heat with the meal coming from the right — same segment/falloff math, no live state.
        r = 5
        heat, sharp, meal_ang = 0.8, 1.0, 0.0
        floor = BLACK_HOLE_FLARE_FAR_SIDE_FLOOR
        step = 2.0 * math.pi / BLACK_HOLE_RING_SEGMENTS
        mids = [i * step + step * 0.5 for i in range(BLACK_HOLE_RING_SEGMENTS)]
        profile = [floor + (1.0 - floor) * (0.5 + 0.5 * math.cos(m - meal_ang)) ** BLACK_HOLE_FLARE_CRESCENT_POWER
                   for m in mids]
        mean_p = sum(profile) / len(profile)
        for i in range(BLACK_HOLE_RING_SEGMENTS):
            a0 = i * step
            seg_heat = min(1.0, heat * ((1.0 - sharp) + sharp * profile[i] / mean_p))
            seg_color = interpolate_color(BLACK_HOLE_BORDER_COLOR, BLACK_HOLE_FLARE_COLOR, seg_heat)
            pygame.draw.line(panel, (*seg_color, a),
                             (cx + r * math.cos(a0), cy + r * math.sin(a0)),
                             (cx + r * math.cos(a0 + step), cy + r * math.sin(a0 + step)), 2)
        pygame.draw.circle(panel, (*BLACK_HOLE_COLOR, a), (cx, cy), r - 2)
        pygame.draw.circle(panel, (*BLACK_HOLE_DISK_COLOR, a), (cx, cy - r + 1), 1)
    elif tag == "civ":
        ring_r = 2 + CIVILIZATION_RING_PADDING  # a G-dwarf's sprite radius + padding
        for i in range(CIVILIZATION_RING_DOT_COUNT):
            angle = (2 * math.pi / CIVILIZATION_RING_DOT_COUNT) * i
            pygame.draw.circle(panel, (*CIVILIZATION_RING_COLOR, a),
                               (int(cx + ring_r * math.cos(angle)), int(cy + ring_r * math.sin(angle))),
                               CIVILIZATION_RING_DOT_RADIUS)
        pygame.draw.circle(panel, (*CIVILIZATION_DISC_COLOR, a), (cx, cy),
                           2 + CIVILIZATION_DISC_PADDING)


def hotkeys_alpha(age):
    """Opacity (1 → 0) for the hotkey panel `age` seconds after it was last shown: fully
    opaque for UI_HOTKEYS_HOLD_SECONDS, then a linear fade over UI_HOTKEYS_FADE_SECONDS."""
    if age < UI_HOTKEYS_HOLD_SECONDS:
        return 1.0
    fade_t = age - UI_HOTKEYS_HOLD_SECONDS
    if fade_t >= UI_HOTKEYS_FADE_SECONDS:
        return 0.0
    return 1.0 - fade_t / UI_HOTKEYS_FADE_SECONDS


def draw_hotkeys(screen, alpha):
    """Hotkey cheat sheet plus entity key, one translucent panel in the top-right corner.
    `alpha` (1 → 0) fades the background, text, and swatches uniformly as the panel ages
    out."""
    if alpha <= 0:
        return
    font = _get_hotkeys_font()
    key_surfs = [font.render(f"[{key}]", True, UI_HOTKEYS_KEY_COLOR) for key, _ in _HOTKEY_ROWS]
    label_surfs = [font.render(label, True, UI_HOTKEYS_TEXT_COLOR) for _, label in _HOTKEY_ROWS]
    key_w = max(s.get_width() for s in key_surfs)
    row_h = font.get_height() + UI_HOTKEYS_ROW_SPACING

    entity_labels = [font.render(label, True, UI_HOTKEYS_TEXT_COLOR)
                     for _t, label in _ENTITY_KEY_ROWS]
    # Mini column: as wide as the key column but at least wide enough for the star ladder;
    # entity rows are a touch taller than text rows so the larger minis (Wolf-Rayet shell,
    # red giant) don't collide.
    mini_w = max(key_w, sum(s for _m, _n, _c, s in STAR_CLASSES) + 2 * (len(STAR_CLASSES) - 1))
    entity_row_h = max(row_h, 18)
    entity_row_w = max(mini_w + UI_HOTKEYS_KEY_GAP + s.get_width() for s in entity_labels)

    row_w = max(key_w + UI_HOTKEYS_KEY_GAP + max(s.get_width() for s in label_surfs),
                entity_row_w)
    panel_w = row_w + 2 * UI_HOTKEYS_PAD
    panel_h = (len(_HOTKEY_ROWS) * row_h + len(_ENTITY_KEY_ROWS) * entity_row_h
               + row_h // 2 + 2 * UI_HOTKEYS_PAD)  # half-row divider gap between sections
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((*UI_HOTKEYS_BG[:3], int(UI_HOTKEYS_BG[3] * alpha)))

    # Scale each glyph surface's existing per-pixel alpha (antialiasing) by the fade factor —
    # Surface.set_alpha is ignored on per-pixel-alpha surfaces, so a multiply blend is used
    # instead of a flat opacity call.
    fade_mult = (255, 255, 255, int(255 * alpha))
    swatch_alpha = int(255 * alpha)
    y = UI_HOTKEYS_PAD
    for key_surf, label_surf in zip(key_surfs, label_surfs):
        key_surf.fill(fade_mult, special_flags=pygame.BLEND_RGBA_MULT)
        label_surf.fill(fade_mult, special_flags=pygame.BLEND_RGBA_MULT)
        panel.blit(key_surf, (UI_HOTKEYS_PAD, y))
        panel.blit(label_surf, (UI_HOTKEYS_PAD + key_w + UI_HOTKEYS_KEY_GAP, y))
        y += row_h

    y += row_h // 2
    for (tag, _label), label_surf in zip(_ENTITY_KEY_ROWS, entity_labels):
        _draw_entity_mini(panel, tag, UI_HOTKEYS_PAD + mini_w // 2,
                          y + entity_row_h // 2 - 1, swatch_alpha)
        label_surf.fill(fade_mult, special_flags=pygame.BLEND_RGBA_MULT)
        panel.blit(label_surf, (UI_HOTKEYS_PAD + mini_w + UI_HOTKEYS_KEY_GAP,
                                y + (entity_row_h - font.get_height()) // 2))
        y += entity_row_h

    screen.blit(panel, (screen.get_width() - panel_w - UI_HOTKEYS_MARGIN, UI_HOTKEYS_MARGIN))
