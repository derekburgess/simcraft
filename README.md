# simcraft
![hehe](/assets/cmb.jpg)

2023 CE //

A "blocky" (like minecraft) 2D Universe Simulator (Simcraft). Original base structure (seen in /backups) written with OpenAI GPT4 and VSCode Copilot. Enhanced, tested, and debugged by Derek. Uses `pygame`.

Inspired by https://en.m.wikipedia.org/wiki/Zero-player_game

Why? I had this drunken thought one afternoon along the lines of, "what if the 'great attractor' was actually just gravity caused by mass collecting at the edge of our universe' expanding manifold?" and so I wanted to see if I could make a dumb little 2D simulation using OpenAI- Run it and find out. The simulation will automatically log data evert 500m years...but you can also hit the spacebar to add data to a CSV file. Spam it as needed like you are "observing" the universe. Further more, by using the `simanalysis` command you can see how the universe evolves over time.

https://en.m.wikipedia.org/wiki/Great_Attractor

I should note, I had not read any updated research on the great attractor prior to this and in hindsight alot has changed! I would now say simcraft is more of an attempt to simulate "dark flow" or mass outside of our visible universe...

https://en.m.wikipedia.org/wiki/Dark_flow

But then this happened?

https://www.bbc.com/news/science-environment-67950749


## Setup

First set an env var for the data file: 

`SIMCRAFT_DATA`


Then run:

`pip install -r requirements.txt`

`pip install .`


## Operation

Run `simcraft` for the main game.

Run `simanalysis` with any of the following args:

`--cluster` Clusters units by `type`, `mass`, `distance from center`, and `observation`, returns a 3D plot. Great for exploring the composition of universe over time.

`--heatmap` -- Shows the distribution of units by `mass` and `flux`, calling out black holes. Interesting for analyzing black hole evolution in proximity to possible exoplanets, i.e. "possible civilizations".

`--time` -- Displays the change in the 3 primary unit `types`, Molecular Clouds, Protostars, and Primordial Black Holes. Calculating the stars from the molecular clouds to add a layer of ambiguity and adjustment in the analysis phase.

`--time_3d`  -- Displays a 3D plot of change in unit `type` over time including `X`an `Y` position.


/backups -- Contains older stable versions of the simulator. Earlier examples almost entirelly written by AI.

`clock.py` -- This is a crazy "clock" themed universe simulator. The "great attractor" moves like the old school clocks in a continous minute. This runs like shit after a few minutes (seriously, my rig is no joke), but I ran it for 90 minutes and had some interesting "galaxy clusters" form. In the end, this program was not what I was originally going for but evolved in a fun way and results in fun simulations, forcing you to ponder time and scale. I couldnt get the AI's to reason through concurrency or other performance improvements. Something I will learn and implement myself.
