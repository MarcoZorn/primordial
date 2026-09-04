#!/usr/bin/env python3
"""Watch a running daemon. Read-only; open and close it whenever you like.

    python view.py --run runs/genesis
"""
import argparse

from primordial.viewer import Viewer


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", default="runs/genesis")
    p.add_argument("--scale", type=float, default=0.0)
    p.add_argument("--speed", type=int, default=4,
                   help="ticks the local preview runs per frame")
    a = p.parse_args()
    v = Viewer(run=a.run, scale=a.scale)
    v.fast = a.speed
    v.run_forever()


if __name__ == "__main__":
    main()
