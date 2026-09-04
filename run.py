#!/usr/bin/env python3
"""A throwaway dish in a single process - nothing is checkpointed.

For a run you care about use daemon.py and view.py instead.
"""
import argparse

from primordial.config import Config
from primordial.viewer import Viewer


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=Config.seed)
    p.add_argument("--pop", type=int, default=Config.start_pop)
    p.add_argument("--world", type=int, nargs=2, metavar=("W", "H"),
                   default=[Config.world_w, Config.world_h])
    p.add_argument("--max-pop", type=int, default=Config.max_pop)
    p.add_argument("--scale", type=float, default=0.0)
    a = p.parse_args()
    cfg = Config(seed=a.seed, start_pop=a.pop, max_pop=a.max_pop,
                 world_w=a.world[0], world_h=a.world[1])
    Viewer(cfg=cfg, scale=a.scale).run_forever()


if __name__ == "__main__":
    main()
