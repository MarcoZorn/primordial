import json
import os

from .genes import Conn, Genome


def save(genome, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = {
        "fitness": genome.fitness,
        "nodes": {str(k): v for k, v in genome.nodes.items()},
        "conns": [[c.innov, c.src, c.dst, c.w, c.enabled] for c in genome.conns.values()],
    }
    with open(path, "w") as fh:
        json.dump(data, fh)
    return path


def load(path):
    with open(path) as fh:
        data = json.load(fh)
    g = Genome({int(k): v for k, v in data["nodes"].items()},
               {i: Conn(s, d, w, bool(e), i) for i, s, d, w, e in data["conns"]})
    g.fitness = data.get("fitness", 0.0)
    return g
