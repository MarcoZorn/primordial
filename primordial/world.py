"""The environment the creatures are judged in.

A dish with food and poison. Each creature sees through a fan of rays and
drives itself with two thrusters. Eating food buys it more time alive, poison
costs it. Fitness is food eaten plus a small reward for surviving, so the first
generations - which cannot steer at all - still have a gradient to climb.
"""
import math
import random

import numpy as np

from .brain import Brain

FOOD, POISON = 1, -1


def n_inputs(cfg):
    return cfg.n_rays * 2 + 5


N_OUTPUTS = 2


class Creature:
    __slots__ = ("genome", "brain", "x", "y", "a", "v", "energy", "alive",
                 "eaten", "poisoned", "age", "sensors", "out")

    def __init__(self, genome, cfg, rng):
        self.genome = genome
        self.brain = Brain(genome)
        self.x = rng.uniform(cfg.world_w * 0.2, cfg.world_w * 0.8)
        self.y = rng.uniform(cfg.world_h * 0.2, cfg.world_h * 0.8)
        self.a = rng.uniform(0, 2 * math.pi)
        self.v = 0.0
        self.energy = cfg.start_energy
        self.alive = True
        self.eaten = 0
        self.poisoned = 0
        self.age = 0
        self.sensors = [0.0] * n_inputs(cfg)
        self.out = [0.0, 0.0]

    @property
    def fitness(self):
        return self.eaten * 10.0 - self.poisoned * 6.0 + self.age * 0.01


class World:
    def __init__(self, genomes, cfg, seed=None):
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.tick = 0
        self.creatures = [Creature(g, cfg, self.rng) for g in genomes]
        n = cfg.n_food + cfg.n_poison
        self.items = np.column_stack([
            self.np_rng.uniform(0, cfg.world_w, n),
            self.np_rng.uniform(0, cfg.world_h, n),
        ])
        self.kind = np.array([FOOD] * cfg.n_food + [POISON] * cfg.n_poison)

    @property
    def done(self):
        return self.tick >= self.cfg.ticks or not any(c.alive for c in self.creatures)

    def _respawn(self, i):
        self.items[i] = (self.np_rng.uniform(0, self.cfg.world_w),
                         self.np_rng.uniform(0, self.cfg.world_h))

    def sense(self, c):
        """Fan of rays. Each ray reports the nearest food and nearest poison
        inside its wedge, as proximity in 0..1. Plus walls, energy and speed."""
        cfg = self.cfg
        d = self.items - (c.x, c.y)
        dist = np.hypot(d[:, 0], d[:, 1])
        near = dist < cfg.sight
        out = [0.0] * n_inputs(cfg)
        if near.any():
            ang = (np.arctan2(d[near, 1], d[near, 0]) - c.a + math.pi) % (2 * math.pi) - math.pi
            inside = np.abs(ang) < cfg.fov / 2
            if inside.any():
                ray = ((ang[inside] + cfg.fov / 2) / (cfg.fov / cfg.n_rays)).astype(int)
                ray = np.clip(ray, 0, cfg.n_rays - 1)
                prox = 1.0 - dist[near][inside] / cfg.sight
                kinds = self.kind[near][inside]
                for r, p, k in zip(ray, prox, kinds):
                    slot = r * 2 + (0 if k == FOOD else 1)
                    if p > out[slot]:
                        out[slot] = float(p)
        b = cfg.n_rays * 2
        out[b] = 1.0 - min(1.0, c.x / cfg.sight)
        out[b + 1] = 1.0 - min(1.0, (cfg.world_w - c.x) / cfg.sight)
        out[b + 2] = 1.0 - min(1.0, c.y / cfg.sight)
        out[b + 3] = 1.0 - min(1.0, (cfg.world_h - c.y) / cfg.sight)
        out[b + 4] = min(1.0, c.energy / cfg.start_energy)
        c.sensors = out
        return out

    def step(self):
        cfg = self.cfg
        for c in self.creatures:
            if not c.alive:
                continue
            left, right = c.brain.step(self.sense(c))
            c.out = [left, right]
            c.a += (right - left) * cfg.turn_rate
            c.v = max(0.0, min(cfg.max_speed, (left + right) / 2 * cfg.max_speed))
            c.x = min(cfg.world_w, max(0.0, c.x + math.cos(c.a) * c.v))
            c.y = min(cfg.world_h, max(0.0, c.y + math.sin(c.a) * c.v))

            d = self.items - (c.x, c.y)
            hit = np.nonzero(np.hypot(d[:, 0], d[:, 1]) < cfg.creature_r + 5)[0]
            for i in hit:
                if self.kind[i] == FOOD:
                    c.eaten += 1
                    c.energy += cfg.food_energy
                else:
                    c.poisoned += 1
                    c.energy += cfg.poison_energy
                self._respawn(i)

            c.energy -= cfg.energy_drain + c.v * 0.05
            c.age += 1
            if c.energy <= 0:
                c.alive = False
        self.tick += 1

    def run(self):
        while not self.done:
            self.step()
        return self.score()

    def score(self):
        for c in self.creatures:
            c.genome.fitness = max(0.0, c.fitness)
        return self.creatures
