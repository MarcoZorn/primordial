"""Speciation.

Nothing here decides who lives - the dish already did that. This only groups
living organisms by genetic similarity so the UI can colour lineages and count
how many distinct kinds of thing are alive.
"""
from itertools import count

from .genes import Genome


class Species:
    _ids = count(1)

    def __init__(self, rep):
        self.id = next(Species._ids)
        self.rep = rep
        self.members = []
        self.first_seen = 0
        self.peak = 0


class Speciator:
    def __init__(self, cfg):
        self.cfg = cfg
        self.species = {}

    def update(self, organisms, tick=0):
        cfg = self.cfg
        for s in self.species.values():
            s.members = []
        for o in organisms:
            for s in self.species.values():
                if Genome.distance(o.genome, s.rep, cfg) < cfg.compat_threshold:
                    s.members.append(o)
                    o.genome.species = s.id
                    break
            else:
                s = Species(o.genome)
                s.first_seen = tick
                s.members.append(o)
                o.genome.species = s.id
                self.species[s.id] = s
        for sid in [k for k, s in self.species.items() if not s.members]:
            del self.species[sid]
        for s in self.species.values():
            s.rep = s.members[0].genome
            s.peak = max(s.peak, len(s.members))
        n = len(self.species)
        if n > cfg.target_species:
            cfg.compat_threshold += 0.05
        elif n < cfg.target_species:
            cfg.compat_threshold = max(0.3, cfg.compat_threshold - 0.05)
        return self.species

    def ranked(self):
        return sorted(self.species.values(), key=lambda s: -len(s.members))
