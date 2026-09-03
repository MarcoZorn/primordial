"""Interactive loop: run a generation, draw it, evolve, repeat."""
import math
import time

import pygame

from .config import Config
from .evolution import Population
from .render import Renderer
from .store import save
from .world import N_OUTPUTS, World, n_inputs


class App:
    def __init__(self, cfg=None, seed_world=True):
        self.cfg = cfg or Config()
        pygame.init()
        self.render = Renderer(self.cfg)
        self.pop = Population(n_inputs(self.cfg), N_OUTPUTS, self.cfg)
        self.clock = pygame.time.Clock()
        self.paused = False
        self.fast = False
        self.seed_world = seed_world
        self.sel = None
        self.new_generation()

    def new_generation(self):
        self.pop.speciate()
        seed = self.pop.generation if self.seed_world else None
        self.world = World(self.pop.genomes, self.cfg, seed=seed)
        self.sel = self.pick_best()

    def pick_best(self):
        alive = [c for c in self.world.creatures if c.alive]
        return max(alive, key=lambda c: c.fitness) if alive else None

    def click(self, pos):
        alive = [c for c in self.world.creatures if c.alive]
        if not alive:
            return
        c = min(alive, key=lambda c: math.hypot(c.x - pos[0], c.y - pos[1]))
        if math.hypot(c.x - pos[0], c.y - pos[1]) < 40:
            self.sel = c

    def events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.MOUSEBUTTONDOWN and e.pos[0] < self.cfg.world_w:
                self.click(e.pos)
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_q, pygame.K_ESCAPE):
                    return False
                if e.key == pygame.K_SPACE:
                    self.paused = not self.paused
                if e.key == pygame.K_f:
                    self.fast = not self.fast
                if e.key == pygame.K_n:
                    while not self.world.done:
                        self.world.step()
                if e.key == pygame.K_TAB:
                    self.sel = self.pick_best()
                if e.key == pygame.K_s and self.pop.best:
                    print("saved", save(self.pop.best, f"runs/best_gen{self.pop.generation}.json"))
        return True

    def run(self):
        running = True
        while running:
            running = self.events()
            if not self.paused:
                steps = 12 if self.fast else 1
                for _ in range(steps):
                    if self.world.done:
                        break
                    self.world.step()
            if self.world.done:
                self.world.score()
                self.pop.evolve()
                self.new_generation()
            if self.sel is not None and not self.sel.alive:
                self.sel = self.pick_best()
            self.render.draw(self.world, self.pop, self.sel, {"fast": self.fast})
            self.clock.tick(0 if self.fast else 60)
        pygame.quit()


def headless(cfg, generations, log=print):
    """No window. Used for long runs and for the tests."""
    pop = Population(n_inputs(cfg), N_OUTPUTS, cfg)
    t0 = time.time()
    for _ in range(generations):
        World(pop.genomes, cfg, seed=pop.generation).run()
        pop.evolve()
        r = pop.history[-1]
        log(f"gen {r['gen']:4d}  best {r['best']:7.1f}  mean {r['mean']:6.1f}  "
            f"species {r['species']:3d}  {r['nodes']}n/{r['conns']}c  "
            f"{time.time() - t0:5.1f}s")
    return pop
