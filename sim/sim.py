import os
import pygame
import math
import random
import bisect


GRAVITY_SCALE = 0.15

BARRIER_POINT_COUNT = 600
BARRIER_GRAVITY_CONSTANT = 120 * GRAVITY_SCALE
BARRIER_COLOR = (30, 60, 220)
BARRIER_BASE_OPACITY = 150
BARRIER_FLASH_COLOR = (0, 184, 106)
BARRIER_FLASH_OPACITY = 255
BARRIER_FLASH_DECAY = 3.0
BARRIER_WAVE_PUSH = 400.0
BARRIER_DAMPING = 0.05
BARRIER_DEFORM_THRESHOLD = 0.1
BARRIER_HEAVY_MASS_THRESHOLD = 60
BARRIER_SMOOTHING_PASSES = 3
BARRIER_SMOOTHING_WINDOW = 5

MOLECULAR_CLOUD_COUNT = 20000
MOLECULAR_CLOUD_START_SIZE = 20
MOLECULAR_CLOUD_MIN_SIZE = 2
MOLECULAR_CLOUD_GROWTH_RATE = 1
MOLECULAR_CLOUD_START_MASS = 1
MOLECULAR_CLOUD_GRAVITY_CONSTANT = 0.01 * GRAVITY_SCALE
MOLECULAR_CLOUD_MAX_MASS = 22
MOLECULAR_CLOUD_START_COLORS = [
    (140, 20, 20),   # Hydrogen - Red (H-alpha) - 75%
    (140, 130, 0),   # Helium - Yellow (D3) - 23%
    (20, 140, 20),   # Oxygen - Green (OI) - 1%
    (20, 20, 140),   # Carbon - Blue (C2) - 0.5%
    (160, 100, 0),   # Neon - Orange (NeI) - 0.1%
    (80, 20, 140),   # Nitrogen - Violet (NII) - 0.1%
    (150, 150, 150), # Iron - Metallic Gray
    (140, 90, 40),   # Silicon - Earthy Brown
    (140, 120, 20)   # Gold - Deep Warm Yellow
]
MOLECULAR_CLOUD_END_COLOR = (225, 255, 255)
MOLECULAR_CLOUD_OPACITY = 100
MOLECULAR_CLOUD_MIN_OPACITY = 20
DEFAULT_STATE_CHANCE = 0.01
PROTOSTAR_THRESHOLD = 18
PROTOSTAR_EJECTA_COUNT = 10
PROTOSTAR_EJECTA_SPREAD = 100

BLACK_HOLE_THRESHOLD = 20
BLACK_HOLE_CHANCE = 0.00001
BLACK_HOLE_RADIUS = 5
BLACK_HOLE_MAX_MASS = 20
BLACK_HOLE_GRAVITY_CONSTANT = 18.0 * GRAVITY_SCALE
BLACK_HOLE_DECAY_RATE = 0.5
BLACK_HOLE_DECAY_THRESHOLD = 2
BLACK_HOLE_COLOR = (0,0,0)
BLACK_HOLE_BORDER_COLOR = (100, 0, 0)
BLACK_HOLE_MERGE_COLOR = (0, 60, 180, 100)
DISK_COLOR = (255, 100, 100)
DISK_SIZE = 1
DISK_ROTATION = 10.0

NEUTRON_STAR_CHANCE = 0.04
NEUTRON_STAR_RADIUS = 1
NEUTRON_STAR_GRAVITY_CONSTANT = 1.2 * GRAVITY_SCALE
NEUTRON_STAR_DECAY_RATE = 0.6
NEUTRON_STAR_DECAY_THRESHOLD = 0.8
NEUTRON_STAR_COLOR = (0, 120, 255)
NEUTRON_STAR_PULSE_RATE = 0.03
NEUTRON_STAR_PULSE_STRENGTH = 20
NEUTRON_STAR_PULSE_COLOR = (0, 60, 180, 80)
NEUTRON_STAR_PULSE_WIDTH = 2
NEUTRON_STAR_RIPPLE_SPEED = 40
NEUTRON_STAR_RIPPLE_EFFECT_WIDTH = 10

BH_DECAY_CLOUD_COUNT = 4
BH_DECAY_CLOUD_MASS_MIN = 12
BH_DECAY_CLOUD_MASS_MAX = 16
BH_DECAY_EJECTA_SPREAD = 60

NS_DECAY_CLOUD_COUNT = 2
NS_DECAY_CLOUD_MASS_MIN = 4
NS_DECAY_CLOUD_MASS_MAX = 8
NS_DECAY_EJECTA_SPREAD = 40

KILONOVA_EJECTA_COUNT = 20
KILONOVA_COLLISION_DISTANCE = 5
KILONOVA_EJECTA_SPREAD = 200

NS_PULSE_MASS_BOOST = 0.1

MC_BARRIER_GRAVITY_FACTOR = 0.3
BH_BARRIER_GRAVITY_FACTOR = 0.5
NS_BARRIER_GRAVITY_FACTOR = 0.7

MC_BARRIER_DEFORM_FACTOR = 1.0
BH_BARRIER_DEFORM_FACTOR = 100.0
NS_BARRIER_DEFORM_FACTOR = 20.0
NS_TO_BH_GRAVITY_FACTOR = 1.5
BH_RECOIL_FROM_NS_FACTOR = 0.3

CMB_PERTURBATION_MODES = 6
CMB_PERTURBATION_SCALE = 0.08
CMB_DENSITY_CONTRAST = 0.6

VELOCITY_DAMPING = 0.74

BACKGROUND_COLOR = (0, 6, 16)
LABEL_COLOR = (60, 60, 200)
SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 960

ZOOM_MIN = 0.5
ZOOM_MAX = 1.5
ZOOM_STEP = 0.1


entity_id_counter = 0
def generate_unique_id():
    global entity_id_counter
    entity_id_counter += 1
    return entity_id_counter


