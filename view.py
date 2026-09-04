#!/usr/bin/env python3
"""Watch a running research daemon.

    python view.py                    # attach to runs/research
    python view.py --run runs/other

The viewer is read-only and completely detachable: open it, close it, open it
again, and the daemon never notices. It loads the newest checkpoint, then keeps
simulating locally so motion stays smooth, and resyncs to the real run every
time the daemon writes a new checkpoint. Between resyncs what you see is a
plausible continuation rather than the exact run - the numbers in the stats bar
are from the last real checkpoint.
"""
import argparse
import os
import time

import pygame

from primordial import checkpoint
from primordial.evolution import Speciator
from primordial.render import Renderer


class Viewer:
    def __init__(self, directory, scale=0.0):
        self.path = os.path.join(directory, "state.pkl.gz")
        self.mtime = 0
        pygame.init()
        state = self.wait_for_checkpoint()
        self.cfg = state["world"].cfg
        self.cfg.ui_scale = scale
        self.fit_to_screen()
        self.render = Renderer(self.cfg)
        self.adopt(state)
        self.clock = pygame.time.Clock()
        self.paused = False
        self.fast = 1
        self.sel = None
        self.drag = None
        self.overlay = False
        self.history = []
        self.resyncs = 0

    def wait_for_checkpoint(self):
        while True:
            state, _ = checkpoint.newest(self.path)
            if state:
                self.mtime = os.path.getmtime(self.path)
                return state
            print(f"waiting for {self.path} ...")
            time.sleep(2)

    def adopt(self, state):
        self.world = state["world"]
        self.spec = state.get("spec") or Speciator(self.cfg)
        self.innov = state["innov"]
        self.checkpoint_tick = self.world.tick

    def maybe_resync(self):
        try:
            m = os.path.getmtime(self.path)
        except OSError:
            return
        if m <= self.mtime:
            return
        state, _ = checkpoint.newest(self.path)
        if not state:
            return
        self.mtime = m
        keep = self.sel
        self.adopt(state)
        self.resyncs += 1
        self.sel = None
        if keep is not None:
            # the old object is gone; grab whatever is nearest where it was
            self.pick_world(keep.x, keep.y)

    def fit_to_screen(self):
        info = pygame.display.Info()
        w, h = int(info.current_w * 0.78), int(info.current_h * 0.76)
        if not self.cfg.ui_scale:
            self.cfg.ui_scale = max(1.0, min(3.0, info.current_h / 900.0))
        self.cfg.panel_w = max(320, min(560, int(w * 0.28)))
        self.cfg.stats_h = max(160, min(260, int(h * 0.22)))
        self.cfg.view_w = w - self.cfg.panel_w
        self.cfg.view_h = h - self.cfg.stats_h

    def pick_world(self, wx, wy):
        alive = [o for o in self.world.organisms if o.alive]
        if not alive:
            return
        def gap(o):
            return ((o.x - wx) ** 2 + (o.y - wy) ** 2) ** 0.5 - o.body.radius(self.cfg)
        o = min(alive, key=gap)
        if gap(o) < 60 / max(self.render.cam.zoom, 0.01):
            self.sel = o

    def biggest(self):
        alive = [o for o in self.world.organisms if o.alive]
        return max(alive, key=lambda o: (o.body.mass, o.energy)) if alive else None

    def events(self):
        cam = self.render.cam
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
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
                    self.pick_world(*cam.to_world(*e.pos))
            if e.type == pygame.MOUSEBUTTONUP:
                self.drag = None
            if e.type == pygame.MOUSEMOTION and self.drag:
                cam.pan(e.rel[0], e.rel[1])
            if e.type == pygame.MOUSEWHEEL:
                cam.zoom_at(*pygame.mouse.get_pos(), 1.15 ** e.y)
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
                if e.key == pygame.K_SPACE:
                    self.paused = not self.paused
                if e.key == pygame.K_f:
                    self.fast = {1: 4, 4: 16, 16: 1}[self.fast]
                if e.key == pygame.K_g:
                    self.overlay = not self.overlay
                if e.key == pygame.K_c:
                    cam.follow = self.sel if cam.follow is None else None
                if e.key == pygame.K_TAB:
                    self.sel = self.biggest()
                    cam.follow = self.sel
                if e.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                    self.render.set_scale(self.cfg.ui_scale
                                          + (0.15 if e.key == pygame.K_RIGHTBRACKET
                                             else -0.15))
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
            self.fast = {1: 4, 4: 16, 16: 1}[self.fast]
        elif hit == "stats":
            self.overlay = not self.overlay
        return True

    def run(self):
        while self.events():
            self.maybe_resync()
            if not self.paused:
                for _ in range(self.fast):
                    self.world.step()
                if self.world.tick % 60 == 0:
                    self.history.append(self.world.census())
                    del self.history[:-400]
            if self.sel is not None and not self.sel.alive:
                self.sel = self.biggest()
                if self.render.cam.follow:
                    self.render.cam.follow = self.sel
            self.render.draw(self.world, self.spec, self.sel,
                             {"fast": self.fast if self.fast > 1 else 0,
                              "paused": self.paused, "history": self.history,
                              "overlay": self.overlay, "speed": self.fast,
                              "attached": self.checkpoint_tick})
            self.clock.tick(60)
        pygame.quit()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", default="runs/research")
    p.add_argument("--scale", type=float, default=0.0)
    a = p.parse_args()
    Viewer(a.run, a.scale).run()


if __name__ == "__main__":
    main()
