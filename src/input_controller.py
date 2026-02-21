from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import arcade


@dataclass
class InputState:
    pressed_keys: set[int] = field(default_factory=set)
    mouse_buttons: set[int] = field(default_factory=set)
    mouse_x: int = 0
    mouse_y: int = 0
    modifiers: int = 0


@dataclass
class InputTargets:
    camera: object
    selected_creature: Optional[object] = None


class InputMode:
    name: str = "base"

    def on_enter(self, state: InputState, targets: InputTargets) -> None:
        return

    def on_exit(self, state: InputState, targets: InputTargets) -> None:
        return

    def on_key_press(self, key: int, modifiers: int, state: InputState, targets: InputTargets) -> bool:
        return False

    def on_key_release(self, key: int, modifiers: int, state: InputState, targets: InputTargets) -> bool:
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
        targets: InputTargets,
    ) -> bool:
        return False

    def on_mouse_scroll(
        self,
        x: int,
        y: int,
        scroll_x: int,
        scroll_y: int,
        state: InputState,
        targets: InputTargets,
    ) -> bool:
        return False

    def update(self, dt: float, state: InputState, targets: InputTargets) -> None:
        return


class CameraMode(InputMode):
    name = "camera"

    def on_key_press(self, key: int, modifiers: int, state: InputState, targets: InputTargets) -> bool:
        camera = targets.camera
        if getattr(camera, "camera", None) is None:
            return True

        if key == arcade.key.X:
            camera.apply_zoom("in")
            return True
        if key == arcade.key.Z:
            camera.apply_zoom("out")
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
        targets: InputTargets,
    ) -> bool:
        camera = targets.camera
        if getattr(camera, "camera", None) is None:
            return True
        camera.handle_drag(dx, dy)
        return True

    def on_mouse_scroll(
        self,
        x: int,
        y: int,
        scroll_x: int,
        scroll_y: int,
        state: InputState,
        targets: InputTargets,
    ) -> bool:
        camera = targets.camera
        if getattr(camera, "camera", None) is None:
            return True

        if scroll_y > 0:
            camera.apply_zoom("in")
            return True
        if scroll_y < 0:
            camera.apply_zoom("out")
            return True

        return True

    def update(self, dt: float, state: InputState, targets: InputTargets) -> None:
        camera = targets.camera
        if getattr(camera, "camera", None) is None:
            return
        camera.update_panning(state.pressed_keys, dt)


class InputController:
    def __init__(self, targets: InputTargets, default_mode: InputMode):
        self.targets = targets
        self.state = InputState()
        self._mode_stack: list[InputMode] = [default_mode]
        default_mode.on_enter(self.state, self.targets)

    @property
    def mode(self) -> InputMode:
        return self._mode_stack[-1]

    def push_mode(self, mode: InputMode) -> None:
        self.mode.on_exit(self.state, self.targets)
        self._mode_stack.append(mode)
        mode.on_enter(self.state, self.targets)

    def pop_mode(self) -> None:
        if len(self._mode_stack) <= 1:
            return
        self.mode.on_exit(self.state, self.targets)
        self._mode_stack.pop()
        self.mode.on_enter(self.state, self.targets)

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
        self.mode.update(dt, self.state, self.targets)

    def _dispatch(self, method_name: str, *args) -> None:
        # Bubble from top-most mode down until consumed.
        for mode in reversed(self._mode_stack):
            handler = getattr(mode, method_name)
            consumed = handler(*args, self.state, self.targets)
            if consumed:
                return
