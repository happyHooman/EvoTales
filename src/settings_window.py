"""
Settings window for EvoTales. Runs as its own process (the simulation opens it)
and talks to the simulation through settings.json.

    uv run python src/settings_window.py
"""
import os
import signal
import sys

import arcade
from arcade.gui import UIAnchorLayout, UIBoxLayout, UIFlatButton, UILabel, UIManager

# Allow running from the repo root (paths in the code are relative to it)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings  # noqa: E402

WIDTH, HEIGHT = 620, 860
ROW_HEIGHT = 26
FOOD_LAYERS = ["plants", "herbivores", "smarties", "carnivores"]
LABELS = {
    "initial_count": "Initial count (restart)",
    "min_spacing": "Min spacing (restart)",
}


def _step(key: str, value):
    if key.endswith("ratio"):
        return 0.05
    if isinstance(value, int):
        return max(1, round(abs(value) * 0.1))
    return max(0.05, round(abs(value) * 0.1, 2))


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


class SettingsWindow(arcade.Window):
    def __init__(self):
        # A settings form doesn't need 60 fps; keep it light next to the simulation
        super().__init__(WIDTH, HEIGHT, "EvoTales settings", resizable=True,
                         update_rate=1 / 20, draw_rate=1 / 20)
        self.background_color = (34, 40, 49)
        # The simulation's Settings button sends SIGUSR1 when this window is already open
        self._raise_requested = False
        signal.signal(signal.SIGUSR1, lambda *_: setattr(self, "_raise_requested", True))
        self.view_options = settings.display_options()
        self.ui = UIManager()
        self.ui.enable()
        self.values = settings.current_values()
        self.section = "herbivores"
        self.status = ""
        self.build()

    # ------------------------------------------------------------------ layout

    def build(self):
        self.ui.clear()
        root = UIBoxLayout(vertical=True, space_between=6, align="left")

        tabs = UIBoxLayout(vertical=False, space_between=4)
        for name in settings.SECTIONS:
            label = f"[{name}]" if name == self.section else name
            tabs.add(self._button(label, 112, lambda n=name: self.select(n)))
        root.add(tabs)

        view = UIBoxLayout(vertical=False, space_between=6)
        for key, text in (("show_fov", "field of view"), ("show_energy", "energy bars")):
            mark = "[x]" if self.view_options[key] else "[  ]"
            view.add(self._button(f"{mark} Show {text}", 200, lambda k=key: self.toggle_display(k), height=30))
        root.add(view)

        values = self.values[self.section]
        for key in settings.editable_keys(self.section):
            row = UIBoxLayout(vertical=False, space_between=4)
            row.add(UILabel(LABELS.get(key, key.replace("_", " ").capitalize()),
                            width=270, height=ROW_HEIGHT, size_hint=None))
            if key == "diet":
                root.add(row)
                row = UIBoxLayout(vertical=False, space_between=4)
                for food in FOOD_LAYERS:
                    if food == self.section:
                        continue
                    on = food in values["diet"]
                    row.add(self._button(("eats " if on else "not ") + food, 140,
                                         lambda f=food: self.toggle_diet(f), height=ROW_HEIGHT))
            else:
                value_label = UILabel(_fmt(values[key]), width=90, height=ROW_HEIGHT, align="center", size_hint=None)
                row.add(self._button("-", 36, lambda k=key, lbl=value_label: self.nudge(k, -1, lbl), height=ROW_HEIGHT))
                row.add(value_label)
                row.add(self._button("+", 36, lambda k=key, lbl=value_label: self.nudge(k, 1, lbl), height=ROW_HEIGHT))
            root.add(row)

        actions = UIBoxLayout(vertical=False, space_between=6)
        actions.add(self._button("Apply live", 140, lambda: self.apply(restart=False)))
        actions.add(self._button("Apply + restart", 160, lambda: self.apply(restart=True)))
        actions.add(self._button("Defaults", 110, self.reset_section))
        root.add(actions)

        notes = list(settings.speed_warnings(self.values))
        if self.status:
            notes.insert(0, self.status)
        root.add(UILabel("\n".join(notes) or " ", width=WIDTH - 40, multiline=True,
                         text_color=arcade.color.LIGHT_SALMON_PINK if notes else arcade.color.WHITE))

        anchor = UIAnchorLayout()
        anchor.add(root, anchor_x="left", anchor_y="top", align_x=16, align_y=-12)
        self.ui.add(anchor)

    def _button(self, text, width, callback, height=34):
        button = UIFlatButton(text=text, width=width, height=height)
        button.set_handler("on_click", lambda event: callback())
        return button

    # ----------------------------------------------------------------- actions

    def select(self, section):
        self.section = section
        self.status = ""
        self.build()

    def nudge(self, key, direction, label):
        values = self.values[self.section]
        value = values[key]
        new = value + direction * _step(key, value)
        new = max(0, new)
        if isinstance(value, float):
            new = round(new, 2)
            if key.endswith("ratio"):
                new = min(new, 1.0)
            if key == "run_speed_multiplier":
                new = max(new, 1.05)  # must stay above walking for the energy formula
            if key == "run_energy_multiplier":
                new = max(new, 1.0)
        values[key] = new
        label.text = _fmt(new)
        self.status = "Not applied yet"
        self.build()

    def toggle_display(self, key):
        """Overlay toggles apply immediately; they don't touch the simulation values."""
        self.view_options[key] = not self.view_options[key]
        settings.save_display(self.view_options)
        self.build()

    def on_update(self, delta_time):
        if self._raise_requested:
            self._raise_requested = False
            self.set_visible(True)
            self.activate()

    def toggle_diet(self, food):
        diet = self.values[self.section]["diet"]
        if food in diet:
            diet.remove(food)
        else:
            diet.append(food)
        self.status = "Not applied yet"
        self.build()

    def reset_section(self):
        self.values[self.section] = {k: settings.DEFAULTS[self.section][k]
                                     for k in settings.editable_keys(self.section)}
        if isinstance(self.values[self.section].get("diet"), list):
            self.values[self.section]["diet"] = list(self.values[self.section]["diet"])
        self.status = f"{self.section}: code defaults restored, not applied yet"
        self.build()

    def apply(self, restart):
        settings.save(self.values, restart=restart)
        self.status = "Applied, restarting the simulation" if restart else "Applied live (initial counts need a restart)"
        self.build()

    def on_draw(self):
        self.clear()
        self.ui.draw()


def main():
    SettingsWindow()
    arcade.run()


if __name__ == "__main__":
    main()
