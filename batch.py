#!/usr/bin/env python3
"""Headless runs across several seeds.

One run is an anecdote. This is the thing that produces evidence: the same
configuration repeated over independent seeds, so a claim like "photosynthesis
always appears first" can be checked instead of asserted.

    python batch.py --seeds 8 --ticks 200000
"""
import argparse
import json
import os
import time

from primordial.config import Config
from primordial.evolution import Speciator
from primordial.genes import Innovations
from primordial.world import World


def run(seed, ticks, cfg, out_dir, every=600, quiet=False):
    cfg = Config(**{**cfg.__dict__, "seed": seed})
    world = World(cfg)
    world.seed_life(Innovations())
    spec = Speciator(cfg)
    path = os.path.join(out_dir, f"seed{seed}.jsonl")
    t0 = time.time()
    extinctions = 0
    with open(path, "w") as fh:
        for t in range(ticks):
            world.step()
            if not world.organisms:
                extinctions += 1
                world.seed_life(world.innov)
            if t % cfg.speciate_every == 0:
                spec.update(world.organisms, t)
            if t % every == 0:
                c = world.census()
                c["species"] = len(spec.species)
                c["wall"] = round(time.time() - t0, 1)
                c["extinctions"] = extinctions
                fh.write(json.dumps(c) + "\n")
                if not quiet and t % (every * 20) == 0:
                    print(f"  seed {seed} t={t:>8} pop={c['pop']:>4} "
                          f"plants={c['plant']:>4} animals={c['animal']:>4} "
                          f"cells={c['mass']:.2f} neurons={c['neurons']:.1f}",
                          flush=True)
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", type=int, default=6)
    p.add_argument("--ticks", type=int, default=200000)
    p.add_argument("--out", default="runs/batch")
    p.add_argument("--first-seed", type=int, default=1)
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cfg = Config()
    for s in range(a.first_seed, a.first_seed + a.seeds):
        print(f"seed {s}", flush=True)
        run(s, a.ticks, cfg, a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
