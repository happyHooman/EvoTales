"""
Base class for moving creatures.

A creature is a body (energy, movement, senses) driven by a Brain. Each frame
it pays its energy costs, asks the brain for a new Intent every
think_interval seconds, carries out the current Intent, then steers.
When it dies it stays on the map as a corpse for a while, so predators can
still eat it, then vanishes.
"""
import math
import random
from .brain import Brain, Instinct, Intent, Observation, Percept
from .entity import Entity
from config import CREATURE_DEFAULTS
from sprite_manager import sprite_manager
from sprite_config import SPRITE_ANGLE_OFFSET

TWO_PI = 2 * math.pi
HALF_PI = math.pi / 2
# Escape directions tried when fleeing, as offsets from "straight away from the
# predators". Never beyond 90 degrees, so a fleeing creature never turns toward them.
FLEE_OFFSETS = [0.0] + [sign * step * math.pi / 12 for step in range(1, 7) for sign in (1, -1)]
CORPSE_COLOR = (80, 80, 80, 200)


def _angle_toward(current: float, target: float, max_step: float) -> float:
    """Rotate current toward target by at most max_step. Returns new angle."""
    diff = (target - current) % TWO_PI
    if diff > math.pi:
        diff -= TWO_PI
    if abs(diff) <= max_step:
        return target
    return current + math.copysign(max_step, diff)


