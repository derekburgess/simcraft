"""All simulation tuning constants. Values are load-bearing: the black-hole/galaxy behavior was
tuned as a system (see README + comments) — change dials here, not formulas in the physics code."""
import os

# ── Display ──
BACKGROUND_COLOR = (0, 10, 20) # RGB background color (dark blue-black, like space).

SCREEN_WIDTH = 1920             # Display width in pixels. Change to match your monitor.
SCREEN_HEIGHT = 1080             # Display height in pixels. Change to match your monitor.

# ── UI ──
LABEL_COLOR = (60, 60, 200)    # RGB color for UI text labels.

UI_LABEL_X = 30                 # X position (pixels from left) for all HUD text labels.
UI_STATS_Y = 30                 # Y position (pixels from top) for the stats readout (FPS/universes/entities/RNG).
UI_STATS_LINE_SPACING = 22      # Vertical spacing between stats readout lines.
UI_STATS_FONT = 'notosans'      # Sans-serif font for the stats readout.
UI_STATS_FONT_SIZE = 14         # Point size for the stats readout font.
UI_STATS_COLOR = (110, 110, 245)  # Stats readout text color — brighter than LABEL_COLOR for contrast on the dark background.
UI_ZOOM_Y_OFFSET = 140          # Y offset from bottom of screen for the zoom label.
UI_EXIT_Y_OFFSET = 110          # Y offset from bottom of screen for the exit/quit label.
UI_TEXT_Y_OFFSET = 40           # Y offset from bottom of screen for the year counter display.

# ── Zoom ──
ZOOM_MIN = 0.5                 # Minimum zoom level (zoomed out). Lower = can see more.
ZOOM_MAX = 2.0                 # Maximum zoom level (zoomed in). Higher = can zoom in more.
ZOOM_STEP = 0.25               # Zoom change per scroll wheel tick.

# ── Simulation ──
SPATIAL_HASH_CELL_SIZE = 40     # Cell size (pixels) for the local-gravity neighborhood grid. Should match typical entity interaction radius.

# ── Cloud/star gravity backends ──
# All backends compute the SAME force formula (tiered grav_mass, softening); they differ only in
# speed and (for Barnes-Hut) approximation. Dispatch: GPU if available → Barnes-Hut → numpy brute.
GPU_GRAVITY_ENABLED = True      # Use the Taichi GPU kernel for cloud/star gravity when available (exact all-pairs). Falls back to Barnes-Hut/brute on CPU if Taichi/GPU is unavailable.
BARNES_HUT_ENABLED = True       # Toggle the Barnes-Hut CPU backend (compiled quadtree, approximate long-range). False = numpy brute-force fallback.
BARNES_HUT_THETA = 0.7          # Opening angle. Lower = more accurate & slower (0 = brute force O(N^2)).
BARNES_HUT_SOFTENING = 2.0      # Softening length (pixels) added to the force denominator to prevent close-range spikes.
BARNES_HUT_MAX_DEPTH = 28       # Max quadtree depth. Caps recursion when many clouds share near-identical positions.

# ── Timing ──
YEAR_RATE = 60                 # Simulated years per real second. Higher = faster time progression in the UI counter.
MAX_DELTA_TIME = 0.05          # Maximum physics time step per frame (seconds). Caps dt to prevent instability on lag spikes.
HEAT_DEATH_LINGER_DURATION = 12.0  # Seconds to display the empty ring after all matter is gone before starting a new universe.
TARGET_FPS = 60                    # Target frame rate cap for the simulation loop.

# ── Physics ──
GRAVITY_SCALE = 0.15  # Master gravity multiplier applied to all gravitational constants. Increase for stronger gravity everywhere.
VELOCITY_DAMPING = 0.999        # Per-frame velocity multiplier for all entities. Below 1.0 = energy dissipation. 1.0 = no damping.

# ── CMB Perturbations (initial conditions, inspired by real cosmic microwave background) ──
# These control how the universe looks at the very start of the simulation.
# The barrier ring isn't a perfect circle — it's warped by Fourier perturbations,
# and clouds spawn denser in the "dented" regions, seeding the clumps that
# eventually collapse into stars and black holes. Set all to 0 for a perfectly
# uniform start (boring). Crank them up for wild, lumpy initial conditions.
CMB_PERTURBATION_MODES = 18     # Number of sine-wave modes layered onto the barrier shape. 1 = simple oval,
                                # 6 = complex bumpy ring, 20+ = very jagged. Each higher mode adds finer detail.
