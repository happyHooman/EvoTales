"""
Settings window for EvoTales: a native Qt form. Runs as its own process (the
simulation opens it) and talks to the simulation through settings.json.

    uv run python src/settings_window.py
"""
import copy
import os
import signal
import sys

from PySide6.QtCore import QLocale, QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox,
                               QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QScrollArea,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)

# Allow running from the repo root (paths in the code are relative to it)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings  # noqa: E402

FOOD_LAYERS = ["plants", "herbivores", "smarties", "carnivores"]
LABELS = {
    "initial_count": "Initial count (on restart)",
    "min_spacing": "Min spacing (on restart)",
    "max_growth_timer": "Growth time per stage (s)",
    "reproduction_delay": "Seeding delay (s)",
    "min_edible_level": "Min edible growth stage",
    "walk_speed": "Walk speed (px/s)",
    "vision_range": "Vision range (px)",
    "turn_rate": "Turn rate (rad/s)",
    "avoid_horizon": "Avoid look-ahead (s)",
    "avoid_margin": "Avoid margin (px)",
    "birth_stamina_ratio": "Birth stamina (fraction)",
    "alive_stamina_cost": "Alive stamina cost (/s)",
    "walk_stamina_cost": "Walk stamina cost (/s)",
    "food_drain": "Food drain (/s)",
    "digest_rate": "Digest rate (food/s)",
    "digest_efficiency": "Stamina per food",
    "starve_ratio": "Starving below (food fraction)",
    "starve_damage": "Starving damage (hp/s)",
    "muscle_burn": "Muscle burn (hp per stamina owed)",
    "heal_rate": "Heal rate while relaxing (hp/s)",
    "heal_stamina_cost": "Healing stamina cost (/s)",
    "heal_food_cost": "Healing food cost (/s)",
    "hungry_ratio": "Hungry below (food fraction)",
    "full_ratio": "Full at (food fraction)",
    "relaxed_ratio": "Relaxes above (food fraction)",
    "rest_ratio": "Tired below (stamina fraction)",
    "rested_ratio": "Rested at (stamina fraction)",
    "sprint_range": "Sprints at prey within (px)",
    "reproduction_interval": "Reproduction interval (s)",
    "reproduction_food_threshold": "Reproduction needs food",
    "reproduction_health_ratio": "Reproduction needs health (fraction)",
    "reproduction_food_cost": "Reproduction food cost",
    "boldness_interval": "Boldness re-roll (s)",
    "corpse_duration": "Corpse duration (s)",
    "mutation_rate": "Mutation at birth",
    "reintroduce_after": "Reintroduce if extinct after (s)",
    "winter_wither": "Winter wither chance (/s)",
    "night_vision": "Night vision (fraction kept)",
    "winter_hunger": "Extra winter hunger",
    "day_length": "Day length (s)",
    "year_length": "Year length (s, 4 seasons)",
    "season_strength": "Season strength",
    "night_darkness": "Night darkness",
    "start_time": "Start time (s, on restart)",
    "seed": "Seed",
    "width_tiles": "Width (tiles)",
    "height_tiles": "Height (tiles)",
    "tile_size": "Tile size (px)",
    "terrain_scale": "Terrain feature size (tiles)",
    "climate_scale": "Climate zone size (tiles)",
    "water_level": "Water level (0..1)",
    "beach_width": "Beach width",
    "temperature_shift": "Warmer (+) / colder (-)",
    "moisture_shift": "Wetter (+) / drier (-)",
    "latitude_strength": "North-south temperature drop",
    "attack_damage": "Bite damage (hunting)",
    "defense_damage": "Bite-back damage",
    "attack_cooldown": "Seconds between bites",
    "herd_radius": "Herd radius (px)",
    "herd_bonus": "Bite-back bonus per herd peer",
    "crowd_penalty": "Avoids prey in crowds (per peer)",
    "herd_cohesion": "Herding (0..1)",
    "dominance": "Dominance in squabbles",
    "contest_damage": "Squabble bite damage",
    "contest_range": "Squabble range (px)",
    "yield_time": "Loser stays away (s)",
    "call_range": "Alarm call range (px, 0 = none)",
    "alarm_duration": "Flees after hearing a call (s)",
    "founder_variation": "Founder variation (on restart)",
}
TOOLTIPS = {
    "run_speed_multiplier": "Running speed = walk speed x this",
    "run_stamina_multiplier": "Running costs this many times the walking stamina",
    "relax_speed_ratio": "Relaxing speed as a fraction of walk speed",
    "hungry_ratio": "Starts foraging below this fraction of the food bar",
    "full_ratio": "Keeps foraging until this fraction of the food bar",
    "relaxed_ratio": "Relaxes when the food bar is above this (also when hurt or out of breath)",
    "rest_ratio": "Becomes tired below this fraction of stamina and rests (even if hungry) until rested",
    "sprint_range": "Hunters stalk at a walk and only sprint once prey is this close",
    "muscle_burn": "When stamina is empty, each stamina point still needed costs this much health",
    "digest_rate": "Food turned into stamina per second, while stamina isn't full",
    "hunger_boldness": "Chance (with an empty food bar) that hunger beats fear of a predator that isn't chasing",
    "nutrition": "Food a predator gains from eating this creature",
    "reintroduce_after": "If a species dies out, new founders arrive after this many seconds (0 = stays extinct)",
    "mutation_rate": "Typical change of each gene (speed, stamina, vision, boldness) from parent to child",
    "avoid_horizon": "How far ahead creatures predict each other's paths to avoid bumping (0 = off)",
}
# Arrow-button step per setting. Integers stay integers.
STEPS = {
    "min_spacing": 1, "seed_min_distance": 5, "seed_range": 10,
    "max_growth_timer": 1.0, "reproduction_delay": 1.0, "min_edible_level": 1,
    "initial_count": 1, "max_population": 1,
    "walk_speed": 1, "run_speed_multiplier": 0.05, "run_stamina_multiplier": 0.1,
    "relax_speed_ratio": 0.05, "turn_rate": 0.1, "vision_range": 10,
    "avoid_horizon": 0.1, "avoid_margin": 1,
    "max_health": 5, "max_stamina": 5, "max_food": 5, "birth_food": 5, "birth_stamina_ratio": 0.05,
    "alive_stamina_cost": 0.05, "walk_stamina_cost": 0.05, "food_drain": 0.05,
    "digest_rate": 0.1, "digest_efficiency": 0.05, "starve_ratio": 0.05, "starve_damage": 0.1,
    "muscle_burn": 0.05, "heal_rate": 0.1, "heal_stamina_cost": 0.1, "heal_food_cost": 0.1,
    "hungry_ratio": 0.05, "full_ratio": 0.05, "relaxed_ratio": 0.05, "rest_ratio": 0.05,
    "rested_ratio": 0.05, "sprint_range": 10,
    "reproduction_interval": 1.0, "reproduction_food_threshold": 5, "reproduction_health_ratio": 0.05,
    "reproduction_food_cost": 5,
    "hunger_boldness": 0.05, "boldness_interval": 0.5,
    "nutrition": 5, "corpse_duration": 1.0, "mutation_rate": 0.01, "founder_variation": 0.01,
    "reintroduce_after": 10.0,
    "night_vision": 0.05, "winter_hunger": 0.05, "winter_wither": 0.01,
    "day_length": 10.0, "year_length": 60.0, "season_strength": 0.05, "night_darkness": 0.05, "start_time": 10.0,
    "attack_damage": 1, "defense_damage": 1, "attack_cooldown": 0.1,
    "herd_radius": 5, "herd_bonus": 0.05, "crowd_penalty": 0.05, "herd_cohesion": 0.05,
    "dominance": 0.1, "contest_damage": 1, "contest_range": 5, "yield_time": 0.5,
    "call_range": 10, "alarm_duration": 0.5,
}
PLANT_STEPS = {"initial_count": 10}
# Decimal point and no thousands separators, whatever the system locale
NUMBER_LOCALE = QLocale.c()
NUMBER_LOCALE.setNumberOptions(QLocale.NumberOption.OmitGroupSeparator)
MINIMUMS = {"temperature_shift": -1.0, "moisture_shift": -1.0, "width_tiles": 40, "height_tiles": 30,
            "tile_size": 8, "terrain_scale": 5, "climate_scale": 5, "day_length": 10.0, "year_length": 60.0, "run_speed_multiplier": 1.05, "run_stamina_multiplier": 1.0, "boldness_interval": 0.1,
            "max_health": 5, "max_stamina": 5, "max_food": 5, "digest_efficiency": 0.05,
            "min_edible_level": 1}