class SpatialHash:
    def __init__(self, cell_size=40):
        self.cell_size = cell_size
        self.grid = {}

    def clear(self):
        self.grid.clear()

    def _key(self, x, y):
        return (int(x // self.cell_size), int(y // self.cell_size))

    def insert(self, entity):
        key = self._key(entity.x, entity.y)
        if key not in self.grid:
            self.grid[key] = []
        self.grid[key].append(entity)

    def bulk_insert(self, entities):
        for entity in entities:
            self.insert(entity)

    def query_neighbors(self, entity):
        cx, cy = self._key(entity.x, entity.y)
        neighbors = []
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                key = (cx + dx, cy + dy)
                if key in self.grid:
                    neighbors.extend(self.grid[key])
        return neighbors


class SimulationState:
    def __init__(self):
        self.molecular_clouds = []
        self.black_holes = []
        self.neutron_stars = []
        self.black_hole_pulses = []
        self.spatial_hash = SpatialHash(40)


class BARRIER:
    def __init__(self, center, screen_size, num_points):
        self.center = center
        self.num_points = num_points
        self.angles = [(2 * math.pi / num_points) * i for i in range(num_points)]

        cx, cy = center
        r = max(screen_size[0], screen_size[1]) / 2.0
        self.rest_radii = [r] * num_points
        self.rest_radius = r

        self.perturbation = [0.0] * num_points
        for mode in range(1, CMB_PERTURBATION_MODES + 1):
            amplitude = random.gauss(0, CMB_PERTURBATION_SCALE / mode)
            phase = random.uniform(0, 2 * math.pi)
            for i in range(num_points):
                self.perturbation[i] += amplitude * math.sin(mode * self.angles[i] + phase)

        self.radii = [self.rest_radii[i] * (1.0 + self.perturbation[i]) for i in range(num_points)]
        self.radii_vel = [0.0] * num_points
        self.flash = [0.0] * num_points

    def get_radius_at_angle(self, angle):
        angle = angle % (2 * math.pi)
        step = 2 * math.pi / self.num_points
        idx = angle / step
        i0 = int(idx) % self.num_points
        i1 = (i0 + 1) % self.num_points
        t = idx - int(idx)
        return self.radii[i0] * (1 - t) + self.radii[i1] * t

    def _entity_angle_and_dist(self, entity):
        dx = entity.x - self.center[0]
        dy = entity.y - self.center[1]
        dist = math.hypot(dx, dy)
        angle = math.atan2(dy, dx) % (2 * math.pi)
        return angle, dist, dx, dy

    def apply_gravity(self, state, delta_time):
        cx, cy = self.center
        for mc in state.molecular_clouds:
            angle, dist, dx, dy = self._entity_angle_and_dist(mc)
            barrier_r = self.get_radius_at_angle(angle)
            target_dx = cx + barrier_r * math.cos(angle) - mc.x
            target_dy = cy + barrier_r * math.sin(angle) - mc.y
            target_dist = max(math.hypot(target_dx, target_dy), 1)
            force = (BARRIER_GRAVITY_CONSTANT * math.sqrt(mc.mass) / (target_dist ** 2)) * MC_BARRIER_GRAVITY_FACTOR
            if target_dist > mc.size / 2:
                mc.vx += (target_dx / target_dist) * force * delta_time
                mc.vy += (target_dy / target_dist) * force * delta_time

        for bh in state.black_holes:
            angle, dist, dx, dy = self._entity_angle_and_dist(bh)
            barrier_r = self.get_radius_at_angle(angle)
            target_dx = cx + barrier_r * math.cos(angle) - bh.x
            target_dy = cy + barrier_r * math.sin(angle) - bh.y
            target_dist = max(math.hypot(target_dx, target_dy), 1)
            force = (BARRIER_GRAVITY_CONSTANT * bh.mass / (target_dist ** 2)) * BH_BARRIER_GRAVITY_FACTOR
            bh.vx += (target_dx / target_dist) * force * delta_time
            bh.vy += (target_dy / target_dist) * force * delta_time

        for ns in state.neutron_stars:
            angle, dist, dx, dy = self._entity_angle_and_dist(ns)
            barrier_r = self.get_radius_at_angle(angle)
            target_dx = cx + barrier_r * math.cos(angle) - ns.x
            target_dy = cy + barrier_r * math.sin(angle) - ns.y
            target_dist = max(math.hypot(target_dx, target_dy), 1)
            force = (BARRIER_GRAVITY_CONSTANT * ns.mass / (target_dist ** 2)) * NS_BARRIER_GRAVITY_FACTOR
            ns.vx += (target_dx / target_dist) * force * delta_time
            ns.vy += (target_dy / target_dist) * force * delta_time

    def _accum_deformation(self, entity, mass_accum, step, proximity_threshold, factor):
        angle, dist, _, _ = self._entity_angle_and_dist(entity)
        barrier_r = self.get_radius_at_angle(angle)
        if abs(dist - barrier_r) < proximity_threshold:
            idx = angle / step
            i0 = int(idx) % self.num_points
            i1 = (i0 + 1) % self.num_points
            t = idx - int(idx)
            effective_mass = math.sqrt(entity.mass) * factor
            mass_accum[i0] += effective_mass * (1 - t)
            mass_accum[i1] += effective_mass * t

    def update_deformation(self, state, delta_time):
        mass_accum = [0.0] * self.num_points
        step = 2 * math.pi / self.num_points
        proximity_threshold = self.rest_radius * 0.3

        for mc in state.molecular_clouds:
            if mc.mass < PROTOSTAR_THRESHOLD:
                continue
            self._accum_deformation(mc, mass_accum, step, proximity_threshold, MC_BARRIER_DEFORM_FACTOR)

        for bh in state.black_holes:
            self._accum_deformation(bh, mass_accum, step, proximity_threshold, BH_BARRIER_DEFORM_FACTOR)

        for ns in state.neutron_stars:
            self._accum_deformation(ns, mass_accum, step, proximity_threshold, NS_BARRIER_DEFORM_FACTOR)

        damping = BARRIER_DAMPING ** delta_time
        for i in range(self.num_points):
            inward_force = mass_accum[i] * 2.0
            self.radii_vel[i] -= inward_force * delta_time
            self.radii_vel[i] *= damping
            old_radius = self.radii[i]
            self.radii[i] += self.radii_vel[i] * delta_time
            self.radii[i] = max(self.radii[i], 1.0)

            if abs(self.radii[i] - old_radius) > BARRIER_DEFORM_THRESHOLD:
                self.flash[i] = 1.0

        decay = math.exp(-BARRIER_FLASH_DECAY * delta_time)
        for i in range(self.num_points):
            self.flash[i] *= decay

    def enforce_barrier(self, state, delta_time):
        cx, cy = self.center
        step = 2 * math.pi / self.num_points

        for mc in state.molecular_clouds:
            angle, dist, dx, dy = self._entity_angle_and_dist(mc)
            barrier_r = self.get_radius_at_angle(angle)
            if dist >= barrier_r:
                mc.x = cx + barrier_r * 0.99 * math.cos(angle)
                mc.y = cy + barrier_r * 0.99 * math.sin(angle)
                if dist > 0:
                    radial_vx = (dx / dist) * ((mc.vx * dx + mc.vy * dy) / dist)
                    radial_vy = (dy / dist) * ((mc.vx * dx + mc.vy * dy) / dist)
                    if mc.vx * dx + mc.vy * dy > 0:
                        mc.vx -= radial_vx
                        mc.vy -= radial_vy

        for ns in state.neutron_stars:
            angle, dist, dx, dy = self._entity_angle_and_dist(ns)
            barrier_r = self.get_radius_at_angle(angle)
            if dist >= barrier_r:
                idx = angle / step
                i0 = int(idx) % self.num_points
                i1 = (i0 + 1) % self.num_points
                section_mass = sum(
                    bh.mass for bh in state.black_holes
                    if abs((self._entity_angle_and_dist(bh)[0] - angle + math.pi) % (2 * math.pi) - math.pi) < step * 3
                ) + sum(
                    ns2.mass for ns2 in state.neutron_stars
                    if abs((self._entity_angle_and_dist(ns2)[0] - angle + math.pi) % (2 * math.pi) - math.pi) < step * 3
                )
                weakness = min(section_mass / BARRIER_HEAVY_MASS_THRESHOLD, 1.0)
                containment = 1.0 - weakness * 0.7
                if dist > 0 and containment > 0.05:
                    push_strength = 200.0 * containment
                    ns.vx -= (dx / dist) * push_strength * delta_time
                    ns.vy -= (dy / dist) * push_strength * delta_time

        for bh in state.black_holes:
            angle, dist, dx, dy = self._entity_angle_and_dist(bh)
            barrier_r = self.get_radius_at_angle(angle)
            if dist >= barrier_r:
                idx = angle / step
                section_mass = sum(
                    bh2.mass for bh2 in state.black_holes
                    if abs((self._entity_angle_and_dist(bh2)[0] - angle + math.pi) % (2 * math.pi) - math.pi) < step * 3
                ) + sum(
                    ns.mass for ns in state.neutron_stars
                    if abs((self._entity_angle_and_dist(ns)[0] - angle + math.pi) % (2 * math.pi) - math.pi) < step * 3
                )
                weakness = min(section_mass / BARRIER_HEAVY_MASS_THRESHOLD, 1.0)
                containment = 1.0 - weakness * 0.9
                if dist > 0 and containment > 0.05:
                    push_strength = 80.0 * containment
                    bh.vx -= (dx / dist) * push_strength * delta_time
                    bh.vy -= (dy / dist) * push_strength * delta_time

    def draw_barrier(self, screen):
        cx, cy = self.center
        smoothed = list(self.radii)
        half_w = BARRIER_SMOOTHING_WINDOW // 2
        n = self.num_points
        for _ in range(BARRIER_SMOOTHING_PASSES):
            prev = list(smoothed)
            for i in range(n):
                total = 0.0
                for k in range(-half_w, half_w + 1):
                    total += prev[(i + k) % n]
                smoothed[i] = total / BARRIER_SMOOTHING_WINDOW

        points = []
        for i in range(self.num_points):
            a = self.angles[i]
            r = smoothed[i]
            points.append((int(cx + r * math.cos(a)), int(cy + r * math.sin(a))))

        barrier_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)

        base_color = BARRIER_COLOR + (BARRIER_BASE_OPACITY,)
        pygame.draw.polygon(barrier_surface, base_color, points, 3)

        for i in range(self.num_points):
            j = (i + 1) % self.num_points
            flash_val = max(self.flash[i], self.flash[j])
            if flash_val > 0.01:
                opacity = int(BARRIER_BASE_OPACITY + flash_val * (BARRIER_FLASH_OPACITY - BARRIER_BASE_OPACITY))
                r = int(BARRIER_COLOR[0] + flash_val * (BARRIER_FLASH_COLOR[0] - BARRIER_COLOR[0]))
                g = int(BARRIER_COLOR[1] + flash_val * (BARRIER_FLASH_COLOR[1] - BARRIER_COLOR[1]))
                b = int(BARRIER_COLOR[2] + flash_val * (BARRIER_FLASH_COLOR[2] - BARRIER_COLOR[2]))
                color = (r, g, b, min(255, opacity))
                pygame.draw.line(barrier_surface, color, points[i], points[j], 3)

        screen.blit(barrier_surface, (0, 0))


def interpolate_color(start_color, end_color, factor):
    r = start_color[0] + factor * (end_color[0] - start_color[0])
    g = start_color[1] + factor * (end_color[1] - start_color[1])
    b = start_color[2] + factor * (end_color[2] - start_color[2])
    return int(r), int(g), int(b)


def interpolate_multi_color(colors, factor):
    if factor <= 0:
        return colors[0]
    if factor >= 1:
        return colors[-1]

    num_segments = len(colors) - 1
    segment_size = 1.0 / num_segments
    segment_index = min(int(factor / segment_size), num_segments - 1)
    segment_factor = (factor - segment_index * segment_size) / segment_size
    start_color = colors[segment_index]
    end_color = colors[segment_index + 1]

    return interpolate_color(start_color, end_color, segment_factor)


ELEMENTAL_ABUNDANCE = [
    (0, 0.75),       # Hydrogen range: 0-75%
    (0.75, 0.98),    # Helium range: 75-98%
    (0.98, 0.99),    # Oxygen range: 98-99%
    (0.99, 0.995),   # Carbon range: 99-99.5%
    (0.995, 0.996),  # Neon range: 99.5-99.6%
    (0.996, 0.999),  # Nitrogen range: 99.6-99.9%
    (0.999, 0.9995), # Iron range: 99.9-99.95%
    (0.9995, 0.9999),# Silicon range: 99.95-99.99%
    (0.9999, 1.0)    # Gold range: 99.99-100%
]

EJECTA_ELEMENTAL_ABUNDANCE = [
    (0, 0.50),     # Hydrogen range: 0-50%
    (0.50, 0.80),  # Helium range: 50-80%
    (0.80, 0.88),  # Oxygen range: 80-88%
    (0.88, 0.92),  # Carbon range: 88-92%
    (0.92, 0.92),  # Neon range: 92-92%
    (0.92, 0.92),  # Nitrogen range: 92-92%
    (0.92, 0.96),  # Iron range: 92-96%
    (0.96, 0.99),  # Silicon range: 96-99%
    (0.99, 1.0)    # Gold range: 99-100%
]

BH_DECAY_ELEMENTAL_ABUNDANCE = [
    (0, 0.08),     # Hydrogen range: 0-8%
    (0.08, 0.16),  # Helium range: 8-16%
    (0.16, 0.22),  # Oxygen range: 16-22%
    (0.22, 0.28),  # Carbon range: 22-28%
    (0.28, 0.30),  # Neon range: 28-30%
    (0.30, 0.38),  # Nitrogen range: 30-38%
    (0.38, 0.62),  # Iron range: 38-62%
    (0.62, 0.82),  # Silicon range: 62-82%
    (0.82, 1.0)    # Gold range: 82-100%
]

KILONOVA_ELEMENTAL_ABUNDANCE = [
    (0, 0.03),     # Hydrogen range: 0-3%
    (0.03, 0.06),  # Helium range: 3-6%
    (0.06, 0.09),  # Oxygen range: 6-9%
    (0.09, 0.12),  # Carbon range: 9-12%
    (0.12, 0.13),  # Neon range: 12-13%
    (0.13, 0.21),  # Nitrogen range: 13-21%
    (0.21, 0.41),  # Iron range: 21-41%
    (0.41, 0.61),  # Silicon range: 41-61%
    (0.61, 1.0)    # Gold range: 61-100%
]

class MOLECULAR_CLOUD:
    def __init__(self, x, y, size, mass, abundance=None):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.size = size
        self.mass = mass
        self.opacity = 255

        rand = random.random()
        for i, (start, end) in enumerate(abundance or ELEMENTAL_ABUNDANCE):
            if start <= rand < end:
                self.start_color = MOLECULAR_CLOUD_START_COLORS[i]
                break

    def draw_molecular_cloud(self, screen):
        if self.size <= 4:
            self.color = MOLECULAR_CLOUD_END_COLOR
        else:
            factor = 1.0 - (self.size - 4) / (MOLECULAR_CLOUD_START_SIZE - 4)
            self.color = interpolate_color(self.start_color, MOLECULAR_CLOUD_END_COLOR, factor)
        if self.opacity < 255:
            s = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
            s.fill(self.color + (self.opacity,))
            screen.blit(s, (self.x, self.y))
        else:
            pygame.draw.rect(screen, self.color, (self.x, self.y, self.size, self.size))

    def update_molecular_cloud(self):
        self.size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((self.mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
        self.mass = min(self.mass, MOLECULAR_CLOUD_MAX_MASS)
        if self.mass >= PROTOSTAR_THRESHOLD:
            self.opacity = 255
        elif self.size < 4:
            self.opacity = random.randint(MOLECULAR_CLOUD_MIN_OPACITY, 255)
        else:
            self.opacity = MOLECULAR_CLOUD_OPACITY

    def check_collisions_with_molecular_clouds(self, other):
        return (self.x < other.x + other.size and
                self.x + self.size > other.x and
                self.y < other.y + other.size and
                self.y + self.size > other.y)


class BLACK_HOLE:
    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mass = min(mass, BLACK_HOLE_MAX_MASS)
        self.border_radius = int(self.mass // BLACK_HOLE_RADIUS)
        self.tracer_angle = random.uniform(0, 2 * math.pi)

    def draw_black_hole(self, screen):
        radius = int(self.mass // BLACK_HOLE_RADIUS)
        self.border_radius = radius
        pygame.draw.circle(screen, BLACK_HOLE_BORDER_COLOR, (int(self.x), int(self.y)), radius)
        pygame.draw.circle(screen, BLACK_HOLE_COLOR, (int(self.x), int(self.y)), radius - 2)

        tracer_x = self.x + self.border_radius * math.cos(self.tracer_angle)
        tracer_y = self.y + self.border_radius * math.sin(self.tracer_angle)
        pygame.draw.circle(screen, DISK_COLOR, (int(tracer_x), int(tracer_y)), DISK_SIZE)

    def attract_entities_to_black_holes(self, state, delta_time, mc_to_remove, ns_to_remove, bh_to_remove):
        for black_hole in state.black_holes:
            if black_hole is not self and black_hole not in bh_to_remove:
                dx = self.x - black_hole.x
                dy = self.y - black_hole.y
                distance = max(math.hypot(dx, dy), 1)

                if self.mass > black_hole.mass and distance < self.border_radius:
                    bh_to_remove.add(black_hole)
                    self.mass += black_hole.mass
                    self.mass = min(self.mass, BLACK_HOLE_MAX_MASS)
                    state.black_hole_pulses.append([self.x, self.y, 0, black_hole.mass])
                elif distance > 0:
                    force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * black_hole.mass) / (distance**2)
                    black_hole.vx += (dx / distance) * force * delta_time
                    black_hole.vy += (dy / distance) * force * delta_time

        for entity in state.molecular_clouds:
            if entity in mc_to_remove:
                continue
            dx = self.x - entity.x
            dy = self.y - entity.y
            distance = max(math.hypot(dx, dy), 1)
            if distance < self.border_radius:
                mc_to_remove.add(entity)
                self.mass += entity.mass
                self.mass = min(self.mass, BLACK_HOLE_MAX_MASS)
            else:
                force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * entity.mass) / (distance**2)
                entity.vx += (dx / distance) * force * delta_time
                entity.vy += (dy / distance) * force * delta_time

        for entity in state.neutron_stars:
            if entity in ns_to_remove:
                continue
            dx = self.x - entity.x
            dy = self.y - entity.y
            distance = max(math.hypot(dx, dy), 1)
            if distance < self.border_radius:
                ns_to_remove.add(entity)
                self.mass += entity.mass
                self.mass = min(self.mass, BLACK_HOLE_MAX_MASS)
            else:
                force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * entity.mass) / (distance**2)
                entity.vx += (dx / distance) * force * delta_time
                entity.vy += (dy / distance) * force * delta_time

    def update_gravity_of_black_holes(self, state, delta_time):
        for entity in state.molecular_clouds + state.neutron_stars + state.black_holes:
            if entity is not self:
                dx = entity.x - self.x
                dy = entity.y - self.y
                distance = max(math.hypot(dx, dy), 1)
                force = MOLECULAR_CLOUD_GRAVITY_CONSTANT * (self.mass * entity.mass) / (distance**2)
                self.vx += (dx / distance) * force * delta_time
                self.vy += (dy / distance) * force * delta_time

    def black_hole_decay(self, delta_time):
        self.mass -= BLACK_HOLE_DECAY_RATE * delta_time


class NEUTRON_STAR:
    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mass = mass
        self.radius = NEUTRON_STAR_RADIUS
        self.pulse_rate = NEUTRON_STAR_PULSE_RATE
        self.pulse_strength = NEUTRON_STAR_PULSE_STRENGTH
        self.time_since_last_pulse = 0
        self.active_pulses = []
        self.pulse_color_state = 0  # 0: normal color, 1: white during pulse
        self.pulse_color_duration = 0.1  # Duration of white color in seconds

    def draw_neutron_star(self, screen, ring, all_pulses):
        current_color = (255, 255, 255) if self.pulse_color_state == 1 else NEUTRON_STAR_COLOR
        pygame.draw.circle(screen, current_color, (int(self.x), int(self.y)), self.radius)

        for pulse in self.active_pulses:
            pulse_radius, _, fade = pulse
            if pulse_radius <= 1:
                continue

            points = _clip_pulse_points(self.x, self.y, pulse_radius, ring, all_pulses)

            alpha = int(NEUTRON_STAR_PULSE_COLOR[3] * fade)
            alpha = max(0, min(255, alpha))
            color = (NEUTRON_STAR_PULSE_COLOR[0], NEUTRON_STAR_PULSE_COLOR[1], NEUTRON_STAR_PULSE_COLOR[2], alpha)

            min_x = min(p[0] for p in points) - 2
            min_y = min(p[1] for p in points) - 2
            max_x = max(p[0] for p in points) + 2
            max_y = max(p[1] for p in points) + 2
            w = max_x - min_x
            h = max_y - min_y
            if w > 0 and h > 0:
                pulse_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                local_points = [(p[0] - min_x, p[1] - min_y) for p in points]
                pygame.draw.polygon(pulse_surface, color, local_points, NEUTRON_STAR_PULSE_WIDTH)
                screen.blit(pulse_surface, (min_x, min_y))

    def pulse_gravity_from_neutron_star(self, state, ring, delta_time):
        self.time_since_last_pulse += delta_time

        if self.pulse_color_state == 1:
            self.pulse_color_duration -= delta_time
            if self.pulse_color_duration <= 0:
                self.pulse_color_state = 0
                self.pulse_color_duration = 0.1

        dist_to_center = math.hypot(self.x - ring.center[0], self.y - ring.center[1])
        min_barrier_dist = max(ring.rest_radius - dist_to_center, 1.0)
        max_barrier_dist = dist_to_center + ring.rest_radius

        pulses_to_remove = []
        for i, pulse in enumerate(self.active_pulses):
            radius, time_alive, fade = pulse
            new_radius = min(radius + (NEUTRON_STAR_RIPPLE_SPEED * delta_time), max_barrier_dist)
            new_time = time_alive + delta_time
            new_fade = fade

            if new_radius >= min_barrier_dist:
                new_fade -= delta_time * 1.5

            self.active_pulses[i] = [new_radius, new_time, new_fade]

            cx, cy = ring.center
            for bi in range(ring.num_points):
                bx = cx + ring.radii[bi] * math.cos(ring.angles[bi])
                by = cy + ring.radii[bi] * math.sin(ring.angles[bi])
                dist_to_star = math.hypot(bx - self.x, by - self.y)
                if abs(dist_to_star - new_radius) < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2:
                    ring.flash[bi] = max(ring.flash[bi], new_fade * 0.6)
                    ring.radii_vel[bi] += BARRIER_WAVE_PUSH * new_fade * delta_time

            for molecular_cloud in state.molecular_clouds:
                dx = molecular_cloud.x - self.x
                dy = molecular_cloud.y - self.y
                distance = math.hypot(dx, dy)

                ripple_dist = abs(distance - radius)
                if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH:
                    effect_factor = 1.0 - (ripple_dist / NEUTRON_STAR_RIPPLE_EFFECT_WIDTH)
                    force = self.pulse_strength * effect_factor / ((ripple_dist + 1) ** 0.8)

                    if distance > 0:
                        molecular_cloud.vx += (dx / distance) * force * delta_time
                        molecular_cloud.vy += (dy / distance) * force * delta_time
                        molecular_cloud.mass += NS_PULSE_MASS_BOOST * effect_factor * delta_time
                        molecular_cloud.mass = min(molecular_cloud.mass, MOLECULAR_CLOUD_MAX_MASS)

            for black_hole in state.black_holes:
                dx = black_hole.x - self.x
                dy = black_hole.y - self.y
                distance = math.hypot(dx, dy)

                ripple_dist = abs(distance - radius)
                if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH:
                    effect_factor = (1.0 - (ripple_dist / NEUTRON_STAR_RIPPLE_EFFECT_WIDTH)) * 0.3
                    force = self.pulse_strength * effect_factor / ((ripple_dist + 1) ** 1.2)

                    if distance > 0:
                        black_hole.vx += (dx / distance) * force * delta_time * 0.2
                        black_hole.vy += (dy / distance) * force * delta_time * 0.2

            if new_fade <= 0.01:
                pulses_to_remove.append(i)

        for i in sorted(pulses_to_remove, reverse=True):
            if i < len(self.active_pulses):
                self.active_pulses.pop(i)

        if self.time_since_last_pulse >= self.pulse_rate and len(self.active_pulses) == 0:
            self.active_pulses.append([0, 0, 1.0])
            self.time_since_last_pulse = 0
            self.pulse_color_state = 1  # Set to white during pulse
            self.pulse_color_duration = 0.1  # Reset duration

    def update_position_of_entities_from_pulse(self, state, delta_time):
        for molecular_cloud in state.molecular_clouds:
            if molecular_cloud is not self:
                dx = molecular_cloud.x - self.x
                dy = molecular_cloud.y - self.y
                distance = max(math.hypot(dx, dy), 1)

                force = NEUTRON_STAR_GRAVITY_CONSTANT * (self.mass * molecular_cloud.mass) / (distance**2)

                molecular_cloud.vx -= (dx / distance) * force * delta_time
                molecular_cloud.vy -= (dy / distance) * force * delta_time

                self.vx += (dx / distance) * force * delta_time
                self.vy += (dy / distance) * force * delta_time

        for black_hole in state.black_holes:
            dx = black_hole.x - self.x
            dy = black_hole.y - self.y
            distance = max(math.hypot(dx, dy), 1)

            force = NEUTRON_STAR_GRAVITY_CONSTANT * (self.mass * black_hole.mass) / (distance**2)

            self.vx += (dx / distance) * force * delta_time * NS_TO_BH_GRAVITY_FACTOR
            self.vy += (dy / distance) * force * delta_time * NS_TO_BH_GRAVITY_FACTOR

            black_hole.vx -= (dx / distance) * force * delta_time * BH_RECOIL_FROM_NS_FACTOR
            black_hole.vy -= (dy / distance) * force * delta_time * BH_RECOIL_FROM_NS_FACTOR

    def decay_neutron_star(self, delta_time):
        self.mass -= NEUTRON_STAR_DECAY_RATE * delta_time


def integrate_entity(entity, delta_time):
    damping = VELOCITY_DAMPING ** delta_time
    entity.vx *= damping
    entity.vy *= damping
    entity.x += entity.vx * delta_time
    entity.y += entity.vy * delta_time


def apply_mc_gravity(state, delta_time):
    for mc in state.molecular_clouds:
        neighbors = state.spatial_hash.query_neighbors(mc)
        ax, ay = 0.0, 0.0
        for other in neighbors:
            if other is mc:
                continue
            dx = other.x - mc.x
            dy = other.y - mc.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < 1:
                continue
            dist = math.sqrt(dist_sq)
            force = MOLECULAR_CLOUD_GRAVITY_CONSTANT * (mc.mass * other.mass) / dist_sq
            ax += (dx / dist) * force
            ay += (dy / dist) * force
        mc.vx += ax * delta_time
        mc.vy += ay * delta_time


def handle_collisions(state):
    to_remove = set()
    for mc in state.molecular_clouds:
        if mc in to_remove:
            continue
        neighbors = state.spatial_hash.query_neighbors(mc)
        for other in neighbors:
            if other is mc or other in to_remove:
                continue
            if mc.check_collisions_with_molecular_clouds(other):
                merged_mass = mc.mass + other.mass
                to_remove.add(other)
                mc.mass = min(merged_mass, MOLECULAR_CLOUD_MAX_MASS)
                mc.update_molecular_cloud()
                break
    if to_remove:
        state.molecular_clouds = [mc for mc in state.molecular_clouds if mc not in to_remove]


def update_entities(state):
    handle_collisions(state)
    list_of_molecular_clouds_to_remove = []
    new_clouds = []
    for molecular_cloud in state.molecular_clouds:
        molecular_cloud.update_molecular_cloud()
        if molecular_cloud.mass > BLACK_HOLE_THRESHOLD:
            if random.random() < BLACK_HOLE_CHANCE:
                if random.random() < NEUTRON_STAR_CHANCE:
                    state.neutron_stars.append(NEUTRON_STAR(molecular_cloud.x, molecular_cloud.y, molecular_cloud.mass))
                else:
                    state.black_holes.append(BLACK_HOLE(molecular_cloud.x, molecular_cloud.y, molecular_cloud.mass))
                list_of_molecular_clouds_to_remove.append(molecular_cloud)
            elif random.random() < DEFAULT_STATE_CHANCE:
                for _ in range(PROTOSTAR_EJECTA_COUNT):
                    offset_angle = random.uniform(0, 2 * math.pi)
                    offset_dist = random.uniform(5, PROTOSTAR_EJECTA_SPREAD)
                    ex = molecular_cloud.x + offset_dist * math.cos(offset_angle)
                    ey = molecular_cloud.y + offset_dist * math.sin(offset_angle)
                    mass = random.uniform(MOLECULAR_CLOUD_START_MASS, PROTOSTAR_THRESHOLD)
                    size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                    child = MOLECULAR_CLOUD(ex, ey, size, mass, EJECTA_ELEMENTAL_ABUNDANCE)
                    child.vx = math.cos(offset_angle) * offset_dist * 0.5
                    child.vy = math.sin(offset_angle) * offset_dist * 0.5
                    new_clouds.append(child)
                molecular_cloud.mass = MOLECULAR_CLOUD_START_MASS
                molecular_cloud.size = MOLECULAR_CLOUD_START_SIZE
    for molecular_cloud in list_of_molecular_clouds_to_remove:
        state.molecular_clouds.remove(molecular_cloud)
    state.molecular_clouds.extend(new_clouds)


def draw_static_key(screen, font, zoom):
    snapshot_pos = (30, SCREEN_HEIGHT - 140)
    if zoom != 1.0:
        zoom_text = f'[SCROLL] ZOOM: {zoom:.1f}x'
    else:
        zoom_text = '[SCROLL] ZOOM'
    screen.blit(font.render(zoom_text, True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))
    snapshot_pos = (30, SCREEN_HEIGHT - 110)
    screen.blit(font.render('[Q] EXIT', True, LABEL_COLOR), (snapshot_pos[0], snapshot_pos[1]))


def screen_to_world(screen_x, screen_y, zoom, view_center_x, view_center_y):
    view_w = SCREEN_WIDTH / zoom
    view_h = SCREEN_HEIGHT / zoom
    view_left = view_center_x - view_w / 2
    view_top = view_center_y - view_h / 2
    world_x = view_left + screen_x / zoom
    world_y = view_top + screen_y / zoom
    return world_x, world_y


def handle_input(zoom, view_center_x, view_center_y):
    running = True

    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
            running = False
        if event.type == pygame.MOUSEWHEEL:
            mouse_sx, mouse_sy = pygame.mouse.get_pos()
            world_x, world_y = screen_to_world(mouse_sx, mouse_sy, zoom, view_center_x, view_center_y)
            old_zoom = zoom
            zoom += event.y * ZOOM_STEP
            zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))
            if zoom != old_zoom:
                if zoom <= 1.0:
                    view_center_x = SCREEN_WIDTH / 2.0
                    view_center_y = SCREEN_HEIGHT / 2.0
                else:
                    view_center_x = world_x - (mouse_sx - SCREEN_WIDTH / 2) / zoom
                    view_center_y = world_y - (mouse_sy - SCREEN_HEIGHT / 2) / zoom

    return running, zoom, view_center_x, view_center_y


