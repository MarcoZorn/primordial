"""The dish. One continuous world, no generations, no resets.

Organisms feed, move, eat each other and divide whenever they can afford to.
Nothing is scored and nothing is culled by the simulation: a lineage continues
because its members kept paying their energy bill long enough to split. That is
the whole selection mechanism.
"""
import math
import random

import numpy as np
from scipy.spatial import cKDTree

from .body import ARMOR, Body, EATER, MOVER, PHOTO, SENSOR, STORE, TOXIN
from .brain import Brain
from .genes import Genome

N_OUTPUTS = 3          # left thruster, right thruster, urge to divide


def n_inputs(cfg):
    return cfg.n_rays * 3 + 6


class Organism:
    __slots__ = ("genome", "body", "brain", "st", "x", "y", "a", "v", "energy",
                 "age", "alive", "sensors", "out", "gen", "eaten", "born",
                 "lifespan")

    def __init__(self, genome, body, x, y, a, energy, cfg, gen=0, lifespan=None):
        self.genome = genome
        self.body = body
        self.brain = Brain(genome)
        self.st = body.stats(cfg)
        self.x, self.y, self.a = x, y, a
        self.v = 0.0
        self.energy = energy
        self.age = 0
        self.alive = True
        self.gen = gen
        self.eaten = 0.0
        self.born = 0
        # inherited with a wobble, so cohorts do not all die on the same tick
        self.lifespan = lifespan or cfg.max_age
        self.sensors = [0.0] * n_inputs(cfg)
        self.out = [0.0] * N_OUTPUTS

    @property
    def kingdom(self):
        return self.body.kingdom()


