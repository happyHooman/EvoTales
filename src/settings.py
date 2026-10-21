"""
User settings: overrides on top of config.py, stored in settings.json.

The settings window writes the file; the simulation watches it, applies the
values live, and restarts when asked to. Both run as separate processes, so the
file is the only thing they share.
"""
import copy
import json
import os

from config import (BIOME_CONFIG, CARNIVORE_CONFIG, CREATURE_DEFAULTS, ENVIRONMENT_CONFIG, HERBIVORE_CONFIG,
                    MAP_CONFIG, PLANT_CONFIG, SMARTIE_CONFIG, SPECIES_BIOME_CONFIG)
from world.mapgen import BIOMES, BLOCKED_BIOMES

SETTINGS_PATH = "settings.json"
RESTART_KEY = "_restart"
DISPLAY_KEY = "display"
DISPLAY_DEFAULTS = {"show_fov": False, "show_energy": False}

SECTIONS = {
    "map": MAP_CONFIG,
    "biomes": BIOME_CONFIG,
    "world": ENVIRONMENT_CONFIG,
    "plants": PLANT_CONFIG,
    "herbivores": HERBIVORE_CONFIG,
    "smarties": SMARTIE_CONFIG,
    "carnivores": CARNIVORE_CONFIG,
    "species_biomes": SPECIES_BIOME_CONFIG,  # flattened to "species.biome.param" keys below
}
NON_CREATURE_SECTIONS = ("map", "biomes", "world", "plants", "species_biomes")
CREATURE_SECTIONS = [name for name in SECTIONS if name not in NON_CREATURE_SECTIONS]
MAP_KEYS = ["seed", "width_tiles", "height_tiles", "tile_size", "terrain_scale", "climate_scale",
            "water_level", "beach_width", "temperature_shift", "moisture_shift", "latitude_strength"]
BIOME_KEYS = list(BIOME_CONFIG)
WORLD_KEYS = ["sim_speed", "day_length", "year_length", "season_strength", "night_darkness", "start_time"]

PLANT_KEYS = [
    "initial_count", "min_spacing", "seed_min_distance", "seed_range",
    "max_growth_timer", "reproduction_delay", "min_edible_level", "regrow_time", "winter_wither",
]
CREATURE_KEYS = [
    "initial_count", "max_population",
    "walk_speed", "run_speed_multiplier", "run_stamina_multiplier", "relax_speed_ratio",
    "turn_rate", "vision_range", "avoid_horizon", "avoid_margin",
    "max_health", "max_stamina", "max_food", "birth_food", "birth_stamina_ratio",
    "alive_stamina_cost", "walk_stamina_cost", "food_drain", "digest_rate", "digest_efficiency",
    "starve_ratio", "starve_damage", "muscle_burn", "heal_rate", "heal_stamina_cost", "heal_food_cost",
    "hungry_ratio", "full_ratio", "relaxed_ratio", "rest_ratio", "rested_ratio", "sprint_range",
    "hunger_boldness", "boldness_interval",
    "reproduction_interval", "reproduction_food_threshold", "reproduction_health_ratio",
    "reproduction_food_cost",
    "mutation_rate", "founder_variation", "night_vision", "winter_hunger",
    "attack", "rival_bite", "attack_cooldown",
    "personal_space", "crowd_limit", "crowd_damage", "aggression",
    "herd_radius", "herd_bonus", "crowd_penalty", "herd_cohesion",
    "dominance", "contest_range", "yield_time",
    "call_range", "alarm_duration",
    "nutrition", "corpse_duration", "reintroduce_after", "diet",
]
CREATURE_KEYS.insert(CREATURE_KEYS.index("night_vision"), "visibility")
# Creature parameters a biome can scale per species (everything numeric except bookkeeping)
BIOME_PARAM_KEYS = [k for k in CREATURE_KEYS if k not in (
    "initial_count", "max_population", "mutation_rate", "founder_variation", "reintroduce_after", "diet")]
