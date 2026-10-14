"""
User settings: overrides on top of config.py, stored in settings.json.

The settings window writes the file; the simulation watches it, applies the
values live, and restarts when asked to. Both run as separate processes, so the
file is the only thing they share.
"""
import copy
import json
import os

from config import (CARNIVORE_CONFIG, CREATURE_DEFAULTS, HERBIVORE_CONFIG, OMNIVORE_CONFIG,
                    PLANT_CONFIG, SMARTIE_CONFIG)

SETTINGS_PATH = "settings.json"
RESTART_KEY = "_restart"
DISPLAY_KEY = "display"
DISPLAY_DEFAULTS = {"show_fov": False, "show_energy": False}

SECTIONS = {
    "plants": PLANT_CONFIG,
    "herbivores": HERBIVORE_CONFIG,
    "omnivores": OMNIVORE_CONFIG,
    "carnivores": CARNIVORE_CONFIG,
    "smarties": SMARTIE_CONFIG,
}
CREATURE_SECTIONS = [name for name in SECTIONS if name != "plants"]

PLANT_KEYS = [
    "initial_count", "min_spacing", "seed_min_distance", "seed_range",
    "max_growth_timer", "reproduction_delay", "min_edible_level",
]
CREATURE_KEYS = [
    "initial_count", "max_population",
    "walk_speed", "run_speed_multiplier", "run_energy_multiplier", "relax_speed_ratio",
    "turn_rate", "vision_range",
    "max_energy", "birth_energy", "alive_energy_cost", "walk_energy_cost",
    "hungry_ratio", "full_ratio", "relaxed_ratio",
    "reproduction_interval", "reproduction_energy_threshold", "reproduction_energy_cost",
    "nutrition", "corpse_duration", "diet",
]
# Only take effect when the world is rebuilt
RESTART_ONLY_KEYS = {"initial_count", "min_spacing"}


def editable_keys(section: str) -> list[str]:
    return PLANT_KEYS if section == "plants" else CREATURE_KEYS


def _effective(section: str) -> dict:
    cfg = SECTIONS[section]
    return dict(cfg) if section == "plants" else {**CREATURE_DEFAULTS, **cfg}


# Code defaults, captured before any overrides are applied
DEFAULTS = {section: copy.deepcopy(_effective(section)) for section in SECTIONS}


def current_values() -> dict:
    """Editable values per section, from the code defaults plus saved overrides."""
    values = {s: {k: copy.deepcopy(DEFAULTS[s][k]) for k in editable_keys(s)} for s in SECTIONS}
    for section, overrides in load().items():
        if section in values:
            for key, value in overrides.items():
                if key in values[section]:
                    values[section][key] = value
    return values


def load() -> dict:
    try:
        with open(SETTINGS_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(values: dict, restart: bool = False) -> None:
    """Store values that differ from the code defaults. Written atomically."""
    previous = load()
    data = {}
    for section, entries in values.items():
        diff = {k: v for k, v in entries.items() if v != DEFAULTS[section].get(k)}
        if diff:
            data[section] = diff
    data[RESTART_KEY] = previous.get(RESTART_KEY, 0) + (1 if restart else 0)
    if DISPLAY_KEY in previous:
        data[DISPLAY_KEY] = previous[DISPLAY_KEY]
    _write(data)


def display_options(data: dict | None = None) -> dict:
    """Overlay toggles (field of view, energy bars), with defaults filled in."""
    data = load() if data is None else data
    return {**DISPLAY_DEFAULTS, **data.get(DISPLAY_KEY, {})}


def save_display(options: dict) -> None:
    """Store the overlay toggles without touching the simulation values."""
    data = load()
    data[DISPLAY_KEY] = {k: bool(options.get(k, v)) for k, v in DISPLAY_DEFAULTS.items()}
    _write(data)


def _write(data: dict) -> None:
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, SETTINGS_PATH)


def apply(data: dict) -> None:
    """Apply saved overrides to the live config dicts (values not overridden go back to defaults)."""
    for section, cfg in SECTIONS.items():
        overrides = data.get(section, {})
        for key in editable_keys(section):
            value = overrides.get(key, DEFAULTS[section][key])
            cfg[key] = copy.deepcopy(value)


def speed_warnings(values: dict) -> list[str]:
    """Predators must be able to outrun their prey."""
    run = {s: values[s]["walk_speed"] * values[s]["run_speed_multiplier"] for s in CREATURE_SECTIONS}
    warnings = []
    for hunter in CREATURE_SECTIONS:
        for prey in values[hunter]["diet"]:
            if prey in run and run[hunter] <= run[prey]:
                warnings.append(f"{hunter} can't outrun {prey} ({run[hunter]:.0f} vs {run[prey]:.0f} px/s)")
    return warnings


class SettingsWatcher:
    """Polls settings.json; reports whether values changed and whether a restart was requested."""

    def __init__(self):
        self._mtime = self._stat()
        self._restart = load().get(RESTART_KEY, 0)

    @staticmethod
    def _stat():
        try:
            return os.stat(SETTINGS_PATH).st_mtime_ns
        except OSError:
            return None

    def poll(self):
        """Returns (data, restart_requested), or (None, False) when nothing changed."""
        mtime = self._stat()
        if mtime == self._mtime:
            return None, False
        self._mtime = mtime
        data = load()
        restart = data.get(RESTART_KEY, 0) != self._restart
        self._restart = data.get(RESTART_KEY, 0)
        return data, restart
