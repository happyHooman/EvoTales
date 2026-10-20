"""
Headless scenario sweep: run many variations of the settings, score how
interesting each run would be to watch, and save the best as presets.

    .venv/bin/python tools/scenarios.py --runs 24 --minutes 12 --workers 12

"Interesting" (see score()):
- all three species are still around at the end (extinctions and rescues cost)
- populations swing (boom and bust) rather than sitting flat at a cap
- lots of action per creature: chases, kills, escapes, fights back, alarm calls,
  squabbles and fights for space
- a watchable crowd size (not a handful, not thousands)
- evolution moves: genes drift away from the founders
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Each knob: (section, key, low, high). Values are sampled uniformly per run.
KNOBS = [
    ("plants", "regrow_time", 5.0, 25.0),
    ("plants", "reproduction_delay", 10.0, 35.0),
    ("world", "season_strength", 0.3, 0.9),
    ("herbivores", "herd_cohesion", 0.0, 0.8),
    ("herbivores", "attack", 2.0, 12.0),
    ("herbivores", "reproduction_interval", 15.0, 45.0),
    ("herbivores", "max_population", 80, 400),
    ("smarties", "attack", 8.0, 25.0),
    ("smarties", "reproduction_interval", 20.0, 50.0),
    ("smarties", "max_population", 30, 150),
    ("carnivores", "max_stamina", 16.0, 40.0),
    ("carnivores", "sprint_range", 100.0, 260.0),
    ("carnivores", "attack", 25.0, 60.0),
    ("carnivores", "max_population", 10, 60),
    ("carnivores", "reproduction_interval", 25.0, 70.0),
    ("herbivores", "crowd_limit", 2, 8),
]
SPECIES = ("herbivores", "smarties", "carnivores")


def sample(rng):
    overrides = {}
    for section, key, lo, hi in KNOBS:
        value = rng.uniform(lo, hi)
        if isinstance(lo, int):
            value = int(round(value))
        else:
            value = round(value, 2)
        overrides.setdefault(section, {})[key] = value
    overrides.setdefault("map", {})["seed"] = rng.randint(0, 999999)
    return overrides


def simulate(job):
    name, overrides, minutes, seed = job
    from _headless import world
    import numpy as np
    import settings
    em = world(seed=seed)
    settings.apply(overrides)
    em = _rebuild(overrides, seed)
    em.spawn_initial_population()
    st = em.creatures.store
    from engine.store import GENES
    history = {s: [] for s in SPECIES}
    t0 = time.time()
    for _ in range(int(minutes * 6)):           # sample every 10 sim-seconds
        for _ in range(600):
            em.update(1 / 60)
        for s in SPECIES:
            history[s].append(em.population(s))
    rows = st.living_rows()
    drift = float(np.mean([abs(np.log(getattr(st.genes, g)[rows])).mean() for g in GENES])) if len(rows) else 0.0
    return {"name": name, "overrides": overrides, "history": history, "stats": dict(em.stats),
            "drift": drift, "seconds": time.time() - t0}


def _rebuild(overrides, seed):
    """Settings must be in place before the world (and map) are built."""
    import random as _r
    import numpy as np
    import settings
    settings.apply(overrides)
    _r.seed(seed)
    np.random.seed(seed)
    from entities.entity_manager import EntityManager
    return EntityManager()


def score(result):
    import numpy as np
    h = {s: np.array(v, dtype=float) for s, v in result["history"].items()}
    st = result["stats"]
    minutes = len(h["herbivores"]) / 6
    alive_end = sum(h[s][-1] > 0 for s in SPECIES)
    rescues = sum(v for k, v in st.items() if "reintroduced" in k)
    mean_pop = sum(h[s].mean() for s in SPECIES)
    swings = np.mean([h[s].std() / max(h[s].mean(), 1) for s in SPECIES])
    def count(*words):
        return sum(v for k, v in st.items() if any(w in k for w in words))
    kills = count("killed by carnivores", "killed by smarties")
    chases = count("chases started")
    escapes = max(chases - kills, 0)
    fights = count("fighting back", "fought off", "fought for space", "drove off")
    calls = count("alarm calls")
    # Fights for space are capped: a few are drama, thousands just mean a crush
    action = (kills + 0.5 * escapes + min(fights, 20 * minutes) + 0.1 * calls) / max(mean_pop, 1) / max(minutes, 1)
    crowd_ok = 1.0 if 60 <= mean_pop <= 600 else 0.5
    parts = {
        "coexistence": alive_end / 3 - 0.15 * rescues,
        "swings": min(swings, 0.8) / 0.8,
        "action": min(action / 2.0, 1.0),
        "evolution": min(result["drift"] / 0.15, 1.0),
        "crowd": crowd_ok,
    }
    total = (2.0 * parts["coexistence"] + 1.5 * parts["swings"] + 2.0 * parts["action"]
             + 0.5 * parts["evolution"] + 1.0 * parts["crowd"])
    return total, parts, {"kills": kills, "chases": chases, "escapes": escapes, "fights": fights,
                          "calls": calls, "rescues": rescues, "mean_pop": round(mean_pop)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=24)
    ap.add_argument("--minutes", type=float, default=12)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--save-top", type=int, default=3)
    ap.add_argument("--report", default="scenarios_report.json")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    jobs = [("baseline", {}, args.minutes, 1)]
    jobs += [(f"variant {i:02d}", sample(rng), args.minutes, i + 2) for i in range(args.runs - 1)]
    with mp.get_context("spawn").Pool(args.workers) as pool:
        results = pool.map(simulate, jobs)
    ranked = []
    for r in results:
        total, parts, facts = score(r)
        ranked.append({**r, "score": round(total, 2), "parts": {k: round(v, 2) for k, v in parts.items()},
                       "facts": facts})
    ranked.sort(key=lambda r: -r["score"])
    for r in ranked:
        ends = {s: r["history"][s][-1] for s in SPECIES}
        print(f"{r['score']:5.2f} {r['name']:11} {r['parts']} {r['facts']} end={ends}")
    with open(args.report, "w") as f:
        json.dump(ranked, f, indent=1)
    import _headless  # noqa: F401  (puts src/ on the path)
    import settings
    for k, r in enumerate(ranked[:args.save_top]):
        values = settings.current_values(r["overrides"])
        name = settings.save_preset(f"Scenario {k + 1} ({r['name']})", values)
        print("saved preset:", name)


if __name__ == "__main__":
    main()
