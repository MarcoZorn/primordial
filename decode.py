#!/usr/bin/env python3
"""Does the chirp channel carry information?

The organisms have an acoustic output and ears. Nothing makes a chirp mean
anything - it is just a number an organism emits at a cost. The interesting
question is whether evolution has started using it, and that is a measurement,
not an opinion.

Two things are measured, both in bits:

  signal -> world   mutual information between what an organism emits and the
                    state of the world around it. If a chirp is louder when a
                    predator is near, the emission carries information about
                    predators whether or not anyone listens.

  signal -> response  mutual information between what an organism hears now and
                    what it does next. If hearing changes behaviour, the channel
                    is being read.

Communication in any defensible sense needs both: a signal correlated with the
world, and a receiver whose behaviour depends on it. Either alone is not enough.

A control is run alongside: the same statistic computed against shuffled
pairings. Real structure has to beat the shuffle, otherwise the number is just
the bias of a small sample.

    python decode.py --run runs/genesis --ticks 4000
"""
import argparse
import math
import random
from collections import Counter

from primordial import checkpoint


def entropy(counts):
    n = sum(counts.values())
    if not n:
        return 0.0
    return -sum((c / n) * math.log2(c / n) for c in counts.values() if c)


def mutual_information(pairs):
    """I(X;Y) over discrete samples, in bits."""
    if not pairs:
        return 0.0
    xs = Counter(x for x, _ in pairs)
    ys = Counter(y for _, y in pairs)
    joint = Counter(pairs)
    return max(0.0, entropy(xs) + entropy(ys) - entropy(joint))


def shuffled(pairs, rng):
    ys = [y for _, y in pairs]
    rng.shuffle(ys)
    return list(zip((x for x, _ in pairs), ys))


def bucket(v, n=4, lo=0.0, hi=1.0):
    if hi <= lo:
        return 0
    return min(n - 1, max(0, int((v - lo) / (hi - lo) * n)))


def collect(world, ticks, rays):
    """Walk the world forward, recording what each organism emits, what the
    world around it looks like, what it hears, and what it does next."""
    emit_world, hear_act = [], []
    prev_heard = {}
    for _ in range(ticks):
        world.step()
        for o in world.organisms:
            if not o.alive:
                continue
            s = o.sensors
            if not s:
                continue
            seen_near = max(s[i * 3] for i in range(rays))
            seen_toxic = max(s[i * 3 + 2] for i in range(rays))
            heard = max(s[rays * 3 + i] for i in range(rays))

            # what the world looks like right now, coarsely
            state = (bucket(seen_near, 3), bucket(seen_toxic, 2),
                     1 if o.st["eaters"] > 0.25 else 0)
            emit_world.append((bucket(o.chirp, 4), state))

            # what it heard last tick against what it is doing now
            was = prev_heard.get(id(o))
            if was is not None:
                turn = o.out[0] - o.out[1]
                action = (bucket(turn, 3, -2.0, 2.0), bucket(o.out[2], 2, -1.0, 1.0))
                hear_act.append((was, action))
            prev_heard[id(o)] = bucket(heard, 4)
    return emit_world, hear_act


def report(name, pairs, rng, trials=8):
    if len(pairs) < 200:
        return f"{name:<22} not enough data ({len(pairs)} samples)"
    real = mutual_information(pairs)
    controls = [mutual_information(shuffled(pairs, rng)) for _ in range(trials)]
    base = sum(controls) / len(controls)
    lift = real - base
    verdict = ("nothing above chance" if lift < 0.005 else
               "weak structure" if lift < 0.02 else
               "clear structure - worth looking at")
    return (f"{name:<22} {real:.4f} bits   shuffled {base:.4f}   "
            f"lift {lift:+.4f}   {verdict}   n={len(pairs)}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", default="runs/genesis")
    p.add_argument("--ticks", type=int, default=4000)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()

    state, path = checkpoint.newest(f"{a.run}/state.pkl.gz")
    if not state:
        raise SystemExit(f"no checkpoint in {a.run}")
    world = state["world"]
    rng = random.Random(a.seed)
    print(f"{path}  tick {world.tick:,}  {len(world.organisms)} organisms")
    chirpers = sum(1 for o in world.organisms if o.chirp > 0.15)
    print(f"chirping right now: {chirpers}\n")
    print(f"replaying {a.ticks} ticks from the checkpoint (the run is untouched)\n")

    emit_world, hear_act = collect(world, a.ticks, world.cfg.n_rays)
    print(report("signal -> world", emit_world, rng))
    print(report("heard -> response", hear_act, rng))
    print("\nBoth need to beat their shuffled control before the word "
          "'communication' means anything.")


if __name__ == "__main__":
    main()
