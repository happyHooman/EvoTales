"""
Search for settings that make a self-sustaining world: no species dies out,
populations rise and fall in waves, nobody needs rescuing, caps are never what
holds a population back, and creatures don't crowd into a few spots.

Validation conditions (checked every 5 sim-seconds, a run stops at the first failure):
  FAIL  extinct        a species reaches 0 (reintroduction is switched off)
  FAIL  near-extinct   after a warm-up, a species drops below FLOOR creatures
  FAIL  explosion      more than MAX_TOTAL creatures in total (crowded, laggy, and a sign of no control)
Measured over a run that survives:
  waves      boom-bust cycles per species: a rise of >= WAVE_RATIO x from a trough
             and a fall back by the same factor counts as one wave
  low_ratio  lowest population after warm-up / its average (how close it came to zero)
  at_cap     share of samples a species sits at >= 90% of its cap (cap doing the balancing)
  crowding   share of creatures with 4+ of their own kind within 40 px (a crowd on screen)
A setting PASSES when it survives the whole run on every seed and, for every species,
has at least one wave per sim-year, low_ratio >= MIN_LOW_RATIO, never sits at its cap,
and crowding stays under MAX_CROWDING. The score also prefers fewer than PEAK_TOTAL
creatures at the busiest moment.

Strategy: the food web is tuned one layer at a time (plants + herbivores, then
hunters on top, then smarties) to get a base where all three live; the search then
varies KNOBS around it with all three species present:
  explore   random settings, one seed each (cheap: failures stop early)
  confirm   the best explored settings on several new seeds and maps
  refine    small random changes around the confirmed ones, kept if they do better
  evolve    keep the best few, try mutated copies, all on the same maps (default map
            included), generation after generation
  validate  long runs on more seeds for the finalists
  save      the validated settings that pass become presets ("Balanced - ...")

    .venv/bin/python tools/balance.py explore  --n 140 --minutes 50 --out runs/
    .venv/bin/python tools/balance.py confirm  --top 14 --seeds 3 --minutes 50 --out runs/
    .venv/bin/python tools/balance.py refine   --rounds 2 --children 6 --seeds 3 --minutes 50 --out runs/
    .venv/bin/python tools/balance.py validate --top 6 --seeds 5 --minutes 100 --out runs/
    .venv/bin/python tools/balance.py save     --out runs/
"""
import argparse
import copy
import json
import multiprocessing as mp
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Many worlds run side by side: one math thread each, so they don't fight over cores
for _var in ("VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

SPECIES = ("herbivores", "smarties", "carnivores")
FLOOR = 5
WARMUP_MIN = 6.0
MAX_TOTAL = 1500        # more than this at once is too crowded (and slow) to be a good setting
EVAL_CAP = 2000          # caps during evaluation: safety only
WAVE_RATIO = 1.5
MIN_LOW_RATIO = 0.15
MAX_CROWDING = 0.03
CROWD_RADIUS = 40        # a crowd on screen: CROWD_PEERS or more of the same species this close
CROWD_PEERS = 4
PEAK_TOTAL = 1000        # more creatures than this at once costs score (busy screen, slower frames)
SAMPLE_S = 5.0
DT = 1 / 30

# Starting point for a search, on top of the code defaults. The defaults in config.py
# are already the result of this process (layered hand tuning, then evolve + validate),
# so this is empty; put overrides here to search around something else.
BASE = {}

# (section, key, low, high, kind). kind: "f" float, "i" int. Ranges stay within what
# keeps behaviour readable (no huge personal spaces, no hidden creatures): tuning only.
KNOBS = [
    ("world", "season_strength", 0.1, 0.5, "f"),
    ("plants", "regrow_time", 20.0, 150.0, "f"),
    ("plants", "min_spacing", 30, 70, "i"),
    ("plants", "max_growth_timer", 8.0, 25.0, "f"),
    ("plants", "reproduction_delay", 15.0, 60.0, "f"),
    ("herbivores", "initial_count", 60, 200, "i"),
    ("herbivores", "reproduction_interval", 12.0, 60.0, "f"),
    ("herbivores", "run_speed_multiplier", 2.0, 2.5, "f"),
    ("herbivores", "reproduction_food_threshold", 90, 140, "i"),
    ("herbivores", "reproduction_food_cost", 40, 70, "i"),
    ("herbivores", "food_drain", 0.15, 0.4, "f"),
    ("herbivores", "alive_stamina_cost", 0.2, 0.5, "f"),
    ("herbivores", "walk_stamina_cost", 0.6, 1.2, "f"),
    ("herbivores", "herd_bonus", 0.3, 1.0, "f"),
    ("herbivores", "attack", 2.0, 6.0, "f"),
    ("herbivores", "nutrition", 40, 100, "i"),
    ("herbivores", "vision_range", 160, 260, "i"),
    ("herbivores", "max_stamina", 60.0, 130.0, "f"),
    ("herbivores", "personal_space", 25, 40, "i"),
    ("herbivores", "crowd_limit", 3, 6, "i"),
    ("smarties", "initial_count", 10, 40, "i"),
    ("smarties", "reproduction_interval", 40.0, 180.0, "f"),
    ("smarties", "reproduction_food_threshold", 120, 175, "i"),
    ("smarties", "reproduction_food_cost", 50, 80, "i"),
    ("smarties", "food_drain", 0.3, 0.8, "f"),
    ("smarties", "alive_stamina_cost", 0.3, 0.8, "f"),
    ("smarties", "max_food", 120, 200, "i"),
    ("smarties", "walk_speed", 30.0, 38.0, "f"),
    ("smarties", "walk_stamina_cost", 0.8, 1.2, "f"),
    ("smarties", "attack", 20.0, 40.0, "f"),
    ("smarties", "crowd_penalty", 0.0, 1.0, "f"),
    ("smarties", "max_health", 100, 140, "i"),
    ("smarties", "personal_space", 25, 50, "i"),
    ("smarties", "crowd_limit", 2, 4, "i"),
    ("carnivores", "initial_count", 6, 20, "i"),
    ("carnivores", "reproduction_interval", 60.0, 300.0, "f"),
    ("carnivores", "reproduction_food_threshold", 150, 210, "i"),
    ("carnivores", "reproduction_food_cost", 60, 160, "i"),
    ("carnivores", "crowd_damage", 0.1, 1.0, "f"),
    ("carnivores", "food_drain", 0.15, 0.35, "f"),
    ("carnivores", "alive_stamina_cost", 0.2, 0.45, "f"),
    ("carnivores", "walk_stamina_cost", 0.5, 0.9, "f"),
    ("carnivores", "attack", 35.0, 60.0, "f"),
    ("carnivores", "hungry_ratio", 0.35, 0.65, "f"),
    ("carnivores", "max_food", 200, 300, "i"),
    ("carnivores", "crowd_penalty", 0.0, 0.8, "f"),
    ("carnivores", "digest_rate", 2.0, 4.0, "f"),
    ("carnivores", "max_stamina", 20.0, 40.0, "f"),
    ("carnivores", "personal_space", 30, 80, "i"),
]


# ------------------------------------------------------------------ settings

def sample_knobs(rng):
    return {f"{s}:{k}": _draw(rng, lo, hi, kind) for s, k, lo, hi, kind in KNOBS}


def mutate_knobs(knobs, rng, strength=0.15, share=0.35):
    child = dict(knobs)
    for s, k, lo, hi, kind in KNOBS:
        key = f"{s}:{k}"
        if key not in child:  # a knob added since the parent was made
            child[key] = _draw(rng, lo, hi, kind)
            continue
        value = child[key]
        if rng.random() < share:
            value += rng.gauss(0, strength * (hi - lo))
        value = min(max(value, lo), hi)  # ranges may have moved since the parent was made
        child[key] = int(round(value)) if kind == "i" else round(value, 3)
    return child


def _draw(rng, lo, hi, kind):
    value = rng.uniform(lo, hi)
    return int(round(value)) if kind == "i" else round(value, 3)


def to_preset(knobs):
    """BASE plus knobs: the settings a preset (or settings.json) would hold."""
    ov = copy.deepcopy(BASE)
    for key, value in knobs.items():
        section, name = key.split(":", 1)
        ov.setdefault(section, {})[name] = value
    for sp in SPECIES:
        ov.setdefault(sp, {})["reintroduce_after"] = 0
    return ov


def to_overrides(knobs, map_seed, layers=SPECIES):
    """The preset plus evaluation-only changes: caps as a far-off safety net, the map
    seed, and species outside `layers` left out."""
    ov = to_preset(knobs)
    ov.setdefault("map", {})["seed"] = map_seed
    for sp in SPECIES:
        ov[sp]["max_population"] = EVAL_CAP
        if sp not in layers:
            ov[sp]["initial_count"] = 0
    return ov


# ------------------------------------------------------------------- running

def run_world(job):
    """One headless world. Returns metrics, stopping at the first failure."""
    knobs, seed, minutes = job["knobs"], job["seed"], job["minutes"]
    layers = tuple(job.get("layers", SPECIES))
    import _headless  # noqa: F401
    import numpy as np
    import settings
    map_seed = job.get("map_seed", seed * 7919 % 1000003)
    settings.apply(to_overrides(knobs, map_seed=map_seed, layers=layers))
    random.seed(seed)
    np.random.seed(seed)
    from sprite_manager import sprite_manager
    sprite_manager.load_all_sprite_sheets()
    from entities.entity_manager import EntityManager
    em = EntityManager()
    em.spawn_initial_population()
    st = em.creatures.store
    steps = int(SAMPLE_S / DT)
    series = {s: [] for s in SPECIES}
    crowding, fail, t0 = [], None, time.time()
    for k in range(int(minutes * 60 / SAMPLE_S)):
        for _ in range(steps):
            em.update(DT)
        pops = {s: em.population(s) for s in SPECIES}
        for s in SPECIES:
            series[s].append(pops[s])
        rows = st.living_rows()
        if len(rows):
            crowding.append(_crowded_share(em, rows))
        sim_min = (k + 1) * SAMPLE_S / 60
        dead = [s for s in layers if pops[s] == 0]
        if dead:
            fail = f"extinct: {dead[0]}"
        elif sim_min > WARMUP_MIN and any(pops[s] < FLOOR for s in layers):
            fail = "near-extinct: " + min(layers, key=lambda s: pops[s])
        elif sum(pops.values()) > MAX_TOTAL:
            fail = "explosion"
        if fail:
            break
    return {"knobs": knobs, "seed": seed, "map_seed": map_seed, "minutes": minutes, "layers": list(layers),
            "series": series,
            "crowding": float(np.mean(crowding)) if crowding else 0.0, "fail": fail,
            "survived_min": len(series["herbivores"]) * SAMPLE_S / 60,
            "year_min": settings.SECTIONS["world"]["year_length"] / 60,
            "stats": dict(em.stats), "wall_s": round(time.time() - t0, 1)}


def _crowded_share(em, rows):
    """Share of creatures packed in with their own kind: CROWD_PEERS or more of the same
    species within CROWD_RADIUS px (what looks like a crowd on screen)."""
    import numpy as np
    st = em.creatures.store
    i, j, _ = em.creatures.physics.pairs_within(rows, CROWD_RADIUS)
    same = st.species[rows[i]] == st.species[rows[j]]
    counts = np.bincount(np.concatenate([i[same], j[same]]), minlength=len(rows))
    return float((counts >= CROWD_PEERS).mean())


# ------------------------------------------------------------------- scoring

def count_waves(values, ratio=WAVE_RATIO):
    """Zig-zag count: a peak is confirmed once the series falls to peak / ratio after
    having risen from a trough by `ratio`."""
    if len(values) < 3:
        return 0
    waves, trough, peak, rising = 0, values[0], values[0], None
    for v in values[1:]:
        v = max(v, 0.5)
        if rising in (None, True):
            peak = max(peak, v)
            if v <= peak / ratio and peak >= max(trough, 0.5) * ratio:
                waves += 1
                rising, trough = False, v
            elif rising is None and v >= trough * ratio:
                rising = True
        if rising is False:
            trough = min(trough, v)
            if v >= trough * ratio:
                rising, peak = True, v
    return waves


def summarize(result):
    import numpy as np
    warm = int(WARMUP_MIN * 60 / SAMPLE_S)
    out = {}
    for s in result.get("layers", SPECIES):
        series = np.array(result["series"][s], dtype=float)
        after = series[warm:] if len(series) > warm else series
        mean = after.mean() if len(after) else 0.0
        out[s] = {
            "waves": count_waves(list(after)),
            "low_ratio": float(after.min() / mean) if len(after) and mean > 0 else 0.0,
            "mean": float(mean), "low": float(after.min()) if len(after) else 0.0,
            "high": float(after.max()) if len(after) else 0.0,
            "at_cap": float((series >= 0.9 * EVAL_CAP).mean()) if len(series) else 0.0,
        }
    return out


def wanted_waves(result):
    """At least one wave per full sim-year after warm-up (seasons alone make one)."""
    return max(1, int((result["minutes"] - WARMUP_MIN) // result.get("year_min", 24)))


def score(result):
    """Higher is better. Survival time dominates, then how safely the low points stay
    above zero, then waves, minus crowding and cap time."""
    s = summarize(result)
    survived = result["survived_min"] / result["minutes"]
    want = wanted_waves(result)
    waves = sum(min(x["waves"], want) / want for x in s.values()) / len(s)
    low = min(min(x["low_ratio"] for x in s.values()), 0.5)
    cap = max(x["at_cap"] for x in s.values())
    peak = max(sum(v) for v in zip(*result["series"].values())) if result["series"]["herbivores"] else 0
    return round(10 * survived + 2 * waves + 8 * low - 60 * max(result["crowding"] - MAX_CROWDING, 0)
                 - 10 * cap - 4 * max(peak - PEAK_TOTAL, 0) / PEAK_TOTAL, 3)


def passes(results):
    for r in results:
        if r["fail"]:
            return False
        want = wanted_waves(r)
        for x in summarize(r).values():
            if x["waves"] < want or x["low_ratio"] < MIN_LOW_RATIO or x["at_cap"] > 0:
                return False
        if r["crowding"] > MAX_CROWDING:
            return False
    return True


# -------------------------------------------------------------------- stages

def _background():
    """Search workers run at low priority so the live simulation stays smooth."""
    try:
        os.nice(15)
    except OSError:  # already as low as it goes
        pass


def _pool_run(jobs, workers, log_path):
    results = []
    with mp.get_context("spawn").Pool(workers, initializer=_background) as pool, open(log_path, "a") as log:
        for r in pool.imap_unordered(run_world, jobs):
            r["score"] = score(r)
            results.append(r)
            log.write(json.dumps({k: r[k] for k in ("seed", "minutes", "survived_min", "fail", "score",
                                                     "crowding", "wall_s")}) + "\n")
            log.flush()
    return results


def _group(results):
    """Results of the same knobs (different seeds) together, best worst-seed score first."""
    groups = {}
    for r in results:
        groups.setdefault(json.dumps(r["knobs"], sort_keys=True), []).append(r)
    return sorted(groups.values(), key=lambda g: -min(x["score"] for x in g))


def _load(out, stage):
    with open(os.path.join(out, f"{stage}.json")) as f:
        results = json.load(f)
    for r in results:
        r["score"] = score(r)  # the scoring may have changed since the run
    return results


def _save(out, stage, results):
    with open(os.path.join(out, f"{stage}.json"), "w") as f:
        json.dump(results, f)


def _report(groups, n=10):
    for g in groups[:n]:
        s = [summarize(r) for r in g]
        fails = [r["fail"] for r in g if r["fail"]]
        lows = {sp: min(x[sp]["low"] for x in s) for sp in s[0]}
        highs = {sp: max(x[sp]["high"] for x in s) for sp in s[0]}
        waves = {sp: min(x[sp]["waves"] for x in s) for sp in s[0]}
        print(f"score {min(r['score'] for r in g):6.2f} | seeds {len(g)} | "
              f"survived {min(r['survived_min'] for r in g):5.1f}/{g[0]['minutes']} min | "
              + " ".join(f"{sp[:4]} {lows[sp]:.0f}-{highs[sp]:.0f} w{waves[sp]}" for sp in lows)
              + f" | crowd {max(r['crowding'] for r in g):.3f} | fails {fails[:2]} | pass {passes(g)}",
              flush=True)


def save_presets(groups, prefix="Balanced"):
    """Write the passing settings as presets (differences from the code defaults)."""
    import _headless  # noqa: F401
    import settings
    names = []
    for i, g in enumerate([g for g in groups if passes(g)]):
        name = f"{prefix} {i + 1}"
        settings.save_preset(name, settings.current_values(to_preset(g[0]["knobs"])))
        names.append(name)
    return names


DEFAULT_MAP = 7  # the map seed the simulation starts with


def _evaluate(candidates, args, log):
    """Every candidate on the same maps (the default map plus fixed random ones), so
    they are compared on equal ground. Returns one result list per candidate."""
    maps = [DEFAULT_MAP] + [(9000 + j) * 7919 % 1000003 for j in range(args.seeds - 1)]
    jobs = [{"knobs": k, "seed": 9000 + j, "map_seed": m, "minutes": args.minutes, "layers": args.layers}
            for k in candidates for j, m in enumerate(maps)]
    results = _pool_run(jobs, args.workers, log)
    by_knobs = {}
    for r in results:
        by_knobs.setdefault(json.dumps(r["knobs"], sort_keys=True), []).append(r)
    return [by_knobs[json.dumps(k, sort_keys=True)] for k in candidates]


def _rank_key(group):
    """Maps survived first, then the average score over the maps."""
    survived = sum(1 for r in group if not r["fail"])
    return (survived, sum(r["score"] for r in group) / len(group))


def evolve(args, rng, log):
    """(mu + lambda) evolution: keep the best `parents` settings, each generation try
    `children` mutated copies of them, all on the same maps."""
    starts = []
    for path in (args.parent or "").split(","):
        if path:
            with open(path) as f:
                starts.append(json.load(f))
    pool = _evaluate(starts, args, log) if starts else []
    if args.source:  # carry on from earlier evolve results
        earlier = {}
        for name in args.source.split(","):
            for r in _load(args.out, name):
                earlier.setdefault(json.dumps(r["knobs"], sort_keys=True), []).append(r)
        pool += list(earlier.values())
    for gen in range(args.rounds):
        pool.sort(key=_rank_key, reverse=True)
        parents = [g[0]["knobs"] for g in pool[:args.parents]]
        children = [mutate_knobs(parents[i % len(parents)], rng, strength=0.12, share=0.3)
                    for i in range(args.children)]
        pool += _evaluate(children, args, log)
        pool.sort(key=_rank_key, reverse=True)
        _save(args.out, "evolve", [r for g in pool for r in g])
        print(f"--- generation {gen}", flush=True)
        for g in pool[:6]:
            survived, mean = _rank_key(g)
            print(f"  maps survived {survived}/{len(g)}  mean score {mean:.2f}", end="  ")
            _report([g], 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("explore", "confirm", "refine", "evolve", "validate", "report", "save"))
    ap.add_argument("--n", type=int, default=140)
    ap.add_argument("--top", type=int, default=14)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--children", type=int, default=6)
    ap.add_argument("--parents", type=int, default=4)
    ap.add_argument("--parent", default=None,
                    help="explore/refine/validate: a knobs JSON file to start from (evolve: comma-separated files)")
    ap.add_argument("--minutes", type=float, default=50)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 4))
    ap.add_argument("--from", dest="source", default=None, help="stage file to take candidates from")
    ap.add_argument("--rng", type=int, default=1)
    ap.add_argument("--out", default="balance_runs")
    ap.add_argument("--layers", default=",".join(SPECIES), help="species in the world (e.g. herbivores,carnivores)")
    ap.add_argument("--knobs", default=None, help="JSON file with the knob list to search instead of KNOBS")
    ap.add_argument("--base", default=None, help="JSON file of knob values every candidate starts from")
    args = ap.parse_args()
    args.layers = [s for s in args.layers.split(",") if s]
    global KNOBS
    if args.knobs:
        with open(args.knobs) as f:
            KNOBS = [tuple(k) for k in json.load(f)]
    base = {}
    if args.base:  # fixed knob values carried by every candidate (workers only see the knobs)
        with open(args.base) as f:
            base = json.load(f)
    os.makedirs(args.out, exist_ok=True)
    log = os.path.join(args.out, "log.jsonl")
    rng = random.Random(args.rng)

    if args.stage == "explore":
        if args.parent:  # local search around a known-good setting instead of the whole box
            with open(args.parent) as f:
                parent = json.load(f)
            draws = [mutate_knobs(parent, rng, strength=0.25, share=0.5) for _ in range(args.n)]
        else:
            draws = [sample_knobs(rng) for _ in range(args.n)]
        jobs = [{"knobs": {**base, **k}, "seed": 1000 + i, "minutes": args.minutes, "layers": args.layers}
                for i, k in enumerate(draws)]
        results = _pool_run(jobs, args.workers, log)
        _save(args.out, "explore", results)
        _report(_group(results), 15)

    elif args.stage == "confirm":
        prev = _group(_load(args.out, args.source or "explore"))[:args.top]
        jobs = [{"knobs": g[0]["knobs"], "seed": 2000 + 17 * i + j, "minutes": args.minutes}
                for i, g in enumerate(prev) for j in range(args.seeds)]
        results = _pool_run(jobs, args.workers, log)
        _save(args.out, "confirm", results)
        _report(_group(results), args.top)

    elif args.stage == "refine":
        if args.parent:  # start from one known-good setting
            with open(args.parent) as f:
                start = [json.load(f)]
            pool_results = []
        else:
            pool_results = [r for name in (args.source or "confirm").split(",") for r in _load(args.out, name)]
        for round_ in range(args.rounds):
            parents = (start if args.parent and round_ == 0
                       else [g[0]["knobs"] for g in _group(pool_results)[:args.parents]])
            jobs = []
            for p_i, parent in enumerate(parents):
                for c in range(args.children):
                    child = mutate_knobs(parent, rng)
                    for j in range(args.seeds):
                        jobs.append({"knobs": child, "seed": 3000 + 101 * round_ + 13 * p_i + 7 * c + j,
                                     "minutes": args.minutes})
            results = _pool_run(jobs, args.workers, log)
            pool_results = pool_results + results
            _save(args.out, f"refine{round_}", results)
            print(f"--- refine round {round_}")
            _report(_group(pool_results), 8)
        _save(args.out, "refine", pool_results)

    elif args.stage == "validate":
        prev = _group([r for name in (args.source or "refine").split(",") for r in _load(args.out, name)])[:args.top]
        candidates = [g[0]["knobs"] for g in prev]
        if args.parent:
            with open(args.parent) as f:
                candidates.append(json.load(f))
        # the same maps for every candidate, so they are compared on equal ground
        jobs = [{"knobs": k, "seed": 5000 + j, "minutes": args.minutes}
                for k in candidates for j in range(args.seeds)]
        results = _pool_run(jobs, args.workers, log)
        _save(args.out, "validate", results)
        _report(_group(results), args.top)

    elif args.stage == "evolve":
        evolve(args, rng, log)

    elif args.stage == "report":
        _report(_group(_load(args.out, args.source or "explore")), args.top)

    elif args.stage == "save":
        print(save_presets(_group(_load(args.out, args.source or "validate"))))


if __name__ == "__main__":
    main()