CMB_PERTURBATION_SCALE = 0.4  # Amplitude of each mode (as a fraction of barrier radius). 0 = perfect circle,
                                # 0.08 = subtle bumps (~8%), 0.3+ = dramatic deformations.
CMB_DENSITY_CONTRAST = 0.8     # How strongly barrier shape biases initial cloud placement. 0 = clouds spread
                                # evenly regardless of barrier shape, 0.6 = noticeably clumpy, 1.0 = extreme
                                # clustering in dented regions (can leave large voids elsewhere).

# ── Barrier (cosmic boundary ring) ──
BARRIER_POINT_COUNT = 240       # Number of vertices defining the barrier ring. More = smoother circle, but slower (drawing + deformation + contact all scale with this, per universe).
MOLECULAR_CLOUD_MAX_PER_UNIVERSE = 800  # Hard cap on clouds in a single universe. Bounds per-frame physics AND rendering cost so the sim doesn't degrade as matter regenerates. Excess (lowest-mass) clouds are trimmed.
MULTIVERSE_MAX_CLOUDS = 10000   # Hard cap on total clouds across ALL universes — bounds the whole frame regardless of how many universes spawn. Lowest-mass clouds are trimmed globally.
BARRIER_INITIAL_SIZE = 32      # Starting diameter of the barrier ring in pixels.
BARRIER_GRAVITY_CONSTANT = 70 * GRAVITY_SCALE  # Base gravitational pull of the barrier on entities. Reduced so it contains without out-competing black holes for nearby clumping.
BARRIER_COLOR = (30, 60, 220)   # RGB color of the barrier ring at rest.
BARRIER_BASE_OPACITY = 150      # Transparency of the barrier at rest (0=invisible, 255=opaque).
BARRIER_FLASH_COLOR = (0, 184, 106)  # RGB color the barrier flashes when deformed (green).
BARRIER_FLASH_OPACITY = 255     # Peak opacity during a barrier flash (0-255).
BARRIER_FLASH_DECAY = 4      # How fast barrier flashes fade per second. Higher = faster fade.
BARRIER_WAVE_PUSH = 400      # Force magnitude when pulses hit the barrier. Higher = more barrier wobble.
BARRIER_DAMPING = 0.04          # Damping factor for barrier deformation velocity. Lower = more oscillation.
BARRIER_TENSION = 2.5           # Membrane tension: per second, each barrier vertex relaxes this strongly toward its neighbours' average radius. Keeps the ring smooth (no spikes/web) — but too high erases contact dents, so kept moderate. 0 = no smoothing.
BARRIER_DEFORM_THRESHOLD = 0.1  # Minimum radius change (pixels) to trigger a flash effect.
BARRIER_HEAVY_MASS_THRESHOLD = 100  # Combined mass near a barrier section that weakens containment. Higher = harder to break out.
BARRIER_SMOOTHING_PASSES = 3    # Number of smoothing iterations when drawing the barrier. More = smoother shape.
BARRIER_SMOOTHING_WINDOW = 5    # Window size for the smoothing algorithm (must be odd). Larger = smoother but less detail.
BARRIER_DEFORMATION_PROXIMITY_FACTOR = 0.3  # Fraction of rest radius used as proximity threshold for deformation accumulation.
BARRIER_SECTION_SEARCH_RANGE = 3  # Angular step multiplier when searching for nearby compact objects at a barrier section.
BARRIER_LINE_WIDTH = 3          # Line width (pixels) for drawing the barrier ring polygon and flash segments.

# ── Barrier Interaction (how different entities interact with the barrier) ──
MOLECULAR_CLOUD_BARRIER_GRAVITY_FACTOR = 0.001  # Gravity multiplier for clouds vs barrier. Very weak — clouds drift inward gently.
MOLECULAR_CLOUD_BARRIER_DEFORM_FACTOR = 6     # How strongly massive clouds dent the barrier on approach.

