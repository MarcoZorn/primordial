#!/usr/bin/env python3
"""Write LIVE.md from a run's telemetry, and optionally publish it.

    python status.py                     # print and write LIVE.md
    python status.py --push              # also commit and push it
    python status.py --watch 900 --push  # keep doing it every 15 minutes

This is the public face of the run: anyone on the repo can see what the dish is
doing right now without having it installed.
"""
import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone

BAR = "█"


def read(path, tail=4000):
    with open(path) as fh:
        rows = fh.readlines()[-tail:]
    return [json.loads(r) for r in rows if r.strip()]


def spark(values, width=48, height=6):
    """A tiny ascii chart, so the status page needs no images."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = max(1, len(values) // width)
    pts = values[::step][-width:]
    rows = []
    for level in range(height, 0, -1):
        line = ""
        for v in pts:
            frac = (v - lo) / span
            line += BAR if frac * height >= level - 0.5 else " "
        rows.append(f"{line}")
    return "\n".join(rows)


def first(rows, test):
    return next((r["tick"] for r in rows if test(r)), None)


def render(rows, run):
    now = rows[-1]
    started = now.get("wall", 0)
    cells = now["cells"]
    total_cells = sum(cells.values()) or 1
    age = f"{started / 3600:.1f} h of compute"

    lines = [
        "# primordial — live run status",
        "",
        f"**Run `{os.path.basename(run)}` · tick {now['tick']:,} · "
        f"day {now.get('day', 0):,} · {age}**",
        "",
        f"_Updated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. "
        "Generated from telemetry by `status.py`; nothing here is written by hand._",
        "",
        "## Right now",
        "",
        "| | |",
        "|---|---|",
        f"| organisms alive | **{now['pop']:,}** |",
        f"| plants | {now['plant']:,} |",
        f"| animals | {now['animal']:,} |",
        f"| microbes | {now['microbe']:,} |",
        f"| species | {now.get('species', '-')} |",
        f"| mean cells per body | {now['mass']:.2f} |",
        f"| largest body | {now['top_mass']} cells |",
        f"| mean hidden neurons | {now.get('hidden_neurons', 0):.1f} |",
        f"| largest brain (hidden) | {now.get('top_hidden_neurons', 0)} neurons |",
        f"| genome size incl. reserved slots | {now['top_neurons']} |",
        f"| deepest lineage | {now['depth']} generations |",
        f"| oldest living | {now['top_age']:,} ticks |",
        f"| carrion | {now.get('corpses', 0):,} |",
        f"| chirping | {now.get('chirping', 0):,} |",
        f"| total births | {now['births']:,} |",
        f"| total deaths | {now['deaths']:,} |",
        f"| weather | {now.get('event') or 'calm'} |",
        f"| daylight | {now.get('daylight', 1.0):.2f} |",
        f"| resumes | {now.get('resumes', 0)} |",
        "",
        "## Cell census",
        "",
        "| cell | count | share |",
        "|---|---|---|",
    ]
    for name, n in sorted(cells.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {n:,} | {100 * n / total_cells:.1f}% |")

    lines += ["", "## Milestones reached", "", "| event | tick |", "|---|---|"]
    marks = [
        ("first photo cell", lambda r: r["cells"]["photo"] > 0),
        ("first mover cell", lambda r: r["cells"]["mover"] > 0),
        ("first eater cell", lambda r: r["cells"]["eater"] > 0),
        ("first sensor cell", lambda r: r["cells"]["sensor"] > 0),
        ("first toxin cell", lambda r: r["cells"]["toxin"] > 0),
        ("first 3-cell body", lambda r: r["top_mass"] >= 3),
        ("first 10-cell body", lambda r: r["top_mass"] >= 10),
        ("first 25-cell body", lambda r: r["top_mass"] >= 25),
        ("first animal", lambda r: r["animal"] > 0),
        ("50+ hidden neurons", lambda r: r.get("top_hidden_neurons", 0) >= 50),
        ("100+ hidden neurons", lambda r: r.get("top_hidden_neurons", 0) >= 100),
    ]
    for label, test in marks:
        t = first(rows, test)
        lines.append(f"| {label} | {'not yet' if t is None else f'{t:,}'} |")

    for key, title in (("pop", "population"), ("mass", "mean cells per body"),
                       ("hidden_neurons", "mean hidden neurons")):
        lines += ["", f"### {title}", "", "```",
                  spark([r[key] for r in rows]), "```"]

    lines += [
        "",
        "---",
        "",
        "There is no fitness function in this simulation. Nothing above was a "
        "target; it is what survived.",
        "",
        f"Source: [`{os.path.basename(run)}/telemetry.jsonl`]"
        f"(runs/{os.path.basename(run)}/telemetry.jsonl)",
        "",
    ]
    return "\n".join(lines)


def publish(path):
    for cmd in (["git", "add", path, "-f"],
                ["git", "commit", "-m", f"status: {os.path.basename(path)} update",
                 "--author", "MarcoZorn <m@zorn.it>"],
                ["git", "push", "-q", "origin", "main"]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode and "nothing to commit" in (r.stdout + r.stderr):
            return False
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", default="runs/genesis")
    p.add_argument("--out", default="LIVE.md")
    p.add_argument("--push", action="store_true")
    p.add_argument("--watch", type=int, default=0, metavar="SECONDS")
    a = p.parse_args()
    telemetry = os.path.join(a.run, "telemetry.jsonl")
    while True:
        try:
            rows = read(telemetry)
            if rows:
                with open(a.out, "w") as fh:
                    fh.write(render(rows, a.run))
                if a.push:
                    publish(a.out)
                print(f"{datetime.now():%H:%M:%S} wrote {a.out} "
                      f"at tick {rows[-1]['tick']}", flush=True)
        except Exception as e:
            print("status error:", e, flush=True)
        if not a.watch:
            return
        time.sleep(a.watch)


if __name__ == "__main__":
    main()
