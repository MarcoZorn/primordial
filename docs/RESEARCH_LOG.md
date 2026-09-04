# Research log

Dated notes on what actually happened in runs, including the things that went
wrong. Raw telemetry lives in `runs/logs/`.

Reproduce any table here with:

    python analyse.py runs/logs/<file>.jsonl

---

## 2026-09-04 — run 01, first long continuous run

`1600×1200`, 200 founders, `max_pop=800`, seed 7. Watched live to tick 43,800.

### Milestones

| event | tick |
|---|---|
| first `photo` cell | 1,200 |
| first `mover` cell | 600 |
| first 3-cell body | 5,400 |
| first organism classed as an animal | 11,400 |

### Trajectory

| tick | pop | plants | animals | avg cells | largest body | species |
|---|---|---|---|---|---|---|
| 15,600 | 67 | 41 | 0 | 2.51 | 5 | 15 |
| 35,400 | 459 | 34 | 413 | 6.99 | 13 | 25 |
| 43,800 | 282 | 15 | 267 | 12.01 | 21 | 12 |

### What happened

**A photosynthesis sweep, then a predation sweep.** The founding population of
free-feeding single cells collapsed from 200 to 67 by tick 15,600 — 591 deaths
against 458 births. The survivors were almost entirely organisms carrying a
`photo` cell: 66 photo cells across 67 organisms. Making your own energy beat
subsisting on the core's trickle, and the dish found that first.

Predation arrived much later. `mover` and `eater` cells existed from tick 600
onward but were useless in isolation — an eater with nothing to steer it, or a
mover with nothing to catch. The first organism carrying both appeared at tick
11,400, and once the combination existed it spread hard: 0 → 413 animals
between tick 15,600 and 35,400, against a standing crop of plants that could
not run.

**Then the animals overshot.** By tick 43,800 plants were down to 15 and total
population had fallen from 459 to 282 while average body size kept climbing to
12 cells. This is the shape of a predator–prey overshoot: the consumers
outgrew the resource that fed them. Nothing in the code models this; it falls
out of the energy economy.

**Body size rose monotonically** — 1.0 → 2.5 → 7.0 → 12.0 mean cells, with the
largest body reaching 21 cells. Metabolic cost scales as `mass^0.75`, so this is
size being worth paying for, not size being free.

**Toxin cells appeared** (39 by tick 35,400) once predation was established, and
not meaningfully before. That ordering is what a defensive trait should look
like: toxins cost upkeep every tick and are worthless until something is trying
to eat you.

### Caveats

This is one run on one seed and none of the above is established. The ordering
of the sweeps is the interesting claim and it needs replication across
independent seeds before it means anything — that is what `batch.py` is for.
The population also spent the late run pressed toward `max_pop`, so the final
numbers are partly an artefact of a hard ceiling rather than pure ecology.


---

## 2026-09-04 — run 02, and what actually limits brain size

Engine v2: recurrent networks, continuous cell traits, carrion, an acoustic
channel, day/night and seasons. `genesis` reached tick 462,000 (day 192, 165
generations) with plants and animals coexisting in roughly equal numbers over
hundreds of thousands of ticks — a predator/prey balance that held without
intervention once trophic efficiency was in.

### Three bugs that were changing the results

**`kill()` was not idempotent.** A dead organism stays in the list until the
tick ends, so several predators could reach the same body and each call
`kill()` on it. That inflated the death toll to 59 million against 534,000
births — but far worse, **each call dropped another corpse**, creating energy
from nothing. The population had been propped up against its cap by phantom
food for the whole run. Fixed, with a test; the counter was corrected exactly
from the identity that everything ever born is either alive or dead.

**Traits could only ratchet upwards.** Drift was clipped at zero, so a trait at
zero could move in one direction only. Bodies steadily accumulated capabilities
nothing selected for, paying upkeep for all of them, until they starved. This
is what killed the first v2 run: population 460 → 1 over 105,000 ticks, 1,128
births against 5,612 deaths. Expressed traits now drift both ways and can be
lost; dormant ones need a separate, rarer mutation to switch on.

**Blinding used the absolute amount of predation.** One cell drifting slightly
predatory switched off photosynthesis for an entire large body. It is now the
*share* of the body committed to predation that costs you the light.

### Performance, measured rather than assumed

Profiling at 1,798 organisms: `sense()` 28% of runtime, `brain.step()` 22%,
with 2.5 million `atan2` calls per 60 ticks. Vectorising the sensing pass took
the run from **14 to 20 ticks/sec**. A numpy evaluation path for large networks
was added behind a test asserting it is bit-identical to the python one — that
test immediately caught a real defect, where neurons whose only inputs were
recurrent sat at level 0 and were silently never evaluated.

