import os
import platform
import sys
import arcade
from config import *
from simulation.camera_controller import CameraController
from arcade.types.rect import Rect, LRBT, LBWH
from sprite_manager import SpriteManager

TILE_SCALING = 1.0
SPRITE_DEBUG = False

class SimulationWindow(arcade.Window):
    """
    Main application class for the simulation.
    """

    def __init__(self):
        # Initialize the parent class with window properties
        super().__init__(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            SCREEN_TITLE,
            resizable=True,
            vsync=True,
            antialiasing=True
        )
        self.set_exclusive_keyboard(False)
        self.set_minimum_size(400, 300)

        # Initialize the CameraController
        self.camera_controller = CameraController(CAMERA_SETTINGS, self)

        # Initialize the SpriteManager and load all sprite sheets
        self.sprite_manager = SpriteManager()
        self.sprite_manager.load_all_sprite_sheets()
        
        # Key tracking for smooth panning
        self.pressed_keys = set()

        # Set the background color
        self.background_color = arcade.color.AMAZON

        # Tile map and scene setup
        self.tile_map = None
        self.scene = None
        self.plant_list = None

    def setup(self):
        """Set up the game environment. Call this function to restart the game."""
        layer_options = {
            "ground": {
                "use_spatial_hash": True
            }
        }
        self.tile_map = arcade.load_tilemap(
            "assets/maps/uniform_map.json",
            scaling=TILE_SCALING,
            layer_options=layer_options
        )
        map_width = self.tile_map.width * self.tile_map.tile_width
        map_height = self.tile_map.height * self.tile_map.tile_height
        self.camera_controller.setup(map_width, map_height)
        
        # Create the scene
        self.scene = arcade.Scene.from_tilemap(self.tile_map)
        
        # Add a plant layer
        self.plant_list = arcade.SpriteList()
        self.scene.add_sprite_list("plants", self.plant_list)

        # Create and add a single plant using the sprite manager
        plant = self.sprite_manager.create_sprite("smartie")
        plant.center_x = map_width / 2
        plant.center_y = map_height / 2
        
        # Add directly to scene instead of through plant_list
        self.scene.add_sprite("plants", plant)
        # Also add to our reference for easy access
        self.plant_list.append(plant)

    def on_resize(self, width: int, height: int):
        """Handle window resizing events."""
        super().on_resize(width, height)
        self.camera_controller.handle_resize(width, height)

    def on_draw(self):
        """Render the screen."""
        self.clear()
        self.camera_controller.camera.use()
        self.scene.draw()

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        """Handle mouse drag events for camera panning."""
        self.camera_controller.handle_drag(dx, dy)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        """Handle mouse scroll events for zooming."""
        if scroll_y > 0:
            self.camera_controller.apply_zoom("in")
        elif scroll_y < 0:
            self.camera_controller.apply_zoom("out")

    def on_key_press(self, key, modifiers):
        """Handle key press events."""
        self.pressed_keys.add(key)
        if key == arcade.key.X:
            self.camera_controller.apply_zoom("in")
        elif key == arcade.key.Z:
            self.camera_controller.apply_zoom("out")
        
        if SPRITE_DEBUG:
            self.sprite_adjust(key, modifiers)
        

    def sprite_adjust(self, key, modifiers):
        """
        Adjust the sprite position based on the key pressed. You have to select or define a sprite first
        """
        # TODO: fix this function
        if key in self.sprite_manager.handler_keys:
            if self.plant_list:
                plant = self.plant_list[0]  
                direction = chr(key).lower()
                # For now, assume we're adjusting the smartie sprite
                sprite_name = "smartie"
                if self.sprite_manager.adjust_sprite_position_by_name(sprite_name, direction):
                    # Update the plant's texture with the new position
                    new_texture = self.sprite_manager.get_sprite_texture(
                        self.sprite_manager.find_sprite_sheet(sprite_name), 
                        sprite_name
                    )
                    if new_texture:
                        plant.texture = new_texture

    def on_key_release(self, key, modifiers):
        """Handle key release events."""
        self.pressed_keys.discard(key)

    def on_update(self, delta_time):
        """Update game logic."""
        self.camera_controller.update_panning(self.pressed_keys, delta_time)

    def on_close(self):
        """Handle window close events for a graceful shutdown."""
        arcade.close_window()
        if sys.platform == 'darwin' or platform.system() == 'Darwin':
            import time
            time.sleep(0.1)
            os._exit(0)

def main():
    """Main function to run the simulation."""
    window = SimulationWindow()
    window.setup()
    arcade.run()

if __name__ == "__main__":
    main()
