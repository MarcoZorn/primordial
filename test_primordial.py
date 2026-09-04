"""Run with: python test_primordial.py

Small and assert-based on purpose. Each check is here because the thing it
checks broke at least once.
"""
import math
import random

from primordial.body import Body, CORE, MOVER, PHOTO, _connected
from primordial.brain import Brain
from primordial.config import Config
from primordial.evolution import Speciator
from primordial.genes import Genome, Innovations
from primordial.store import load, save
from primordial.world import N_OUTPUTS, World, n_inputs


def genome(cfg, innov, n=40):
    g = Genome.minimal(4, 2, innov, cfg)
    for _ in range(n):
        g.mutate(innov, cfg)
    return g


def test_innovations_are_shared():
    """The same structural change must get the same number for everyone,
    otherwise crossover lines genes up wrongly."""
    innov = Innovations()
    assert innov.conn(3, 7) == innov.conn(3, 7)
    assert innov.conn(3, 7) != innov.conn(7, 3)
    assert innov.split(5) == innov.split(5)


def test_networks_stay_acyclic():
    cfg, innov = Config(), Innovations()
    for seed in range(20):
        random.seed(seed)
        g = genome(cfg, innov, 80)
        b = Brain(g)
        # every node must appear in the topological order exactly once
        assert sorted(b.order) == sorted(g.nodes), "topological sort dropped a node"
        rank = {n: i for i, n in enumerate(b.order)}
        for src, dst, _ in b.edges:
            assert rank[src] < rank[dst], "edge points backwards - graph has a cycle"


def test_brain_is_deterministic_and_bounded():
    cfg, innov = Config(), Innovations()
    random.seed(1)
    b = Brain(genome(cfg, innov))
    a = b.step([0.3, -0.7, 1.0, 0.0])
    c = b.step([0.3, -0.7, 1.0, 0.0])
    assert a == c
    assert all(-1.0 <= v <= 1.0 for v in a), "tanh outputs must stay in range"


def test_add_node_preserves_behaviour_shape():
    cfg, innov = Config(), Innovations()
    random.seed(2)
    g = genome(cfg, innov, 30)
    before = len(g.nodes)
    g.mutate_add_node(innov)
    assert len(g.nodes) == before + 1
    disabled = [c for c in g.conns.values() if not c.enabled]
    assert disabled, "splitting a connection must disable the original"


def test_crossover_keeps_every_node_an_edge_needs():
    cfg, innov = Config(), Innovations()
    random.seed(3)
    a, b = genome(cfg, innov, 50), genome(cfg, innov, 50)
    a.fitness, b.fitness = 2.0, 1.0
    child = Genome.crossover(a, b, cfg)
    for c in child.conns.values():
        assert c.src in child.nodes and c.dst in child.nodes
    Brain(child)  # must be evaluable


def test_distance_is_zero_for_a_copy():
    cfg, innov = Config(), Innovations()
    random.seed(4)
    g = genome(cfg, innov)
    assert Genome.distance(g, g.copy(), cfg) == 0.0


def test_body_stays_connected():
    cfg = Config()
    random.seed(5)
    b = Body()
    for _ in range(300):
        b.mutate(cfg)
        assert _connected(b.cells), "mutation split the body into pieces"
        assert b.cells[(0, 0)] == CORE, "the core must survive every mutation"


def test_body_stats_respond_to_composition():
    cfg = Config()
    still = Body({(0, 0): CORE, (1, 0): PHOTO})
    swimmer = Body({(0, 0): CORE, (1, 0): MOVER})
    assert still.stats(cfg)["speed"] == 0.0, "no movers means no movement"
    assert swimmer.stats(cfg)["speed"] > 0.0
    assert still.stats(cfg)["light"] > swimmer.stats(cfg)["light"]
    assert still.kingdom() == "plant"


def test_world_runs_and_stays_consistent():
    cfg = Config(start_pop=60, world_w=800, world_h=600, n_obstacles=6)
    w = World(cfg, seed=11)
    w.seed_life(Innovations())
    for _ in range(400):
        w.step()
        for o in w.organisms:
            assert o.alive
            assert 0.0 <= o.x <= cfg.world_w and 0.0 <= o.y <= cfg.world_h
            assert not math.isnan(o.energy)
    c = w.census()
    assert c["pop"] == len(w.organisms)
    assert sum(c["cells"].values()) >= c["pop"], "every organism has at least a core"


def test_obstacles_push_organisms_out():
    cfg = Config(start_pop=1, n_obstacles=1)
    w = World(cfg, seed=2)
    w.seed_life(Innovations())
    ox, oy, orad = w.obstacles[0]
    o = w.organisms[0]
    o.x, o.y = ox + 1.0, oy
    w.clear_obstacles(o)
    assert math.hypot(o.x - ox, o.y - oy) >= orad, "organism left inside a rock"


def test_division_splits_energy_and_mutates():
    cfg = Config(start_pop=2, p_sex=0.0)
    w = World(cfg, seed=3)
    w.seed_life(Innovations())
    parent = w.organisms[0]
    parent.energy = 500.0
    child = w.divide(parent, [])
    assert child.gen == parent.gen + 1
    assert parent.energy < 500.0, "the parent pays for the split"
    assert child.energy <= parent.energy, "the child also pays to build its body"
    assert parent.energy + child.energy <= 500.0, "a split cannot create energy"


def test_a_corpse_never_returns_more_than_the_body_held():
    cfg = Config(start_pop=2)
    w = World(cfg, seed=9)
    w.seed_life(Innovations())
    o = w.organisms[0]
    o.energy = 140.0
    w.kill(o)
    corpse = w.corpses[-1]
    ceiling = o.energy + cfg.cell_build * o.body.mass
    assert corpse.energy <= ceiling, "death must not create energy"
    assert corpse.energy > 0


def test_speciator_groups_and_clears():
    cfg = Config(start_pop=40, world_w=600, world_h=600)
    w = World(cfg, seed=4)
    w.seed_life(Innovations())
    spec = Speciator(cfg)
    spec.update(w.organisms, 0)
    assert spec.species
    assert sum(len(s.members) for s in spec.species.values()) == len(w.organisms)
    spec.update([], 1)
    assert not spec.species, "empty species must be dropped"


def test_genome_survives_a_save_load_round_trip(tmp="runs/_test.json"):
    cfg, innov = Config(), Innovations()
    random.seed(6)
    g = genome(cfg, innov, 60)
    back = load(save(g, tmp))
    assert back.nodes == g.nodes
    assert len(back.conns) == len(g.conns)
    a = Brain(g).step([0.1, 0.2, 0.3, 0.4])
    b = Brain(back).step([0.1, 0.2, 0.3, 0.4])
    assert a == b, "a reloaded genome must compute the same thing"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} passed")
