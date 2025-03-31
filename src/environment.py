import os
import platform
import sys
import arcade
from arcade.types import LRBT
from config import *

TILE_SCALING = 1.0

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

        self.tile_map = None
        self.map_bounds = None  # Will store (left, bottom, right, top)
        self.padding = 20.0  # Pixels of padding allowed outside map bounds

        # Camera zoom limits
        self.max_zoom = CAMERA_SETTINGS["MAX_ZOOM"]  # Maximum zoom in (400% of original size)
        self.min_zoom = CAMERA_SETTINGS["MIN_ZOOM"] # Default minimum zoom, will be calculated dynamically

    def setup(self):
        """Set up the game here. Call this function to restart the game."""

        # Load the tile map
        layer_options = {
            "ground": {
                "use_spatial_hash": True
            }
        }

        # Load our TileMap
        self.tile_map = arcade.load_tilemap(
            "assets/maps/uniform_map.json",
            scaling=TILE_SCALING,  # Adjust this value based on your tile size
            layer_options=layer_options
        )

        # Calculate map bounds (world coordinates)
        map_width = self.tile_map.width * self.tile_map.tile_width
        map_height = self.tile_map.height * self.tile_map.tile_height
        self.map_bounds = (0.0, 0.0, float(map_width), float(map_height)) # Use floats
        self.padding = 20.0  # Pixels of padding allowed outside map bounds

        self.scene = arcade.Scene.from_tilemap(self.tile_map)
        # Calculate initial minimum zoom based on map, padding and screen size
        self.update_min_zoom()
        self.camera = arcade.Camera2D()
        self.gui_camera = arcade.Camera2D()
        self.center_camera_on_map()

    def update_min_zoom(self):
        """Calculate minimum zoom to fit map + padding."""
        if self.map_bounds is None:
            self.min_zoom = CAMERA_SETTINGS["MIN_ZOOM"] # Fallback
            return

        map_width = self.map_bounds[2] - self.map_bounds[0]
        map_height = self.map_bounds[3] - self.map_bounds[1]

        # Calculate required world dimensions to show map + padding
        required_world_width = map_width + 2 * self.padding
        required_world_height = map_height + 2 * self.padding

        # Prevent division by zero or negative values
        if required_world_width <= 0 or required_world_height <= 0:
             self.min_zoom = CAMERA_SETTINGS["MIN_ZOOM"] # Fallback
             return

        # Calculate zoom needed to fit width and height
        zoom_for_width = self.width / required_world_width
        zoom_for_height = self.height / required_world_height

        # Minimum zoom is the smaller of the two, ensures both fit
        self.min_zoom = min(zoom_for_width, zoom_for_height)

        # Ensure min_zoom is not excessively small or zero/negative
        self.min_zoom = max(self.min_zoom, CAMERA_SETTINGS["MIN_ZOOM"]) # Absolute minimum zoom floor

    def center_camera_on_map(self):
        """Center the camera's view on the map center."""
        if self.map_bounds is None:
            return

        map_center_x = (self.map_bounds[0] + self.map_bounds[2]) / 2
        map_center_y = (self.map_bounds[1] + self.map_bounds[3]) / 2
        self.camera.position = (map_center_x, map_center_y)

    def clamp_camera_position(self, x=None, y=None):
        x = x or self.camera.position[0]
        y = y or self.camera.position[1]
        if not self.map_bounds:
            return x, y

        # Calculate visible area based on projection
        proj = self.camera.projection
        visible_width = proj.right - proj.left
        visible_height = proj.top - proj.bottom

        # Map boundaries with padding
        map_left = self.map_bounds[0] - self.padding
        map_right = self.map_bounds[2] + self.padding
        map_bottom = self.map_bounds[1] - self.padding
        map_top = self.map_bounds[3] + self.padding

        # Calculate clamping boundaries for centered camera
        min_x = map_left + visible_width / 2
        max_x = map_right - visible_width / 2
        min_y = map_bottom + visible_height / 2
        max_y = map_top - visible_height / 2

        # Handle map smaller than viewport
        if visible_width > (map_right - map_left):
            x = (map_left + map_right) / 2
        else:
            x = max(min_x, min(x, max_x))

        if visible_height > (map_top - map_bottom):
            y = (map_bottom + map_top) / 2
        else:
            y = max(min_y, min(y, max_y))

        self.camera.position = (x, y)

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        if not self.camera:
            return

        # Update minimum zoom based on new window size
        self.update_min_zoom()
        self.camera.zoom = max(self.camera.zoom, self.min_zoom)

        h_w = width / 2 / self.camera.zoom # half width
        h_h = height / 2 / self.camera.zoom # half height
        self.camera.viewport = self.rect
        self.camera.projection = LRBT(-h_w, h_w, -h_h, h_h)
        self.clamp_camera_position()

    def on_draw(self):
        """Render the screen."""
        self.clear()
        self.camera.use()
        self.scene.draw()
        # Activate our GUI camera if you have GUI elements
        # self.gui_camera.use()
        # Draw GUI elements here

    def zoom(self, key):
        """Handle zoom operations."""
        zoom_factor = CAMERA_SETTINGS["ZOOM_FACTOR"]
        if key == CAMERA_SETTINGS["ZOOM_IN"]:
            self.camera.zoom = min(self.camera.zoom * zoom_factor, self.max_zoom)
        elif key == CAMERA_SETTINGS["ZOOM_OUT"]:
            self.camera.zoom = max(self.camera.zoom / zoom_factor, self.min_zoom)
        else:
             raise ValueError(f"Invalid camera operation: {key}")
        self.clamp_camera_position()

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.mouse_pressed = True
            # Store the initial mouse position in screen coordinates
            self.last_mouse_position = (x, y)

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.mouse_pressed = False

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        if self.mouse_pressed:
            # Calculate movement delta in world coordinates
            # dx/dy are screen coordinate changes, convert to world coord changes
            world_dx = dx / self.camera.zoom
            world_dy = dy / self.camera.zoom

            # Calculate new potential position (subtract world delta)
            new_x = self.camera.position[0] - world_dx
            new_y = self.camera.position[1] - world_dy
            self.clamp_camera_position(new_x, new_y)

            # Update last mouse position for next drag event
            self.last_mouse_position = (x, y)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if scroll_y > 0:
            self.zoom(CAMERA_SETTINGS["ZOOM_IN"])
        elif scroll_y < 0:
            self.zoom(CAMERA_SETTINGS["ZOOM_OUT"])

    def on_key_press(self, key, modifiers):
        self.pressed_keys.add(key)
        # Handle zoom keys directly here now, calling camera_operation
        if key == arcade.key.X: # Assuming X is zoom in
            self.zoom(CAMERA_SETTINGS["ZOOM_IN"])
        elif key == arcade.key.Z: # Assuming Z is zoom out
             self.zoom(CAMERA_SETTINGS["ZOOM_OUT"])
        # Note: Panning keys are handled in on_update

    def on_key_release(self, key, modifiers):
        self.pressed_keys.discard(key)

    def on_update(self, delta_time):
        pan_speed = CAMERA_SETTINGS["PAN_RATE"] * delta_time  # pixels per second
        dx = dy = 0

        if arcade.key.LEFT in self.pressed_keys:
            dx -= pan_speed
        if arcade.key.RIGHT in self.pressed_keys:
            dx += pan_speed
        if arcade.key.UP in self.pressed_keys:
            dy += pan_speed
        if arcade.key.DOWN in self.pressed_keys:
            dy -= pan_speed

        if dx or dy:
            new_x = self.camera.position[0] + dx
            new_y = self.camera.position[1] + dy
            self.camera.position = self.clamp_camera_position(new_x, new_y)

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

