"""NEAT genome: nodes, connections, mutation, crossover.

Reference: Stanley & Miikkulainen (2002), "Evolving Neural Networks through
Augmenting Topologies".
"""
import random
from dataclasses import dataclass, replace

INPUT, BIAS, HIDDEN, OUTPUT = "in", "bias", "hid", "out"


class Innovations:
    """Global historical markings, shared by the whole population.

    Two genomes that grew the same structure independently must get the same
    innovation number, otherwise crossover cannot line them up.
    """

    def __init__(self):
        self._conn = {}
        self._split = {}
        self.next_conn = 0
        self.next_node = 0

    def conn(self, src, dst):
        key = (src, dst)
        if key not in self._conn:
            self._conn[key] = self.next_conn
            self.next_conn += 1
        return self._conn[key]

    def node(self):
        n = self.next_node
        self.next_node += 1
        return n

    def split(self, conn_innov):
        """Node id created by splitting this connection (same for everyone)."""
        if conn_innov not in self._split:
            self._split[conn_innov] = self.node()
        return self._split[conn_innov]


@dataclass(slots=True)
class Conn:
    src: int
    dst: int
    w: float
    enabled: bool
    innov: int


class Genome:
    def __init__(self, nodes=None, conns=None):
        self.nodes = nodes or {}       # id -> INPUT/BIAS/HIDDEN/OUTPUT
        self.conns = conns or {}       # innov -> Conn
        self.fitness = 0.0
        self.adjusted = 0.0
        self.species = 0

    # --- construction ---

    @classmethod
    def minimal(cls, n_in, n_out, innov, cfg, connect=True):
        """Inputs + bias + outputs, no hidden layer. NEAT starts from nothing."""
        g = cls()
        ins = [innov.node() for _ in range(n_in)]
        bias = innov.node()
        outs = [innov.node() for _ in range(n_out)]
        for i in ins:
            g.nodes[i] = INPUT
        g.nodes[bias] = BIAS
        for o in outs:
            g.nodes[o] = OUTPUT
        if connect:
            for s in ins + [bias]:
                for d in outs:
                    g.add_conn(s, d, random.gauss(0, cfg.weight_init_std), innov)
        return g

    def copy(self):
        g = Genome(dict(self.nodes), {i: replace(c) for i, c in self.conns.items()})
        return g

    def add_conn(self, src, dst, w, innov):
        i = innov.conn(src, dst)
        self.conns[i] = Conn(src, dst, w, True, i)
        return i

    # --- queries ---

    def ids(self, *kinds):
        return [i for i, k in self.nodes.items() if k in kinds]

    def _creates_cycle(self, src, dst):
        """Would src->dst close a loop? Networks stay feedforward."""
        if src == dst:
            return True
        stack, seen = [dst], set()
        while stack:
            n = stack.pop()
            if n == src:
                return True
            if n in seen:
                continue
            seen.add(n)
            stack.extend(c.dst for c in self.conns.values() if c.src == n)
        return False

    # --- mutation ---

    def mutate(self, innov, cfg):
        if random.random() < cfg.p_weight:
            self.mutate_weights(cfg)
        if random.random() < cfg.p_add_conn:
            self.mutate_add_conn(innov, cfg)
        if random.random() < cfg.p_add_node:
            self.mutate_add_node(innov)
        if random.random() < cfg.p_toggle:
            self.mutate_toggle()
        return self

    def mutate_weights(self, cfg):
        for c in self.conns.values():
            if random.random() < cfg.p_weight_replace:
                c.w = random.gauss(0, cfg.weight_init_std)
            else:
                c.w += random.gauss(0, cfg.weight_step)
            c.w = max(-cfg.weight_cap, min(cfg.weight_cap, c.w))

    def mutate_add_conn(self, innov, cfg):
        sources = self.ids(INPUT, BIAS, HIDDEN)
        targets = self.ids(HIDDEN, OUTPUT)
        if not sources or not targets:
            return
        existing = {(c.src, c.dst) for c in self.conns.values()}
        for _ in range(cfg.add_conn_tries):
            s, d = random.choice(sources), random.choice(targets)
            if (s, d) in existing or self._creates_cycle(s, d):
                continue
            self.add_conn(s, d, random.gauss(0, cfg.weight_init_std), innov)
            return

    def mutate_add_node(self, innov):
        """Split a connection in two. The old one is disabled, not deleted."""
        live = [c for c in self.conns.values() if c.enabled]
        if not live:
            return
        old = random.choice(live)
        old.enabled = False
        new = innov.split(old.innov)
        self.nodes[new] = HIDDEN
        self.add_conn(old.src, new, 1.0, innov)
        self.add_conn(new, old.dst, old.w, innov)

    def mutate_toggle(self):
        if self.conns:
            c = random.choice(list(self.conns.values()))
            c.enabled = not c.enabled

    # --- crossover / distance ---

    @staticmethod
    def crossover(a, b, cfg):
        """a is the fitter parent. Shared genes are picked at random from both,
        the rest are inherited from the fitter one only."""
        if b.fitness > a.fitness:
            a, b = b, a
        child = Genome(dict(a.nodes), {})
        for i, ca in a.conns.items():
            cb = b.conns.get(i)
            c = replace(ca if cb is None or random.random() < 0.5 else cb)
            if cb is not None and not (ca.enabled and cb.enabled):
                c.enabled = random.random() > cfg.p_inherit_disabled
            child.conns[i] = c
        for c in child.conns.values():
            child.nodes.setdefault(c.src, HIDDEN)
            child.nodes.setdefault(c.dst, HIDDEN)
        return child

    @staticmethod
    def distance(a, b, cfg):
        """Compatibility distance. Drives speciation."""
        ia, ib = set(a.conns), set(b.conns)
        shared = ia & ib
        n = max(len(ia), len(ib), 1)
        if n < cfg.small_genome:
            n = 1
        dw = sum(abs(a.conns[i].w - b.conns[i].w) for i in shared) / len(shared) if shared else 0.0
        return cfg.c_disjoint * len(ia ^ ib) / n + cfg.c_weight * dw

    def complexity(self):
        return len(self.nodes), sum(1 for c in self.conns.values() if c.enabled)
