import math
import random
from .entity import Entity
from config import HERBIVORE_CONFIG
from sprite_manager import sprite_manager
from sprite_config import SPRITE_ANGLE_OFFSET


class Herbivore(Entity):
    layer_name = "herbivores"

    @classmethod
    def spawn(cls, scene, map_size, x: float | None = None, y: float | None = None):
        """Handler: create and register a herbivore at (x, y). Defaults to map center."""
        map_w, map_h = map_size
        cx = x if x is not None else map_w / 2
        cy = y if y is not None else map_h / 2
        return cls(cx, cy, scene)

    @classmethod
    def spawn_initial(cls, scene, map_size):
        """Spawn initial herbivore population according to config."""
        padding = HERBIVORE_CONFIG.get("bounds_padding", 20)
        map_w, map_h = map_size
        for _ in range(HERBIVORE_CONFIG["initial_count"]):
            x = random.uniform(padding, map_w - padding)
            y = random.uniform(padding, map_h - padding)
            cls.spawn(scene, map_size, x, y)

    def __init__(self, x, y, scene):
        texture = sprite_manager.get_texture("herbivore")
        super().__init__(texture, x, y)
        self.scene = scene
        self.config = HERBIVORE_CONFIG
        self.facing_angle = random.uniform(0, 2 * math.pi)
        self.turn_timer = self.config["turn_interval"]
        self._register(physics_params=self.config.get("physics", {}))

    def update(self, delta_time: float = 1 / 60):
        self.turn_timer -= delta_time
        if self.turn_timer <= 0:
            self.facing_angle = random.uniform(0, 2 * math.pi)
            self.turn_timer = self.config["turn_interval"]

        speed = self.config["speed"]
        vx = speed * math.cos(self.facing_angle)
        vy = speed * math.sin(self.facing_angle)

        physics = self.scene.physics_engine
        po = physics.get_physics_object(self)
        if po:
            po.body.velocity = (vx, vy)
            po.body.angle = self.facing_angle + SPRITE_ANGLE_OFFSET