class World:
    def __init__(self, cfg, seed=None):
        self.cfg = cfg
        seed = cfg.seed if seed is None else seed
        self.rng = random.Random(seed)
        random.seed(seed)          # mutation uses the module rng; pin it too
        self.tick = 0
        self.next_id = 0
        self.births = 0
        self.deaths = 0
        self.organisms = []
        self.innov = None      # set by the driver so ids stay consistent
        self.event = None
        self.log = []
        self.obstacles = [
            (self.rng.uniform(0, cfg.world_w), self.rng.uniform(0, cfg.world_h),
             self.rng.uniform(*cfg.obstacle_r))
            for _ in range(cfg.n_obstacles)
        ]

    def seed_life(self, innov):
        """Everything starts as one undifferentiated cell with a random brain."""
        self.innov = innov
        cfg = self.cfg
        proto = Genome.minimal(n_inputs(cfg), N_OUTPUTS, innov, cfg)
        for _ in range(cfg.start_pop):
            g = proto.copy().mutate(innov, cfg)
            self.organisms.append(Organism(
                g, Body(),
                self.rng.uniform(0, cfg.world_w), self.rng.uniform(0, cfg.world_h),
                self.rng.uniform(0, 2 * math.pi), cfg.start_energy, cfg,
                lifespan=self.jitter_lifespan(cfg.max_age)))

    def jitter_lifespan(self, base):
        j = self.cfg.lifespan_jitter
        return max(400.0, base * self.rng.gauss(1.0, j))

    def clear_obstacles(self, o):
        """Push an organism back out of anything solid it walked into."""
        r = o.body.radius(self.cfg)
        for ox, oy, orad in self.obstacles:
            dx, dy = o.x - ox, o.y - oy
            d = math.hypot(dx, dy)
            if d < orad + r and d > 1e-6:
                push = (orad + r - d) / d
                o.x += dx * push
                o.y += dy * push

    # --- weather ---

    def maybe_event(self):
        cfg = self.cfg
        if self.event:
            self.event["left"] -= 1
            if self.event["left"] <= 0:
                self.event = None
            return
        if self.rng.random() > cfg.p_event:
            return
        kind = self.rng.choice(("drought", "bloom", "meteor"))
        if kind == "meteor":
            x = self.rng.uniform(0, cfg.world_w)
            y = self.rng.uniform(0, cfg.world_h)
            r = self.rng.uniform(*cfg.meteor_r)
            hit = 0
            for o in self.organisms:
                if math.hypot(o.x - x, o.y - y) < r:
                    o.alive = False
                    self.deaths += 1
                    hit += 1
            self.event = {"kind": kind, "left": 90, "light": 1.0, "x": x, "y": y, "r": r}
            self.note(f"meteor wiped {hit}")
            return
        light = 0.35 if kind == "drought" else 1.9
        self.event = {"kind": kind, "left": self.rng.randint(*cfg.event_len),
                      "light": light}
        self.note(kind)

    def note(self, text):
        self.log.append((self.tick, text))
        del self.log[:-40]

    @property
    def light_mult(self):
        return self.event["light"] if self.event else 1.0

    # --- perception ---

    def sense(self, o, neighbours):
        cfg = self.cfg
        s = [0.0] * n_inputs(cfg)
        sight = o.st["sight"]
        half = cfg.fov / 2
        wedge = cfg.fov / cfg.n_rays
        for other, d in neighbours:
            if d > sight or d < 1e-6:
                continue
            dx, dy = other.x - o.x, other.y - o.y
            ang = (math.atan2(dy, dx) - o.a + math.pi) % (2 * math.pi) - math.pi
            if abs(ang) > half:
                continue
            r = min(cfg.n_rays - 1, int((ang + half) / wedge))
            prox = 1.0 - d / sight
            base = r * 3
            if prox > s[base]:
                s[base] = prox
                s[base + 1] = min(1.0, other.energy / 400.0)   # how rich it looks
                s[base + 2] = other.st["toxin"]                 # how bad it tastes
        b = cfg.n_rays * 3
        s[b] = 1.0 - min(1.0, o.x / sight)
        s[b + 1] = 1.0 - min(1.0, (cfg.world_w - o.x) / sight)
        s[b + 2] = 1.0 - min(1.0, o.y / sight)
        s[b + 3] = 1.0 - min(1.0, (cfg.world_h - o.y) / sight)
        s[b + 4] = min(1.0, o.energy / o.st["capacity"])
        s[b + 5] = min(1.0, o.age / o.lifespan)
        o.sensors = s
        return s

    # --- the tick ---

    def neighbourhood(self):
        """Nearest-k neighbours for everyone, in one C-speed pass.

        Attention is deliberately capped: an organism reacts to the handful of
        things closest to it, which is both cheap and closer to what a real
        sensor does than seeing every object in range.
        """
        orgs = self.organisms
        n = len(orgs)
        pts = np.array([(o.x, o.y) for o in orgs]) if n else np.zeros((0, 2))
        tree = cKDTree(pts)
        k = min(self.cfg.neighbours + 1, n)
        dist, idx = tree.query(pts, k=k)
        if k == 1:
            dist, idx = dist.reshape(n, 1), idx.reshape(n, 1)
        return dist, idx

    def step(self):
        cfg = self.cfg
        if not self.organisms:
            self.tick += 1
            return
        self.maybe_event()
        orgs = self.organisms
        dist, idx = self.neighbourhood()
        newborns = []
        for i, o in enumerate(orgs):
            if not o.alive:
                continue
            near = [(orgs[j], d) for j, d in zip(idx[i][1:], dist[i][1:])
                    if orgs[j].alive and d != np.inf]
            left, right, split = o.brain.step(self.sense(o, near))
            o.out = [left, right, split]

            speed = o.st["speed"]
            if speed:
                o.a += (right - left) * o.st["turn"]
                o.v = max(0.0, min(speed, (left + right) / 2 * speed))
                o.x = min(cfg.world_w, max(0.0, o.x + math.cos(o.a) * o.v))
                o.y = min(cfg.world_h, max(0.0, o.y + math.sin(o.a) * o.v))
                self.clear_obstacles(o)

            self.feed(o, near)
            self.bite(o, near)

            o.energy -= o.st["drain"] + o.v * cfg.move_cost
            o.energy = min(o.energy, o.st["capacity"] * 2.0)
            o.age += 1
            if o.energy <= 0 or o.age > o.lifespan:
                o.alive = False
                self.deaths += 1
                continue
            if (split > 0 and o.energy >= o.st["capacity"] * cfg.split_energy
                    and len(self.organisms) + len(newborns) < cfg.max_pop):
                newborns.append(self.divide(o, near))

        self.organisms = [o for o in self.organisms if o.alive] + newborns
        self.births += len(newborns)
        self.tick += 1

    def feed(self, o, near):
        """Photosynthesis, minus whatever the neighbours are shading out."""
        light = o.st["light"]
        if light <= 0:
            return
        cfg = self.cfg
        crowd = sum(other.body.mass for other, d in near if d < cfg.shade_radius)
        o.energy += light * self.light_mult / (1.0 + cfg.shade_factor * crowd)

    def bite(self, o, near):
        eaters = o.st["eaters"]
        if not eaters:
            return
        cfg = self.cfg
        reach = o.st["reach"]
        for other, d in near:
            if not other.alive or d > reach + other.body.radius(cfg):
                continue
            bite = cfg.bite_rate * eaters * (1.0 - other.st["armor"])
            bite = min(bite, other.energy)
            other.energy -= bite
            # toxins hurt the diner, armour on the diner does not help
            o.energy += bite * (1.0 - other.st["toxin"])
            o.energy -= bite * other.st["toxin"]
            o.eaten += bite
            if other.energy <= 0:
                other.alive = False
                self.deaths += 1
            break

    def divide(self, o, near):
        """Mitosis. The child is a mutated copy; sometimes it borrows genes from
        a neighbour, which is as close to sex as this dish gets."""
        cfg = self.cfg
        genome = o.genome
        mate = None
        if self.rng.random() < cfg.p_sex:
            options = [x for x, d in near if x.alive and d < cfg.mate_radius]
            if options:
                mate = self.rng.choice(options)
        child_genome = (Genome.crossover(genome, mate.genome, cfg) if mate
                        else genome.copy())
        child_genome.mutate(self.innov, cfg)
        child_body = o.body.copy().mutate(cfg)

        share = o.energy * (1.0 - cfg.split_cost) / 2.0
        o.energy = share
        o.born += 1
        a = self.rng.uniform(0, 2 * math.pi)
        d = o.body.radius(cfg) + cfg.cell_r * 2
        return Organism(
            child_genome, child_body,
            min(cfg.world_w, max(0.0, o.x + math.cos(a) * d)),
            min(cfg.world_h, max(0.0, o.y + math.sin(a) * d)),
            self.rng.uniform(0, 2 * math.pi), share, cfg, gen=o.gen + 1,
            lifespan=self.jitter_lifespan(o.lifespan))

    # --- readouts for the UI ---

    def census(self):
        """Everything the dish knows about itself, in one dict."""
        from .body import TYPE_NAME
        c = {"plant": 0, "animal": 0, "microbe": 0}
        cells = {name: 0 for name in TYPE_NAME.values()}
        mass = neurons = syn = gen = 0
        top_mass = top_neurons = top_age = 0
        energy = 0.0
        for o in self.organisms:
            c[o.kingdom] += 1
            mass += o.body.mass
            n, e = o.genome.complexity()
            neurons += n
            syn += e
            energy += o.energy
            gen = max(gen, o.gen)
            top_mass = max(top_mass, o.body.mass)
            top_neurons = max(top_neurons, n)
            top_age = max(top_age, o.age)
            for kind in o.body.cells.values():
                cells[TYPE_NAME[kind]] += 1
        n = max(len(self.organisms), 1)
        c.update(tick=self.tick, pop=len(self.organisms),
                 mass=mass / n, neurons=neurons / n, synapses=syn / n,
                 depth=gen, energy=energy / n, cells=cells,
                 top_mass=top_mass, top_neurons=top_neurons, top_age=top_age,
                 births=self.births, deaths=self.deaths,
                 event=self.event["kind"] if self.event else None)
        return c
