import math
import random
from entities.entity import Entity
from config import PLANT_CONFIG
from sprite_manager import sprite_manager


class Plant(Entity):
    @staticmethod
    def spawn_initial(entity_manager):
        padding = PLANT_CONFIG["bounds_padding"]
        map_w, map_h = entity_manager.map_size
        for _ in range(PLANT_CONFIG["initial_count"]):
            growth_level = random.randint(1, PLANT_CONFIG["max_growth_level"])
            x = random.uniform(padding, map_w - padding)
            y = random.uniform(padding, map_h - padding)
            entity_manager.handle_seed_drop(x, y, growth_level=growth_level)

    def __init__(self, x, y, entity_manager, growth_level=1):
        if growth_level < 1 or growth_level > PLANT_CONFIG["max_growth_level"]:
            raise ValueError(f"Invalid growth level: {growth_level}. Must be between 1 and {PLANT_CONFIG['max_growth_level']}")
        if entity_manager is None:
            raise ValueError("Entity manager is required for plant initialization")
        
        self.config = PLANT_CONFIG
        self.growth_timer = self.config["max_growth_timer"]
        self.reproduction_timer = self.config["reproduction_delay"]
        self.entity_manager = entity_manager
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
        return self.entity_manager.handle_seed_drop(seed_x, seed_y)
