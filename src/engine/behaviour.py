"""
BehaviourSystem: the only writer of store.mind (what each creature is doing)
and store.command (the heading and speed it asks physics for). It never moves
a creature itself.

Per step:
1. decide: creatures whose think timer ran out perceive (batched by map region)
   and pick an action with their instinct, or with their Brain (smarties only)
2. act: every creature carries out its action: gait, roaming, heading for food,
   eating on contact, giving birth
3. steer: turn the action's goal heading into the command for physics, adding
   the trail-planning dodge (never back toward predators while fleeing)

Instinct (shared by every species; its only dice roll is how much hunger
overrides fear):
1. Predators in sight: run from any that is running, otherwise walk away;
   this holds while relaxing too. Hunters stalk at a walk and sprint once
   within sprint_range. A bold forager ignores predators
   that aren't chasing it and goes for food.
2. Reproduce when the interval, food and health allow it.
3. Foraging (hungry until full): meat before plants, and corpses (easy food)
   before live prey; within a kind, the closest. Below desperate_ratio of its
   stomach (it hasn't eaten for a long time) it takes whatever food is closest. It keeps its current target while it's in sight
   unless a better kind of food shows up, and never lets go of prey it has
   already bitten (until the prey is dead). Run at moving prey, walk to plants,
   corpses and still prey. No food in sight: roam.
4. Tired (until rested), well fed or hurt: relax (drift slowly; heals like sleep).
Every creature has an attack value (attack, weakened by low health and stamina).
Hunters bite living prey (one bite every attack_cooldown s) rather than
swallowing it, staying on it (facing it, matching its pace) between bites; prey bites back, harder with its herd around it (when caught
exhausted or with its herd near, it stops and turns to fight), and hunters
prefer prey that isn't in a crowd. Roaming creatures drift toward their herd.
Prey running from a predator give alarm calls; peers that hear one flee the
same way for a while, even if they can't see the danger.
Personal space is a resource: too many of its own kind within personal_space
and a creature is crammed (slowly loses health) and may bite the closest one,
which backs off.
Creatures reaching the same food item squabble: the strongest (dominance x
health) keeps it; the rest take a bite and stay away from it for yield_time.
5. Otherwise roam.

New activities plug in here: a new action code, a branch in _decide_region,
and a handler in act() that sets mind.goal and the gait.
"""
import math

import numpy as np

from entities.brain import Intent, Observation, Percept
from .physics import wrap_angle
from .store import EAT, FLEE, RELAX, WANDER

TWO_PI = 2 * math.pi
HALF_PI = math.pi / 2
# Escape directions tried when fleeing: offsets from straight-away, never past 90 degrees
FLEE_OFFSETS = np.array([0.0] + [s * k * math.pi / 12 for k in range(1, 7) for s in (1, -1)])
DETOUR_OFFSETS = np.array([0.8, -0.8, 1.6, -1.6, 2.4, -2.4, math.pi])
DETOUR_TIME = 0.8
CALL_COOLDOWN = 2.0  # seconds between one creature's alarm calls
CALL_FLASH = 0.6     # seconds the call ripple is shown
STAND_TIME = 1.2     # seconds caught prey stands and fights before trying to run again
# Thinkers are batched by map region: at least this big (and at least their vision
# range), and bigger when the map is sparse, so each batch holds about
# REGION_CREATURES creatures (numpy pays per call, so fewer, fuller batches are faster)
REGION_SIZE = 800.0
REGION_CREATURES = 200
CORPSE_FIRST = 1e12  # added to live prey's distance so any corpse in sight ranks first


