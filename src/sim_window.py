import os
import platform
import signal
import subprocess
import sys
import time
from typing import Optional

import arcade
from arcade.gui import UIAnchorLayout, UIBoxLayout, UIFlatButton, UIManager

import settings
from config import CAMERA_SETTINGS, SCREEN_TITLE, WINDOW_HEIGHT, WINDOW_WIDTH
from entities.entity_manager import EntityManager
from input_controller import CameraMode, InputController
from overlays import Overlays
from creature_renderer import CreatureRenderer
from simulation.camera_controller import CameraController
from sprite_manager import sprite_manager

HUD_REFRESH = 0.5       # seconds between HUD text updates
SETTINGS_POLL = 0.5     # seconds between checks of settings.json
SETTINGS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings_window.py")
LAYERS = ("plants", "herbivores", "smarties", "carnivores")


class SimulationWindow(arcade.Window):
    """
    Main application class for the simulation.
    """

    def __init__(self, open_settings: bool = True):
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
        self.paused = False
        self.overlays = Overlays()
        self.creature_renderer = None
        # Screen-space camera and cached Text object for the HUD (arcade.Text is far
        # cheaper than draw_text, which rebuilds glyphs every frame)
        self.hud_camera = arcade.Camera2D()
        self.hud_text = arcade.Text("", 10, 10, arcade.color.WHITE, 12)
        self._hud_timer = 0.0
        self._frames = 0
        self._fps_clock = time.perf_counter()

        self.settings_watcher = settings.SettingsWatcher()
        self._settings_timer = SETTINGS_POLL
        self._settings_process: Optional[subprocess.Popen] = None
        self._build_toolbar()
        if open_settings:
            self.open_settings()

    def _build_toolbar(self):
        self.ui = UIManager(self)
        self.ui.enable()
        bar = UIBoxLayout(vertical=False, space_between=6)
        for text, callback in (("Restart", self.restart), ("Pause", self.toggle_pause), ("Settings", self.open_settings)):
            button = UIFlatButton(text=text, width=96, height=30)
            button.set_handler("on_click", lambda event, cb=callback: cb())
            bar.add(button)
            if text == "Pause":
                self.pause_button = button
        anchor = UIAnchorLayout()
        anchor.add(bar, anchor_x="right", anchor_y="top", align_x=-8, align_y=-8)
        self.ui.add(anchor)

    def setup(self):
        """Build a fresh world with the current settings. Also used by Restart."""
        sprite_manager.load_all_sprite_sheets()
        data = settings.load()
        settings.apply(data)
        self.overlays.configure(**settings.display_options(data))
        self.entity_manager = EntityManager()
        if self.creature_renderer is None:
            from entities.entity_manager import CREATURE_TYPES
            self.creature_renderer = CreatureRenderer(CREATURE_TYPES)
        map_width, map_height = self.entity_manager.get_map_size()
        self.camera_controller.setup(map_width, map_height)
        self.entity_manager.spawn_initial_population()
        self._refresh_hud()

    # ----------------------------------------------------------------- toolbar

    def restart(self):
        self.setup()

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_button.text = "Resume" if self.paused else "Pause"

    def open_settings(self):
        """Open the settings window (a separate process), or bring it to the front if it's open."""
        if self._settings_process is not None and self._settings_process.poll() is None:
            self._settings_process.send_signal(signal.SIGUSR1)
            return
        self._settings_process = subprocess.Popen([sys.executable, SETTINGS_SCRIPT])

    def _poll_settings(self):
        data, restart = self.settings_watcher.poll()
        if data is None:
            return
        self.overlays.configure(**settings.display_options(data))
        if restart:
            self.restart()
            return
        settings.apply(data)
        self.entity_manager.refresh_food_chain()

    # ------------------------------------------------------------------ events

    def on_resize(self, width: int, height: int):
        """Handle window resizing events."""
        super().on_resize(width, height)
        self.camera_controller.handle_resize(width, height)
        self.hud_camera.match_window(position=True)

    def on_draw(self):
        """Render the screen."""
        self.clear()
        self.camera_controller.use()
        self.entity_manager.scene.draw()
        self.creature_renderer.draw(self.entity_manager.creatures.store)
        self.overlays.draw()
        self.hud_camera.use()
        self.hud_text.draw()
        self.ui.draw()
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
        self._settings_timer -= delta_time
        if self._settings_timer <= 0:
            self._settings_timer = SETTINGS_POLL
            self._poll_settings()
        if not self.paused:
            self.entity_manager.update(delta_time)
        self.overlays.update(self.entity_manager, LAYERS[1:])
        self._hud_timer -= delta_time
        if self._hud_timer <= 0:
            self._hud_timer = HUD_REFRESH
            self._refresh_hud()

    def _refresh_hud(self):
        em = self.entity_manager
        counts = "  ".join(f"{name}: {em.population(name)}" for name in LAYERS)
        now = time.perf_counter()
        fps = self._frames / max(now - self._fps_clock, 1e-6)
        self._frames, self._fps_clock = 0, now
        paused = "  |  paused" if self.paused else ""
        self.hud_text.text = f"{counts}  |  {fps:.0f} fps{paused}"

    def on_close(self):
        """Handle window close events for a graceful shutdown."""
        if self._settings_process is not None and self._settings_process.poll() is None:
            self._settings_process.terminate()
        arcade.close_window()
        if sys.platform == 'darwin' or platform.system() == 'Darwin':
            time.sleep(0.1)
            os._exit(0)
