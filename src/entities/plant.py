import math
import random
import pymunk
from entities.entity import Entity
from config import PLANT_CONFIG
from sprite_manager import sprite_manager


class Plant(Entity):
    layer_name = "plants"

    @classmethod
    def spawn(cls, scene, map_size, x: float | None = None, y: float | None = None, *, growth_level: int = 1):
        """Handler: create and register a plant at (x, y). Defaults to map center."""
        map_w, map_h = map_size
        cx = x if x is not None else map_w / 2
        cy = y if y is not None else map_h / 2
        return cls(cx, cy, scene, map_size, growth_level=growth_level)

    @classmethod
    def _try_spawn(cls, scene, map_size, seed_x: float, seed_y: float, *, growth_level: int = 1) -> bool:
        """Bounds check, spacing check, then spawn. Returns True if spawned."""
        map_width, map_height = map_size
        padding = PLANT_CONFIG["bounds_padding"]
        min_spacing = PLANT_CONFIG["min_spacing"]
        min_spacing_sq = min_spacing * min_spacing

        if not (padding <= seed_x <= map_width - padding and padding <= seed_y <= map_height - padding):
            return False

        query_bb = pymunk.BB(
            seed_x - min_spacing,
            seed_y - min_spacing,
            seed_x + min_spacing,
            seed_y + min_spacing,
        )
        for shape in scene.physics_engine.space.bb_query(query_bb, pymunk.ShapeFilter()):
            sprite = scene.physics_engine.get_sprite_for_shape(shape)
            if not isinstance(sprite, Plant):
                continue
            dx = sprite.center_x - seed_x
            dy = sprite.center_y - seed_y
            if dx * dx + dy * dy < min_spacing_sq:
                return False

        cls.spawn(scene, map_size, seed_x, seed_y, growth_level=growth_level)
        return True

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
            if self.drop_seed():
                self.reproduction_history["successes"] += 1
                self.reproduction_history["fails"] = 0
            else:
                self.reproduction_history["fails"] += 1
                self.reproduction_history["successes"] = 0

            if self.reproduction_history["successes"] >= self.config["reproduction"]["max_successes"]:
                self.reproduction_history["successes"] = 0
                self.reproduction_history["factor"] = 1

            if self.reproduction_history["fails"] >= self.config["reproduction"]["max_fails"]:
                self.reproduction_history["fails"] = 0
                self.reproduction_history["factor"] = self.reproduction_history["factor"] * self.config["reproduction"]["factor"]

            # Reset timer with randomization
            base_delay = self.config["reproduction_delay"] * self.reproduction_history["factor"]
            variability = 0.2
            self.reproduction_timer = base_delay * random.uniform(1-variability, 1+variability)

    def drop_seed(self) -> bool:
        direction = random.uniform(0, 2 * math.pi)
        distance = random.uniform(self.config["seed_min_distance"], self.config["seed_range"])
        seed_x = self.center_x + distance * math.cos(direction)
        seed_y = self.center_y + distance * math.sin(direction)
        return Plant._try_spawn(self.scene, self.map_size, seed_x, seed_y)
