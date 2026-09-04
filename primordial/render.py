"""Everything you can see. The renderer only reads state, never writes it.

The dish is drawn through a camera you can zoom and pan, so you can go from the
whole world down to a single cell. Organisms are drawn cell by cell, which is
the point: what a thing is made of is what it can do.
"""
import colorsys
import math

import pygame

from .body import ARMOR, CORE, EATER, MOVER, PHOTO, SENSOR, STORE, TOXIN, TYPE_NAME

BG = (12, 14, 19)
PANEL = (19, 22, 29)
LINE = (36, 41, 53)
TEXT = (166, 176, 194)
DIM = (104, 114, 134)
BRIGHT = (233, 239, 249)
ACCENT = (122, 172, 255)
ROCK = (44, 48, 58)

CELL_COLOR = {
    CORE:   (226, 230, 240),
    PHOTO:  (78, 200, 118),
    MOVER:  (96, 156, 255),
    EATER:  (232, 96, 84),
    SENSOR: (86, 214, 226),
    ARMOR:  (150, 158, 176),
    STORE:  (238, 200, 92),
    TOXIN:  (198, 108, 232),
}


def species_color(sid):
    h = 0.47 + 0.48 * ((sid * 0.381966) % 1.0)
    r, g, b = colorsys.hsv_to_rgb(h, 0.55, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def act_color(v):
    v = max(-1.0, min(1.0, v))
    if v >= 0:
        return int(70 + 185 * v), int(70 + 100 * v), int(80 - 40 * v)
    return int(70 + 20 * v), int(70 + 40 * -v), int(80 + 175 * -v)


class Camera:
    def __init__(self, cfg):
        self.cfg = cfg
        self.zoom = min(cfg.view_w / cfg.world_w, cfg.view_h / cfg.world_h)
        self.x = cfg.world_w / 2
        self.y = cfg.world_h / 2
        self.follow = None

    def to_screen(self, wx, wy):
        return ((wx - self.x) * self.zoom + self.cfg.view_w / 2,
                (wy - self.y) * self.zoom + self.cfg.view_h / 2)

    def to_world(self, sx, sy):
        return ((sx - self.cfg.view_w / 2) / self.zoom + self.x,
                (sy - self.cfg.view_h / 2) / self.zoom + self.y)

    def zoom_at(self, sx, sy, factor):
        wx, wy = self.to_world(sx, sy)
        self.zoom = max(0.08, min(12.0, self.zoom * factor))
        nx, ny = self.to_world(sx, sy)
        self.x += wx - nx
        self.y += wy - ny

    def pan(self, dx, dy):
        self.follow = None
        self.x -= dx / self.zoom
        self.y -= dy / self.zoom

    def visible(self, wx, wy, pad=40):
        sx, sy = self.to_screen(wx, wy)
        return -pad <= sx <= self.cfg.view_w + pad and -pad <= sy <= self.cfg.view_h + pad

    def track(self, org):
        if self.follow and self.follow.alive:
            self.x += (self.follow.x - self.x) * 0.15
            self.y += (self.follow.y - self.y) * 0.15


class Renderer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.size = (cfg.view_w + cfg.panel_w, cfg.view_h + cfg.stats_h)
        self.screen = pygame.display.set_mode(self.size, pygame.RESIZABLE)
        pygame.display.set_caption("primordial")
        self.cam = Camera(cfg)
        self.set_scale(cfg.ui_scale)

    def set_scale(self, s):
        self.cfg.ui_scale = max(0.6, min(2.6, s))
        n = self.cfg.ui_scale
        self.f = pygame.font.SysFont("monospace", int(14 * n))
        self.fb = pygame.font.SysFont("monospace", int(19 * n), bold=True)
        self.fs = pygame.font.SysFont("monospace", int(12 * n))
        self.lh = int(19 * n)

    def text(self, s, x, y, col=TEXT, font=None):
        self.screen.blit((font or self.f).render(str(s), True, col), (x, y))

    def draw(self, world, spec, sel, ui):
        self.screen.fill(BG)
        self.cam.track(sel)
        self.dish(world, sel)
        self.brain(sel)
        self.stats(world, spec, sel, ui)
        pygame.display.flip()

    # --- the dish ---

    def dish(self, world, sel):
        cfg = self.cfg
        sc = self.screen
        sc.set_clip((0, 0, cfg.view_w, cfg.view_h))
        tl = self.cam.to_screen(0, 0)
        br = self.cam.to_screen(cfg.world_w, cfg.world_h)
        pygame.draw.rect(sc, (16, 19, 25), (tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]))
        pygame.draw.rect(sc, LINE, (tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]), 1)

        for ox, oy, orad in world.obstacles:
            if self.cam.visible(ox, oy, orad * self.cam.zoom + 20):
                x, y = self.cam.to_screen(ox, oy)
                pygame.draw.circle(sc, ROCK, (int(x), int(y)), max(2, int(orad * self.cam.zoom)))

        for o in world.organisms:
            if o.alive and self.cam.visible(o.x, o.y):
                self.organism(o, o is sel)

        ev = world.event
        if ev and ev["kind"] == "meteor":
            x, y = self.cam.to_screen(ev["x"], ev["y"])
            pygame.draw.circle(sc, (220, 120, 70), (int(x), int(y)),
                               max(2, int(ev["r"] * self.cam.zoom)), 2)
        if sel and sel.alive:
            self.vision(sel)
        sc.set_clip(None)
        pygame.draw.line(sc, LINE, (cfg.view_w, 0), (cfg.view_w, cfg.view_h))
        pygame.draw.line(sc, LINE, (0, cfg.view_h), (self.size[0], cfg.view_h))

    def organism(self, o, is_sel):
        cfg = self.cfg
        z = self.cam.zoom
        sx, sy = self.cam.to_screen(o.x, o.y)
        r = max(1.0, cfg.cell_r * z)
        if r < 2.0:
            # too far out to draw cells - one dot, coloured by what it mostly is
            col = CELL_COLOR[PHOTO] if o.st["photo"] else (
                CELL_COLOR[EATER] if o.st["eaters"] else CELL_COLOR[CORE])
            pygame.draw.circle(self.screen, col, (int(sx), int(sy)),
                               max(1, int(o.body.radius(cfg) * z)))
            return
        ca, sa = math.cos(o.a), math.sin(o.a)
        step = cfg.cell_r * 2 * z
        for (gx, gy), kind in o.body.cells.items():
            px, py = gx * step, gy * step
            x = sx + px * ca - py * sa
            y = sy + px * sa + py * ca
            pygame.draw.circle(self.screen, CELL_COLOR[kind], (int(x), int(y)), int(r))
        if is_sel:
            pygame.draw.circle(self.screen, BRIGHT, (int(sx), int(sy)),
                               int(o.body.radius(cfg) * z + 6 * z + 3), 1)

    def vision(self, o):
        cfg = self.cfg
        sight = o.st["sight"] * self.cam.zoom
        sx, sy = self.cam.to_screen(o.x, o.y)
        for i in range(cfg.n_rays):
            a = o.a - cfg.fov / 2 + cfg.fov * (i + 0.5) / cfg.n_rays
            prox = o.sensors[i * 3]
            tox = o.sensors[i * 3 + 2]
            length = sight * (1 - prox) if prox else sight
            col = (198, 108, 232) if tox > 0.2 else (
                (120, 220, 150) if prox else (48, 54, 68))
            pygame.draw.line(self.screen, col, (sx, sy),
                             (sx + math.cos(a) * length, sy + math.sin(a) * length), 1)

    # --- brain ---

    def brain(self, o):
        cfg = self.cfg
        x0 = cfg.view_w
        pygame.draw.rect(self.screen, PANEL, (x0, 0, cfg.panel_w, cfg.view_h))
        pad = int(16 * cfg.ui_scale)
        self.text("ORGANISM", x0 + pad, pad, BRIGHT, self.fb)
        if o is None:
            self.text("click something", x0 + pad, pad + self.lh * 2)
            return
        b = o.brain
        st = o.st
        rows = [
            f"{o.kingdom}  species {getattr(o.genome, 'species', 0)}",
            f"{b_count(o)}  gen {o.gen}",
            f"energy {o.energy:6.0f}/{st['capacity']:.0f}   age {o.age}/{o.lifespan:.0f}",
            f"speed {st['speed']:.2f}  sight {st['sight']:.0f}  light {st['light']:.2f}",
        ]
        for i, r in enumerate(rows):
            self.text(r, x0 + pad, pad + self.lh * (1.4 + i * 0.95), TEXT, self.fs)

        top = pad + int(self.lh * 6)
        bottom = cfg.view_h - int(28 * cfg.ui_scale)
        cols = {}
        for node, d in b.depth.items():
            cols.setdefault(d, []).append(node)
        maxd = max(cols) or 1
        pos = {}
        lw = int(74 * cfg.ui_scale)
        for d, nodes in cols.items():
            nodes.sort()
            for i, node in enumerate(nodes):
                x = x0 + lw + (cfg.panel_w - lw - int(56 * cfg.ui_scale)) * (d / maxd)
                y = top + (bottom - top) * ((i + 0.5) / len(nodes))
                pos[node] = (x, y)

        for src, dst, w in b.edges:
            if src in pos and dst in pos:
                sig = b.act.get(src, 0.0) * w
                pygame.draw.aaline(self.screen, act_color(sig), pos[src], pos[dst])
        for node, (x, y) in pos.items():
            v = b.act.get(node, 0.0)
            r = (4 + 4 * min(1.0, abs(v))) * cfg.ui_scale
            pygame.draw.circle(self.screen, act_color(v), (int(x), int(y)), int(r))

        if len(pos) <= 40:
            names = []
            for i in range(cfg.n_rays):
                names += [f"r{i} near", f"r{i} rich", f"r{i} toxic"]
            names += ["wall L", "wall R", "wall U", "wall D", "energy", "age"]
            for node, name in zip(b.inputs, names):
                x, y = pos[node]
                self.text(name, x - int(70 * cfg.ui_scale), y - 7, DIM, self.fs)
            for node in b.bias:
                if node in pos:
                    x, y = pos[node]
                    self.text("bias", x - int(70 * cfg.ui_scale), y - 7, DIM, self.fs)
            for node, name in zip(b.outputs, ["turn L", "turn R", "divide"]):
                x, y = pos[node]
                self.text(name, x + int(10 * cfg.ui_scale), y - 7, BRIGHT, self.fs)

    # --- stats ---

    def stats(self, world, spec, sel, ui):
        cfg = self.cfg
        y0 = cfg.view_h
        pygame.draw.rect(self.screen, PANEL, (0, y0, self.size[0], cfg.stats_h))
        c = world.census()
        pad = int(14 * cfg.ui_scale)
        self.text(f"tick {world.tick}", pad, y0 + pad, BRIGHT, self.fb)
        rows = [
            f"alive   {c['pop']}",
            f"plants  {c['plant']}   animals {c['animal']}   microbes {c['microbe']}",
            f"cells   {c['mass']:.2f} avg   neurons {c['neurons']:.1f} avg",
            f"species {len(spec.species)}   lineage depth {c['depth']}",
            f"births  {c['births']}   deaths {c['deaths']}",
        ]
        for i, r in enumerate(rows):
            self.text(r, pad, y0 + pad + self.lh * (1.3 + i * 0.9), TEXT, self.fs)

        gx = int(360 * cfg.ui_scale)
        self.graph(ui.get("history", []), gx, y0 + pad, int(320 * cfg.ui_scale),
                   cfg.stats_h - pad * 2)
        self.species_bar(spec, gx + int(340 * cfg.ui_scale), y0 + pad,
                         int(260 * cfg.ui_scale), cfg.stats_h - pad * 2)
        ex = gx + int(620 * cfg.ui_scale)
        self.text("events", ex, y0 + pad, DIM, self.fs)
        for i, (t, txt) in enumerate(reversed(world.log[-4:])):
            self.text(f"{t:>7} {txt}", ex, y0 + pad + self.lh * (0.9 + i * 0.85), DIM, self.fs)
        if world.event:
            self.text(world.event["kind"].upper(), ex, y0 + cfg.stats_h - self.lh - 6,
                      (240, 170, 90), self.fb)

        hint = ("space pause  f fast  wheel zoom  drag pan  c follow  " 
                "click select  [ ] text  s save  q quit")
        self.text(hint, pad, y0 + cfg.stats_h - int(18 * cfg.ui_scale), (92, 100, 118), self.fs)
        if ui.get("fast"):
            self.text(f"FAST x{ui['fast']}", self.size[0] - int(120 * cfg.ui_scale),
                      y0 + pad, ACCENT, self.fb)
        if ui.get("paused"):
            self.text("PAUSED", self.size[0] - int(120 * cfg.ui_scale),
                      y0 + pad + self.lh, (240, 170, 90), self.fb)

    def graph(self, hist, x, y, w, h):
        pygame.draw.rect(self.screen, BG, (x, y, w, h))
        self.text("population", x + 6, y + 3, DIM, self.fs)
        if len(hist) < 2:
            return
        top = max(max(r["pop"] for r in hist), 5)
        n = len(hist)
        series = (("pop", (150, 160, 185)), ("plant", CELL_COLOR[PHOTO]),
                  ("animal", CELL_COLOR[EATER]))
        for key, col in series:
            pts = [(x + w * i / (n - 1), y + h - 5 - (h - 22) * (r[key] / top))
                   for i, r in enumerate(hist)]
            pygame.draw.aalines(self.screen, col, False, pts)
        self.text(str(top), x + w - int(42 * self.cfg.ui_scale), y + 3, DIM, self.fs)

    def species_bar(self, spec, x, y, w, h):
        pygame.draw.rect(self.screen, BG, (x, y, w, h))
        self.text("species", x + 6, y + 3, DIM, self.fs)
        ranked = spec.ranked()
        if not ranked:
            return
        total = sum(len(s.members) for s in ranked) or 1
        cx = x + 3
        for s in ranked:
            bw = max(1.5, (w - 6) * len(s.members) / total)
            pygame.draw.rect(self.screen, species_color(s.id),
                             (cx, y + int(20 * self.cfg.ui_scale), bw - 0.5,
                              h - int(26 * self.cfg.ui_scale)))
            cx += bw


def b_count(o):
    n, c = o.genome.complexity()
    return f"{o.body.mass} cells  {n} neurons  {c} synapses"
