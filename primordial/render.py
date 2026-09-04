"""Everything you can see. The renderer only reads state, never writes it.

The dish is drawn through a camera you can zoom and pan, so you can go from the
whole world down to a single cell. Organisms are drawn cell by cell, which is
the point: what a thing is made of is what it can do.
"""
import colorsys
import math

import pygame

from .body import (ARMOR, BITE, CORE, DIGEST, N_TRAITS, PHOTO, SENSE,
                   SHELL, STORE, THRUST, TOXIN, TRAIT_NAME, TYPE_NAME)

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
    THRUST: (96, 156, 255),
    BITE:   (232, 96, 84),
    SENSE:  (86, 214, 226),
    ARMOR:  (150, 158, 176),
    STORE:  (238, 200, 92),
    TOXIN:  (198, 108, 232),
    DIGEST: (226, 148, 96),
    SHELL:  (110, 122, 148),
}


def cell_color(cell):
    """A cell is a mixture, so its colour is the mixture of what it does."""
    total = sum(cell)
    if total < 0.15:
        return CELL_COLOR[CORE]
    r = g = b = 0.0
    for t in range(N_TRAITS):
        w = cell[t] / total
        c = CELL_COLOR[t]
        r += c[0] * w
        g += c[1] * w
        b += c[2] * w
    # a committed cell is vivid, a jack-of-all-trades is washed out
    focus = min(1.0, max(cell) / total * 1.6)
    return (int(r * focus + 150 * (1 - focus)),
            int(g * focus + 155 * (1 - focus)),
            int(b * focus + 165 * (1 - focus)))


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
        self.zoom = 2.2
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

    def fit(self):
        self.zoom = min(self.cfg.view_w / self.cfg.world_w,
                        self.cfg.view_h / self.cfg.world_h) * 0.98
        self.x, self.y = self.cfg.world_w / 2, self.cfg.world_h / 2
        self.follow = None

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
        self.fullscreen = False
        self.cam = Camera(cfg)
        self.buttons = {}
        self.set_scale(cfg.ui_scale)

    def resize(self, w, h):
        """Adopt a size SDL has already applied. Calling set_mode here would
        destroy and recreate the window, which on wayland looks like a crash."""
        cfg = self.cfg
        want = (max(700, w), max(480, h))
        surf = pygame.display.get_surface()
        if surf is not None and surf.get_size() == want:
            self.screen = surf
        else:
            self.screen = pygame.display.set_mode(want, pygame.RESIZABLE)
        self.size = self.screen.get_size()
        cfg.panel_w = max(300, min(620, int(self.size[0] * 0.28)))
        cfg.stats_h = max(150, min(300, int(self.size[1] * 0.22)))
        cfg.view_w = self.size[0] - cfg.panel_w
        cfg.view_h = self.size[1] - cfg.stats_h

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.size, pygame.RESIZABLE)
        self.resize(*self.screen.get_size())

    def set_scale(self, s):
        self.cfg.ui_scale = max(0.6, min(2.6, s))
        n = self.cfg.ui_scale
        self.f = pygame.font.SysFont("monospace", int(14 * n))
        self.fb = pygame.font.SysFont("monospace", int(19 * n), bold=True)
        self.fs = pygame.font.SysFont("monospace", int(12 * n))
        self.lh = int(19 * n)

    def button(self, label, x, y, w=None, on=False):
        """Draw a clickable chip and remember where it landed."""
        n = self.cfg.ui_scale
        w = w or int(30 * n)
        h = int(26 * n)
        rect = pygame.Rect(int(x), int(y), w, h)
        pygame.draw.rect(self.screen, (34, 39, 50) if not on else (58, 88, 140), rect)
        pygame.draw.rect(self.screen, LINE, rect, 1)
        surf = self.f.render(label, True, BRIGHT if on else TEXT)
        self.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                rect.centery - surf.get_height() // 2))
        self.buttons[label if not on else label] = rect
        return rect.right + int(6 * n)

    def toolbar(self, y0, ui):
        n = self.cfg.ui_scale
        self.buttons = {}
        x = self.size[0] - int(430 * n)
        y = y0 + int(12 * n)
        y3 = y + int(64 * n)
        bx = self.size[0] - int(430 * n)
        bx = self.button("best", bx, y3, int(78 * n))
        bx = self.button("plant", bx, y3, int(82 * n))
        bx = self.button("animal", bx, y3, int(92 * n))
        self.button(f"show:{ui.get('filter', 'all')}", bx, y3, int(150 * n),
                    on=ui.get("filter", "all") != "all")
        self.text("text", x, y + int(4 * n), DIM, self.fs)
        x += int(42 * n)
        x = self.button("A-", x, y)
        x = self.button("A+", x, y)
        x += int(10 * n)
        self.text("zoom", x, y + int(4 * n), DIM, self.fs)
        x += int(50 * n)
        x = self.button("-", x, y)
        x = self.button("+", x, y)
        x = self.button("fit", x, y, int(48 * n))
        y2 = y + int(32 * n)
        x = self.size[0] - int(430 * n)
        x = self.button("pause" if not ui.get("paused") else "resume", x, y2, int(96 * n),
                        on=bool(ui.get("paused")))
        x = self.button(f"speed x{ui.get('speed', 1)}", x, y2, int(126 * n),
                        on=ui.get("speed", 1) > 1)
        x = self.button("stats", x, y2, int(84 * n), on=bool(ui.get("overlay")))

    def text(self, s, x, y, col=TEXT, font=None):
        self.screen.blit((font or self.f).render(str(s), True, col), (x, y))

    def draw(self, world, spec, sel, ui):
        from .viewer import matches
        mode = ui.get("filter", "all")
        self._filter = (lambda o: True) if mode == "all" else (
            lambda o: matches(o, mode))
        self.screen.fill(BG)
        self.cam.track(sel)
        self.dish(world, sel)
        self.brain(sel)
        self.legend(sel)
        self.stats(world, spec, sel, ui)
        if ui.get("overlay"):
            self.global_stats(world, spec)
        pygame.display.flip()

    # --- the dish ---

    def dish(self, world, sel):
        cfg = self.cfg
        sc = self.screen
        sc.set_clip((0, 0, cfg.view_w, cfg.view_h))
        tl = self.cam.to_screen(0, 0)
        br = self.cam.to_screen(cfg.world_w, cfg.world_h)
        pygame.draw.rect(sc, (13, 15, 20), (tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]))
        self.light_field(world)
        pygame.draw.rect(sc, LINE, (tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]), 1)

        for ox, oy, orad in world.obstacles:
            if self.cam.visible(ox, oy, orad * self.cam.zoom + 20):
                x, y = self.cam.to_screen(ox, oy)
                pygame.draw.circle(sc, ROCK, (int(x), int(y)), max(2, int(orad * self.cam.zoom)))

        keep = self._filter
        for o in world.organisms:
            if o.alive and self.cam.visible(o.x, o.y):
                self.organism(o, o is sel, dim=not keep(o))

        if world.is_night:
            veil = pygame.Surface((cfg.view_w, cfg.view_h), pygame.SRCALPHA)
            veil.fill((6, 10, 28, int(120 * (1.0 - world.daylight))))
            sc.blit(veil, (0, 0))
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

    def light_field(self, world):
        """Rings showing where the light is, dimmed by the day/night cycle."""
        cfg = self.cfg
        wx, wy = world.light_centre()
        cx, cy = self.cam.to_screen(wx, wy)
        day = world.daylight
        rings = 18
        span = math.sqrt(max(0.02, world.season()))
        for i in range(rings, 0, -1):
            f = i / rings
            lit = math.exp(-(f * span * 2.2) ** 2 / max(0.02, world.season()))
            v = 12 + int(52 * lit * day)
            rx = cfg.world_w / 2 * span * 2.2 * f * self.cam.zoom
            ry = rx
            rect = pygame.Rect(0, 0, int(rx * 2), int(ry * 2))
            rect.center = (int(cx), int(cy))
            if rect.width > 2:
                pygame.draw.ellipse(self.screen, (v, v + 2, v + 7), rect)

    def organism(self, o, is_sel, dim=False):
        cfg = self.cfg
        z = self.cam.zoom
        sx, sy = self.cam.to_screen(o.x, o.y)
        r = max(1.5, cfg.cell_r * z)
        if cfg.cell_r * z < 2.2:
            # too far out to draw cells - one dot, coloured by what it mostly is
            col = (CELL_COLOR[BITE] if o.st["eaters"] > 0.25 else
                   CELL_COLOR[PHOTO] if o.st["photo"] > 0.25 else CELL_COLOR[CORE])
            if dim:
                col = (col[0] // 4 + 10, col[1] // 4 + 11, col[2] // 4 + 13)
            pygame.draw.circle(self.screen, col, (int(sx), int(sy)),
                               max(2, int(o.body.radius(cfg) * z)))
            return
        ca, sa = math.cos(o.a), math.sin(o.a)
        step = cfg.cell_r * 2 * z
        for (gx, gy), cell in o.body.cells.items():
            px, py = gx * step, gy * step
            x = sx + px * ca - py * sa
            y = sy + px * sa + py * ca
            col = cell_color(cell)
            if dim:
                col = (col[0] // 4 + 10, col[1] // 4 + 11, col[2] // 4 + 13)
            pygame.draw.circle(self.screen, col, (int(x), int(y)), int(r))
        if o.chirp > 0.15:
            pygame.draw.circle(self.screen, (240, 220, 140), (int(sx), int(sy)),
                               int((o.body.radius(cfg) + 6 + 22 * o.chirp) * z), 1)
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
            self.text("click an organism to watch its brain", x0 + pad,
                      pad + self.lh * 2, DIM, self.fs)
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
        legend_h = int(self.lh * 6.2)
        bottom = cfg.view_h - legend_h - int(20 * cfg.ui_scale)
        cols = {}
        for node, d in b.depth.items():
            cols.setdefault(d, []).append(node)
        maxd = max(cols) or 1
        pos = {}
        lw = int(74 * cfg.ui_scale)
        for d, nodes in cols.items():
            nodes.sort()
            for i, node in enumerate(nodes):
                x = x0 + lw + (cfg.panel_w - lw - int(96 * cfg.ui_scale)) * (d / maxd)
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
            names += [f"r{i} hear" for i in range(cfg.n_rays)]
            names += ["wall L", "wall R", "wall U", "wall D", "energy", "age",
                      "speed", "turning"]
            for node, name in zip(b.inputs, names):
                x, y = pos[node]
                self.text(name, x - int(70 * cfg.ui_scale), y - 7, DIM, self.fs)
            for node in b.bias:
                if node in pos:
                    x, y = pos[node]
                    self.text("bias", x - int(70 * cfg.ui_scale), y - 7, DIM, self.fs)
            for node, name in zip(b.outputs, ["turn L", "turn R", "divide", "chirp"]):
                x, y = pos[node]
                self.text(name, x + int(10 * cfg.ui_scale), y - 7, BRIGHT, self.fs)

    def legend(self, o):
        """What the cell colours mean. Counts are for the selected organism."""
        cfg = self.cfg
        x0 = cfg.view_w
        n = cfg.ui_scale
        y = cfg.view_h - int(self.lh * 6.0)
        pad = int(16 * n)
        self.text("cell types", x0 + pad, y - int(self.lh * 0.9), DIM, self.fs)
        order = (CORE, PHOTO, THRUST, BITE, SENSE, ARMOR, STORE, TOXIN,
                 DIGEST, SHELL)
        col_w = (cfg.panel_w - pad * 2) // 2
        for i, kind in enumerate(order):
            cx = x0 + pad + (i % 2) * col_w
            cy = y + (i // 2) * self.lh
            r = int(5 * n)
            pygame.draw.circle(self.screen, CELL_COLOR[kind], (cx + r, int(cy + r + 2)), r)
            if o is None:
                label, count = TYPE_NAME[kind], 0
            elif kind == CORE:
                count = o.body.count(CORE)
                label = f"{TYPE_NAME[kind]} {count}"
            else:
                count = o.body.count(kind)
                label = f"{TYPE_NAME[kind]} {count} ({o.body.total(kind):.1f})"
            self.text(label, cx + r * 3, cy, TEXT if count else DIM, self.fs)

    # --- stats ---

    def stats(self, world, spec, sel, ui):
        cfg = self.cfg
        y0 = cfg.view_h
        pygame.draw.rect(self.screen, PANEL, (0, y0, self.size[0], cfg.stats_h))
        c = world.census()
        pad = int(14 * cfg.ui_scale)
        sun = "night" if world.is_night else "day"
        self.text(f"day {world.day}  {sun}", pad, y0 + pad, BRIGHT, self.fb)
        bar = int(120 * cfg.ui_scale)
        by = y0 + pad + int(4 * cfg.ui_scale)
        bx = pad + int(200 * cfg.ui_scale)
        pygame.draw.rect(self.screen, BG, (bx, by, bar, int(12 * cfg.ui_scale)))
        pygame.draw.rect(self.screen, (250, 215, 130) if not world.is_night
                         else (90, 110, 190),
                         (bx, by, int(bar * world.daylight), int(12 * cfg.ui_scale)))
        rows = [
            f"tick    {c['tick']}   loops {c.get('loops', 0)}",
            f"alive   {c['pop']}",
            f"plants  {c['plant']}   animals {c['animal']}   microbes {c['microbe']}",
            f"cells   {c['mass']:.2f} avg   neurons {c['neurons']:.1f} avg",
            f"species {len(spec.species)}   lineage depth {c['depth']}",
            f"births  {c['births']}   deaths {c['deaths']}   carrion {c['corpses']}",
            f"chirping {c['chirping']}",
        ]
        for i, r in enumerate(rows):
            self.text(r, pad, y0 + pad + self.lh * (1.3 + i * 0.9), TEXT, self.fs)

        # the toolbar owns the right edge; everything else shares what is left
        free = self.size[0] - int(450 * cfg.ui_scale)
        text_w = int(330 * cfg.ui_scale)
        rest = max(240, free - text_w - pad * 3)
        gw = int(rest * 0.42)
        sw = int(rest * 0.28)
        ew = rest - gw - sw
        gh = cfg.stats_h - pad * 2
        gx = text_w + pad
        self.graph(ui.get("history", []), gx, y0 + pad, gw, gh)
        sx = gx + gw + pad
        self.species_bar(spec, sx, y0 + pad, sw, gh)
        ex = sx + sw + pad
        self.text("events", ex, y0 + pad, DIM, self.fs)
        for i, (t, txt) in enumerate(reversed(world.log[-4:])):
            self.text(f"{t:>7} {txt}"[: max(8, int(ew / (8 * cfg.ui_scale)))],
                      ex, y0 + pad + self.lh * (0.9 + i * 0.85), DIM, self.fs)
        if world.event:
            self.text(world.event["kind"].upper(), ex,
                      y0 + cfg.stats_h - self.lh - int(10 * cfg.ui_scale),
                      (240, 170, 90), self.fb)

        hint = ("space pause  f speed  +/- zoom  0 fit  drag pan  c follow  "
                "b best  p plant  a animal  v filter  g stats  F11 full  q quit")
        self.text(hint[: max(20, int((self.size[0] - int(470 * cfg.ui_scale))
                                     / (7.2 * cfg.ui_scale)))],
                  pad, y0 + cfg.stats_h - int(18 * cfg.ui_scale), (92, 100, 118), self.fs)
        self.toolbar(y0, ui)

    def global_stats(self, world, spec):
        """Everything about the dish at once. Toggled with g."""
        cfg = self.cfg
        w = int(cfg.view_w * 0.62)
        h = int(cfg.view_h * 0.86)
        x = (cfg.view_w - w) // 2
        y = (cfg.view_h - h) // 2
        pygame.draw.rect(self.screen, (10, 12, 16), (x, y, w, h))
        pygame.draw.rect(self.screen, LINE, (x, y, w, h), 1)
        c = world.census()
        pad = int(22 * cfg.ui_scale)
        self.text("GLOBAL STATS", x + pad, y + pad, BRIGHT, self.fb)
        left = [
            ("tick", c["tick"]),
            ("organisms alive", c["pop"]),
            ("plants", c["plant"]),
            ("animals", c["animal"]),
            ("microbes", c["microbe"]),
            ("species", len(spec.species)),
            ("births", c["births"]),
            ("deaths", c["deaths"]),
            ("deepest lineage", c["depth"]),
        ]
        right = [
            ("avg cells", f"{c['mass']:.2f}"),
            ("avg neurons", f"{c['neurons']:.1f}"),
            ("avg synapses", f"{c['synapses']:.1f}"),
            ("avg energy", f"{c['energy']:.0f}"),
            ("largest body", f"{c['top_mass']} cells"),
            ("largest brain", f"{c['top_neurons']} neurons"),
            ("oldest", f"{c['top_age']} ticks"),
            ("weather", c["event"] or "calm"),
            ("compat threshold", f"{cfg.compat_threshold:.2f}"),
        ]
        top = y + pad + int(self.lh * 1.8)
        for i, (k, v) in enumerate(left):
            self.text(f"{k:<18}{v}", x + pad, top + i * self.lh, TEXT, self.f)
        for i, (k, v) in enumerate(right):
            self.text(f"{k:<18}{v}", x + w // 2, top + i * self.lh, TEXT, self.f)

        cy = top + len(left) * self.lh + self.lh
        self.text("cell census", x + pad, cy, BRIGHT, self.f)
        cy += int(self.lh * 1.2)
        total = sum(c["cells"].values()) or 1
        bar_w = w - pad * 2
        for name, n in sorted(c["cells"].items(), key=lambda kv: -kv[1]):
            kind = next(k for k, v in TYPE_NAME.items() if v == name)
            frac = n / total
            self.text(f"{name:<8}{n:>6}  {frac * 100:5.1f}%", x + pad, cy, DIM, self.fs)
            bx = x + pad + int(220 * cfg.ui_scale)
            pygame.draw.rect(self.screen, CELL_COLOR[kind],
                             (bx, cy + 4, max(1, int((bar_w - 240 * cfg.ui_scale) * frac)),
                              int(10 * cfg.ui_scale)))
            cy += self.lh

        self.text("g to close", x + pad, y + h - int(28 * cfg.ui_scale), DIM, self.fs)

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
