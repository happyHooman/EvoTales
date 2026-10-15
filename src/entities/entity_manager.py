import json
import math
import random
from collections import Counter

import arcade
from arcade.types import LRBT
from config import DEFAULT_DAMPING, GRAVITY
from sprite_config import SPRITE_ANGLE_OFFSET
from entities.plant import Plant
from entities.herbivore import Herbivore
from entities.carnivore import Carnivore
from entities.smartie import Smarty

MAP_PATH = "assets/maps/uniform_map.json"
TILE_SCALING = 1.0
# Ground tile ids creatures can walk on; every other ground tile (the pond and its
# shoreline) is treated as water. Tiled gids, as stored in the map json.
WALKABLE_GROUND_GIDS = {51}
CREATURE_TYPES = (Herbivore, Smarty, Carnivore)
# Plants only need coarse timing (growth takes seconds), so tick them a few times a second
PLANT_TICK = 0.25
# Cap the physics/behaviour step so a slow frame doesn't teleport creatures through walls
MAX_STEP = 1 / 20
ALL_CREATURES = "*creatures"  # pseudo-layer for nearby(): every creature layer at once
# Cell size of the creature grid used for vision and avoidance queries
GRID_CELL = 96


class EntityManager():
    """
    The world: owns the scene, physics and map, and offers the services entities
    use (spatial queries, wall checks, deferred removal). Lifecycle handlers live
    on entities: Plant.spawn(world, x, y), Herbivore.spawn(world), etc.
    """
    def __init__(self):
        self.tile_map = arcade.load_tilemap(MAP_PATH, scaling=TILE_SCALING)
        self.scene = arcade.Scene.from_tilemap(self.tile_map)
        self.scene.physics_engine = arcade.PymunkPhysicsEngine(damping=DEFAULT_DAMPING, gravity=GRAVITY)
        self.map_size = self.get_map_size()
        self._build_blocked_grid()

        # Walls and water are static physics bodies so creatures cannot pass through
        static = dict(friction=0.6, body_type=arcade.PymunkPhysicsEngine.STATIC)
        self.scene.physics_engine.add_sprite_list(self.scene["walls"], **static)
        water = arcade.SpriteList()  # physics only, not drawn (ground layer already shows it)
        water.extend(s for s in self.scene["ground"] if self.is_blocked(s.center_x, s.center_y))
        self.scene.physics_engine.add_sprite_list(water, **static)

        # Runtime layers (not from tilemap), created up front so they exist even when a
        # species has no members. Plants are many and static, so they get a spatial hash.
        # Creatures are few and always moving: re-hashing every move costs more than
        # scanning the list, so they don't.
        self.scene.add_sprite_list("plants", use_spatial_hash=True)
        for creature_type in CREATURE_TYPES:
            self.scene.add_sprite_list(creature_type.layer_name)

        self.creature_layers = [c.layer_name for c in CREATURE_TYPES]
        self._grids = {}
        self.stats: Counter[str] = Counter()
        self._living: Counter[str] = Counter()
        self._removals: list = []
        self._plant_time = 0.0
        Plant._pending_seeds = []  # a restart must not inherit seeds from the old world
        self.refresh_food_chain()

    def refresh_food_chain(self) -> None:
        """Derive who hunts whom from the species diets. Call again after diets change."""
        self._predators = {
            prey.layer_name: [hunter.layer_name for hunter in CREATURE_TYPES
                              if prey.layer_name in hunter.config["diet"]]
            for prey in CREATURE_TYPES
        }
        self.warnings = []
        speed = {c.layer_name: c.config["walk_speed"] * c.config["run_speed_multiplier"] for c in CREATURE_TYPES}
        for prey, hunters in self._predators.items():
            for hunter in hunters:
                if speed[hunter] <= speed[prey]:
                    self.warnings.append(f"{hunter} can't outrun {prey} ({speed[hunter]:.0f} vs {speed[prey]:.0f} px/s)")
        for warning in self.warnings:
            print("Warning:", warning)

    def update(self, delta_time: float = 1/60):
        """Update plants (coarse tick), creatures, then physics."""
        delta_time = min(delta_time, MAX_STEP)

        self._plant_time += delta_time
        if self._plant_time >= PLANT_TICK:
            for plant in self.scene["plants"]:
                plant.update(self._plant_time)
            self._plant_time = 0.0
            Plant.process_pending_seeds(self)

        if not self._grids:
            self._sync_and_index()
        for creature_type in CREATURE_TYPES:
            # Copy: creatures may give birth during the pass
            for creature in list(self.scene[creature_type.layer_name]):
                creature.update(delta_time)

        self._flush_removals()
        self.scene.physics_engine.step(delta_time, resync_sprites=False)
        self._sync_and_index()

    def get_map_size(self):
        return self.tile_map.width * self.tile_map.tile_width, self.tile_map.height * self.tile_map.tile_height

    def spawn_initial_population(self):
        Plant.spawn_initial(self)
        for creature_type in CREATURE_TYPES:
            creature_type.spawn_initial(self)

    # ------------------------------------------------------- world services

    def population(self, layer_name: str) -> int:
        """Living members of a layer (corpses don't count)."""
        if layer_name == "plants":
            return len(self.scene["plants"])
        return self._living[layer_name]

    def predators_of(self, layer_name: str) -> list[str]:
        return self._predators.get(layer_name, [])

    def on_birth(self, creature) -> None:
        self._living[creature.layer_name] += 1

    def on_death(self, creature) -> None:
        self._living[creature.layer_name] -= 1

    def _sync_and_index(self) -> None:
        """
        After the physics step, in one pass over every creature:
        - copy body positions to the sprites (a lean version of arcade's resync,
          which also re-reads angles and fires callbacks we don't use), and
        - bucket creatures (corpses included) into GRID_CELL-sized cells with their
          position cached. Creatures move every frame, so this per-frame rebuild is far
          cheaper than keeping arcade's spatial hash in sync on every move, and it turns
          vision/avoidance queries from O(N) scans into a few cells.
        """
        degrees = math.degrees
        grids = {}
        everyone = {}  # all layers together, for collision avoidance
        for layer in self.creature_layers:
            cells = {}
            for e in self.scene[layer]:
                if e.removed:
                    continue
                if e.alive:
                    x, y = e._body.position
                    e.position = (x, y)
                    if e.heading != e.drawn_heading:
                        e.drawn_heading = e.heading
                        e.angle = -degrees(e.heading + SPRITE_ANGLE_OFFSET)
                else:
                    x, y = e.position
                key = (int(x // GRID_CELL), int(y // GRID_CELL))
                entry = (e, x, y)
                bucket = cells.get(key)
                if bucket is None:
                    cells[key] = [entry]
                else:
                    bucket.append(entry)
                bucket = everyone.get(key)
                if bucket is None:
                    everyone[key] = [entry]
                else:
                    bucket.append(entry)
            grids[layer] = cells
        grids[ALL_CREATURES] = everyone
        self._grids = grids

    def nearby_entries(self, layer_name: str, x: float, y: float, radius: float):
        """Raw grid entries (entity, x, y) of a creature layer in the cells around a circle.
        Cheaper than nearby() for hot loops; the caller does its own distance test."""
        cells = self._grids.get(layer_name, {})
        x0, x1 = int((x - radius) // GRID_CELL), int((x + radius) // GRID_CELL)
        y0, y1 = int((y - radius) // GRID_CELL), int((y + radius) // GRID_CELL)
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                bucket = cells.get((cx, cy))
                if bucket is not None:
                    yield from bucket

    def nearby(self, layer_name: str, x: float, y: float, radius: float,
               include_corpses: bool = False) -> list[tuple]:
        """Entities in a layer within radius of (x, y), as (entity, distance) pairs.
        Living ones only, unless include_corpses."""
        r2 = radius * radius
        found = []
        cells = self._grids.get(layer_name)
        if cells is not None:
            # Creature positions are as of the start of this frame (a sub-pixel lag)
            x0, x1 = int((x - radius) // GRID_CELL), int((x + radius) // GRID_CELL)
            y0, y1 = int((y - radius) // GRID_CELL), int((y + radius) // GRID_CELL)
            for cx in range(x0, x1 + 1):
                for cy in range(y0, y1 + 1):
                    bucket = cells.get((cx, cy))
                    if bucket is None:
                        continue
                    for e, ex, ey in bucket:
                        if e.removed or not (e.alive or include_corpses):
                            continue
                        dx = ex - x
                        dy = ey - y
                        d2 = dx * dx + dy * dy
                        if d2 <= r2:
                            found.append((e, d2 ** 0.5))
            return found
        sprite_list = self.scene[layer_name]
        hash_ = sprite_list.spatial_hash
        candidates = (hash_.get_sprites_near_rect(LRBT(x - radius, x + radius, y - radius, y + radius))
                      if hash_ is not None else sprite_list)
        for e in candidates:
            if e.removed or not (e.alive or include_corpses):
                continue
            dx = e.center_x - x
            dy = e.center_y - y
            d2 = dx * dx + dy * dy
            if d2 <= r2:
                found.append((e, d2 ** 0.5))
        return found

    def _build_blocked_grid(self) -> None:
        """One byte per tile: 1 where a wall or water tile is. Rows run bottom-up like world y."""
        with open(MAP_PATH) as f:
            layers = {layer["name"]: layer["data"] for layer in json.load(f)["layers"]}
        cols, rows = self.tile_map.width, self.tile_map.height
        ground, walls = layers["ground"], layers["walls"]
        self._tile_size = self.tile_map.tile_width * TILE_SCALING
        self._grid_cols, self._grid_rows = cols, rows
        self._blocked = bytearray(cols * rows)
        for i in range(cols * rows):
            if walls[i] or ground[i] not in WALKABLE_GROUND_GIDS:
                row_from_top, col = divmod(i, cols)
                self._blocked[(rows - 1 - row_from_top) * cols + col] = 1

    def is_blocked(self, x: float, y: float) -> bool:
        """True if (x, y) is off the map or on a wall/water tile. O(1) grid lookup."""
        col = int(x // self._tile_size)
        row = int(y // self._tile_size)
        if not (0 <= col < self._grid_cols and 0 <= row < self._grid_rows):
            return True
        return self._blocked[row * self._grid_cols + col] == 1

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
