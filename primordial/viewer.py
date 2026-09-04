"""The one interactive window.

It runs in two modes. Attached to a run directory it loads the daemon's newest
checkpoint, simulates locally so motion stays smooth, and resyncs every time
the daemon writes a new one. Standalone it simply owns a world of its own.
Everything else - camera, selection, filters, the brain view - is the same
either way, which is the point of there only being one of these.
"""
import os
import time

import pygame

from . import checkpoint
from .config import Config
from .evolution import Speciator
from .genes import Innovations
from .render import Renderer
from .store import save
from .world import World

FILTERS = ("all", "plants", "animals", "microbes", "chirping", "biggest brains")


def matches(o, mode):
    if mode == "all":
        return True
    if mode == "plants":
        return o.kingdom == "plant"
    if mode == "animals":
        return o.kingdom == "animal"
    if mode == "microbes":
        return o.kingdom == "microbe"
    if mode == "chirping":
        return o.chirp > 0.15
    if mode == "biggest brains":
        return len(o.genome.nodes) > 40
    return True


def complexity(o):
    """How evolved something is, as one number.

    Deliberately crude and stated out loud rather than hidden: brain size,
    body size and how far down its own lineage it sits. There is no correct
    definition of 'most evolved', so this is a ranking for the UI, not a claim.
    """
    nodes, conns = o.genome.complexity()
    return nodes + conns * 0.5 + o.body.mass * 2.0 + o.gen * 0.5 + o.brain.loops * 3.0


class Viewer:
    def __init__(self, run=None, cfg=None, scale=0.0):
        self.run = run
        self.path = os.path.join(run, "state.pkl.gz") if run else None
        self.mtime = 0
        pygame.init()
        if run:
            state = self.wait_for_checkpoint()
            self.cfg = state["world"].cfg
        else:
            self.cfg = cfg or Config()
            state = None
        self.cfg.ui_scale = scale
        self.fit_to_screen()
        self.render = Renderer(self.cfg)
        if state:
            self.adopt(state)
        else:
            self.world = World(self.cfg)
            self.innov = Innovations()
            self.world.seed_life(self.innov)
            self.spec = Speciator(self.cfg)
            self.spec.update(self.world.organisms, 0)
            self.checkpoint_tick = None
        self.clock = pygame.time.Clock()
        self.paused = False
        self.fast = 1
        self.sel = None
        self.drag = None
        self.overlay = False
        self.filter = 0
        self.history = []

    # --- attaching ---

    def wait_for_checkpoint(self):
        while True:
            state, _ = checkpoint.newest(self.path)
            if state:
                self.mtime = os.path.getmtime(self.path)
                return state
            print(f"waiting for {self.path} ...", flush=True)
            time.sleep(2)

    def adopt(self, state):
        self.world = state["world"]
        self.spec = state.get("spec") or Speciator(self.cfg)
        self.innov = state["innov"]
        self.checkpoint_tick = self.world.tick

    def maybe_resync(self):
        if not self.path:
            return
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
        where = (self.sel.x, self.sel.y) if self.sel else None
        self.adopt(state)
        self.sel = None
        if where:
            self.pick_world(*where)
            if self.render.cam.follow is not None:
                self.render.cam.follow = self.sel

    # --- layout ---

    def fit_to_screen(self):
        info = pygame.display.Info()
        w, h = int(info.current_w * 0.78), int(info.current_h * 0.76)
        if not self.cfg.ui_scale:
            self.cfg.ui_scale = max(1.0, min(3.0, info.current_h / 900.0))
        self.cfg.panel_w = max(320, min(560, int(w * 0.28)))
        self.cfg.stats_h = max(160, min(280, int(h * 0.22)))
        self.cfg.view_w = w - self.cfg.panel_w
        self.cfg.view_h = h - self.cfg.stats_h

    # --- finding things ---

    def alive(self):
        return [o for o in self.world.organisms if o.alive]

    def pick_world(self, wx, wy):
        alive = self.alive()
        if not alive:
            return
        def gap(o):
            return ((o.x - wx) ** 2 + (o.y - wy) ** 2) ** 0.5 - o.body.radius(self.cfg)
        o = min(alive, key=gap)
        if gap(o) < 60 / max(self.render.cam.zoom, 0.01):
            self.sel = o

    def go_to(self, o):
        """Select something and put the camera on it."""
        if o is None:
            return
        self.sel = o
        cam = self.render.cam
        cam.x, cam.y = o.x, o.y
        cam.follow = o
        if cam.zoom < 1.2:
            cam.zoom = 1.6

    def most_evolved(self):
        alive = self.alive()
        return max(alive, key=complexity) if alive else None

    def find(self, kind):
        pool = [o for o in self.alive() if matches(o, kind)]
        if not pool:
            return None
        return max(pool, key=complexity)

    # --- input ---

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
            if e.type == pygame.KEYDOWN and not self.key(e, cam):
                return False
        return True

    def key(self, e, cam):
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
        if e.key == pygame.K_v:
            self.filter = (self.filter + 1) % len(FILTERS)
        if e.key == pygame.K_c:
            cam.follow = self.sel if cam.follow is None else None
        if e.key == pygame.K_b:
            self.go_to(self.most_evolved())
        if e.key == pygame.K_p:
            self.go_to(self.find("plants"))
        if e.key == pygame.K_a:
            self.go_to(self.find("animals"))
        if e.key == pygame.K_TAB:
            self.go_to(self.most_evolved())
        if e.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
            self.render.set_scale(self.cfg.ui_scale
                                  + (0.15 if e.key == pygame.K_RIGHTBRACKET else -0.15))
        if e.key == pygame.K_s and self.sel:
            print("saved", save(self.sel.genome, f"runs/pick{self.world.tick}.json"))
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
        elif hit == "best":
            self.go_to(self.most_evolved())
        elif hit == "plant":
            self.go_to(self.find("plants"))
        elif hit == "animal":
            self.go_to(self.find("animals"))
        elif hit.startswith("show:"):
            self.filter = (self.filter + 1) % len(FILTERS)
        return True

    # --- loop ---

    def run_forever(self):
        while self.events():
            self.maybe_resync()
            if not self.paused:
                for _ in range(self.fast):
                    self.world.step()
                if self.world.tick % 120 == 0:
                    if self.path is None:
                        self.spec.update(self.world.organisms, self.world.tick)
                    self.history.append(self.world.census())
                    del self.history[:-400]
            if self.sel is not None and not self.sel.alive:
                self.sel = self.most_evolved()
                if self.render.cam.follow:
                    self.render.cam.follow = self.sel
            if not self.world.organisms:
                self.world.seed_life(self.innov)
                self.world.note("reseeded - total extinction")
            self.render.draw(self.world, self.spec, self.sel, {
                "fast": self.fast if self.fast > 1 else 0,
                "paused": self.paused, "history": self.history,
                "overlay": self.overlay, "speed": self.fast,
                "filter": FILTERS[self.filter],
                "attached": self.checkpoint_tick,
            })
            self.clock.tick(60)
        pygame.quit()
