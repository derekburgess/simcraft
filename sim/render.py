"""All drawing. Reads the simulation state (arrays + compact objects) and never mutates
physics — except black_hole.border_radius, which has always been refreshed at draw time.

The world surface is sized to the view plus a margin (capped by MULTIVERSE_RENDER_MAX), never
to the full extent of the multiverse, and universes fully outside the view are culled.
"""
import math

import numpy as np
import pygame

from sim.config import *

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
    tier = np.select([elem >= PROTOSTAR_ELEMENT_WEIGHT_HEAVY, elem >= PROTOSTAR_ELEMENT_WEIGHT_MEDIUM],
                     [2, 1], 0)
    star_color = np.stack(_STAR_COLOR_LUT)[tier]
    color = np.where(is_star[:, None], star_color, color).astype(np.int64)
    return size, color, opacity


def draw_clouds(screen, clouds, offset_x=0, offset_y=0):
    if clouds.n == 0:
        return
    size, color, opacity = _cloud_visuals(clouds)
    X = clouds.X
    Y = clouds.Y
    is_star = clouds.IS_STAR
    offsets = clouds.offsets
    sprites = clouds.sprites
    keys = clouds.sprite_keys
    for k in range(clouds.n):
        s = int(size[k])
        col = (int(color[k, 0]), int(color[k, 1]), int(color[k, 2]))
        if is_star[k]:
            pygame.draw.rect(screen, col, (X[k] + offset_x, Y[k] + offset_y, s, s))
            continue
        # Translucent block-cluster sprite, rebuilt only when size/color/opacity change.
        key = (s, col, int(opacity[k]))
        if keys[k] != key:
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
            keys[k] = key
        center_x = int(X[k] + s / 2 + offset_x)
        center_y = int(Y[k] + s / 2 + offset_y)
        screen.blit(sprites[k], (center_x - s, center_y - s))


# ── Pulses / compact objects ────────────────────────────────────────────────────────────────

def _clip_pulse_points(origin_x, origin_y, pulse_radius, ring, all_pulses, num_pts=PULSE_RENDER_POINT_COUNT, offset_x=0, offset_y=0):
    cx = ring.center[0] + offset_x
    cy = ring.center[1] + offset_y
    points = []
    for k in range(num_pts):
        theta = (2 * math.pi / num_pts) * k
        px = origin_x + pulse_radius * math.cos(theta)
        py = origin_y + pulse_radius * math.sin(theta)

        for ox, oy, o_radius, _ in all_pulses:
            if abs(ox - origin_x) < 0.1 and abs(oy - origin_y) < 0.1:
                continue
            dx_op = px - ox
            dy_op = py - oy
            dist_to_other = math.hypot(dx_op, dy_op)
            if dist_to_other < o_radius and dist_to_other > 0:
                px = ox + o_radius * dx_op / dist_to_other
                py = oy + o_radius * dy_op / dist_to_other

        dxc = px - cx
        dyc = py - cy
        dist_from_center = math.hypot(dxc, dyc)
        if dist_from_center > 0:
            barrier_angle = math.atan2(dyc, dxc) % (2 * math.pi)
            barrier_r = ring.get_radius_at_angle(barrier_angle)
            if dist_from_center > barrier_r - PULSE_BARRIER_CLIP_MARGIN:
                px = cx + (barrier_r - PULSE_BARRIER_CLIP_MARGIN) * math.cos(barrier_angle)
                py = cy + (barrier_r - 4) * math.sin(barrier_angle)

        points.append((int(px), int(py)))
    return points


