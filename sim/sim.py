import os
import pygame
import math
import random
import bisect


# ── Display ──
BACKGROUND_COLOR = (0, 10, 20) # RGB background color (dark blue-black, like space).
LABEL_COLOR = (60, 60, 200)    # RGB color for UI text labels.
SCREEN_WIDTH = 1440             # Display width in pixels. Change to match your monitor.
SCREEN_HEIGHT = 960             # Display height in pixels. Change to match your monitor.

# ── Zoom ──
ZOOM_MIN = 0.5                 # Minimum zoom level (zoomed out). Lower = can see more.
ZOOM_MAX = 1.5                 # Maximum zoom level (zoomed in). Higher = can zoom in more.
ZOOM_STEP = 0.25               # Zoom change per scroll wheel tick.

# ── Timing ──
YEAR_RATE = 60                 # Simulated years per real second. Higher = faster time progression in the UI counter.
MAX_DELTA_TIME = 0.05          # Maximum physics time step per frame (seconds). Caps dt to prevent instability on lag spikes.

# ── Physics ──
GRAVITY_SCALE = 0.15  # Master gravity multiplier applied to all gravitational constants. Increase for stronger gravity everywhere.
VELOCITY_DAMPING = 0.97        # Per-frame velocity multiplier for all entities. Below 1.0 = energy dissipation. 1.0 = no damping.

# ── CMB Perturbations (initial conditions, inspired by real cosmic microwave background) ──
# These control how the universe looks at the very start of the simulation.
# The barrier ring isn't a perfect circle — it's warped by Fourier perturbations,
# and clouds spawn denser in the "dented" regions, seeding the clumps that
# eventually collapse into stars and black holes. Set all to 0 for a perfectly
# uniform start (boring). Crank them up for wild, lumpy initial conditions.
CMB_PERTURBATION_MODES = 10     # Number of sine-wave modes layered onto the barrier shape. 1 = simple oval,
                                # 6 = complex bumpy ring, 20+ = very jagged. Each higher mode adds finer detail.
CMB_PERTURBATION_SCALE = 0.08  # Amplitude of each mode (as a fraction of barrier radius). 0 = perfect circle,
                                # 0.08 = subtle bumps (~8%), 0.3+ = dramatic deformations.
CMB_DENSITY_CONTRAST = 0.4     # How strongly barrier shape biases initial cloud placement. 0 = clouds spread
                                # evenly regardless of barrier shape, 0.6 = noticeably clumpy, 1.0 = extreme
                                # clustering in dented regions (can leave large voids elsewhere).

# ── Barrier (cosmic boundary ring) ──
BARRIER_POINT_COUNT = 640       # Number of vertices defining the barrier ring. More = smoother circle, but slower.
BARRIER_INITIAL_SIZE = 240      # Starting diameter of the barrier ring in pixels.
BARRIER_GRAVITY_CONSTANT = 120 * GRAVITY_SCALE  # Base gravitational pull of the barrier on entities. Higher = stronger inward pull.
BARRIER_COLOR = (30, 60, 220)   # RGB color of the barrier ring at rest.
BARRIER_BASE_OPACITY = 150      # Transparency of the barrier at rest (0=invisible, 255=opaque).
BARRIER_FLASH_COLOR = (0, 184, 106)  # RGB color the barrier flashes when deformed (green).
BARRIER_FLASH_OPACITY = 255     # Peak opacity during a barrier flash (0-255).
BARRIER_FLASH_DECAY = 4.0       # How fast barrier flashes fade per second. Higher = faster fade.
BARRIER_WAVE_PUSH = 400.0       # Force magnitude when pulses hit the barrier. Higher = more barrier wobble.
BARRIER_DAMPING = 0.04          # Damping factor for barrier deformation velocity. Lower = more oscillation.
BARRIER_DEFORM_THRESHOLD = 0.1  # Minimum radius change (pixels) to trigger a flash effect.
BARRIER_HEAVY_MASS_THRESHOLD = 100  # Combined mass near a barrier section that weakens containment. Higher = harder to break out.
BARRIER_SMOOTHING_PASSES = 3    # Number of smoothing iterations when drawing the barrier. More = smoother shape.
BARRIER_SMOOTHING_WINDOW = 5    # Window size for the smoothing algorithm (must be odd). Larger = smoother but less detail.

# ── Barrier Interaction (how different entities interact with the barrier) ──
MC_BARRIER_GRAVITY_FACTOR = 0.001  # Gravity multiplier for clouds vs barrier. Very weak — clouds drift inward gently.
BH_BARRIER_GRAVITY_FACTOR = 0.01   # Gravity multiplier for black holes vs barrier. 10x stronger than clouds.
NS_BARRIER_GRAVITY_FACTOR = 0.008   # Gravity multiplier for neutron stars vs barrier. Strongest pull.

MC_BARRIER_DEFORM_FACTOR = 2.0     # How strongly massive clouds dent the barrier on approach.
BH_BARRIER_DEFORM_FACTOR = 12.0    # How strongly black holes dent the barrier. Very high.
NS_BARRIER_DEFORM_FACTOR = 6.0     # How strongly neutron stars dent the barrier.

# ── Molecular Clouds ──
MOLECULAR_CLOUD_COUNT = 4800    # Number of clouds spawned at simulation start. More = denser universe, slower performance.
MOLECULAR_CLOUD_START_SIZE = 20 # Initial visual size of clouds in pixels.
MOLECULAR_CLOUD_MIN_SIZE = 6    # Smallest a cloud can shrink to as it gains mass.
MOLECULAR_CLOUD_GROWTH_RATE = 0.24  # How fast clouds visually shrink as they gain mass. Higher = shrinks faster.
MOLECULAR_CLOUD_START_MASS = 1  # Initial mass of each cloud.
MOLECULAR_CLOUD_GRAVITY_CONSTANT = 0.0008 * GRAVITY_SCALE  # Gravitational attraction between clouds. Very low to prevent instant clumping.
MOLECULAR_CLOUD_MERGE_CHANCE = 0.004  # Probability (0-1) of two colliding clouds merging per frame. Higher = faster merging.
MOLECULAR_CLOUD_MAX_MASS = 48   # Maximum mass a cloud/star can reach. Caps growth.
MOLECULAR_CLOUD_START_COLORS = [
    (140, 20, 20),   # Hydrogen - Red (H-alpha)
    (140, 130, 0),   # Helium - Yellow (D3)
    (20, 140, 20),   # Oxygen - Green (OI)
    (20, 20, 140),   # Carbon - Blue (C2)
    (160, 100, 0),   # Neon - Orange (NeI)
    (80, 20, 140),   # Nitrogen - Violet (NII)
    (150, 150, 150), # Iron - Metallic Gray
    (140, 90, 40),   # Silicon - Earthy Brown
    (140, 120, 20),  # Gold - Deep Warm Yellow
    (180, 60, 80),   # Sulfur - Crimson-Rose (SII)
    (100, 170, 200), # Magnesium - Pale Blue (MgII)
    (40, 140, 150),  # Phosphorus - Teal (PI)
    (160, 40, 130),  # Lithium - Magenta (LiI)
    (210, 210, 230), # Platinum - Cool Silver
    (60, 90, 160),   # Cobalt - Steel Blue (CoII)
    (200, 120, 50),  # Calcium - Warm Orange (CaII)
    (220, 170, 40),  # Sodium - Amber (NaI D-line)
    (120, 120, 100), # Nickel - Dark Gray (NiI)
    (50, 130, 70),   # Chromium - Deep Green (CrI)
    (110, 70, 160),  # Titanium - Violet-Blue (TiI)
]
MOLECULAR_CLOUD_END_COLOR = (225, 255, 255)  # Color clouds fade toward as they gain mass (white-blue).
MOLECULAR_CLOUD_OPACITY = 128   # Maximum opacity for clouds below protostar mass (0-255).
MOLECULAR_CLOUD_MIN_OPACITY = 64  # Minimum opacity for the lightest clouds (0-255).
DEFAULT_STATE_CHANCE = 0.002    # Per-frame chance a massive star resets to gas cloud, ejecting material (supernova-like event).
EJECTA_HEAVIER_ELEMENT_CHANCE = 0.4  # Probability that ejecta from supernovae produce heavier elements than the parent.

