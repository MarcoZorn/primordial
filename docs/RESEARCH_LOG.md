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
