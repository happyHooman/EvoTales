"""
The creature engine. Creatures are rows in numpy arrays (CreatureStore); three
systems own and update them, always in this order every frame:

    1. MetabolismSystem  writes store.vitals   energy, hunger, boldness, starvation, corpses
    2. BehaviourSystem   writes store.mind     decides and acts; writes store.command
                         (heading + speed it wants)
    3. PhysicsEngine     writes store.body     turns toward the command, moves, slides along
                         walls, keeps bodies solid

Each array group has exactly one writer; everything else only reads it.
"""
from .behaviour import BehaviourSystem
from .metabolism import MetabolismSystem
from .physics import PhysicsEngine
from .store import ACTION_NAMES, EAT, FLEE, RELAX, WANDER, CreatureStore

__all__ = ["CreatureEngine", "CreatureStore", "ACTION_NAMES", "WANDER", "RELAX", "EAT", "FLEE"]


class CreatureEngine:
    def __init__(self, world, species_types, sprite_sizes):
        self.store = CreatureStore(world, species_types, sprite_sizes)
        self.metabolism = MetabolismSystem(self.store)
        self.physics = PhysicsEngine(self.store, world)
        self.behaviour = BehaviourSystem(self.store, world, self.physics, self.metabolism)

    def step(self, dt):
        self.metabolism.step(dt)
        self.behaviour.step(dt)
        self.physics.step(self.store.living_rows(), dt)

    # Convenience pass-throughs
    def spawn(self, layer_name, x, y, energy=None):
        return self.store.spawn(layer_name, x, y, energy)

    def set_brain(self, row, brain):
        self.behaviour.set_brain(row, brain)

    def population(self, layer_name):
        return self.store.population(layer_name)

    def refresh_params(self):
        self.store.refresh_params()
