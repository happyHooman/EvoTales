"""
All creatures, as numpy arrays (one row per creature).

Every per-frame step is a whole-array operation: energy, timers, steering,
movement, wall sliding and body separation. Decisions run for the creatures
whose think timer expired this frame (about 1/12 of them per frame), also as
array operations against every creature and plant.

Instinct (shared by every species, rule-based; its only dice roll is how much
hunger overrides fear):
1. Predators in sight: run from any that is running or chasing me, otherwise
   walk away; this holds while relaxing too. A bold forager (more likely the
   hungrier it is) ignores predators that aren't chasing it and goes for food.
2. Reproduce when the interval and energy allow it.
3. Foraging (hungry until full): keep the current target while it's in sight,
   else go for the closest food. Run at moving prey, walk to plants, corpses
   and still prey. No food in sight: roam.
4. Well fed: relax (drift slowly, pay only the cost of being alive).
5. Otherwise roam.
Dead creatures stay as edible corpses for corpse_duration seconds.

Only smarties may get another Brain (brain.py); for them the swarm builds an
Observation, asks the brain, and applies its Intent.
"""
import math

import numpy as np

from .brain import Intent, Observation, Percept

TWO_PI = 2 * math.pi
HALF_PI = math.pi / 2

# Action codes
WANDER, RELAX, EAT, FLEE = 0, 1, 2, 3
ACTION_NAMES = {WANDER: "wander", RELAX: "relax", EAT: "eat", FLEE: "flee"}

# Escape directions tried when fleeing: offsets from straight-away, never past 90 degrees
FLEE_OFFSETS = np.array([0.0] + [s * k * math.pi / 12 for k in range(1, 7) for s in (1, -1)])
DETOUR_OFFSETS = np.array([0.8, -0.8, 1.6, -1.6, 2.4, -2.4, math.pi])
DETOUR_TIME = 0.8
# Thinkers are batched by map region of this size (at least their vision range)
REGION_SIZE = 800.0

# Per-species parameters copied from the config dicts every frame (so live settings apply)
PARAM_KEYS = [
    "walk_speed", "run_speed_multiplier", "run_energy_multiplier", "relax_speed_ratio",
    "turn_rate", "wander_turn_interval", "wall_probe_distance",
    "avoid_horizon", "avoid_margin", "avoid_turn",
    "vision_range", "think_interval",
    "max_energy", "birth_energy", "alive_energy_cost", "walk_energy_cost",
    "hungry_ratio", "full_ratio", "relaxed_ratio", "eat_range",
    "hunger_boldness", "boldness_interval",
    "reproduction_interval", "reproduction_energy_threshold", "reproduction_energy_cost",
    "nutrition", "corpse_duration", "max_population",
]

INT_FIELDS = ("species", "action", "target_creature", "target_plant")
BOOL_FIELDS = ("used", "alive", "foraging", "bold", "running", "relaxing", "replan_flee")
FLOAT_FIELDS = ("x", "y", "heading", "desired", "speed", "vx", "vy", "energy", "radius",
                "half_w", "half_h", "avoid_offset", "flee_away",
                "think_timer", "wander_timer", "detour_timer", "boldness_timer",
                "reproduction_timer", "corpse_timer")


def _wrap(a):
    """Angle difference into (-pi, pi]."""
    return (a + math.pi) % TWO_PI - math.pi


