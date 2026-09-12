# primordial

An open-ended evolution sandbox. It starts with a dish of identical single
cells and no goal, and you watch what shows up.

There is no fitness function anywhere in this repository. Nothing is scored,
ranked or bred by the simulation. An organism has one problem, stay solvent
long enough to divide, and every structure you see on screen is something that
problem paid for.

**[→ Live status of the ongoing run](LIVE.md)**, regenerated from telemetry
while the run is going, not written by hand.

![primordial: organisms in the dish, and the evolved brain of the one being tracked](docs/demo.gif)

<sub>Day 1245 of a live run. 1799 organisms, 28 species, lineage depth 637. The panel on
the right is the actual neural network of the organism being followed: 144 hidden neurons
and 859 synapses that nothing in this repository designed.</sub>

## What is actually being simulated

Every organism has two genomes that mutate independently when it divides.

**A body.** A clump of cells on a square lattice. Every organism begins as a
single undifferentiated cell. Mutation can bolt on a cell, respecialise one, or
drop one, and the cell types decide what the organism can physically do:

| cell | what it buys |
|---|---|
| `core` | feeds weakly on ambient light; every body has exactly one |
| `photo` | photosynthesis: free energy, but it does not move |
| `mover` | speed and turning rate |
| `eater` | reach and bite strength, lets it consume other organisms |
| `sensor` | sight range |
| `armor` | reduces damage taken when bitten |
| `store` | energy capacity |
| `toxin` | hurts whatever eats it, and costs upkeep every tick |

**A brain.** A neural network evolved with NEAT (Stanley & Miikkulainen 2002),
starting from a bare input→output layer with no hidden neurons. Mutation
perturbs weights, adds connections, and splits existing connections to insert
new neurons, so depth and width are discovered rather than configured. The
network reads 24 senses and drives three outputs: left thruster, right
thruster, and the urge to divide.

### Nobody defines a plant or an animal

There is one organism type in the code. A clump that fills with `photo` cells
and never grows a `mover` **is** a plant. One that grows movers and eaters is
an animal, and it can only survive by eating things that are evolving not to be
eaten. The kingdom label in the UI is read off the body after the fact; nothing
in the simulation branches on it.

### Light is local and exhaustible

All energy enters the world as light, and light is not a background constant,
it is a resource sitting on the ground in patches. Feeding draws the patch you
are standing on down, and it recovers slowly. A patch supports one sessile
organism for around 1,600 ticks and eight of them for around 200.

This is the single most important rule in the simulation, because it is what
makes a brain worth having. Without depletion the best possible strategy is to
sit in the brightest spot and divide, which requires no perception, no
movement, and no thought. With it, staying alive means finding ground that has
not been grazed, which means moving, sensing a gradient, and comparing what is
underfoot now with what it was a moment ago. That last part needs memory, and
memory is what recurrent connections are for.

Organisms are told how much light is under them. They are not told where more
of it is.

### The rest of the economy

Every organism pays rent. A cell costs
upkeep each tick, scaled sublinearly with body mass (Kleiber's law), so large
bodies must earn their size. Photosynthesis is shaded by nearby neighbours, so
crowding starves a patch and space itself becomes contested. Movement, toxins
and division all cost. Nothing is free, which is the only reason selection has
anything to bite on.

Rocks block movement. Droughts, blooms and meteor strikes fire at random and
are logged in the UI.

## Running it

    pip install pygame numpy scipy
    python run.py

### A long run

For anything longer than a sitting, the simulation runs headless in a daemon
that owns the world and checkpoints itself, with a viewer you attach and detach
at will:

    python daemon.py --run runs/genesis     # start, or resume where it left off
    python view.py   --run runs/genesis     # watch; close it whenever, the run continues
    python status.py --run runs/genesis     # regenerate LIVE.md from telemetry

The daemon checkpoints every 10,000 ticks and survives being killed: start it
again on the same directory and it comes back as the same world, same
organisms, same innovation numbers, same random stream. Stopping it with a
signal makes it checkpoint before exiting, so pausing a run is safe.

The window sizes itself to your display. Press the `speed` button a couple of
times; real change takes tens of thousands of ticks.

| control | |
|---|---|
| `space` | pause |
| `f` / speed button | cycle x1 → x4 → x16 → x64 |
| wheel, `+` / `-` | zoom |
| `0` | fit whole world |
| drag | pan |
| click | select an organism and watch its brain fire |
| `tab` | jump to the largest organism alive |
| `c` | follow the selection |
| `g` | global stats: full cell census, largest body, largest brain |
| `[` `]`, `A-` `A+` | UI text size |
| `F11` | fullscreen |
| `s` | save the selected genome to `runs/` |

## Reading the display

Organisms are drawn **cell by cell**, coloured by cell type, so what a thing is
made of is visible at a glance. Zoom in far enough and you are looking at the
actual body plan that evolution arrived at.

The brain panel draws the selected organism's network live. Orange is
excitation, blue is inhibition, node size is firing strength, and every line is
a synapse coloured by the signal currently crossing it. Neurons in the middle
columns did not exist at the start of the run; they were inserted by mutation.

## Layout

    primordial/genes.py      NEAT genome: innovations, mutation, crossover, distance
    primordial/brain.py      genome -> evaluable feedforward network
    primordial/body.py       cell-lattice body genome and its derived stats
    primordial/world.py      the dish: energy economy, senses, eating, division, weather
    primordial/evolution.py  speciation (labels and colours only)
    primordial/render.py     camera, cell rendering, brain view, stats
    primordial/app.py        the interactive loop
    run.py                   entry point

`docs/` holds the design notes and the running research log.

## Status

Working and open-ended. See [docs/ROADMAP.md](docs/ROADMAP.md) for what is next
and, more importantly, for an honest account of which parts of the long-term
goal are engineering and which are unsolved research.

MIT licensed.
