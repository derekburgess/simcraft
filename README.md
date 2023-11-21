# simcraft
![hehe](/assets/cmb.jpg)

2023 CE //

A pixel universe simulator written with OpenAI GPT4 and VSCode Copilot. Uses `Python` and `pygame`.

```pip install pygame```

Delete `data.csv` before running the simulator.

```python sim.py``` -- A set and forget universe simulator with my "great attractor" ring. Why? I had this drunken thought along the lines of "what if the 'great attractor' was actually just gravity on the edge of our universe' expanding manifold?" and so I wanted to see if I could make a dumb little 2D simulation using OpenAI, because that's been my thing lately lol... anyways- run it and find out. You can hit spacebar to add data to a CSV file, spam it as needed like you are "observing" the universe. Further more, using the `analysis` scripts, you can see how the universe evolves over time.
```backups``` -- Contains older stable versions of the simulator.

```clock.py``` -- This crazy "clock" based universe simulator, our "great attractor" moves like the old school clocks in a continous minute. This runs like shit after a few minutes, but I ran it for 90 minutes and had some interesting "galaxy clusters" form. In the end, this program was not what I was originally going for but evolved in a fun way and results in fun simulations, forcing you to ponder time and scale. I couldnt get the AI's to reason through concurrency or other performance improvements. Something I will learn and implement myself.

```analysis``` -- The Analysis directory contains some scripts that ingest the `data.csv` file (created and updated by hitting spacebar) and return some visualizations to enhance your experience.

```cluster.py``` Clusters units by `type`, `mass`, `distance from center`, and `observation`, returns a 3D plot.

```flux.py``` -- A dumb "exoplanet" graph. Shows change in `flux` (dip in opacity), over `observations`...

```heatmap.py``` -- Shows the distribution of units by `mass` and `flux`, calling out black holes.

```network.py``` -- Creates heirarchical network graphs of the units, based on their distance from more massive units like stars and black holes. Not much to say on what this really means, I thought it would be interesting to see a mapping of matter impacted by the presense of a black hole, but this needs some work...

```time_3d.py```  -- Displays a 3D plot of change in unit `type` over time including `X`an `Y` position.

```timeseries.py``` -- Displays the change in the 3 primary unit `types`, Molecular Clouds, Protostars, and Primordial Black Holes. Calculating the stars from the molecular clouds to add a layer of ambiguity and adjustment in the analysis phase.

```example_data.csv``` -- 8 Billion year run of the simulator.

![hehe](/assets/demo_171123.gif)