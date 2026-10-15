import json
import random
from collections import Counter

import arcade
import numpy as np
from config import BIOME_CONFIG, MAP_CONFIG, PLANT_CONFIG
from entities.plant import Plant
from entities.herbivore import Herbivore
from entities.carnivore import Carnivore
from entities.smartie import Smarty
from engine import CreatureEngine
from world import mapgen
from environment import Environment
from sprite_manager import sprite_manager

MAP_PATH = "assets/maps/uniform_map.json"
TILE_SCALING = 1.0
# Ground tile ids creatures can walk on; every other ground tile (the pond and its
# shoreline) is treated as water. Tiled gids, as stored in the map json.
WALKABLE_GROUND_GIDS = {51}
CREATURE_TYPES = (Herbivore, Smarty, Carnivore)
BIOME_EFFECTS = ("plants", "speed", "vision", "stamina", "hunger")
# Plants only need coarse timing (growth takes seconds), so tick them a few times a second
PLANT_TICK = 0.25
# Cap the behaviour step so a slow frame doesn't teleport creatures through walls
MAX_STEP = 1 / 20


class EntityManager():
    """
    The world: owns the map, the plants (arcade sprites) and the creatures (the numpy
    CreatureEngine), and offers the services they use: wall checks, plant arrays, stats.
    """
    def __init__(self):
        if MAP_CONFIG["source"] == "tiled":
            self._load_tiled_map()
        else:
            self._generate_map()
        self.refresh_biomes()

        # Plants are many and static, so they get a spatial hash (used for seed spacing)
        self.scene.add_sprite_list("plants", use_spatial_hash=True)
        self._plants: list[Plant] = []
        self._new_plants: list[Plant] = []
        self._px = self._py = self._pradius = np.zeros(0)
        self._pedible = np.zeros(0, dtype=bool)
        self._pclaim = np.zeros(0, dtype=np.int32)

        self.creature_layers = [c.layer_name for c in CREATURE_TYPES]
        sizes = []
        for c in CREATURE_TYPES:
            tex = sprite_manager.get_texture(c.texture_name)
            scale = tex.properties.get("scale", 1.0)
            sizes.append((tex.width * scale, tex.height * scale))
        self.creatures = CreatureEngine(self, CREATURE_TYPES, sizes)
        self.environment = Environment(CREATURE_TYPES)
        self.creatures.store.env = self.environment

        self.stats: Counter[str] = Counter()
        self._extinct_for: dict[str, float] = {}
        self._removals: list = []
        self._plant_time = 0.0
        Plant._pending_seeds = []  # a restart must not inherit seeds from the old world
        self.refresh_food_chain()

    def refresh_food_chain(self) -> None:
        """Re-read species settings (diets, speeds, ...). Call again after settings change."""
        self.creatures.refresh_params()
        self.refresh_biomes()
        self.warnings = []
        speed = {c.layer_name: c.config["walk_speed"] * c.config["run_speed_multiplier"] for c in CREATURE_TYPES}
        for hunter in CREATURE_TYPES:
            for prey in hunter.config["diet"]:
                if prey in speed and speed[hunter.layer_name] <= speed[prey]:
                    self.warnings.append(f"{hunter.layer_name} can't outrun {prey} "
                                         f"({speed[hunter.layer_name]:.0f} vs {speed[prey]:.0f} px/s)")
        for warning in self.warnings:
            print("Warning:", warning)

    def update(self, delta_time: float = 1/60):
        """Update plants (coarse tick), then all creatures."""
        delta_time = min(delta_time, MAX_STEP)
        self.environment.step(delta_time)

        self._plant_time += delta_time
        if self._plant_time >= PLANT_TICK:
            # Plants grow and seed faster in summer, barely in winter
            plant_dt = self._plant_time * self.environment.plant_growth
            plants = self.scene["plants"]
            for plant in plants:
                plant.update(plant_dt * plant.biome_growth)
            # Cold seasons wither plants back toward seedlings (less food in winter)
            chill = max(0.0, 1.0 - self.environment.plant_growth)
            wither = PLANT_CONFIG["winter_wither"] * chill * self._plant_time
            if wither > 0 and len(plants):
                for i in np.nonzero(np.random.random(len(plants)) < wither)[0]:
                    plant = plants[int(i)]
                    if plant.growth_level > 1:
                        plant.set_growth_level(plant.growth_level - 1)
            self._plant_time = 0.0
            Plant.process_pending_seeds(self)

        self.creatures.step(delta_time)
        self._rescue_extinct(delta_time)
        self._flush_removals()

    def _rescue_extinct(self, dt):
        """A species gone for reintroduce_after seconds gets a fresh group of founders
        (0 = let it stay extinct)."""
        for c in CREATURE_TYPES:
            delay = c.config["reintroduce_after"]
            if delay <= 0 or self.population(c.layer_name) > 0:
                self._extinct_for[c.layer_name] = 0.0
                continue
            self._extinct_for[c.layer_name] = self._extinct_for.get(c.layer_name, 0.0) + dt
            if self._extinct_for[c.layer_name] >= delay:
                self._extinct_for[c.layer_name] = 0.0
                self.record(f"{c.layer_name} reintroduced")
                self._spawn_founders(c)

    def _spawn_founders(self, creature_type):
        cfg = creature_type.config
        for _ in range(int(cfg["initial_count"])):
            pos = self.random_free_position(cfg["bounds_padding"])
            if pos is not None:
                row = self.creatures.spawn(creature_type.layer_name, *pos)
                # Stagger the first births so the founders don't all reproduce at once
                self.creatures.store.vitals.reproduction_timer[row] *= random.uniform(0.3, 1.0)

    def get_map_size(self):
        return self.map_size

    # ------------------------------------------------------------------- map

    def _generate_map(self) -> None:
        """A fresh world from noise (see world/mapgen.py): biomes, water, ground art."""
        cfg = MAP_CONFIG
        self.tiles = mapgen.generate(cfg)  # biome id per tile, row 0 = bottom
        self._tile_size = float(cfg["tile_size"])
        self._grid_rows, self._grid_cols = self.tiles.shape
        self._blocked = np.isin(self.tiles, mapgen.BLOCKED_BIOMES)
        self.map_size = (self._grid_cols * self._tile_size, self._grid_rows * self._tile_size)
        image = mapgen.render_ground(self.tiles, int(self._tile_size), cfg["seed"])
        # Bounding-box hit box: the default one scans every pixel of this big image
        texture = arcade.Texture(image.convert("RGBA"), hash=f"ground-{cfg['seed']}-{image.size}",
                                 hit_box_algorithm=arcade.hitbox.algo_bounding_box)
        ground = arcade.Sprite(texture)
        ground.position = (self.map_size[0] / 2, self.map_size[1] / 2)
        self.scene = arcade.Scene()
        self.scene.add_sprite_list("ground")
        self.scene.add_sprite("ground", ground)

    def _load_tiled_map(self) -> None:
        """The hand-made Tiled map: grassland everywhere, its pond and walls blocked."""
        self.tile_map = arcade.load_tilemap(MAP_PATH, scaling=TILE_SCALING)
        self.scene = arcade.Scene.from_tilemap(self.tile_map)
        self.map_size = (self.tile_map.width * self.tile_map.tile_width,
                         self.tile_map.height * self.tile_map.tile_height)
        self._build_blocked_grid()
        self.tiles = np.where(self._blocked, mapgen.WATER, mapgen.GRASSLAND).astype(np.int8)

    def refresh_biomes(self) -> None:
        """Biome effect tables (effect -> value per biome id) from BIOME_CONFIG."""
        self.biome_effects = {}
        for effect in BIOME_EFFECTS:
            table = np.ones(len(mapgen.BIOMES))
            for b, name in enumerate(mapgen.BIOMES):
                table[b] = BIOME_CONFIG.get(f"{name}_{effect}", 1.0)
            self.biome_effects[effect] = table

    def biome_at(self, xs, ys):
        """Biome id under each point (water outside the map)."""
        col = np.floor(np.asarray(xs) / self._tile_size).astype(np.int64)
        row = np.floor(np.asarray(ys) / self._tile_size).astype(np.int64)
        inside = (col >= 0) & (col < self._grid_cols) & (row >= 0) & (row < self._grid_rows)
        result = np.full(col.shape, mapgen.WATER, dtype=np.int64)
        result[inside] = self.tiles[row[inside], col[inside]]
        return result

    def plant_factor(self, x, y) -> float:
        """How well plants grow at (x, y): growth speed and the chance a seed takes."""
        return float(self.biome_effects["plants"][self.biome_at(x, y)])

    def spawn_initial_population(self):
        Plant.spawn_initial(self)
        for creature_type in CREATURE_TYPES:
            self._spawn_founders(creature_type)

    # ------------------------------------------------------- world services

    def population(self, layer_name: str) -> int:
        """Living members of a layer (corpses don't count)."""
        if layer_name == "plants":
            return len(self.scene["plants"])
        return self.creatures.population(layer_name)

    def nearby(self, layer_name: str, x: float, y: float, radius: float) -> list:
        """Plants within radius of (x, y) (uses the plants' spatial hash)."""
        from arcade.types import LRBT
        candidates = self.scene[layer_name].spatial_hash.get_sprites_near_rect(
            LRBT(x - radius, x + radius, y - radius, y + radius))
        r2 = radius * radius
        return [e for e in candidates
                if not e.removed and (e.center_x - x) ** 2 + (e.center_y - y) ** 2 <= r2]

    # Plants as arrays for the creature engine. Plants are only ever added (grazing resets them to a
    # seedling), so each keeps a fixed index and only new ones need appending.
    def plant_added(self, plant) -> None:
        plant.index = len(self._plants) + len(self._new_plants)
        self._new_plants.append(plant)

    def plant_changed(self, plant) -> None:
        i = getattr(plant, "index", -1)
        if 0 <= i < len(self._pedible):
            self._pedible[i] = plant.edible
            self._pradius[i] = plant.width / 2

    def plant_arrays(self):
        """(x, y, edible, claim) arrays; claim[i] is the creature row walking to plant i, or -1."""
        if self._new_plants:
            new = self._new_plants
            self._px = np.concatenate([self._px, [p.center_x for p in new]])
            self._py = np.concatenate([self._py, [p.center_y for p in new]])
            self._pradius = np.concatenate([self._pradius, [p.width / 2 for p in new]])
            self._pedible = np.concatenate([self._pedible, [p.edible for p in new]])
            self._pclaim = np.concatenate([self._pclaim, np.full(len(new), -1, dtype=np.int32)])
            self._plants.extend(new)
            self._new_plants = []
        return self._px, self._py, self._pedible, self._pclaim

    def plant_radius(self, indices):
        return self._pradius[indices]

    def eat_plant(self, index) -> float:
        plant = self._plants[index]
        if not plant.edible:
            return 0.0
        return plant.be_eaten()

    def _build_blocked_grid(self) -> None:
        """One byte per tile: 1 where a wall or water tile is. Rows run bottom-up like world y."""
        with open(MAP_PATH) as f:
            layers = {layer["name"]: layer["data"] for layer in json.load(f)["layers"]}
        cols, rows = self.tile_map.width, self.tile_map.height
        ground = np.array(layers["ground"]).reshape(rows, cols)
        walls = np.array(layers["walls"]).reshape(rows, cols)
        blocked = (walls != 0) | ~np.isin(ground, list(WALKABLE_GROUND_GIDS))
        self._blocked = blocked[::-1].copy()  # Tiled rows are top-down
        self._tile_size = self.tile_map.tile_width * TILE_SCALING
        self._grid_cols, self._grid_rows = cols, rows

    def is_blocked(self, x: float, y: float) -> bool:
        """True if (x, y) is off the map or on a wall/water tile."""
        col = int(x // self._tile_size)
        row = int(y // self._tile_size)
        if not (0 <= col < self._grid_cols and 0 <= row < self._grid_rows):
            return True
        return bool(self._blocked[row, col])

    def blocked_at(self, xs, ys):
        """Vectorized is_blocked for arrays of points."""
        col = np.floor(np.asarray(xs) / self._tile_size).astype(np.int64)
        row = np.floor(np.asarray(ys) / self._tile_size).astype(np.int64)
        inside = (col >= 0) & (col < self._grid_cols) & (row >= 0) & (row < self._grid_rows)
        result = np.ones(col.shape, dtype=bool)
        result[inside] = self._blocked[row[inside], col[inside]]
        return result

    def random_free_position(self, padding: float, tries: int = 50):
        w, h = self.map_size
        for _ in range(tries):
            x = random.uniform(padding, w - padding)
            y = random.uniform(padding, h - padding)
            if not self.is_blocked(x, y):
                return x, y
        return None

    def queue_removal(self, entity) -> None:
        self._removals.append(entity)

    def record(self, event: str) -> None:
        """Count a life event (births, deaths by cause) for the HUD and debugging."""
        self.stats[event] += 1

    def _flush_removals(self) -> None:
        if not self._removals:
            return
        for entity in self._removals:
            entity._remove_now()
        self._removals.clear()
