"""
Brains decide what a creature does; the creature's body carries it out.

The contract is deliberately small so different brains can be swapped in:

    observation = creature.observe()        # what the creature senses
    intent = brain.decide(observation)      # which action ("tool") to use
    creature.act(intent)                    # body executes it every frame

An Intent names one of Creature.ACTIONS plus an optional target, which is the
same shape as a tool call. A future language-model brain can describe the
Observation in text, let the model pick a tool, and return an Intent.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .creature import Creature


@dataclass(slots=True)
class Percept:
    """Something the creature can see."""
    entity: Any
    kind: str          # layer name: "plants", "herbivores", ...
    distance: float


@dataclass(slots=True)
class Observation:
    energy: float
    energy_ratio: float
    age: float
    can_reproduce: bool
    food: list[Percept] = field(default_factory=list)     # nearest first
    threats: list[Percept] = field(default_factory=list)  # nearest first


@dataclass(slots=True)
class Intent:
    action: str                 # one of Creature.ACTIONS
    target: Any = None          # entity to move to / eat / flee from
    reason: str = ""            # free text, handy for debugging and for LM brains


class Brain:
    """Base class. Subclasses implement decide()."""

    def decide(self, obs: Observation) -> Intent:
        raise NotImplementedError


class SurvivalBrain(Brain):
    """
    Rule-based baseline shared by all species for now:
    flee threats > reproduce when able > eat when hungry > wander.
    """

    def __init__(self, hungry_ratio: float = 0.7):
        self.hungry_ratio = hungry_ratio

    def decide(self, obs: Observation) -> Intent:
        if obs.threats:
            return Intent("flee", obs.threats[0].entity, "threat in sight")
        if obs.can_reproduce:
            return Intent("reproduce", reason="enough energy")
        if obs.food and obs.energy_ratio < self.hungry_ratio:
            # Prefer close food, with a little randomness so a group spreads out
            choice = obs.food[0] if len(obs.food) == 1 or random.random() < 0.8 else obs.food[1]
            return Intent("eat", choice.entity, "hungry")
        return Intent("wander")