def resolve_pulse_collisions(state, delta_time):
    all_pulses = []
    for ns in state.neutron_stars:
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
                fade_rate = 4.0 * overlap
                pulse_a[2] -= fade_rate * delta_time
                pulse_b[2] -= fade_rate * delta_time


def update_simulation_state(state, ring, delta_time):
    state.spatial_hash.clear()
    state.spatial_hash.bulk_insert(state.molecular_clouds)

    apply_mc_gravity(state, delta_time)
    update_entities(state)

    ring.apply_gravity(state, delta_time)
    ring.enforce_barrier(state, delta_time)

    for black_hole in state.black_holes:
        black_hole.tracer_angle += DISK_ROTATION * delta_time

    pulses_to_remove = []
    for i, pulse in enumerate(state.black_hole_pulses):
        x, y, radius, consumed_mass = pulse
        new_radius = radius + (NEUTRON_STAR_RIPPLE_SPEED * delta_time * 1.5)
        state.black_hole_pulses[i] = [x, y, new_radius, consumed_mass]

        for molecular_cloud in state.molecular_clouds:
            dx = molecular_cloud.x - x
            dy = molecular_cloud.y - y
            distance = math.hypot(dx, dy)

            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2))
                force = NEUTRON_STAR_PULSE_STRENGTH * 5 * effect_factor * (consumed_mass / 10) / ((ripple_dist + 1) ** 1.5)

                if distance > 0:
                    molecular_cloud.vx += (dx / distance) * force * delta_time
                    molecular_cloud.vy += (dy / distance) * force * delta_time

        for black_hole in state.black_holes:
            dx = black_hole.x - x
            dy = black_hole.y - y
            distance = math.hypot(dx, dy)

            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3))
                force = NEUTRON_STAR_PULSE_STRENGTH * 2 * effect_factor * (consumed_mass / 10) / ((ripple_dist + 1) ** 2)

                if distance > 0:
                    black_hole.vx += (dx / distance) * force * delta_time * 0.5
                    black_hole.vy += (dy / distance) * force * delta_time * 0.5

        for neutron_star in state.neutron_stars:
            dx = neutron_star.x - x
            dy = neutron_star.y - y
            distance = math.hypot(dx, dy)

            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 2))
                force = NEUTRON_STAR_PULSE_STRENGTH * 3 * effect_factor * (consumed_mass / 10) / ((ripple_dist + 1) ** 1.8)

                if distance > 0:
                    neutron_star.vx += (dx / distance) * force * delta_time * 1.5
                    neutron_star.vy += (dy / distance) * force * delta_time * 1.5

        cx, cy = ring.center
        pulse_fade = max(0.0, 1.0 - new_radius / ring.rest_radius)
        for bi in range(ring.num_points):
            bx = cx + ring.radii[bi] * math.cos(ring.angles[bi])
            by = cy + ring.radii[bi] * math.sin(ring.angles[bi])
            dist_to_pulse = math.hypot(bx - x, by - y)
            if abs(dist_to_pulse - new_radius) < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3:
                ring.flash[bi] = max(ring.flash[bi], pulse_fade * 0.8)
                ring.radii_vel[bi] += BARRIER_WAVE_PUSH * 1.5 * pulse_fade * delta_time

        if new_radius > max(ring.radii):
            pulses_to_remove.append(i)

    for i in sorted(pulses_to_remove, reverse=True):
        if i < len(state.black_hole_pulses):
            state.black_hole_pulses.pop(i)

    mc_to_remove = set()
    ns_to_remove = set()
    bh_to_remove = set()
    new_clouds = []

    for black_hole in state.black_holes:
        if black_hole in bh_to_remove:
            continue
        black_hole.attract_entities_to_black_holes(state, delta_time, mc_to_remove, ns_to_remove, bh_to_remove)
        black_hole.update_gravity_of_black_holes(state, delta_time)
        black_hole.black_hole_decay(delta_time)
        if black_hole.mass <= BLACK_HOLE_DECAY_THRESHOLD:
            bh_to_remove.add(black_hole)
            for _ in range(BH_DECAY_CLOUD_COUNT):
                offset_angle = random.uniform(0, 2 * math.pi)
                offset_dist = random.uniform(5, BH_DECAY_EJECTA_SPREAD)
                ex = black_hole.x + offset_dist * math.cos(offset_angle)
                ey = black_hole.y + offset_dist * math.sin(offset_angle)
                mass = random.uniform(BH_DECAY_CLOUD_MASS_MIN, BH_DECAY_CLOUD_MASS_MAX)
                size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                child = MOLECULAR_CLOUD(ex, ey, size, mass, BH_DECAY_ELEMENTAL_ABUNDANCE)
                child.vx = math.cos(offset_angle) * offset_dist * 0.5
                child.vy = math.sin(offset_angle) * offset_dist * 0.5
                new_clouds.append(child)

    for neutron_star in state.neutron_stars:
        if neutron_star in ns_to_remove:
            continue
        neutron_star.update_position_of_entities_from_pulse(state, delta_time)
        neutron_star.pulse_gravity_from_neutron_star(state, ring, delta_time)
        neutron_star.decay_neutron_star(delta_time)
        if neutron_star.mass <= NEUTRON_STAR_DECAY_THRESHOLD:
            ns_to_remove.add(neutron_star)
            for _ in range(NS_DECAY_CLOUD_COUNT):
                offset_angle = random.uniform(0, 2 * math.pi)
                offset_dist = random.uniform(5, NS_DECAY_EJECTA_SPREAD)
                ex = neutron_star.x + offset_dist * math.cos(offset_angle)
                ey = neutron_star.y + offset_dist * math.sin(offset_angle)
                mass = random.uniform(NS_DECAY_CLOUD_MASS_MIN, NS_DECAY_CLOUD_MASS_MAX)
                size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                child = MOLECULAR_CLOUD(ex, ey, size, mass, EJECTA_ELEMENTAL_ABUNDANCE)
                child.vx = math.cos(offset_angle) * offset_dist * 0.5
                child.vy = math.sin(offset_angle) * offset_dist * 0.5
                new_clouds.append(child)

    # NS-NS Kilonova mergers
    alive_ns = [ns for ns in state.neutron_stars if ns not in ns_to_remove]
    merged_ns = set()
    for i in range(len(alive_ns)):
        if alive_ns[i] in merged_ns:
            continue
        for j in range(i + 1, len(alive_ns)):
            if alive_ns[j] in merged_ns:
                continue
            dx = alive_ns[i].x - alive_ns[j].x
            dy = alive_ns[i].y - alive_ns[j].y
            dist = math.hypot(dx, dy)
            if dist < KILONOVA_COLLISION_DISTANCE:
                ns_a = alive_ns[i]
                ns_b = alive_ns[j]
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
                    mass = random.uniform(MOLECULAR_CLOUD_START_MASS, PROTOSTAR_THRESHOLD)
                    size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                    child = MOLECULAR_CLOUD(ex, ey, size, mass, KILONOVA_ELEMENTAL_ABUNDANCE)
                    child.vx = math.cos(offset_angle) * offset_dist * 0.5
                    child.vy = math.sin(offset_angle) * offset_dist * 0.5
                    new_clouds.append(child)
                state.black_hole_pulses.append([cx, cy, 0, combined_mass])
                break

    resolve_pulse_collisions(state, delta_time)

    if mc_to_remove:
        state.molecular_clouds = [mc for mc in state.molecular_clouds if mc not in mc_to_remove]
    if bh_to_remove:
        state.black_holes = [bh for bh in state.black_holes if bh not in bh_to_remove]
    if ns_to_remove:
        state.neutron_stars = [ns for ns in state.neutron_stars if ns not in ns_to_remove]
    if new_clouds:
        state.molecular_clouds.extend(new_clouds)

    for mc in state.molecular_clouds:
        integrate_entity(mc, delta_time)
    for bh in state.black_holes:
        integrate_entity(bh, delta_time)
    for ns in state.neutron_stars:
        integrate_entity(ns, delta_time)