MAXIMUMS = {"water_level": 0.9, "beach_width": 0.3, "temperature_shift": 1.0, "moisture_shift": 1.0,
            "width_tiles": 1000, "height_tiles": 1000, "tile_size": 64, "seed": 999999,
            "min_edible_level": 4, "hunger_boldness": 1.0, "herd_cohesion": 1.0, "night_vision": 1.0,
            "season_strength": 0.95, "night_darkness": 0.95}


MAP_STEPS = {"seed": 1, "width_tiles": 10, "height_tiles": 10, "tile_size": 1, "terrain_scale": 5,
             "climate_scale": 5, "water_level": 0.02, "beach_width": 0.01, "temperature_shift": 0.05,
             "moisture_shift": 0.05, "latitude_strength": 0.05}


def _step(section, key):
    if section == "plants" and key in PLANT_STEPS:
        return PLANT_STEPS[key]
    if section == "map":
        return MAP_STEPS.get(key, 1)
    if section == "biomes":
        return 0.05
    return STEPS.get(key, 1)


def _label(key):
    return LABELS.get(key, key.replace("_", " ").capitalize())


def _activate_app():
    """Bring this process to the front on macOS (Qt alone won't steal focus from another app)."""
    if sys.platform != "darwin":
        return
    try:
        from pyglet.libs.darwin.cocoapy import ObjCClass
        ObjCClass("NSApplication").sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        pass


