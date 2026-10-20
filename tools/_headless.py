"""Shared setup for headless tools: run from the repo root, simulate without a window."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))


def world(map_source=None, seed=None, settings_file=False):
    """A fresh EntityManager. map_source "tiled" gives the fixed hand-made map (for
    reproducible checks); settings_file=True applies the user's settings.json."""
    import random
    import numpy as np
    import config
    import settings
    if settings_file:
        settings.apply(settings.load())
    else:
        settings.apply({})
    if map_source:
        config.MAP_CONFIG["source"] = map_source
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    from sprite_manager import sprite_manager
    sprite_manager.load_all_sprite_sheets()
    from entities.entity_manager import EntityManager
    return EntityManager()


def run(em, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt)):
        em.update(dt)
