"""
Measure the rates a predator-prey model needs, in small controlled headless
"arenas" where the counts are held fixed (no breeding; whoever dies or is eaten is
replaced), so each number belongs to one known density:

  hunt      kills per hunter per minute at a given prey density (functional
            response), and how much of a hunter's food comes from meat vs plants
  graze     food a grazer gets per minute at a given crowd size (competition for plants)
  budget    food each species burns per minute: being alive, walking, running, healing,
            weighted by how much of its time it spends in each gait

    .venv/bin/python tools/measure.py --minutes 6 --out measurements.json
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _var in ("VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

SPECIES = ("herbivores", "smarties", "carnivores")
DT = 1 / 30
SETTLE_S = 60.0
FROZEN = 1e9   # a reproduction interval nobody reaches


def _background():
    try:
        os.nice(15)
    except OSError:
        pass


def arena(job):
    """Hold each species at a fixed count for job['minutes'] and record what happens."""
    import _headless  # noqa: F401
    import numpy as np
    import settings
    counts = job["counts"]
    ov = {"world": {"season_strength": 0.0}, "map": {"seed": job.get("map_seed", 7)}}
    hold = job.get("hold", list(counts))  # species kept at a fixed count (no breeding, dead replaced)
    for sp in SPECIES:
        ov[sp] = {"initial_count": counts.get(sp, 0), "reintroduce_after": 0, "max_population": 100000}
        if sp in hold:
            ov[sp]["reproduction_interval"] = FROZEN
    for section, values in job.get("overrides", {}).items():  # parameter values under test
        ov.setdefault(section, {}).update(values)
    settings.apply(ov)
    random.seed(job["seed"])
    np.random.seed(job["seed"])
    from sprite_manager import sprite_manager
    sprite_manager.load_all_sprite_sheets()
    from entities.entity_manager import CREATURE_TYPES, EntityManager
    em = EntityManager()
    em.spawn_initial_population()
    st, eng = em.creatures.store, em.creatures
    types = {c.layer_name: c for c in CREATURE_TYPES}

    # Who ate what: eat_plant is called right before metabolism.eat for plant meals
    meals = Counter()
    state = {"plant": False}
    eat_plant = em.eat_plant

    def eat_plant_logged(index):
        state["plant"] = True
        return eat_plant(index)
    em.eat_plant = eat_plant_logged
    metab_eat = eng.metabolism.eat

    def eat_logged(row, amount):
        sp = st.species_type(row).layer_name
        absorbed = min(amount, max(float(st.p("max_food", row)) - float(st.vitals.food[row]), 0.0))
        meals[(sp, "plants" if state["plant"] else "meat")] += absorbed
        state["plant"] = False
        return metab_eat(row, amount)
    eng.metabolism.eat = eat_logged
    eng.behaviour.metabolism.eat = eat_logged

    def top_up():
        for sp, n in counts.items():
            if sp not in hold:
                continue
            missing = n - em.population(sp)
            cfg = types[sp].config
            for _ in range(max(missing, 0)):
                pos = em.random_free_position(cfg["bounds_padding"])
                if pos is not None:
                    food = cfg["max_food"] * random.uniform(cfg["hungry_ratio"], cfg["full_ratio"])
                    eng.spawn(sp, *pos, food=food)

    series = {sp: [] for sp in counts}
    gait = Counter()
    food_ratio = Counter()
    samples = Counter()
    steps = int(job["minutes"] * 60 / DT)
    settle = int(SETTLE_S / DT)
    start_stats = None
    for k in range(steps):
        em.update(DT)
        if k % 30 == 0:
            top_up()
        if k % int(30 / DT) == 0:
            for sp in counts:
                series[sp].append(em.population(sp))
        if k == settle:
            start_stats = Counter(em.stats)
            meals.clear()
        if k > settle and k % 15 == 0:
            rows = st.living_rows()
            for sp in counts:
                r = rows[st.species[rows] == st.layer_index[sp]]
                if not len(r):
                    continue
                walk = st.p("walk_speed", r)
                speed = st.body.speed[r]
                gait[(sp, "rest")] += int((speed <= walk * 0.5).sum())
                gait[(sp, "walk")] += int(((speed > walk * 0.5) & (speed <= walk * 1.2)).sum())
                gait[(sp, "run")] += int((speed > walk * 1.2).sum())
                food_ratio[sp] += float((st.vitals.food[r] / st.p("max_food", r)).sum())
                samples[sp] += len(r)
    minutes = (steps - settle) * DT / 60
    stats = Counter(em.stats)
    stats.subtract(start_stats)
    out = {"job": job, "minutes": minutes, "series": series, "stats": {k: v for k, v in stats.items() if v},
           "meals": {f"{a}:{b}": v for (a, b), v in meals.items()},
           "gait": {f"{a}:{b}": v for (a, b), v in gait.items()},
           "food_ratio": {sp: food_ratio[sp] / samples[sp] for sp in samples}}
    return out


def budget():
    """Food burned per minute per gait, straight from the species parameters."""
    import _headless  # noqa: F401
    import settings
    settings.apply({})
    from entities.entity_manager import CREATURE_TYPES
    out = {}
    for c in CREATURE_TYPES:
        p = c.config
        k_run = p["run_stamina_multiplier"]
        alive, walk, drain = p["alive_stamina_cost"], p["walk_stamina_cost"], p["food_drain"]
        eff = p["digest_efficiency"]
        out[c.layer_name] = {
            "rest": round(60 * (drain + alive / eff), 1),
            "walk": round(60 * (drain + (alive + walk) / eff), 1),
            "run": round(60 * (drain + (alive + walk * k_run) / eff), 1),
            "max_food": p["max_food"], "nutrition": p["nutrition"],
            "birth_cost": p["reproduction_food_cost"], "birth_threshold": p["reproduction_food_threshold"],
            "birth_interval": p["reproduction_interval"],
        }
    return out


def jobs(minutes):
    out = []
    for n in (25, 50, 100, 200, 400, 800):
        out.append({"name": "carnivores hunt herbivores", "counts": {"carnivores": 12, "herbivores": n}})
        out.append({"name": "smarties hunt herbivores", "counts": {"smarties": 30, "herbivores": n}})
    for n in (10, 20, 40, 80, 160):
        out.append({"name": "carnivores hunt smarties", "counts": {"carnivores": 12, "smarties": n}})
    for n in (50, 100, 200, 400, 800, 1600):
        out.append({"name": "herbivores graze", "counts": {"herbivores": n}})
    for n in (20, 40, 80, 160, 320):
        out.append({"name": "smarties graze", "counts": {"smarties": n}})
    for i, j in enumerate(out):
        j.update(seed=100 + i, minutes=minutes)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=6)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 4))
    ap.add_argument("--out", default="measurements.json")
    args = ap.parse_args()
    results = {"budget": budget(), "arenas": []}
    with mp.get_context("spawn").Pool(args.workers, initializer=_background) as pool:
        for r in pool.imap_unordered(arena, jobs(args.minutes)):
            results["arenas"].append(r)
            print(r["job"]["name"], r["job"]["counts"], flush=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=1)


if __name__ == "__main__":
    main()
