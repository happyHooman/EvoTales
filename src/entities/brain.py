"""
Brains decide what a creature does; the creature's body carries it out.

    observation = creature.observe()        # what the creature senses
    intent = brain.decide(observation)      # which action ("tool") to use
    creature.act(intent)                    # body executes it every frame

Every species runs on Instinct, a fixed deterministic rule set. Only smarties
may be given another Brain (for example a small language model that reads the
Observation and answers with a tool call); everything else stays instinctive.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Percept:
    """Something the creature can see."""
    entity: Any
    kind: str             # layer name: "plants", "herbivores", ...
    distance: float
    is_corpse: bool = False
    running: bool = False     # threats: is it running right now?
    attacking: bool = False   # threats: is it chasing me?


@dataclass(slots=True)
class Observation:
    energy: float
    energy_ratio: float
    foraging: bool            # hungry, and stays so until full
    relaxed: bool             # well fed and not foraging
    can_reproduce: bool
    current_target: Any       # what the creature is currently heading for, if anything
    food: list[Percept] = field(default_factory=list)     # nearest first
    threats: list[Percept] = field(default_factory=list)  # nearest first


@dataclass(slots=True)
class Intent:
    action: str               # one of Creature.ACTIONS
    target: Any = None        # entity to eat, or the threats to get away from
    run: bool = False         # run (faster, costs more) instead of walking
    reason: str = ""          # free text, handy for debugging and for LM brains


class Brain:
    """Base class. Subclasses implement decide()."""

    def decide(self, obs: Observation) -> Intent:
        raise NotImplementedError


class Instinct(Brain):
    """
    Deterministic behaviour shared by every species:

    1. Predators in sight: run away from any that is running or chasing me,
       otherwise walk away. This holds even while relaxing.
    2. Reproduce when the interval and energy allow it.
    3. Foraging (hungry until full): keep the current food target while it is
       in sight, otherwise go for the closest food. Run at moving prey, walk to
       plants, corpses and still prey. With no food in sight, roam.
    4. Well fed: relax (drift very slowly).
    5. Otherwise roam.
    """

    def decide(self, obs: Observation) -> Intent:
        if obs.threats:
            run = any(t.running or t.attacking for t in obs.threats)
            return Intent("flee", [t.entity for t in obs.threats], run=run, reason="predator in sight")
        if obs.can_reproduce:
            return Intent("reproduce", reason="ready to reproduce")
        if obs.foraging:
            target = None
            if obs.current_target is not None:
                target = next((p for p in obs.food if p.entity is obs.current_target), None)
            if target is None and obs.food:
                target = obs.food[0]
            if target is not None:
                run = getattr(target.entity, "is_moving", False)
                return Intent("eat", target.entity, run=run, reason="hungry")
            return Intent("wander", reason="looking for food")
        if obs.relaxed:
            return Intent("relax", reason="well fed")
        return Intent("wander")