STAR_BARRIER_GRAVITY_FACTOR = 0.005    # Gravity multiplier for ignited stars vs barrier. Stronger than clouds.
STAR_BARRIER_DEFORM_FACTOR = 10        # How strongly stars dent the barrier on approach.

BLACK_HOLE_BARRIER_GRAVITY_FACTOR = 0.025  # Gravity multiplier for black holes vs barrier (the only thing the barrier attracts). Gentle so holes stay central and their disks don't overhang the barrier edge (overhanging clouds get pinned to the edge by enforce()).
BLACK_HOLE_BARRIER_DEFORM_FACTOR = 40    # How strongly black holes dent the barrier.
BLACK_HOLE_BARRIER_WEAKENING_FACTOR = 0.01  # How much nearby mass weakens containment for black holes. Higher = escapes more easily.
BLACK_HOLE_BARRIER_PUSH_STRENGTH = 10    # Base push force applied to black holes hitting the barrier boundary.

NEUTRON_STAR_BARRIER_GRAVITY_FACTOR = 0.001   # Gravity multiplier for neutron stars vs barrier. Strongest pull.
NEUTRON_STAR_BARRIER_DEFORM_FACTOR = 10     # How strongly neutron stars dent the barrier.
NEUTRON_STAR_BARRIER_WEAKENING_FACTOR = 0.7  # How much nearby mass weakens containment for neutron stars (0=no effect, 1=full escape).
NEUTRON_STAR_BARRIER_PUSH_STRENGTH = 6   # Base push force applied to neutron stars hitting the barrier boundary.

BARRIER_CONTAINMENT_THRESHOLD = 0.05  # Minimum containment strength below which the barrier stops pushing an entity back.

# ── Molecular Clouds ──
MOLECULAR_CLOUD_COUNT = 1800    # Number of clouds spawned at simulation start. More = denser universe, slower performance.
MOLECULAR_CLOUD_START_SIZE = 20 # Initial visual size of clouds in pixels.
MOLECULAR_CLOUD_MIN_SIZE = 6    # Smallest a cloud can shrink to as it gains mass.
MOLECULAR_CLOUD_GROWTH_RATE = 0.06  # How fast clouds visually shrink as they gain mass. Higher = shrinks faster.
MOLECULAR_CLOUD_START_MASS = 1  # Initial mass of each cloud.
MOLECULAR_CLOUD_GRAVITY_CONSTANT = 0.0015 * GRAVITY_SCALE  # Base gravitational attraction for the diffuse cloud/star field. Weak: clouds barely self-organize — they condense onto denser objects (stars, black holes).
STAR_GRAVITY_MULTIPLIER = 5.0   # Extra gravitational "charge" a star carries beyond its raw mass, making it a moderate condensation seed (a distinct tier between weak clouds and strong black holes).
MOLECULAR_CLOUD_MERGE_CHANCE = 0.12  # Probability (0-1) of two colliding clouds merging per frame. Higher = faster merging.
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

# ── Molecular Cloud Emission (clouds shed daughter clouds) ──
MOLECULAR_CLOUD_EMISSION_CHANCE = 0.2         # Per-frame chance for eligible clouds to emit
MOLECULAR_CLOUD_EMISSION_MIN_PARENT_MASS = 1     # Minimum parent mass to emit
MOLECULAR_CLOUD_EMISSION_MASS_MIN = 1            # Min mass of emitted cloud
MOLECULAR_CLOUD_EMISSION_MASS_MAX = 4            # Max mass of emitted cloud
MOLECULAR_CLOUD_EMISSION_VELOCITY = 0.6         # Emission kick speed
MOLECULAR_CLOUD_EMISSION_SPREAD = 14              # Max spawn distance from parent
MOLECULAR_CLOUD_EMISSION_COUNT = 10               # Max number of emissions per cloud

