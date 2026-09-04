"""Body genome. Every organism is a clump of cells.

Everything starts as one undifferentiated cell that feeds weakly on ambient
light. Mutation can bolt on a cell, respecialise one, or drop one. Nothing
declares what a plant or an animal is: a clump that fills up with PHOTO cells
and never grows a MOVER is a plant, one that grows movers and eaters is an
animal, and the dish decides which pays.
"""
import math
import random

CORE, PHOTO, MOVER, EATER, SENSOR, ARMOR, STORE, TOXIN = range(8)
TYPES = (PHOTO, MOVER, EATER, SENSOR, ARMOR, STORE, TOXIN)
TYPE_NAME = {CORE: "core", PHOTO: "photo", MOVER: "mover", EATER: "eater",
             SENSOR: "sensor", ARMOR: "armor", STORE: "store", TOXIN: "toxin"}
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Body:
    def __init__(self, cells=None):
        self.cells = cells or {(0, 0): CORE}

    def copy(self):
        return Body(dict(self.cells))

    def mutate(self, cfg):
        if random.random() < cfg.p_cell_add and len(self.cells) < cfg.max_cells:
            self._add()
        if random.random() < cfg.p_cell_type:
            self._retype()
        if random.random() < cfg.p_cell_drop and len(self.cells) > 1:
            self._drop()
        return self

    def _add(self):
        slots = [(x + dx, y + dy)
                 for (x, y) in self.cells
                 for dx, dy in NEIGHBOURS
                 if (x + dx, y + dy) not in self.cells]
        if slots:
            self.cells[random.choice(slots)] = random.choice(TYPES)

    def _retype(self):
        spots = [c for c in self.cells if c != (0, 0)]
        if spots:
            self.cells[random.choice(spots)] = random.choice(TYPES)

    def _drop(self):
        """Only drop a cell if what is left still holds together."""
        spots = [c for c in self.cells if c != (0, 0)]
        random.shuffle(spots)
        for c in spots:
            rest = dict(self.cells)
            del rest[c]
            if _connected(rest):
                self.cells = rest
                return

    def count(self, kind):
        return sum(1 for k in self.cells.values() if k == kind)

    @property
    def mass(self):
        return len(self.cells)

    def stats(self, cfg):
        m = self.mass
        movers, photo = self.count(MOVER), self.count(PHOTO)
        return {
            "mass": m,
            "movers": movers,
            "photo": photo,
            "eaters": self.count(EATER),
            "speed": cfg.max_speed * movers / m if movers else 0.0,
            "turn": cfg.turn_rate * (0.4 + 0.9 * movers / m),
            "reach": self.radius(cfg) + cfg.bite_reach * self.count(EATER),
            "sight": cfg.sight * (0.55 + 0.55 * self.count(SENSOR) / m),
            "armor": self.count(ARMOR) / m,
            # the core feeds weakly on its own, so a lone cell can still live
            "light": cfg.photo_rate * (photo + cfg.core_photo),
            "capacity": cfg.start_energy * (1.0 + 0.9 * self.count(STORE)),
            "toxin": self.count(TOXIN) / m,
            # bigger bodies cost more to run, sublinearly - Kleiber's law
            "drain": cfg.energy_drain * m ** 0.75 + cfg.toxin_cost * self.count(TOXIN),
        }

    def radius(self, cfg):
        return cfg.cell_r * math.sqrt(self.mass)

    def kingdom(self):
        """Purely a label for the UI - nothing in the sim branches on it."""
        if self.count(EATER) and self.count(MOVER):
            return "animal"
        if self.count(PHOTO) and not self.count(MOVER):
            return "plant"
        return "microbe"


def _connected(cells):
    if not cells:
        return False
    seen, stack = set(), [next(iter(cells))]
    while stack:
        x, y = stack.pop()
        if (x, y) in seen:
            continue
        seen.add((x, y))
        for dx, dy in NEIGHBOURS:
            if (x + dx, y + dy) in cells:
                stack.append((x + dx, y + dy))
    return len(seen) == len(cells)
