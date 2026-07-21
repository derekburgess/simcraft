"""All simulation tuning constants. Values are load-bearing: the black-hole/galaxy behavior was
tuned as a system (see README + comments) — change dials here, not formulas in the physics code."""
import os

# ── Display ──
BACKGROUND_COLOR = (0, 10, 20) # RGB background color (dark blue-black, like space).

SCREEN_WIDTH = 1920             # Initial window width in pixels; rendering follows the live window size. Also anchors the world spawn center.
SCREEN_HEIGHT = 1080             # Initial window height in pixels; rendering follows the live window size.

# ── UI ──
LABEL_COLOR = (60, 60, 200)    # RGB color for UI text labels.

UI_LABEL_X = 30                 # X position (pixels from left) for all HUD text labels.
UI_STATS_FONT = 'notosans'      # Sans-serif font for the stats readout.
UI_STATS_FONT_SIZE = 14         # Point size for the stats readout table cells.
UI_STATS_RNG_FONT_SIZE = 24     # Point size for the RNG output cell — larger than the rest of the row.
UI_STATS_COLOR = (110, 110, 245)  # Stats readout text color — brighter than LABEL_COLOR for contrast on the dark background.
UI_STATS_GRID_COLOR = (60, 60, 140)  # Stats table cell-separator color — dimmer than the text.
UI_STATS_BOTTOM_MARGIN = 24     # Gap (pixels) between the stats table row and the bottom of the screen.
UI_STATS_CELL_PAD_X = 14        # Horizontal padding inside each stats table cell.
UI_STATS_CELL_PAD_Y = 6         # Vertical padding inside the stats table row.
UI_ZOOM_Y_OFFSET = 140          # Y offset from bottom of screen for the zoom label.
UI_EXIT_Y_OFFSET = 110          # Y offset from bottom of screen for the exit/quit label.
UI_TEXT_Y_OFFSET = 40           # Y offset from bottom of screen for the year counter display.

# ── Event ticker (readout row of the stats table, drawn directly above the stats row) ──
# Styling (font, colors, padding) comes from the UI_STATS_* constants above so the two rows
# read as one table.
UI_TICKER_MAX_LINES = 3         # Lines the readout cell holds (fixed height).
UI_TICKER_LIFETIME = 7.0        # Seconds an event entry stays visible in the LIVE view before it fades out fully.
UI_TICKER_HISTORY = 60          # Entries kept for mouse-wheel scrollback (each may coalesce many events). Scrolled-back entries show at full brightness regardless of age.

# ── Element inventory row (one block per element currently present, drawn above the ticker) ──
UI_ELEMENTS_FONT_SIZE = 11      # Point size for the element symbol drawn on each block.
UI_ELEMENTS_BLOCK_SIZE = 20     # Side length (pixels) of each element color block (square).
UI_ELEMENTS_BLOCK_GAP = 3       # Horizontal gap (pixels) between adjacent blocks.
UI_ELEMENTS_MARGIN_BOTTOM = 6   # Gap (pixels) between the block row and the ticker panel above it.

# ── Legend (entity + element key, toggled with [L]) ──
UI_LEGEND_FONT_SIZE = 13        # Point size for legend text.
UI_LEGEND_MARGIN = 24           # Gap (pixels) between the legend block and the screen edges.
UI_LEGEND_PAD = 10              # Inner padding (pixels) of the legend panel.
UI_LEGEND_ROW_HEIGHT = 17       # Vertical spacing (pixels) between legend rows.
UI_LEGEND_SWATCH = 10           # Side length (pixels) of the color swatch squares.
UI_LEGEND_BG = (0, 14, 28, 215)  # RGBA panel background (slightly lighter than space, mostly opaque).
UI_LEGEND_TEXT_COLOR = (150, 170, 220)  # Legend text color.
UI_LEGEND_HEADER_COLOR = (110, 110, 245)  # Legend section-header color.

# ── Zoom ──
ZOOM_MIN = 0.5                 # Minimum zoom level (zoomed out). Lower = can see more.
ZOOM_MAX = 2.0                 # Maximum zoom level (zoomed in). Higher = can zoom in more.
ZOOM_STEP_FACTOR = 1.15        # Multiplicative zoom per wheel tick (target *= this). Multiplicative so a tick feels the same at every scale.
ZOOM_SMOOTH_RATE = 10.0        # Per-second exponential ease of the displayed zoom/center toward their targets. Higher = snappier, lower = floatier.

# ── Simulation ──
SPATIAL_HASH_CELL_SIZE = 40     # Cell size (pixels) for the local-gravity neighborhood grid. Should match typical entity interaction radius.

