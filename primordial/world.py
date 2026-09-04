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

from .body import Body
from .brain import Brain
from .genes import Genome

N_OUTPUTS = 4          # left thruster, right thruster, urge to divide, chirp


def n_inputs(cfg):
    # per ray: what it sees (near, rich, toxic) and what it hears (chirp)
    # then: 4 walls, energy, age, own speed, own turn rate
    return cfg.n_rays * 4 + 8


class Organism:
    __slots__ = ("genome", "body", "brain", "st", "x", "y", "a", "v", "w",
                 "energy", "age", "alive", "sensors", "out", "gen", "eaten",
                 "born", "lifespan", "chirp", "upkeep")

    def __init__(self, genome, body, x, y, a, energy, cfg, gen=0, lifespan=None):
        self.genome = genome
        self.body = body
        self.brain = Brain(genome)
        self.st = body.stats(cfg)
        hidden = len(genome.nodes) - len(self.brain.inputs) - len(self.brain.bias) \
            - len(self.brain.outputs)
        self.upkeep = (self.st["drain"]
                       + cfg.neuron_cost * max(0, hidden)
                       + cfg.synapse_cost * len(self.brain.edges))
        self.x, self.y, self.a = x, y, a
        self.v = 0.0
        self.w = 0.0
        self.chirp = 0.0
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

    # the network and the current sensor reading are both derived from state
    # that is already saved, so a checkpoint does not carry them
    def __getstate__(self):
        return {k: getattr(self, k) for k in self.__slots__
                if k not in ("brain", "sensors")}

    def __setstate__(self, state):
        for k, v in state.items():
            setattr(self, k, v)
        self.brain = Brain(self.genome)
        self.sensors = [0.0] * len(self.brain.inputs)
        if not hasattr(self, "upkeep"):
            self.upkeep = self.st["drain"]


class _Husk:
    """Stand-in body so a corpse can be treated like anything else in range."""

    def __init__(self, mass):
        self.mass = mass

    def radius(self, cfg):
        return cfg.cell_r * math.sqrt(self.mass)


