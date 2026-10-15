"""
MetabolismSystem: the only writer of store.vitals (health, stamina, food,
moods), and the one that decides deaths and when corpses disappear.

Per step, for every living creature at once:
- stamina pays for being alive and moving; moving costs
  walk_stamina_cost * (speed / walk_speed) ^ k, with k chosen so running at
  run_speed_multiplier x walk speed costs run_stamina_multiplier x as much.
  Relaxing moves for free.
- being alive slowly drains the food bar
- above the starving line, food digests into stamina (while stamina isn't full)
- stamina owed when it's already empty comes out of health (burning muscle)
- below the starving line, health drops
- relaxing while hurt heals (like sleep), costing extra stamina and food
- zero health: dies, leaving a corpse; corpses vanish after corpse_duration
- moods: foraging starts below hungry_ratio of the food bar and lasts until
  full_ratio; tiredness starts below rest_ratio of stamina and lasts until
  rested_ratio; every boldness_interval s a foraging creature rolls whether hunger
  beats fear (chance grows with hunger)
"""
import numpy as np


class MetabolismSystem:
    def __init__(self, store):
        self.store = store

    def step(self, dt):
        s, v = self.store, self.store.vitals
        n = s.count
        corpses = np.nonzero(s.used[:n] & ~s.alive[:n])[0]
        if len(corpses):
            v.corpse_timer[corpses] -= dt
            gone = corpses[v.corpse_timer[corpses] <= 0]
            if len(gone):
                s.free(gone)

        rows = s.living_rows()
        if not len(rows):
            return
        P, sp = s.params, s.species[rows]
        max_h, max_s, max_f = s.p("max_health", rows), s.p("max_stamina", rows), s.p("max_food", rows)
        starve_line = P["starve_ratio"][sp] * max_f
        health, stamina, food = v.health[rows], v.stamina[rows], v.food[rows]

        # What this step costs (movement is priced against the species' base walk speed,
        # so a creature born faster pays more for its speed)
        speed = s.body.speed[rows]
        relaxing = s.mind.relaxing[rows]
        moving = (speed > 0) & ~relaxing
        k = np.log(P["run_stamina_multiplier"][sp]) / np.log(P["run_speed_multiplier"][sp])
        move_cost = np.where(moving, s.p("walk_stamina_cost", rows) * (speed / P["walk_speed"][sp]) ** k, 0.0)
        healing = relaxing & (health < max_h) & (food > starve_line)
        stamina_cost = (s.p("alive_stamina_cost", rows) + move_cost
                        + np.where(healing, P["heal_stamina_cost"][sp], 0.0)) * dt
        food = np.maximum(food - (s.p("food_drain", rows) + np.where(healing, P["heal_food_cost"][sp], 0.0)) * dt, 0.0)

        # Digest: food above the starving line turns into stamina
        eff = P["digest_efficiency"][sp]
        digest = np.clip(np.minimum(P["digest_rate"][sp] * dt, food - starve_line), 0.0, None)
        digest = np.minimum(digest, np.maximum(max_s - stamina, 0.0) / eff)
        food -= digest
        stamina += digest * eff

        # Pay; what stamina can't cover is taken from health
        stamina -= stamina_cost
        owed = np.maximum(-stamina, 0.0)
        stamina = np.maximum(stamina, 0.0)
        health -= owed * P["muscle_burn"][sp]
        starving = food <= starve_line
        health -= np.where(starving, P["starve_damage"][sp] * dt, 0.0)
        health = np.minimum(health + np.where(healing, P["heal_rate"][sp] * dt, 0.0), max_h)

        v.health[rows], v.stamina[rows], v.food[rows] = health, stamina, food
        v.reproduction_timer[rows] -= dt

        dead = health <= 0
        if dead.any():
            for cause, mask in (("starved", dead & starving), ("collapsed from exhaustion", dead & ~starving)):
                if mask.any():
                    s.kill(rows[mask], cause, leave_corpse=True)
            rows = s.living_rows()
            if not len(rows):
                return
            sp = s.species[rows]

        ratio = v.food[rows] / s.p("max_food", rows)
        v.foraging[rows[ratio < P["hungry_ratio"][sp]]] = True
        v.foraging[rows[ratio >= P["full_ratio"][sp]]] = False
        # Tiredness: below rest_ratio of stamina until back at rested_ratio
        sratio = v.stamina[rows] / s.p("max_stamina", rows)
        v.tired[rows[sratio < P["rest_ratio"][sp]]] = True
        v.tired[rows[sratio >= P["rested_ratio"][sp]]] = False

        v.boldness_timer[rows] -= dt
        roll = rows[v.boldness_timer[rows] <= 0]
        if len(roll):
            rs = s.species[roll]
            v.boldness_timer[roll] = P["boldness_interval"][rs]
            v.bold[roll] = v.foraging[roll] & (np.random.random(len(roll)) < self.boldness_chance(roll))

    def boldness_chance(self, rows):
        """Chance that hunger beats fear: 0 at the hungry line, hunger_boldness with an empty food bar."""
        s = self.store
        hunger = np.clip(1 - s.vitals.food[rows] / (s.p("max_food", rows) * s.p("hungry_ratio", rows)), 0, 1)
        return s.p("hunger_boldness", rows) * hunger

    def eat(self, row, amount):
        """Food goes into the food bar (digestion turns it into stamina over time)."""
        s = self.store
        cap = s.p("max_food", row)
        s.vitals.food[row] = min(cap, s.vitals.food[row] + amount)

    def damage(self, rows, amounts, cause):
        """Wounds. Creatures brought to zero health die (and leave a corpse)."""
        s, v = self.store, self.store.vitals
        rows = np.asarray(rows)
        v.health[rows] -= amounts
        dead = rows[(v.health[rows] <= 0) & s.alive[rows]]
        if len(dead):
            s.kill(dead, cause, leave_corpse=True)

    def reproduced(self, row):
        """Pay the cost of giving birth and restart the reproduction timer."""
        s = self.store
        sp = s.species[row]
        s.vitals.food[row] -= s.params["reproduction_food_cost"][sp]
        s.vitals.reproduction_timer[row] = s.params["reproduction_interval"][sp]
