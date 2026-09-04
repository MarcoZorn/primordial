# Design notes

Why the simulation is put together the way it is. Mostly this is a record of
choices that had a cheaper-looking alternative.

## No fitness function

The obvious way to build this is to score organisms and breed the top N. That
produces an optimiser, not an ecosystem: it can only ever find the maximum of
whatever was written into the scoring function, and it cannot surprise you.

Here nothing is scored. An organism accumulates energy, pays upkeep, and
divides when it is above threshold. A lineage persists because its members kept
paying. This is slower and messier and it is the entire point — the selection
pressure is whatever the dish currently happens to be, including the other
organisms in it, which are also changing.

## One organism type

An earlier version had a `Plant` class with growth/toxicity genes and a
separate `Creature` class with a brain. It was deleted. Hardcoding the split
answers the most interesting question in advance.

With one type and a `photo` cell available to everyone, the plant/animal
distinction becomes an outcome. It also means the boundary can move: nothing
stops a lineage from being both, or from abandoning photosynthesis later.

## Two genomes, not one

Body and brain mutate independently. A brain that wants to chase is worthless
without movers, and movers are worthless without a brain that steers — so the
two have to arrive in some order, and the order matters. Keeping them separate
lets that play out instead of coupling them through a single encoding.

## Bounded attention

Neighbour queries go through a KD-tree and are capped at the nearest `k`
organisms. This started as a performance fix — the first version was quadratic
and the process was killed — but it is also more defensible than perfect
omniscient perception: a real sensor has finite bandwidth.

## Metabolic scaling

Upkeep is `energy_drain × mass^0.75` rather than linear in mass. That exponent
is Kleiber's law, the empirical scaling of metabolic rate with body mass across
real organisms. With linear upkeep, size is neutral; with the exponent, size is
an advantage that has to be paid for, which is the condition under which large
bodies are worth evolving at all.

## Shading

Photosynthesis is divided by local crowding. Without it, light is unlimited,
population grows until it hits the hard cap, and nothing ever starves — which
is exactly what the first balanced run did. Density-dependent light makes space
a contested resource and is what turns the dish from a paradise into a place
where dying is possible.

## Jittered lifespans

Lifespan is inherited with a wobble instead of being a constant. With a
constant, the entire founding cohort dies on the same tick and the run
near-collapses; the first long run lost 200 of 214 organisms in one step at
tick 6000. Inherited jitter both fixes that and makes lifespan itself evolvable.

## Feedforward only

Networks are acyclic and evaluated in topological order, and the add-connection
mutation refuses any edge that would close a loop. This is a real limitation —
it means no memory between ticks — and it is on the roadmap to lift. It is
currently in place because acyclic evaluation is trivially correct and cheap,
and there was no reason to pay for recurrence before there was behaviour worth
remembering.
