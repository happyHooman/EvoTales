from __future__ import annotations

from dataclasses import dataclass, field

import arcade


@dataclass
class InputState:
    pressed_keys: set[int] = field(default_factory=set)
    mouse_buttons: set[int] = field(default_factory=set)
    mouse_x: int = 0
    mouse_y: int = 0
    modifiers: int = 0


class InputMode:
    name: str = "base"

    def on_enter(self, state: InputState) -> None:
        return

    def on_exit(self, state: InputState) -> None:
        return

    def on_key_press(self, key: int, modifiers: int, state: InputState) -> bool:
        return False

    def on_key_release(self, key: int, modifiers: int, state: InputState) -> bool:
        return False

    def on_mouse_drag(
        self,
        x: int,
        y: int,
        dx: int,
        dy: int,
        buttons: int,
        modifiers: int,
        state: InputState,
    ) -> bool:
        return False

    def on_mouse_scroll(
        self,
        x: int,
        y: int,
        scroll_x: int,
        scroll_y: int,
        state: InputState,
    ) -> bool:
        return False

    def update(self, dt: float, state: InputState) -> None:
        return


class CameraMode(InputMode):
    """
    Handles camera movement and zooming.

    Args:
        camera: CameraController instance

    Events:
     - mouse_drag: pan camera
     - mouse_scroll: zoom camera
     - Z: zoom in
     - X: zoom out
    """
    name = "camera"

    def __init__(self, camera: object):
        self.camera = camera

    def on_key_press(self, key: int, modifiers: int, state: InputState) -> bool:
        if getattr(self.camera, "camera", None) is None:
            return True

        if key == arcade.key.X:
            self.camera.apply_zoom("in")
            return True
        if key == arcade.key.Z:
            self.camera.apply_zoom("out")
            return True

        return False

    def on_mouse_drag(
        self,
        x: int,
        y: int,
        dx: int,
        dy: int,
        buttons: int,
        modifiers: int,
        state: InputState,
    ) -> bool:
        if getattr(self.camera, "camera", None) is None:
            return True
        self.camera.handle_drag(dx, dy)
        return True

    def on_mouse_scroll(
        self,
        x: int,
        y: int,
        scroll_x: int,
        scroll_y: int,
        state: InputState,
    ) -> bool:
        if getattr(self.camera, "camera", None) is None:
            return True

        if scroll_y > 0:
            self.camera.apply_zoom("in")
            return True
        if scroll_y < 0:
            self.camera.apply_zoom("out")
            return True

        return True

    def update(self, dt: float, state: InputState) -> None:
        if getattr(self.camera, "camera", None) is None:
            return
        self.camera.update_panning(state.pressed_keys, dt)


class InputController:
    """
    Handles input events and dispatches them to the current input mode.

    Args:
        default_mode: InputMode instance
    """
    def __init__(self, default_mode: InputMode):
        self.state = InputState()
        self._mode: InputMode = default_mode
        default_mode.on_enter(self.state)

    @property
    def mode(self) -> InputMode:
        return self._mode

    def set_mode(self, mode: InputMode) -> None:
        self._mode.on_exit(self.state)
        self._mode = mode
        mode.on_enter(self.state)

    def on_key_press(self, key: int, modifiers: int) -> None:
        self.state.modifiers = modifiers
        self.state.pressed_keys.add(key)
        self._dispatch("on_key_press", key, modifiers)

    def on_key_release(self, key: int, modifiers: int) -> None:
        self.state.modifiers = modifiers
        self.state.pressed_keys.discard(key)
        self._dispatch("on_key_release", key, modifiers)

    def on_mouse_drag(
        self,
        x: int,
        y: int,
        dx: int,
        dy: int,
        buttons: int,
        modifiers: int,
    ) -> None:
        self.state.mouse_x, self.state.mouse_y = x, y
        self.state.modifiers = modifiers
        self._dispatch("on_mouse_drag", x, y, dx, dy, buttons, modifiers)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        self.state.mouse_x, self.state.mouse_y = x, y
        self._dispatch("on_mouse_scroll", x, y, scroll_x, scroll_y)

    def update(self, dt: float) -> None:
        self.mode.update(dt, self.state)

    def _dispatch(self, method_name: str, *args) -> None:
        handler = getattr(self._mode, method_name)
        handler(*args, self.state)
