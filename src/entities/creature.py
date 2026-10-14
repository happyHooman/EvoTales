"""
Base class for moving creatures.

Shared behaviour: spawn, spawn_initial, smooth turning, velocity application.
"""
import math
import random
from .entity import Entity
from sprite_manager import sprite_manager
from sprite_config import SPRITE_ANGLE_OFFSET


def _angle_toward(current: float, target: float, max_step: float) -> float:
    """Rotate current toward target by at most max_step. Returns new angle."""
    diff = (target - current) % (2 * math.pi)
    if diff > math.pi:
        diff -= 2 * math.pi
    if abs(diff) <= max_step:
        return target
    return current + math.copysign(max_step, diff)


class Creature(Entity):
    """Base for herbivores, carnivores, smarties. Shared movement logic."""

    layer_name: str = ""
    texture_name: str = ""
    config: dict | None = None  # Subclass must set

    @classmethod
    def spawn(cls, scene, map_size, x: float | None = None, y: float | None = None):
        """Handler: create and register a creature at (x, y). Defaults to map center."""
        map_w, map_h = map_size
        cx = x if x is not None else map_w / 2
        cy = y if y is not None else map_h / 2
        return cls(cx, cy, scene)

    @classmethod
    def spawn_initial(cls, scene, map_size):
        """Spawn initial population according to config."""
        cfg = cls.config
        padding = cfg.get("bounds_padding", 20)
        map_w, map_h = map_size
        for _ in range(cfg["initial_count"]):
            x = random.uniform(padding, map_w - padding)
            y = random.uniform(padding, map_h - padding)
            cls.spawn(scene, map_size, x, y)

    def __init__(self, x, y, scene):
        texture = sprite_manager.get_texture(self.texture_name)
        super().__init__(texture, x, y)
        self.scene = scene
        self.config = self.__class__.config
        self.facing_angle = random.uniform(0, 2 * math.pi)
        self.target_angle = self.facing_angle
        self.turn_timer = self.config.get("turn_interval", 5.0)
        self._register(physics_params=self.config.get("physics", {}))

    def update(self, delta_time: float = 1 / 60):
        """Smooth turning toward target, then apply velocity."""
        self.turn_timer -= delta_time
        if self.turn_timer <= 0:
            self.target_angle = random.uniform(0, 2 * math.pi)
            self.turn_timer = self.config.get("turn_interval", 5.0)

        turn_rate = self.config.get("turn_rate", 2.0)
        max_turn = turn_rate * delta_time
        self.facing_angle = _angle_toward(self.facing_angle, self.target_angle, max_turn)

        speed = self.config.get("speed", 20)
        vx = speed * math.cos(self.facing_angle)
        vy = speed * math.sin(self.facing_angle)

        physics = self.scene.physics_engine
        po = physics.get_physics_object(self)
        if po:
            po.body.velocity = (vx, vy)
            po.body.angle = self.facing_angle + SPRITE_ANGLE_OFFSET