Brain scaling, measured on one core:

| neurons | synapses | evaluation | genome |
|---|---|---|---|
| 2,789 | 5,701 | 0.07 ms | 1 MB |
| 18,916 | 38,705 | 0.44 ms | 6.5 MB |
| 68,192 | 140,424 | 1.13 ms | 24 MB |
| 129,532 | 267,780 | 2.36 ms | 45 MB |

A fruit fly runs on about 135,000 neurons, so that scale is reachable — for a
population in the tens. It is not reachable for a population of thousands, and
100 million neurons is not reachable at all: one such genome would need roughly
34 GB. Big brains and big populations are mutually exclusive on one core.

### Duplication, and why it was not enough

Adding one neuron at a time grows a network linearly. At the observed rate that
is about 40,000 generations to reach 1,000 neurons — around 100 million ticks.
Genomes in biology do not grow that way; they grow by duplication, and the
copies diverge afterwards. Adding a duplication mutation changes the curve
completely:

| generation | without duplication | with duplication |
|---|---|---|
| 250 | 45 neurons | 90 |
| 500 | 53 | 1,086 |
| 1,000 | 65 | 3,248 |

**And it still did not produce big brains in the dish.** A dedicated run at low
population grew the largest brain from 37 to 58 neurons by tick 68,000, and
then lost it: by tick 74,000 the population was back to 37 neurons exactly.
The big-brained lineage went extinct.

Two reasons, and they are the interesting part:

**Duplication needs a seed.** It amplifies existing hidden structure, and there
was almost none — the mutation that creates the first hidden neuron was rare,
and a lone hidden neuron rarely survived long enough to be duplicated.

**Nothing rewarded the brain.** This is the real limit. Neurons cost energy and
bought nothing, because staying alive in this dish does not require
computation: sit in the light, divide when full. A larger network is pure
overhead, so selection removes it. Raising mutation rates only changes how fast
useless neurons appear, not whether they are kept.

Population stability turned out to be a precondition either way. At 5–20
organisms drift dominates and no lineage survives long enough to accumulate
anything; with shading softened so the population sits near its cap, mean brain
size began climbing steadily (37 → 41.8, largest 46) instead of collapsing.

### Open question this raises

The honest next experiment is not a bigger mutation rate. It is an environment
where computation pays — where an organism that remembers, anticipates or
discriminates outlives one that does not. Until such a pressure exists, every
number reported about brain size here is drift, and should be read as drift.

---

## Bugs that changed results

Recording these because each one silently produced plausible-looking output.

**Unseeded global RNG.** Mutation used the module-level `random`, which was
never seeded, so runs were not reproducible and two "identical" runs diverged
wildly. Two supposedly comparable runs reported 214 and 349 organisms at
similar ticks. Fixed by pinning `random.seed()` alongside the world's own RNG.

**Synchronised cohort death.** `max_age` was a constant, so the entire founding
population died within a few ticks of each other — 200 of 214 organisms in a
single step at tick 6,000, near-extinction from nothing but arithmetic.
Lifespan is now inherited with a wobble, which fixes the artefact and makes
lifespan itself an evolvable trait.

**A paradise with no selection.** The first balanced configuration had a single
core cell earning more light than it spent on upkeep, so nothing ever starved:
8,000 ticks, zero deaths. Selection needs a way to lose. Density-dependent
shading was added so crowding starves a patch and space becomes contested.

**Quadratic neighbour search.** The hand-rolled spatial grid degenerated when
organisms clustered — cells the size of the sight radius meant a dense cluster
put hundreds of candidates in every query, and the process was killed. Replaced
with a KD-tree and a hard cap on how many neighbours an organism attends to.

**Window recreated on resize.** Calling `set_mode()` from the resize handler
destroys and rebuilds the window under Wayland, which looks exactly like a
crash. The handler now adopts the surface SDL has already resized.

---

## Open questions

- Does the photosynthesis-then-predation ordering replicate across seeds, or
  was run 01 lucky?
- Does the predator–prey overshoot settle into a stable oscillation, or does it
  crash to extinction? Run 01 was restarted before this resolved.
- Does mean body size plateau, and if so at what cost ratio? `mass^0.75` is the
  knob that decides this.
- Do toxin cells reliably lag the first animal, or was that coincidence?
- Does a larger world produce more species, or just more of the same ones?