# ── Supernova (molecular cloud reset events) ──
MOLECULAR_CLOUD_DEFAULT_STATE_CHANCE = 0.01    # Per-frame chance a massive star resets to gas cloud, ejecting material (supernova-like event).
MOLECULAR_CLOUD_EJECTA_HEAVIER_ELEMENT_CHANCE = 0.07  # Probability that ejecta from supernovae produce heavier elements than the parent.
SUPERNOVA_EJECTA_COUNT_HIGH = 2   # Number of ejecta pieces from a high-tier (heavy element) supernova.
SUPERNOVA_EJECTA_COUNT_MEDIUM = 6 # Number of ejecta pieces from a medium-tier supernova.
SUPERNOVA_EJECTA_COUNT_LOW = 20    # Number of ejecta pieces from a low-tier (light element) supernova.
SUPERNOVA_EJECTA_SPREAD_HIGH = 14  # Max spawn radius (pixels) of ejecta from a high-tier supernova.
SUPERNOVA_EJECTA_SPREAD_MEDIUM = 20  # Max spawn radius (pixels) of ejecta from a medium-tier supernova.
SUPERNOVA_EJECTA_SPREAD_LOW = 26   # Max spawn radius (pixels) of ejecta from a low-tier supernova.
SUPERNOVA_EJECTA_MAX_MASS_FRACTION = 0.35    # Maximum ejecta mass as a fraction of PROTOSTAR_THRESHOLD.

# ── Protostars (clouds that reach enough mass to ignite) ──
PROTOSTAR_THRESHOLD = 28        # Mass at which a cloud becomes a protostar (changes appearance and behavior).
PROTOSTAR_EJECTA_COUNT = 4     # Number of ejecta pieces produced during protostar formation events.
PROTOSTAR_EJECTA_SPREAD = 14    # Max spawn distance (pixels) of ejecta from the parent star.

# Element weight boundaries for star tiers.
# When a cloud reaches PROTOSTAR_THRESHOLD mass, its element_index (position in
# MOLECULAR_CLOUD_START_COLORS above) determines which tier of star it becomes:
#   Index 0-2  (H, He, O)                   → LOW tier  — small white star
#   Index 3-9  (C, Ne, N, Fe, Si, Au, S)               → MEDIUM tier — mid-size yellow-green star
#   Index 10-19 (Mg, P, Li, Pt, Co, Ca, Na, Ni, Cr, Ti) → HIGH tier — large red giant
# Lowering these values makes heavier stars more common; raising them makes them rarer.
PROTOSTAR_ELEMENT_WEIGHT_MEDIUM = 3   # Element index at or above which a star becomes medium tier.
PROTOSTAR_ELEMENT_WEIGHT_HEAVY = 10   # Element index at or above which a star becomes a red giant (high tier).

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
PROTOSTAR_RED_GIANT_BLACK_HOLE_CHANCE = 0.001

# ── Black Holes ──
BLACK_HOLE_THRESHOLD = 42       # Mass above which a star can collapse into a black hole.
BLACK_HOLE_CHANCE = 0.0001      # Per-frame probability a qualifying star becomes a black hole. Very rare.
BLACK_HOLE_MAX_COUNT = 5        # Hard cap on coexisting black holes. Keeps holes sparse (so disks can swirl without being flung) while leaving formation frequent enough to drive the cloud matter cycle. Stars that would collapse past the cap stay stars (and supernova instead).

