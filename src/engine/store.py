"""
CreatureStore: every creature is a row; its data lives in numpy arrays grouped
by the system that owns (writes) them. Anyone may read anything; each group
has exactly one writer, so it is always clear who changed what:

    store.*        core: used, alive, species, radius          -> the store (spawn / kill / free)
    store.body     x, y, vx, vy, heading, speed                 -> PhysicsEngine
    store.command  heading, speed                               -> BehaviourSystem (what physics should do)
    store.mind     action, targets, gait, timers, steering      -> BehaviourSystem
    store.vitals   energy, foraging, bold, timers               -> MetabolismSystem
"""
import math

import numpy as np

TWO_PI = 2 * math.pi

# Per-species parameters, copied from the live config dicts by refresh_params()
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

# Action codes (store.mind.action)
WANDER, RELAX, EAT, FLEE = 0, 1, 2, 3
ACTION_NAMES = {WANDER: "wander", RELAX: "relax", EAT: "eat", FLEE: "flee"}


class Columns:
    """A named group of equally long numpy arrays."""

    def __init__(self, **fields):
        self._fields = fields  # name -> (dtype, fill)

    def grow(self, capacity):
        for name, (dtype, fill) in self._fields.items():
            old = getattr(self, name, None)
            arr = np.full(capacity, fill, dtype=dtype)
            if old is not None:
                arr[:len(old)] = old
            setattr(self, name, arr)


F, I, B = (np.float64, 0.0), (np.int32, -1), (bool, False)


class CreatureStore:
    def __init__(self, world, species_types, sprite_sizes):
        self.world = world
        self.species_types = list(species_types)
        self.layer_index = {s.layer_name: i for i, s in enumerate(self.species_types)}
        self.sprite_sizes = sprite_sizes  # species index -> (width, height) in world px
        self.core = Columns(used=B, alive=B, species=I, radius=F)
        self.body = Columns(x=F, y=F, vx=F, vy=F, heading=F, speed=F)
        self.command = Columns(heading=F, speed=F)
        self.mind = Columns(action=I, target_creature=I, target_plant=I, running=B, relaxing=B,
                            goal=F, avoid_offset=F, flee_away=F,
                            think_timer=F, wander_timer=F, detour_timer=F)
        self.vitals = Columns(energy=F, foraging=B, bold=B,
                              boldness_timer=F, reproduction_timer=F, corpse_timer=F)
        self.capacity = 0
        self.count = 0  # rows ever used (high-water mark); freed rows below it are reused
        self._free = []
        self._listeners = []  # called with rows that were freed
        self._grow(512)
        self.refresh_params()

    # Core columns are used everywhere, so expose them directly
    used = property(lambda self: self.core.used)
    alive = property(lambda self: self.core.alive)
    species = property(lambda self: self.core.species)
    radius = property(lambda self: self.core.radius)

    def _grow(self, capacity):
        for group in (self.core, self.body, self.command, self.mind, self.vitals):
            group.grow(capacity)
        self.capacity = capacity

    def refresh_params(self):
        """Per-species parameter vectors and the food chain, from the live config dicts."""
        cfgs = [s.config for s in self.species_types]
        self.params = {k: np.array([float(c[k]) for c in cfgs]) for k in PARAM_KEYS}
        n = len(cfgs)
        self.eats = np.zeros((n, n), dtype=bool)  # eats[a, b]: species a eats species b
        self.eats_plants = np.zeros(n, dtype=bool)
        for a, c in enumerate(cfgs):
            for food in c["diet"]:
                if food == "plants":
                    self.eats_plants[a] = True
                elif food in self.layer_index:
                    self.eats[a, self.layer_index[food]] = True

    def p(self, key, rows):
        """A species parameter, per row."""
        return self.params[key][self.core.species[rows]]

    def species_type(self, row):
        return self.species_types[self.core.species[row]]

    def on_free(self, callback):
        self._listeners.append(callback)

    # ------------------------------------------------------------- lifecycle

    def spawn(self, layer_name, x, y, energy=None):
        if self._free:
            i = self._free.pop()
        else:
            if self.count >= self.capacity:
                self._grow(self.capacity * 2)
            i = self.count
            self.count += 1
        s = self.layer_index[layer_name]
        cfg = self.species_types[s].config
        w, h = self.sprite_sizes[s]
        rng = np.random
        c, b, cmd, m, v = self.core, self.body, self.command, self.mind, self.vitals
        c.species[i], c.used[i], c.alive[i], c.radius[i] = s, True, True, max(w, h) / 2
        heading = rng.uniform(0, TWO_PI)
        b.x[i], b.y[i], b.heading[i] = x, y, heading
        b.vx[i] = b.vy[i] = b.speed[i] = 0.0
        cmd.heading[i], cmd.speed[i] = heading, 0.0
        m.action[i] = WANDER
        m.target_creature[i] = m.target_plant[i] = -1
        m.running[i] = m.relaxing[i] = False
        m.goal[i] = heading
        m.avoid_offset[i] = m.flee_away[i] = 0.0
        m.think_timer[i] = rng.uniform(0, cfg["think_interval"])
        m.wander_timer[i] = rng.uniform(0, cfg["wander_turn_interval"])
        m.detour_timer[i] = 0.0
        v.energy[i] = cfg["birth_energy"] if energy is None else energy
        v.foraging[i], v.bold[i] = True, False
        v.boldness_timer[i] = v.corpse_timer[i] = 0.0
        v.reproduction_timer[i] = cfg["reproduction_interval"]
        return i

    def kill(self, rows, cause, leave_corpse):
        """Living creatures die: they stop, and either stay as a corpse or vanish."""
        rows = np.asarray(rows)
        for r in rows:
            self.world.record(f"{self.species_type(int(r)).layer_name} {cause}")
        self.core.alive[rows] = False
        self.body.speed[rows] = self.body.vx[rows] = self.body.vy[rows] = 0.0
        self.command.speed[rows] = 0.0
        if leave_corpse:
            self.vitals.corpse_timer[rows] = self.p("corpse_duration", rows)
        else:
            self.free(rows)

    def free(self, rows):
        """Remove creatures (or corpses) from the map; their rows get reused."""
        rows = np.asarray(rows)
        self.core.used[rows] = False
        self.core.alive[rows] = False
        self._free.extend(int(r) for r in rows)
        for callback in self._listeners:
            callback(rows)

    def populations(self):
        n = self.count
        live = self.core.alive[:n]
        return np.bincount(self.core.species[:n][live], minlength=len(self.species_types))

    def population(self, layer_name):
        return int(self.populations()[self.layer_index[layer_name]])

    def living_rows(self):
        return np.nonzero(self.core.alive[:self.count])[0]
