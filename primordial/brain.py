"""Phenotype: turn a genome into something that can be evaluated.

Networks may contain cycles. Edges that run forwards through the evaluation
order read this tick's values; edges that run backwards read last tick's, which
is what gives an organism memory between ticks. Without that every behaviour is
a reflex, and nothing that depends on sequence - anticipation, timing, anything
resembling syntax - is reachable at all.

Activations are retained after each step so the UI can draw the network firing.
"""
import math

import numpy as np

from .genes import BIAS, HIDDEN, INPUT, OUTPUT

# below this many neurons a plain python loop beats numpy, because the call
# overhead costs more than the arithmetic saves. Above it numpy wins by a mile,
# which is what makes large brains affordable at all.
VECTOR_THRESHOLD = 130


def tanh(x):
    return math.tanh(max(-30.0, min(30.0, x)))


class Brain:
    def __init__(self, genome):
        self.inputs = sorted(genome.ids(INPUT))
        self.outputs = sorted(genome.ids(OUTPUT))
        self.bias = genome.ids(BIAS)
        self.edges = [(c.src, c.dst, c.w) for c in genome.conns.values() if c.enabled]
        self.order = self._topo(genome)
        self._act = {n: 0.0 for n in genome.nodes}
        self.prev = dict(self._act)
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
        self.vector = len(self.order) >= VECTOR_THRESHOLD
        if self.vector:
            self._compile()

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

    @property
    def act(self):
        """Activations by node id. Only the UI wants this shape, so in the
        vectorised path it is built on demand rather than every tick."""
        if self.vector:
            return {n: float(self._vals[i]) for n, i in self._pos.items()}
        return self._act

    def _compile(self):
        """Lay the network out as flat arrays, grouped into evaluation levels.

        Every node in a level depends only on earlier levels, so one level is
        one scatter-add over all of its incoming edges at once.
        """
        pos = {n: i for i, n in enumerate(self.order)}
        self._pos = pos
        self._n = len(self.order)
        self._in_idx = np.array([pos[n] for n in self.inputs], dtype=np.int64)
        self._bias_idx = np.array([pos[n] for n in self.bias], dtype=np.int64)
        self._out_idx = np.array([pos[n] for n in self.outputs], dtype=np.int64)

        level = {n: 0 for n in self.order}
        for n in self.order:
            for src, _ in self.incoming.get(n, ()):
                level[n] = max(level[n], level[src] + 1)
        self.levels = []
        edges = {}
        for dst, ins in self.incoming.items():
            for src, w in ins:
                edges.setdefault(level[dst], []).append((pos[src], pos[dst], w))
        # every non-input node has to be evaluated, including ones sitting at
        # level 0 because their only inputs are recurrent - skipping those left
        # them stuck at zero and silently changed what the network computed
        nodes_at = {}
        for n, lv in level.items():
            if n not in self._fixed:
                nodes_at.setdefault(lv, []).append(pos[n])
        for lv in sorted(set(edges) | set(nodes_at)):
            e = edges.get(lv, [])
            self.levels.append((
                np.array([x[0] for x in e], dtype=np.int64),
                np.array([x[1] for x in e], dtype=np.int64),
                np.array([x[2] for x in e], dtype=float),
                np.array(sorted(nodes_at.get(lv, [])), dtype=np.int64),
            ))
        rec = [(pos[src], pos[dst], w)
               for dst, ins in self.recurrent.items() for src, w in ins]
        self._rec = (np.array([x[0] for x in rec], dtype=np.int64),
                     np.array([x[1] for x in rec], dtype=np.int64),
                     np.array([x[2] for x in rec], dtype=float))
        self._vals = np.zeros(self._n)

    def _step_vector(self, values):
        v = self._vals
        rs, rd, rw = self._rec
        prev = v.copy() if rs.size else None
        v[:] = 0.0
        v[self._in_idx[:len(values)]] = values[:len(self._in_idx)]
        v[self._bias_idx] = 1.0
        carry = (np.bincount(rd, weights=prev[rs] * rw, minlength=self._n)
                 if rs.size else None)
        for src, dst, w, nodes in self.levels:
            if src.size:
                totals = np.bincount(dst, weights=v[src] * w, minlength=self._n)
                if carry is not None:
                    totals = totals + carry
                if nodes.size:
                    v[nodes] = np.tanh(np.clip(totals[nodes], -30.0, 30.0))
            elif nodes.size:
                v[nodes] = (np.tanh(np.clip(carry[nodes], -30.0, 30.0))
                            if carry is not None else 0.0)
        return v[self._out_idx].tolist()

    def step(self, values):
        if self.vector:
            return self._step_vector(np.asarray(values, dtype=float))
        a = self._act
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
