"""
CreatureStore: every creature is a row; its data lives in numpy arrays grouped
by the system that owns (writes) them. Anyone may read anything; each group
has exactly one writer, so it is always clear who changed what:

    store.*        core: used, alive, species, radius          -> the store (spawn / kill / free)
    store.body     x, y, vx, vy, heading, speed                 -> PhysicsEngine
    store.command  heading, speed                               -> BehaviourSystem (what physics should do)
    store.mind     action, targets, gait, timers, steering      -> BehaviourSystem
    store.vitals   health, stamina, food, moods, timers         -> MetabolismSystem
    store.genes    inherited trait multipliers                  -> set at birth only
"""
import math

import numpy as np

TWO_PI = 2 * math.pi

# Per-species parameters, copied from the live config dicts by refresh_params()
PARAM_KEYS = [
    "walk_speed", "run_speed_multiplier", "run_stamina_multiplier", "relax_speed_ratio",
    "turn_rate", "wander_turn_interval", "wall_probe_distance",
    "avoid_horizon", "avoid_margin", "avoid_turn",
    "vision_range", "think_interval",
    "max_health", "max_stamina", "max_food", "birth_food", "birth_stamina_ratio",
    "alive_stamina_cost", "walk_stamina_cost",
    "food_drain", "digest_rate", "digest_efficiency", "starve_ratio", "starve_damage", "muscle_burn",
    "heal_rate", "heal_stamina_cost", "heal_food_cost",
    "hungry_ratio", "full_ratio", "relaxed_ratio", "rest_ratio", "rested_ratio", "eat_range",
    "sprint_range",
    "hunger_boldness", "boldness_interval",
    "reproduction_interval", "reproduction_food_threshold", "reproduction_health_ratio",
    "reproduction_food_cost",
    "nutrition", "corpse_duration", "max_population",
    "mutation_rate", "founder_variation", "night_vision", "winter_hunger",
    "attack_damage", "defense_damage", "attack_cooldown",
    "herd_radius", "herd_bonus", "crowd_penalty", "herd_cohesion",
    "dominance", "contest_damage", "contest_range", "yield_time",
    "call_range", "alarm_duration",
]

# Inherited traits. Each gene is a multiplier around 1.0, copied from the parent
# with a small random mutation. Each one changes some species parameters, with
# trade-offs so no gene is free: parameter -> [(gene, exponent), ...]
# Every one of these creature features is its own gene: a multiplier on the species
# value, inherited from the parent with a small mutation.
GENES = (
    "walk_speed", "vision_range",
    "max_stamina", "max_food",                                   # stamina pool, stomach size
    "digest_rate", "digest_efficiency",                          # food -> stamina conversion
    "alive_stamina_cost", "walk_stamina_cost", "run_stamina_multiplier",  # what activities cost
    "heal_rate", "heal_stamina_cost", "heal_food_cost",          # recovery while relaxing
    "food_drain",                                                # hunger
    "hungry_ratio", "full_ratio", "relaxed_ratio", "rest_ratio", "rested_ratio",  # thresholds
    "hunger_boldness",
    "reproduction_food_threshold", "reproduction_health_ratio", "reproduction_food_cost",
    "reproduction_interval",
)
GENE_EFFECTS = {gene: [(gene, 1.0)] for gene in GENES}
# Kept from before: sharp eyes and a big stamina pool cost upkeep
GENE_EFFECTS["alive_stamina_cost"] = [("alive_stamina_cost", 1.0), ("vision_range", 0.3)]
GENE_EFFECTS["food_drain"] = [("food_drain", 1.0), ("max_stamina", 0.3)]
GENE_RANGE = (0.5, 2.0)
# Fractions stay fractions whatever the genes say
RATIO_LIMITS = {"hungry_ratio": (0.05, 0.95), "full_ratio": (0.1, 1.0), "relaxed_ratio": (0.05, 1.0),
                "rest_ratio": (0.0, 0.9), "rested_ratio": (0.05, 1.0), "reproduction_health_ratio": (0.1, 1.0),
                "hunger_boldness": (0.0, 1.0), "run_stamina_multiplier": (1.0, None)}
