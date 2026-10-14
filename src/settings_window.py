"""
Settings window for EvoTales. Runs as its own process (the simulation opens it)
and talks to the simulation through settings.json.

    uv run python src/settings_window.py
"""
import copy
import os
import signal
import sys

import arcade
from arcade.gui import UIAnchorLayout, UIBoxLayout, UIFlatButton, UILabel, UIManager

# Allow running from the repo root (paths in the code are relative to it)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings  # noqa: E402

WIDTH, HEIGHT = 940, 660
ROW_HEIGHT = 26
FOOD_LAYERS = ["plants", "herbivores", "smarties", "carnivores"]
LABELS = {
    "initial_count": "Initial count (restart)",
    "min_spacing": "Min spacing (restart)",
}


# How much one click on - / + changes each value (shift-click: 10x).
# Integers stay integers; everything else is rounded to the step's precision.
STEPS = {
    # plants
    "min_spacing": 1, "seed_min_distance": 5, "seed_range": 10,
    "max_growth_timer": 1.0, "reproduction_delay": 1.0, "min_edible_level": 1,
    # creatures
    "initial_count": 1, "max_population": 1,
    "walk_speed": 1, "run_speed_multiplier": 0.05, "run_energy_multiplier": 0.1,
    "relax_speed_ratio": 0.05, "turn_rate": 0.1, "vision_range": 10,
    "avoid_horizon": 0.1, "avoid_margin": 1,
    "max_energy": 5, "birth_energy": 5, "alive_energy_cost": 0.05, "walk_energy_cost": 0.05,
    "hungry_ratio": 0.05, "full_ratio": 0.05, "relaxed_ratio": 0.05,
    "reproduction_interval": 1.0, "reproduction_energy_threshold": 5, "reproduction_energy_cost": 5,
    "hunger_boldness": 0.05, "boldness_interval": 0.5,
    "nutrition": 5, "corpse_duration": 1.0,
}
PLANT_STEPS = {"initial_count": 10}
MINIMUMS = {"run_speed_multiplier": 1.05, "run_energy_multiplier": 1.0, "boldness_interval": 0.1,
            "think_interval": 0.05, "max_energy": 5, "min_edible_level": 1}


def _step(section: str, key: str):
    if section == "plants" and key in PLANT_STEPS:
        return PLANT_STEPS[key]
    return STEPS.get(key, 1)


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


