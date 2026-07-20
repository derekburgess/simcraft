"""All drawing. Reads the simulation state (arrays + compact objects) and never mutates
physics — except black_hole.border_radius, which has always been refreshed at draw time.

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
_STAR_COLOR_LUT = (np.array(PROTOSTAR_LOW_COLOR, dtype=float),
                   np.array(PROTOSTAR_MEDIUM_COLOR, dtype=float),
                   np.array(PROTOSTAR_HIGH_COLOR, dtype=float))


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
    """Vectorized size/color/opacity, same formulas the object version computed per cloud."""
    n = clouds.n
    mass = clouds.M
    size = clouds.SIZE.astype(np.int64)
    elem = clouds.ELEM
    is_star = clouds.IS_STAR

    factor = np.clip((mass - MOLECULAR_CLOUD_START_MASS) / (PROTOSTAR_THRESHOLD - MOLECULAR_CLOUD_START_MASS), 0.0, 1.0)
    opacity = (MOLECULAR_CLOUD_MIN_OPACITY + factor * (MOLECULAR_CLOUD_OPACITY - MOLECULAR_CLOUD_MIN_OPACITY)).astype(np.int64)
    opacity = np.where(is_star, 255, opacity)

    start = _START_COLOR_LUT[elem]
    f2 = np.clip(1.0 - (size - 4) / (MOLECULAR_CLOUD_START_SIZE - 4), None, None)[:, None]
    color = np.where((size <= 4)[:, None], _END_COLOR, start + f2 * (_END_COLOR - start))
    # Star color follows MASS — the real temperature sequence: small red, sun-like white, massive blue.
    tier = np.select([mass >= STAR_TIER_HIGH_MASS, mass >= STAR_TIER_MEDIUM_MASS],
                     [2, 1], 0)
    star_color = np.stack(_STAR_COLOR_LUT)[tier]
    color = np.where(is_star[:, None], star_color, color).astype(np.int64)
    return size, color, opacity


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


# ── Pulses / compact objects ────────────────────────────────────────────────────────────────

def _clip_pulse_points(origin_x, origin_y, pulse_radius, ring, all_pulses, num_pts=PULSE_RENDER_POINT_COUNT, offset_x=0, offset_y=0):
    """Vectorized over the ring points (the old per-point/per-pulse Python loops were a top
    frame cost once many pulses coexist). Pulses are still applied in list order — each
    point's clamp sequence is unchanged, so the geometry is the same math as the scalar loop."""
    cx = ring.center[0] + offset_x
    cy = ring.center[1] + offset_y
    theta = (2 * math.pi / num_pts) * np.arange(num_pts)
    px = origin_x + pulse_radius * np.cos(theta)
    py = origin_y + pulse_radius * np.sin(theta)

    for ox, oy, o_radius, _ in all_pulses:
        if abs(ox - origin_x) < 0.1 and abs(oy - origin_y) < 0.1:
            continue
        dx_op = px - ox
        dy_op = py - oy
        dist = np.hypot(dx_op, dy_op)
        inside = (dist < o_radius) & (dist > 0)
        if inside.any():
            scale = o_radius / dist[inside]
            px[inside] = ox + dx_op[inside] * scale
            py[inside] = oy + dy_op[inside] * scale

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
    radius = int(bh.mass // BLACK_HOLE_RADIUS)
    bh.border_radius = radius
    pygame.draw.circle(screen, BLACK_HOLE_BORDER_COLOR, (draw_x, draw_y), radius)
    pygame.draw.circle(screen, BLACK_HOLE_COLOR, (draw_x, draw_y), radius - 2)

    if bh.is_flaring:
        jet_length = bh.flare_length
        base_half = max(1, radius * BLACK_HOLE_FLARE_BASE_FRACTION)
        for sign in (1, -1):
            y_base = draw_y + sign * radius
            y_tip = draw_y + sign * (radius + jet_length)
            pygame.draw.polygon(screen, BLACK_HOLE_FLARE_COLOR, [
                (draw_x - base_half, y_base),
                (draw_x + base_half, y_base),
                (draw_x, y_tip),
            ])

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


def draw_neutron_star(screen, ns, ring, all_pulses, offset_x=0, offset_y=0):
    draw_x = int(ns.x + offset_x)
    draw_y = int(ns.y + offset_y)
    pulse_ox = ns.x + offset_x
    pulse_oy = ns.y + offset_y
    current_color = NEUTRON_STAR_DEAD_COLOR if ns.is_dead else NEUTRON_STAR_COLOR

    if not ns.is_dead:  # jets are the beam that dies with the pulsar, not a separate fade
        flashing = ns.pulse_color_state == 1
        jet_color = (255, 255, 255) if flashing else NEUTRON_STAR_COLOR
        jet_length = NEUTRON_STAR_JET_FLASH_LENGTH if flashing else NEUTRON_STAR_JET_LENGTH
        pygame.draw.line(screen, jet_color, (draw_x, draw_y - jet_length),
                          (draw_x, draw_y + jet_length), NEUTRON_STAR_JET_WIDTH)

    # pygame.draw.circle at radius 1 rasterizes as a 2px blob offset from (draw_x, draw_y),
    # which would visibly throw off the jet's alignment through the core — a symmetric square
    # keeps a true center pixel at (draw_x, draw_y) for the jet line to line up with.
    core_size = ns.radius * 2 + 1
    pygame.draw.rect(screen, current_color, (draw_x - ns.radius, draw_y - ns.radius, core_size, core_size))

    for pulse in ns.active_pulses:
        pulse_radius, _, fade = pulse
        if pulse_radius <= 1:
            continue
        alpha = max(0, min(255, int(NEUTRON_STAR_PULSE_COLOR[3] * fade * _crowd_dim(all_pulses))))
        if alpha == 0:
            continue
        points = _clip_pulse_points(pulse_ox, pulse_oy, pulse_radius, ring, all_pulses, offset_x=offset_x, offset_y=offset_y)
        color = (NEUTRON_STAR_PULSE_COLOR[0], NEUTRON_STAR_PULSE_COLOR[1], NEUTRON_STAR_PULSE_COLOR[2], alpha)
        min_x = min(p[0] for p in points) - PULSE_RENDER_MARGIN
        min_y = min(p[1] for p in points) - PULSE_RENDER_MARGIN
        max_x = max(p[0] for p in points) + PULSE_RENDER_MARGIN
        max_y = max(p[1] for p in points) + PULSE_RENDER_MARGIN
        w = max_x - min_x
        h = max_y - min_y
        if w > 0 and h > 0:
            pulse_surface = pygame.Surface((w, h), pygame.SRCALPHA)
            local_points = [(p[0] - min_x, p[1] - min_y) for p in points]
            pygame.draw.polygon(pulse_surface, color, local_points, NEUTRON_STAR_PULSE_WIDTH)
            screen.blit(pulse_surface, (min_x, min_y))


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


def draw_universe(screen, universe, offset_x=0, offset_y=0):
    ring = universe.barrier
    draw_barrier(screen, ring, offset_x, offset_y)
    draw_clouds(screen, universe.clouds, offset_x, offset_y)

    all_pulses = []
    for ns in universe.neutron_stars:
        for pulse in ns.active_pulses:
            all_pulses.append((ns.x + offset_x, ns.y + offset_y, pulse[0], pulse[2]))
    for pulse in universe.black_hole_pulses:
        all_pulses.append((pulse[0] + offset_x, pulse[1] + offset_y, pulse[2], 1.0))

    for pulse in universe.black_hole_pulses:
        x, y, pulse_radius, consumed_mass = pulse
        if pulse_radius > 1:
            draw_x = x + offset_x
            draw_y = y + offset_y
            pulse_width = max(2, int(consumed_mass / 20))
            points = _clip_pulse_points(draw_x, draw_y, pulse_radius, ring, all_pulses, offset_x=offset_x, offset_y=offset_y)
            min_x = min(p[0] for p in points) - PULSE_RENDER_MARGIN
            min_y = min(p[1] for p in points) - PULSE_RENDER_MARGIN
            max_x = max(p[0] for p in points) + PULSE_RENDER_MARGIN
            max_y = max(p[1] for p in points) + PULSE_RENDER_MARGIN
            w = max_x - min_x
            h = max_y - min_y
            if w > 0 and h > 0:
                pulse_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                local_points = [(p[0] - min_x, p[1] - min_y) for p in points]
                merge_color = (*BLACK_HOLE_MERGE_COLOR[:3],
                               int(BLACK_HOLE_MERGE_COLOR[3] * _crowd_dim(all_pulses)))
                pygame.draw.polygon(pulse_surface, merge_color, local_points, pulse_width)
                screen.blit(pulse_surface, (min_x, min_y))

    for white_dwarf in universe.white_dwarfs:
        draw_white_dwarf(screen, white_dwarf, offset_x, offset_y)
    for black_hole in universe.black_holes:
        draw_black_hole(screen, black_hole, offset_x, offset_y)
    for neutron_star in universe.neutron_stars:
        draw_neutron_star(screen, neutron_star, ring, all_pulses, offset_x, offset_y)
    for magnetar in universe.magnetars:
        draw_magnetar(screen, magnetar, offset_x, offset_y)


# ── World renderer (bounded surface + culling + visible-rect blit) ──────────────────────────

class WorldRenderer:
    def __init__(self):
        self.world_surface = None
        self.w = 0
        self.h = 0

    def render(self, screen, state, zoom, view_center_x, view_center_y):
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

        wox = (self.w - screen_w) // 2
        woy = (self.h - screen_h) // 2
        ws_cx = wox + view_center_x
        ws_cy = woy + view_center_y
        view_left = max(0, min(self.w - view_w, int(ws_cx - view_w / 2)))
        view_top = max(0, min(self.h - view_h, int(ws_cy - view_h / 2)))
        visible_rect = pygame.Rect(view_left, view_top, view_w, view_h)

        self.world_surface.fill(BACKGROUND_COLOR)
        for universe in state.universes:
            # Cull universes entirely outside the view — off-screen universes cost nothing.
            bcx = universe.barrier.center[0] + wox
            bcy = universe.barrier.center[1] + woy
            reach = float(universe.barrier.radii.max()) + UNIVERSE_CULL_MARGIN
            if (bcx + reach < view_left or bcx - reach > view_left + view_w or
                    bcy + reach < view_top or bcy - reach > view_top + view_h):
                continue
            draw_universe(self.world_surface, universe, wox, woy)

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


def format_year_display(current_year):
    return f"TIME(YEARS): {format_years(current_year)}"


def draw_static_key(screen, font, zoom):
    screen_h = screen.get_height()
    snapshot_pos = (UI_LABEL_X, screen_h - UI_ZOOM_Y_OFFSET)
    if zoom != 1.0:
        zoom_text = f'[SCROLL] ZOOM: {zoom:.1f}x'
    else:
        zoom_text = '[SCROLL] ZOOM'
    screen.blit(font.render(zoom_text, True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))
    snapshot_pos = (UI_LABEL_X, screen_h - UI_EXIT_Y_OFFSET)
    screen.blit(font.render('[Q] EXIT', True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))
    snapshot_pos = (UI_LABEL_X, screen_h - UI_EXIT_Y_OFFSET - 30)
    screen.blit(font.render('[F11] FULLSCREEN', True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))


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


def draw_stats(screen, fps, current_year, universe_count, entity_count, salt_folds, rng_number,
               metallicity=0.0, rng_flash=0.0):
    """Full-width single-row table along the bottom of the screen, bordered, with
    UI_LABEL_X margins at the sides. The RNG output is the final cell in a larger
    font, sized to its 20-digit content; the leftover width is split evenly among
    the stat cells so the columns don't jitter as values change. SALT is the
    entropy-pool fold count feeding the RNG output beside it. Z is the mean
    metallicity — how chemically aged the multiverse is (0 = pristine Big-Bang gas).
    `rng_flash` (1→0) flashes the RNG cell white as copied-to-clipboard feedback."""
    global RNG_CELL_RECT
    font, rng_font = _get_stats_fonts()
    stat_cells = [
        f"FPS: {fps:.0f}",
        f"YEAR: {format_years(current_year)}",
        f"UNIVERSES: {universe_count}",
        f"ENTITIES: {entity_count}",
        f"METALLICITY: {metallicity:.3f}",
        f"SALT: {salt_folds:,}",
    ]
    rng_text = f"{rng_number}" if rng_number is not None else "..."

    row_h = rng_font.get_height() + 2 * UI_STATS_CELL_PAD_Y
    row_top = screen.get_height() - UI_STATS_BOTTOM_MARGIN - row_h
    row_bottom = row_top + row_h
    table_left = UI_LABEL_X
    table_w = screen.get_width() - 2 * UI_LABEL_X

    rng_w = rng_font.size("0" * RNG_DIGITS)[0] + 2 * UI_STATS_CELL_PAD_X
    stat_w = (table_w - rng_w) // len(stat_cells)

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


def draw_ui(screen, font, current_year, zoom=1.0):
    draw_static_key(screen, font, zoom)
    year_text = font.render(format_year_display(current_year), True, LABEL_COLOR)
    screen.blit(year_text, (UI_LABEL_X, screen.get_height() - UI_TEXT_Y_OFFSET))


# ── Event ticker (readout row of the stats table) ───────────────────────────────────────────

# Hit-test rect for the readout panel, refreshed each draw. The input handler uses it to
# decide whether a mouse-wheel tick scrolls the log (cursor over the panel) or zooms.
TICKER_PANEL_RECT = None


def draw_ticker(screen, ticker, offset=0):
    """Event readout row: a single full-width cell spanning the table, sitting directly on
    top of the stats row. Events stack inside it as a live feed — newest at the bottom,
    fading out with age. Each entry is a [text, age, count] triple maintained by the sim
    loop; repeats within a beat are coalesced there, so a line appears once no matter how
    many identical events fired (the count is tracked but not displayed).

    `offset` scrolls back through history: 0 = live (fading feed); >0 shows entries that
    far back from the newest, at full brightness so old history stays readable."""
    global TICKER_PANEL_RECT
    font, rng_font = _get_stats_fonts()
    stats_row_h = rng_font.get_height() + 2 * UI_STATS_CELL_PAD_Y
    stats_row_top = screen.get_height() - UI_STATS_BOTTOM_MARGIN - stats_row_h
    line_h = font.get_height() + 2
    panel_h = UI_TICKER_MAX_LINES * line_h + 2 * UI_STATS_CELL_PAD_Y
    panel_top = stats_row_top - panel_h
    table_left = UI_LABEL_X
    table_w = screen.get_width() - 2 * UI_LABEL_X
    TICKER_PANEL_RECT = pygame.Rect(table_left, panel_top, table_w, panel_h)

    if offset > 0:
        end = len(ticker) - offset
        lines = [(text, 0.0, count) for text, _, count in ticker[max(0, end - UI_TICKER_MAX_LINES):end]]
    else:
        lines = [e for e in ticker if e[1] < UI_TICKER_LIFETIME][-UI_TICKER_MAX_LINES:]

    # No border: the feed floats above the stats table (TICKER_PANEL_RECT still marks the
    # area so the mouse wheel scrolls the log when hovering here).
    y = stats_row_top - UI_STATS_CELL_PAD_Y - line_h * len(lines)  # stack anchored to the bottom
    for text, age, count in lines:
        fade = max(0.0, 1.0 - age / UI_TICKER_LIFETIME)
        color = interpolate_color(BACKGROUND_COLOR, UI_STATS_COLOR, fade)
        screen.blit(font.render(text, True, color), (table_left + UI_STATS_CELL_PAD_X, y))
        y += line_h


# ── Legend (toggled with [L]) ───────────────────────────────────────────────────────────────

_legend_font = None

def _get_legend_font():
    global _legend_font
    if _legend_font is None:
        _legend_font = pygame.font.SysFont(UI_STATS_FONT, UI_LEGEND_FONT_SIZE)
    return _legend_font


# (swatch color, label) rows; None color = section header.
_LEGEND_ROWS = [
    (None, "ENTITIES"),
    (PROTOSTAR_LOW_COLOR, "Red dwarf — cool, almost immortal"),
    (PROTOSTAR_MEDIUM_COLOR, "Sun-like star"),
    (PROTOSTAR_HIGH_COLOR, "Blue giant — lives fast, dies violently"),
    (WHITE_DWARF_COLOR, "White dwarf — cooling stellar core"),
    (NEUTRON_STAR_COLOR, "Pulsar — spinning neutron star"),
    (NEUTRON_STAR_DEAD_COLOR, "Dead pulsar — past the death line"),
    (MAGNETAR_COLOR_A, "Magnetar — extreme magnetic field"),
    (BLACK_HOLE_BORDER_COLOR, "Black hole — event horizon ring"),
    (BARRIER_COLOR, "Barrier — the edge of a universe"),
    (None, "ELEMENTS (cloud colors)"),
] + list(zip(MOLECULAR_CLOUD_START_COLORS, ELEMENT_NAMES))


def draw_legend(screen):
    """Key to every entity and element color, drawn as a translucent panel on the right."""
    font = _get_legend_font()
    rendered = []
    max_w = 0
    for color, label in _LEGEND_ROWS:
        surf = font.render(label, True,
                           UI_LEGEND_HEADER_COLOR if color is None else UI_LEGEND_TEXT_COLOR)
        rendered.append((color, surf))
        w = surf.get_width() + (UI_LEGEND_SWATCH + 8 if color is not None else 0)
        max_w = max(max_w, w)

    panel_w = max_w + 2 * UI_LEGEND_PAD
    panel_h = len(rendered) * UI_LEGEND_ROW_HEIGHT + 2 * UI_LEGEND_PAD
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill(UI_LEGEND_BG)
    y = UI_LEGEND_PAD
    for color, surf in rendered:
        x = UI_LEGEND_PAD
        if color is not None:
            sw_y = y + (UI_LEGEND_ROW_HEIGHT - UI_LEGEND_SWATCH) // 2
            pygame.draw.rect(panel, color, (x, sw_y, UI_LEGEND_SWATCH, UI_LEGEND_SWATCH))
            x += UI_LEGEND_SWATCH + 8
        panel.blit(surf, (x, y + (UI_LEGEND_ROW_HEIGHT - surf.get_height()) // 2))
        y += UI_LEGEND_ROW_HEIGHT
    screen.blit(panel, (screen.get_width() - panel_w - UI_LEGEND_MARGIN, UI_LEGEND_MARGIN))
