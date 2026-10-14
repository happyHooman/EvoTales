"""
Base class for moving creatures.

A creature is a body (energy, age, movement, senses) driven by a Brain.
Each frame: age and burn energy, ask the brain for a new Intent every
think_interval seconds, carry out the current Intent, then steer.
"""
import math
import random
from .brain import Brain, Intent, Observation, Percept, SurvivalBrain
from .entity import Entity
from config import CREATURE_DEFAULTS
from sprite_manager import sprite_manager
from sprite_config import SPRITE_ANGLE_OFFSET

TWO_PI = 2 * math.pi


def _angle_toward(current: float, target: float, max_step: float) -> float:
    """Rotate current toward target by at most max_step. Returns new angle."""
    diff = (target - current) % TWO_PI
    if diff > math.pi:
        diff -= TWO_PI
    if abs(diff) <= max_step:
        return target
    return current + math.copysign(max_step, diff)


class Creature(Entity):
    """Base for herbivores, carnivores, smarties. Shared body logic."""

    layer_name: str = ""
    texture_name: str = ""
    config: dict | None = None  # Subclass sets species overrides; merged with CREATURE_DEFAULTS
    brain_class: type[Brain] = SurvivalBrain

    # The actions ("tools") a brain may choose. Each maps to a _do_<name> method.
    ACTIONS = ("wander", "move_to", "eat", "flee", "rest", "reproduce")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.config is not None:
            cls.config = {**CREATURE_DEFAULTS, **cls.config}

    @classmethod
    def spawn(cls, world, x: float | None = None, y: float | None = None, **kwargs):
        """Create and register a creature at (x, y). Defaults to map center."""
        map_w, map_h = world.map_size
        cx = x if x is not None else map_w / 2
        cy = y if y is not None else map_h / 2
        return cls(cx, cy, world, **kwargs)

    @classmethod
    def spawn_initial(cls, world):
        """Spawn initial population on free (non-water) ground."""
        cfg = cls.config
        for _ in range(cfg["initial_count"]):
            pos = world.random_free_position(cfg["bounds_padding"])
            if pos is not None:
                cls.spawn(world, *pos)

    def __init__(self, x, y, world, energy: float | None = None, brain: Brain | None = None):
        texture = sprite_manager.get_texture(self.texture_name)
        super().__init__(texture, x, y, world)
        cfg = self.config
        self.radius = max(self.width, self.height) / 2
        self.energy = cfg["initial_energy"] if energy is None else energy
        self.age = 0.0
        # Stagger timers so a freshly spawned group doesn't act in lockstep
        self.reproduction_timer = cfg["reproduction_cooldown"] * random.uniform(0.5, 1.0)
        self.think_timer = random.uniform(0, cfg["think_interval"])
        self.wander_timer = random.uniform(0, cfg["wander_turn_interval"])
        self.detour_timer = 0.0

        self.heading = random.uniform(0, TWO_PI)
        self.desired_heading = self.heading
        self.speed = 0.0

        self.brain = brain or self.brain_class(cfg["hungry_ratio"])
        self.intent = Intent("wander")

        self._register(physics_params=cfg["physics"])
        self._body = self.scene.physics_engine.get_physics_object(self).body

    # ------------------------------------------------------------------ loop

    def update(self, delta_time: float = 1 / 60):
        if not self.alive:
            return
        cfg = self.config
        self.age += delta_time
        self.reproduction_timer -= delta_time
        self.energy -= (cfg["base_energy_drain"] + cfg["move_energy_factor"] * self.speed * self.speed) * delta_time
        if self.energy <= 0:
            self.die("starved")
            return
        if self.age >= cfg["max_age"]:
            self.die("old age")
            return

        self.think_timer -= delta_time
        if self.think_timer <= 0:
            self.think_timer += cfg["think_interval"]
            self.intent = self.brain.decide(self.observe())
            self._check_walls()
            self._update_tint()

        self.act(self.intent, delta_time)
        self._steer(delta_time)

    # ---------------------------------------------------------------- senses

    def observe(self) -> Observation:
        cfg = self.config
        vision = cfg["vision_range"]
        x, y = self.center_x, self.center_y
        food = []
        for layer in cfg["diet"]:
            # Look close first: in a dense meadow this skips most of the vision area
            for radius in (vision / 3, vision):
                found = [Percept(e, layer, d) for e, d in self.world.nearby(layer, x, y, radius)
                         if e is not self and getattr(e, "edible", True)]
                if found:
                    break
            food.extend(found)
        threats = [Percept(e, layer, d) for layer in cfg["threats"]
                   for e, d in self.world.nearby(layer, x, y, vision)]
        food.sort(key=lambda p: p.distance)
        threats.sort(key=lambda p: p.distance)
        return Observation(
            energy=self.energy,
            energy_ratio=self.energy / cfg["max_energy"],
            age=self.age,
            can_reproduce=self.can_reproduce(),
            food=food[:5],
            threats=threats[:3],
        )

    def can_reproduce(self) -> bool:
        cfg = self.config
        return (
            self.energy >= cfg["reproduction_energy_threshold"]
            and self.reproduction_timer <= 0
            and self.world.population(self.layer_name) < cfg["max_population"]
        )

    # --------------------------------------------------------------- actions

    def act(self, intent: Intent, delta_time: float) -> None:
        if intent.action not in self.ACTIONS:
            raise ValueError(f"Unknown action {intent.action!r}; expected one of {self.ACTIONS}")
        getattr(self, "_do_" + intent.action)(intent.target, delta_time)

    def _do_wander(self, target, delta_time):
        self.speed = self.config["wander_speed"]
        self.wander_timer -= delta_time
        if self.wander_timer <= 0:
            self.wander_timer = self.config["wander_turn_interval"] * random.uniform(0.5, 1.5)
            self.desired_heading = self.heading + random.uniform(-math.pi / 2, math.pi / 2)

    def _do_move_to(self, target, delta_time):
        if not self._valid(target):
            self.intent = Intent("wander")
            return
        self.speed = self.config["wander_speed"]
        self._face(target.center_x, target.center_y)

    def _do_eat(self, target, delta_time):
        if not self._valid(target) or not getattr(target, "edible", True):
            self.intent = Intent("wander")
            return
        cfg = self.config
        reach = self.radius + target.width / 2 + cfg["eat_range"]
        dx = target.center_x - self.center_x
        dy = target.center_y - self.center_y
        if dx * dx + dy * dy <= reach * reach:
            self._consume(target)
            self.intent = Intent("wander")
            return
        is_prey = isinstance(target, Creature)
        self.speed = cfg["run_speed"] if is_prey else (cfg["wander_speed"] + cfg["run_speed"]) / 2
        self._face(target.center_x, target.center_y)

    def _do_flee(self, target, delta_time):
        if not self._valid(target):
            self.intent = Intent("wander")
            return
        self.speed = self.config["run_speed"]
        self._face(2 * self.center_x - target.center_x, 2 * self.center_y - target.center_y)

    def _do_rest(self, target, delta_time):
        self.speed = 0.0

    def _do_reproduce(self, target, delta_time):
        self.intent = Intent("wander")
        if not self.can_reproduce():
            return
        cfg = self.config
        angle = random.uniform(0, TWO_PI)
        dist = self.radius * 3
        x = self.center_x + dist * math.cos(angle)
        y = self.center_y + dist * math.sin(angle)
        if self.world.is_blocked(x, y):
            return
        self.energy -= cfg["energy_cost_reproduction"]
        self.reproduction_timer = cfg["reproduction_cooldown"]
        self.world.record(f"{self.layer_name} born")
        type(self).spawn(self.world, x, y, energy=cfg["child_energy"])

    # --------------------------------------------------------------- helpers

    def _consume(self, target) -> None:
        if isinstance(target, Creature):
            gain = target.config["nutrition"]
            target.die(f"eaten by {self.layer_name}")
        else:
            gain = target.be_eaten()
        self.energy = min(self.config["max_energy"], self.energy + gain)

    def die(self, cause: str) -> None:
        if self.alive:
            self.world.record(f"{self.layer_name} {cause}")
            self.despawn()

    @staticmethod
    def _valid(target) -> bool:
        return target is not None and target.alive

    def _face(self, x: float, y: float) -> None:
        if self.detour_timer <= 0:
            self.desired_heading = math.atan2(y - self.center_y, x - self.center_x)

    def _check_walls(self) -> None:
        """Look ahead along the current heading; pick a free direction if water is in the way."""
        probe = self.radius + self.config["wall_probe_distance"]
        x, y = self.center_x, self.center_y
        if not self.world.is_blocked(x + probe * math.cos(self.heading), y + probe * math.sin(self.heading)):
            return
        for offset in (0.8, -0.8, 1.6, -1.6, 2.4, -2.4, math.pi):
            angle = self.heading + offset
            if not self.world.is_blocked(x + probe * math.cos(angle), y + probe * math.sin(angle)):
                self.desired_heading = angle
                self.detour_timer = 0.8
                return
        self.desired_heading = self.heading + math.pi

    def _steer(self, delta_time: float) -> None:
        if self.detour_timer > 0:
            self.detour_timer -= delta_time
        self.heading = _angle_toward(self.heading, self.desired_heading, self.config["turn_rate"] * delta_time)
        self.heading %= TWO_PI
        self.desired_heading %= TWO_PI
        body = self._body
        body.velocity = (self.speed * math.cos(self.heading), self.speed * math.sin(self.heading))
        body.angle = self.heading + SPRITE_ANGLE_OFFSET

    def _update_tint(self) -> None:
        """Fade toward dark as energy runs low, so hunger is visible."""
        ratio = max(0.0, min(1.0, self.energy / self.config["max_energy"]))
        v = int(110 + 145 * ratio)
        self.color = (v, v, v, 255)