def _clip_pulse_points(origin_x, origin_y, pulse_radius, ring, all_pulses, num_pts=64):
    cx, cy = ring.center
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
            if dist_from_center > barrier_r - 4:
                px = cx + (barrier_r - 4) * math.cos(barrier_angle)
                py = cy + (barrier_r - 4) * math.sin(barrier_angle)

        points.append((int(px), int(py)))
    return points


def draw_simulation(screen, ring, state, offset_x=0, offset_y=0):
    if offset_x != 0 or offset_y != 0:
        orig_center = ring.center
        ring.center = (ring.center[0] + offset_x, ring.center[1] + offset_y)
        for mc in state.molecular_clouds:
            mc.x += offset_x
            mc.y += offset_y
        for bh in state.black_holes:
            bh.x += offset_x
            bh.y += offset_y
        for ns in state.neutron_stars:
            ns.x += offset_x
            ns.y += offset_y
        for pulse in state.black_hole_pulses:
            pulse[0] += offset_x
            pulse[1] += offset_y

    ring.draw_barrier(screen)

    for molecular_cloud in state.molecular_clouds:
        molecular_cloud.draw_molecular_cloud(screen)

    all_pulses = []
    for ns in state.neutron_stars:
        for pulse in ns.active_pulses:
            all_pulses.append((ns.x, ns.y, pulse[0], pulse[2]))
    for pulse in state.black_hole_pulses:
        all_pulses.append((pulse[0], pulse[1], pulse[2], 1.0))

    for pulse in state.black_hole_pulses[:]:
        x, y, pulse_radius, consumed_mass = pulse
        if pulse_radius > 1:
            pulse_width = max(2, int(consumed_mass / 20))
            points = _clip_pulse_points(x, y, pulse_radius, ring, all_pulses)
            min_x = min(p[0] for p in points) - 2
            min_y = min(p[1] for p in points) - 2
            max_x = max(p[0] for p in points) + 2
            max_y = max(p[1] for p in points) + 2
            w = max_x - min_x
            h = max_y - min_y
            if w > 0 and h > 0:
                pulse_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                local_points = [(p[0] - min_x, p[1] - min_y) for p in points]
                pygame.draw.polygon(pulse_surface, BLACK_HOLE_MERGE_COLOR, local_points, pulse_width)
                screen.blit(pulse_surface, (min_x, min_y))

    for black_hole in state.black_holes:
        black_hole.draw_black_hole(screen)

    for neutron_star in state.neutron_stars:
        neutron_star.draw_neutron_star(screen, ring, all_pulses)

    if offset_x != 0 or offset_y != 0:
        ring.center = orig_center
        for mc in state.molecular_clouds:
            mc.x -= offset_x
            mc.y -= offset_y
        for bh in state.black_holes:
            bh.x -= offset_x
            bh.y -= offset_y
        for ns in state.neutron_stars:
            ns.x -= offset_x
            ns.y -= offset_y
        for pulse in state.black_hole_pulses:
            pulse[0] -= offset_x
            pulse[1] -= offset_y