# Parameters the environment scales per species (day/night, seasons): param -> Environment attribute
ENV_EFFECTS = {"vision_range": "vision", "food_drain": "food_drain"}
# Parameters the ground under each creature scales: param -> biome effect (see BIOME_CONFIG)
BIOME_PARAM_EFFECTS = {"walk_speed": "speed", "vision_range": "vision", "alive_stamina_cost": "stamina",
                       "walk_stamina_cost": "stamina", "food_drain": "hunger"}

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
        self.core = Columns(used=B, alive=B, species=I, radius=F, generation=I, uid=(np.int64, -1),
                            biome=I)
        self.genes = Columns(**{g: (np.float64, 1.0) for g in GENES})
        self.body = Columns(x=F, y=F, vx=F, vy=F, heading=F, speed=F)
        self.command = Columns(heading=F, speed=F)
        self.mind = Columns(action=I, target_creature=I, target_plant=I, running=B, relaxing=B,
                            goal=F, avoid_offset=F, flee_away=F,
                            think_timer=F, wander_timer=F, detour_timer=F, attack_timer=F,
                            yield_timer=F, banned_plant=I, banned_creature=I,
                            alarm_timer=F, alarm_heading=F, call_timer=F, call_flash=F,
                            stand_timer=F, stand_target=I)
        self.vitals = Columns(health=F, stamina=F, food=F, foraging=B, bold=B, tired=B, hurt_flash=F,
                              boldness_timer=F, reproduction_timer=F, corpse_timer=F)
        self.env = None  # Environment, set by the world
        self.capacity = 0
        self.count = 0  # rows ever used (high-water mark); freed rows below it are reused
        self._free = []
        self._next_uid = 0  # rows get reused; uid never repeats
        self._listeners = []  # called with rows that were freed
        self.watched_uid = -1      # a creature someone is following (see hud.py)
        self.watched_death = None  # ...and how it died
        self._grow(512)
        self.refresh_params()

    # Core columns are used everywhere, so expose them directly
    used = property(lambda self: self.core.used)
    alive = property(lambda self: self.core.alive)
    species = property(lambda self: self.core.species)
    radius = property(lambda self: self.core.radius)

    def _grow(self, capacity):
        for group in (self.core, self.body, self.command, self.mind, self.vitals, self.genes):
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
        """A parameter per row: the species value, shaped by each creature's genes."""
        sp = self.core.species[rows]
        value = self.params[key][sp]
        for gene, exponent in GENE_EFFECTS.get(key, ()):
            value = value * getattr(self.genes, gene)[rows] ** exponent
        if key in RATIO_LIMITS:
            value = np.clip(value, *RATIO_LIMITS[key])
        if self.env is not None and key in ENV_EFFECTS:
            value = value * getattr(self.env, ENV_EFFECTS[key])[sp]
        if key in BIOME_PARAM_EFFECTS:
            biome = self.core.biome[rows]
            value = value * np.where(biome >= 0, self.world.biome_effects[BIOME_PARAM_EFFECTS[key]][biome], 1.0)
        return value

    def update_biomes(self, rows):
        """Which biome each creature stands on (the world calls this every frame)."""
        self.core.biome[rows] = self.world.biome_at(self.body.x[rows], self.body.y[rows])

    def gene_max(self, gene):
        n = self.count
        live = self.core.alive[:n]
        return float(getattr(self.genes, gene)[:n][live].max()) if live.any() else 1.0

    def species_type(self, row):
        return self.species_types[self.core.species[row]]

    def on_free(self, callback):
        self._listeners.append(callback)

    # ------------------------------------------------------------- lifecycle

    def spawn(self, layer_name, x, y, food=None, parent=None):
        """New creature. With a parent it inherits mutated genes; founders get random ones."""
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
        sigma = cfg["mutation_rate"] if parent is not None else cfg["founder_variation"]
        for gene in GENES:
            base = getattr(self.genes, gene)[parent] if parent is not None else 1.0
            getattr(self.genes, gene)[i] = np.clip(base * np.exp(rng.normal(0, sigma)), *GENE_RANGE)
        c.generation[i] = c.generation[parent] + 1 if parent is not None else 0
        c.species[i], c.used[i], c.alive[i] = s, True, True
        c.uid[i] = self._next_uid
        self._next_uid += 1
        c.radius[i] = max(w, h) / 2
        c.biome[i] = int(self.world.biome_at(x, y))
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
        m.detour_timer[i] = m.attack_timer[i] = m.yield_timer[i] = 0.0
        m.banned_plant[i] = m.banned_creature[i] = -1
        m.alarm_timer[i] = m.alarm_heading[i] = m.call_timer[i] = m.call_flash[i] = 0.0
        m.stand_timer[i], m.stand_target[i] = 0.0, -1
        v.health[i] = self.p("max_health", i)
        v.stamina[i] = self.p("max_stamina", i) * cfg["birth_stamina_ratio"]
        v.food[i] = cfg["birth_food"] if food is None else food
        v.foraging[i], v.bold[i], v.tired[i], v.hurt_flash[i] = True, False, False, 0.0
        v.boldness_timer[i] = v.corpse_timer[i] = 0.0
        v.reproduction_timer[i] = self.p("reproduction_interval", i)
        return i

    def kill(self, rows, cause, leave_corpse):
        """Living creatures die: they stop, and either stay as a corpse or vanish."""
        rows = np.asarray(rows)
        for r in rows:
            self.world.record(f"{self.species_type(int(r)).layer_name} {cause}")
            if self.core.uid[r] == self.watched_uid:
                self.watched_death = cause
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