LAND_BIOMES = [b for i, b in enumerate(BIOMES) if i not in BLOCKED_BIOMES]
SPECIES_BIOME_KEYS = [f"{sp}.{b}.{k}" for sp in ("herbivores", "smarties", "carnivores")
                      for b in LAND_BIOMES for k in BIOME_PARAM_KEYS]


def _flatten_species_biomes(nested: dict) -> dict:
    flat = {key: 1.0 for key in SPECIES_BIOME_KEYS}
    for sp, biomes in nested.items():
        for b, params in biomes.items():
            for k, v in params.items():
                flat[f"{sp}.{b}.{k}"] = v
    return flat


def _apply_species_biomes(flat: dict) -> None:
    """Rebuild the nested SPECIES_BIOME_CONFIG in place (keeping only multipliers != 1)."""
    nested = {}
    for key, value in flat.items():
        if value != 1.0:
            sp, b, k = key.split(".")
            nested.setdefault(sp, {}).setdefault(b, {})[k] = value
    SPECIES_BIOME_CONFIG.clear()
    SPECIES_BIOME_CONFIG.update(nested)


# Only take effect when the world is rebuilt
RESTART_ONLY_KEYS = {"initial_count", "min_spacing"}


def editable_keys(section: str) -> list[str]:
    return {"plants": PLANT_KEYS, "world": WORLD_KEYS, "map": MAP_KEYS, "biomes": BIOME_KEYS,
            "species_biomes": SPECIES_BIOME_KEYS}.get(section, CREATURE_KEYS)


def _effective(section: str) -> dict:
    cfg = SECTIONS[section]
    if section == "species_biomes":
        return _flatten_species_biomes(cfg)
    return dict(cfg) if section in NON_CREATURE_SECTIONS else {**CREATURE_DEFAULTS, **cfg}


# Code defaults, captured before any overrides are applied
DEFAULTS = {section: copy.deepcopy(_effective(section)) for section in SECTIONS}


def current_values(data: dict | None = None) -> dict:
    """Editable values per section: code defaults plus overrides (from settings.json,
    or from `data`, e.g. a preset)."""
    values = {s: {k: copy.deepcopy(DEFAULTS[s][k]) for k in editable_keys(s)} for s in SECTIONS}
    for section, overrides in (load() if data is None else data).items():
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


def _diff_from_defaults(values: dict) -> dict:
    data = {}
    for section, entries in values.items():
        diff = {k: v for k, v in entries.items() if v != DEFAULTS[section].get(k)}
        if diff:
            data[section] = diff
    return data


def save(values: dict, restart: bool = False) -> None:
    """Store values that differ from the code defaults. Written atomically."""
    previous = load()
    data = _diff_from_defaults(values)
    data[RESTART_KEY] = previous.get(RESTART_KEY, 0) + (1 if restart else 0)
    if DISPLAY_KEY in previous:
        data[DISPLAY_KEY] = previous[DISPLAY_KEY]
    _write(data)


# Presets: named scenarios, saved as the differences from the code defaults
PRESETS_DIR = "presets"


def list_presets() -> list[str]:
    try:
        return sorted(f[:-5] for f in os.listdir(PRESETS_DIR) if f.endswith(".json"))
    except OSError:
        return []


def _preset_path(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in " -_").strip()
    if not safe:
        raise ValueError("Preset name needs letters or numbers")
    return os.path.join(PRESETS_DIR, safe + ".json")


def save_preset(name: str, values: dict) -> str:
    os.makedirs(PRESETS_DIR, exist_ok=True)
    path = _preset_path(name)
    with open(path, "w") as f:
        json.dump(_diff_from_defaults(values), f, indent=2)
    return os.path.splitext(os.path.basename(path))[0]


def load_preset(name: str) -> dict:
    """The preset's full set of editable values (defaults where it doesn't say)."""
    with open(_preset_path(name)) as f:
        return current_values(json.load(f))


def delete_preset(name: str) -> None:
    os.remove(_preset_path(name))


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
        if section == "species_biomes":
            _apply_species_biomes({k: overrides.get(k, DEFAULTS[section][k]) for k in SPECIES_BIOME_KEYS})
            continue
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