class Creature(Entity):
    """Base for herbivores, smarties (omnivores) and carnivores. Shared body logic."""

    layer_name: str = ""
    texture_name: str = ""
    config: dict | None = None  # Subclass sets species overrides; merged with CREATURE_DEFAULTS
    can_have_brain: bool = False  # Only smarties may think beyond their instincts

    # The actions ("tools") a brain may choose. Each maps to a _do_<name> method.
    ACTIONS = ("wander", "relax", "eat", "flee", "reproduce")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.config is not None:
            merged = {**CREATURE_DEFAULTS, **cls.config}
            # Update in place so other modules holding the species dict see the full config
            cls.config.clear()
            cls.config.update(merged)

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
        for _ in range(int(cfg["initial_count"])):
            pos = world.random_free_position(cfg["bounds_padding"])
            if pos is not None:
                creature = cls.spawn(world, *pos)
                # Stagger the first births so the founders don't all reproduce at once
                creature.reproduction_timer *= random.uniform(0.3, 1.0)

    def __init__(self, x, y, world, brain: Brain | None = None):
        if brain is not None and not self.can_have_brain:
            raise ValueError(f"{type(self).__name__} runs on instinct only")
        texture = sprite_manager.get_texture(self.texture_name)
        super().__init__(texture, x, y, world)
        cfg = self.config
        self.radius = max(self.width, self.height) / 2
        self.energy = cfg["birth_energy"]
        self.foraging = True
        self.reproduction_timer = cfg["reproduction_interval"]
        self.think_timer = random.uniform(0, cfg["think_interval"])
        self.wander_timer = random.uniform(0, cfg["wander_turn_interval"])
        self.detour_timer = 0.0
        self.corpse_timer = 0.0
        self.bold = False  # hunger currently outweighs fear of predators
        self.boldness_timer = 0.0

        self.heading = random.uniform(0, TWO_PI)
        self.desired_heading = self.heading
        self.speed = 0.0
        self.running = False
        self.relaxing = False
        self.target = None  # food currently being approached
        self.avoid_offset = 0.0  # heading tweak to pass a creature we'd otherwise bump into
        self.flee_away = None    # straight-away heading while fleeing; dodges never cross 90 deg from it

        self.brain = brain or Instinct()
        self.intent = Intent("wander")

        self._register(physics_params=cfg["physics"])
        self._body = self.scene.physics_engine.get_physics_object(self).body
        self.world.on_birth(self)

    # ------------------------------------------------------------------ loop

    def update(self, delta_time: float = 1 / 60):
        if not self.alive:
            if not self.removed:
                self.corpse_timer -= delta_time
                if self.corpse_timer <= 0:
                    self.despawn()
            return

        cfg = self.config
        self.reproduction_timer -= delta_time
        self.energy -= self.energy_rate() * delta_time
        if self.energy <= 0:
            self.die("starved")
            return
        ratio = self.energy / cfg["max_energy"]
        if ratio < cfg["hungry_ratio"]:
            self.foraging = True
        elif ratio >= cfg["full_ratio"]:
            self.foraging = False
        self.boldness_timer -= delta_time
        if self.boldness_timer <= 0:
            self.boldness_timer = cfg["boldness_interval"]
            self.bold = self.foraging and random.random() < self.boldness_chance()

        self.think_timer -= delta_time
        if self.think_timer <= 0:
            self.think_timer += cfg["think_interval"]
            self.intent = self.brain.decide(self.observe())
            if self.intent.action != "flee":
                self._check_walls()
            self._plan_avoidance()

        self.act(self.intent, delta_time)
        self._steer(delta_time)

    def boldness_chance(self) -> float:
        """Chance that hunger beats fear: 0 at the hungry threshold, hunger_boldness when empty."""
        cfg = self.config
        hunger = 1 - self.energy / (cfg["max_energy"] * cfg["hungry_ratio"])
        return cfg["hunger_boldness"] * max(0.0, min(1.0, hunger))

    def energy_rate(self) -> float:
        """Energy spent per second: being alive, plus moving (relaxing moves for free)."""
        cfg = self.config
        rate = cfg["alive_energy_cost"]
        if self.speed > 0 and not self.relaxing:
            # cost = walk_cost * (speed / walk_speed) ^ k, with k chosen so that running at
            # run_speed_multiplier x walk speed costs run_energy_multiplier x walk energy
            k = math.log(cfg["run_energy_multiplier"]) / math.log(cfg["run_speed_multiplier"])
            rate += cfg["walk_energy_cost"] * (self.speed / cfg["walk_speed"]) ** k
        return rate

    # ---------------------------------------------------------------- senses

    @property
    def is_moving(self) -> bool:
        """Walking or running (a relaxing drift doesn't count)."""
        return self.alive and self.speed > self.config["walk_speed"] * self.config["relax_speed_ratio"] * 1.01

    def observe(self) -> Observation:
        cfg = self.config
        vision = cfg["vision_range"]
        x, y = self.center_x, self.center_y
        world = self.world

        food: list[Percept] = []
        for layer in cfg["diet"]:
            # Look close first: in a dense meadow this skips most of the vision area
            for radius in (vision / 3, vision):
                found = [Percept(e, layer, d, is_corpse=not e.alive)
                         for e, d in world.nearby(layer, x, y, radius, include_corpses=True)
                         if e is not self and getattr(e, "edible", True) and not self._claimed_by_other(e)]
                if found:
                    break
            food.extend(found)
        # Keep the current target in view even if closer food turned up nearby
        target = self.target
        if target is not None and not target.removed and all(p.entity is not target for p in food):
            d = math.hypot(target.center_x - x, target.center_y - y)
            if d <= vision and getattr(target, "edible", True):
                food.append(Percept(target, target.layer_name, d, is_corpse=not target.alive))
        food.sort(key=lambda p: p.distance)

        threats = [Percept(e, layer, d, running=e.running, attacking=e.target is self)
                   for layer in world.predators_of(self.layer_name)
                   for e, d in world.nearby(layer, x, y, vision)]
        threats.sort(key=lambda p: p.distance)

        ratio = self.energy / cfg["max_energy"]
        return Observation(
            energy=self.energy,
            energy_ratio=ratio,
            foraging=self.foraging,
            bold=self.bold,
            relaxed=not self.foraging and ratio >= cfg["relaxed_ratio"],
            can_reproduce=self.can_reproduce(),
            current_target=self.target,
            food=food[:5],
            threats=threats[:3],
        )

    def can_reproduce(self) -> bool:
        cfg = self.config
        return (
            self.energy >= cfg["reproduction_energy_threshold"]
            and self.energy > cfg["reproduction_energy_cost"]
            and self.reproduction_timer <= 0
            and self.world.population(self.layer_name) < cfg["max_population"]
        )

    # --------------------------------------------------------------- actions

    def act(self, intent: Intent, delta_time: float) -> None:
        if intent.action not in self.ACTIONS:
            raise ValueError(f"Unknown action {intent.action!r}; expected one of {self.ACTIONS}")
        getattr(self, "_do_" + intent.action)(intent, delta_time)

    def _set_gait(self, run: bool = False, relax: bool = False) -> None:
        cfg = self.config
        self.running = run
        self.relaxing = relax
        if run:
            self.speed = cfg["walk_speed"] * cfg["run_speed_multiplier"]
        elif relax:
            self.speed = cfg["walk_speed"] * cfg["relax_speed_ratio"]
        else:
            self.speed = cfg["walk_speed"]

    def _roam(self, delta_time) -> None:
        self.target = None
        self.wander_timer -= delta_time
        if self.wander_timer <= 0:
            self.wander_timer = self.config["wander_turn_interval"] * random.uniform(0.5, 1.5)
            self.desired_heading = self.heading + random.uniform(-HALF_PI, HALF_PI)

    def _do_wander(self, intent, delta_time):
        self._set_gait()
        self._roam(delta_time)

    def _do_relax(self, intent, delta_time):
        self._set_gait(relax=True)
        self._roam(delta_time)

    def _do_eat(self, intent, delta_time):
        target = intent.target
        if target is None or target.removed or not getattr(target, "edible", True):
            self.target = None
            self.intent = Intent("wander")
            return
        self.target = target
        if not (isinstance(target, Creature) and target.alive):
            target.claimed_by = self  # still food (plant, corpse): others look elsewhere
        reach = self.radius + target.width / 2 + self.config["eat_range"]
        dx = target.center_x - self.center_x
        dy = target.center_y - self.center_y
        if dx * dx + dy * dy <= reach * reach:
            self._consume(target)
            self.target = None
            self.intent = Intent("wander")
            return
        self._set_gait(run=intent.run)
        self._face(target.center_x, target.center_y)

    def _do_flee(self, intent, delta_time):
        threats = [t for t in intent.target if t.alive]
        if not threats:
            self.intent = Intent("wander")
            return
        self.target = None
        self._set_gait(run=intent.run)
        # Away from all visible predators, closer ones weighing more
        x, y = self.center_x, self.center_y
        ax = ay = 0.0
        for t in threats:
            dx, dy = x - t.center_x, y - t.center_y
            d2 = max(dx * dx + dy * dy, 1.0)
            ax += dx / d2
            ay += dy / d2
        away = math.atan2(ay, ax)
        self.flee_away = away
        self.detour_timer = 0.0
        heading = self._free_heading(away, FLEE_OFFSETS)
        self.desired_heading = away if heading is None else heading

    def _do_reproduce(self, intent, delta_time):
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
        self.energy -= cfg["reproduction_energy_cost"]
        self.reproduction_timer = cfg["reproduction_interval"]
        self.world.record(f"{self.layer_name} born")
        type(self).spawn(self.world, x, y)

    # ------------------------------------------------------------ life/death

    def _consume(self, target) -> None:
        if isinstance(target, Creature):
            gain = target.config["nutrition"]
            if target.alive:
                target.die(f"eaten by {self.layer_name}", leave_corpse=False)
            else:
                self.world.record(f"{target.layer_name} corpses eaten")
                target.despawn()
        else:
            gain = target.be_eaten()
        self.energy = min(self.config["max_energy"], self.energy + gain)

    def die(self, cause: str, leave_corpse: bool = True) -> None:
        if not self.alive:
            return
        self.world.record(f"{self.layer_name} {cause}")
        self.world.on_death(self)
        self.alive = False
        self.speed = 0.0
        self.running = self.relaxing = False
        self.target = None
        if not leave_corpse:
            self.despawn()
            return
        # Corpse: stays visible and edible, but no longer a physical obstacle
        for engine in list(self.physics_engines):
            engine.remove_sprite(self)
            self.physics_engines.remove(engine)
        self.corpse_timer = self.config["corpse_duration"]
        self.color = CORPSE_COLOR

    # --------------------------------------------------------------- helpers

    def _claimed_by_other(self, food) -> bool:
        """Plants and corpses another creature is already walking to are left to it."""
        other = getattr(food, "claimed_by", None)
        return other is not None and other is not self and other.alive and other.target is food

    def _face(self, x: float, y: float) -> None:
        if self.detour_timer <= 0:
            self.desired_heading = math.atan2(y - self.center_y, x - self.center_x)

    def _is_path_free(self, angle: float) -> bool:
        probe = self.radius + self.config["wall_probe_distance"]
        x, y = self.center_x, self.center_y
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        return not (self.world.is_blocked(x + probe * cos_a, y + probe * sin_a)
                    or self.world.is_blocked(x + 2 * probe * cos_a, y + 2 * probe * sin_a))

    def _free_heading(self, base: float, offsets) -> float | None:
        for offset in offsets:
            if self._is_path_free(base + offset):
                return base + offset
        return None

    def _check_walls(self) -> None:
        """Look ahead along the current heading; pick a free direction if water is in the way."""
        if self._is_path_free(self.heading):
            return
        angle = self._free_heading(self.heading, (0.8, -0.8, 1.6, -1.6, 2.4, -2.4, math.pi))
        self.desired_heading = angle if angle is not None else self.heading + math.pi
        self.detour_timer = 0.8

    def _steer(self, delta_time: float) -> None:
        if self.detour_timer > 0:
            self.detour_timer -= delta_time
        goal = self.desired_heading + self.avoid_offset
        if self.intent.action == "flee" and self.flee_away is not None:
            # A dodge while fleeing must never point back toward the predators
            off = (goal - self.flee_away + math.pi) % TWO_PI - math.pi
            goal = self.flee_away + max(-HALF_PI, min(HALF_PI, off))
        self.heading = _angle_toward(self.heading, goal, self.config["turn_rate"] * delta_time)
        self.heading %= TWO_PI
        self.desired_heading %= TWO_PI
        body = self._body
        body.velocity = (self.speed * math.cos(self.heading), self.speed * math.sin(self.heading))
        body.angle = self.heading + SPRITE_ANGLE_OFFSET

    def _plan_avoidance(self) -> None:
        """
        Trail planning: predict where nearby creatures will be over the next
        avoid_horizon seconds (constant velocity) and, if we'd touch one, veer to
        the side it isn't on. The soonest predicted contact wins. Chases are left
        alone: a hunter doesn't dodge its prey, and prey doesn't dodge its hunter.
        """
        self.avoid_offset = 0.0
        cfg = self.config
        horizon = cfg["avoid_horizon"]
        if horizon <= 0 or self.speed <= 0:
            return
        x, y = self.center_x, self.center_y
        vx, vy = self.speed * math.cos(self.heading), self.speed * math.sin(self.heading)
        look = horizon * (self.speed + 70) + 2 * self.radius
        soonest = horizon
        hit = None
        for layer in self.world.creature_layers:
            for other, _ in self.world.nearby(layer, x, y, look):
                if other is self or other is self.target or other.target is self:
                    continue
                ox, oy = other.center_x - x, other.center_y - y
                ovx = other.speed * math.cos(other.heading) - vx
                ovy = other.speed * math.sin(other.heading) - vy
                closing = ovx * ovx + ovy * ovy
                if closing < 1e-6:
                    continue
                t = -(ox * ovx + oy * ovy) / closing  # time of closest approach
                if t <= 0 or t >= soonest:
                    continue
                cx, cy = ox + ovx * t, oy + ovy * t      # where it will be relative to us
                clearance = self.radius + other.radius + cfg["avoid_margin"]
                if cx * cx + cy * cy < clearance * clearance:
                    soonest, hit = t, (cx, cy)
        if hit is None:
            return
        # Which side of our path will it be on? Turn the other way (head-on: pass on the right).
        side = math.cos(self.heading) * hit[1] - math.sin(self.heading) * hit[0]
        urgency = 1 - soonest / horizon
        self.avoid_offset = -math.copysign(cfg["avoid_turn"] * (0.4 + 0.6 * urgency), side or 1.0)
