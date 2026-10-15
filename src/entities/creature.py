"""
Species descriptors. Creatures themselves are rows in the Swarm's numpy arrays
(see swarm.py); a species class only carries its layer name, sprite and config.
"""
from config import CREATURE_DEFAULTS


class Creature:
    """Base for herbivores, smarties (omnivores) and carnivores."""

    layer_name: str = ""
    texture_name: str = ""
    config: dict | None = None  # Subclass sets species overrides; merged with CREATURE_DEFAULTS
    can_have_brain: bool = False  # Only smarties may think beyond their instincts

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.config is not None:
            merged = {**CREATURE_DEFAULTS, **cls.config}
            # Update in place so other modules holding the species dict see the full config
            cls.config.clear()
            cls.config.update(merged)
