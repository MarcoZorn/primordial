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

VERSION = 1


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
    tmp = f"{path}.tmp"
    with gzip.open(tmp, "wb", compresslevel=4) as fh:
        pickle.dump(state, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)
    return path


def load(path):
    with gzip.open(path, "rb") as fh:
        state = pickle.load(fh)
    if state.get("version") != VERSION:
        raise ValueError(f"checkpoint version {state.get('version')} != {VERSION}")
    random.setstate(state["py_random"])
    return state


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
