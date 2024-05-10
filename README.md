# simcraft
![hehe](/assets/cmb.jpg)

2023 CE //

"blocky" (like minecraft) 2D universe simulator (simcraft lol). Base structure written with OpenAI GPT4 and VSCode Copilot. Enhanced, tested, and debugged by Derek. Uses `Python` and `pygame`.

A set and forget universe simulator with my "great attractor" ring. Why? I had this drunken thought one afternoon along the lines of, "what if the 'great attractor' was actually just gravity caused by mass collecting at the edge of our universe' expanding manifold?" and so I wanted to see if I could make a dumb little 2D simulation using OpenAI- Run it and find out. You can hit spacebar to add data to a CSV file, spam it as needed like you are "observing" the universe. Further more, using the `analysis` scripts, you can see how the universe evolves over time.

https://en.m.wikipedia.org/wiki/Great_Attractor

I should note, I had not read any updated research on the great attractor prior to this and in hindsight alot has changed! I would now say simcraft is more of an attempt to simulate "dark flow" or mass outside of our visible universe...

https://en.m.wikipedia.org/wiki/Dark_flow

But then this happened?

https://www.bbc.com/news/science-environment-67950749

Inspiration: https://en.m.wikipedia.org/wiki/Zero-player_game

First set an env var for the data file: 

`SIMCRAFT_DATA`

Pull the repo and:

`pip install -r requirements.txt`

`pip install .`

Then run: `simcraft`

Running `simanalysis` with any of the following args:

`--cluster` Clusters units by `type`, `mass`, `distance from center`, and `observation`, returns a 3D plot. Great for exploring the composition of universe over time.

`--flux` -- A dumb "exoplanet" graph. Shows change in `flux` (dip in opacity), over `observations`... Since flux dip is random, its just a dumb graph.

`--heatmap` -- Shows the distribution of units by `mass` and `flux`, calling out black holes. Interesting for analyzing black hole evolution in proximity to possible exoplanets, i.e. "possible civilizations".

`--time_3d`  -- Displays a 3D plot of change in unit `type` over time including `X`an `Y` position.

`--timeseries` -- Displays the change in the 3 primary unit `types`, Molecular Clouds, Protostars, and Primordial Black Holes. Calculating the stars from the molecular clouds to add a layer of ambiguity and adjustment in the analysis phase.

![hehe](/assets/demo_211123.gif)

/backups -- Contains older stable versions of the simulator. Earlier examples almost entirelly written by AI.

`clock.py` -- This is a crazy "clock" themed universe simulator. The "great attractor" moves like the old school clocks in a continous minute. This runs like shit after a few minutes (seriously, my rig is no joke), but I ran it for 90 minutes and had some interesting "galaxy clusters" form. In the end, this program was not what I was originally going for but evolved in a fun way and results in fun simulations, forcing you to ponder time and scale. I couldnt get the AI's to reason through concurrency or other performance improvements. Something I will learn and implement myself.
