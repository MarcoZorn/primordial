# Roadmap

The long-term goal is a dish that keeps producing new kinds of thing without
anyone telling it what to produce. This file tracks how far that has actually
got, and is deliberately blunt about which parts of the ambition are
engineering and which are open research.

## Done

**Stage 0 — NEAT.** Genome with historical markings, weight/structure mutation,
crossover aligned on innovation numbers, compatibility distance, speciation.
Networks start with no hidden neurons and grow them.

**Stage 1 — a continuous dish.** No generations, no resets, no fitness
function. Organisms divide when they can afford it and die when they cannot pay
upkeep. Selection is entirely a side effect of the energy economy.

**Stage 2 — multicellular bodies.** Every organism is a lattice of cells with
its own genome. Cell composition determines speed, sight, reach, capacity,
armour, toxicity and photosynthesis. Bodies begin as one cell.

**Stage 3 — emergent kingdoms.** No plant or animal class exists. Photosynthesis
and predation are two strategies available to the same organism type, and which
one appears is decided by the dish.

**Stage 4 — terrain and weather.** Obstacles, droughts, blooms, meteor strikes.

**Stage 5 — instrumentation.** Cell-level rendering, live brain view, camera,
global census, telemetry written to `runs/telemetry.jsonl`.

## What actually caps open-endedness

Three structural limits decide whether this system can keep producing genuinely
new kinds of thing, or whether it plateaus. Everything else is decoration.

**1. Cell types are a fixed list of eight.** Morphology can only ever
recombine the same eight parts. Replacing the enum with an evolvable trait
vector per cell — each cell carrying continuous values for photosynthesis,
thrust, bite, sensitivity, toughness, storage, toxicity — makes the space of
possible bodies genuinely open, and lets intermediate and hybrid cells exist.

**2. The sensory interface is fixed.** Every organism has exactly the same 32
inputs and 4 outputs no matter what its body is. A lineage cannot evolve a new
sense. The deep fix is to derive the interface from the body: each SENSOR cell
contributes its own input node, each MOVER its own output, so growing a body
grows the brain's interface with it. This is the single most important change
for open-endedness and the most invasive.

**3. No recurrence, therefore no memory.** Networks are acyclic, so nothing can
hold state between ticks. Every behaviour is a reflex. Sequence, anticipation,
and anything resembling syntax are all impossible until this is lifted.

## Next, in order

**Corpses and decomposition.** Dead organisms currently just vanish. Leaving
their energy behind as carrion opens a scavenger niche and closes the nutrient
loop, which is the cheapest way to add a whole trophic level.

**Recurrence and memory.** Networks are strictly feedforward, so an organism
cannot hold state between ticks. Allowing recurrent connections gives it
short-term memory — the precondition for anything resembling behaviour over
time rather than reflex.

**A decoder for the signalling channel.** *(the channel itself now exists:
a `chirp` output, per-ray hearing inputs, and a small energy cost to emit.)*
The channel means nothing on its own — what matters is measuring whether it
carries information. The instrument is mutual information between an
organism's emission and the world state around it, and between an emission and
what nearby organisms do next. If a chirp reliably precedes an escape
manoeuvre, that is communication by an operational definition rather than a
hopeful one. Evolved signalling — including deceptive signalling under
competition — is a replicated result in evolutionary robotics, so this is a
measurement problem, not a gamble.

**An input channel the observer controls.** One extra sense wired to a value
set from outside the simulation. Whether lineages evolve to exploit it is a
real experiment, and it is the only honest version of "talking to them".

**Sexual reproduction proper.** Currently a division sometimes borrows genes
from a neighbour. Real mate choice, driven by the brain, would let sexual
selection act.

**Speed.** Brain evaluation is pure Python. A vectorised or compiled evaluator
is the difference between 10³ and 10⁶ neurons in play.

## Honest limits

Some of the things this project is aiming at are not scheduled work, and it
would be dishonest to list them as if they were tasks:

- **Hundreds of billions of neurons is not reachable on this substrate, or on
  any single machine.** For scale, that is the order of a human brain, and no
  system anyone has built simulates one at neuron resolution. What *is*
  reachable here is thousands of neurons per organism with a compiled
  evaluator. The genome→phenotype split is kept clean specifically so the
  evaluator can be replaced without touching the evolution.

- **Emergent language you could hold a conversation in is unsolved research.**
  Evolving a signalling channel that demonstrably carries information is
  achievable. Evolving compositional grammar is at the frontier. Evolving
  something that speaks a human language it was never exposed to is not
  possible in principle — a language has to come from somewhere.

- **Organisms modifying the simulation's own code is not evolution**, it is a
  separate mechanism that would have to be designed and handed to them. If it
  is interesting it is interesting as its own project.

- **Civilisation is not a thing evolution produces on a timescale a laptop can
  reach.** Cooperation, territoriality and signalling are plausible. Culture is
  not.

None of this makes the project less interesting. The reason open-ended
evolution is a live research area is precisely that nobody can currently get a
dish to keep producing genuinely new kinds of complexity indefinitely — runs
tend to plateau. Watching *where* this one plateaus, and finding out what
removes the ceiling, is the actual experiment.
