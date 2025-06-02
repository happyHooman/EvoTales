import os
import platform
import sys
import arcade
from config import *
from simulation.camera_controller import CameraController
from typing import Optional
from entities import EntityManager

TILE_SCALING = 1.0
DEFAULT_DAMPING = .6

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
        self.pressed_keys = set()
        self.camera_controller = CameraController(CAMERA_SETTINGS, self)
        self.background_color = arcade.color.AMAZON
        self.entity_manager: Optional[EntityManager] = None

    def setup(self):
        """Set up the game environment. Call this function to restart the game."""
        self.entity_manager = EntityManager()
        map_width, map_height = self.entity_manager.get_map_size()
        self.camera_controller.setup(map_width, map_height)
        self.entity_manager.generate_initial_population()

    def on_resize(self, width: int, height: int):
        """Handle window resizing events."""
        super().on_resize(width, height)
        self.camera_controller.handle_resize(width, height)

    def on_draw(self):
        """Render the screen."""
        self.clear()
        self.camera_controller.camera.use()
        self.entity_manager.scene.draw()

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
        # Regular game keys
        if key == arcade.key.X:
            self.camera_controller.apply_zoom("in")
        elif key == arcade.key.Z:
            self.camera_controller.apply_zoom("out")

    def on_key_release(self, key, modifiers):
        """Handle key release events."""
        self.pressed_keys.discard(key)

    def on_update(self, delta_time):
        """Update game logic."""
        self.camera_controller.update_panning(self.pressed_keys, delta_time)
        self.entity_manager.update(delta_time)

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
