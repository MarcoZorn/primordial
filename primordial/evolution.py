"""Speciation and reproduction - the natural selection half of NEAT.

Genomes are grouped into species by how similar they are. Fitness is shared
inside a species, so a lineage that just invented something new does not get
wiped out by the current champion before it has had time to be optimised.
"""
import random
from itertools import count

from .genes import Genome, Innovations


class Species:
    _ids = count(1)

    def __init__(self, rep):
        self.id = next(Species._ids)
        self.rep = rep
        self.members = [rep]
        self.best = rep.fitness
        self.stale = 0

    def reset(self):
        self.rep = random.choice(self.members)
        self.members = []


class Population:
    def __init__(self, n_in, n_out, cfg):
        self.cfg = cfg
        self.innov = Innovations()
        self.species = []
        self.generation = 0
        self.best = None
        self.history = []
        # one prototype, then copies: every genome must agree on the ids of the
        # input and output nodes or crossover between them is meaningless
        proto = Genome.minimal(n_in, n_out, self.innov, cfg)
        self.genomes = [proto.copy().mutate(self.innov, cfg) for _ in range(cfg.pop_size)]

    def speciate(self):
        cfg = self.cfg
        for s in self.species:
            s.reset()
        for g in self.genomes:
            for s in self.species:
                if Genome.distance(g, s.rep, cfg) < cfg.compat_threshold:
                    s.members.append(g)
                    break
            else:
                self.species.append(Species(g))
        self.species = [s for s in self.species if s.members]
        # keep the species count near target by nudging the threshold
        if len(self.species) > cfg.target_species:
            cfg.compat_threshold += 0.1
        elif len(self.species) < cfg.target_species:
            cfg.compat_threshold = max(0.5, cfg.compat_threshold - 0.1)

    def _cull(self):
        cfg = self.cfg
        for s in self.species:
            s.members.sort(key=lambda g: g.fitness, reverse=True)
            top = s.members[0].fitness
            if top > s.best:
                s.best, s.stale = top, 0
            else:
                s.stale += 1
            keep = max(2, int(len(s.members) * cfg.survival))
            s.members = s.members[:keep]
        alive = [s for s in self.species if s.stale < cfg.stagnation]
        if alive:
            self.species = alive if len(alive) > 1 else self.species[:2]

    def _offspring_counts(self):
        """Fitness sharing: a species' share of the next generation is its
        average adjusted fitness relative to everyone else's."""
        for s in self.species:
            for g in s.members:
                g.adjusted = g.fitness / len(s.members)
        avg = [sum(g.adjusted for g in s.members) / len(s.members) for s in self.species]
        total = sum(avg) or 1.0
        room = self.cfg.pop_size
        counts = [max(1, int(room * a / total)) for a in avg]
        while sum(counts) > room:
            counts[counts.index(max(counts))] -= 1
        while sum(counts) < room:
            counts[avg.index(max(avg))] += 1
        return counts

    def breed(self, s):
        cfg = self.cfg
        if len(s.members) > 1 and random.random() < cfg.p_crossover:
            a, b = random.sample(s.members, 2)
            child = Genome.crossover(a, b, cfg)
        else:
            child = random.choice(s.members).copy()
        return child.mutate(self.innov, cfg)

    def evolve(self):
        """Called once every genome has a fitness. Produces the next generation."""
        self.speciate()
        champion = max(self.genomes, key=lambda g: g.fitness)
        if self.best is None or champion.fitness > self.best.fitness:
            self.best = champion.copy()
            self.best.fitness = champion.fitness
        self.history.append({
            "gen": self.generation,
            "best": champion.fitness,
            "mean": sum(g.fitness for g in self.genomes) / len(self.genomes),
            "species": len(self.species),
            "nodes": champion.complexity()[0],
            "conns": champion.complexity()[1],
        })
        self._cull()
        counts = self._offspring_counts()
        nxt = []
        for s, n in zip(self.species, counts):
            for g in s.members[: min(self.cfg.elitism, n)]:
                nxt.append(g.copy())
            for _ in range(n - min(self.cfg.elitism, n)):
                nxt.append(self.breed(s))
        self.genomes = nxt[: self.cfg.pop_size]
        while len(self.genomes) < self.cfg.pop_size:
            self.genomes.append(self.breed(random.choice(self.species)))
        self.generation += 1
