"""Phenotype: turn a genome into something that can be evaluated.

Kept deliberately simple - feedforward only, evaluated in topological order.
Activations are retained after each step so the UI can draw the network firing.
"""
import math

from .genes import BIAS, HIDDEN, INPUT, OUTPUT


def tanh(x):
    return math.tanh(max(-30.0, min(30.0, x)))


class Brain:
    def __init__(self, genome):
        self.inputs = sorted(genome.ids(INPUT))
        self.outputs = sorted(genome.ids(OUTPUT))
        self.bias = genome.ids(BIAS)
        self.edges = [(c.src, c.dst, c.w) for c in genome.conns.values() if c.enabled]
        self.order = self._topo(genome)
        self.act = {n: 0.0 for n in genome.nodes}
        self.incoming = {}
        for s, d, w in self.edges:
            self.incoming.setdefault(d, []).append((s, w))
        self.depth = self._depths(genome)

    def _topo(self, genome):
        indeg = {n: 0 for n in genome.nodes}
        for _, d, _ in self.edges:
            indeg[d] += 1
        ready = [n for n, k in indeg.items() if k == 0]
        order = []
        while ready:
            n = ready.pop()
            order.append(n)
            for s, d, _ in self.edges:
                if s == n:
                    indeg[d] -= 1
                    if indeg[d] == 0:
                        ready.append(d)
        return order

    def _depths(self, genome):
        """Longest path from an input. Used only for laying the graph out."""
        depth = {n: 0 for n in genome.nodes}
        for n in self.order:
            for s, w in self.incoming.get(n, []):
                depth[n] = max(depth[n], depth[s] + 1)
        maxd = max([depth[n] for n in self.outputs] or [1]) or 1
        for n in self.outputs:
            depth[n] = maxd
        for n in genome.ids(INPUT, BIAS):
            depth[n] = 0
        return depth

    def step(self, values):
        a = self.act
        for n, v in zip(self.inputs, values):
            a[n] = v
        for n in self.bias:
            a[n] = 1.0
        for n in self.order:
            if n in self.inputs or n in self.bias:
                continue
            a[n] = tanh(sum(a[s] * w for s, w in self.incoming.get(n, [])))
        return [a[n] for n in self.outputs]