# ── Multiverse (each black-hole birth opens a new universe outside the current ones) ──
UNIVERSE_MAX_COUNT = max(2, os.cpu_count() or 4)  # Cap coexisting universes at the machine's core count — one core per universe when stepped in parallel.
BLACK_HOLE_RIP_MASS_FACTOR = 0.9  # Fraction of max mass a hole must reach to "rip" open a new universe. <1 because decay keeps holes hovering just under the hard cap.
UNIVERSE_RIP_TRANSFER_FRACTION = 0.4  # Fraction of the source universe's clouds pulled through into a newly ripped universe (instead of spawning fresh matter). Keeps total entity count bounded.
UNIVERSE_STREAM_FRACTION = 0.6  # After ripping, chance each cloud the hole accretes is streamed into its child universe (wormhole) instead of being consumed. 0 = one-time transfer only; 1 = everything it eats flows through.
UNIVERSE_SPAWN_GAP = 20         # Minimum gap (pixels) between a newly spawned barrier and existing ones; also the clearance kept between barriers by repulsion. Small = universes cluster close together.
BARRIER_REPULSION_RATE = 15.0   # Per-second rate at which overlapping universes are separated/flattened. Higher = firmer (less overlap).
BARRIER_RESOLVE_ITERATIONS = 4  # Relaxation passes per frame for barrier contact. More = better convergence when many universes are packed together (prevents residual overlap).
BARRIER_CONTACT_DEFORM = 1.0    # How strongly barriers flatten each other where they press together — the primary no-overlap mechanism at contact. Higher = deeper flattening.
BARRIER_SEPARATION_SHARE = 0.15  # Of the penetration when two barriers press, this fraction is resolved by pushing them apart; the rest by flattening (denting) the contact faces. Low = balloon-like (they stay in contact and visibly flatten rather than shoving apart).
MULTIVERSE_RENDER_MAX = 5000    # Max pixels per side of the off-screen surface used to draw the whole multiverse before scaling to the window.
UNIVERSE_CULL_MARGIN = 100      # Extra pixels beyond a universe's barrier radius still treated as on-view when culling off-screen universes from rendering (covers entities/pulses that momentarily poke past the barrier).
BLACK_HOLE_RADIUS = 14           # Visual radius divisor — smaller value = larger drawn black hole (mass / this). Shrinks the drawn disk and event horizon without changing gravitational mass.
BLACK_HOLE_MAX_MASS = 115       # Maximum mass a black hole can accumulate. Capped lower so no single hole grows into an overwhelming dominant one.
BLACK_HOLE_GRAVITY_CONSTANT = 30 * GRAVITY_SCALE  # Gravitational pull strength. Much higher than clouds; raised so disk clouds orbit faster (more visible swirl) and bind tighter.
BLACK_HOLE_GROWTH_RATE = 1      # Maximum mass gained per second from the accretion buffer. Must stay below minimum decay rate (~1.23/sec at max mass) so BHs always net-decay.
BLACK_HOLE_DECAY_RATE = 50    # Mass lost per second AT the evaporation threshold (Hawking radiation analog). Actual rate scales as rate*(threshold/mass)^2 — large BHs decay far slower.
BLACK_HOLE_DECAY_THRESHOLD = 8  # Mass at which a black hole evaporates and releases ejecta.
BLACK_HOLE_GRAVITY_SOFTENING = 3     # Softening length (pixels) added to BH gravity denominator. Lower = steeper well = sharper slingshots, but less stable. Prevents catastrophic close-range force spikes.
# The event horizon (where matter is actually consumed) is decoupled from the drawn disk
# (border_radius). Making it a fraction of the visual radius leaves an annulus where clouds
# can swing close, get flung by the steep gravity well, and orbit instead of vanishing on touch.
BLACK_HOLE_EVENT_HORIZON_FACTOR = 0.4  # Consume radius as a fraction of the visual radius. Lower = more slingshots/orbits, less consumption.
BLACK_HOLE_MIN_CAPTURE_RADIUS = 2      # Absolute floor (pixels) for the consume radius so small black holes still capture and fast entities can't tunnel through.
# Frame-dragging swirl: near a hole, each cloud's velocity vector is gently rotated, curving
# straight infall into a rotating accretion disk. Rotation conserves speed (no energy is added),
# so the swirl can't blow up. Direction follows the hole's spin (angular_momentum).
BLACK_HOLE_SWIRL_RATE = 5.0            # Relaxation rate (per second) at which disk clouds are driven toward circular-orbit speed; fades to 0 at the swirl radius. Higher = stronger/faster swirl.
BLACK_HOLE_SWIRL_RADIUS = 140         # Disk radius (pixels) at the reference mass below. Scales with hole mass, so a massive hole organizes/swirls entities from much farther out than a small one.
BLACK_HOLE_SWIRL_REFERENCE_MASS = 100  # Hole mass at which the disk radius equals BLACK_HOLE_SWIRL_RADIUS. A 2x-mass hole reaches 2x as far.
# Dynamical friction: a massive hole plowing through the cloud sea is gravitationally braked.
# Modeled as strong extra velocity damping (per second) so holes act as near-stationary anchors
# instead of being dragged along by accretion and bulk flows. 1.0 = no extra braking.
BLACK_HOLE_VELOCITY_DAMPING = 0.15    # Per-second velocity retention for black holes. Strong anchor so a hole drifts SLOWER than its disk rotates — otherwise the disk smears into a comet instead of a visible swirl. Higher = roams more (smears the swirl).
BLACK_HOLE_COLOR = (0,0,0)      # RGB fill color of the black hole (black).
BLACK_HOLE_BORDER_COLOR = (100, 0, 0)  # RGB color of the event horizon ring (dark red).
BLACK_HOLE_MERGE_COLOR = (0, 60, 180, 200)  # RGBA color of the gravitational wave pulse from BH mergers.
BLACK_HOLE_DISK_COLOR = (255, 100, 100)    # RGB color of the accretion disk tracer dot (light red).
BLACK_HOLE_DISK_SIZE = 1                   # Visual size in pixels of the accretion disk tracer.
BLACK_HOLE_DISK_ROTATION = 10            # Base rotation speed (rad/s) of the accretion disk tracer. Spin adds to this.
BLACK_HOLE_ANGULAR_MOMENTUM_DISSIPATION = 0.999  # Per-second dissipation rate for black hole angular momentum (spin-down).
BLACK_HOLE_PULSE_SPEED_MULTIPLIER = 1.5  # Speed multiplier applied to BH merger pulses relative to NS ripple speed.
BLACK_HOLE_PULSE_MASS_SCALE = 3.5      # Divisor for consumed mass when scaling merger pulse force on the BARRIER. Lower = stronger barrier ripple on a merger.
BLACK_HOLE_PULSE_ENTITY_FACTOR = 0.3   # Extra multiplier applied to the pulse's push on ENTITIES (clouds/holes/neutron stars) only, not the barrier. <1 so the wave wobbles the barrier strongly but doesn't blast galaxies apart.

