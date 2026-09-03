#!/usr/bin/env python3
import argparse

from primordial.app import App, headless
from primordial.config import Config
from primordial.store import save


def main():
    p = argparse.ArgumentParser(description="primordial - evolve brains in a dish")
    p.add_argument("--headless", type=int, metavar="GENERATIONS",
                   help="run without a window for N generations")
    p.add_argument("--pop", type=int, default=Config.pop_size)
    p.add_argument("--ticks", type=int, default=Config.ticks)
    p.add_argument("--out", default="runs/best.json")
    a = p.parse_args()

    cfg = Config(pop_size=a.pop, ticks=a.ticks)
    if a.headless:
        pop = headless(cfg, a.headless)
        print("saved", save(pop.best, a.out))
    else:
        App(cfg).run()


if __name__ == "__main__":
    main()