# ── Cloud/star gravity backends ──
# All backends compute the SAME force formula (tiered grav_mass, softening); they differ only in
# speed and (for Barnes-Hut) approximation. Dispatch: GPU if available → Barnes-Hut → numpy brute.
GPU_GRAVITY_ENABLED = True      # Use the Taichi GPU kernel for cloud/star gravity when available (all-pairs, float32 — ~1e-7 error vs the f64 CPU paths). Falls back to Barnes-Hut/brute on CPU if Taichi/GPU is unavailable.
BARNES_HUT_ENABLED = True       # Toggle the Barnes-Hut CPU backend (compiled quadtree, approximate long-range). False = numpy brute-force fallback.
BARNES_HUT_THETA = 0.7          # Opening angle. Lower = more accurate & slower (0 = brute force O(N^2)).
BARNES_HUT_SOFTENING = 2.0      # Softening length (pixels) added to the force denominator to prevent close-range spikes.
BARNES_HUT_MAX_DEPTH = 28       # Max quadtree depth. Caps recursion when many clouds share near-identical positions.

# ── Timing ──
# The cosmic clock is LOGARITHMIC — display only, nothing in the physics reads the year.
# No linear rate can walk the K→M→B→T progression (each suffix spans 1000x the years of the
# last, so linear time either crawls or teleports); instead each factor of 10 in cosmic years
# takes a fixed slice of real time, which is also how cosmology actually talks about deep time
# (log10 "cosmological decades", per the Five Ages of the Universe). Uncapped, that rate has no
# ceiling — it compounds forever, so it never stops feeling like it's speeding up. MAX_YEAR_RATE
# below caps it once it reaches the pace that felt right (right around 1B years: 1K at ~2.7 s,
# 1M at ~27 s, 1B at ~54 s, all unchanged from the pure-exponential curve), after which growth
# is linear at that capped rate instead of continuing to accelerate — so 1T now takes ~67 min
# instead of 81 s, and the heat-death decade (10^100 years) is hours away, not ~14.5 min.
COSMIC_DECADE_SECONDS = 9       # Real seconds per factor-of-10 of cosmic years.
MAX_YEAR_RATE = 2.5e8           # Ceiling (years/sec) on the cosmic clock — growth goes linear past this rate.
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
BARRIER_BASE_OPACITY = 120      # Transparency of the barrier at rest (0=invisible, 255=opaque).
BARRIER_FLASH_COLOR = (0, 184, 106)  # RGB color the barrier flashes when deformed (green).
BARRIER_FLASH_OPACITY = 175     # Peak opacity during a barrier flash (0-255). Below full: during wave storms many segments flash at once, and at 255 the ring strobes.
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
MOLECULAR_CLOUD_BARRIER_DEFORM_FACTOR = 0.3   # How strongly massive clouds dent the barrier on approach. Tuned for the recollapse era: a dead universe packed with evaporation clouds grinds down to its Big Crunch in ~6-7 minutes (at 6 it imploded in seconds). This dial was dead code until BARRIER_DEFORM_CLOUD_MASS gave clouds their own gate, so no historical behavior depended on the old value.
BARRIER_DEFORM_CLOUD_MASS = 24  # Mass at which a cloud starts denting the barrier. Below PROTOSTAR_THRESHOLD (28) on purpose: the deform gate used to reuse the star threshold, which made this factor dead code — anything heavy enough to dent became a star first. 24 matches the black-hole evaporation clouds ("these are heavy!"), so a dead universe full of them recollapses under its own weight toward the Big Crunch — a closed universe doing what closed universes do.

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
# Element names, index-aligned with MOLECULAR_CLOUD_START_COLORS (used by the HUD legend).
ELEMENT_NAMES = [
    "Hydrogen", "Helium", "Oxygen", "Carbon", "Neon", "Nitrogen", "Iron", "Silicon",
    "Gold", "Sulfur", "Magnesium", "Phosphorus", "Lithium", "Platinum", "Cobalt",
    "Calcium", "Sodium", "Nickel", "Chromium", "Titanium",
]
# Periodic table abbreviations, index-aligned with ELEMENT_NAMES (used by the HUD element row).
ELEMENT_SYMBOLS = [
    "H", "He", "O", "C", "Ne", "N", "Fe", "Si",
    "Au", "S", "Mg", "P", "Li", "Pt", "Co",
    "Ca", "Na", "Ni", "Cr", "Ti",
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

# ── Supernova (core collapse of massive stars) ──
# Only high-tier (massive, blue) stars — mass above BLACK_HOLE_THRESHOLD — can supernova,
# matching the real mass cutoff (~8 solar masses) below which stars end as white dwarfs.
MOLECULAR_CLOUD_DEFAULT_STATE_CHANCE = 0.01    # Base per-frame chance a massive star goes supernova (resets to gas + ejecta).
SUPERNOVA_LIFETIME_MASS_EXPONENT = 2  # Supernova chance scales as (mass/threshold)^this: heavier stars live faster and die younger.
SUPERNOVA_EJECTA_COUNT_BASE = 6    # Ejecta pieces from a star right at the collapse threshold.
SUPERNOVA_EJECTA_COUNT_PER_MASS = 0.6  # Extra ejecta pieces per unit of mass above the threshold (bigger star, bigger blast).
SUPERNOVA_EJECTA_SPREAD = 20       # Max spawn radius (pixels) of supernova ejecta.
SUPERNOVA_EJECTA_MAX_MASS_FRACTION = 0.35    # Maximum ejecta mass as a fraction of PROTOSTAR_THRESHOLD.

# ── Protostars (clouds that reach enough mass to ignite) ──
PROTOSTAR_THRESHOLD = 28        # Mass at which a cloud becomes a protostar (changes appearance and behavior).
PROTOSTAR_EJECTA_COUNT = 4     # Number of ejecta pieces produced during protostar formation events.
PROTOSTAR_EJECTA_SPREAD = 14    # Max spawn distance (pixels) of ejecta from the parent star.

# Star tiers are set by MASS (as in reality: mass determines a star's temperature, color, and
# fate), not by element. Color runs cool-red (small) → warm white (sun-like) → blue (massive),
# the real temperature sequence. Only high-tier stars can collapse or supernova; the rest
# eventually fade into white dwarfs.
STAR_TIER_MEDIUM_MASS = 34      # Mass at or above which a star is mid tier (sun-like).
STAR_TIER_HIGH_MASS = 42        # Mass at or above which a star is a blue giant. Kept aligned with BLACK_HOLE_THRESHOLD: exactly the massive stars are the ones that can die violently.

# ── Civilizations (rare Dyson-swarm dimming on stable, non-violent, metal-enriched stars) ──
CIVILIZATION_CHANCE = 0.0001    # Per-frame chance an eligible medium-tier star develops one, at Z=0.
CIVILIZATION_Z_BOOST = 4.0      # Multiplier added at Z=1: chance scales by (1 + Z * this), so a fully enriched universe is 5x more likely.
CIVILIZATION_DISC_COLOR = (225, 225, 235)  # Flat cold white-grey — doesn't appear elsewhere in the palette.
CIVILIZATION_DISC_PADDING = 1   # Pixels beyond the star's own sprite radius for the opaque occluding disc.
CIVILIZATION_RING_COLOR = (150, 150, 162)  # Metallic gray for the swarm's ring segments — distinct from the disc's cold white.
CIVILIZATION_RING_PADDING = 3   # Pixels beyond the star's own sprite radius for the dot ring.
CIVILIZATION_RING_DOT_COUNT = 8   # Number of small dots (swarm segments) spaced around the ring.
CIVILIZATION_RING_DOT_RADIUS = 1  # Visual radius (pixels) of each ring dot.
CIVILIZATION_FLICKER_STEP = 0.15    # Seconds per flicker step — a stepped light curve, not a smooth pulse.
CIVILIZATION_FLICKER_GAP_CHANCE = 4  # 1-in-N steps the star's own disc blinks off (a transit-style gap); the ring stays steady.

# Ignition mass boost depends on the cloud's own metallicity: pristine hydrogen/helium clouds
# fragment less and ignite as monsters (Population III), enriched clouds ignite smaller.
STAR_ENRICHED_ELEMENT_MIN = 3   # Element index at or above which a cloud counts as metal-enriched (beyond H/He/O).
PROTOSTAR_PRISTINE_MASS_BOOST = 12  # Ignition boost for pristine (H/He/O) clouds — first stars are giants.
PROTOSTAR_ENRICHED_MASS_BOOST = 4   # Ignition boost for metal-enriched clouds.

PROTOSTAR_LOW_COLOR = (255, 120, 70)       # Red dwarf — cool, dim, effectively immortal.
PROTOSTAR_LOW_SIZE = 2
PROTOSTAR_MEDIUM_COLOR = (255, 240, 200)   # Sun-like — warm white.
PROTOSTAR_MEDIUM_SIZE = 4
PROTOSTAR_HIGH_COLOR = (150, 190, 255)     # Blue giant — hot, massive, short-lived.
PROTOSTAR_HIGH_SIZE = 6

# Collapse odds scale steeply with mass (fate is a knife-edge function of mass in reality).
COLLAPSE_MASS_EXPONENT = 17     # BH/NS collapse chance scales as (mass/threshold)^this above BLACK_HOLE_THRESHOLD. 17 gives ~10x at the 48-mass cap, matching the old red-giant fast path so compact-object formation (which drives the matter cycle) stays frequent.
# Metallicity biases the remnant: metal-rich massive stars shed more mass in winds and tend to
# leave neutron stars; metal-poor ones keep their mass and collapse straight to black holes.
COLLAPSE_NS_METALLICITY_BIAS = 0.15  # Added to NEUTRON_STAR_CHANCE for enriched stars, subtracted for pristine ones.

# ── White Dwarfs (the quiet endpoint of most stars) ──
# Sub-massive stars (below STAR_TIER_HIGH_MASS) don't explode: they shed a planetary nebula
# and leave a white dwarf that cools for a long time, fades to a black dwarf, and vanishes.
WHITE_DWARF_CHANCE = 0.002      # Base per-frame chance a sub-massive star ends its life; scaled by (mass/high-tier)^WHITE_DWARF_LIFETIME_MASS_EXPONENT so sun-like stars retire well before red dwarfs (live fast, die young — gently).
WHITE_DWARF_LIFETIME_MASS_EXPONENT = 4  # Steepness of that scaling: at 4, a sun-like star retires ~3x sooner than a red dwarf.
WHITE_DWARF_MASS_FRACTION = 0.5 # Fraction of the star's mass kept by the white dwarf; the rest blows off as the nebula.
WHITE_DWARF_GRAVITY_CONSTANT = 1 * GRAVITY_SCALE  # Gravitational pull on clouds. Weaker than a neutron star's — dense, but not exotic-matter dense.
PLANETARY_NEBULA_EJECTA_COUNT = 6  # Clouds in the ejected shell (light elements — H/He/C).
PLANETARY_NEBULA_SPREAD = 18    # Max spawn radius (pixels) of the nebula shell.
WHITE_DWARF_COOL_TIME = 90.0    # Seconds for a white dwarf to cool to invisibility (black dwarf) and be removed.
WHITE_DWARF_RADIUS = 2          # Visual radius in pixels (tiny, Earth-sized in reality).
WHITE_DWARF_COLOR = (235, 240, 255)  # Fresh white dwarf — blazing white.
WHITE_DWARF_COOL_COLOR = (70, 35, 25)  # Color it cools toward before fading into the background.
# WD-WD collisions detonate as Type Ia supernovae: total destruction, no remnant, and the
# iron-peak ejecta that make Type Ia the universe's main iron source (and standard candles).
TYPE_IA_COLLISION_DISTANCE = 5  # Distance (pixels) at which two white dwarfs detonate.
TYPE_IA_EJECTA_COUNT = 14       # Ejecta pieces from a Type Ia detonation.
TYPE_IA_EJECTA_SPREAD = 30      # Max spawn radius (pixels) of Type Ia ejecta.

# ── Black Holes ──
BLACK_HOLE_THRESHOLD = 42       # Mass above which a star can collapse (kept equal to STAR_TIER_HIGH_MASS: only blue giants die violently).
BLACK_HOLE_CHANCE = 0.0001      # Base per-frame collapse probability AT the threshold; scales as (mass/threshold)^COLLAPSE_MASS_EXPONENT. Very rare.
BLACK_HOLE_MAX_COUNT = 5        # Hard cap on coexisting black holes. Keeps holes sparse (so disks can swirl without being flung) while leaving formation frequent enough to drive the cloud matter cycle. Stars that would collapse past the cap stay stars (and supernova instead).

# ── Multiverse (each black-hole birth opens a new universe outside the current ones) ──
UNIVERSE_MAX_COUNT = max(2, os.cpu_count() or 4)  # Cap coexisting universes at the machine's core count — one core per universe when stepped in parallel.
BLACK_HOLE_RIP_MASS_FACTOR = 0.9  # Fraction of max mass a hole must reach to "rip" open a new universe. <1 because decay keeps holes hovering just under the hard cap.
UNIVERSE_RIP_TRANSFER_FRACTION = 0.4  # Fraction of the source universe's clouds pulled through into a newly ripped universe (instead of spawning fresh matter). Keeps total entity count bounded.
UNIVERSE_STREAM_FRACTION = 0.6  # After ripping, chance each cloud the hole accretes is streamed into its child universe (wormhole) instead of being consumed. 0 = one-time transfer only; 1 = everything it eats flows through.
UNIVERSE_SPAWN_GAP = 4          # Minimum gap (pixels) between a newly spawned barrier and existing ones (measured to each barrier's local edge). Small = newborn universes bud right off their parent and the multiverse grows as a touching cluster.
# Cosmological natural selection (Smolin): a ripped child inherits its parent's local physics
# with a small mutation, so universes whose constants happen to make more black holes rip more
# children under the multiverse's carrying capacity. Root (Big-Bang) universes are baseline 1.0.
UNIVERSE_MUTATION_SCALE = 0.03  # σ of the log-normal drift applied to each local dial per generation. Small on purpose: the dynamics is threshold-dense and big jumps fall off bifurcation cliffs.
UNIVERSE_DIAL_MIN = 0.5         # Hard floor for any local-physics multiplier, however many generations drift accumulates.
UNIVERSE_DIAL_MAX = 2.0         # Hard ceiling for any local-physics multiplier.
DARK_FLOW_RATE = 0.01           # Per-second rate at which every universe drifts toward the multiverse's mass-weighted centroid (exponential approach, ~100 s time constant). The cause of the drift lies outside any universe's own boundary — that's the point.
UNIVERSE_COLLAPSE_RADIUS = 8    # Mean barrier radius (pixels) below which a universe dies in a Big Crunch, taking everything inside with it. Half the natal radius (BARRIER_INITIAL_SIZE/2 = 16): a latched magnetar squeezes TO natal size and can't crunch a universe alone — sustained grinding (contact denting, mass loading) must finish the job.
BARRIER_REPULSION_RATE = 15.0   # Per-second rate at which overlapping universes are separated/flattened. Higher = firmer (less overlap).
BARRIER_RESOLVE_ITERATIONS = 4  # Relaxation passes per frame for barrier contact. More = better convergence when many universes are packed together (prevents residual overlap).
BARRIER_CONTACT_DEFORM = 1.0    # How strongly barriers flatten each other where they press together — the primary no-overlap mechanism at contact. Higher = deeper flattening.
BARRIER_SEPARATION_SHARE = 0.15  # Of the penetration when two barriers press, this fraction is resolved by pushing them apart; the rest by flattening (denting) the contact faces. Low = balloon-like (they stay in contact and visibly flatten rather than shoving apart).
MULTIVERSE_RENDER_MAX = 5000    # Max pixels per side of the off-screen surface used to draw the whole multiverse before scaling to the window.
UNIVERSE_CULL_MARGIN = 100      # Extra pixels beyond a universe's barrier radius still treated as on-view when culling off-screen universes from rendering (covers entities/pulses that momentarily poke past the barrier).
BLACK_HOLE_RADIUS = 14           # Visual radius divisor — smaller value = larger drawn black hole (mass / this). Shrinks the drawn disk and event horizon without changing gravitational mass.
BLACK_HOLE_MAX_MASS = 115       # Maximum mass a black hole can accumulate. Capped lower so no single hole grows into an overwhelming dominant one.
BLACK_HOLE_GRAVITY_CONSTANT = 30 * GRAVITY_SCALE  # Gravitational pull strength. Much higher than clouds; raised so disk clouds orbit faster (more visible swirl) and bind tighter.
BLACK_HOLE_GROWTH_RATE = 1      # Maximum mass gained per second from the accretion buffer, before the Eddington throttle below. (Raw decay at max mass is only ~0.24/s — the old "always net-decay" claim here was stale from a lower mass cap; the throttle is what actually keeps fed holes under the cap now.)
BLACK_HOLE_EDDINGTON_EXPONENT = 12  # Accretion efficiency scales by 1-(mass/max)^this — radiation pressure choking accretion near the cap. Steep on purpose: the growth-vs-decay margin is thin around mass 55-70, so a soft throttle there slows rip pacing several-fold. At 12, growth below mass ~95 is effectively untouched; a continuously fed hole settles at ~112 (above rip mass, below the cap) instead of pinning at 115 forever. Starve it and the 1/m^2 Hawking curve wins.
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
BLACK_HOLE_SWIRL_RATE = 12.0           # Relaxation rate (per second) at which disk clouds are driven toward circular-orbit speed; fades to 0 at the swirl radius. Higher = stronger/faster swirl.
BLACK_HOLE_SWIRL_RADIUS = 180         # Disk radius (pixels) at the reference mass below. Scales with hole mass, so a massive hole organizes/swirls entities from much farther out than a small one.
BLACK_HOLE_DISK_CIRCULARIZATION = 2.0  # Per-second damping of RADIAL motion inside the disk (viscous settling). This is what makes a disk look like a disk: swirl alone sets tangential speed but clouds still plunge through and get eaten in one pass; damping the radial component settles them into persistent orbits. Partial on purpose — the residual radial drift is the viscous accretion that keeps feeding the hole.
BLACK_HOLE_SWIRL_REFERENCE_MASS = 100  # Hole mass at which the disk radius equals BLACK_HOLE_SWIRL_RADIUS. A 2x-mass hole reaches 2x as far.
# Dynamical friction: a massive hole plowing through the cloud sea is gravitationally braked.
# Modeled as strong extra velocity damping (per second) so holes act as near-stationary anchors
# instead of being dragged along by accretion and bulk flows. 1.0 = no extra braking.
BLACK_HOLE_VELOCITY_DAMPING = 0.15    # Per-second velocity retention for black holes. Strong anchor so a hole drifts SLOWER than its disk rotates — otherwise the disk smears into a comet instead of a visible swirl. Higher = roams more (smears the swirl).
BLACK_HOLE_COLOR = (0,0,0)      # RGB fill color of the black hole (black).
BLACK_HOLE_BORDER_COLOR = (100, 0, 0)  # RGB color of the event horizon ring (dark red).
BLACK_HOLE_MERGE_COLOR = (0, 60, 180, 110)  # RGBA color of the gravitational wave pulse from BH mergers. Brighter than pulsar rings on purpose (rarer, weightier events); crowd-dimming applies to these too.
BLACK_HOLE_DISK_COLOR = (255, 100, 100)    # RGB color of the accretion disk tracer dot (light red).
BLACK_HOLE_DISK_SIZE = 1                   # Visual size in pixels of the accretion disk tracer.
BLACK_HOLE_DISK_ROTATION = 10            # Base rotation speed (rad/s) of the accretion disk tracer. Spin adds to this.

# ── Quasar Flares (Eddington-choked accretion bursts, see BlackHole.decay) ──
BLACK_HOLE_FLARE_THRESHOLD = 0.96     # Minimum flare_length (pixels) before jets render/log.
BLACK_HOLE_FLARE_PX_PER_MASS = 0.64   # Jet length (pixels) granted per unit of mass captured, at full choke.
BLACK_HOLE_FLARE_DECAY_PER_SEC = 10   # How fast (pixels/sec) a flare shrinks back down between meals.
BLACK_HOLE_FLARE_MAX_LENGTH = 11.52   # Cap on jet length (pixels) so one huge capture doesn't paint off-screen beams.
BLACK_HOLE_FLARE_COLOR = (255, 245, 200)  # Hot white-yellow, distinct from the disk tracer's soft red.
BLACK_HOLE_FLARE_BASE_FRACTION = 0.18  # Cone base half-width as a fraction of the hole's own radius, so it visibly touches the hole.
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
NEUTRON_STAR_CHANCE = 0.6      # Base probability of a neutron star instead of a black hole on collapse (biased by metallicity, see COLLAPSE_NS_METALLICITY_BIAS).
NEUTRON_STAR_VELOCITY_DAMPING = 0.35  # Per-second velocity retention for neutron stars AND magnetars. Dense compact objects plow through the cloud sea with heavy dynamical friction, anchoring them like black holes (0.15) but less strongly. 1.0 = no extra braking.
NEUTRON_STAR_RADIUS = 1         # Visual radius in pixels (tiny, as expected).
NEUTRON_STAR_GRAVITY_CONSTANT = 2 * GRAVITY_SCALE  # Gravitational pull strength. Moderate — between clouds and BHs.
# Pulsars spin down (as in reality: the period grows until the pulsar crosses the "death line"
# and goes radio-quiet) instead of losing mass while active. Real neutron stars then persist
# forever; the slow dead-phase decay below is an artistic-license concession that returns their
# mass to the cloud cycle — without it, dead pulsars would permanently drain the universe.
NEUTRON_STAR_SPINDOWN_RATE = 1.5  # Pulse period grows as PULSE_RATE * (1 + age * this). Higher = faster spin-down.
NEUTRON_STAR_DEATH_LINE_PERIOD = 0.5  # Pulse period (seconds) at which the pulsar goes dark and quiet (~21s of life at the rates above).
NEUTRON_STAR_ACTIVE_DECAY_RATE = 0.05  # Mass lost per second while pulsing (rotational energy leaving as pulses — near zero).
NEUTRON_STAR_DEAD_DECAY_RATE = 1.0  # Mass lost per second once dark (matter-cycle concession, see above).
NEUTRON_STAR_DECAY_THRESHOLD = 0.8  # Mass at which a dead neutron star quietly dissipates into a few cold clouds.
PULSAR_REMNANT_CLOUD_COUNT = 6  # Cold clouds released when a dead neutron star dissipates (no pulse, no fireworks).
PULSAR_REMNANT_SPREAD = 14      # Max spawn radius (pixels) of those clouds.
NEUTRON_STAR_COLOR = (0, 120, 255)  # RGB color of the neutron star (cyan-blue).
NEUTRON_STAR_JET_LENGTH = 2     # Visual length (pixels) of each polar jet segment.
NEUTRON_STAR_JET_FLASH_LENGTH = 4  # Jet length (pixels) during the white flash window — the beam pulse stretching out.
NEUTRON_STAR_JET_WIDTH = 1      # Line width (pixels) for drawing jets.
NEUTRON_STAR_DEAD_COLOR = (70, 80, 100)  # Dim slate color of a pulsar that crossed the death line.
NEUTRON_STAR_PULSE_RATE = 0.015  # Seconds between pulsar pulses. Lower = faster pulsing.
NEUTRON_STAR_PULSE_STRENGTH = 7 # Force magnitude of each pulse ripple. Higher = stronger push on nearby entities.
NEUTRON_STAR_PULSE_COLOR = (0, 140, 255, 90)  # RGBA color of the expanding pulse ring. Alpha kept low: rings overlap and stack additively during wave storms.
PULSE_CROWD_REFERENCE = 3  # Number of coexisting wave rings (per universe) shown at full brightness; beyond it each ring's alpha scales by sqrt(reference/count) — loudness normalization, so a lone kilonova ring stays dramatic while a storm of twenty auto-quiets instead of stacking to glare.
NEUTRON_STAR_PULSE_WIDTH = 2    # Line width (pixels) for drawing pulse rings.
NEUTRON_STAR_RIPPLE_SPEED = 64  # How fast (pixels/sec) pulse ripples expand outward.
NEUTRON_STAR_RIPPLE_EFFECT_WIDTH = 24  # Width (pixels) of the zone where ripples exert force on entities.
NEUTRON_STAR_PULSE_COLOR_DURATION = 0.1  # Seconds the neutron star flashes white after each pulse.
NEUTRON_STAR_PULSE_FADE_RATE = 1.5  # Rate multiplier for pulse fade once the wavefront reaches the barrier.

# ── Magnetars (rare neutron-star births with an extreme magnetic field) ──
MAGNETAR_CHANCE = 0.15          # Probability a neutron-star birth is a magnetar instead of a plain NS.
FERROMAGNETIC_ELEMENTS = (6, 14, 17)  # Element indices the field grips: Iron, Cobalt, Nickel.
MAGNETAR_MAGNETIC_CONSTANT = 5 * GRAVITY_SCALE  # Magnetic pull on ferromagnetic clouds. Falls off as 1/d (not 1/d^2), so the grip stays near-constant across the whole field radius — but only ~7% of clouds respond, so it never competes with black holes for organizing matter.
MAGNETAR_FIELD_RADIUS = 120     # Reach (pixels) of the magnetic pull.
MAGNETAR_FIELD_LIFETIME = 15.0  # Seconds before the field dies and the magnetar settles into a plain neutron star.
MAGNETAR_DECAY_RATE = 1         # Mass lost per second. Slower than NS decay so it survives long enough to settle.
MAGNETAR_FLARE_CHANCE = 0.003   # Per-frame chance of a giant flare (outward pulse via the BH-merger pulse machinery).
MAGNETAR_FLARE_ENERGY = 25      # Flare pulse energy budget (same units as BH-merger consumed mass).
MAGNETAR_FLARE_MASS_COST = 2    # Mass the magnetar loses per giant flare.
MAGNETAR_RADIUS = 3             # Visual core radius in pixels (larger than a plain neutron star).
MAGNETAR_COLOR_A = (235, 60, 200)  # Magenta pole of the color oscillation.
MAGNETAR_COLOR_B = (60, 130, 255)  # Blue pole of the color oscillation.
MAGNETAR_COLOR_CYCLE_RATE = 3.0    # Color oscillation phase speed (radians/sec).
MAGNETAR_GLOW_RADIUS = 9        # Radius (pixels) of the translucent aura drawn around the core.
MAGNETAR_GLOW_ALPHA = 80        # Aura opacity (0-255).
MAGNETAR_BARRIER_CONTRACT_FACTOR = 2  # Whole-ring inward acceleration (sqrt(mass)-scaled) while a magnetar is latched onto the wall — the contraction counterpart to pulse-driven expansion. Barrier damping bounds the resulting contraction speed to a few px/s (at 2, a mass-40 magnetar reels the ring in at ~4 px/s). Higher = faster squeeze but risks out-pulling flare/pulse expansion entirely. Soft-floored at the natal (Big-Bang) radius.
MAGNETAR_WALL_STICK = 12        # Pull (px/s^2) drawing an in-field magnetar to the wall, ramping to full strength at contact. Must beat the NS containment push (6) or the magnetar gets shoved off before it can reel the wall in; the stick is what turns a one-dent pinch into sustained contraction.
MAGNETAR_BARRIER_ATTRACT_RATE = 1.2  # Per-second relaxation of in-field wall vertices toward the magnetar's radial distance — the visible "wall bows toward the magnet" attraction. Target-based (bounded), so it cannot run away like a constant pull would.

# ── Kilonova (neutron star merger) ──
KILONOVA_EJECTA_COUNT = 20      # Number of ejecta pieces from a NS-NS collision. Rich in heavy elements (r-process: gold, platinum — the GW170817 result).
KILONOVA_COLLISION_DISTANCE = 6 # Distance (pixels) at which two neutron stars merge.
KILONOVA_EJECTA_SPREAD = 40     # Max spawn distance (pixels) of kilonova ejecta. Large explosion!
# The remnant depends on the combined mass (as with GW170817): light pairs leave a magnetar,
# heavy pairs collapse straight to a black hole.
KILONOVA_MAGNETAR_REMNANT_MAX = 70  # Combined mass below which the merger leaves a magnetar instead of a black hole.

# ── Metallicity (chemical evolution of a universe) ──
# Each universe tracks a metallicity Z in [0, 1] — a blend factor from pristine Big-Bang gas
# toward metal-rich matter. Every enrichment event ratchets it up, and ejecta composition is
# blended toward the metal-rich tables by Z, so universes visibly age chemically over
# generations of stars (Population III → II → I). Children inherit Z when a universe rips.
METALLICITY_PER_SUPERNOVA = 0.0002  # Z gained per core-collapse supernova (they are frequent; the arc should take many minutes).
METALLICITY_PER_TYPE_IA = 0.002    # Z gained per Type Ia detonation (the main iron injector).
METALLICITY_PER_KILONOVA = 0.004   # Z gained per kilonova (rare but heavy-element rich).
METALLICITY_PER_NEBULA = 0.0002    # Z gained per planetary nebula (gentle enrichment).
# Quenching: chemically old gas stops forming stars. Merge chances (ambient and shock) scale by
# (1-Z)^exponent, so the Z ratchet doubles as a thermodynamic age — star formation declines over
# generations and a universe can die quietly of exhaustion instead of only by violence.
STAR_FORMATION_QUENCH_EXPONENT = 2.0  # Steepness of the decline: at Z=0.3 formation runs at ~half rate; at Z=0.7, ~a tenth.
HEAT_DEATH_Z = 0.9              # A universe that dies above this Z earns the heat-death epitaph (died of completion); below it, the plainer one.

# ── Shock-triggered star formation ──
# Supernova/pulsar wavefronts compress the clouds they pass through; compressed clouds are far
# more likely to merge/collapse while the shock lasts — the real mechanism by which star
# formation propagates in waves through galaxies.
SHOCK_DURATION = 1.5           # Seconds a cloud stays "shocked" after a wavefront passes it.
SHOCK_MERGE_CHANCE = 0.5       # Merge probability per frame for overlapping SHOCKED cloud pairs (vs 0.12 base).

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

# Type Ia supernovae burn a carbon-oxygen white dwarf to iron-peak elements: no hydrogen or
# helium, no r-process metals — mostly iron, nickel, silicon, sulfur, calcium, chromium.
TYPE_IA_ELEMENTAL_ABUNDANCE = [
    (0, 0.0),      # Hydrogen - none (the dwarf has no envelope)
    (0.0, 0.0),    # Helium - none
    (0.0, 0.06),   # Oxygen range: 0-6% (unburned fuel)
    (0.06, 0.10),  # Carbon range: 6-10% (unburned fuel)
    (0.10, 0.11),  # Neon range: 10-11%
    (0.11, 0.11),  # Nitrogen - none
    (0.11, 0.55),  # Iron range: 11-55% (the main product)
    (0.55, 0.68),  # Silicon range: 55-68%
    (0.68, 0.68),  # Gold - none (no r-process in a thermonuclear burn)
    (0.68, 0.76),  # Sulfur range: 68-76%
    (0.76, 0.79),  # Magnesium range: 76-79%
    (0.79, 0.80),  # Phosphorus range: 79-80%
    (0.80, 0.80),  # Lithium - none
    (0.80, 0.80),  # Platinum - none
    (0.80, 0.84),  # Cobalt range: 80-84%
    (0.84, 0.90),  # Calcium range: 84-90%
    (0.90, 0.91),  # Sodium range: 90-91%
    (0.91, 0.97),  # Nickel range: 91-97%
    (0.97, 0.99),  # Chromium range: 97-99%
    (0.99, 1.0),   # Titanium range: 99-100%
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
