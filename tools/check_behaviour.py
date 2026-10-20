"""
Behaviour checks (headless, fixed map). Prints what happened in each scenario.

    .venv/bin/python tools/check_behaviour.py
"""
import math

import numpy as np

from _headless import run, world

from engine import ACTION_NAMES  # noqa: E402  (after _headless sets the path)
from entities.brain import Brain, Intent  # noqa: E402
from entities.plant import Plant  # noqa: E402


def dist(st, a, b):
    return math.hypot(st.body.x[a] - st.body.x[b], st.body.y[a] - st.body.y[b])


def chase():
    em = world("tiled", seed=3)
    eng, st = em.creatures, em.creatures.store
    c = eng.spawn("carnivores", 2000, 1200, food=60)
    h = eng.spawn("herbivores", 2120, 1200, food=3)
    run(em, 8)
    return f"starving prey vs hungry hunter -> {dict(em.stats)}"


def walk_away_then_relax():
    em = world("tiled", seed=3)
    eng, st = em.creatures, em.creatures.store
    c = eng.spawn("carnivores", 1000, 1000, food=215); st.vitals.foraging[c] = False
    h = eng.spawn("herbivores", 1150, 1000, food=145); st.vitals.foraging[h] = False
    st.vitals.reproduction_timer[h] = 99
    run(em, 0.5)
    first = f"{ACTION_NAMES[st.mind.action[h]]} ({'running' if st.mind.running[h] else 'walking'})"
    run(em, 6)
    return f"fed hunter nearby: {first}, later {ACTION_NAMES[st.mind.action[h]]} at {dist(st, c, h):.0f}px"


def hunger_beats_fear():
    out = []
    for food in (85, 50, 15):
        ate = 0
        for trial in range(30):
            em = world("tiled", seed=trial)
            eng, st = em.creatures, em.creatures.store
            c = eng.spawn("carnivores", 1500, 1200, food=210); st.vitals.foraging[c] = False
            h = eng.spawn("herbivores", 1650, 1200, food=food); st.vitals.reproduction_timer[h] = 99
            Plant.spawn(em, 1610, 1200, growth_level=4)
            run(em, 3)
            ate += st.vitals.food[h] > food
        out.append(f"food {food}: {ate}/30")
    return "ate next to a predator: " + ", ".join(out)


def stays_on_land():
    em = world(None, seed=5)
    em.spawn_initial_population()
    run(em, 120)
    st = em.creatures.store
    n = st.count
    live = st.used[:n]
    bad = int(em.blocked_at(st.body.x[:n][live], st.body.y[:n][live]).sum())
    return f"creatures in water after 2 min: {bad} of {int(live.sum())}"


def brain_hook():
    class Greedy(Brain):
        def decide(self, obs):
            return Intent("eat", obs.food[0].entity) if obs.food else Intent("wander")
    em = world("tiled", seed=1)
    eng, st = em.creatures, em.creatures.store
    r = eng.spawn("smarties", 1500, 1200, food=100); st.vitals.foraging[r] = False
    eng.set_brain(r, Greedy())
    Plant.spawn(em, 1560, 1200, growth_level=4)
    run(em, 6)
    try:
        eng.set_brain(eng.spawn("herbivores", 100, 100), Greedy())
        refused = "NOT refused"
    except ValueError:
        refused = "refused"
    return f"brain-driven smartie ate: {st.vitals.food[r] > 100}; herbivore brain {refused}"


if __name__ == "__main__":
    for check in (chase, walk_away_then_relax, hunger_beats_fear, stays_on_land, brain_hook):
        print(f"{check.__name__:22} {check()}", flush=True)
