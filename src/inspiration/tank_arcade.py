"""
Arcade port of the Chipmunk tank demo.

Same physics as tank.py (pymunk) but uses Arcade for display and input.
Drive the tank towards the mouse cursor.
"""

import random

import arcade
import pymunk
from pymunk.space_debug_draw_options import SpaceDebugColor, SpaceDebugDrawOptions
from pymunk.vec2d import Vec2d

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
FPS = 60
TANK_STOP_DISTANCE_SQ = 30**2  # Stop when within 30px of target

# Module-level refs for update (matches original tank.py structure)
tank_body = None
tank_control_body = None

# Pymunk uses y-down (pygame-style). Arcade uses y-up. Flip y when drawing/input.


class ArcadeDrawOptions(SpaceDebugDrawOptions):
    """Draw pymunk space using Arcade primitives. Converts y-down to y-up inline."""

    def __init__(self, height: int):
        super().__init__()
        self.height = height

    def draw_circle(
        self,
        pos: Vec2d,
        angle: float,
        radius: float,
        outline_color: SpaceDebugColor,
        fill_color: SpaceDebugColor,
    ) -> None:
        x, y = pos.x, self.height - pos.y
        arcade.draw_circle_filled(x, y, radius, fill_color.as_int())
        arcade.draw_circle_outline(x, y, radius, outline_color.as_int(), 1)

    def draw_segment(self, a: Vec2d, b: Vec2d, color: SpaceDebugColor) -> None:
        arcade.draw_line(
            a.x, self.height - a.y,
            b.x, self.height - b.y,
            color.as_int(), 2
        )

    def draw_fat_segment(
        self,
        a: tuple,
        b: tuple,
        radius: float,
        outline_color: SpaceDebugColor,
        fill_color: SpaceDebugColor,
    ) -> None:
        ax, ay = a[0], self.height - a[1]
        bx, by = b[0], self.height - b[1]
        arcade.draw_line(ax, ay, bx, by, fill_color.as_int(), max(2, int(radius * 2)))

    def draw_polygon(
        self,
        verts,
        radius: float,
        outline_color: SpaceDebugColor,
        fill_color: SpaceDebugColor,
    ) -> None:
        points = [
            (v.x, self.height - v.y) if hasattr(v, "x") else (v[0], self.height - v[1])
            for v in verts
        ]
        arcade.draw_polygon_filled(points, fill_color.as_int())
        oc = outline_color.as_int()
        for i in range(len(points)):
            ax, ay = points[i]
            bx, by = points[(i + 1) % len(points)]
            arcade.draw_line(ax, ay, bx, by, oc, 1)

    def draw_dot(self, size: float, pos: Vec2d, color: SpaceDebugColor) -> None:
        arcade.draw_circle_filled(pos.x, self.height - pos.y, size, color.as_int())


def update(space: pymunk.Space, dt: float, mouse_pos_pymunk: Vec2d) -> None:
    global tank_body, tank_control_body

    mouse_delta = mouse_pos_pymunk - tank_body.position
    turn = tank_body.rotation_vector.cpvunrotate(mouse_delta).angle
    tank_control_body.angle = tank_body.angle - turn

    if (mouse_pos_pymunk - tank_body.position).get_length_sqrd() < TANK_STOP_DISTANCE_SQ:
        tank_control_body.velocity = 0, 0
    else:
        if mouse_delta.dot(tank_body.rotation_vector) > 0.0:
            direction = 1.0
        else:
            direction = -1.0
        dv = Vec2d(30.0 * direction, 0.0)
        tank_control_body.velocity = tank_body.rotation_vector.cpvrotate(dv)

    space.step(dt)


def add_box(space: pymunk.Space, size: float, mass: float) -> pymunk.Body:
    radius = Vec2d(size, size).length

    body = pymunk.Body()
    space.add(body)

    body.position = Vec2d(
        random.random() * (SCREEN_WIDTH - 2 * radius) + radius,
        random.random() * (SCREEN_HEIGHT - 2 * radius) + radius,
    )

    shape = pymunk.Poly.create_box(body, (size, size), 0.0)
    shape.mass = mass
    shape.friction = 0.7
    space.add(shape)

    return body


def init_space() -> pymunk.Space:
    global tank_body, tank_control_body

    space = pymunk.Space()
    space.iterations = 10
    space.sleep_time_threshold = 0.5

    static_body = space.static_body

    for (a, b) in [
        ((1, 1), (1, SCREEN_HEIGHT)),
        ((SCREEN_WIDTH, 1), (SCREEN_WIDTH, SCREEN_HEIGHT)),
        ((1, 1), (SCREEN_WIDTH, 1)),
        ((1, SCREEN_HEIGHT), (SCREEN_WIDTH, SCREEN_HEIGHT)),
    ]:
        shape = pymunk.Segment(static_body, a, b, 1.0)
        space.add(shape)
        shape.elasticity = 1
        shape.friction = 1

    for _ in range(50):
        body = add_box(space, 20, 1)
        pivot = pymunk.PivotJoint(static_body, body, (0, 0), (0, 0))
        space.add(pivot)
        pivot.max_bias = 0
        pivot.max_force = 1000

        gear = pymunk.GearJoint(static_body, body, 0.0, 1.0)
        space.add(gear)
        gear.max_bias = 0
        gear.max_force = 5000

    tank_control_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    tank_control_body.position = SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2
    space.add(tank_control_body)

    tank_body = add_box(space, 30, 10)
    tank_body.position = SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2
    for s in tank_body.shapes:
        s.color = (0, 255, 100, 255)

    pivot = pymunk.PivotJoint(tank_control_body, tank_body, (0, 0), (0, 0))
    space.add(pivot)
    pivot.max_bias = 0
    pivot.max_force = 10000

    gear = pymunk.GearJoint(tank_control_body, tank_body, 0.0, 1.0)
    space.add(gear)
    gear.error_bias = 0
    gear.max_bias = 1.2
    gear.max_force = 50000

    return space


class TankWindow(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, "Tank (Arcade)")
        arcade.set_background_color(arcade.color.BLACK)
        self.space = init_space()
        self.draw_options = ArcadeDrawOptions(SCREEN_HEIGHT)
        self.draw_options.flags = (
            SpaceDebugDrawOptions.DRAW_SHAPES | SpaceDebugDrawOptions.DRAW_CONSTRAINTS
        )
        self.mouse_x = SCREEN_WIDTH / 2
        self.mouse_y = SCREEN_HEIGHT / 2

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        self.mouse_x = x
        self.mouse_y = y

    def on_draw(self):
        self.clear()
        self.space.debug_draw(self.draw_options)

        arcade.draw_text(
            "Use the mouse to drive the tank, it will follow the cursor.",
            15, SCREEN_HEIGHT - 25,
            arcade.color.WHITE, 14,
        )

    def on_update(self, delta_time: float):
        mouse_pos_pymunk = Vec2d(self.mouse_x, SCREEN_HEIGHT - self.mouse_y)
        update(self.space, 1 / FPS, mouse_pos_pymunk)

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.ESCAPE, arcade.key.Q):
            arcade.close_window()


def main():
    window = TankWindow()
    arcade.run()


if __name__ == "__main__":
    main()
