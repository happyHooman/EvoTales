import math
import random
from entities.entity import Entity
from config import PLANT_CONFIG
from sprite_manager import sprite_manager


class Plant(Entity):
    layer_name = "plants"
    use_physics = False  # Soft plants: creatures pass through, no collision

    _pending_seeds: list = []  # List of (plant, seed_x, seed_y) for batch processing

    @classmethod
    def spawn(cls, scene, map_size, x: float | None = None, y: float | None = None, *, growth_level: int = 1):
        """Handler: create and register a plant at (x, y). Defaults to map center."""
        map_w, map_h = map_size
        cx = x if x is not None else map_w / 2
        cy = y if y is not None else map_h / 2
        return cls(cx, cy, scene, map_size, growth_level=growth_level)

    @classmethod
    def _is_valid_seed_position(cls, scene, map_size, seed_x: float, seed_y: float, exclude: set) -> bool:
        """Check bounds and min spacing from plants and excluded positions."""
        map_width, map_height = map_size
        padding = PLANT_CONFIG["bounds_padding"]
        min_spacing = PLANT_CONFIG["min_spacing"]
        min_spacing_sq = min_spacing * min_spacing

        if not (padding <= seed_x <= map_width - padding and padding <= seed_y <= map_height - padding):
            return False

        try:
            plants_layer = scene["plants"]
        except KeyError:
            plants_layer = ()

        for sprite in plants_layer:
            if not isinstance(sprite, Plant):
                continue
            dx = sprite.center_x - seed_x
            dy = sprite.center_y - seed_y
            if dx * dx + dy * dy < min_spacing_sq:
                return False

        for (ex_x, ex_y) in exclude:
            dx = ex_x - seed_x
            dy = ex_y - seed_y
            if dx * dx + dy * dy < min_spacing_sq:
                return False

        return True

    @classmethod
    def _try_spawn(cls, scene, map_size, seed_x: float, seed_y: float, *, growth_level: int = 1) -> bool:
        """Bounds check, spacing check, then spawn. Returns True if spawned."""
        if not cls._is_valid_seed_position(scene, map_size, seed_x, seed_y, exclude=set()):
            return False
        cls.spawn(scene, map_size, seed_x, seed_y, growth_level=growth_level)
        return True

    @classmethod
    def process_pending_seeds(cls, scene, map_size) -> None:
        """Process all queued seeds in one batch. Validates, spawns valid ones, updates reproduction_history."""
        if not cls._pending_seeds:
            return

        batch = cls._pending_seeds
        cls._pending_seeds = []

        spawned_positions: set[tuple[float, float]] = set()
        results: dict[object, bool] = {}  # plant -> success

        for plant, seed_x, seed_y in batch:
            valid = cls._is_valid_seed_position(scene, map_size, seed_x, seed_y, exclude=spawned_positions)
            if valid:
                cls.spawn(scene, map_size, seed_x, seed_y)
                spawned_positions.add((seed_x, seed_y))
                results[plant] = True
            else:
                results[plant] = False

        for plant, _, _ in batch:
            success = results[plant]
            if success:
                plant.reproduction_history["successes"] += 1
                plant.reproduction_history["fails"] = 0
            else:
                plant.reproduction_history["fails"] += 1
                plant.reproduction_history["successes"] = 0

            if plant.reproduction_history["successes"] >= plant.config["reproduction"]["max_successes"]:
                plant.reproduction_history["successes"] = 0
                plant.reproduction_history["factor"] = 1

            if plant.reproduction_history["fails"] >= plant.config["reproduction"]["max_fails"]:
                plant.reproduction_history["fails"] = 0
                plant.reproduction_history["factor"] *= plant.config["reproduction"]["factor"]

            base_delay = plant.config["reproduction_delay"] * plant.reproduction_history["factor"]
            variability = 0.2
            plant.reproduction_timer = base_delay * random.uniform(1 - variability, 1 + variability)

    @staticmethod
    def spawn_initial(scene, map_size):
        padding = PLANT_CONFIG["bounds_padding"]
        map_w, map_h = map_size
        for _ in range(PLANT_CONFIG["initial_count"]):
            growth_level = random.randint(1, PLANT_CONFIG["max_growth_level"])
            x = random.uniform(padding, map_w - padding)
            y = random.uniform(padding, map_h - padding)
            Plant._try_spawn(scene, map_size, x, y, growth_level=growth_level)

    def __init__(self, x, y, scene, map_size, growth_level=1):
        if growth_level < 1 or growth_level > PLANT_CONFIG["max_growth_level"]:
            raise ValueError(f"Invalid growth level: {growth_level}. Must be between 1 and {PLANT_CONFIG['max_growth_level']}")
        if scene is None:
            raise ValueError("Scene is required for plant initialization")

        self.config = PLANT_CONFIG
        self.growth_timer = self.config["max_growth_timer"]
        self.reproduction_timer = self.config["reproduction_delay"]
        self.scene = scene
        self.map_size = map_size
        self.growth_textures = sprite_manager.get_texture(self.config["growth_textures"])
        self.reproduction_history = {
            "successes": 0,
            "fails": 0,
            "factor": 1
        }

        # Ensure texture_index is valid and the texture exists
        initial_texture = self.growth_textures[growth_level - 1]

        super().__init__(initial_texture, x, y)

        self.growth_level = growth_level
        self.full_grown = self.growth_level >= self.config["max_growth_level"]
        self._register(physics_params=self.config.get("physics", {}))

    def set_growth_level(self, new_growth_level: int):
        self.full_grown = new_growth_level >= self.config["max_growth_level"]
        requested_level = min(max(new_growth_level, 1), self.config["max_growth_level"])
        texture_index = max(0, min(requested_level - 1, len(self.growth_textures) - 1))
        
        # Ensure texture_index is valid and the texture exists
        if texture_index < len(self.growth_textures) and self.growth_textures[texture_index] is not None:
            if self.growth_level != requested_level or self.texture != self.growth_textures[texture_index]:
                self.growth_level = requested_level
                self.texture = self.growth_textures[texture_index]
                # Reset timer with randomization
                variability = 0.2
                self.growth_timer = self.config["max_growth_timer"] * random.uniform(1-variability, 1+variability)
        else:
            print(f"Warning: Could not set growth level {requested_level}. Texture not available.")

    def update(self, delta_time: float = 1/60):
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

    def drop_seed(self) -> bool:
        direction = random.uniform(0, 2 * math.pi)
        distance = random.uniform(self.config["seed_min_distance"], self.config["seed_range"])
        seed_x = self.center_x + distance * math.cos(direction)
        seed_y = self.center_y + distance * math.sin(direction)
        return Plant._try_spawn(self.scene, self.map_size, seed_x, seed_y)
