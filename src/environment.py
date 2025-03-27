import os
import platform
import sys
import arcade
from arcade.types import LRBT
from config import *


class GameView(arcade.View):
    def __init__(self):
        super().__init__()
        self.background_color = arcade.color.AMAZON
        self.camera = arcade.Camera2D(
            position=(0, 0),
            projection=LRBT(left=0, right=self.window.width, bottom=0, top=self.window.height),
            viewport=self.window.rect
        )
        self._center_camera()

    def _get_center_position(self, width=None, height=None):
        width = width if width else self.window.width
        height = height if height else self.window.height
        center_x = self.camera.position[0] + width / 2
        center_y = self.camera.position[1] + height / 2
        return (center_x, center_y)
    
    def _get_center_from_projection(self):
        width = self.camera.projection.right - self.camera.projection.left
        height = self.camera.projection.top - self.camera.projection.bottom
        return self._get_center_position(width, height)
    
    def _center_camera(self):
        w = self.window.width
        h = self.window.height
        self.camera.position = (
            self.camera.position[0] - w / 2,
            self.camera.position[1] - h / 2
        )

    def on_resize(self, width: int, height: int):
        old_center = self._get_center_from_projection()

        # Update the camera projection and viewport
        self.camera.projection = LRBT(0, width, 0, height)
        self.camera.viewport = self.window.rect
        
        new_center = self._get_center_position(width, height)
        self.camera.position = (
            self.camera.position[0] + (old_center[0] - new_center[0]),
            self.camera.position[1] + (old_center[1] - new_center[1])
        )
        
        super().on_resize(width, height)

    def on_draw(self):
        self.clear()
        with self.camera.activate():
            arcade.draw_rect_outline(
                LRBT(0, 400, 0, 300),
                color=arcade.color.WHITE,
                border_width=5,
            )

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

    def on_key_press(self, key, modifiers):
        pan_rate = CAMERA_OPS["PAN_RATE"]
        match key:
            case arcade.key.LEFT:
                print("LEFT", self.camera.position)
                self.camera.position = (self.camera.position[0] - pan_rate, self.camera.position[1])
            case arcade.key.RIGHT:
                print("RIGHT", self.camera.position)
                self.camera.position = (self.camera.position[0] + pan_rate, self.camera.position[1])
            case arcade.key.UP:
                print("UP", self.camera.position)
                self.camera.position = (self.camera.position[0], self.camera.position[1] + pan_rate)
            case arcade.key.DOWN:
                print("DOWN", self.camera.position)
                self.camera.position = (self.camera.position[0], self.camera.position[1] - pan_rate)
            case arcade.key.X:
                self.camera_operation(CAMERA_OPS["ZOOM_IN"])
            case arcade.key.Z:
                self.camera_operation(CAMERA_OPS["ZOOM_OUT"])
            case _:
                pass

    def on_update(self, delta_time):
        pass


class EvoTalesWorld(arcade.Window):
    def __init__(self):
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
        
        self.game = GameView()
        self.show_view(self.game)
        
    def on_draw(self):
        pass
    
    def on_update(self, delta_time: float):
        pass
    
    def on_close(self):
        # More graceful shutdown sequence
        self.game = None  # Clear the view reference
        arcade.close_window()
        if sys.platform == 'darwin' or platform.system() == 'Darwin':
            # Give a small delay before force exit on macOS
            import time
            time.sleep(0.1)
            os._exit(0)

