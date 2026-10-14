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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDoubleSpinBox, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QSpinBox,
                               QTabWidget, QVBoxLayout, QWidget)

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
    "alive_energy_cost": "Alive energy cost (/s)",
    "walk_energy_cost": "Walk energy cost (/s)",
    "reproduction_interval": "Reproduction interval (s)",
    "boldness_interval": "Boldness re-roll (s)",
    "corpse_duration": "Corpse duration (s)",
}
TOOLTIPS = {
    "run_speed_multiplier": "Running speed = walk speed x this",
    "run_energy_multiplier": "Running costs this many times the walking energy",
    "relax_speed_ratio": "Relaxing speed as a fraction of walk speed",
    "hungry_ratio": "Starts foraging below this fraction of max energy",
    "full_ratio": "Keeps foraging until this fraction of max energy",
    "relaxed_ratio": "Relaxes above this fraction when not foraging",
    "hunger_boldness": "Chance (at zero energy) that hunger beats fear of a predator that isn't chasing",
    "nutrition": "Energy a predator gains from eating this creature",
    "avoid_horizon": "How far ahead creatures predict each other's paths to avoid bumping (0 = off)",
}
# Arrow-button step per setting. Integers stay integers.
STEPS = {
    "min_spacing": 1, "seed_min_distance": 5, "seed_range": 10,
    "max_growth_timer": 1.0, "reproduction_delay": 1.0, "min_edible_level": 1,
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
# Decimal point and no thousands separators, whatever the system locale
NUMBER_LOCALE = QLocale.c()
NUMBER_LOCALE.setNumberOptions(QLocale.NumberOption.OmitGroupSeparator)
MINIMUMS = {"run_speed_multiplier": 1.05, "run_energy_multiplier": 1.0, "boldness_interval": 0.1,
            "max_energy": 5, "min_edible_level": 1}
MAXIMUMS = {"min_edible_level": 4, "hunger_boldness": 1.0}


def _step(section, key):
    if section == "plants" and key in PLANT_STEPS:
        return PLANT_STEPS[key]
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
        for key, text in (("show_fov", "Show field of view"), ("show_energy", "Show energy bars")):
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

        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.warnings = QLabel()
        self.warnings.setWordWrap(True)
        self.warnings.setStyleSheet("color: #d9534f;")
        layout.addWidget(self.warnings)
        self._refresh_warnings()
        self.resize(780, 690)

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
        grid.setRowStretch(half + 1, 1)
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
        spin.setKeyboardTracking(False)  # typing commits on Enter / focus change, not per keystroke
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

    def apply(self, restart):
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