class SettingsWindow(arcade.Window):
    """
    The form for each tab is built once and kept; clicks only update the label
    that changed. (Rebuilding ~100 widgets per click took ~150 ms and made the
    window feel stuck.)
    """

    def __init__(self):
        super().__init__(WIDTH, HEIGHT, "EvoTales settings", resizable=True,
                         update_rate=1 / 30, draw_rate=1 / 30)
        self.background_color = (34, 40, 49)
        # The simulation's Settings button sends SIGUSR1 when this window is already open
        self._raise_requested = False
        signal.signal(signal.SIGUSR1, lambda *_: setattr(self, "_raise_requested", True))
        self.view_options = settings.display_options()
        self.values = settings.current_values()
        self.section = "herbivores"
        self.status = ""
        self._forms = {}  # section -> (widget, value labels by key, diet buttons by food)

        self.ui = UIManager()
        self.ui.enable()
        root = UIBoxLayout(vertical=True, space_between=6, align="left")

        tabs = UIBoxLayout(vertical=False, space_between=4)
        self._tab_buttons = {}
        for name in settings.SECTIONS:
            self._tab_buttons[name] = tabs.add(self._button(name, 112, lambda n=name: self.select(n)))
        root.add(tabs)

        view = UIBoxLayout(vertical=False, space_between=6)
        self._view_buttons = {}
        for key in ("show_fov", "show_energy"):
            self._view_buttons[key] = view.add(self._button("", 200, lambda k=key: self.toggle_display(k), height=30))
        root.add(view)

        self._form_slot = root.add(UIBoxLayout(vertical=True, align="left"))

        actions = UIBoxLayout(vertical=False, space_between=6)
        actions.add(self._button("Apply live", 140, lambda: self.apply(restart=False)))
        actions.add(self._button("Apply + restart", 160, lambda: self.apply(restart=True)))
        actions.add(self._button("Defaults", 110, self.reset_section))
        root.add(actions)
        self._notes = root.add(UILabel(" ", width=WIDTH - 40, height=60, multiline=True,
                                       text_color=arcade.color.LIGHT_SALMON_PINK, size_hint=None))
        root.add(UILabel("Shift-click - / + for 10x steps.", text_color=arcade.color.GRAY))

        anchor = UIAnchorLayout()
        anchor.add(root, anchor_x="left", anchor_y="top", align_x=16, align_y=-12)
        self.ui.add(anchor)
        self._refresh_view_buttons()
        for section in settings.SECTIONS:  # build every tab up front so switching is instant
            self._form(section)
        self.select(self.section)

    # ------------------------------------------------------------------ layout

    def _form(self, section):
        if section in self._forms:
            return self._forms[section]
        form = UIBoxLayout(vertical=True, space_between=8, align="left")
        columns = form.add(UIBoxLayout(vertical=False, space_between=24, align="top"))
        numeric = [k for k in settings.editable_keys(section) if k != "diet"]
        half = (len(numeric) + 1) // 2
        labels, diet_buttons = {}, {}
        for keys in (numeric[:half], numeric[half:]):
            column = columns.add(UIBoxLayout(vertical=True, space_between=4, align="left"))
            for key in keys:
                row = column.add(UIBoxLayout(vertical=False, space_between=4))
                name = LABELS.get(key, key.replace("_", " ").capitalize())
                step = _step(section, key)
                row.add(UILabel(f"{name}  (\u00b1{_fmt(step)})", width=272, height=ROW_HEIGHT, size_hint=None))
                row.add(self._button("-", 32, lambda mult, k=key: self.nudge(k, -mult), height=ROW_HEIGHT, shift_aware=True))
                labels[key] = row.add(UILabel("", width=64, height=ROW_HEIGHT, align="center", size_hint=None))
                row.add(self._button("+", 32, lambda mult, k=key: self.nudge(k, mult), height=ROW_HEIGHT, shift_aware=True))
        if "diet" in settings.editable_keys(section):
            row = form.add(UIBoxLayout(vertical=False, space_between=4))
            row.add(UILabel("Diet", width=60, height=ROW_HEIGHT, size_hint=None))
            for food in FOOD_LAYERS:
                if food != section:
                    diet_buttons[food] = row.add(self._button(
                        "", 150, lambda f=food: self.toggle_diet(f), height=ROW_HEIGHT))
        self._forms[section] = (form, labels, diet_buttons)
        return self._forms[section]

    def _button(self, text, width, callback, height=34, shift_aware=False):
        button = UIFlatButton(text=text, width=width, height=height)
        if shift_aware:
            button.set_handler("on_click", lambda event: callback(
                10 if event.modifiers & arcade.key.MOD_SHIFT else 1))
        else:
            button.set_handler("on_click", lambda event: callback())
        return button

    def _refresh_form(self):
        _, labels, diet_buttons = self._form(self.section)
        values = self.values[self.section]
        for key, label in labels.items():
            label.text = _fmt(values[key])
        for food, button in diet_buttons.items():
            button.text = ("eats " if food in values["diet"] else "not ") + food

    def _refresh_view_buttons(self):
        for key, text in (("show_fov", "field of view"), ("show_energy", "energy bars")):
            mark = "[x]" if self.view_options[key] else "[  ]"
            self._view_buttons[key].text = f"{mark} Show {text}"

    def _refresh_notes(self):
        notes = list(settings.speed_warnings(self.values))
        if self.status:
            notes.insert(0, self.status)
        self._notes.text = "\n".join(notes) or " "

    # ----------------------------------------------------------------- actions

    def select(self, section):
        self.section = section
        for name, button in self._tab_buttons.items():
            button.text = f"[{name}]" if name == section else name
        self._form_slot.clear()
        self._form_slot.add(self._form(section)[0])
        self._refresh_form()
        self._refresh_notes()

    def nudge(self, key, direction):
        values = self.values[self.section]
        value = values[key]
        step = _step(self.section, key) * abs(direction)
        new = value + (step if direction > 0 else -step)
        new = max(MINIMUMS.get(key, 0), new)
        if key.endswith("ratio") or key == "hunger_boldness":
            new = min(new, 1.0)
        if isinstance(value, int) and isinstance(step, int):
            new = int(new)
        else:
            new = round(float(new), 2)
        values[key] = new
        self._forms[self.section][1][key].text = _fmt(new)
        self.status = "Not applied yet"
        self._refresh_notes()

    def toggle_display(self, key):
        """Overlay toggles apply immediately; they don't touch the simulation values."""
        self.view_options[key] = not self.view_options[key]
        settings.save_display(self.view_options)
        self._refresh_view_buttons()

    def toggle_diet(self, food):
        diet = self.values[self.section]["diet"]
        if food in diet:
            diet.remove(food)
        else:
            diet.append(food)
        self.status = "Not applied yet"
        self._refresh_form()
        self._refresh_notes()

    def reset_section(self):
        self.values[self.section] = {k: copy.deepcopy(settings.DEFAULTS[self.section][k])
                                     for k in settings.editable_keys(self.section)}
        self.status = f"{self.section}: code defaults restored, not applied yet"
        self._refresh_form()
        self._refresh_notes()

    def apply(self, restart):
        settings.save(self.values, restart=restart)
        self.status = "Applied, restarting the simulation" if restart else "Applied live (initial counts need a restart)"
        self._refresh_notes()

    def on_update(self, delta_time):
        if self._raise_requested:
            self._raise_requested = False
            self.set_visible(True)
            self.activate()

    def on_draw(self):
        self.clear()
        self.ui.draw()


def main():
    SettingsWindow()
    arcade.run()


if __name__ == "__main__":
    main()
