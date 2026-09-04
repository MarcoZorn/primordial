"""Phenotype: turn a genome into something that can be evaluated.

Networks may contain cycles. Edges that run forwards through the evaluation
order read this tick's values; edges that run backwards read last tick's, which
is what gives an organism memory between ticks. Without that every behaviour is
a reflex, and nothing that depends on sequence - anticipation, timing, anything
resembling syntax - is reachable at all.

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
        self.prev = dict(self.act)
        rank = {n: i for i, n in enumerate(self.order)}
        # split the edges once: anything pointing backwards through the order is
        # a memory edge and reads the previous tick
        self.incoming = {}
        self.recurrent = {}
        for s, d, w in self.edges:
            table = self.incoming if rank[s] < rank[d] else self.recurrent
            table.setdefault(d, []).append((s, w))
        self.loops = sum(len(v) for v in self.recurrent.values())
        self.depth = self._depths(genome)
        self._fixed = set(self.inputs) | set(self.bias)

    def _topo(self, genome):
        """Evaluation order. Inputs first, then Kahn's algorithm; whatever is
        left is inside a cycle and gets appended in a stable order."""
        indeg = {n: 0 for n in genome.nodes}
        out = {}
        for s, d, _ in self.edges:
            indeg[d] += 1
            out.setdefault(s, []).append(d)
        fixed = self.inputs + self.bias
        for n in fixed:
            indeg[n] = 0
        ready = [n for n in genome.nodes if indeg[n] == 0]
        order, seen = [], set()
        while ready:
            n = ready.pop()
            if n in seen:
                continue
            seen.add(n)
            order.append(n)
            for d in out.get(n, ()):
                indeg[d] -= 1
                if indeg[d] <= 0 and d not in seen:
                    ready.append(d)
        order += [n for n in genome.nodes if n not in seen]
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
        self.prev = dict(a)
        prev = self.prev
        fixed = self._fixed
        for n, v in zip(self.inputs, values):
            a[n] = v
        for n in self.bias:
            a[n] = 1.0
        rec = self.recurrent
        inc = self.incoming
        for n in self.order:
            if n in fixed:
                continue
            total = 0.0
            for s, w in inc.get(n, ()):
                total += a[s] * w
            for s, w in rec.get(n, ()):
                total += prev[s] * w
            a[n] = tanh(total)
        return [a[n] for n in self.outputs]
