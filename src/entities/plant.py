import math
import random
from entities.entity import Entity
from config import PLANT_CONFIG
from sprite_manager import sprite_manager


class Plant(Entity):
    layer_name = "plants"

    _pending_seeds: list = []  # List of (plant, seed_x, seed_y) for batch processing

    @classmethod
    def spawn(cls, world, x: float | None = None, y: float | None = None, *, growth_level: int = 1):
        """Handler: create and register a plant at (x, y). Defaults to map center."""
        map_w, map_h = world.map_size
        cx = x if x is not None else map_w / 2
        cy = y if y is not None else map_h / 2
        return cls(cx, cy, world, growth_level=growth_level)

    @classmethod
    def _is_valid_seed_position(cls, world, seed_x: float, seed_y: float, exclude: set) -> bool:
        """Check bounds, water, and min spacing from plants and excluded positions."""
        map_width, map_height = world.map_size
        padding = PLANT_CONFIG["bounds_padding"]
        min_spacing = PLANT_CONFIG["min_spacing"]
        min_spacing_sq = min_spacing * min_spacing

        if not (padding <= seed_x <= map_width - padding and padding <= seed_y <= map_height - padding):
            return False

        # Spatial-hash lookup instead of scanning every plant
        if world.nearby("plants", seed_x, seed_y, min_spacing):
            return False

        for (ex_x, ex_y) in exclude:
            dx = ex_x - seed_x
            dy = ex_y - seed_y
            if dx * dx + dy * dy < min_spacing_sq:
                return False

        if world.is_blocked(seed_x, seed_y):
            return False
        # Seeds take root more readily in fertile biomes (forest, swamp) than in desert or tundra
        return random.random() < min(1.0, world.plant_factor(seed_x, seed_y))

    @classmethod
    def _try_spawn(cls, world, seed_x: float, seed_y: float, *, growth_level: int = 1) -> bool:
        """Bounds check, spacing check, then spawn. Returns True if spawned."""
        if not cls._is_valid_seed_position(world, seed_x, seed_y, exclude=set()):
            return False
        cls.spawn(world, seed_x, seed_y, growth_level=growth_level)
        return True

    @classmethod
    def process_pending_seeds(cls, world) -> None:
        """Process all queued seeds in one batch. Validates, spawns valid ones, updates reproduction_history."""
        if not cls._pending_seeds:
            return

        batch = cls._pending_seeds
        cls._pending_seeds = []

        spawned_positions: set[tuple[float, float]] = set()
        reproduction = PLANT_CONFIG["reproduction"]

        for plant, seed_x, seed_y in batch:
            success = cls._is_valid_seed_position(world, seed_x, seed_y, exclude=spawned_positions)
            if success:
                cls.spawn(world, seed_x, seed_y)
                spawned_positions.add((seed_x, seed_y))

            history = plant.reproduction_history
            if success:
                history["successes"] += 1
                history["fails"] = 0
            else:
                history["fails"] += 1
                history["successes"] = 0

            if history["successes"] >= reproduction["max_successes"]:
                history["successes"] = 0
                history["factor"] = 1

            if history["fails"] >= reproduction["max_fails"]:
                history["fails"] = 0
                history["factor"] *= reproduction["factor"]

            base_delay = plant.config["reproduction_delay"] * history["factor"]
            variability = 0.2
            plant.reproduction_timer = base_delay * random.uniform(1 - variability, 1 + variability)

    @staticmethod
    def spawn_initial(world):
        """Place initial_count plants at random spots that respect the spacing (fewer
        if the map runs out of room)."""
        padding = PLANT_CONFIG["bounds_padding"]
        map_w, map_h = world.map_size
        wanted = int(PLANT_CONFIG["initial_count"])
        placed = 0
        for _ in range(wanted * 10):
            if placed >= wanted:
                break
            growth_level = random.randint(1, PLANT_CONFIG["max_growth_level"])
            x = random.uniform(padding, map_w - padding)
            y = random.uniform(padding, map_h - padding)
            placed += Plant._try_spawn(world, x, y, growth_level=growth_level)

    def __init__(self, x, y, world, growth_level=1):
        if growth_level < 1 or growth_level > PLANT_CONFIG["max_growth_level"]:
            raise ValueError(f"Invalid growth level: {growth_level}. Must be between 1 and {PLANT_CONFIG['max_growth_level']}")

        self.config = PLANT_CONFIG
        self.regrow_timer = 0.0
        # Randomize so plants planted together don't all grow on the same frame
        self.growth_timer = self.config["max_growth_timer"] * random.uniform(0.8, 1.2)
        self.reproduction_timer = self.config["reproduction_delay"] * random.uniform(0.8, 1.2)
        self.growth_textures = sprite_manager.get_texture(self.config["growth_textures"])
        self.reproduction_history = {
            "successes": 0,
            "fails": 0,
            "factor": 1
        }

        initial_texture = self.growth_textures[growth_level - 1]

        super().__init__(initial_texture, x, y, world)

        self.growth_level = growth_level
        self.full_grown = self.growth_level >= self.config["max_growth_level"]
        self._register()
        self.biome_growth = world.plant_factor(x, y)
        world.plant_added(self)

    def set_growth_level(self, new_growth_level: int):
        self.full_grown = new_growth_level >= self.config["max_growth_level"]
        requested_level = min(max(new_growth_level, 1), self.config["max_growth_level"])
        texture_index = max(0, min(requested_level - 1, len(self.growth_textures) - 1))

        # Ensure texture_index is valid and the texture exists
        if texture_index < len(self.growth_textures) and self.growth_textures[texture_index] is not None:
            if self.growth_level != requested_level or self.texture != self.growth_textures[texture_index]:
                self.growth_level = requested_level
                self.texture = self.growth_textures[texture_index]
                self.world.plant_changed(self)
                # Reset timer with randomization
                variability = 0.2
                self.growth_timer = self.config["max_growth_timer"] * random.uniform(1-variability, 1+variability)
        else:
            print(f"Warning: Could not set growth level {requested_level}. Texture not available.")

    @property
    def edible(self) -> bool:
        """Seedlings, and plants grazed less than regrow_time ago, are left alone so
        grazed areas can recover (otherwise one plant feeds a crowd forever)."""
        return self.growth_level >= self.config["min_edible_level"] and self.regrow_timer <= 0

    def be_eaten(self) -> float:
        """Graze the plant back to a seedling and return the energy it provides."""
        energy = self.config["provided_energy"][self.growth_level - 1]
        self.full_grown = False
        self.growth_level = 1
        self.texture = self.growth_textures[0]
        self.growth_timer = self.config["max_growth_timer"] * random.uniform(0.8, 1.2)
        self.regrow_timer = self.config["regrow_time"] * random.uniform(0.8, 1.2)
        self.world.plant_changed(self)
        return energy

    def update(self, delta_time: float = 1/60):
        if self.regrow_timer > 0:
            self.regrow_timer -= delta_time
            if self.regrow_timer <= 0:
                self.world.plant_changed(self)  # edible again
        if self.full_grown:
            self.reproduce(delta_time)
        else:
            self.grow(delta_time)

    def grow(self, delta_time: float = 1/60):
        self.growth_timer -= delta_time
        if self.growth_timer <= 0:
            self.set_growth_level(self.growth_level + 1)

    def reproduce(self, delta_time: float = 1/60):
        self.reproduction_timer -= delta_time
        if self.reproduction_timer <= 0:
            self._queue_seed()

    def _queue_seed(self) -> None:
        """Queue a seed for batch processing. Actual spawn and history update happen in process_pending_seeds."""
        direction = random.uniform(0, 2 * math.pi)
        distance = random.uniform(self.config["seed_min_distance"], self.config["seed_range"])
        seed_x = self.center_x + distance * math.cos(direction)
        seed_y = self.center_y + distance * math.sin(direction)
        Plant._pending_seeds.append((self, seed_x, seed_y))
