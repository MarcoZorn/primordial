"""Interactive driver. One world, running forever, drawn every frame."""
import json
import os
import time

import pygame

from .config import Config
from .evolution import Speciator
from .genes import Innovations
from .render import Renderer
from .store import save
from .world import World


class App:
    def __init__(self, cfg=None, telemetry="runs/telemetry.jsonl"):
        self.cfg = cfg or Config()
        pygame.init()
        self.fit_to_screen()
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
        self.overlay = False
        self.telemetry = telemetry
        if telemetry:
            os.makedirs(os.path.dirname(telemetry) or ".", exist_ok=True)
            self._fh = open(telemetry, "a")
            self._t0 = time.time()

    def fit_to_screen(self):
        """Open as large as the desktop comfortably allows."""
        info = pygame.display.Info()
        w = int(info.current_w * 0.78)
        h = int(info.current_h * 0.76)
        if not self.cfg.ui_scale:
            # a 900px-tall desktop is scale 1.0; HiDPI screens need much more
            self.cfg.ui_scale = max(1.0, min(3.0, info.current_h / 900.0))
        self.cfg.panel_w = max(320, min(560, int(w * 0.28)))
        self.cfg.stats_h = max(160, min(260, int(h * 0.22)))
        self.cfg.view_w = w - self.cfg.panel_w
        self.cfg.view_h = h - self.cfg.stats_h

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
            # x11 sends VIDEORESIZE, wayland sends WINDOWRESIZED; take either,
            # and let resize() ignore it when the surface already matches
            if e.type == pygame.VIDEORESIZE:
                self.render.resize(e.w, e.h)
            elif e.type == pygame.WINDOWRESIZED:
                self.render.resize(e.x, e.y)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.toolbar(e.pos):
                continue
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
                if e.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    cam.zoom_at(self.cfg.view_w / 2, self.cfg.view_h / 2, 1.35)
                if e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    cam.zoom_at(self.cfg.view_w / 2, self.cfg.view_h / 2, 1 / 1.35)
                if e.key == pygame.K_0:
                    cam.fit()
                if e.key == pygame.K_F11:
                    self.render.toggle_fullscreen()
                if e.key == pygame.K_g:
                    self.overlay = not self.overlay
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

    def toolbar(self, pos):
        hit = next((k for k, r in self.render.buttons.items() if r.collidepoint(pos)), None)
        if hit is None:
            return False
        cam = self.render.cam
        mid = (self.cfg.view_w / 2, self.cfg.view_h / 2)
        if hit == "A-":
            self.render.set_scale(self.cfg.ui_scale - 0.15)
        elif hit == "A+":
            self.render.set_scale(self.cfg.ui_scale + 0.15)
        elif hit == "-":
            cam.zoom_at(*mid, 1 / 1.35)
        elif hit == "+":
            cam.zoom_at(*mid, 1.35)
        elif hit == "fit":
            cam.fit()
        elif hit in ("pause", "resume"):
            self.paused = not self.paused
        elif hit.startswith("speed"):
            self.fast = {1: 4, 4: 16, 16: 64, 64: 1}[self.fast]
        elif hit == "stats":
            self.overlay = not self.overlay
        return True

    def sample(self):
        c = self.world.census()
        self.history.append(c)
        del self.history[:-400]
        if self.telemetry and self.world.tick % 600 == 0:
            c["wall"] = round(time.time() - self._t0, 1)
            c["species"] = len(self.spec.species)
            self._fh.write(json.dumps(c) + "\n")
            self._fh.flush()

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
                              "paused": self.paused, "history": self.history,
                              "overlay": self.overlay, "speed": self.fast})
            self.clock.tick(0 if self.fast > 1 else 60)
        pygame.quit()
