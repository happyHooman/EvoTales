import os
import platform
import sys
import time
import arcade
from config import *
from simulation.camera_controller import CameraController
from typing import Optional
from entities.entity_manager import EntityManager
from input_controller import CameraMode, InputController
from sprite_manager import sprite_manager

HUD_REFRESH = 0.5  # seconds between HUD text updates

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
        self.camera_controller = CameraController(CAMERA_SETTINGS, self)
        self.input_controller = InputController(
            default_mode=CameraMode(self.camera_controller),
        )
        self.background_color = arcade.color.AMAZON
        self.entity_manager: Optional[EntityManager] = None
        # Screen-space camera and cached Text object for the HUD (arcade.Text is far
        # cheaper than draw_text, which rebuilds glyphs every frame)
        self.hud_camera = arcade.Camera2D()
        self.hud_text = arcade.Text("", 10, 10, arcade.color.WHITE, 12)
        self._hud_timer = 0.0
        self._frames = 0
        self._fps_clock = time.perf_counter()

    def setup(self):
        """Set up the game environment. Call this function to restart the game."""
        sprite_manager.load_all_sprite_sheets()
        self.entity_manager = EntityManager()
        map_width, map_height = self.entity_manager.get_map_size()
        self.camera_controller.setup(map_width, map_height)
        self.entity_manager.spawn_initial_population()

    def on_resize(self, width: int, height: int):
        """Handle window resizing events."""
        super().on_resize(width, height)
        self.camera_controller.handle_resize(width, height)
        self.hud_camera.match_window()

    def on_draw(self):
        """Render the screen."""
        self.clear()
        self.camera_controller.use()
        self.entity_manager.scene.draw()
        self.hud_camera.use()
        self.hud_text.draw()
        self._frames += 1

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        """Handle mouse drag events for camera panning."""
        self.input_controller.on_mouse_drag(x, y, dx, dy, buttons, modifiers)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        """Handle mouse scroll events for zooming."""
        self.input_controller.on_mouse_scroll(x, y, scroll_x, scroll_y)

    def on_key_press(self, key, modifiers):
        """Handle key press events."""
        self.input_controller.on_key_press(key, modifiers)

    def on_key_release(self, key, modifiers):
        """Handle key release events."""
        self.input_controller.on_key_release(key, modifiers)

    def on_update(self, delta_time):
        """Update game logic."""
        self.input_controller.update(delta_time)
        self.entity_manager.update(delta_time)
        self._hud_timer -= delta_time
        if self._hud_timer <= 0:
            self._hud_timer = HUD_REFRESH
            self._refresh_hud()

    def _refresh_hud(self):
        em = self.entity_manager
        counts = "  ".join(f"{name}: {em.population(name)}"
                           for name in ("plants", "herbivores", "carnivores", "smarties"))
        now = time.perf_counter()
        fps = self._frames / max(now - self._fps_clock, 1e-6)
        self._frames, self._fps_clock = 0, now
        self.hud_text.text = f"{counts}  |  {fps:.0f} fps"

    def on_close(self):
        """Handle window close events for a graceful shutdown."""
        arcade.close_window()
        if sys.platform == 'darwin' or platform.system() == 'Darwin':
            import time
            time.sleep(0.1)
            os._exit(0)
