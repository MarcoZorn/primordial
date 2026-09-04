#!/usr/bin/env python3
"""Turn telemetry into numbers and a figure.

    python analyse.py runs/batch/*.jsonl
    python analyse.py runs/telemetry.jsonl
"""
import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(path):
    with open(path) as fh:
        return [json.loads(l) for l in fh if l.strip()]


def first_tick(rows, test):
    return next((r["tick"] for r in rows if test(r)), None)


def summarise(path, rows):
    last = rows[-1]
    cells = last["cells"]
    return {
        "run": os.path.basename(path),
        "ticks": last["tick"],
        "final pop": last["pop"],
        "plants": last["plant"],
        "animals": last["animal"],
        "avg cells": round(last["mass"], 2),
        "largest body": last["top_mass"],
        "largest brain": last["top_neurons"],
        "species": last.get("species"),
        "first photo cell": first_tick(rows, lambda r: r["cells"]["photo"] > 0),
        "first mover": first_tick(rows, lambda r: r["cells"]["mover"] > 0),
        "first animal": first_tick(rows, lambda r: r["animal"] > 0),
        "first 3-cell body": first_tick(rows, lambda r: r["top_mass"] >= 3),
        "extinctions": last.get("extinctions", 0),
        "toxin cells": cells.get("toxin", 0),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("paths", nargs="+")
    p.add_argument("--out", default="docs/analysis.png")
    a = p.parse_args()

    runs = {path: load(path) for path in a.paths}
    runs = {k: v for k, v in runs.items() if v}
    keys = list(summarise(*next(iter(runs.items()))))
    width = max(len(k) for k in keys) + 2
    for path, rows in runs.items():
        print()
        for k, v in summarise(path, rows).items():
            print(f"{k:<{width}}{v}")

    fig, ax = plt.subplots(2, 2, figsize=(12, 7))
    panels = [
        ("pop", "population", ax[0][0]),
        ("mass", "mean cells per organism", ax[0][1]),
        ("neurons", "mean neurons per organism", ax[1][0]),
        ("animal", "organisms classed as animals", ax[1][1]),
    ]
    for key, title, axis in panels:
        for path, rows in runs.items():
            axis.plot([r["tick"] for r in rows], [r[key] for r in rows],
                      lw=1.0, label=os.path.basename(path))
        axis.set_title(title, fontsize=10)
        axis.set_xlabel("tick", fontsize=8)
        axis.grid(alpha=0.2)
    if len(runs) > 1:
        ax[0][0].legend(fontsize=6)
    fig.tight_layout()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    fig.savefig(a.out, dpi=130)
    print("\nwrote", a.out)


if __name__ == "__main__":
    main()
