"""
Clone of pymunk_top_down.py using arcade.Scene instead of SpriteLists.

Proves that Scene and SpriteLists work the same way for physics and drawing.
"""
import math
import random
import arcade
from typing import Optional
from arcade.pymunk_physics_engine import PymunkPhysicsEngine

SCREEN_TITLE = "PyMunk Top-Down (Scene)"
SPRITE_SCALING_PLAYER = 0.5
MOVEMENT_SPEED = 5

SPRITE_IMAGE_SIZE = 128
SPRITE_SIZE = int(SPRITE_IMAGE_SIZE * SPRITE_SCALING_PLAYER)

SCREEN_WIDTH = SPRITE_SIZE * 15
SCREEN_HEIGHT = SPRITE_SIZE * 10

PLAYER_MOVE_FORCE = 4000
BULLET_MOVE_FORCE = 2500


class MyWindow(arcade.Window):
    """ Main Window - uses Scene instead of SpriteLists """
    def __init__(self, width, height, title):
        """ Init """
        super().__init__(width, height, title)

        arcade.set_background_color(arcade.color.AMAZON)

        self.scene = None
        self.player_sprite = None
        self.physics_engine: Optional[PymunkPhysicsEngine] = None

        self.left_pressed = False
        self.right_pressed = False
        self.up_pressed = False
        self.down_pressed = False

    def setup(self):
        """ Set up everything using Scene """
        self.scene = arcade.Scene()

        # Create layers (order = draw order). Walls need spatial_hash for collision.
        self.scene.add_sprite_list("Walls", use_spatial_hash=True)
        self.scene.add_sprite_list("Bullets")
        self.scene.add_sprite_list("Rocks")
        self.scene.add_sprite_list("Gems")

        # Set up the player
        self.player_sprite = arcade.Sprite(
            ":resources:images/animated_characters/female_person/femalePerson_idle.png",
            SPRITE_SCALING_PLAYER
        )
        self.player_sprite.center_x = 250
        self.player_sprite.center_y = 250
        self.scene.add_sprite("Player", self.player_sprite)

        # Set up the walls
        for x in range(0, SCREEN_WIDTH + 1, SPRITE_SIZE):
            wall = arcade.Sprite(":resources:images/tiles/grassCenter.png", SPRITE_SCALING_PLAYER)
            wall.center_x = x
            wall.center_y = 0
            self.scene.add_sprite("Walls", wall)

            wall = arcade.Sprite(":resources:images/tiles/grassCenter.png", SPRITE_SCALING_PLAYER)
            wall.center_x = x
            wall.center_y = SCREEN_HEIGHT
            self.scene.add_sprite("Walls", wall)

        for y in range(SPRITE_SIZE, SCREEN_HEIGHT, SPRITE_SIZE):
            wall = arcade.Sprite(":resources:images/tiles/grassCenter.png", SPRITE_SCALING_PLAYER)
            wall.center_x = 0
            wall.center_y = y
            self.scene.add_sprite("Walls", wall)

            wall = arcade.Sprite(":resources:images/tiles/grassCenter.png", SPRITE_SCALING_PLAYER)
            wall.center_x = SCREEN_WIDTH
            wall.center_y = y
            self.scene.add_sprite("Walls", wall)

        # Add some movable rocks
        for x in range(SPRITE_SIZE * 2, SPRITE_SIZE * 13, SPRITE_SIZE):
            rock = random.randrange(4) + 1
            item = arcade.Sprite(
                f":resources:images/space_shooter/meteorGrey_big{rock}.png",
                SPRITE_SCALING_PLAYER
            )
            item.center_x = x
            item.center_y = 400
            self.scene.add_sprite("Rocks", item)

        # Add some movable coins
        for x in range(SPRITE_SIZE * 2, SPRITE_SIZE * 13, SPRITE_SIZE):
            items = [
                ":resources:images/items/gemBlue.png",
                ":resources:images/items/gemRed.png",
                ":resources:images/items/coinGold.png",
                ":resources:images/items/keyBlue.png",
            ]
            item_name = random.choice(items)
            item = arcade.Sprite(item_name, SPRITE_SCALING_PLAYER)
            item.center_x = x
            item.center_y = 300
            self.scene.add_sprite("Gems", item)

        # --- Pymunk Physics Engine Setup ---
        damping = 0.7
        gravity = (0, 0)
        self.physics_engine = PymunkPhysicsEngine(damping=damping, gravity=gravity)

        def rock_hit_handler(sprite_a, sprite_b, arbiter, space, data):
            bullet_shape = arbiter.shapes[0]
            bullet_sprite = self.physics_engine.get_sprite_for_shape(bullet_shape)
            bullet_sprite.remove_from_sprite_lists()
            print("Rock")

        def wall_hit_handler(sprite_a, sprite_b, arbiter, space, data):
            bullet_shape = arbiter.shapes[0]
            bullet_sprite = self.physics_engine.get_sprite_for_shape(bullet_shape)
            bullet_sprite.remove_from_sprite_lists()
            print("Wall")

        self.physics_engine.add_collision_handler("bullet", "rock", post_handler=rock_hit_handler)
        self.physics_engine.add_collision_handler("bullet", "wall", post_handler=wall_hit_handler)

        # Add the player
        self.physics_engine.add_sprite(
            self.player_sprite,
            friction=0.6,
            moment_of_inertia=PymunkPhysicsEngine.MOMENT_INF,
            damping=0.01,
            collision_type="player",
            max_velocity=400,
        )

        # Add walls, rocks, gems - use scene["LayerName"] to get the SpriteList
        self.physics_engine.add_sprite_list(
            self.scene["Walls"],
            friction=0.6,
            collision_type="wall",
            body_type=PymunkPhysicsEngine.STATIC,
        )
        self.physics_engine.add_sprite_list(
            self.scene["Rocks"],
            mass=2,
            friction=0.8,
            damping=0.1,
            collision_type="rock",
        )
        self.physics_engine.add_sprite_list(
            self.scene["Gems"],
            mass=0.5,
            friction=0.8,
            damping=0.4,
            collision_type="rock",
        )

    def on_mouse_press(self, x, y, button, modifiers):
        """ Called whenever the mouse button is clicked. """
        bullet = arcade.SpriteSolidColor(5, 5, arcade.color.RED)
        bullet.position = self.player_sprite.position

        start_x = self.player_sprite.center_x
        start_y = self.player_sprite.center_y
        x_diff = x - start_x
        y_diff = y - start_y
        angle = math.atan2(y_diff, x_diff)

        force = [math.cos(angle), math.sin(angle)]
        size = max(self.player_sprite.width, self.player_sprite.height) / 2
        bullet.center_x += size * force[0]
        bullet.center_y += size * force[1]

        self.scene.add_sprite("Bullets", bullet)
        self.physics_engine.add_sprite(
            bullet,
            mass=0.1,
            damping=1.0,
            friction=0.6,
            collision_type="bullet",
            elasticity=0.9,
        )

        force[0] *= BULLET_MOVE_FORCE
        force[1] *= BULLET_MOVE_FORCE
        self.physics_engine.apply_force(bullet, force)

    def on_key_press(self, key, modifiers):
        """Called whenever a key is pressed. """
        if key == arcade.key.UP:
            self.up_pressed = True
        elif key == arcade.key.DOWN:
            self.down_pressed = True
        elif key == arcade.key.LEFT:
            self.left_pressed = True
        elif key == arcade.key.RIGHT:
            self.right_pressed = True
        elif key == arcade.key.SPACE:
            bullet = arcade.SpriteSolidColor(9, 9, arcade.color.RED)
            bullet.position = self.player_sprite.position
            bullet.center_x += 30
            self.scene.add_sprite("Bullets", bullet)
            self.physics_engine.add_sprite(
                bullet,
                mass=0.2,
                damping=1.0,
                friction=0.6,
                collision_type="bullet",
            )
            force = (3000, 0)
            self.physics_engine.apply_force(bullet, force)

    def on_key_release(self, key, modifiers):
        """Called when the user releases a key. """
        if key == arcade.key.UP:
            self.up_pressed = False
        elif key == arcade.key.DOWN:
            self.down_pressed = False
        elif key == arcade.key.LEFT:
            self.left_pressed = False
        elif key == arcade.key.RIGHT:
            self.right_pressed = False

    def on_update(self, delta_time):
        """ Movement and game logic """
        self.player_sprite.change_x = 0
        self.player_sprite.change_y = 0

        if self.up_pressed and not self.down_pressed:
            force = (0, PLAYER_MOVE_FORCE)
            self.physics_engine.apply_force(self.player_sprite, force)
        elif self.down_pressed and not self.up_pressed:
            force = (0, -PLAYER_MOVE_FORCE)
            self.physics_engine.apply_force(self.player_sprite, force)
        if self.left_pressed and not self.right_pressed:
            self.player_sprite.change_x = -MOVEMENT_SPEED
            force = (-PLAYER_MOVE_FORCE, 0)
            self.physics_engine.apply_force(self.player_sprite, force)
        elif self.right_pressed and not self.left_pressed:
            force = (PLAYER_MOVE_FORCE, 0)
            self.physics_engine.apply_force(self.player_sprite, force)

        self.physics_engine.step()

    def on_draw(self):
        """ Draw everything - single scene.draw() replaces 5 list draws """
        self.clear()
        self.scene.draw()


def main():
    """ Main function """
    window = MyWindow(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.setup()
    arcade.run()


if __name__ == "__main__":
    main()
