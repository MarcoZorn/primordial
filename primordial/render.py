"""Everything you can see: the dish, the selected creature's brain, the stats.

Nothing here feeds back into the simulation - the renderer only reads state.
"""
import colorsys
import math

import pygame

BG = (14, 16, 22)
PANEL = (20, 23, 31)
LINE = (38, 43, 55)
TEXT = (168, 178, 196)
BRIGHT = (232, 238, 248)
FOOD_C = (86, 204, 128)
POISON_C = (214, 78, 90)
ACCENT = (120, 170, 255)

BRAIN_W = 440
STATS_H = 150


def species_color(sid):
    # golden-angle hues, kept out of the green/red band so creatures never read
    # as food or poison
    h = 0.47 + 0.48 * ((sid * 0.381966) % 1.0)
    r, g, b = colorsys.hsv_to_rgb(h, 0.55, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def act_color(v):
    """Blue for inhibited, grey for idle, orange for firing."""
    v = max(-1.0, min(1.0, v))
    if v >= 0:
        return (int(70 + 185 * v), int(70 + 100 * v), int(80 - 40 * v))
    return (int(70 + 20 * v), int(70 + 40 * -v), int(80 + 175 * -v))


class Renderer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.size = (cfg.world_w + BRAIN_W, cfg.world_h + STATS_H)
        self.screen = pygame.display.set_mode(self.size)
        pygame.display.set_caption("primordial")
        self.f = pygame.font.SysFont("monospace", 13)
        self.fb = pygame.font.SysFont("monospace", 17, bold=True)
        self.fs = pygame.font.SysFont("monospace", 11)

    def text(self, s, x, y, col=TEXT, font=None):
        self.screen.blit((font or self.f).render(str(s), True, col), (x, y))

    def draw(self, world, pop, selected, ui):
        self.screen.fill(BG)
        self.dish(world, selected)
        self.brain(selected)
        self.stats(world, pop, selected, ui)
        pygame.display.flip()

    # --- dish ---

    def dish(self, world, sel):
        cfg = self.cfg
        sc = self.screen
        for (x, y), k in zip(world.items, world.kind):
            pygame.draw.circle(sc, FOOD_C if k > 0 else POISON_C, (int(x), int(y)), 4)
        for c in world.creatures:
            if not c.alive:
                continue
            col = species_color(getattr(c.genome, "species", 0))
            self.body(c, col, c is sel)
        if sel and sel.alive:
            self.vision(sel)
        pygame.draw.line(sc, LINE, (cfg.world_w, 0), (cfg.world_w, cfg.world_h))
        pygame.draw.line(sc, LINE, (0, cfg.world_h), (self.size[0], cfg.world_h))

    def body(self, c, col, is_sel):
        r = self.cfg.creature_r
        a = c.a
        pts = [(c.x + math.cos(a) * r * 1.6, c.y + math.sin(a) * r * 1.6),
               (c.x + math.cos(a + 2.5) * r, c.y + math.sin(a + 2.5) * r),
               (c.x + math.cos(a - 2.5) * r, c.y + math.sin(a - 2.5) * r)]
        pygame.draw.polygon(self.screen, col, pts)
        if is_sel:
            pygame.draw.circle(self.screen, BRIGHT, (int(c.x), int(c.y)), int(r * 2.2), 1)

    def vision(self, c):
        cfg = self.cfg
        for i in range(cfg.n_rays):
            a = c.a - cfg.fov / 2 + cfg.fov * (i + 0.5) / cfg.n_rays
            f, p = c.sensors[i * 2], c.sensors[i * 2 + 1]
            hit = max(f, p)
            length = cfg.sight * (1 - hit) if hit else cfg.sight
            col = FOOD_C if f > p else POISON_C
            col = col if hit > 0.01 else (52, 58, 72)
            pygame.draw.line(self.screen, col, (c.x, c.y),
                             (c.x + math.cos(a) * length, c.y + math.sin(a) * length), 1)

    # --- brain ---

    def brain(self, c):
        x0 = self.cfg.world_w
        pygame.draw.rect(self.screen, PANEL, (x0, 0, BRAIN_W, self.cfg.world_h))
        self.text("BRAIN", x0 + 16, 14, BRIGHT, self.fb)
        if c is None:
            self.text("click a creature", x0 + 16, 40)
            return
        b = c.brain
        n, e = c.genome.complexity()
        self.text(f"species {getattr(c.genome, 'species', 0)}   {n} neurons  {e} synapses",
                  x0 + 16, 38)
        self.text(f"energy {c.energy:6.0f}   ate {c.eaten}   poison {c.poisoned}", x0 + 16, 56)

        cols = {}
        for node, d in b.depth.items():
            cols.setdefault(d, []).append(node)
        maxd = max(cols) or 1
        pos = {}
        top, bottom = 96, self.cfg.world_h - 40
        for d, nodes in cols.items():
            nodes.sort()
            for i, node in enumerate(nodes):
                x = x0 + 78 + (BRAIN_W - 150) * (d / maxd)
                y = top + (bottom - top) * ((i + 0.5) / len(nodes))
                pos[node] = (x, y)

        for src, dst, w in b.edges:
            if src not in pos or dst not in pos:
                continue
            signal = b.act.get(src, 0.0) * w
            col = act_color(max(-1.0, min(1.0, signal)))
            pygame.draw.aaline(self.screen, col, pos[src], pos[dst])
        for node, (x, y) in pos.items():
            v = b.act.get(node, 0.0)
            r = 5 + 4 * min(1.0, abs(v))
            pygame.draw.circle(self.screen, act_color(v), (int(x), int(y)), int(r))
            pygame.draw.circle(self.screen, LINE, (int(x), int(y)), int(r), 1)

        labels = []
        for i in range(self.cfg.n_rays):
            labels += [f"ray{i} food", f"ray{i} bad"]
        labels += ["wall L", "wall R", "wall U", "wall D", "energy"]
        for node, name in zip(b.inputs, labels):
            x, y = pos[node]
            self.text(name, x - 72, y - 6, TEXT, self.fs)
        for node in b.bias:
            if node in pos:
                x, y = pos[node]
                self.text("bias", x - 72, y - 6, (120, 130, 150), self.fs)
        for node, name in zip(b.outputs, ["left", "right"]):
            x, y = pos[node]
            self.text(name, x + 12, y - 6, BRIGHT, self.fs)

    # --- stats ---

    def stats(self, world, pop, sel, ui):
        cfg = self.cfg
        y0 = cfg.world_h
        pygame.draw.rect(self.screen, PANEL, (0, y0, self.size[0], STATS_H))
        alive = sum(c.alive for c in world.creatures)
        best = max((c.fitness for c in world.creatures), default=0)
        self.text(f"gen {pop.generation}", 16, y0 + 12, BRIGHT, self.fb)
        rows = [
            f"tick    {world.tick}/{cfg.ticks}",
            f"alive   {alive}/{len(world.creatures)}",
            f"species {len(pop.species)}",
            f"best    {best:.1f}",
            f"record  {pop.best.fitness:.1f}" if pop.best else "record  -",
        ]
        for i, r in enumerate(rows):
            self.text(r, 16, y0 + 38 + i * 18)
        self.text("space pause   f fast   n next gen   click select   tab cycle   s save   q quit",
                  16, y0 + STATS_H - 20, (110, 120, 140), self.fs)
        self.graph(pop, 240, y0 + 14, 420, STATS_H - 34)
        self.species_bar(pop, 690, y0 + 14, self.size[0] - 710, STATS_H - 34)
        if ui.get("fast"):
            self.text("FAST", self.size[0] - 60, y0 + STATS_H - 22, ACCENT, self.fb)

    def graph(self, pop, x, y, w, h):
        pygame.draw.rect(self.screen, BG, (x, y, w, h))
        self.text("fitness", x + 6, y + 4, (110, 120, 140), self.fs)
        hist = pop.history
        if len(hist) < 2:
            return
        top = max(max(r["best"] for r in hist), 1.0)
        n = len(hist)
        for key, col in (("mean", (90, 110, 150)), ("best", ACCENT)):
            pts = [(x + w * i / (n - 1), y + h - h * (r[key] / top) * 0.92 - 4)
                   for i, r in enumerate(hist)]
            pygame.draw.aalines(self.screen, col, False, pts)
        self.text(f"{top:.0f}", x + w - 40, y + 4, (110, 120, 140), self.fs)

    def species_bar(self, pop, x, y, w, h):
        pygame.draw.rect(self.screen, BG, (x, y, w, h))
        self.text("species", x + 6, y + 4, (110, 120, 140), self.fs)
        if not pop.species:
            return
        total = sum(len(s.members) or 1 for s in pop.species) or 1
        cx = x + 4
        for s in sorted(pop.species, key=lambda s: -len(s.members)):
            bw = max(2, (w - 8) * (len(s.members) or 1) / total)
            pygame.draw.rect(self.screen, species_color(s.id), (cx, y + 20, bw - 1, h - 28))
            cx += bw