class Swarm:
    def __init__(self, world, species_types, sprite_sizes):
        self.world = world
        self._species_types = list(species_types)
        self.layer_index = {s.layer_name: i for i, s in enumerate(self._species_types)}
        self.sprite_sizes = sprite_sizes  # species index -> (width, height) in world px
        self.capacity = 0
        self.count = 0  # rows in use (high-water mark); free rows below it are reused
        self._free = []
        self.brains = {}  # row -> Brain, smarties only
        self._grow(512)
        self.refresh_params()

    # ------------------------------------------------------------- storage

    def _grow(self, new_capacity):
        def grow(name, dtype, fill):
            old = getattr(self, name, None)
            arr = np.full(new_capacity, fill, dtype=dtype)
            if old is not None:
                arr[:len(old)] = old
            setattr(self, name, arr)
        for f in INT_FIELDS:
            grow(f, np.int32, -1)
        for f in BOOL_FIELDS:
            grow(f, bool, False)
        for f in FLOAT_FIELDS:
            grow(f, np.float64, 0.0)
        self.capacity = new_capacity

    def refresh_params(self):
        """Per-species parameter vectors and the food chain, from the live config dicts."""
        cfgs = [s.config for s in self._species_types]
        self.params = {k: np.array([float(c[k]) for c in cfgs]) for k in PARAM_KEYS}
        n = len(self._species_types)
        self.eats = np.zeros((n, n), dtype=bool)          # eats[a, b]: species a eats species b
        self.eats_plants = np.zeros(n, dtype=bool)
        for a, c in enumerate(cfgs):
            for food in c["diet"]:
                if food == "plants":
                    self.eats_plants[a] = True
                elif food in self.layer_index:
                    self.eats[a, self.layer_index[food]] = True

    def spawn(self, layer_name, x, y, energy=None):
        if self._free:
            i = self._free.pop()
        else:
            if self.count >= self.capacity:
                self._grow(self.capacity * 2)
            i = self.count
            self.count += 1
        s = self.layer_index[layer_name]
        cfg = self._species_types[s].config
        w, h = self.sprite_sizes[s]
        rng = np.random
        self.species[i] = s
        self.used[i] = True
        self.alive[i] = True
        self.x[i], self.y[i] = x, y
        self.heading[i] = self.desired[i] = rng.uniform(0, TWO_PI)
        self.speed[i] = self.vx[i] = self.vy[i] = 0.0
        self.energy[i] = cfg["birth_energy"] if energy is None else energy
        self.radius[i] = max(w, h) / 2
        self.half_w[i], self.half_h[i] = w / 2, h / 2
        self.foraging[i] = True
        self.bold[i] = self.running[i] = self.relaxing[i] = False
        self.replan_flee[i] = False
        self.action[i] = WANDER
        self.target_creature[i] = self.target_plant[i] = -1
        self.avoid_offset[i] = self.flee_away[i] = 0.0
        self.think_timer[i] = rng.uniform(0, cfg["think_interval"])
        self.wander_timer[i] = rng.uniform(0, cfg["wander_turn_interval"])
        self.detour_timer[i] = self.boldness_timer[i] = self.corpse_timer[i] = 0.0
        self.reproduction_timer[i] = cfg["reproduction_interval"]
        self.brains.pop(i, None)
        return i

    def set_brain(self, row, brain):
        if not self.species_type(row).can_have_brain:
            raise ValueError(f"{self.species_type(row).__name__} runs on instinct only")
        self.brains[row] = brain

    def species_type(self, row):
        return self._species_types[self.species[row]]

    def _free_rows(self, rows):
        for i in rows:
            self.used[i] = False
            self.alive[i] = False
            self.brains.pop(int(i), None)
            self._free.append(int(i))
        # Nobody keeps chasing or eating a creature that is gone
        gone = np.zeros(self.capacity, dtype=bool)
        gone[rows] = True
        n = self.count
        tc = self.target_creature[:n]
        stale = (tc >= 0) & gone[np.maximum(tc, 0)]
        tc[stale] = -1

    def populations(self):
        n = self.count
        live = self.alive[:n]
        return np.bincount(self.species[:n][live], minlength=len(self._species_types))

    def population(self, layer_name):
        return int(self.populations()[self.layer_index[layer_name]])

    # ------------------------------------------------------------- per frame

    def update(self, dt):
        n = self.count
        if n == 0:
            return
        rng = np.random
        alive = self.alive[:n].copy()
        used = self.used[:n]

        # Corpses fade away
        corpse = used & ~alive
        if corpse.any():
            self.corpse_timer[:n][corpse] -= dt
            vanish = np.nonzero(corpse & (self.corpse_timer[:n] <= 0))[0]
            if len(vanish):
                self._free_rows(vanish)

        if not alive.any():
            return
        idx = np.nonzero(alive)[0]
        sp = self.species[idx]
        P = self.params

        # Energy: being alive, plus moving (relaxing moves for free).
        # cost = walk_cost * (speed / walk_speed) ^ k, with k such that running at
        # run_speed_multiplier x walk speed costs run_energy_multiplier x walk energy.
        k = np.log(P["run_energy_multiplier"][sp]) / np.log(P["run_speed_multiplier"][sp])
        moving = (self.speed[idx] > 0) & ~self.relaxing[idx]
        move_cost = np.where(moving, P["walk_energy_cost"][sp]
                             * (self.speed[idx] / P["walk_speed"][sp]) ** k, 0.0)
        self.energy[idx] -= (P["alive_energy_cost"][sp] + move_cost) * dt
        self.reproduction_timer[idx] -= dt

        starved = idx[self.energy[idx] <= 0]
        if len(starved):
            self._die(starved, "starved", leave_corpse=True)
            keep = self.alive[idx]
            idx, sp = idx[keep], sp[keep]
            if len(idx) == 0:
                return

        # Hunger hysteresis: forage below hungry_ratio until full_ratio
        ratio = self.energy[idx] / P["max_energy"][sp]
        self.foraging[idx[ratio < P["hungry_ratio"][sp]]] = True
        self.foraging[idx[ratio >= P["full_ratio"][sp]]] = False

        # Hunger beats fear: re-roll every boldness_interval seconds
        self.boldness_timer[idx] -= dt
        roll = idx[self.boldness_timer[idx] <= 0]
        if len(roll):
            rs = self.species[roll]
            self.boldness_timer[roll] = P["boldness_interval"][rs]
            hunger = np.clip(1 - self.energy[roll] / (P["max_energy"][rs] * P["hungry_ratio"][rs]), 0, 1)
            self.bold[roll] = self.foraging[roll] & (rng.random(len(roll)) < P["hunger_boldness"][rs] * hunger)

        # Decisions for creatures whose think timer ran out
        self.think_timer[idx] -= dt
        due = idx[self.think_timer[idx] <= 0]
        if len(due):
            self.think_timer[due] += P["think_interval"][self.species[due]]
            self._think(due)
            keep = self.alive[idx]
            idx, sp = idx[keep], sp[keep]

        self._act(idx, dt)
        self._steer(idx, dt)
        self._move(idx, dt)
        self._separate(idx)

    # ------------------------------------------------------------ perception

    def _think(self, rows):
        """
        Perceive and decide for `rows`. Rows are grouped by map region, and each group
        is compared only with the creatures and plants near that region, so the cost
        grows with local density rather than with (thinkers x everyone).
        """
        P = self.params
        n = self.count
        margin = float(max(P["vision_range"].max(),
                           (P["avoid_horizon"] * (P["walk_speed"] * P["run_speed_multiplier"] + 70)).max() + 40))
        region = max(REGION_SIZE, margin)
        rx = np.floor(self.x[rows] / region).astype(np.int64)
        ry = np.floor(self.y[rows] / region).astype(np.int64)
        keys = rx * 100003 + ry
        order = np.argsort(keys, kind="stable")
        keys_sorted = keys[order]
        splits = np.nonzero(np.diff(keys_sorted))[0] + 1
        cx, cy = self.x[:n], self.y[:n]
        used = np.nonzero(self.used[:n])[0]
        ux, uy = cx[used], cy[used]
        px, py, _, _ = self.world.plant_arrays()
        for group in np.split(order, splits):
            g = rows[group]
            x0, y0 = rx[group[0]] * region - margin, ry[group[0]] * region - margin
            x1, y1 = x0 + region + 2 * margin, y0 + region + 2 * margin
            cols = used[(ux >= x0) & (ux < x1) & (uy >= y0) & (uy < y1)]
            pcols = np.nonzero((px >= x0) & (px < x1) & (py >= y0) & (py < y1))[0] if len(px) else np.zeros(0, int)
            self._think_region(g, cols, pcols)

    def _think_region(self, rows, cols, pcols):
        """Perceive and decide for `rows`, against creature rows `cols` and plants `pcols`."""
        P = self.params
        rs = self.species[rows]
        vision = P["vision_range"][rs]
        vision2 = (vision * vision)[:, None]
        x, y = self.x[rows], self.y[rows]

        # --- creatures in sight (rows x candidate columns) ---
        dx = self.x[cols][None, :] - x[:, None]
        dy = self.y[cols][None, :] - y[:, None]
        d2 = dx * dx + dy * dy
        in_sight = (d2 <= vision2) & self.used[cols][None, :] & (cols[None, :] != rows[:, None])
        others_sp = self.species[cols]
        others_alive = self.alive[cols]
        others_target = self.target_creature[cols]

        # Threats: living creatures whose species eats mine
        is_threat = in_sight & others_alive[None, :] & self.eats[others_sp[None, :], rs[:, None]]
        has_threat = is_threat.any(axis=1)
        attacking = is_threat & (others_target[None, :] == rows[:, None])
        any_attacking = attacking.any(axis=1)
        alarming = is_threat & (self.running[cols][None, :] | (others_target[None, :] == rows[:, None]))
        any_alarming = alarming.any(axis=1)

        # Creature food: species I eat, alive or corpse
        is_cfood = in_sight & self.eats[rs[:, None], others_sp[None, :]]
        cfood_d2 = np.where(is_cfood, d2, np.inf)
        bc = np.argmin(cfood_d2, axis=1) if len(cols) else np.zeros(len(rows), dtype=int)
        best_c_d2 = cfood_d2[np.arange(len(rows)), bc] if len(cols) else np.full(len(rows), np.inf)
        best_c = cols[bc] if len(cols) else np.full(len(rows), -1)

        # --- plants in sight (rows x plants) ---
        px, py, edible, claim = self.world.plant_arrays()
        best_p = np.full(len(rows), -1)
        best_p_d2 = np.full(len(rows), np.inf)
        eats_pl = self.eats_plants[rs]
        if len(pcols) and eats_pl.any():
            pr = np.nonzero(eats_pl)[0]
            pdx = px[pcols][None, :] - x[pr, None]
            pdy = py[pcols][None, :] - y[pr, None]
            pd2 = pdx * pdx + pdy * pdy
            # Plants someone else is already walking to are left to them
            pclaim = claim[pcols]
            c = np.maximum(pclaim, 0)
            claim_live = (pclaim >= 0) & self.alive[c] & (self.target_plant[c] == pcols)
            claimed_by_other = claim_live[None, :] & (pclaim[None, :] != rows[pr, None])
            ok = edible[pcols][None, :] & ~claimed_by_other & (pd2 <= vision2[pr])
            pd2 = np.where(ok, pd2, np.inf)
            bp = np.argmin(pd2, axis=1)
            best_p[pr] = pcols[bp]
            best_p_d2[pr] = pd2[np.arange(len(pr)), bp]

        # Keep the current target while it is still in sight and valid
        cur_c = self.target_creature[rows]
        cur_p = self.target_plant[rows]
        keep_c = cur_c >= 0
        if keep_c.any():
            kc = np.nonzero(keep_c)[0]
            colpos = np.full(self.count, -1)
            colpos[cols] = np.arange(len(cols))
            pos = colpos[cur_c[kc]]
            keep_c[kc] = (pos >= 0) & is_cfood[kc, np.maximum(pos, 0)]
        keep_p = (cur_p >= 0) & (cur_p < len(px))
        if keep_p.any():
            kp = np.nonzero(keep_p)[0]
            tp = cur_p[kp]
            pd = (px[tp] - x[kp]) ** 2 + (py[tp] - y[kp]) ** 2
            keep_p[kp] = edible[tp] & (pd <= vision2[kp, 0])

        has_food = np.isfinite(best_c_d2) | np.isfinite(best_p_d2) | keep_c | keep_p
        choose_c = np.where(keep_c, True, np.where(keep_p, False, best_c_d2 <= best_p_d2))
        target_c = np.where(keep_c, cur_c, np.where(choose_c & np.isfinite(best_c_d2), best_c, -1))
        target_p = np.where(keep_p, cur_p, np.where(~choose_c & np.isfinite(best_p_d2), best_p, -1))
        target_c = np.where(target_p >= 0, -1, target_c)

        # --- instinct ---
        energy = self.energy[rows]
        max_e = P["max_energy"][rs]
        foraging = self.foraging[rows]
        relaxed = ~foraging & (energy / max_e >= P["relaxed_ratio"][rs])
        can_repro = ((energy >= P["reproduction_energy_threshold"][rs])
                     & (energy > P["reproduction_energy_cost"][rs])
                     & (self.reproduction_timer[rows] <= 0))
        if can_repro.any():
            pops = self.populations()
            can_repro &= pops[rs] < P["max_population"][rs]

        hunger_wins = self.bold[rows] & foraging & has_food & ~any_attacking
        flee = has_threat & ~hunger_wins
        repro = ~flee & can_repro
        eat = ~flee & ~repro & foraging & has_food
        relax = ~flee & ~repro & ~eat & ~foraging & relaxed

        action = np.full(len(rows), WANDER)
        action[relax] = RELAX
        action[eat] = EAT
        action[flee] = FLEE

        # Brain-driven smarties override their instinct
        brain_runs = {}
        if self.brains:
            for j, r in enumerate(rows):
                brain = self.brains.get(int(r))
                if brain is not None:
                    action[j], target_c[j], target_p[j], run_override = self._ask_brain(
                        int(r), brain, cols, is_threat[j], attacking[j], is_cfood[j], d2[j],
                        target_c[j], target_p[j], has_threat[j], can_repro[j])
                    brain_runs[j] = bool(run_override)
                    repro[j] = action[j] == -1
                    if action[j] == -1:
                        action[j] = WANDER

        self.action[rows] = action
        self.target_creature[rows] = np.where(action == EAT, target_c, -1)
        self.target_plant[rows] = np.where(action == EAT, target_p, -1)
        # Claim plants being walked to
        tp_rows = rows[(action == EAT) & (target_p >= 0)]
        if len(tp_rows):
            claim[self.target_plant[tp_rows]] = tp_rows

        # Run at moving prey; walk to plants, corpses and still prey
        tc = self.target_creature[rows]
        prey_moving = np.zeros(len(rows), dtype=bool)
        has_tc = tc >= 0
        if has_tc.any():
            t = tc[has_tc]
            ts = self.species[t]
            prey_moving[has_tc] = self.alive[t] & (
                self.speed[t] > P["walk_speed"][ts] * P["relax_speed_ratio"][ts] * 1.01)
        self.running[rows] = ((action == EAT) & prey_moving) | ((action == FLEE) & any_alarming)
        for j, run in brain_runs.items():
            self.running[rows[j]] = run and action[j] in (EAT, FLEE)

        # Fleeing: away from all visible predators (closer ones weigh more), around water
        fr = np.nonzero(action == FLEE)[0]
        if len(fr):
            w = np.where(is_threat[fr], 1.0 / np.maximum(d2[fr], 1.0), 0.0)
            ax = -(dx[fr] * w).sum(axis=1)
            ay = -(dy[fr] * w).sum(axis=1)
            away = np.arctan2(ay, ax)
            self.flee_away[rows[fr]] = away
            heading = self._free_heading(rows[fr], away, FLEE_OFFSETS)
            self.desired[rows[fr]] = np.where(np.isnan(heading), away, heading)
            self.detour_timer[rows[fr]] = 0.0

        # Look ahead for water when not fleeing
        nf = rows[action != FLEE]
        if len(nf):
            self._check_walls(nf)

        # Collision avoidance (trail planning)
        self._plan_avoidance(rows, cols)

        # Reproduction (few per frame: plain loop)
        for r in rows[repro]:
            self._reproduce(int(r))

    def _ask_brain(self, r, brain, cols, threat_row, attack_row, food_row, d2_row, tc, tp, has_threat, can_repro):
        """Build an Observation for one brain-driven creature and apply its Intent."""
        P = self.params
        s = self.species[r]
        food = [Percept(("creature", int(cols[j])), self.species_type(int(cols[j])).layer_name,
                        float(np.sqrt(d2_row[j])), is_corpse=not self.alive[cols[j]])
                for j in np.nonzero(food_row)[0]]
        if tp >= 0:
            px, py, _, _ = self.world.plant_arrays()
            food.append(Percept(("plant", int(tp)), "plants",
                                float(math.hypot(px[tp] - self.x[r], py[tp] - self.y[r]))))
        threats = [Percept(("creature", int(cols[j])), self.species_type(int(cols[j])).layer_name,
                           float(np.sqrt(d2_row[j])), running=bool(self.running[cols[j]]),
                           attacking=bool(attack_row[j]))
                   for j in np.nonzero(threat_row)[0]]
        food.sort(key=lambda p: p.distance)
        threats.sort(key=lambda p: p.distance)
        ratio = self.energy[r] / P["max_energy"][s]
        current = (("creature", int(self.target_creature[r])) if self.target_creature[r] >= 0 else
                   ("plant", int(self.target_plant[r])) if self.target_plant[r] >= 0 else None)
        obs = Observation(energy=float(self.energy[r]), energy_ratio=float(ratio),
                          foraging=bool(self.foraging[r]), bold=bool(self.bold[r]),
                          relaxed=bool(not self.foraging[r] and ratio >= P["relaxed_ratio"][s]),
                          can_reproduce=bool(can_repro), current_target=current,
                          food=food[:5], threats=threats[:3])
        intent: Intent = brain.decide(obs)
        kind_idx = intent.target if isinstance(intent.target, tuple) else (None, -1)
        if intent.action == "eat":
            return EAT, (kind_idx[1] if kind_idx[0] == "creature" else -1), \
                (kind_idx[1] if kind_idx[0] == "plant" else -1), intent.run
        if intent.action == "flee":
            return FLEE, -1, -1, intent.run
        if intent.action == "reproduce":
            return -1, -1, -1, False
        return (RELAX if intent.action == "relax" else WANDER), -1, -1, False

    # --------------------------------------------------------------- actions

    def _act(self, idx, dt):
        P = self.params
        sp = self.species[idx]
        action = self.action[idx]
        walk = P["walk_speed"][sp]
        run_mult = P["run_speed_multiplier"][sp]
        relax_ratio = P["relax_speed_ratio"][sp]
        running = self.running[idx]

        # Gait
        self.relaxing[idx] = action == RELAX
        self.speed[idx] = np.where(running, walk * run_mult, np.where(action == RELAX, walk * relax_ratio, walk))
        self.running[idx] = running & ((action == EAT) | (action == FLEE))

        # Roaming: random heading changes now and then
        roam = idx[(action == WANDER) | (action == RELAX)]
        if len(roam):
            self.target_creature[roam] = -1
            self.target_plant[roam] = -1
            self.wander_timer[roam] -= dt
            turn = roam[self.wander_timer[roam] <= 0]
            if len(turn):
                ts = self.species[turn]
                self.wander_timer[turn] = P["wander_turn_interval"][ts] * np.random.uniform(0.5, 1.5, len(turn))
                self.desired[turn] = self.heading[turn] + np.random.uniform(-HALF_PI, HALF_PI, len(turn))

        # Eating: head for the target, consume on contact
        eaters = idx[action == EAT]
        if len(eaters):
            self._do_eat(eaters)

    def _do_eat(self, eaters):
        P = self.params
        px, py, edible, _ = self.world.plant_arrays()
        tc = self.target_creature[eaters]
        tp = self.target_plant[eaters]
        valid = np.zeros(len(eaters), dtype=bool)
        tx = np.zeros(len(eaters))
        ty = np.zeros(len(eaters))
        tr = np.zeros(len(eaters))
        c = tc >= 0
        if c.any():
            t = tc[c]
            valid[c] = self.used[t]
            tx[c], ty[c], tr[c] = self.x[t], self.y[t], self.radius[t]
        p = (tp >= 0) & (tp < len(px))
        if p.any():
            t = tp[p]
            valid[p] = edible[t]
            tx[p], ty[p] = px[t], py[t]
            tr[p] = self.world.plant_radius(t)
        lost = eaters[~valid]
        if len(lost):
            self.action[lost] = WANDER
            self.target_creature[lost] = -1
            self.target_plant[lost] = -1
            self.running[lost] = False
        ok = np.nonzero(valid)[0]
        if not len(ok):
            return
        e = eaters[ok]
        reach = self.radius[e] + tr[ok] + P["eat_range"][self.species[e]]
        ddx = tx[ok] - self.x[e]
        ddy = ty[ok] - self.y[e]
        touching = ddx * ddx + ddy * ddy <= reach * reach
        # Head straight for it (unless detouring around water)
        steer = ~touching & (self.detour_timer[e] <= 0)
        self.desired[e[steer]] = np.arctan2(ddy[steer], ddx[steer])
        for j in np.nonzero(touching)[0]:
            self._consume(int(e[j]))

    def _consume(self, r):
        """r eats its target (if it's still there)."""
        P = self.params
        tc, tp = int(self.target_creature[r]), int(self.target_plant[r])
        gain = 0.0
        if tc >= 0 and self.used[tc]:
            gain = P["nutrition"][self.species[tc]]
            eater = self.species_type(r).layer_name
            if self.alive[tc]:
                self._die(np.array([tc]), f"eaten by {eater}", leave_corpse=False)
            else:
                self.world.record(f"{self.species_type(tc).layer_name} corpses eaten")
                self._free_rows(np.array([tc]))
        elif tp >= 0:
            gain = self.world.eat_plant(tp)
        if gain:
            s = self.species[r]
            self.energy[r] = min(P["max_energy"][s], self.energy[r] + gain)
        self.action[r] = WANDER
        self.target_creature[r] = self.target_plant[r] = -1
        self.running[r] = False

    def _die(self, rows, cause, leave_corpse):
        for r in rows:
            self.world.record(f"{self.species_type(int(r)).layer_name} {cause}")
        self.alive[rows] = False
        self.speed[rows] = self.vx[rows] = self.vy[rows] = 0.0
        self.running[rows] = self.relaxing[rows] = False
        self.target_creature[rows] = self.target_plant[rows] = -1
        if leave_corpse:
            self.corpse_timer[rows] = self.params["corpse_duration"][self.species[rows]]
        else:
            self._free_rows(rows)

    def _reproduce(self, r):
        P = self.params
        s = self.species[r]
        if self.populations()[s] >= P["max_population"][s]:
            return
        angle = np.random.uniform(0, TWO_PI)
        dist = self.radius[r] * 3
        cx = self.x[r] + dist * math.cos(angle)
        cy = self.y[r] + dist * math.sin(angle)
        if self.world.is_blocked(cx, cy):
            return
        self.energy[r] -= P["reproduction_energy_cost"][s]
        self.reproduction_timer[r] = P["reproduction_interval"][s]
        name = self.species_type(r).layer_name
        self.world.record(f"{name} born")
        self.spawn(name, cx, cy)

    # -------------------------------------------------------------- steering

    def _free_heading(self, rows, base, offsets):
        """First free direction from base+offsets per row (NaN when every option is blocked)."""
        P = self.params
        probe = self.radius[rows] + P["wall_probe_distance"][self.species[rows]]
        angles = base[:, None] + offsets[None, :]
        ca, sa = np.cos(angles), np.sin(angles)
        x, y = self.x[rows][:, None], self.y[rows][:, None]
        pr = probe[:, None]
        blocked = (self.world.blocked_at(x + pr * ca, y + pr * sa)
                   | self.world.blocked_at(x + 2 * pr * ca, y + 2 * pr * sa))
        free = ~blocked
        first = np.argmax(free, axis=1)
        result = angles[np.arange(len(rows)), first]
        return np.where(free.any(axis=1), result, np.nan)

    def _check_walls(self, rows):
        """Look ahead along the current heading; pick a free direction if water is in the way."""
        heading = self.heading[rows]
        ahead_free = ~np.isnan(self._free_heading(rows, heading, np.array([0.0])))
        stuck = rows[~ahead_free]
        if len(stuck):
            h = self._free_heading(stuck, self.heading[stuck], DETOUR_OFFSETS)
            self.desired[stuck] = np.where(np.isnan(h), self.heading[stuck] + math.pi, h)
            self.detour_timer[stuck] = DETOUR_TIME

    def _plan_avoidance(self, rows, cols):
        """
        Trail planning: predict nearby creatures' paths over avoid_horizon seconds
        (constant velocity) and, if we'd touch one, veer to the side it isn't on.
        Hunters don't dodge their prey and vice versa.
        """
        P = self.params
        rs = self.species[rows]
        horizon = P["avoid_horizon"][rs]
        self.avoid_offset[rows] = 0.0
        active = (horizon > 0) & (self.speed[rows] > 0)
        if not active.any():
            return
        rows, rs, horizon = rows[active], rs[active], horizon[active]
        ox = self.x[cols][None, :] - self.x[rows][:, None]
        oy = self.y[cols][None, :] - self.y[rows][:, None]
        rvx = self.vx[cols][None, :] - self.vx[rows][:, None]
        rvy = self.vy[cols][None, :] - self.vy[rows][:, None]
        closing = rvx * rvx + rvy * rvy
        with np.errstate(divide="ignore", invalid="ignore"):
            t = -(ox * rvx + oy * rvy) / closing
        cx = ox + rvx * t
        cy = oy + rvy * t
        clearance = self.radius[cols][None, :] + self.radius[rows][:, None] + P["avoid_margin"][rs][:, None]
        hit = (self.alive[cols][None, :] & (closing > 1e-6) & (t > 0) & (t < horizon[:, None])
               & (cx * cx + cy * cy < clearance * clearance))
        hit &= cols[None, :] != rows[:, None]
        hit &= self.target_creature[cols][None, :] != rows[:, None]          # it isn't hunting me
        hit &= cols[None, :] != self.target_creature[rows][:, None]          # I'm not hunting it
        any_hit = hit.any(axis=1)
        if not any_hit.any():
            return
        t = np.where(hit, t, np.inf)
        j = np.argmin(t, axis=1)
        ar = np.arange(len(rows))
        soonest = t[ar, j]
        hx, hy = cx[ar, j], cy[ar, j]
        h = self.heading[rows]
        side = np.cos(h) * hy - np.sin(h) * hx
        side = np.where(side == 0, 1.0, side)
        urgency = 1 - soonest / horizon
        offset = -np.sign(side) * P["avoid_turn"][rs] * (0.4 + 0.6 * urgency)
        self.avoid_offset[rows[any_hit]] = offset[any_hit]

    def _steer(self, idx, dt):
        P = self.params
        sp = self.species[idx]
        self.detour_timer[idx] = np.maximum(self.detour_timer[idx] - dt, 0)
        goal = self.desired[idx] + self.avoid_offset[idx]
        fleeing = self.action[idx] == FLEE
        if fleeing.any():
            away = self.flee_away[idx]
            # A dodge while fleeing never points back toward the predators
            clamped = away + np.clip(_wrap(goal - away), -HALF_PI, HALF_PI)
            goal = np.where(fleeing, clamped, goal)
        diff = _wrap(goal - self.heading[idx])
        max_step = P["turn_rate"][sp] * dt
        heading = (self.heading[idx] + np.clip(diff, -max_step, max_step)) % TWO_PI
        self.heading[idx] = heading
        self.desired[idx] %= TWO_PI
        self.vx[idx] = self.speed[idx] * np.cos(heading)
        self.vy[idx] = self.speed[idx] * np.sin(heading)

    def _move(self, idx, dt):
        """Integrate positions; slide along walls/water instead of entering them."""
        x, y = self.x[idx], self.y[idx]
        nx = x + self.vx[idx] * dt
        ny = y + self.vy[idx] * dt
        blocked = self.world.blocked_at(nx, ny)
        if blocked.any():
            bx = self.world.blocked_at(nx, y)   # try moving along x only
            by = self.world.blocked_at(x, ny)   # or along y only
            nx = np.where(blocked & bx, x, nx)
            ny = np.where(blocked & by, y, ny)
            still = self.world.blocked_at(nx, ny)
            nx = np.where(still, x, nx)
            ny = np.where(still, y, ny)
        self.x[idx] = nx
        self.y[idx] = ny

    def _separate(self, idx):
        """Push apart living creatures whose bodies overlap (bodies are solid)."""
        if len(idx) < 2:
            return
        x, y, r = self.x[idx], self.y[idx], self.radius[idx]
        cell = float(2 * r.max())
        cx = np.floor(x / cell).astype(np.int64)
        cy = np.floor(y / cell).astype(np.int64)
        key = cx * 100003 + cy
        order = np.argsort(key, kind="stable")
        skey = key[order]
        pi_list, pj_list = [], []
        for ox, oy in ((0, 0), (1, -1), (1, 0), (1, 1), (0, 1)):
            nkey = (cx + ox) * 100003 + (cy + oy)
            lo = np.searchsorted(skey, nkey, side="left")
            hi = np.searchsorted(skey, nkey, side="right")
            counts = hi - lo
            total = counts.sum()
            if total == 0:
                continue
            i = np.repeat(np.arange(len(idx)), counts)
            starts = np.repeat(lo - np.cumsum(counts) + counts, counts)
            j = order[np.arange(total) + starts]
            if ox == 0 and oy == 0:
                keep = j > i  # each same-cell pair once
                i, j = i[keep], j[keep]
            pi_list.append(i)
            pj_list.append(j)
        if not pi_list:
            return
        i = np.concatenate(pi_list)
        j = np.concatenate(pj_list)
        dx = x[j] - x[i]
        dy = y[j] - y[i]
        d = np.sqrt(dx * dx + dy * dy)
        overlap = r[i] + r[j] - d
        m = overlap > 0
        if not m.any():
            return
        i, j, dx, dy, d, overlap = i[m], j[m], dx[m], dy[m], d[m], overlap[m]
        d = np.where(d < 1e-6, 1e-6, d)
        push = 0.5 * overlap / d
        px = np.zeros(len(idx))
        py = np.zeros(len(idx))
        np.add.at(px, i, -dx * push)
        np.add.at(py, i, -dy * push)
        np.add.at(px, j, dx * push)
        np.add.at(py, j, dy * push)
        nx, ny = x + px, y + py
        ok = ~self.world.blocked_at(nx, ny)
        self.x[idx] = np.where(ok, nx, x)
        self.y[idx] = np.where(ok, ny, y)