class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EvoTales settings")
        self.values = settings.current_values()
        self.view_options = settings.display_options()
        self.inputs = {}       # (section, key) -> spin box
        self.diet_boxes = {}   # (section, food) -> check box
        self._loading = False

        layout = QVBoxLayout(self)

        view = QGroupBox("View (applies immediately)")
        view_row = QHBoxLayout(view)
        for key, text in (("show_fov", "Show field of view"), ("show_energy", "Show health / stamina / food bars")):
            box = QCheckBox(text)
            box.setChecked(self.view_options[key])
            box.toggled.connect(lambda checked, k=key: self.toggle_view(k, checked))
            view_row.addWidget(box)
        view_row.addStretch()
        layout.addWidget(view)

        self.tabs = QTabWidget()
        for section in settings.SECTIONS:
            self.tabs.addTab(self._build_tab(section), section.capitalize())
        self.tabs.setCurrentIndex(list(settings.SECTIONS).index("herbivores"))
        layout.addWidget(self.tabs, stretch=1)

        buttons = QHBoxLayout()
        for text, slot in (("Apply live", lambda: self.apply(False)),
                           ("Apply + restart", lambda: self.apply(True)),
                           ("Reset tab to defaults", self.reset_tab)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        presets = QGroupBox("Presets (scenarios)")
        row = QHBoxLayout(presets)
        self.preset_box = QComboBox()
        self.preset_box.setMinimumWidth(220)
        row.addWidget(self.preset_box)
        for text, slot in (("Load", self.load_preset), ("Save as...", self.save_preset),
                           ("Delete", self.delete_preset)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            row.addWidget(button)
        row.addStretch()
        layout.addWidget(presets)
        self._refresh_presets()

        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.warnings = QLabel()
        self.warnings.setWordWrap(True)
        self.warnings.setStyleSheet("color: #d9534f;")
        layout.addWidget(self.warnings)
        self._refresh_warnings()
        self.resize(800, 860)

    # ------------------------------------------------------------------ layout

    def _build_tab(self, section):
        page = QWidget()
        grid = QGridLayout(page)
        grid.setHorizontalSpacing(16)
        numeric = [k for k in settings.editable_keys(section) if k != "diet"]
        half = (len(numeric) + 1) // 2
        for i, key in enumerate(numeric):
            col, row = divmod(i, half)
            label = QLabel(_label(key))
            spin = self._spin_box(section, key)
            if key in TOOLTIPS:
                label.setToolTip(TOOLTIPS[key])
                spin.setToolTip(TOOLTIPS[key])
            grid.addWidget(label, row, col * 2)
            grid.addWidget(spin, row, col * 2 + 1)
            self.inputs[(section, key)] = spin
        if "diet" in settings.editable_keys(section):
            diet = QGroupBox("Eats")
            diet_row = QHBoxLayout(diet)
            for food in FOOD_LAYERS:
                if food == section:
                    continue
                box = QCheckBox(food)
                box.setChecked(food in self.values[section]["diet"])
                box.toggled.connect(lambda checked, s=section, f=food: self.set_diet(s, f, checked))
                diet_row.addWidget(box)
                self.diet_boxes[(section, food)] = box
            diet_row.addStretch()
            grid.addWidget(diet, half, 0, 1, 4)
        if section == "map":
            row = QHBoxLayout()
            for text, slot in (("New random seed", self.random_seed), ("Regenerate map", lambda: self.apply(True))):
                button = QPushButton(text)
                button.clicked.connect(slot)
                row.addWidget(button)
            row.addStretch()
            box = QWidget()
            box.setLayout(row)
            grid.addWidget(box, half + 1, 0, 1, 4)
            note = QLabel("Map changes take effect when the map is regenerated (Apply + restart).")
            note.setWordWrap(True)
            grid.addWidget(note, half + 2, 0, 1, 4)
        grid.setRowStretch(half + 3, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def _spin_box(self, section, key):
        value = self.values[section][key]
        step = _step(section, key)
        is_int = isinstance(value, int) and isinstance(step, int)
        maximum = MAXIMUMS.get(key, 1.0 if key.endswith("ratio") else 100000)
        if is_int:
            spin = QSpinBox()
            spin.setRange(int(MINIMUMS.get(key, 0)), int(maximum))
        else:
            spin = QDoubleSpinBox()
            text = f"{step}"
            spin.setDecimals(max(len(text.split(".")[1]) if "." in text else 0, 1))
            spin.setRange(MINIMUMS.get(key, 0.0), maximum)
        spin.setLocale(NUMBER_LOCALE)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.setMinimumWidth(100)
        spin.valueChanged.connect(
            lambda v, s=section, k=key, i=is_int: self.set_value(s, k, int(v) if i else round(v, 4)))
        return spin

    # ----------------------------------------------------------------- actions

    def set_value(self, section, key, value):
        if self._loading:
            return
        self.values[section][key] = value
        self._mark_pending()

    def set_diet(self, section, food, checked):
        if self._loading:
            return
        diet = self.values[section]["diet"]
        if checked and food not in diet:
            diet.append(food)
        elif not checked and food in diet:
            diet.remove(food)
        self._mark_pending()

    def toggle_view(self, key, checked):
        self.view_options[key] = checked
        settings.save_display(self.view_options)

    def reset_tab(self):
        section = list(settings.SECTIONS)[self.tabs.currentIndex()]
        self.values[section] = {k: copy.deepcopy(settings.DEFAULTS[section][k])
                                for k in settings.editable_keys(section)}
        self._loading = True
        for (s, key), spin in self.inputs.items():
            if s == section:
                spin.setValue(self.values[section][key])
        for (s, food), box in self.diet_boxes.items():
            if s == section:
                box.setChecked(food in self.values[section]["diet"])
        self._loading = False
        self._mark_pending(f"{section.capitalize()}: code defaults restored, not applied yet.")

    def random_seed(self):
        import random
        self.inputs[("map", "seed")].setValue(random.randint(0, 999999))
        self._mark_pending("New seed picked. Regenerate map to see it.")

    # ---------------------------------------------------------------- presets

    def _refresh_presets(self, select=None):
        self.preset_box.clear()
        names = settings.list_presets()
        self.preset_box.addItems(names)
        if select in names:
            self.preset_box.setCurrentText(select)

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:",
                                        text=self.preset_box.currentText())
        if not ok or not name.strip():
            return
        for spin in self.inputs.values():
            spin.interpretText()
        try:
            saved = settings.save_preset(name, self.values)
        except ValueError as e:
            QMessageBox.warning(self, "Save preset", str(e))
            return
        self._refresh_presets(select=saved)
        self.status.setText(f"Saved preset '{saved}' (every tab).")

    def load_preset(self):
        name = self.preset_box.currentText()
        if not name:
            return
        self.values = settings.load_preset(name)
        self._show_values()
        self._mark_pending(f"Loaded preset '{name}' into the form. Apply + restart to run it as a scenario.")

    def delete_preset(self):
        name = self.preset_box.currentText()
        if not name or QMessageBox.question(self, "Delete preset", f"Delete preset '{name}'?") \
                != QMessageBox.StandardButton.Yes:
            return
        settings.delete_preset(name)
        self._refresh_presets()
        self.status.setText(f"Deleted preset '{name}'.")

    def _show_values(self):
        """Put self.values into every field without marking them as user edits."""
        self._loading = True
        for (section, key), spin in self.inputs.items():
            spin.setValue(self.values[section][key])
        for (section, food), box in self.diet_boxes.items():
            box.setChecked(food in self.values[section]["diet"])
        self._loading = False

    def apply(self, restart):
        # A number still being typed counts (buttons on macOS don't take focus, so the
        # field never gets the "editing finished" that would commit it)
        for spin in self.inputs.values():
            spin.interpretText()
        problems = settings.speed_warnings(self.values)
        if problems and QMessageBox.question(
                self, "Predators too slow", "\n".join(problems) + "\n\nApply anyway?"
        ) != QMessageBox.StandardButton.Yes:
            return
        settings.save(self.values, restart=restart)
        self.status.setText("Applied. The simulation is restarting." if restart
                            else "Applied live. Initial counts and min spacing take effect on restart.")

    def _mark_pending(self, text="Changes not applied yet."):
        self.status.setText(text)
        self._refresh_warnings()

    def _refresh_warnings(self):
        self.warnings.setText("\n".join(settings.speed_warnings(self.values)))

    def bring_to_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        _activate_app()


def main():
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    window.bring_to_front()

    # The simulation's Settings button sends SIGUSR1 when this window is already open.
    # Python only runs signal handlers between bytecodes, so a timer keeps it ticking.
    raise_requested = []
    signal.signal(signal.SIGUSR1, lambda *_: raise_requested.append(True))
    signal.signal(signal.SIGTERM, lambda *_: app.quit())

    def poll_signals():
        if raise_requested:
            raise_requested.clear()
            window.bring_to_front()

    timer = QTimer()
    timer.timeout.connect(poll_signals)
    timer.start(200)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
