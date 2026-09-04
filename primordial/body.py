"""Body genome. Every organism is a clump of cells, and every cell is a mix.

Cells are not picked from a menu. Each one carries seven continuous traits and
mutation nudges them, so the space of possible bodies is open rather than a
recombination of eight fixed parts. A cell can be purely photosynthetic, purely
predatory, or any blend in between, and blends are where new strategies come
from.

Nothing is free: a cell pays upkeep in proportion to everything it is good at,
so a cell that tries to do all seven jobs costs seven times as much as one that
commits. That cost is the only reason specialisation happens at all.

Everything still starts as one bare cell with every trait near zero, feeding
weakly on ambient light.
"""
import math
import random

PHOTO, THRUST, BITE, SENSE, ARMOR, STORE, TOXIN, DIGEST, SHELL = range(9)
N_TRAITS = 9
TRAIT_NAME = {PHOTO: "photo", THRUST: "mover", BITE: "eater", SENSE: "sensor",
              ARMOR: "armor", STORE: "store", TOXIN: "toxin",
              DIGEST: "digest", SHELL: "shell"}
CORE = -1                      # only ever a label for the UI
TYPE_NAME = {**TRAIT_NAME, CORE: "core"}
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def blank():
    return [0.0] * N_TRAITS


def seeded(rng=random):
    """A new cell commits mostly to one job, with a little of something else."""
    c = blank()
    c[rng.randrange(N_TRAITS)] = rng.uniform(0.35, 1.0)
    if rng.random() < 0.3:
        c[rng.randrange(N_TRAITS)] += rng.uniform(0.05, 0.4)
    return c


class Body:
    def __init__(self, cells=None):
        self.cells = cells or {(0, 0): blank()}

    def copy(self):
        return Body({k: list(v) for k, v in self.cells.items()})

    # --- mutation ---

    def mutate(self, cfg):
        if random.random() < cfg.p_cell_add and len(self.cells) < cfg.max_cells:
            self._add()
        if random.random() < cfg.p_cell_drop and len(self.cells) > 1:
            self._drop()
        self._drift(cfg)
        return self

    def _add(self):
        slots = [(x + dx, y + dy)
                 for (x, y) in self.cells
                 for dx, dy in NEIGHBOURS
                 if (x + dx, y + dy) not in self.cells]
        if slots:
            self.cells[random.choice(slots)] = seeded()

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

    def _drift(self, cfg):
        """Traits wander. This is where genuinely new cell kinds come from."""
        for cell in self.cells.values():
            for i in range(N_TRAITS):
                if random.random() < cfg.p_trait:
                    cell[i] = min(cfg.trait_cap,
                                  max(0.0, cell[i] + random.gauss(0, cfg.trait_step)))

    # --- what the body can do ---

    def total(self, trait):
        return sum(c[trait] for c in self.cells.values())

    def count(self, trait):
        """How many cells are mostly this. Labels and colours only."""
        n = 0
        for c in self.cells.values():
            if max(c) < 0.15:
                if trait == CORE:
                    n += 1
            elif c.index(max(c)) == trait:
                n += 1
        return n

    @property
    def mass(self):
        return len(self.cells)

    def stats(self, cfg):
        m = self.mass
        photo, thrust = self.total(PHOTO), self.total(THRUST)
        bite, sense = self.total(BITE), self.total(SENSE)
        armor, store, toxin = self.total(ARMOR), self.total(STORE), self.total(TOXIN)
        digest, shell = self.total(DIGEST), self.total(SHELL)
        invested = (photo + thrust + bite + sense + armor + store + toxin
                    + digest + shell)
        # a shell is cheap to hold and hard to bite through, but it is opaque:
        # you cannot armour yourself and photosynthesise with the same surface
        cover = min(0.85, shell / m)
        # committing to predation shuts photosynthesis down; you are one or the
        # other, and part-way is worth part of each
        autotrophy = max(0.0, 1.0 - bite * cfg.bite_blinds)
        return {
            "mass": m,
            "movers": thrust,
            "photo": photo,
            "eaters": bite,
            "speed": cfg.max_speed * min(1.0, thrust / m) * (1.0 - 0.5 * cover),
            "turn": cfg.turn_rate * (0.4 + 0.9 * min(1.0, thrust / m)),
            "reach": self.radius(cfg) + cfg.bite_reach * bite,
            "sight": cfg.sight * (0.55 + 0.55 * min(1.5, sense / m)),
            "armor": min(0.92, armor / m + cover * 0.6),
            "light": (cfg.photo_rate * (photo + cfg.core_photo)
                      * autotrophy * (1.0 - cover)),
            # what fraction of a bite actually becomes yours
            "digest": min(cfg.digest_cap, cfg.bite_efficiency * (1.0 + digest / m)),
            "shell": cover,
            "capacity": cfg.start_energy * (1.0 + 0.9 * store),
            "toxin": min(1.0, toxin / m),
            # Kleiber's law for the structure, plus rent on every capability
            # a shell is dead weight: it costs little to hold and slows you down
            "drain": (cfg.energy_drain * m ** 0.75
                      + cfg.trait_cost * (invested - shell * 0.6)
                      + cfg.toxin_cost * toxin
                      + cfg.eater_cost * bite),
        }

    def radius(self, cfg):
        return cfg.cell_r * math.sqrt(self.mass)

    def kingdom(self):
        """A label read off the body afterwards. Nothing branches on it."""
        if self.total(BITE) > 0.25:
            return "animal"
        if self.total(PHOTO) > 0.25:
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