# ── Black Hole Decay (when BH evaporates) ──
BLACK_HOLE_DECAY_CLOUD_COUNT = 6       # Number of heavy clouds spawned when a BH evaporates.
BLACK_HOLE_DECAY_CLOUD_MASS_MIN = 24   # Minimum mass of each decay cloud. These are heavy!
BLACK_HOLE_DECAY_CLOUD_MASS_MAX = 28   # Maximum mass of each decay cloud.
BLACK_HOLE_DECAY_EJECTA_SPREAD = 20    # Max spawn distance (pixels) of decay ejecta from the BH.

# ── Neutron Stars ──
NEUTRON_STAR_CHANCE = 0.6      # Probability of becoming a neutron star instead of a black hole on collapse.
NEUTRON_STAR_RADIUS = 1         # Visual radius in pixels (tiny, as expected).
NEUTRON_STAR_GRAVITY_CONSTANT = 2 * GRAVITY_SCALE  # Gravitational pull strength. Moderate — between clouds and BHs.
NEUTRON_STAR_DECAY_RATE = 2   # Mass lost per second. Higher = shorter lifespan.
NEUTRON_STAR_DECAY_THRESHOLD = 0.8  # Mass at which a neutron star dissipates into ejecta.
NEUTRON_STAR_COLOR = (0, 120, 255)  # RGB color of the neutron star (cyan-blue).
NEUTRON_STAR_PULSE_RATE = 0.015  # Seconds between pulsar pulses. Lower = faster pulsing.
NEUTRON_STAR_PULSE_STRENGTH = 7 # Force magnitude of each pulse ripple. Higher = stronger push on nearby entities.
NEUTRON_STAR_PULSE_COLOR = (0, 140, 255, 245)  # RGBA color of the expanding pulse ring.
NEUTRON_STAR_PULSE_WIDTH = 2    # Line width (pixels) for drawing pulse rings.
NEUTRON_STAR_RIPPLE_SPEED = 64  # How fast (pixels/sec) pulse ripples expand outward.
NEUTRON_STAR_RIPPLE_EFFECT_WIDTH = 24  # Width (pixels) of the zone where ripples exert force on entities.
NEUTRON_STAR_PULSE_MASS_BOOST = 0.02      # Mass cost per unit of pulse force. Pulsing drains the neutron star.
NEUTRON_STAR_PULSE_COLOR_DURATION = 0.1  # Seconds the neutron star flashes white after each pulse.
NEUTRON_STAR_PULSE_FADE_RATE = 1.5  # Rate multiplier for pulse fade once the wavefront reaches the barrier.

