"""Save and restore a whole run.

A research run is meant to last months, across reboots and crashes, so the
simulation has to be able to stop mid-tick and come back as the same world -
same organisms, same innovation numbers, same random stream. Writes go to a
temporary file and are renamed into place, so a checkpoint is never half
written even if the process dies during a save.
"""
import gzip
import os
import pickle
import random
import time

# bump whenever the genome, the body encoding or the sensory layout changes:
# an old checkpoint restored into a new engine is silently wrong, not broken
VERSION = 3


def save(path, world, spec, innov, extra=None):
    state = {
        "version": VERSION,
        "saved": time.time(),
        "world": world,
        "spec": spec,
        "innov": innov,
        "cfg": world.cfg,
        "py_random": random.getstate(),
        "extra": extra or {},
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # per-process temp name: two writers must never share one staging file
    tmp = f"{path}.{os.getpid()}.tmp"
    with gzip.open(tmp, "wb", compresslevel=4) as fh:
        pickle.dump(state, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)
    return path


def load(path):
    with gzip.open(path, "rb") as fh:
        state = pickle.load(fh)
    if state.get("version") != VERSION:
        raise ValueError(f"checkpoint version {state.get('version')} != {VERSION}")
    _refresh_config(state)
    random.setstate(state["py_random"])
    return state


def _refresh_config(state):
    """Fill in config fields added since this checkpoint was written.

    A run is meant to outlive many edits to the code. An old Config instance
    unpickled into a newer engine is simply missing the new attributes, and the
    first line that reads one crashes the run. Defaults are copied in; anything
    already set is left exactly as it was.
    """
    from .config import Config
    fresh = Config()
    cfg = state.get("cfg") or getattr(state.get("world"), "cfg", None)
    if cfg is None:
        return
    added = []
    for name, value in vars(fresh).items():
        if not hasattr(cfg, name):
            setattr(cfg, name, value)
            added.append(name)
    if added:
        print(f"checkpoint: filled in new config fields {', '.join(sorted(added))}")


def newest(path):
    """The checkpoint, or its backup if the main one is unreadable."""
    for p in (path, f"{path}.prev"):
        if os.path.exists(p):
            try:
                return load(p), p
            except Exception:
                continue
    return None, None


def rotate(path):
    if os.path.exists(path):
        try:
            os.replace(path, f"{path}.prev")
        except OSError:
            pass