def draw_black_hole(screen, bh, offset_x=0, offset_y=0):
    draw_x = int(bh.x + offset_x)
    draw_y = int(bh.y + offset_y)
    radius = int(bh.mass // BLACK_HOLE_RADIUS)
    bh.border_radius = radius
    pygame.draw.circle(screen, BLACK_HOLE_BORDER_COLOR, (draw_x, draw_y), radius)
    pygame.draw.circle(screen, BLACK_HOLE_COLOR, (draw_x, draw_y), radius - 2)

    tracer_x = draw_x + bh.border_radius * math.cos(bh.tracer_angle)
    tracer_y = draw_y + bh.border_radius * math.sin(bh.tracer_angle)
    pygame.draw.circle(screen, BLACK_HOLE_DISK_COLOR, (int(tracer_x), int(tracer_y)), BLACK_HOLE_DISK_SIZE)


def draw_neutron_star(screen, ns, ring, all_pulses, offset_x=0, offset_y=0):
    draw_x = int(ns.x + offset_x)
    draw_y = int(ns.y + offset_y)
    pulse_ox = ns.x + offset_x
    pulse_oy = ns.y + offset_y
    current_color = (255, 255, 255) if ns.pulse_color_state == 1 else NEUTRON_STAR_COLOR
    pygame.draw.circle(screen, current_color, (draw_x, draw_y), ns.radius)

    for pulse in ns.active_pulses:
        pulse_radius, _, fade = pulse
        if pulse_radius <= 1:
            continue
        alpha = max(0, min(255, int(NEUTRON_STAR_PULSE_COLOR[3] * fade)))
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
                pygame.draw.polygon(pulse_surface, BLACK_HOLE_MERGE_COLOR, local_points, pulse_width)
                screen.blit(pulse_surface, (min_x, min_y))

    for black_hole in universe.black_holes:
        draw_black_hole(screen, black_hole, offset_x, offset_y)
    for neutron_star in universe.neutron_stars:
        draw_neutron_star(screen, neutron_star, ring, all_pulses, offset_x, offset_y)


# ── World renderer (bounded surface + culling + visible-rect blit) ──────────────────────────

class WorldRenderer:
    def __init__(self):
        self.world_surface = None
        self.w = 0
        self.h = 0

    def render(self, screen, state, zoom, view_center_x, view_center_y):
        view_w = int(SCREEN_WIDTH / zoom)
        view_h = int(SCREEN_HEIGHT / zoom)
        # Only the visible rect is ever blitted and the view can't pan past the start center,
        # so the world surface never needs to grow with the multiverse.
        needed_w = min(view_w + SCREEN_WIDTH, MULTIVERSE_RENDER_MAX)
        needed_h = min(view_h + SCREEN_HEIGHT, MULTIVERSE_RENDER_MAX)
        if needed_w > self.w or needed_h > self.h:
            self.w = max(self.w, needed_w)
            self.h = max(self.h, needed_h)
            self.world_surface = pygame.Surface((self.w, self.h))

        wox = (self.w - SCREEN_WIDTH) // 2
        woy = (self.h - SCREEN_HEIGHT) // 2
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
            scaled = pygame.transform.scale(visible_area, (SCREEN_WIDTH, SCREEN_HEIGHT))
            screen.blit(scaled, (0, 0))


# ── HUD ─────────────────────────────────────────────────────────────────────────────────────

def format_year_display(current_year):
    if current_year >= 1_000_000:
        return "TIME(YEARS): ∞"
    elif current_year >= 1_000:
        return f"TIME(YEARS): {current_year / 1_000:.1f}B"
    else:
        return f"TIME(YEARS): {int(current_year)}M"


def draw_static_key(screen, font, zoom):
    snapshot_pos = (UI_LABEL_X, SCREEN_HEIGHT - UI_ZOOM_Y_OFFSET)
    if zoom != 1.0:
        zoom_text = f'[SCROLL] ZOOM: {zoom:.1f}x'
    else:
        zoom_text = '[SCROLL] ZOOM'
    screen.blit(font.render(zoom_text, True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))
    snapshot_pos = (UI_LABEL_X, SCREEN_HEIGHT - UI_EXIT_Y_OFFSET)
    screen.blit(font.render('[Q] EXIT', True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))
    snapshot_pos = (UI_LABEL_X, SCREEN_HEIGHT - UI_EXIT_Y_OFFSET - 30)
    screen.blit(font.render('[F11] FULLSCREEN', True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))


def draw_ui(screen, font, current_year, zoom=1.0):
    draw_static_key(screen, font, zoom)
    year_text = font.render(format_year_display(current_year), True, LABEL_COLOR)
    screen.blit(year_text, (UI_LABEL_X, SCREEN_HEIGHT - UI_TEXT_Y_OFFSET))
