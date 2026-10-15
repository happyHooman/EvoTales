"""
Environment: the world clock, day/night and seasons.

Each step it advances time and publishes multipliers the rest of the world reads:
- plant_growth: how fast plants grow and seed (lush summer, near-dormant winter)
- per species: vision (night shortens sight, by each species' night_vision) and
  food_drain (cold winters burn food faster, by winter_hunger)
It also says how dark and what tint the screen should be.
"""
import math

import numpy as np

from config import ENVIRONMENT_CONFIG

SEASONS = ("spring", "summer", "autumn", "winter")
# Ground tint per season (r, g, b, alpha), blended between neighbouring seasons
SEASON_TINT = {
    "spring": (0.0, 0.0, 0.0, 0.0),
    "summer": (1.0, 0.85, 0.3, 0.08),
    "autumn": (0.75, 0.4, 0.1, 0.16),
    "winter": (0.9, 0.95, 1.0, 0.3),
}
NIGHT_TINT = (0.02, 0.03, 0.12)


class Environment:
    def __init__(self, species_types):
        self.species_types = list(species_types)
        self.time = ENVIRONMENT_CONFIG["start_time"]
        self.plant_growth = 1.0
        n = len(self.species_types)
        self.vision = np.ones(n)
        self.food_drain = np.ones(n)
        self.step(0.0)

    @property
    def config(self):
        return ENVIRONMENT_CONFIG

    def step(self, dt):
        cfg = ENVIRONMENT_CONFIG
        self.time += dt
        self.daylight = self._daylight()
        self.season_pos = (self.time / cfg["year_length"]) % 1.0  # 0 = start of spring
        warmth = math.sin(2 * math.pi * (self.season_pos - 0.125))  # peaks mid-summer, lowest mid-winter
        swing = cfg["season_strength"]
        self.plant_growth = max(0.05, 1.0 + swing * warmth)
        cold = max(0.0, -warmth) * swing
        dark = 1.0 - self.daylight
        for i, s in enumerate(self.species_types):
            c = s.config
            self.vision[i] = 1.0 - dark * (1.0 - c["night_vision"])
            self.food_drain[i] = 1.0 + cold * c["winter_hunger"]

    def _daylight(self):
        """1 at noon, 0 at midnight, with soft dawn and dusk."""
        cfg = ENVIRONMENT_CONFIG
        phase = (self.time / cfg["day_length"]) % 1.0  # 0 = midnight
        sun = -math.cos(2 * math.pi * phase)            # -1 midnight, 1 noon
        return float(np.clip(0.5 + sun, 0.0, 1.0))

    @property
    def season(self):
        return SEASONS[int(self.season_pos * 4) % 4]

    @property
    def day(self):
        return int(self.time // ENVIRONMENT_CONFIG["day_length"]) + 1

    @property
    def clock(self):
        phase = (self.time / ENVIRONMENT_CONFIG["day_length"]) % 1.0
        minutes = int(phase * 24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def screen_tint(self):
        """(r, g, b, a) to lay over the world: season colour plus night darkness."""
        pos = self.season_pos * 4
        a, b = SEASON_TINT[SEASONS[int(pos) % 4]], SEASON_TINT[SEASONS[(int(pos) + 1) % 4]]
        f = pos - int(pos)
        tint = [a[k] * (1 - f) + b[k] * f for k in range(4)]
        night = (1.0 - self.daylight) * ENVIRONMENT_CONFIG["night_darkness"]
        if night > tint[3]:
            mix = night / max(night + tint[3], 1e-6)
            rgb = [NIGHT_TINT[k] * mix + tint[k] * (1 - mix) for k in range(3)]
            return (*rgb, night)
        return tuple(tint)