# ── Molecular Cloud Emission (clouds shed daughter clouds) ──
MC_EMISSION_CHANCE = 0.2          # Per-frame chance for eligible clouds to emit
MC_EMISSION_MIN_PARENT_MASS = 6     # Minimum parent mass to emit
MC_EMISSION_MASS_MIN = 1            # Min mass of emitted cloud
MC_EMISSION_MASS_MAX = 4            # Max mass of emitted cloud
MC_EMISSION_VELOCITY = 0.8         # Emission kick speed
MC_EMISSION_SPREAD = 12              # Max spawn distance from parent
MC_EMISSION_COUNT = 4               # Max number of emissions per cloud

# ── Protostars (clouds that reach enough mass to ignite) ──
PROTOSTAR_THRESHOLD = 32        # Mass at which a cloud becomes a protostar (changes appearance and behavior).
PROTOSTAR_EJECTA_COUNT = 12     # Number of ejecta pieces produced during protostar formation events.
PROTOSTAR_EJECTA_SPREAD = 32    # Max spawn distance (pixels) of ejecta from the parent star.

# Element weight boundaries for star tiers.
# When a cloud reaches PROTOSTAR_THRESHOLD mass, its element_index (position in
# MOLECULAR_CLOUD_START_COLORS above) determines which tier of star it becomes:
#   Index 0-4  (H, He, O, C, Ne)           → LOW tier  — small white star
#   Index 5-9  (N, Fe, Si, Au, S)           → MEDIUM tier — mid-size yellow-green star
#   Index 10-19 (Mg, P, Li, Pt, Co, Ca...) → HIGH tier — large red giant
# Lowering these values makes heavier stars more common; raising them makes them rarer.
ELEMENT_WEIGHT_MEDIUM = 5   # Element index at or above which a star becomes medium tier.
ELEMENT_WEIGHT_HEAVY = 10   # Element index at or above which a star becomes a red giant (high tier).

PROTOSTAR_LOW_COLOR = (225, 255, 255)      # White (current)
PROTOSTAR_LOW_SIZE = 2
PROTOSTAR_LOW_MASS_BOOST = 4              # No extra mass for light stars

PROTOSTAR_MEDIUM_COLOR = (200, 230, 80)    # Yellow-green
PROTOSTAR_MEDIUM_SIZE = 4
PROTOSTAR_MEDIUM_MASS_BOOST = 8           # Medium stars get +3 mass on formation

PROTOSTAR_HIGH_COLOR = (180, 60, 30)       # Red-orange
PROTOSTAR_HIGH_SIZE = 6
PROTOSTAR_HIGH_MASS_BOOST = 12             # Red giants get +6 mass on formation

# Higher BH conversion chance for red giants
RED_GIANT_BLACK_HOLE_CHANCE = 0.00002

# ── Black Holes ──
BLACK_HOLE_THRESHOLD = 42       # Mass above which a star can collapse into a black hole.
BLACK_HOLE_CHANCE = 0.0004      # Per-frame probability a qualifying star becomes a black hole. Very rare.
BLACK_HOLE_RADIUS = 10           # Visual radius divisor — smaller value = larger drawn black hole (mass / this).
BLACK_HOLE_MAX_MASS = 64        # Maximum mass a black hole can accumulate.
BLACK_HOLE_GRAVITY_CONSTANT = 14.0 * GRAVITY_SCALE  # Gravitational pull strength. Much higher than clouds.
BLACK_HOLE_DECAY_RATE = 0.8     # Mass lost per second (Hawking radiation analog). Higher = shorter lifespan.
BLACK_HOLE_DECAY_THRESHOLD = 8  # Mass at which a black hole evaporates and releases ejecta.
BLACK_HOLE_COLOR = (0,0,0)      # RGB fill color of the black hole (black).
BLACK_HOLE_BORDER_COLOR = (100, 0, 0)  # RGB color of the event horizon ring (dark red).
BLACK_HOLE_MERGE_COLOR = (0, 60, 180, 100)  # RGBA color of the gravitational wave pulse from BH mergers.
DISK_COLOR = (255, 100, 100)    # RGB color of the accretion disk tracer dot (light red).
DISK_SIZE = 1                   # Visual size in pixels of the accretion disk tracer.
DISK_ROTATION = 10.0            # Base rotation speed (rad/s) of the accretion disk tracer. Spin adds to this.

# ── Black Hole Decay (when BH evaporates) ──
BH_DECAY_CLOUD_COUNT = 6       # Number of heavy clouds spawned when a BH evaporates.
BH_DECAY_CLOUD_MASS_MIN = 24   # Minimum mass of each decay cloud. These are heavy!
BH_DECAY_CLOUD_MASS_MAX = 28   # Maximum mass of each decay cloud.
BH_DECAY_EJECTA_SPREAD = 20    # Max spawn distance (pixels) of decay ejecta from the BH.

# ── Black Hole Jets (relativistic jets from accretion events) ──
BH_JET_CHANCE = 0.4             # Probability of jet formation when a BH absorbs something.
BH_JET_STAR_COUNT = 8           # Number of clouds emitted per jet burst.
BH_JET_DURATION = 4             # Duration of jet emission in seconds.
BH_JET_SPREAD = 60              # Max spawn distance (pixels) of jet particles from the BH.
BH_JET_VELOCITY = 12.0           # Speed of ejected jet particles. Higher = faster jets.

# ── Black Hole Emission (random mass leakage) ──
BH_EMISSION_CHANCE = 0.008       # Per-frame chance a BH randomly emits a small cloud.
BH_EMISSION_MASS_MIN = 1        # Minimum mass of emitted particles.
BH_EMISSION_MASS_MAX = 3        # Maximum mass of emitted particles.
BH_EMISSION_EJECTA_SPREAD = 20  # Max spawn distance (pixels) of emitted particles.
BH_EMISSION_VELOCITY = 0.8      # Speed of emitted particles.

