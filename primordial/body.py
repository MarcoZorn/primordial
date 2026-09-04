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
# Traits 0..ACTIVE_TRAITS-1 mean something. The rest are reserved slots that
# every cell already carries: inert, free, and never mutated until a later
# version gives one of them a meaning. Bodies then need no migration.
ACTIVE_TRAITS = 9
N_TRAITS = 16
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
    c[rng.randrange(ACTIVE_TRAITS)] = rng.uniform(0.35, 1.0)
    if rng.random() < 0.3:
        c[rng.randrange(ACTIVE_TRAITS)] += rng.uniform(0.05, 0.4)
    return c


class Body:
    def __init__(self, cells=None):
        self.cells = cells or {(0, 0): blank()}

    def copy(self):
        return Body({k: list(v) for k, v in self.cells.items()})

    # --- mutation ---

    def mutate(self, cfg):
        if random.random() < cfg.p_segment:
            self.duplicate_segment(cfg)
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
        """Traits wander. This is where genuinely new cell kinds come from.

        A trait that is already expressed drifts both ways and can be lost. A
        trait sitting at zero has to be switched on by a rarer mutation - if it
        could simply drift up, every trait would creep upwards forever, because
        zero is a floor and there is nowhere else to go.
        """
        for cell in self.cells.values():
            for i in range(ACTIVE_TRAITS):
                if cell[i] > 0.0:
                    if random.random() < cfg.p_trait:
                        cell[i] = min(cfg.trait_cap,
                                      max(0.0, cell[i] + random.gauss(0, cfg.trait_step)))
                elif random.random() < cfg.p_trait_new:
                    cell[i] = random.uniform(0.05, 0.3)

    # --- what the body can do ---

    def total(self, trait, cells=None):
        return sum(c[trait] for c in (cells or self.cells).values())

    def growth_order(self):
        """The order cells are grown in: outward from the core.

        An organism is born as a single cell and builds the rest of its body
        over its life, paying as it goes. Being born fully formed would mean
        paying for every cell out of what it inherited, which caps a newborn at
        a handful of cells no matter what its genome says.
        """
        order, seen, queue = [(0, 0)], {(0, 0)}, [(0, 0)]
        while queue:
            x, y = queue.pop(0)
            for dx, dy in NEIGHBOURS:
                n = (x + dx, y + dy)
                if n in self.cells and n not in seen:
                    seen.add(n)
                    order.append(n)
                    queue.append(n)
        order += [c for c in self.cells if c not in seen]
        return order

    def duplicate_segment(self, cfg):
        """Copy a block of the body and graft it on.

        Adding one cell per birth grows a body linearly. Real body plans get
        big by repeating parts - segments, limbs, whole duplicated regions -
        and then letting the copies specialise.
        """
        if len(self.cells) >= cfg.max_cells:
            return
        coords = list(self.cells)
        block = random.sample(coords, max(1, min(len(coords),
                                                 int(len(coords) * cfg.segment_share) + 1)))
        for dx, dy in random.sample(list(NEIGHBOURS), len(NEIGHBOURS)):
            span = max(abs(x) for x, _ in coords) - min(abs(x) for x, _ in coords) + 1
            shift = (dx * span, dy * span)
            placed = {(x + shift[0], y + shift[1]): list(self.cells[(x, y)])
                      for x, y in block}
            if any(c in self.cells for c in placed):
                continue
            merged = {**self.cells, **placed}
            if len(merged) <= cfg.max_cells and _connected(merged):
                self.cells = merged
                return

    def count(self, trait):
        """How many cells are mostly this. Labels and colours only."""
        n = 0
        for c in self.cells.values():
            live = c[:ACTIVE_TRAITS]
            if max(live) < 0.15:
                if trait == CORE:
                    n += 1
            elif live.index(max(live)) == trait:
                n += 1
        return n

    @property
    def mass(self):
        return len(self.cells)

    def stats(self, cfg, cells=None):
        """What the body can do. `cells` is the part actually grown so far."""
        cells = self.cells if cells is None else cells
        m = max(1, len(cells))
        photo, thrust = self.total(PHOTO, cells), self.total(THRUST, cells)
        bite, sense = self.total(BITE, cells), self.total(SENSE, cells)
        armor = self.total(ARMOR, cells)
        store, toxin = self.total(STORE, cells), self.total(TOXIN, cells)
        digest, shell = self.total(DIGEST, cells), self.total(SHELL, cells)
        invested = (photo + thrust + bite + sense + armor + store + toxin
                    + digest + shell)
        # a shell is cheap to hold and hard to bite through, but it is opaque:
        # you cannot armour yourself and photosynthesise with the same surface
        cover = min(0.85, shell / m)
        # committing to predation shuts photosynthesis down; you are one or the
        # other, and part-way is worth part of each
        autotrophy = max(0.0, 1.0 - (bite / m) * cfg.bite_blinds)
        return {
            "mass": m,
            "movers": thrust,
            "photo": photo,
            "eaters": bite,
            "speed": cfg.max_speed * min(1.0, thrust / m) * (1.0 - 0.5 * cover),
            "turn": cfg.turn_rate * (0.4 + 0.9 * min(1.0, thrust / m)),
            "reach": cfg.cell_r * math.sqrt(m) + cfg.bite_reach * bite,
            "sight": cfg.sight * (0.55 + 0.55 * min(1.5, sense / m)),
            "armor": min(0.92, armor / m + cover * 0.6),
            "light": (cfg.photo_rate * (photo + cfg.core_photo)
                      * autotrophy * (1.0 - cover)),
            # what fraction of a bite actually becomes yours
            "digest": min(cfg.digest_cap, cfg.bite_efficiency * (1.0 + digest / m)),
            "shell": cover,
            # a bigger body holds a proportionally larger energy buffer purely
            # from bulk - independent of any trait investment. This is a
            # reward for size (survives a lean patch better, so lives longer
            # and reproduces more over its life), not a discount on the cost
            # of growing: the price per cell is unchanged.
            "capacity": cfg.start_energy * (1.0 + 0.9 * store
                                            + cfg.size_capacity_bonus * (m - 1)),
            "toxin": min(1.0, toxin / m),
            # Kleiber's law for the structure, plus rent on every capability
            # a shell is dead weight: it costs little to hold and slows you down
            "drain": (cfg.energy_drain * m ** 0.75
                      + cfg.trait_cost * (invested - shell * 0.6)
                      + cfg.toxin_cost * toxin
                      + cfg.eater_cost * bite),
        }

    def radius(self, cfg, mass=None):
        return cfg.cell_r * math.sqrt(self.mass if mass is None else mass)

    def kingdom(self, cells=None):
        """A label read off the body afterwards. Nothing branches on it."""
        if self.total(BITE, cells) > 0.25:
            return "animal"
        if self.total(PHOTO, cells) > 0.25:
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
