"""Interactive driver. One world, running forever, drawn every frame."""
import pygame

from .config import Config
from .evolution import Speciator
from .genes import Innovations
from .render import Renderer
from .store import save
from .world import World


class App:
    def __init__(self, cfg=None):
        self.cfg = cfg or Config()
        pygame.init()
        self.render = Renderer(self.cfg)
        self.world = World(self.cfg)
        self.innov = Innovations()
        self.world.seed_life(self.innov)
        self.spec = Speciator(self.cfg)
        self.spec.update(self.world.organisms, 0)
        self.clock = pygame.time.Clock()
        self.paused = False
        self.fast = 1
        self.sel = None
        self.drag = None
        self.history = []

    def pick(self, sx, sy):
        wx, wy = self.render.cam.to_world(sx, sy)
        alive = [o for o in self.world.organisms if o.alive]
        if not alive:
            return
        o = min(alive, key=lambda o: (o.x - wx) ** 2 + (o.y - wy) ** 2)
        if ((o.x - wx) ** 2 + (o.y - wy) ** 2) ** 0.5 < 60 / self.render.cam.zoom:
            self.sel = o

    def biggest(self):
        alive = [o for o in self.world.organisms if o.alive]
        return max(alive, key=lambda o: (o.body.mass, o.energy)) if alive else None

    def events(self):
        cam = self.render.cam
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 4:
                    cam.zoom_at(*e.pos, 1.15)
                elif e.button == 5:
                    cam.zoom_at(*e.pos, 1 / 1.15)
                elif e.pos[0] < self.cfg.view_w:
                    self.drag = e.pos
                    self.pick(*e.pos)
            if e.type == pygame.MOUSEBUTTONUP:
                self.drag = None
            if e.type == pygame.MOUSEMOTION and self.drag:
                cam.pan(e.rel[0], e.rel[1])
            if e.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                cam.zoom_at(mx, my, 1.15 ** e.y)
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_q, pygame.K_ESCAPE):
                    return False
                if e.key == pygame.K_SPACE:
                    self.paused = not self.paused
                if e.key == pygame.K_f:
                    self.fast = {1: 4, 4: 16, 16: 64, 64: 1}[self.fast]
                if e.key == pygame.K_c:
                    cam.follow = self.sel if cam.follow is None else None
                if e.key == pygame.K_TAB:
                    self.sel = self.biggest()
                    cam.follow = self.sel
                if e.key == pygame.K_LEFTBRACKET:
                    self.render.set_scale(self.cfg.ui_scale - 0.15)
                if e.key == pygame.K_RIGHTBRACKET:
                    self.render.set_scale(self.cfg.ui_scale + 0.15)
                if e.key == pygame.K_s and self.sel:
                    print("saved", save(self.sel.genome, f"runs/t{self.world.tick}.json"))
        return True

    def sample(self):
        c = self.world.census()
        self.history.append(c)
        del self.history[:-400]

    def run(self):
        while self.events():
            if not self.paused:
                for _ in range(self.fast):
                    self.world.step()
                    if self.world.tick % self.cfg.speciate_every == 0:
                        self.spec.update(self.world.organisms, self.world.tick)
                    if self.world.tick % 60 == 0:
                        self.sample()
            if self.sel is not None and not self.sel.alive:
                self.sel = self.biggest()
                if self.render.cam.follow:
                    self.render.cam.follow = self.sel
            if not self.world.organisms:
                self.world.seed_life(self.innov)
                self.world.note("reseeded - total extinction")
            self.render.draw(self.world, self.spec, self.sel,
                             {"fast": self.fast if self.fast > 1 else 0,
                              "paused": self.paused, "history": self.history})
            self.clock.tick(0 if self.fast > 1 else 60)
        pygame.quit()
