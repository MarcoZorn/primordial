#!/usr/bin/env python3
"""The research run. Headless, checkpointed, meant to survive months.

    python daemon.py                     # start or resume runs/research
    python daemon.py --run runs/other    # a different run directory
    python daemon.py --fresh             # discard and start over

It owns the simulation. Kill it, reboot, start it again and it picks up from
the last checkpoint. Open `view.py` whenever you want to watch; the viewer is
read-only and can come and go without touching the run.
"""
import argparse
import atexit
import errno
import json
import os
import signal
import time

from primordial import checkpoint
from primordial.config import Config
from primordial.evolution import Speciator
from primordial.genes import Innovations
from primordial.world import World

STOP = False


def _stop(signum, frame):
    global STOP
    STOP = True


def take_lock(directory):
    """Refuse to start if another daemon already owns this run.

    Two daemons on one directory step separate copies of the world and
    overwrite each other's checkpoints, which quietly destroys the run.
    """
    path = os.path.join(directory, "daemon.pid")
    os.makedirs(directory, exist_ok=True)
    if os.path.exists(path):
        try:
            pid = int(open(path).read().strip())
            os.kill(pid, 0)
        except (ValueError, OSError) as e:
            if isinstance(e, OSError) and e.errno not in (errno.ESRCH, errno.EPERM):
                raise
            if not isinstance(e, OSError) or e.errno == errno.ESRCH:
                os.unlink(path)          # stale, the old process is gone
            else:
                raise SystemExit(f"another daemon owns {directory} (pid {pid})")
        else:
            raise SystemExit(f"another daemon is already running on {directory} "
                             f"(pid {pid}) - stop it first")
    with open(path, "w") as fh:
        fh.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(path) and os.unlink(path))


class Run:
    def __init__(self, directory, cfg=None, fresh=False):
        take_lock(directory)
        self.dir = directory
        self.ckpt = os.path.join(directory, "state.pkl.gz")
        self.telemetry = os.path.join(directory, "telemetry.jsonl")
        os.makedirs(directory, exist_ok=True)
        state = None if fresh else checkpoint.newest(self.ckpt)[0]
        if state:
            self.world = state["world"]
            self.spec = state["spec"]
            self.innov = state["innov"]
            self.cfg = self.world.cfg
            self.started = state["extra"].get("started", time.time())
            self.resumes = state["extra"].get("resumes", 0) + 1
            print(f"resumed {self.ckpt} at tick {self.world.tick} "
                  f"({len(self.world.organisms)} alive, resume #{self.resumes})")
        else:
            self.cfg = cfg or Config()
            self.world = World(self.cfg)
            self.innov = Innovations()
            self.world.seed_life(self.innov)
            self.spec = Speciator(self.cfg)
            self.spec.update(self.world.organisms, 0)
            self.started = time.time()
            self.resumes = 0
            print(f"new run in {self.dir}")

    def save(self):
        checkpoint.rotate(self.ckpt)
        checkpoint.save(self.ckpt, self.world, self.spec, self.innov,
                        extra={"started": self.started, "resumes": self.resumes})

    def record(self):
        c = self.world.census()
        c["species"] = len(self.spec.species)
        c["wall"] = round(time.time() - self.started, 1)
        c["resumes"] = self.resumes
        with open(self.telemetry, "a") as fh:
            fh.write(json.dumps(c) + "\n")
        return c

    def loop(self, save_every, log_every, report_every):
        last_report = 0
        while not STOP:
            self.world.step()
            t = self.world.tick
            if not self.world.organisms:
                self.world.seed_life(self.innov)
                self.world.note("reseeded after total extinction")
            if t % self.cfg.speciate_every == 0:
                self.spec.update(self.world.organisms, t)
            if t % log_every == 0:
                c = self.record()
                if t - last_report >= report_every:
                    last_report = t
                    print(f"t={t:>10} day={c['day']:>6} pop={c['pop']:>5} "
                          f"pl={c['plant']:>5} an={c['animal']:>5} "
                          f"cells={c['mass']:.2f} neur={c['neurons']:.1f} "
                          f"sp={c['species']:>3} carrion={c['corpses']:>4}",
                          flush=True)
            if t % save_every == 0:
                self.save()
        self.save()
        print(f"stopped and checkpointed at tick {self.world.tick}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", default="runs/research")
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--save-every", type=int, default=4000)
    p.add_argument("--log-every", type=int, default=1000)
    p.add_argument("--report-every", type=int, default=20000)
    p.add_argument("--world", type=int, nargs=2, default=None)
    p.add_argument("--pop", type=int, default=None)
    p.add_argument("--max-pop", type=int, default=None)
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override a config value; applies to a resumed run too, "
                        "which is how the world gets tuned without losing it")
    a = p.parse_args()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    cfg = Config()
    if a.world:
        cfg.world_w, cfg.world_h = a.world
    if a.pop:
        cfg.start_pop = a.pop
    if a.max_pop:
        cfg.max_pop = a.max_pop
    run = Run(a.run, cfg, fresh=a.fresh)
    for pair in a.set:
        key, _, value = pair.partition("=")
        if not hasattr(run.cfg, key):
            raise SystemExit(f"no such config key: {key}")
        old = getattr(run.cfg, key)
        setattr(run.cfg, key, type(old)(value) if not isinstance(old, bool)
                else value.lower() in ("1", "true", "yes"))
        print(f"config {key}: {old} -> {getattr(run.cfg, key)}")
        run.world.note(f"{key} {old} -> {getattr(run.cfg, key)}")
    run.loop(a.save_every, a.log_every, a.report_every)


if __name__ == "__main__":
    main()