def format_year_display(current_year):
    if current_year >= 1_000_000:
        return "TIME(YEARS): \u221e"
    elif current_year >= 1_000:
        return f"TIME(YEARS): {current_year / 1_000:.1f}B"
    else:
        return f"TIME(YEARS): {current_year}M"


def draw_ui(screen, font, current_year, zoom=1.0):
    draw_static_key(screen, font, zoom)

    year_text = font.render(format_year_display(current_year), True, LABEL_COLOR)
    screen.blit(year_text, (30, SCREEN_HEIGHT - 40 ))


def run_simulation(screen, font, state, ring):
    try:
        running = True
        clock = pygame.time.Clock()
        current_year = 0
        last_frame_time = pygame.time.get_ticks()
        zoom = 1.0
        view_center_x = SCREEN_WIDTH / 2.0
        view_center_y = SCREEN_HEIGHT / 2.0
        world_surface_w = 0
        world_surface_h = 0
        world_surface = None

        while running:
            current_time = pygame.time.get_ticks()
            delta_time = (current_time - last_frame_time) / 1000.0
            last_frame_time = current_time

            running, zoom, view_center_x, view_center_y = handle_input(
                zoom, view_center_x, view_center_y
            )
            if not running:
                break

            ring.update_deformation(state, delta_time)

            update_simulation_state(state, ring, delta_time)

            entity_count = len(state.molecular_clouds) + len(state.black_holes) + len(state.neutron_stars)
            total_mass = (
                sum(mc.mass for mc in state.molecular_clouds)
                + sum(bh.mass for bh in state.black_holes)
                + sum(ns.mass for ns in state.neutron_stars)
            )
            if entity_count == 0 or total_mass <= 0:
                print(f"Reset at year {current_year}: entities={entity_count}, mass={total_mass}")
                state, ring = initialize_state()
                current_year = 0
                zoom = 1.0
                view_center_x = SCREEN_WIDTH / 2.0
                view_center_y = SCREEN_HEIGHT / 2.0

            view_w = int(SCREEN_WIDTH / zoom)
            view_h = int(SCREEN_HEIGHT / zoom)
            max_barrier_r = max(ring.radii)
            barrier_diam = int(max_barrier_r * 2)
            needed_w = max(view_w + SCREEN_WIDTH, barrier_diam + SCREEN_WIDTH)
            needed_h = max(view_h + SCREEN_HEIGHT, barrier_diam + SCREEN_HEIGHT)
            if needed_w > world_surface_w or needed_h > world_surface_h:
                world_surface_w = int(needed_w * 1.5)
                world_surface_h = int(needed_h * 1.5)
                world_surface = pygame.Surface((world_surface_w, world_surface_h))

            world_offset_x = (world_surface_w - SCREEN_WIDTH) // 2
            world_offset_y = (world_surface_h - SCREEN_HEIGHT) // 2

            world_surface.fill(BACKGROUND_COLOR)
            draw_simulation(world_surface, ring, state, world_offset_x, world_offset_y)

            ws_cx = world_offset_x + view_center_x
            ws_cy = world_offset_y + view_center_y
            view_left = max(0, min(world_surface_w - view_w, int(ws_cx - view_w / 2)))
            view_top = max(0, min(world_surface_h - view_h, int(ws_cy - view_h / 2)))
            visible_rect = pygame.Rect(view_left, view_top, view_w, view_h)
            if zoom == 1.0:
                screen.blit(world_surface, (0, 0), area=visible_rect)
            else:
                visible_area = world_surface.subsurface(visible_rect)
                scaled = pygame.transform.scale(visible_area, (SCREEN_WIDTH, SCREEN_HEIGHT))
                screen.blit(scaled, (0, 0))

            draw_ui(screen, font, current_year, zoom)

            current_year += 1

            pygame.display.flip()
            clock.tick(60)

        print("Exited simulation")

        try:
            from sim.rng import serialize_state, generate
            state_bytes, entity_count = serialize_state(state)
            result = generate(state_bytes, 10000000000000000000, 99999999999999999999)
            print(f"RANDOM: {result['random_number']}")
        except Exception as rng_err:
            print(f"RNG FAILED: {rng_err}")

    except Exception as e:
        import traceback
        print(f"Error occurred in simulation loop: {e}")
        traceback.print_exc()
    finally:
        pygame.quit()