# ── Kilonova (neutron star merger) ──
KILONOVA_EJECTA_COUNT = 20      # Number of ejecta pieces from a NS-NS collision. Rich in heavy elements.
KILONOVA_COLLISION_DISTANCE = 6 # Distance (pixels) at which two neutron stars merge.
KILONOVA_EJECTA_SPREAD = 40     # Max spawn distance (pixels) of kilonova ejecta. Large explosion!

# ── Pulse Rendering ──
PULSE_RENDER_POINT_COUNT = 64   # Number of polygon vertices used to draw each pulse ring.
PULSE_RENDER_MARGIN = 2         # Pixel margin added around pulse bounding boxes when allocating draw surfaces.
PULSE_COLLISION_FADE_RATE = 4 # Rate at which overlapping pulse wavefronts fade each other out.
PULSE_BARRIER_CLIP_MARGIN = 4   # Pixels inside the barrier edge where pulse ring points are clipped.

# ── Elemental abundance tables (cumulative probability ranges over the 20 elements above) ──
SEED_ELEMENTAL_ABUNDANCE = [
    (0, 0.75),        # Hydrogen range: 0-75%
    (0.75, 0.98),     # Helium range: 75-98%
    (0.98, 1.0),      # Oxygen range: 98-100%
]

ELEMENTAL_ABUNDANCE = [
    (0, 0.35),        # Hydrogen range: 0-35%     } LOW  ~60%
    (0.35, 0.55),     # Helium range: 35-55%      }
    (0.55, 0.60),     # Oxygen range: 55-60%      }
    (0.60, 0.64),     # Carbon range: 60-64%      } MEDIUM ~30%
    (0.64, 0.68),     # Neon range: 64-68%        }
    (0.68, 0.72),     # Nitrogen range: 68-72%    }
    (0.72, 0.77),     # Iron range: 72-77%        }
    (0.77, 0.81),     # Silicon range: 77-81%     }
    (0.81, 0.85),     # Gold range: 81-85%        }
    (0.85, 0.90),     # Sulfur range: 85-90%      }
    (0.90, 0.91),     # Magnesium range: 90-91%   } HIGH ~10%
    (0.91, 0.92),     # Phosphorus range: 91-92%  }
    (0.92, 0.93),     # Lithium range: 92-93%     }
    (0.93, 0.94),     # Platinum range: 93-94%    }
    (0.94, 0.95),     # Cobalt range: 94-95%      }
    (0.95, 0.96),     # Calcium range: 95-96%     }
    (0.96, 0.97),     # Sodium range: 96-97%      }
    (0.97, 0.98),     # Nickel range: 97-98%      }
    (0.98, 0.99),     # Chromium range: 98-99%    }
    (0.99, 1.0),      # Titanium range: 99-100%   }
]

EJECTA_ELEMENTAL_ABUNDANCE = [
    (0, 0.65),     # Hydrogen range: 0-65%
    (0.65, 0.88),  # Helium range: 65-88%
    (0.88, 0.93),  # Oxygen range: 88-93%
    (0.93, 0.95),  # Carbon range: 93-95%
    (0.95, 0.95),  # Neon - not produced in stellar ejecta
    (0.95, 0.95),  # Nitrogen - not produced in stellar ejecta
    (0.95, 0.97),  # Iron range: 95-97%
    (0.97, 0.98),  # Silicon range: 97-98%
    (0.98, 0.985), # Gold range: 98-98.5%
    (0.985, 0.99), # Sulfur range: 98.5-99%
    (0.99, 0.993), # Magnesium range: 99-99.3%
    (0.993, 0.995),# Phosphorus range: 99.3-99.5%
    (0.995, 0.995),# Lithium - not produced in supernovae
    (0.995, 0.996),# Platinum range: 99.5-99.6%
    (0.996, 0.997),# Cobalt range: 99.6-99.7%
    (0.997, 0.998),# Calcium range: 99.7-99.8%
    (0.998, 0.999),# Sodium range: 99.8-99.9%
    (0.999, 0.9994),# Nickel range: 99.9-99.94%
    (0.9994, 0.9997),# Chromium range: 99.94-99.97%
    (0.9997, 1.0), # Titanium range: 99.97-100%
]

BLACK_HOLE_DECAY_ELEMENTAL_ABUNDANCE = [
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