class Corpse:
    """Dead biomass.

    Heterotrophy has to start somewhere. Growing an eater cell switches off
    photosynthesis for the whole body, so the first eater in a lineage is
    normally a death sentence - it cannot hunt before it starves. Carrion is
    the bridge: scavenging something that cannot run away is a far shorter
    evolutionary step than hunting something that can.
    """
    __slots__ = ("x", "y", "energy", "alive", "st", "body", "age", "chirp")

    def __init__(self, x, y, energy, mass):
        self.x, self.y = x, y
        self.energy = energy
        self.alive = True
        self.age = 0
        self.st = {"toxin": 0.0, "armor": 0.0}
        self.chirp = 0.0
        self.body = _Husk(mass)


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
        self.corpses = []
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
            ang = self.rng.uniform(0, 2 * math.pi)
            rad = self.rng.uniform(0, cfg.seed_radius)
            self.organisms.append(Organism(
                g, Body(),
                cfg.world_w / 2 * (1 + rad * math.cos(ang)),
                cfg.world_h / 2 * (1 + rad * math.sin(ang)),
                self.rng.uniform(0, 2 * math.pi), cfg.start_energy, cfg,
                lifespan=self.jitter_lifespan(cfg.max_age)))

    def kill(self, o):
        # idempotent on purpose: a dead organism stays in the list until the end
        # of the tick, so several predators can reach it after it has already
        # died. Counting that twice inflates the toll and, far worse, drops a
        # second corpse - which quietly creates energy out of nothing.
        if not o.alive:
            return
        o.alive = False
        self.deaths += 1
        if len(self.corpses) < self.cfg.max_corpses:
            cfg = self.cfg
            # a body can only give back what it took in and did not spend:
            # unspent energy, plus what was invested in building its cells,
            # minus what decomposition loses. Never more.
            invested = cfg.cell_build * o.body.mass
            left = (max(0.0, o.energy) + invested) * cfg.corpse_keep
            self.corpses.append(Corpse(o.x, o.y, left, o.body.mass))

    # --- the sky ---

    @property
    def daylight(self):
        """Smooth day/night cycle. Nothing photosynthesises much at midnight."""
        cfg = self.cfg
        phase = math.cos(2 * math.pi * self.tick / cfg.day_len)
        return cfg.night_light + (1.0 - cfg.night_light) * 0.5 * (1.0 + phase)

    @property
    def is_night(self):
        return self.daylight < (1.0 + self.cfg.night_light) / 2

    @property
    def day(self):
        return self.tick // self.cfg.day_len

    def light_centre(self):
        """The fertile zone wanders, so no patch of ground stays good forever."""
        cfg = self.cfg
        a = 2 * math.pi * self.tick / cfg.drift_len
        return (cfg.world_w * (0.5 + cfg.drift_amp * math.cos(a)),
                cfg.world_h * (0.5 + cfg.drift_amp * math.sin(a)))

    def season(self):
        """How tight the fertile zone is right now."""
        cfg = self.cfg
        swing = math.sin(2 * math.pi * self.tick / cfg.season_len)
        return cfg.light_spread * (1.0 + cfg.season_swing * swing)

    def light_at(self, x, y):
        """Radial light field around the current fertile centre."""
        cfg = self.cfg
        cx, cy = self.light_centre()
        dx = (x - cx) / (cfg.world_w / 2)
        dy = (y - cy) / (cfg.world_h / 2)
        return max(cfg.light_edge,
                   math.exp(-(dx * dx + dy * dy) / max(0.02, self.season())))

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
                if o.alive and math.hypot(o.x - x, o.y - y) < r:
                    self.kill(o)
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

    def sense_all(self, things, dist, idx):
        """Fill in every organism's senses in one vectorised pass.

        Done per organism this was the single most expensive thing in the
        simulation - a couple of million atan2 calls a second. The work is
        identical, it just happens in numpy instead of in the interpreter.
        """
        cfg = self.cfg
        orgs = self.organisms
        n = len(orgs)
        rays = cfg.n_rays
        half = cfg.fov / 2
        wedge = cfg.fov / rays
        width = n_inputs(cfg)
        out = np.zeros((n, width))
        if n == 0:
            return out

        px = np.fromiter((o.x for o in orgs), float, n)
        py = np.fromiter((o.y for o in orgs), float, n)
        pa = np.fromiter((o.a for o in orgs), float, n)
        sight = np.fromiter((o.st["sight"] for o in orgs), float, n)

        tx = np.fromiter((t.x for t in things), float, len(things))
        ty = np.fromiter((t.y for t in things), float, len(things))
        te = np.fromiter((t.energy for t in things), float, len(things))
        tt = np.fromiter((t.st["toxin"] for t in things), float, len(things))
        tc = np.fromiter((t.chirp for t in things), float, len(things))

        nb = idx[:, 1:]                      # column 0 is the organism itself
        d = dist[:, 1:]
        dx = tx[nb] - px[:, None]
        dy = ty[nb] - py[:, None]
        ang = (np.arctan2(dy, dx) - pa[:, None] + np.pi) % (2 * np.pi) - np.pi

        rows = np.repeat(np.arange(n), nb.shape[1])
        ray = np.clip(((ang + half) / wedge).astype(np.int64), 0, rays - 1).ravel()
        flat = rows * rays + ray
        infield = (np.abs(ang) <= half).ravel() & np.isfinite(d).ravel()

        # sight: keep, per ray, whatever is closest. Sorting by proximity and
        # scattering in that order leaves the nearest thing written last.
        seen = infield & (d <= sight[:, None]).ravel()
        prox = np.where(seen, 1.0 - d.ravel() / np.repeat(sight, nb.shape[1]), 0.0)
        order = np.argsort(prox[seen], kind="stable")
        sel = np.nonzero(seen)[0][order]
        near = np.zeros(n * rays)
        rich = np.zeros(n * rays)
        toxic = np.zeros(n * rays)
        near[flat[sel]] = prox[sel]
        rich[flat[sel]] = np.minimum(1.0, te[nb.ravel()[sel]] / 400.0)
        toxic[flat[sel]] = tt[nb.ravel()[sel]]

        # hearing needs no sensor cells, ignores the dark and carries further
        chirp = tc[nb.ravel()]
        audible = infield & (d.ravel() <= cfg.hearing) & (chirp > 0.0)
        loud = np.where(audible, chirp * (1.0 - d.ravel() / cfg.hearing), 0.0)
        order = np.argsort(loud[audible], kind="stable")
        sel = np.nonzero(audible)[0][order]
        heard = np.zeros(n * rays)
        heard[flat[sel]] = loud[sel]

        near = near.reshape(n, rays)
        out[:, 0:rays * 3:3] = near
        out[:, 1:rays * 3:3] = rich.reshape(n, rays)
        out[:, 2:rays * 3:3] = toxic.reshape(n, rays)
        out[:, rays * 3:rays * 4] = heard.reshape(n, rays)

        b = rays * 4
        out[:, b] = 1.0 - np.minimum(1.0, px / sight)
        out[:, b + 1] = 1.0 - np.minimum(1.0, (cfg.world_w - px) / sight)
        out[:, b + 2] = 1.0 - np.minimum(1.0, py / sight)
        out[:, b + 3] = 1.0 - np.minimum(1.0, (cfg.world_h - py) / sight)
        cap = np.fromiter((o.st["capacity"] for o in orgs), float, n)
        age = np.fromiter((o.age for o in orgs), float, n)
        life = np.fromiter((o.lifespan for o in orgs), float, n)
        speed = np.fromiter((o.st["speed"] for o in orgs), float, n)
        turn = np.fromiter((o.st["turn"] for o in orgs), float, n)
        vel = np.fromiter((o.v for o in orgs), float, n)
        spin = np.fromiter((o.w for o in orgs), float, n)
        out[:, b + 4] = np.minimum(1.0, np.fromiter((o.energy for o in orgs), float, n) / cap)
        out[:, b + 5] = np.minimum(1.0, age / life)
        # proprioception: knowing how fast you are already going and turning is
        # what lets a controller damp itself instead of oscillating
        out[:, b + 6] = np.where(speed > 0, vel / np.where(speed > 0, speed, 1.0), 0.0)
        out[:, b + 7] = np.clip(spin / np.where(turn > 0, turn, 1.0), -1.0, 1.0)
        return out

    # --- the tick ---

    def neighbourhood(self):
        """Nearest-k neighbours for everyone, in one C-speed pass.

        Attention is deliberately capped: an organism reacts to the handful of
        things closest to it, which is both cheap and closer to what a real
        sensor does than seeing every object in range.
        """
        things = self.organisms + self.corpses
        n = len(self.organisms)
        m = len(things)
        pts = np.array([(o.x, o.y) for o in things])
        tree = cKDTree(pts)
        k = min(self.cfg.neighbours + 1, m)
        dist, idx = tree.query(pts[:n], k=k)
        if k == 1:
            dist, idx = dist.reshape(n, 1), idx.reshape(n, 1)
        return things, dist, idx

    def step(self):
        cfg = self.cfg
        if not self.organisms:
            self.tick += 1
            return
        self.maybe_event()
        orgs = self.organisms
        things, dist, idx = self.neighbourhood()
        senses = self.sense_all(things, dist, idx).tolist()
        newborns = []
        for i, o in enumerate(orgs):
            if not o.alive:
                continue
            near = [(things[j], d) for j, d in zip(idx[i][1:], dist[i][1:])
                    if things[j].alive and d != np.inf]
            o.sensors = senses[i]
            left, right, split, chirp = o.brain.step(o.sensors)
            o.out = [left, right, split, chirp]
            o.chirp = max(0.0, chirp)
            if o.chirp:
                o.energy -= cfg.chirp_cost * o.chirp

            speed = o.st["speed"]
            if speed:
                o.w = (right - left) * o.st["turn"]
                o.a += o.w
                o.v = max(0.0, min(speed, (left + right) / 2 * speed))
                o.x = min(cfg.world_w, max(0.0, o.x + math.cos(o.a) * o.v))
                o.y = min(cfg.world_h, max(0.0, o.y + math.sin(o.a) * o.v))
                self.clear_obstacles(o)

            self.feed(o, near)
            self.bite(o, near)

            o.energy -= o.upkeep + o.v * cfg.move_cost
            o.energy = min(o.energy, o.st["capacity"] * 2.0)
            o.age += 1
            if o.energy <= 0 or o.age > o.lifespan:
                self.kill(o)
                continue
            if (split > 0 and o.energy >= o.st["capacity"] * cfg.split_energy
                    and len(self.organisms) + len(newborns) < cfg.max_pop):
                newborns.append(self.divide(o, near))

        self.organisms = [o for o in self.organisms if o.alive] + newborns
        for c in self.corpses:
            c.energy -= self.cfg.corpse_decay * c.body.mass
            if c.energy <= 0:
                c.alive = False
        self.corpses = [c for c in self.corpses if c.alive]
        self.births += len(newborns)
        self.tick += 1

    def feed(self, o, near):
        """Photosynthesis, minus whatever the neighbours are shading out."""
        light = o.st["light"]
        if light <= 0:
            return
        cfg = self.cfg
        crowd = sum(other.body.mass for other, d in near
                    if d < cfg.shade_radius and isinstance(other, Organism))
        o.energy += (light * self.light_mult * self.daylight
                     * self.light_at(o.x, o.y)
                     / (1.0 + cfg.shade_factor * crowd))

    def bite(self, o, near):
        eaters = o.st["eaters"]
        if not eaters:
            return
        cfg = self.cfg
        reach = o.st["reach"]
        for other, d in near:
            if not other.alive or d > reach + other.body.radius(cfg):
                continue
            if other.energy <= 0:
                continue
            bite = cfg.bite_rate * eaters * (1.0 - other.st["armor"])
            bite = min(bite, other.energy)
            other.energy -= bite
            # most of what you take is lost in the eating; toxins hurt the
            # diner, and armour on the diner does not help
            o.energy += bite * o.st["digest"] * (1.0 - other.st["toxin"])
            o.energy -= bite * other.st["toxin"]
            o.eaten += bite
            if other.energy <= 0 and other.body is not None:
                self.kill(other)
            break

    def divide(self, o, near):
        """Mitosis. The child is a mutated copy; sometimes it borrows genes from
        a neighbour, which is as close to sex as this dish gets."""
        cfg = self.cfg
        genome = o.genome
        mate = None
        if self.rng.random() < cfg.p_sex:
            options = [x for x, d in near
                       if x.alive and d < cfg.mate_radius and isinstance(x, Organism)]
            if options:
                mate = self.rng.choice(options)
        child_genome = (Genome.crossover(genome, mate.genome, cfg) if mate
                        else genome.copy())
        child_genome.mutate(self.innov, cfg)
        child_body = o.body.copy().mutate(cfg)

        share = o.energy * (1.0 - cfg.split_cost) / 2.0
        o.energy = share
        # growing a body is not free, and a bigger child costs more to build
        build = cfg.cell_build * child_body.mass
        o.born += 1
        a = self.rng.uniform(0, 2 * math.pi)
        d = o.body.radius(cfg) + cfg.cell_r * 2
        return Organism(
            child_genome, child_body,
            min(cfg.world_w, max(0.0, o.x + math.cos(a) * d)),
            min(cfg.world_h, max(0.0, o.y + math.sin(a) * d)),
            self.rng.uniform(0, 2 * math.pi), max(1.0, share - build), cfg,
            gen=o.gen + 1, lifespan=self.jitter_lifespan(o.lifespan))

    # --- readouts for the UI ---

    def census(self):
        """Everything the dish knows about itself, in one dict."""
        from .body import CORE, N_TRAITS, TRAIT_NAME, TYPE_NAME
        c = {"plant": 0, "animal": 0, "microbe": 0}
        cells = {name: 0 for name in TYPE_NAME.values()}
        traits = {name: 0.0 for name in TRAIT_NAME.values()}
        mass = neurons = syn = gen = loops = 0
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
            loops += o.brain.loops
            cells[TYPE_NAME[CORE]] += o.body.count(CORE)
            for t in range(N_TRAITS):
                cells[TRAIT_NAME[t]] += o.body.count(t)
                traits[TRAIT_NAME[t]] += o.body.total(t)
        n = max(len(self.organisms), 1)
        c.update(tick=self.tick, pop=len(self.organisms),
                 mass=mass / n, neurons=neurons / n, synapses=syn / n,
                 depth=gen, energy=energy / n, cells=cells,
                 traits={k: round(v, 2) for k, v in traits.items()},
                 loops=loops,
                 top_mass=top_mass, top_neurons=top_neurons, top_age=top_age,
                 corpses=len(self.corpses),
                 chirping=sum(1 for o in self.organisms if o.chirp > 0.15),
                 births=self.births, deaths=self.deaths, day=self.day,
                 daylight=round(self.daylight, 3),
                 event=self.event["kind"] if self.event else None)
        return c
