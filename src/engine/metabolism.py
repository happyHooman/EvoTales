"""
MetabolismSystem: the only writer of store.vitals, and the one that decides
deaths from starvation and when corpses disappear.

Per step, for every living creature at once:
- energy drops by the cost of being alive plus moving (relaxing moves for free);
  cost = walk_cost * (speed / walk_speed) ^ k, with k chosen so that running at
  run_speed_multiplier x walk speed costs run_energy_multiplier x walk energy
- zero energy: dies, leaving a corpse; corpses vanish after corpse_duration
- hunger hysteresis: foraging starts below hungry_ratio and lasts until full_ratio
- hunger beats fear: every boldness_interval s, a foraging creature rolls whether
  it ignores predators that aren't chasing it (chance grows with hunger)
- the reproduction timer counts down
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
        speed = s.body.speed[rows]
        moving = (speed > 0) & ~s.mind.relaxing[rows]
        k = np.log(P["run_energy_multiplier"][sp]) / np.log(P["run_speed_multiplier"][sp])
        move_cost = np.where(moving, P["walk_energy_cost"][sp] * (speed / P["walk_speed"][sp]) ** k, 0.0)
        v.energy[rows] -= (P["alive_energy_cost"][sp] + move_cost) * dt
        v.reproduction_timer[rows] -= dt

        starved = rows[v.energy[rows] <= 0]
        if len(starved):
            s.kill(starved, "starved", leave_corpse=True)
            rows = s.living_rows()
            if not len(rows):
                return
            sp = s.species[rows]

        ratio = v.energy[rows] / P["max_energy"][sp]
        v.foraging[rows[ratio < P["hungry_ratio"][sp]]] = True
        v.foraging[rows[ratio >= P["full_ratio"][sp]]] = False

        v.boldness_timer[rows] -= dt
        roll = rows[v.boldness_timer[rows] <= 0]
        if len(roll):
            rs = s.species[roll]
            v.boldness_timer[roll] = P["boldness_interval"][rs]
            hunger = np.clip(1 - v.energy[roll] / (P["max_energy"][rs] * P["hungry_ratio"][rs]), 0, 1)
            v.bold[roll] = v.foraging[roll] & (np.random.random(len(roll)) < P["hunger_boldness"][rs] * hunger)

    def gain(self, row, amount):
        s = self.store
        cap = s.params["max_energy"][s.species[row]]
        s.vitals.energy[row] = min(cap, s.vitals.energy[row] + amount)

    def reproduced(self, row):
        """Pay the cost of giving birth and restart the reproduction timer."""
        s = self.store
        sp = s.species[row]
        s.vitals.energy[row] -= s.params["reproduction_energy_cost"][sp]
        s.vitals.reproduction_timer[row] = s.params["reproduction_interval"][sp]