# ── Neutron Stars ──
NEUTRON_STAR_CHANCE = 0.08      # Probability of becoming a neutron star instead of a black hole on collapse.
NEUTRON_STAR_RADIUS = 1         # Visual radius in pixels (tiny, as expected).
NEUTRON_STAR_GRAVITY_CONSTANT = 2 * GRAVITY_SCALE  # Gravitational pull strength. Moderate — between clouds and BHs.
NEUTRON_STAR_DECAY_RATE = 0.8   # Mass lost per second. Higher = shorter lifespan.
NEUTRON_STAR_DECAY_THRESHOLD = 0.8  # Mass at which a neutron star dissipates into ejecta.
NEUTRON_STAR_COLOR = (0, 120, 255)  # RGB color of the neutron star (cyan-blue).
NEUTRON_STAR_PULSE_RATE = 0.03  # Seconds between pulsar pulses. Lower = faster pulsing.
NEUTRON_STAR_PULSE_STRENGTH = 8 # Force magnitude of each pulse ripple. Higher = stronger push on nearby entities.
NEUTRON_STAR_PULSE_COLOR = (0, 60, 180, 80)  # RGBA color of the expanding pulse ring.
NEUTRON_STAR_PULSE_WIDTH = 2    # Line width (pixels) for drawing pulse rings.
NEUTRON_STAR_RIPPLE_SPEED = 64  # How fast (pixels/sec) pulse ripples expand outward.
NEUTRON_STAR_RIPPLE_EFFECT_WIDTH = 24  # Width (pixels) of the zone where ripples exert force on entities.
NS_PULSE_MASS_BOOST = 0.02      # Mass cost per unit of pulse force. Pulsing drains the neutron star.

# ── Neutron Star Decay (when NS loses enough mass) ──
NS_DECAY_CLOUD_COUNT = 2        # Number of clouds spawned when a neutron star dissipates.
NS_DECAY_CLOUD_MASS_MIN = 1     # Minimum mass of each decay cloud.
NS_DECAY_CLOUD_MASS_MAX = 4     # Maximum mass of each decay cloud.
NS_DECAY_EJECTA_SPREAD = 20     # Max spawn distance (pixels) of decay ejecta.

# ── Kilonova (neutron star merger) ──
KILONOVA_EJECTA_COUNT = 20      # Number of ejecta pieces from a NS-NS collision. Rich in heavy elements.
KILONOVA_COLLISION_DISTANCE = 6 # Distance (pixels) at which two neutron stars merge.
KILONOVA_EJECTA_SPREAD = 80    # Max spawn distance (pixels) of kilonova ejecta. Large explosion!


entity_id_counter = 0
def generate_unique_id():
    global entity_id_counter
    entity_id_counter += 1
    return entity_id_counter


_mc_surface_cache = {}

def _get_mc_surface(size):
    if size not in _mc_surface_cache:
        _mc_surface_cache[size] = pygame.Surface((size, size), pygame.SRCALPHA)
    return _mc_surface_cache[size]


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


