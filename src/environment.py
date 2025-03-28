import os
import platform
import sys
import arcade
from arcade.types import LRBT
from config import *


class EvoTalesWorld(arcade.Window):
    """
    Main application class.
    """
    def __init__(self):
        # Call the parent class and set up the window
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

        # Camera setup
        self.camera = None
        self.gui_camera = None

        # Mouse tracking variables
        self.mouse_pressed = False
        self.last_mouse_position = (0, 0)
        
        # Key tracking for smooth panning
        self.pressed_keys = set()

        # Set the background color
        self.background_color = arcade.color.AMAZON

    def setup(self):
        """Set up the game here. Call this function to restart the game."""
        # Initialize our camera, setting a viewport the size of our window
        self.camera = arcade.Camera2D()

        # Initialize our gui camera, initial settings are the same as our world camera
        self.gui_camera = arcade.Camera2D()

        # Set the camera's viewport to match the window
        self.camera.viewport = self.rect

        # Set the camera's projection to match the window dimensions
        self.camera.projection = LRBT(0, self.width, 0, self.height)

        # Initialize camera position
        self._center_camera()

    def _get_center_position(self, width=None, height=None):
        width = width if width else self.width
        height = height if height else self.height
        center_x = self.camera.position[0] + width / 2
        center_y = self.camera.position[1] + height / 2
        return (center_x, center_y)
    
    def _get_center_from_projection(self):
        width = self.camera.projection.right - self.camera.projection.left
        height = self.camera.projection.top - self.camera.projection.bottom
        return self._get_center_position(width, height)
    
    def _center_camera(self):
        w = self.width
        h = self.height
        self.camera.position = (
            -w / 2,  # Start at negative half width to center the view
            -h / 2   # Start at negative half height to center the view
        )

    def on_resize(self, width: int, height: int):
        # Only proceed if camera is initialized
        if self.camera is None:
            super().on_resize(width, height)
            return

        old_center = self._get_center_from_projection()

        # Update the camera projection and viewport
        self.camera.projection = LRBT(0, width, 0, height)
        self.camera.viewport = self.rect
        
        new_center = self._get_center_position(width, height)
        self.camera.position = (
            self.camera.position[0] + (old_center[0] - new_center[0]),
            self.camera.position[1] + (old_center[1] - new_center[1])
        )
        
        super().on_resize(width, height)

    def on_draw(self):
        """Render the screen."""
        # Clear the screen to the background color
        self.clear()

        # Activate our camera before drawing
        self.camera.use()

        # Draw our game world
        arcade.draw_rect_outline(
            LRBT(0, 400, 0, 300),
            color=arcade.color.WHITE,
            border_width=5,
        )

        # Activate our GUI camera
        self.gui_camera.use()

    def camera_operation(self, key):
        zoom_factor = CAMERA_OPS["ZOOM_FACTOR"]
        old_center = self._get_center_from_projection()
        
        if key == CAMERA_OPS["ZOOM_IN"]:
            self.camera.zoom = self.camera.zoom * zoom_factor
        elif key == CAMERA_OPS["ZOOM_OUT"]:
            self.camera.zoom = self.camera.zoom / zoom_factor
        else:
            raise ValueError(f"Invalid camera operation: {key}")

        # Calculate new center position
        new_center = self._get_center_from_projection()
        self.camera.position = (
            self.camera.position[0] + (old_center[0] - new_center[0]),
            self.camera.position[1] + (old_center[1] - new_center[1])
        )

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.mouse_pressed = True
            self.last_mouse_position = (x, y)

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.mouse_pressed = False

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        # Calculate the movement in world coordinates
        world_dx = dx / self.camera.zoom
        world_dy = dy / self.camera.zoom
        
        # Update camera position
        self.camera.position = (
            self.camera.position[0] - world_dx,
            self.camera.position[1] - world_dy
        )
        
        self.last_mouse_position = (x, y)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if scroll_y > 0:
            self.camera_operation(CAMERA_OPS["ZOOM_IN"])
        elif scroll_y < 0:
            self.camera_operation(CAMERA_OPS["ZOOM_OUT"])

    def on_key_press(self, key, modifiers):
        self.pressed_keys.add(key)
        if key in [arcade.key.X, arcade.key.Z]:
            if key == arcade.key.X:
                self.camera_operation(CAMERA_OPS["ZOOM_IN"])
            elif key == arcade.key.Z:
                self.camera_operation(CAMERA_OPS["ZOOM_OUT"])

    def on_key_release(self, key, modifiers):
        self.pressed_keys.discard(key)

    def on_update(self, delta_time):
        pan_rate = CAMERA_OPS["PAN_RATE"] * delta_time * 60  # Adjust for frame rate
        
        if arcade.key.LEFT in self.pressed_keys:
            self.camera.position = (self.camera.position[0] - pan_rate, self.camera.position[1])
        if arcade.key.RIGHT in self.pressed_keys:
            self.camera.position = (self.camera.position[0] + pan_rate, self.camera.position[1])
        if arcade.key.UP in self.pressed_keys:
            self.camera.position = (self.camera.position[0], self.camera.position[1] + pan_rate)
        if arcade.key.DOWN in self.pressed_keys:
            self.camera.position = (self.camera.position[0], self.camera.position[1] - pan_rate)
    
    def on_close(self):
        # More graceful shutdown sequence
        arcade.close_window()
        if sys.platform == 'darwin' or platform.system() == 'Darwin':
            # Give a small delay before force exit on macOS
            import time
            time.sleep(0.1)
            os._exit(0)


def main():
    """Main function"""
    window = EvoTalesWorld()
    window.setup()  # Make sure to call setup before running
    arcade.run()


if __name__ == "__main__":
    main()

