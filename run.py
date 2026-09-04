#!/usr/bin/env python3
import argparse

from primordial.app import App
from primordial.config import Config


def main():
    p = argparse.ArgumentParser(description="primordial - an evolving dish")
    p.add_argument("--seed", type=int, default=Config.seed)
    p.add_argument("--pop", type=int, default=Config.start_pop)
    p.add_argument("--scale", type=float, default=0.0,
                   help="UI text scale (default: from screen size)")
    a = p.parse_args()
    App(Config(seed=a.seed, start_pop=a.pop, ui_scale=a.scale)).run()


if __name__ == "__main__":
    main()
