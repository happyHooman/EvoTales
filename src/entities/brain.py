"""
Brains decide what a creature does; the swarm's body logic carries it out.

Every species runs on the instinct rules implemented (vectorized) in swarm.py.
Only smarties may be given another Brain (for example a small language model
that reads the Observation and answers with a tool call):

    swarm.set_brain(row, MyBrain())
    # each decision: Observation -> brain.decide() -> Intent
    #   Intent.action is one of "wander", "relax", "eat", "flee", "reproduce";
    #   Intent.target is a percept's entity handle, e.g. ("plant", 12) or ("creature", 40)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Percept:
    """Something the creature can see."""
    entity: Any           # handle: ("plant", index) or ("creature", row)
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
    bold: bool                # hunger currently outweighs fear (a dice roll that grows with hunger)
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
