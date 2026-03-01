import math
import random
from .entity import Entity
from config import HERBIVORE_CONFIG
from sprite_manager import sprite_manager
from sprite_config import SPRITE_ANGLE_OFFSET


class Herbivore(Entity):
    layer_name = "herbivores"

    @classmethod
    def spawn(cls, entity_manager, x: float | None = None, y: float | None = None):
        """Handler: create and register a herbivore at (x, y). Defaults to map center."""
        map_w, map_h = entity_manager.map_size
        cx = x if x is not None else map_w / 2
        cy = y if y is not None else map_h / 2
        return cls(cx, cy, entity_manager)

    def __init__(self, x, y, entity_manager):
        texture = sprite_manager.get_texture("herbivore")
        super().__init__(texture, x, y)
        self.entity_manager = entity_manager
        self.config = HERBIVORE_CONFIG
        self.facing_angle = random.uniform(0, 2 * math.pi)
        self.turn_timer = self.config["turn_interval"]
        self._register()

    def update(self, delta_time: float = 1 / 60):
        self.turn_timer -= delta_time
        if self.turn_timer <= 0:
            self.facing_angle = random.uniform(0, 2 * math.pi)
            self.turn_timer = self.config["turn_interval"]

        speed = self.config["speed"]
        vx = speed * math.cos(self.facing_angle)
        vy = speed * math.sin(self.facing_angle)

        physics = self.entity_manager.scene.physics_engine
        po = physics.get_physics_object(self)
        if po:
            po.body.velocity = (vx, vy)
            po.body.angle = self.facing_angle + SPRITE_ANGLE_OFFSET