class Barrier:
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

    def enforce(self, state, delta_time):
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

        compact_angles_masses = []
        for bh in state.black_holes:
            a, _, _, _ = self._entity_angle_and_dist(bh)
            compact_angles_masses.append((a, bh.mass))
        for ns in state.neutron_stars:
            a, _, _, _ = self._entity_angle_and_dist(ns)
            compact_angles_masses.append((a, ns.mass))

        for ns in state.neutron_stars:
            angle, dist, dx, dy = self._entity_angle_and_dist(ns)
            barrier_r = self.get_radius_at_angle(angle)
            if dist >= barrier_r:
                section_mass = sum(
                    m for a, m in compact_angles_masses
                    if abs((a - angle + math.pi) % (2 * math.pi) - math.pi) < step * 3
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
                section_mass = sum(
                    m for a, m in compact_angles_masses
                    if abs((a - angle + math.pi) % (2 * math.pi) - math.pi) < step * 3
                )
                weakness = min(section_mass / BARRIER_HEAVY_MASS_THRESHOLD, 1.0)
                containment = 1.0 - weakness * 0.9
                if dist > 0 and containment > 0.05:
                    push_strength = 80.0 * containment
                    bh.vx -= (dx / dist) * push_strength * delta_time
                    bh.vy -= (dy / dist) * push_strength * delta_time

    def draw(self, screen, offset_x=0, offset_y=0):
        cx = self.center[0] + offset_x
        cy = self.center[1] + offset_y
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


SEED_ELEMENTAL_ABUNDANCE = [
    (0, 0.75),        # Hydrogen range: 0-75%
    (0.75, 0.98),     # Helium range: 75-98%
    (0.98, 1.0),      # Oxygen range: 98-100%
]

ELEMENTAL_ABUNDANCE = [
    (0, 0.75),        # Hydrogen range: 0-75%
    (0.75, 0.98),     # Helium range: 75-98%
    (0.98, 0.988),    # Oxygen range: 98-98.8%
    (0.988, 0.992),   # Carbon range: 98.8-99.2%
    (0.992, 0.9935),  # Neon range: 99.2-99.35%
    (0.9935, 0.9955), # Nitrogen range: 99.35-99.55%
    (0.9955, 0.9965), # Iron range: 99.55-99.65%
    (0.9965, 0.9975), # Silicon range: 99.65-99.75%
    (0.9975, 0.998),  # Gold range: 99.75-99.8%
    (0.998, 0.9988),  # Sulfur range: 99.8-99.88%
    (0.9988, 0.9993), # Magnesium range: 99.88-99.93%
    (0.9993, 0.9996), # Phosphorus range: 99.93-99.96%
    (0.9996, 0.9998), # Lithium range: 99.96-99.98%
    (0.9998, 0.99985),  # Platinum range: 99.98-99.985%
    (0.99985, 0.9999),  # Cobalt range: 99.985-99.99%
    (0.9999, 0.99994),  # Calcium range: 99.99-99.994%
    (0.99994, 0.99997), # Sodium range: 99.994-99.997%
    (0.99997, 0.99998), # Nickel range: 99.997-99.998%
    (0.99998, 0.99999), # Chromium range: 99.998-99.999%
    (0.99999, 1.0),     # Titanium range: 99.999-100%
]

EJECTA_ELEMENTAL_ABUNDANCE = [
    (0, 0.50),     # Hydrogen range: 0-50%
    (0.50, 0.78),  # Helium range: 50-78%
    (0.78, 0.85),  # Oxygen range: 78-85%
    (0.85, 0.89),  # Carbon range: 85-89%
    (0.89, 0.89),  # Neon - not produced in stellar ejecta
    (0.89, 0.89),  # Nitrogen - not produced in stellar ejecta
    (0.89, 0.93),  # Iron range: 89-93%
    (0.93, 0.96),  # Silicon range: 93-96%
    (0.96, 0.97),  # Gold range: 96-97%
    (0.97, 0.98),  # Sulfur range: 97-98%
    (0.98, 0.99),  # Magnesium range: 98-99%
    (0.99, 0.993), # Phosphorus range: 99-99.3%
    (0.993, 0.993),# Lithium - not produced in supernovae
    (0.993, 0.995),# Platinum range: 99.3-99.5%
    (0.995, 0.997),# Cobalt range: 99.5-99.7%
    (0.997, 0.998),# Calcium range: 99.7-99.8%
    (0.998, 0.999),# Sodium range: 99.8-99.9%
    (0.999, 0.9995),# Nickel range: 99.9-99.95%
    (0.9995, 0.9998),# Chromium range: 99.95-99.98%
    (0.9998, 1.0), # Titanium range: 99.98-100%
]

BH_DECAY_ELEMENTAL_ABUNDANCE = [
    (0, 0.08),     # Hydrogen range: 0-8%
    (0.08, 0.16),  # Helium range: 8-16%
    (0.16, 0.22),  # Oxygen range: 16-22%
    (0.22, 0.28),  # Carbon range: 22-28%
    (0.28, 0.30),  # Neon range: 28-30%
    (0.30, 0.36),  # Nitrogen range: 30-36%
    (0.36, 0.52),  # Iron range: 36-52%
    (0.52, 0.66),  # Silicon range: 52-66%
    (0.66, 0.74),  # Gold range: 66-74%
    (0.74, 0.80),  # Sulfur range: 74-80%
    (0.80, 0.86),  # Magnesium range: 80-86%
    (0.86, 0.90),  # Phosphorus range: 86-90%
    (0.90, 0.93),  # Lithium range: 90-93%
    (0.93, 0.95),  # Platinum range: 93-95%
    (0.95, 0.97),  # Cobalt range: 95-97%
    (0.97, 0.98),  # Calcium range: 97-98%
    (0.98, 0.99),  # Sodium range: 98-99%
    (0.99, 0.995), # Nickel range: 99-99.5%
    (0.995, 0.998),# Chromium range: 99.5-99.8%
    (0.998, 1.0),  # Titanium range: 99.8-100%
]

KILONOVA_ELEMENTAL_ABUNDANCE = [
    (0, 0.03),     # Hydrogen range: 0-3%
    (0.03, 0.06),  # Helium range: 3-6%
    (0.06, 0.09),  # Oxygen range: 6-9%
    (0.09, 0.12),  # Carbon range: 9-12%
    (0.12, 0.13),  # Neon range: 12-13%
    (0.13, 0.18),  # Nitrogen range: 13-18%
    (0.18, 0.30),  # Iron range: 18-30%
    (0.30, 0.44),  # Silicon range: 30-44%
    (0.44, 0.56),  # Gold range: 44-56%
    (0.56, 0.64),  # Sulfur range: 56-64%
    (0.64, 0.72),  # Magnesium range: 64-72%
    (0.72, 0.78),  # Phosphorus range: 72-78%
    (0.78, 0.82),  # Lithium range: 78-82%
    (0.82, 0.87),  # Platinum range: 82-87%
    (0.87, 0.91),  # Cobalt range: 87-91%
    (0.91, 0.94),  # Calcium range: 91-94%
    (0.94, 0.96),  # Sodium range: 94-96%
    (0.96, 0.98),  # Nickel range: 96-98%
    (0.98, 0.99),  # Chromium range: 98-99%
    (0.99, 1.0),   # Titanium range: 99-100%
]

class MolecularCloud:
    def __init__(self, x, y, size, mass, abundance=None):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.size = size
        self.mass = mass
        self.emission_count = 0
        self.is_star = mass >= PROTOSTAR_THRESHOLD
        if self.mass >= PROTOSTAR_THRESHOLD:
            self.opacity = 255
        else:
            factor = (self.mass - MOLECULAR_CLOUD_START_MASS) / (PROTOSTAR_THRESHOLD - MOLECULAR_CLOUD_START_MASS)
            factor = max(0.0, min(1.0, factor))
            self.opacity = int(MOLECULAR_CLOUD_MIN_OPACITY + factor * (MOLECULAR_CLOUD_OPACITY - MOLECULAR_CLOUD_MIN_OPACITY))

        rand = random.random()
        self.element_index = len(MOLECULAR_CLOUD_START_COLORS) - 1
        for i, (start, end) in enumerate(abundance or ELEMENTAL_ABUNDANCE):
            if start <= rand < end:
                self.start_color = MOLECULAR_CLOUD_START_COLORS[i]
                self.element_index = i
                break
        else:
            self.start_color = MOLECULAR_CLOUD_START_COLORS[-1]

        if self.mass >= PROTOSTAR_THRESHOLD:
            if self.element_index >= ELEMENT_WEIGHT_HEAVY:
                self.color = PROTOSTAR_HIGH_COLOR
                self.size = PROTOSTAR_HIGH_SIZE
            elif self.element_index >= ELEMENT_WEIGHT_MEDIUM:
                self.color = PROTOSTAR_MEDIUM_COLOR
                self.size = PROTOSTAR_MEDIUM_SIZE
            else:
                self.color = PROTOSTAR_LOW_COLOR
                self.size = PROTOSTAR_LOW_SIZE
        elif self.size <= 4:
            self.color = MOLECULAR_CLOUD_END_COLOR
        else:
            factor = 1.0 - (self.size - 4) / (MOLECULAR_CLOUD_START_SIZE - 4)
            self.color = interpolate_color(self.start_color, MOLECULAR_CLOUD_END_COLOR, factor)

    def draw(self, screen, offset_x=0, offset_y=0):
        draw_x = self.x + offset_x
        draw_y = self.y + offset_y
        if self.opacity < 255:
            s = _get_mc_surface(self.size)
            s.fill(self.color + (self.opacity,))
            screen.blit(s, (draw_x, draw_y))
        else:
            pygame.draw.rect(screen, self.color, (draw_x, draw_y, self.size, self.size))

    def update(self):
        self.size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((self.mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
        self.mass = min(self.mass, MOLECULAR_CLOUD_MAX_MASS)
        if self.mass >= PROTOSTAR_THRESHOLD:
            if not self.is_star:
                self.is_star = True
                if self.element_index >= ELEMENT_WEIGHT_HEAVY:
                    self.mass = min(self.mass + PROTOSTAR_HIGH_MASS_BOOST, MOLECULAR_CLOUD_MAX_MASS)
                elif self.element_index >= ELEMENT_WEIGHT_MEDIUM:
                    self.mass = min(self.mass + PROTOSTAR_MEDIUM_MASS_BOOST, MOLECULAR_CLOUD_MAX_MASS)
                else:
                    self.mass = min(self.mass + PROTOSTAR_LOW_MASS_BOOST, MOLECULAR_CLOUD_MAX_MASS)
            self.opacity = 255
            if self.element_index >= ELEMENT_WEIGHT_HEAVY:
                self.color = PROTOSTAR_HIGH_COLOR
                self.size = PROTOSTAR_HIGH_SIZE
            elif self.element_index >= ELEMENT_WEIGHT_MEDIUM:
                self.color = PROTOSTAR_MEDIUM_COLOR
                self.size = PROTOSTAR_MEDIUM_SIZE
            else:
                self.color = PROTOSTAR_LOW_COLOR
                self.size = PROTOSTAR_LOW_SIZE
        else:
            factor = (self.mass - MOLECULAR_CLOUD_START_MASS) / (PROTOSTAR_THRESHOLD - MOLECULAR_CLOUD_START_MASS)
            factor = max(0.0, min(1.0, factor))
            self.opacity = int(MOLECULAR_CLOUD_MIN_OPACITY + factor * (MOLECULAR_CLOUD_OPACITY - MOLECULAR_CLOUD_MIN_OPACITY))
            if self.size <= 4:
                self.color = MOLECULAR_CLOUD_END_COLOR
            else:
                factor = 1.0 - (self.size - 4) / (MOLECULAR_CLOUD_START_SIZE - 4)
                self.color = interpolate_color(self.start_color, MOLECULAR_CLOUD_END_COLOR, factor)

    def collides_with(self, other):
        return (self.x < other.x + other.size and
                self.x + self.size > other.x and
                self.y < other.y + other.size and
                self.y + self.size > other.y)


class BlackHole:
    def __init__(self, x, y, mass):
        self.id = generate_unique_id()
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mass = min(mass, BLACK_HOLE_MAX_MASS)
        self.border_radius = int(self.mass // BLACK_HOLE_RADIUS)
        self.tracer_angle = random.uniform(0, 2 * math.pi)
        self.angular_momentum = 0.0  # Spin from off-center accretion
        self.jet_streams = []  # list of [time_remaining, stars_left, angle]

    def draw(self, screen, offset_x=0, offset_y=0):
        draw_x = int(self.x + offset_x)
        draw_y = int(self.y + offset_y)
        radius = int(self.mass // BLACK_HOLE_RADIUS)
        self.border_radius = radius
        pygame.draw.circle(screen, BLACK_HOLE_BORDER_COLOR, (draw_x, draw_y), radius)
        pygame.draw.circle(screen, BLACK_HOLE_COLOR, (draw_x, draw_y), radius - 2)

        tracer_x = draw_x + self.border_radius * math.cos(self.tracer_angle)
        tracer_y = draw_y + self.border_radius * math.sin(self.tracer_angle)
        pygame.draw.circle(screen, DISK_COLOR, (int(tracer_x), int(tracer_y)), DISK_SIZE)

    def attract(self, state, delta_time, mc_to_remove, ns_to_remove, bh_to_remove):
        for black_hole in state.black_holes:
            if black_hole is not self and black_hole not in bh_to_remove:
                dx = self.x - black_hole.x
                dy = self.y - black_hole.y
                distance = max(math.hypot(dx, dy), 1)

                if self.mass > black_hole.mass and distance < self.border_radius:
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
                    self.mass += black_hole.mass
                    self.mass = min(self.mass, BLACK_HOLE_MAX_MASS)
                    state.black_hole_pulses.append([self.x, self.y, 0, black_hole.mass])
                    if random.random() < BH_JET_CHANCE:
                        self.jet_streams.append([BH_JET_DURATION, BH_JET_STAR_COUNT, random.uniform(0, 2 * math.pi)])
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
            # Check both current distance and swept trajectory for tunneling prevention
            captured = distance < self.border_radius or check_swept_collision(entity, self.x, self.y, self.border_radius, delta_time)
            if captured:
                mc_to_remove.add(entity)
                # Transfer angular momentum from off-center accretion: L = r x p
                rel_vx = entity.vx - self.vx
                rel_vy = entity.vy - self.vy
                self.angular_momentum += (dx * rel_vy - dy * rel_vx) * entity.mass
                # Conserve momentum during accretion
                total_mass = self.mass + entity.mass
                if total_mass > 0:
                    self.vx = (self.mass * self.vx + entity.mass * entity.vx) / total_mass
                    self.vy = (self.mass * self.vy + entity.mass * entity.vy) / total_mass
                self.mass += entity.mass
                self.mass = min(self.mass, BLACK_HOLE_MAX_MASS)
                if random.random() < BH_JET_CHANCE:
                    self.jet_streams.append([BH_JET_DURATION, BH_JET_STAR_COUNT, random.uniform(0, 2 * math.pi)])
            else:
                force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * entity.mass) / (distance**2)
                # Newton's 3rd law: MC pulled toward BH, BH pulled toward MC
                entity.vx += (dx / distance) * force * delta_time
                entity.vy += (dy / distance) * force * delta_time
                self.vx -= (dx / distance) * force * delta_time
                self.vy -= (dy / distance) * force * delta_time

        for entity in state.neutron_stars:
            if entity in ns_to_remove:
                continue
            dx = self.x - entity.x
            dy = self.y - entity.y
            distance = max(math.hypot(dx, dy), 1)
            captured = distance < self.border_radius or check_swept_collision(entity, self.x, self.y, self.border_radius, delta_time)
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
                self.mass += entity.mass
                if random.random() < BH_JET_CHANCE:
                    self.jet_streams.append([BH_JET_DURATION, BH_JET_STAR_COUNT, random.uniform(0, 2 * math.pi)])
                self.mass = min(self.mass, BLACK_HOLE_MAX_MASS)
            else:
                force = BLACK_HOLE_GRAVITY_CONSTANT * (self.mass * entity.mass) / (distance**2)
                # Newton's 3rd law: NS pulled toward BH, BH pulled toward NS
                entity.vx += (dx / distance) * force * delta_time
                entity.vy += (dy / distance) * force * delta_time
                self.vx -= (dx / distance) * force * delta_time
                self.vy -= (dy / distance) * force * delta_time

    def decay(self, delta_time):
        self.mass -= BLACK_HOLE_DECAY_RATE * delta_time


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
        self.pulse_rate = NEUTRON_STAR_PULSE_RATE
        self.pulse_strength = NEUTRON_STAR_PULSE_STRENGTH
        self.time_since_last_pulse = 0
        self.active_pulses = []
        self.pulse_color_state = 0  # 0: normal color, 1: white during pulse
        self.pulse_color_duration = 0.1  # Duration of white color in seconds

    def draw(self, screen, ring, all_pulses, offset_x=0, offset_y=0):
        draw_x = int(self.x + offset_x)
        draw_y = int(self.y + offset_y)
        current_color = (255, 255, 255) if self.pulse_color_state == 1 else NEUTRON_STAR_COLOR
        pygame.draw.circle(screen, current_color, (draw_x, draw_y), self.radius)

        for pulse in self.active_pulses:
            pulse_radius, _, fade = pulse
            if pulse_radius <= 1:
                continue

            points = _clip_pulse_points(draw_x, draw_y, pulse_radius, ring, all_pulses, offset_x=offset_x, offset_y=offset_y)

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

    def update_pulse(self, state, ring, delta_time):
        self.time_since_last_pulse += delta_time

        if self.pulse_color_state == 1:
            self.pulse_color_duration -= delta_time
            if self.pulse_color_duration <= 0:
                self.pulse_color_state = 0
                self.pulse_color_duration = 0.1

        dist_to_center = math.hypot(self.x - ring.center[0], self.y - ring.center[1])
        min_barrier_dist = max((ring.rest_radius - dist_to_center) / 2, 1.0)
        max_barrier_dist = (dist_to_center + ring.rest_radius) / 2

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
                    ring.flash[bi] = max(ring.flash[bi], new_fade * 0.4)
                    ring.radii_vel[bi] += BARRIER_WAVE_PUSH * 0.3 * new_fade * delta_time

            r_inner = max(0, radius - NEUTRON_STAR_RIPPLE_EFFECT_WIDTH)
            r_outer = radius + NEUTRON_STAR_RIPPLE_EFFECT_WIDTH
            r_inner_sq = r_inner * r_inner
            r_outer_sq = r_outer * r_outer
            for molecular_cloud in state.molecular_clouds:
                dx = molecular_cloud.x - self.x
                dy = molecular_cloud.y - self.y
                dist_sq = dx * dx + dy * dy
                if dist_sq < r_inner_sq or dist_sq > r_outer_sq:
                    continue
                distance = math.sqrt(dist_sq)

                ripple_dist = abs(distance - radius)
                if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH:
                    effect_factor = 1.0 - (ripple_dist / NEUTRON_STAR_RIPPLE_EFFECT_WIDTH)
                    force = self.pulse_strength * effect_factor / ((ripple_dist + 1) ** 0.8)

                    if distance > 0:
                        molecular_cloud.vx += (dx / distance) * force * delta_time
                        molecular_cloud.vy += (dy / distance) * force * delta_time
                        # Energy cost: subtract imparted kinetic energy from NS mass
                        energy_cost = force * delta_time * NS_PULSE_MASS_BOOST
                        self.mass -= energy_cost
                        self.mass = max(self.mass, 0.1)

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

    def apply_gravity(self, state, delta_time):
        for molecular_cloud in state.spatial_hash.query_neighbors(self):
            dx = molecular_cloud.x - self.x
            dy = molecular_cloud.y - self.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < 1:
                continue
            distance = math.sqrt(dist_sq)

            force = NEUTRON_STAR_GRAVITY_CONSTANT * (self.mass * molecular_cloud.mass) / dist_sq

            molecular_cloud.vx -= (dx / distance) * force * delta_time
            molecular_cloud.vy -= (dy / distance) * force * delta_time

            self.vx += (dx / distance) * force * delta_time
            self.vy += (dy / distance) * force * delta_time

        for black_hole in state.black_holes:
            dx = black_hole.x - self.x
            dy = black_hole.y - self.y
            distance = max(math.hypot(dx, dy), 1)

            force = NEUTRON_STAR_GRAVITY_CONSTANT * (self.mass * black_hole.mass) / (distance**2)

            # Newton's 3rd law: equal and opposite forces
            self.vx += (dx / distance) * force * delta_time
            self.vy += (dy / distance) * force * delta_time
            black_hole.vx -= (dx / distance) * force * delta_time
            black_hole.vy -= (dy / distance) * force * delta_time

    def decay(self, delta_time):
        self.mass -= NEUTRON_STAR_DECAY_RATE * delta_time


def check_swept_collision(entity, target_x, target_y, target_radius, delta_time):
    """Check if entity's trajectory over this frame passes within target_radius of a point.
    Returns True if the closest approach distance is less than target_radius."""
    # Ray from entity's current position along its velocity vector
    dx = entity.vx * delta_time
    dy = entity.vy * delta_time
    move_dist_sq = dx * dx + dy * dy
    if move_dist_sq < 0.01:
        return False  # Not moving fast enough to tunnel

    # Vector from entity to target
    fx = target_x - entity.x
    fy = target_y - entity.y

    # Project target onto movement ray: t = dot(f, d) / dot(d, d)
    t = max(0.0, min(1.0, (fx * dx + fy * dy) / move_dist_sq))

    # Closest point on ray
    closest_x = entity.x + t * dx
    closest_y = entity.y + t * dy
    closest_dist_sq = (target_x - closest_x) ** 2 + (target_y - closest_y) ** 2

    return closest_dist_sq < target_radius * target_radius


def integrate_entity(entity, delta_time):
    # Symplectic Euler: update velocity first (with damping), then position using new velocity
    # This preserves energy much better than forward Euler and allows stable orbits
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
            is_protostar = mc.mass >= PROTOSTAR_THRESHOLD or other.mass >= PROTOSTAR_THRESHOLD
            elements_compatible = is_protostar or abs(mc.element_index - other.element_index) <= 1
            if mc.collides_with(other) and elements_compatible and random.random() < MOLECULAR_CLOUD_MERGE_CHANCE:
                merged_mass = mc.mass + other.mass
                if other.element_index > mc.element_index:
                    survivor, consumed = other, mc
                else:
                    survivor, consumed = mc, other
                to_remove.add(consumed)
                # Conserve momentum: v_new = (m1*v1 + m2*v2) / (m1+m2)
                total_mass = survivor.mass + consumed.mass
                if total_mass > 0:
                    survivor.vx = (survivor.mass * survivor.vx + consumed.mass * consumed.vx) / total_mass
                    survivor.vy = (survivor.mass * survivor.vy + consumed.mass * consumed.vy) / total_mass
                survivor.mass = min(merged_mass, MOLECULAR_CLOUD_MAX_MASS)
                survivor.update()
                if consumed is mc:
                    break
                continue
    if to_remove:
        state.molecular_clouds = [mc for mc in state.molecular_clouds if mc not in to_remove]


def update_entities(state):
    handle_collisions(state)
    to_remove = set()
    new_clouds = []
    for molecular_cloud in state.molecular_clouds:
        molecular_cloud.update()
        if molecular_cloud.mass > BLACK_HOLE_THRESHOLD:
            bh_chance = RED_GIANT_BLACK_HOLE_CHANCE if molecular_cloud.element_index >= ELEMENT_WEIGHT_HEAVY else BLACK_HOLE_CHANCE
            if random.random() < bh_chance:
                if random.random() < NEUTRON_STAR_CHANCE:
                    state.neutron_stars.append(NeutronStar(molecular_cloud.x, molecular_cloud.y, molecular_cloud.mass))
                else:
                    state.black_holes.append(BlackHole(molecular_cloud.x, molecular_cloud.y, molecular_cloud.mass))
                to_remove.add(molecular_cloud)
            elif random.random() < DEFAULT_STATE_CHANCE:
                if molecular_cloud.element_index >= ELEMENT_WEIGHT_HEAVY:
                    ejecta_count = 25
                    ejecta_spread = 80
                elif molecular_cloud.element_index >= ELEMENT_WEIGHT_MEDIUM:
                    ejecta_count = 20
                    ejecta_spread = 60
                else:
                    ejecta_count = 15
                    ejecta_spread = 50
                parent_idx = molecular_cloud.element_index
                max_idx = len(MOLECULAR_CLOUD_START_COLORS) - 1
                for _ in range(ejecta_count):
                    offset_angle = random.uniform(0, 2 * math.pi)
                    offset_dist = random.uniform(5, ejecta_spread)
                    ex = molecular_cloud.x + offset_dist * math.cos(offset_angle)
                    ey = molecular_cloud.y + offset_dist * math.sin(offset_angle)
                    mass = random.uniform(MOLECULAR_CLOUD_START_MASS, PROTOSTAR_THRESHOLD * 0.35)
                    size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                    child = MolecularCloud(ex, ey, size, mass)
                    if random.random() < EJECTA_HEAVIER_ELEMENT_CHANCE and parent_idx < max_idx:
                        child.element_index = min(parent_idx + random.randint(1, 3), max_idx)
                    else:
                        child.element_index = parent_idx
                    child.start_color = MOLECULAR_CLOUD_START_COLORS[child.element_index]
                    child.vx = math.cos(offset_angle) * offset_dist * 0.5
                    child.vy = math.sin(offset_angle) * offset_dist * 0.5
                    new_clouds.append(child)
                molecular_cloud.mass = MOLECULAR_CLOUD_START_MASS
                molecular_cloud.size = MOLECULAR_CLOUD_START_SIZE
                molecular_cloud.update()
        elif molecular_cloud.mass >= MC_EMISSION_MIN_PARENT_MASS and molecular_cloud.emission_count < MC_EMISSION_COUNT and molecular_cloud not in to_remove:
            # Emission: clouds shed small daughter clouds, losing mass in the process
            if random.random() < MC_EMISSION_CHANCE:
                emit_mass = random.uniform(MC_EMISSION_MASS_MIN, min(MC_EMISSION_MASS_MAX, molecular_cloud.mass - MOLECULAR_CLOUD_START_MASS))
                if emit_mass > 0:
                    offset_angle = random.uniform(0, 2 * math.pi)
                    offset_dist = random.uniform(2, MC_EMISSION_SPREAD)
                    ex = molecular_cloud.x + offset_dist * math.cos(offset_angle)
                    ey = molecular_cloud.y + offset_dist * math.sin(offset_angle)
                    size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((emit_mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                    child = MolecularCloud(ex, ey, size, emit_mass)
                    child.element_index = molecular_cloud.element_index
                    child.start_color = MOLECULAR_CLOUD_START_COLORS[child.element_index]
                    # Emission velocity: parent's velocity + kick away
                    child.vx = molecular_cloud.vx + math.cos(offset_angle) * MC_EMISSION_VELOCITY
                    child.vy = molecular_cloud.vy + math.sin(offset_angle) * MC_EMISSION_VELOCITY
                    # Conserve momentum: recoil on parent
                    molecular_cloud.vx -= (emit_mass / molecular_cloud.mass) * math.cos(offset_angle) * MC_EMISSION_VELOCITY
                    molecular_cloud.vy -= (emit_mass / molecular_cloud.mass) * math.sin(offset_angle) * MC_EMISSION_VELOCITY
                    molecular_cloud.mass -= emit_mass
                    molecular_cloud.emission_count += 1
                    molecular_cloud.update()
                    new_clouds.append(child)
    if to_remove:
        state.molecular_clouds = [mc for mc in state.molecular_clouds if mc not in to_remove]
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
    ring.enforce(state, delta_time)

    for black_hole in state.black_holes:
        # Tracer rotation driven by angular momentum (with base rotation)
        spin_rate = DISK_ROTATION + black_hole.angular_momentum / max(black_hole.mass, 1.0)
        black_hole.tracer_angle += spin_rate * delta_time
        # Gradually dissipate angular momentum
        black_hole.angular_momentum *= 0.999 ** delta_time

    pulses_to_remove = []
    for i, pulse in enumerate(state.black_hole_pulses):
        x, y, radius, consumed_mass = pulse
        new_radius = radius + (NEUTRON_STAR_RIPPLE_SPEED * delta_time * 1.5)
        state.black_hole_pulses[i] = [x, y, new_radius, consumed_mass]

        # Track energy budget from consumed mass
        energy_budget = consumed_mass

        # BH merger pulse: force scales with consumed mass (heavier mergers = stronger waves)
        mass_scale = consumed_mass / 5.0
        bh_ew = NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3
        bh_r_inner = max(0, radius - bh_ew)
        bh_r_outer = radius + bh_ew
        bh_r_inner_sq = bh_r_inner * bh_r_inner
        bh_r_outer_sq = bh_r_outer * bh_r_outer
        for molecular_cloud in state.molecular_clouds:
            if energy_budget <= 0:
                break
            dx = molecular_cloud.x - x
            dy = molecular_cloud.y - y
            dist_sq = dx * dx + dy * dy
            if dist_sq < bh_r_inner_sq or dist_sq > bh_r_outer_sq:
                continue
            distance = math.sqrt(dist_sq)

            ripple_dist = abs(distance - radius)
            if ripple_dist < bh_ew:
                effect_factor = 1.0 - (ripple_dist / bh_ew)
                force = NEUTRON_STAR_PULSE_STRENGTH * 3 * effect_factor * mass_scale / ((ripple_dist + 1) ** 1.5)

                if distance > 0:
                    molecular_cloud.vx += (dx / distance) * force * delta_time
                    molecular_cloud.vy += (dy / distance) * force * delta_time
                    energy_budget -= force * delta_time * 0.01

        for black_hole in state.black_holes:
            if energy_budget <= 0:
                break
            dx = black_hole.x - x
            dy = black_hole.y - y
            distance = math.hypot(dx, dy)

            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 4:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 4))
                force = NEUTRON_STAR_PULSE_STRENGTH * 2 * effect_factor * mass_scale / ((ripple_dist + 1) ** 2)

                if distance > 0:
                    black_hole.vx += (dx / distance) * force * delta_time
                    black_hole.vy += (dy / distance) * force * delta_time
                    energy_budget -= force * delta_time * 0.01

        for neutron_star in state.neutron_stars:
            if energy_budget <= 0:
                break
            dx = neutron_star.x - x
            dy = neutron_star.y - y
            distance = math.hypot(dx, dy)

            ripple_dist = abs(distance - radius)
            if ripple_dist < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3:
                effect_factor = 1.0 - (ripple_dist / (NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 3))
                force = NEUTRON_STAR_PULSE_STRENGTH * 2.5 * effect_factor * mass_scale / ((ripple_dist + 1) ** 1.8)

                if distance > 0:
                    neutron_star.vx += (dx / distance) * force * delta_time
                    neutron_star.vy += (dy / distance) * force * delta_time
                    energy_budget -= force * delta_time * 0.01

        # Update consumed_mass to reflect energy spent
        state.black_hole_pulses[i][3] = max(0, energy_budget)

        cx, cy = ring.center
        pulse_fade = max(0.0, 1.0 - new_radius / ring.rest_radius)
        for bi in range(ring.num_points):
            bx = cx + ring.radii[bi] * math.cos(ring.angles[bi])
            by = cy + ring.radii[bi] * math.sin(ring.angles[bi])
            dist_to_pulse = math.hypot(bx - x, by - y)
            if abs(dist_to_pulse - new_radius) < NEUTRON_STAR_RIPPLE_EFFECT_WIDTH * 4:
                ring.flash[bi] = max(ring.flash[bi], pulse_fade * 0.9)
                ring.radii_vel[bi] += BARRIER_WAVE_PUSH * 2.0 * mass_scale * pulse_fade * delta_time

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
        black_hole.attract(state, delta_time, mc_to_remove, ns_to_remove, bh_to_remove)
        black_hole.decay(delta_time)
        # Jet streams: emit H/He/O clouds over time
        jets_done = []
        for ji, jet in enumerate(black_hole.jet_streams):
            jet[0] -= delta_time
            if jet[0] <= 0 or jet[1] <= 0:
                jets_done.append(ji)
                continue
            emit_interval = BH_JET_DURATION / BH_JET_STAR_COUNT
            if jet[0] % emit_interval < delta_time:
                jet[1] -= 1
                angle = jet[2]
                offset_dist = random.uniform(5, BH_JET_SPREAD)
                ex = black_hole.x + offset_dist * math.cos(angle)
                ey = black_hole.y + offset_dist * math.sin(angle)
                mass = random.uniform(MOLECULAR_CLOUD_START_MASS, PROTOSTAR_THRESHOLD * 0.35)
                size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                child = MolecularCloud(ex, ey, size, mass, SEED_ELEMENTAL_ABUNDANCE)
                child.vx = math.cos(angle) * BH_JET_VELOCITY
                child.vy = math.sin(angle) * BH_JET_VELOCITY
                new_clouds.append(child)
        for ji in sorted(jets_done, reverse=True):
            black_hole.jet_streams.pop(ji)
        if black_hole.mass > BLACK_HOLE_DECAY_THRESHOLD and random.random() < BH_EMISSION_CHANCE:
            leak_mass = random.uniform(BH_EMISSION_MASS_MIN, BH_EMISSION_MASS_MAX)
            leak_mass = min(leak_mass, black_hole.mass - BLACK_HOLE_DECAY_THRESHOLD)
            if leak_mass > 0:
                black_hole.mass -= leak_mass
                offset_angle = random.uniform(0, 2 * math.pi)
                offset_dist = random.uniform(3, BH_EMISSION_EJECTA_SPREAD)
                ex = black_hole.x + offset_dist * math.cos(offset_angle)
                ey = black_hole.y + offset_dist * math.sin(offset_angle)
                size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((leak_mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                child = MolecularCloud(ex, ey, size, leak_mass, SEED_ELEMENTAL_ABUNDANCE)
                child.vx = math.cos(offset_angle) * BH_EMISSION_VELOCITY
                child.vy = math.sin(offset_angle) * BH_EMISSION_VELOCITY
                new_clouds.append(child)
        if black_hole.mass <= BLACK_HOLE_DECAY_THRESHOLD:
            bh_to_remove.add(black_hole)
            for _ in range(BH_DECAY_CLOUD_COUNT):
                offset_angle = random.uniform(0, 2 * math.pi)
                offset_dist = random.uniform(5, BH_DECAY_EJECTA_SPREAD)
                ex = black_hole.x + offset_dist * math.cos(offset_angle)
                ey = black_hole.y + offset_dist * math.sin(offset_angle)
                mass = random.uniform(BH_DECAY_CLOUD_MASS_MIN, BH_DECAY_CLOUD_MASS_MAX)
                size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                child = MolecularCloud(ex, ey, size, mass, BH_DECAY_ELEMENTAL_ABUNDANCE)
                child.vx = math.cos(offset_angle) * offset_dist * 0.5
                child.vy = math.sin(offset_angle) * offset_dist * 0.5
                new_clouds.append(child)

    state.spatial_hash.clear()
    state.spatial_hash.bulk_insert(state.molecular_clouds)

    for neutron_star in state.neutron_stars:
        if neutron_star in ns_to_remove:
            continue
        neutron_star.apply_gravity(state, delta_time)
        neutron_star.update_pulse(state, ring, delta_time)
        neutron_star.decay(delta_time)
        if neutron_star.mass <= NEUTRON_STAR_DECAY_THRESHOLD:
            ns_to_remove.add(neutron_star)
            for _ in range(NS_DECAY_CLOUD_COUNT):
                offset_angle = random.uniform(0, 2 * math.pi)
                offset_dist = random.uniform(5, NS_DECAY_EJECTA_SPREAD)
                ex = neutron_star.x + offset_dist * math.cos(offset_angle)
                ey = neutron_star.y + offset_dist * math.sin(offset_angle)
                mass = random.uniform(NS_DECAY_CLOUD_MASS_MIN, NS_DECAY_CLOUD_MASS_MAX)
                size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                child = MolecularCloud(ex, ey, size, mass, EJECTA_ELEMENTAL_ABUNDANCE)
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
                    mass = random.uniform(MOLECULAR_CLOUD_START_MASS, PROTOSTAR_THRESHOLD * 0.35)
                    size = max(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))
                    child = MolecularCloud(ex, ey, size, mass, KILONOVA_ELEMENTAL_ABUNDANCE)
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



def _clip_pulse_points(origin_x, origin_y, pulse_radius, ring, all_pulses, num_pts=64, offset_x=0, offset_y=0):
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
            if dist_from_center > barrier_r - 4:
                px = cx + (barrier_r - 4) * math.cos(barrier_angle)
                py = cy + (barrier_r - 4) * math.sin(barrier_angle)

        points.append((int(px), int(py)))
    return points


def draw_simulation(screen, ring, state, offset_x=0, offset_y=0):
    ring.draw(screen, offset_x, offset_y)

    for molecular_cloud in state.molecular_clouds:
        molecular_cloud.draw(screen, offset_x, offset_y)

    all_pulses = []
    for ns in state.neutron_stars:
        for pulse in ns.active_pulses:
            all_pulses.append((ns.x + offset_x, ns.y + offset_y, pulse[0], pulse[2]))
    for pulse in state.black_hole_pulses:
        all_pulses.append((pulse[0] + offset_x, pulse[1] + offset_y, pulse[2], 1.0))

    for pulse in state.black_hole_pulses:
        x, y, pulse_radius, consumed_mass = pulse
        if pulse_radius > 1:
            draw_x = x + offset_x
            draw_y = y + offset_y
            pulse_width = max(2, int(consumed_mass / 20))
            points = _clip_pulse_points(draw_x, draw_y, pulse_radius, ring, all_pulses, offset_x=offset_x, offset_y=offset_y)
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
        black_hole.draw(screen, offset_x, offset_y)

    for neutron_star in state.neutron_stars:
        neutron_star.draw(screen, ring, all_pulses, offset_x, offset_y)


def format_year_display(current_year):
    if current_year >= 1_000_000:
        return "TIME(YEARS): \u221e"
    elif current_year >= 1_000:
        return f"TIME(YEARS): {current_year / 1_000:.1f}B"
    else:
        return f"TIME(YEARS): {int(current_year)}M"


def draw_ui(screen, font, current_year, zoom=1.0):
    draw_static_key(screen, font, zoom)

    year_text = font.render(format_year_display(current_year), True, LABEL_COLOR)
    screen.blit(year_text, (30, SCREEN_HEIGHT - 40 ))


def run_simulation(screen, font, state, ring):
    try:
        running = True
        clock = pygame.time.Clock()
        current_year = 0.0
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
            delta_time = min(delta_time, MAX_DELTA_TIME)
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
                current_year = 0.0
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

            current_year += delta_time * YEAR_RATE

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
    ring = Barrier((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), (BARRIER_INITIAL_SIZE, BARRIER_INITIAL_SIZE), BARRIER_POINT_COUNT)

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
        molecular_cloud = MolecularCloud(x, y, MOLECULAR_CLOUD_START_SIZE, MOLECULAR_CLOUD_START_MASS, SEED_ELEMENTAL_ABUNDANCE)
        state.molecular_clouds.append(molecular_cloud)

    return state, ring


def main():
    pygame.init()
    pygame.display.set_caption("A long time ago in a universe far, far away...")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    font = pygame.font.SysFont('Monospace', 14)
    print("Populating space with molecular clouds")
    state, ring = initialize_state()

    print("Starting simulation")
    run_simulation(screen, font, state, ring)

if __name__ == "__main__":
    main()