def initialize_state():
    state = SimulationState()
    ring = BARRIER((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), (800, 800), BARRIER_POINT_COUNT)

    density_weights = [max(0.0, 1.0 - CMB_DENSITY_CONTRAST * ring.perturbation[i]) for i in range(ring.num_points)]
    total_weight = sum(density_weights)
    density_weights = [w / total_weight for w in density_weights]
    cumulative_weights = []
    running_sum = 0.0
    for w in density_weights:
        running_sum += w
        cumulative_weights.append(running_sum)

    for _ in range(MOLECULAR_CLOUD_COUNT):
        r = random.random()
        idx = bisect.bisect_left(cumulative_weights, r)
        idx = min(idx, ring.num_points - 1)
        step = 2 * math.pi / ring.num_points
        angle = ring.angles[idx] + random.uniform(0, step)
        local_radius = ring.get_radius_at_angle(angle)
        radius = math.sqrt(random.uniform(0, 1)) * local_radius
        x = SCREEN_WIDTH // 2 + radius * math.cos(angle)
        y = SCREEN_HEIGHT // 2 + radius * math.sin(angle)
        molecular_cloud = MOLECULAR_CLOUD(x, y, MOLECULAR_CLOUD_START_SIZE, MOLECULAR_CLOUD_START_MASS)
        state.molecular_clouds.append(molecular_cloud)

    return state, ring


def main():
    pygame.init()
    pygame.display.set_caption("simcraft")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    font = pygame.font.SysFont('Monospace', 14)
    print("Populating space with molecular clouds")
    state, ring = initialize_state()

    print("Starting simulation")
    run_simulation(screen, font, state, ring)

if __name__ == "__main__":
    main()
