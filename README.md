# simcraft
![hehe](/assets/cmb.jpg)

A zero-player universe simulator, and a small piece of applied metaphysics.

**The math.** Simcraft is not a physics code in the validation sense — it is a designed dynamical system: dissipative, driven, and hybrid (a continuous gravity flow punctuated by discrete events — collisions, ignitions, stellar fates — whose odds depend on the state; formally, a piecewise-deterministic Markov process). There are no conserved quantities, on purpose. The barrier breaks translation symmetry, damping breaks time symmetry, and by Noether's theorem nothing is owed. Structure comes from attractors instead of invariants: galaxies form *because* energy is lost, not despite it.

**The metaphysics.** Runs are unrepeatable by design. Floating-point addition is not associative, each gravity backend sums in its own order, and chaos amplifies every last-bit difference into a different history — so no universe can be re-run, and none exists before it happens. Rounding is many-to-one, so the arrow of time is built into the arithmetic: the map cannot be inverted, the universe cannot be rewound. Each run is an event, not an object. When it ends it is gone completely, leaving one 42-digit number — the whole trajectory folded through an entropy pool that never forgets — as proof that this particular universe occurred. Nobody plays. The universe records itself, says one unrepeatable thing on the way out, and that's the point.

---

2026 CE //

Astrophysics realism pass using `Claude Fable 5`. Stellar fate now follows mass (red dwarf → sun-like → blue giant, the real temperature sequence), with metallicity biasing ignition size and neutron-star-vs-black-hole outcomes. Sub-massive stars retire as white dwarfs via planetary nebulae (WD-WD collisions detonate as Type Ia supernovae); pulsars spin down and cross the death line instead of exploding; kilonova remnants are mass-dependent (magnetar or black hole, per GW170817). Each universe chemically ages: a metallicity Z ratchets up with every enrichment event and blends ejecta composition metal-rich over stellar generations. Supernova/pulsar shockwaves now trigger star formation in the clouds they compress. New HUD: a live event ticker with real-physics glosses, a Z stat, and an entity/element legend on `[L]`.

Full performance refactor using `Claude Fable 5`. Split the sim into modules around a numpy structure-of-arrays core; cloud gravity now has swappable backends (Taichi GPU, a new Cython Barnes-Hut quadtree, numpy brute-force) computing the same physics rules — never the same bits; float addition isn't associative and each backend sums in its own order, which is embraced: runs are unrepeatable by design. Much faster.

Huge refactor using `Claude Code Opus 4.6`
The "Ring" concept has been changed to a dynamic manifold barrier that is manipulated by gravity and gravitational events.
Many other little improvements and bug fixes. Improved RNG and now output number on quit.

2025 CE // 

As the project has grown and AI models have become more capable, agentic IDE's more user friendly, this project has shifted to function as a sort of test. Models that have contributed: `Github Copilot/GPT-3`, `GPT-4`, `GPT-4o`, `GPT-4o-mini`, `Claude 3.5 Sonnet`, `Claude 3.7 Sonnet`, `Gemini 2.5 Pro`, `Grok-2`

Added a RNG for fun...

2023 CE //

A "blocky" (like minecraft) 2D Universe Simulator (Simcraft). Original base structure (seen in /backups) written with OpenAI GPT3.5/4 and VSCode Copilot. Enhanced, tested, and debugged by Derek. Uses `pip install pygame` https://www.pygame.org/

## Original Context

Inspired by: 

https://en.m.wikipedia.org/wiki/Zero-player_game

https://en.m.wikipedia.org/wiki/Great_Attractor

https://en.m.wikipedia.org/wiki/Dark_flow

https://www.bbc.com/news/science-environment-67950749


## Usage

`pip install .`

Run `simcraft` for the main game.