class BehaviourSystem:
    def __init__(self, store, world, physics, metabolism):
        self.store = store
        self.world = world
        self.physics = physics
        self.metabolism = metabolism
        self.brains = {}  # row -> Brain (smarties only)
        store.on_free(self._forget)

    def set_brain(self, row, brain):
        if not self.store.species_type(row).can_have_brain:
            raise ValueError(f"{self.store.species_type(row).__name__} runs on instinct only")
        self.brains[row] = brain

    def _forget(self, rows):
        """Freed rows: drop their brains, and nobody keeps chasing them."""
        for r in rows:
            self.brains.pop(int(r), None)
        n = self.store.count
        tc = self.store.mind.target_creature[:n]
        tc[np.isin(tc, rows)] = -1
        st_ = self.store.mind.stand_target[:n]
        st_[np.isin(st_, rows)] = -1

    def step(self, dt):
        s, m = self.store, self.store.mind
        rows = s.living_rows()
        if not len(rows):
            return
        m.attack_timer[rows] -= dt
        m.yield_timer[rows] -= dt
        self._measure_crowding(rows)
        m.alarm_timer[rows] -= dt
        m.call_timer[rows] -= dt
        m.call_flash[rows] -= dt
        m.stand_timer[rows] -= dt
        self._build_herd_map(rows)
        m.think_timer[rows] -= dt
        due = rows[m.think_timer[rows] <= 0]
        if len(due):
            m.think_timer[due] += s.p("think_interval", due)
            self._decide(due)
            rows = s.living_rows()
        self._act(rows, dt)
        self._steer(rows, dt)

    # ---------------------------------------------------------------- decide

    def _decide(self, rows):
        """Group thinkers by map region; compare each group only with nearby creatures/plants."""
        s = self.store
        P = s.params
        n = s.count
        margin = float(max(P["vision_range"].max() * s.gene_max("vision_range"),
                           (P["avoid_horizon"] * (P["walk_speed"] * P["run_speed_multiplier"]
                                                  * s.gene_max("walk_speed") + 70)).max() + 40))
        used = np.nonzero(s.used[:n])[0]
        map_w, map_h = self.world.map_size
        region = max(REGION_SIZE, margin, math.sqrt(map_w * map_h * REGION_CREATURES / max(len(used), 1)))
        bx, by = s.body.x, s.body.y
        rx = np.floor(bx[rows] / region).astype(np.int64)
        ry = np.floor(by[rows] / region).astype(np.int64)
        keys = rx * 100003 + ry
        order = np.argsort(keys, kind="stable")
        splits = np.nonzero(np.diff(keys[order]))[0] + 1
        ux, uy = bx[used], by[used]
        px, py, _, _ = self.world.plant_arrays()
        for group in np.split(order, splits):
            x0, y0 = rx[group[0]] * region - margin, ry[group[0]] * region - margin
            x1, y1 = x0 + region + 2 * margin, y0 + region + 2 * margin
            cols = used[(ux >= x0) & (ux < x1) & (uy >= y0) & (uy < y1)]
            pcols = np.nonzero((px >= x0) & (px < x1) & (py >= y0) & (py < y1))[0] if len(px) else np.zeros(0, int)
            self._decide_region(rows[group], cols, pcols)

    def _decide_region(self, rows, cols, pcols):
        """Perceive and decide for `rows`, against creature rows `cols` and plants `pcols`."""
        s, m, v = self.store, self.store.mind, self.store.vitals
        P = s.params
        rs = s.species[rows]
        vision = s.p("vision_range", rows)
        vision2 = (vision * vision)[:, None]
        x, y = s.body.x[rows], s.body.y[rows]
        ar = np.arange(len(rows))

        # --- creatures in sight (rows x candidate columns) ---
        dx = s.body.x[cols][None, :] - x[:, None]
        dy = s.body.y[cols][None, :] - y[:, None]
        d2 = dx * dx + dy * dy
        # Others are spotted at my vision x their visibility (forest cover hides them)
        seen_at = vision[:, None] * s.p("visibility", cols)[None, :]
        in_sight = (d2 <= seen_at * seen_at) & s.used[cols][None, :] & (cols[None, :] != rows[:, None])
        others_sp = s.species[cols]
        others_target = m.target_creature[cols]

        # Threats: living creatures whose species eats mine
        is_threat = in_sight & s.alive[cols][None, :] & s.eats[others_sp[None, :], rs[:, None]]
        has_threat = is_threat.any(axis=1)
        # A hunter that has picked me and is running at me is attacking; one that is
        # stalking me at a walk only looks like a predator walking by
        attacking = is_threat & (others_target[None, :] == rows[:, None]) & m.running[cols][None, :]
        any_attacking = attacking.any(axis=1)
        any_alarming = (is_threat & m.running[cols][None, :]).any(axis=1)

        # Creature food: species I eat, alive or corpse
        is_cfood = in_sight & s.eats[rs[:, None], others_sp[None, :]]
        best_c_d2, best_c = np.full(len(rows), np.inf), np.full(len(rows), -1)
        hr = np.nonzero(s.eats[rs].any(axis=1))[0]  # only rows that eat creatures need this
        if len(cols) and len(hr):
            # Herds confuse hunters: prey in a crowd looks further away than it is
            crowd = 1.0 + P["crowd_penalty"][rs[hr]][:, None] * (s.alive[cols] * self.herd_peers(cols))[None, :]
            banned = cols[None, :] == np.where(m.yield_timer[rows[hr]] > 0, m.banned_creature[rows[hr]], -1)[:, None]
            cfood_d2 = np.where(is_cfood[hr] & ~banned, d2[hr] * crowd, np.inf)
            # Corpses are easy food: any corpse in sight comes before any live prey
            live = s.alive[cols][None, :] & np.isfinite(cfood_d2)
            rank = np.where(live, cfood_d2 + CORPSE_FIRST, cfood_d2)
            bc = np.argmin(rank, axis=1)
            best_c_d2[hr], best_c[hr] = cfood_d2[np.arange(len(hr)), bc], cols[bc]

        # --- plants in sight ---
        px, py, edible, claim = self.world.plant_arrays()
        best_p = np.full(len(rows), -1)
        best_p_d2 = np.full(len(rows), np.inf)
        eats_pl = s.eats_plants[rs]
        if len(pcols) and eats_pl.any():
            pr = np.nonzero(eats_pl)[0]
            pdx = px[pcols][None, :] - x[pr, None]
            pdy = py[pcols][None, :] - y[pr, None]
            pd2 = pdx * pdx + pdy * pdy
            # Plants someone else is already walking to are left to them
            pclaim = claim[pcols]
            c = np.maximum(pclaim, 0)
            claim_live = (pclaim >= 0) & s.alive[c] & (m.target_plant[c] == pcols)
            # ...unless they are weaker: then it comes down to a contest at the plant
            weaker = self.strength(c)[None, :] < self.strength(rows[pr])[:, None]
            claimed_by_other = claim_live[None, :] & (pclaim[None, :] != rows[pr, None]) & ~weaker
            banned = pcols[None, :] == np.where(m.yield_timer[rows[pr]] > 0, m.banned_plant[rows[pr]], -1)[:, None]
            ok = edible[pcols][None, :] & ~claimed_by_other & ~banned & (pd2 <= vision2[pr])
            pd2 = np.where(ok, pd2, np.inf)
            bp = np.argmin(pd2, axis=1)
            best_p[pr] = pcols[bp]
            best_p_d2[pr] = pd2[np.arange(len(pr)), bp]

        # Keep the current target while it is still in sight and valid
        cur_c, cur_p = m.target_creature[rows], m.target_plant[rows]
        keep_c = cur_c >= 0
        if keep_c.any():
            kc = np.nonzero(keep_c)[0]
            colpos = np.full(s.count, -1)
            colpos[cols] = np.arange(len(cols))
            pos = colpos[cur_c[kc]]
            keep_c[kc] = (pos >= 0) & is_cfood[kc, np.maximum(pos, 0)]
        keep_p = (cur_p >= 0) & (cur_p < len(px))
        if keep_p.any():
            kp = np.nonzero(keep_p)[0]
            tp = cur_p[kp]
            keep_p[kp] = edible[tp] & ((px[tp] - x[kp]) ** 2 + (py[tp] - y[kp]) ** 2 <= vision2[kp, 0])

        # Kinds of food, best first: corpse, live prey, plant. Meat beats plants unless
        # the creature is starving: then the closest food of any kind will do
        starving = v.food[rows] <= s.p("desperate_ratio", rows) * s.p("max_food", rows)
        best_c_ok = np.isfinite(best_c_d2)
        new_kind = np.where(best_c_ok, np.where(s.alive[np.maximum(best_c, 0)], 1, 0), 3)
        new_kind = np.where(np.isfinite(best_p_d2) & (~best_c_ok | (starving & (best_p_d2 < best_c_d2))),
                            2, new_kind)
        cur_kind = np.where(keep_c, np.where(s.alive[np.maximum(cur_c, 0)], 1, 0), np.where(keep_p, 2, 3))
        # Keep the current target unless a better kind of food is in sight (starving: keep it)
        keep = (keep_c | keep_p) & (starving | (cur_kind <= new_kind))
        # Prey it has already bitten is never let go while it lives
        cc = np.maximum(cur_c, 0)
        gap2 = (s.body.x[cc] - x) ** 2 + (s.body.y[cc] - y) ** 2
        latched = (m.latched[rows] & (cur_c >= 0) & s.used[cc] & s.alive[cc]
                   & (gap2 <= vision2[:, 0]))  # ...unless it got clean away
        keep |= latched
        keep_c, keep_p = keep & (keep_c | latched), keep & keep_p & ~latched
        has_food = (new_kind < 3) | keep_c | keep_p
        target_c = np.where(keep_c, cur_c, np.where(~keep & (new_kind < 2), best_c, -1))
        target_p = np.where(keep_p, cur_p, np.where(~keep & (new_kind == 2), best_p, -1))
        m.latched[rows] &= latched & (target_c == cur_c)

        # --- instinct ---
        food, foraging = v.food[rows], v.foraging[rows]
        # Resting only helps if there is food left to digest into stamina; a starving,
        # exhausted creature has to keep looking for food on its own muscle
        tired = v.tired[rows] & (food > P["starve_ratio"][rs] * s.p("max_food", rows))
        # Relax when well fed or to heal; a tired creature rests even when hungry
        max_health = s.p("max_health", rows)
        relaxed = tired | (~foraging & ((food / s.p("max_food", rows) >= s.p("relaxed_ratio", rows))
                                        | (v.health[rows] < max_health)))
        can_repro = ((food >= s.p("reproduction_food_threshold", rows))
                     & (food > s.p("reproduction_food_cost", rows))
                     & (v.health[rows] >= s.p("reproduction_health_ratio", rows) * max_health)
                     & (v.reproduction_timer[rows] <= 0))
        if can_repro.any():
            can_repro &= s.populations()[rs] < P["max_population"][rs]

        hunger_wins = v.bold[rows] & foraging & has_food & ~any_attacking
        # A peer's alarm call counts as danger even without seeing the predator
        alarmed = (m.alarm_timer[rows] > 0) & ~has_threat
        flee = (has_threat | alarmed) & ~hunger_wins
        repro = ~flee & can_repro
        eat = ~flee & ~repro & ((~tired & foraging & has_food) | latched)
        relax = ~flee & ~repro & ~eat & relaxed
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
                    act, target_c[j], target_p[j], run = self._ask_brain(
                        int(r), brain, cols, is_threat[j], attacking[j], is_cfood[j], d2[j],
                        target_p[j], can_repro[j])
                    repro[j] = act == "reproduce"
                    action[j] = WANDER if act == "reproduce" else act
                    brain_runs[j] = run

        previous_prey = m.target_creature[rows].copy()
        m.action[rows] = action
        m.target_creature[rows] = np.where(action == EAT, target_c, -1)
        m.target_plant[rows] = np.where(action == EAT, target_p, -1)
        tp_rows = rows[(action == EAT) & (target_p >= 0)]
        if len(tp_rows):
            claim[m.target_plant[tp_rows]] = tp_rows  # claim plants being walked to

        # Stalk moving prey at a walk, sprint once within sprint_range; walk to plants,
        # corpses and still prey
        tc = m.target_creature[rows]
        prey_moving = np.zeros(len(rows), dtype=bool)
        has_tc = tc >= 0
        if has_tc.any():
            t = tc[has_tc]
            hr = rows[has_tc]
            gap2 = (s.body.x[t] - s.body.x[hr]) ** 2 + (s.body.y[t] - s.body.y[hr]) ** 2
            prey_moving[has_tc] = s.alive[t] & (
                s.body.speed[t] > s.p("walk_speed", t) * s.p("relax_speed_ratio", t) * 1.01) & (
                gap2 <= s.p("sprint_range", hr) ** 2)
        m.running[rows] = ((action == EAT) & prey_moving) | ((action == FLEE) & (any_alarming | alarmed))
        # A chase starts when a hunter picks a new living prey (for the stats)
        new_chase = (action == EAT) & (tc >= 0) & (tc != previous_prey)
        if new_chase.any():
            self.world.stats["chases started"] += int((new_chase & s.alive[np.maximum(tc, 0)]).sum())
        for j, run in brain_runs.items():
            m.running[rows[j]] = run and action[j] in (EAT, FLEE)

        # Fleeing: away from all visible predators (closer ones weigh more), around water
        fr = np.nonzero(action == FLEE)[0]
        if len(fr):
            w = np.where(is_threat[fr], 1.0 / np.maximum(d2[fr], 1.0), 0.0)
            away = np.arctan2(-(dy[fr] * w).sum(axis=1), -(dx[fr] * w).sum(axis=1))
            away = np.where(has_threat[fr], away, m.alarm_heading[rows[fr]])  # heard, not seen
            m.flee_away[rows[fr]] = away
            heading = self.physics.free_heading(rows[fr], away, FLEE_OFFSETS)
            m.goal[rows[fr]] = np.where(np.isnan(heading), away, heading)
            m.detour_timer[rows[fr]] = 0.0

        self._alarm_calls(rows, cols, d2, (action == FLEE) & any_alarming)
        self._fight_for_space(rows[action != FLEE])

        nf = rows[action != FLEE]
        if len(nf):
            self._check_walls(nf)
        self._plan_avoidance(rows, cols)

        for r in rows[repro]:
            self._give_birth(int(r))

    def _alarm_calls(self, rows, cols, d2, running_scared):
        """Creatures running from a predator call out; peers of their species within
        call_range flee the same way for alarm_duration, even if they can't see it."""
        s, m = self.store, self.store.mind
        call_range = s.p("call_range", rows)
        callers = np.nonzero(running_scared & (call_range > 0) & (m.call_timer[rows] <= 0))[0]
        if not len(callers):
            return
        cr = rows[callers]
        m.call_timer[cr] = CALL_COOLDOWN
        m.call_flash[cr] = CALL_FLASH
        hears = ((d2[callers] <= (call_range[callers] ** 2)[:, None])
                 & (s.species[cols][None, :] == s.species[cr][:, None])
                 & s.alive[cols][None, :] & (cols[None, :] != cr[:, None]))
        heard_by = hears.any(axis=0)
        if not heard_by.any():
            return
        caller_of = np.argmax(hears, axis=0)[heard_by]  # first caller each listener heard
        listeners = cols[heard_by]
        m.alarm_timer[listeners] = s.p("alarm_duration", listeners)
        m.alarm_heading[listeners] = m.flee_away[cr[caller_of]]
        self.world.record(f"{s.species_type(int(cr[0])).layer_name} alarm calls")

    def _ask_brain(self, r, brain, cols, threat_row, attack_row, food_row, d2_row, tp, can_repro):
        """Build an Observation for one brain-driven creature; translate its Intent."""
        s, m, v = self.store, self.store.mind, self.store.vitals
        P, sp = s.params, s.species[r]
        layer = lambda row: s.species_type(int(row)).layer_name  # noqa: E731
        food = [Percept(("creature", int(cols[j])), layer(cols[j]), float(np.sqrt(d2_row[j])),
                        is_corpse=not s.alive[cols[j]]) for j in np.nonzero(food_row)[0]]
        if tp >= 0:
            px, py, _, _ = self.world.plant_arrays()
            food.append(Percept(("plant", int(tp)), "plants",
                                float(math.hypot(px[tp] - s.body.x[r], py[tp] - s.body.y[r]))))
        threats = [Percept(("creature", int(cols[j])), layer(cols[j]), float(np.sqrt(d2_row[j])),
                           running=bool(m.running[cols[j]]), attacking=bool(attack_row[j]))
                   for j in np.nonzero(threat_row)[0]]
        food.sort(key=lambda p: p.distance)
        threats.sort(key=lambda p: p.distance)
        food_ratio = v.food[r] / s.p("max_food", r)
        current = (("creature", int(m.target_creature[r])) if m.target_creature[r] >= 0 else
                   ("plant", int(m.target_plant[r])) if m.target_plant[r] >= 0 else None)
        obs = Observation(health_ratio=float(v.health[r] / s.p("max_health", r)),
                          stamina_ratio=float(v.stamina[r] / s.p("max_stamina", r)),
                          food_ratio=float(food_ratio),
                          foraging=bool(v.foraging[r]), bold=bool(v.bold[r]),
                          relaxed=bool(not v.foraging[r] and food_ratio >= s.p("relaxed_ratio", r)),
                          can_reproduce=bool(can_repro), current_target=current,
                          food=food[:5], threats=threats[:3])
        intent: Intent = brain.decide(obs)
        kind, idx = intent.target if isinstance(intent.target, tuple) else (None, -1)
        if intent.action == "eat":
            return EAT, (idx if kind == "creature" else -1), (idx if kind == "plant" else -1), intent.run
        if intent.action == "flee":
            return FLEE, -1, -1, intent.run
        if intent.action == "reproduce":
            return "reproduce", -1, -1, False
        return (RELAX if intent.action == "relax" else WANDER), -1, -1, False

    # ------------------------------------------------------------------- act

    def _act(self, rows, dt):
        s, m, cmd = self.store, self.store.mind, self.store.command
        action = m.action[rows]
        walk = s.p("walk_speed", rows)
        # Running needs stamina: an exhausted creature can only walk
        running = m.running[rows] & ((action == EAT) | (action == FLEE)) & (s.vitals.stamina[rows] > 1.0)
        m.running[rows] = running
        m.relaxing[rows] = action == RELAX
        cmd.speed[rows] = np.where(running, walk * s.p("run_speed_multiplier", rows),
                                   np.where(action == RELAX, walk * s.p("relax_speed_ratio", rows), walk))

        roam = rows[(action == WANDER) | (action == RELAX)]
        if len(roam):
            m.target_creature[roam] = m.target_plant[roam] = -1
            m.wander_timer[roam] -= dt
            turn = roam[m.wander_timer[roam] <= 0]
            if len(turn):
                m.wander_timer[turn] = s.p("wander_turn_interval", turn) * np.random.uniform(0.5, 1.5, len(turn))
                goal = s.body.heading[turn] + np.random.uniform(-HALF_PI, HALF_PI, len(turn))
                # Herding: drift back toward nearby peers (a cohesion of 1 heads straight for them)
                cohesion = s.p("herd_cohesion", turn)
                cx, cy, peers = self.herd_centroid(turn)
                pull = (cohesion > 0) & (peers > 0)
                if pull.any():
                    to_herd = np.arctan2(cy - s.body.y[turn], cx - s.body.x[turn])
                    goal = np.where(pull, goal + cohesion * wrap_angle(to_herd - goal), goal)
                m.goal[turn] = goal

        eaters = rows[action == EAT]
        if len(eaters):
            self._eat(eaters)

    def _eat(self, eaters):
        """Head for the target; eat it on contact."""
        s, m = self.store, self.store.mind
        px, py, edible, _ = self.world.plant_arrays()
        tc, tp = m.target_creature[eaters], m.target_plant[eaters]
        n = len(eaters)
        valid, tx, ty, tr = np.zeros(n, bool), np.zeros(n), np.zeros(n), np.zeros(n)
        c = tc >= 0
        if c.any():
            t = tc[c]
            valid[c] = s.used[t]
            tx[c], ty[c], tr[c] = s.body.x[t], s.body.y[t], s.radius[t]
        p = (tp >= 0) & (tp < len(px))
        if p.any():
            t = tp[p]
            valid[p] = edible[t]
            tx[p], ty[p], tr[p] = px[t], py[t], self.world.plant_radius(t)
        lost = eaters[~valid]
        if len(lost):
            m.action[lost] = WANDER
            m.target_creature[lost] = m.target_plant[lost] = -1
            m.running[lost] = False
        ok = np.nonzero(valid)[0]
        if not len(ok):
            return
        e = eaters[ok]
        reach = s.radius[e] + tr[ok] + s.p("eat_range", e)
        ddx, ddy = tx[ok] - s.body.x[e], ty[ok] - s.body.y[e]
        touching = ddx * ddx + ddy * ddy <= reach * reach
        steer = ~touching & (m.detour_timer[e] <= 0)  # unless detouring around water
        m.goal[e[steer]] = np.arctan2(ddy[steer], ddx[steer])
        near = ddx * ddx + ddy * ddy <= (reach + s.p("contest_range", e)) ** 2
        if near.sum() > 1:
            losers = self._contest(e[near])
            if len(losers):
                touching &= ~np.isin(e, losers)
        for j in np.nonzero(touching)[0]:
            r = int(e[j])
            t = int(m.target_creature[r])
            if t >= 0 and s.alive[t] and s.p("attack", r) > 0:
                # Latch on: keep facing the prey and match its pace instead of running past it;
                # from the first bite on, it won't switch to other food
                m.latched[r] = True
                m.goal[r] = math.atan2(ddy[j], ddx[j])
                self.store.command.speed[r] = min(self.store.command.speed[r], s.body.speed[t])
                self._fight(r, t)
            else:
                self._consume(r)

    def attack_value(self, rows):
        return self.store.attack_value(rows)

    def strength(self, rows):
        """How a creature fares in a squabble over food: species dominance x attack value."""
        return self.store.p("dominance", rows) * self.attack_value(rows)

    def _contest(self, rows):
        """Creatures close to the same food item squabble: the strongest keeps it; the
        others take a bite of damage, give it up, and won't come back to it for a while.
        Returns the losers."""
        s, m = self.store, self.store.mind
        key = np.where(m.target_plant[rows] >= 0, 2 * m.target_plant[rows], 2 * m.target_creature[rows] + 1)
        order = np.lexsort((-self.strength(rows), key))
        rows, key = rows[order], key[order]
        first = np.r_[True, key[1:] != key[:-1]]
        winner = rows[np.maximum.accumulate(np.where(first, np.arange(len(rows)), 0))]
        losers = rows[~first]
        if not len(losers):
            return losers
        winners = winner[~first]
        for w, l in zip(winners, losers):
            w, l = int(w), int(l)
            if m.attack_timer[w] <= 0:
                m.attack_timer[w] = s.p("attack_cooldown", w)
                self.metabolism.damage([l], self.attack_value(np.array([w]))[0] * s.p("rival_bite", w),
                                       f"killed in a squabble with {s.species_type(w).layer_name}")
            self.world.record(f"{s.species_type(w).layer_name} drove off {s.species_type(l).layer_name}")
        m.banned_plant[losers] = m.target_plant[losers]
        m.banned_creature[losers] = m.target_creature[losers]
        m.yield_timer[losers] = s.p("yield_time", losers)
        m.action[losers] = WANDER
        m.target_plant[losers] = m.target_creature[losers] = -1
        m.running[losers] = False
        # Back off, away from the winner
        m.goal[losers] = np.arctan2(s.body.y[losers] - s.body.y[winners], s.body.x[losers] - s.body.x[winners])
        return losers

    def _fight(self, hunter, prey):
        """Living prey isn't swallowed whole: the hunter bites (attack_cooldown apart),
        and the prey bites back, harder with its herd around it."""
        s, m = self.store, self.store.mind
        if m.attack_timer[hunter] <= 0:
            m.attack_timer[hunter] = s.p("attack_cooldown", hunter)
            self.metabolism.damage([prey], self.attack_value(np.array([hunter]))[0],
                                   f"killed by {s.species_type(hunter).layer_name}")
        if not s.alive[prey] or s.p("attack", prey) <= 0:
            return
        peers = self.herd_peers(np.array([prey]))[0]
        # Caught while exhausted, or with its herd around: turn and stand its ground
        if s.vitals.tired[prey] or peers >= 2:
            m.stand_timer[prey] = STAND_TIME
            m.stand_target[prey] = hunter
        if m.attack_timer[prey] <= 0:
            m.attack_timer[prey] = s.p("attack_cooldown", prey)
            bite = self.attack_value(np.array([prey]))[0] * (1 + s.p("herd_bonus", prey) * peers)
            self.metabolism.damage([hunter], bite, f"killed by {s.species_type(prey).layer_name} fighting back")
            if not s.alive[hunter]:
                self.world.record(f"{s.species_type(prey).layer_name} fought off a hunter")

    # --------------------------------------------------------------- crowding

    def _measure_crowding(self, rows):
        """How many of its own kind are inside each creature's personal space, and
        which of them is closest (the one it would push back against)."""
        s, m = self.store, self.store.mind
        m.crowd[rows] = 0
        m.crowd_neighbor[rows] = -1
        if not len(rows):
            return
        space = s.p("personal_space", rows)
        # Per species, so a wide personal space (territorial hunters) doesn't make every
        # herd pair up across that distance
        parts = []
        for sp in np.unique(s.species[rows]):
            local = np.nonzero(s.species[rows] == sp)[0]
            li, lj, ld = self.physics.pairs_within(rows[local], float(space[local].max()))
            parts.append((local[li], local[lj], ld))
        i = np.concatenate([p[0] for p in parts])
        j = np.concatenate([p[1] for p in parts])
        d = np.concatenate([p[2] for p in parts])
        if not len(i):
            return
        counts = np.zeros(len(rows))
        nearest = np.full(len(rows), np.inf)
        neighbor = np.full(len(rows), -1)
        for a, b in ((i, j), (j, i)):
            inside = d <= space[a]
            np.add.at(counts, a[inside], 1)
            # closest peer: sort by distance descending so the smallest is written last
            order = np.argsort(-d[inside])
            aa, bb, dd = a[inside][order], b[inside][order], d[inside][order]
            closer = dd < nearest[aa]
            nearest[aa[closer]] = dd[closer]
            neighbor[aa[closer]] = rows[bb[closer]]
        m.crowd[rows] = counts
        m.crowd_neighbor[rows] = neighbor

    def _fight_for_space(self, rows):
        """Crammed creatures may bite the closest peer crowding them (chance grows with
        how crammed they are); the bitten one backs off."""
        s, m = self.store, self.store.mind
        limit = s.p("crowd_limit", rows)
        excess = m.crowd[rows] - limit
        crammed = (excess > 0) & (m.crowd_neighbor[rows] >= 0) & (m.attack_timer[rows] <= 0)
        if not crammed.any():
            return
        chance = s.p("aggression", rows) * np.clip(excess / np.maximum(limit, 1), 0, 1)
        attackers = rows[crammed & (np.random.random(len(rows)) < chance)]
        for a in attackers:
            a = int(a)
            victim = int(m.crowd_neighbor[a])
            if not s.alive[victim]:
                continue
            m.attack_timer[a] = s.p("attack_cooldown", a)
            self.metabolism.damage([victim], self.attack_value(np.array([a]))[0] * s.p("rival_bite", a),
                                   f"killed fighting for space with its own kind")
            self.world.record(f"{s.species_type(a).layer_name} fought for space")
            if s.alive[victim] and m.action[victim] != FLEE:
                # back off, away from the attacker, for a moment
                m.action[victim] = WANDER
                m.target_creature[victim] = m.target_plant[victim] = -1
                m.goal[victim] = np.arctan2(s.body.y[victim] - s.body.y[a], s.body.x[victim] - s.body.x[a])
                m.wander_timer[victim] = 1.5

    # ------------------------------------------------------------------ herds

    def _build_herd_map(self, rows):
        """Per species, how many living creatures (and their summed positions) are in
        each herd-sized cell of the map. Rebuilt every frame; used for herd defense,
        hunters' confusion and herding."""
        s = self.store
        self._cell = float(max(s.params["herd_radius"].max(), 10.0))
        w, h = self.world.map_size
        gw, gh = int(w // self._cell) + 1, int(h // self._cell) + 1
        n_sp = len(s.species_types)
        gx = np.clip((s.body.x[rows] // self._cell).astype(np.int64), 0, gw - 1)
        gy = np.clip((s.body.y[rows] // self._cell).astype(np.int64), 0, gh - 1)
        sp = s.species[rows]
        count = np.zeros((n_sp, gw + 2, gh + 2))
        sx = np.zeros_like(count)
        sy = np.zeros_like(count)
        np.add.at(count, (sp, gx + 1, gy + 1), 1)
        np.add.at(sx, (sp, gx + 1, gy + 1), s.body.x[rows])
        np.add.at(sy, (sp, gx + 1, gy + 1), s.body.y[rows])

        def around(a):  # sum of each cell and its 8 neighbours
            out = np.zeros_like(a)
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    out[:, 1:-1, 1:-1] += a[:, 1 + ox:a.shape[1] - 1 + ox, 1 + oy:a.shape[2] - 1 + oy]
            return out
        self._herd_count, self._herd_sx, self._herd_sy = around(count), around(sx), around(sy)
        self._herd_dims = (gw, gh)

    def _herd_cells(self, rows):
        s = self.store
        gw, gh = self._herd_dims
        gx = np.clip((s.body.x[rows] // self._cell).astype(np.int64), 0, gw - 1) + 1
        gy = np.clip((s.body.y[rows] // self._cell).astype(np.int64), 0, gh - 1) + 1
        return s.species[rows], gx, gy

    def herd_peers(self, rows):
        """Same-species creatures around each row (not counting itself)."""
        sp, gx, gy = self._herd_cells(rows)
        return np.maximum(self._herd_count[sp, gx, gy] - 1, 0)

    def herd_centroid(self, rows):
        """Centre of each row's nearby same-species group (excluding itself), and its size."""
        s = self.store
        sp, gx, gy = self._herd_cells(rows)
        count = self._herd_count[sp, gx, gy] - 1
        sx = self._herd_sx[sp, gx, gy] - s.body.x[rows]
        sy = self._herd_sy[sp, gx, gy] - s.body.y[rows]
        safe = np.maximum(count, 1)
        return sx / safe, sy / safe, np.maximum(count, 0)

    def _consume(self, r):
        s, m = self.store, self.store.mind
        tc, tp = int(m.target_creature[r]), int(m.target_plant[r])
        gain = 0.0
        if tc >= 0 and s.used[tc]:
            gain = s.p("nutrition", tc)
            if s.alive[tc]:
                s.kill([tc], f"eaten by {s.species_type(r).layer_name}", leave_corpse=False)
            else:
                self.world.record(f"{s.species_type(tc).layer_name} corpses eaten")
                s.free([tc])
        elif tp >= 0:
            gain = self.world.eat_plant(tp)
        if gain:
            self.metabolism.eat(r, gain)
        m.action[r] = WANDER
        m.target_creature[r] = m.target_plant[r] = -1
        m.running[r] = False
        m.latched[r] = False

    def _give_birth(self, r):
        s = self.store
        sp = s.species[r]
        if s.populations()[sp] >= s.params["max_population"][sp]:
            return
        angle = np.random.uniform(0, TWO_PI)
        dist = s.radius[r] * 3
        cx = s.body.x[r] + dist * math.cos(angle)
        cy = s.body.y[r] + dist * math.sin(angle)
        if self.world.is_blocked(cx, cy):
            return
        self.metabolism.reproduced(r)
        name = s.species_type(r).layer_name
        self.world.record(f"{name} born")
        s.spawn(name, cx, cy, parent=r)

    # ----------------------------------------------------------------- steer

    def _check_walls(self, rows):
        """Look ahead along the current heading; pick a free direction if water is in the way."""
        s, m = self.store, self.store.mind
        heading = s.body.heading[rows]
        stuck = rows[np.isnan(self.physics.free_heading(rows, heading, np.array([0.0])))]
        if len(stuck):
            h = self.physics.free_heading(stuck, s.body.heading[stuck], DETOUR_OFFSETS)
            m.goal[stuck] = np.where(np.isnan(h), s.body.heading[stuck] + math.pi, h)
            m.detour_timer[stuck] = DETOUR_TIME

    def _plan_avoidance(self, rows, cols):
        """
        Trail planning: predict nearby creatures' paths over avoid_horizon seconds
        (constant velocity) and, if we'd touch one, veer to the side it isn't on.
        Hunters don't dodge their prey and vice versa.
        """
        s, m, b = self.store, self.store.mind, self.store.body
        rs = s.species[rows]
        horizon = s.params["avoid_horizon"][rs]
        m.avoid_offset[rows] = 0.0
        active = (horizon > 0) & (b.speed[rows] > 0)
        if not active.any():
            return
        rows, rs, horizon = rows[active], rs[active], horizon[active]
        ox = b.x[cols][None, :] - b.x[rows][:, None]
        oy = b.y[cols][None, :] - b.y[rows][:, None]
        rvx = b.vx[cols][None, :] - b.vx[rows][:, None]
        rvy = b.vy[cols][None, :] - b.vy[rows][:, None]
        closing = rvx * rvx + rvy * rvy
        with np.errstate(divide="ignore", invalid="ignore"):
            t = -(ox * rvx + oy * rvy) / closing
        cx, cy = ox + rvx * t, oy + rvy * t
        clearance = s.radius[cols][None, :] + s.radius[rows][:, None] + s.params["avoid_margin"][rs][:, None]
        hit = (s.alive[cols][None, :] & (closing > 1e-6) & (t > 0) & (t < horizon[:, None])
               & (cx * cx + cy * cy < clearance * clearance))
        hit &= cols[None, :] != rows[:, None]
        hit &= m.target_creature[cols][None, :] != rows[:, None]   # it isn't hunting me
        hit &= cols[None, :] != m.target_creature[rows][:, None]   # I'm not hunting it
        any_hit = hit.any(axis=1)
        if not any_hit.any():
            return
        t = np.where(hit, t, np.inf)
        j = np.argmin(t, axis=1)
        ar = np.arange(len(rows))
        soonest, hx, hy = t[ar, j], cx[ar, j], cy[ar, j]
        h = b.heading[rows]
        side = np.cos(h) * hy - np.sin(h) * hx
        side = np.where(side == 0, 1.0, side)
        offset = -np.sign(side) * s.params["avoid_turn"][rs] * (0.4 + 0.6 * (1 - soonest / horizon))
        m.avoid_offset[rows[any_hit]] = offset[any_hit]

    def _steer(self, rows, dt):
        """Goal heading + dodge -> the heading command physics will turn toward."""
        s, m, cmd = self.store, self.store.mind, self.store.command
        m.detour_timer[rows] = np.maximum(m.detour_timer[rows] - dt, 0)
        m.goal[rows] %= TWO_PI
        heading = m.goal[rows] + m.avoid_offset[rows]
        # Standing its ground: stop and face the attacker
        standing = (m.stand_timer[rows] > 0) & (m.stand_target[rows] >= 0)
        if standing.any():
            sr = rows[standing]
            t = m.stand_target[sr]
            alive = s.alive[t]
            face = np.arctan2(s.body.y[t] - s.body.y[sr], s.body.x[t] - s.body.x[sr])
            heading[standing] = np.where(alive, face, heading[standing])
            cmd.speed[sr] = np.where(alive, 0.0, cmd.speed[sr])
            m.stand_timer[sr[~alive]] = 0.0
        fleeing = (m.action[rows] == FLEE) & ~standing
        if fleeing.any():
            away = m.flee_away[rows]
            # A dodge while fleeing never points back toward the predators
            clamped = away + np.clip(wrap_angle(heading - away), -HALF_PI, HALF_PI)
            heading = np.where(fleeing, clamped, heading)
        cmd.heading[rows] = heading % TWO_PI
