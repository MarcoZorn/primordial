#!/usr/bin/env python3
"""Upgrade a paused run to the current engine, in place.

The reserved input, output and trait slots exist so that adding a capability
later does not invalidate a run. This applies that idea retroactively once: it
widens every genome and every cell to the current pool sizes without touching a
single existing connection, weight or trait value. Every organism keeps its
ancestry, its brain and its body; it just gains empty slots for things that do
not exist yet.

    genesis pause
    python migrate.py --run runs/genesis
    genesis resume
"""
import argparse

from primordial import checkpoint
from primordial.body import N_TRAITS
from primordial.brain import Brain
from primordial.genes import INPUT, OUTPUT


def widen(run, dry=False):
    state, path = checkpoint.newest(f"{run}/state.pkl.gz")
    if not state:
        raise SystemExit(f"no checkpoint in {run}")
    world, innov, cfg = state["world"], state["innov"], state["world"].cfg
    orgs = world.organisms
    if not orgs:
        raise SystemExit("no organisms to migrate")

    sample = orgs[0].genome
    have_in = len(sample.ids(INPUT))
    have_out = len(sample.ids(OUTPUT))
    want_in, want_out = cfg.max_inputs, cfg.max_outputs
    print(f"tick {world.tick:,}   {len(orgs)} organisms")
    print(f"inputs  {have_in} -> {want_in}")
    print(f"outputs {have_out} -> {want_out}")
    print(f"traits per cell -> {N_TRAITS}")
    if have_in > want_in or have_out > want_out:
        raise SystemExit("this run is already wider than the current pools")
    if dry:
        return

    # one shared block of ids, so every genome agrees on which node is which -
    # crossover between them is meaningless otherwise
    new_inputs = [innov.node() for _ in range(want_in - have_in)]
    new_outputs = [innov.node() for _ in range(want_out - have_out)]

    for o in orgs:
        g = o.genome
        for nid in new_inputs:
            g.nodes[nid] = INPUT
        for nid in new_outputs:
            g.nodes[nid] = OUTPUT
        for cell in o.body.cells.values():
            if len(cell) < N_TRAITS:
                cell.extend([0.0] * (N_TRAITS - len(cell)))
        o.brain = Brain(g)
        o.sensors = [0.0] * len(o.brain.inputs)
        o.out = [0.0] * len(o.brain.outputs)

    for s in getattr(state.get("spec"), "species", {}).values():
        if s.members:
            s.rep = s.members[0].genome

    checkpoint.rotate(path)
    checkpoint.save(path, world, state["spec"], innov, extra=state["extra"])
    g = orgs[0].genome
    print(f"migrated: genomes now {len(g.ids(INPUT))} in / {len(g.ids(OUTPUT))} out, "
          f"{len(g.conns)} connections kept")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", default="runs/genesis")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    widen(a.run, a.dry_run)


if __name__ == "__main__":
    main()
