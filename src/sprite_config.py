"""
Configuration for sprites and sprite sheets.
"""
import math

# Sprite art faces down. body.angle = 0 means right. Offset so sprite matches velocity.
# Shared by herbivore, carnivore, smartie.
SPRITE_ANGLE_OFFSET = math.pi / 2

# Sprite sheet paths
SPRITE_SHEETS = {
    # "creatures": "assets/images/sprites2.png",
    "creatures": "assets/images/sprites3.png",
}

# s_width = 40
# s_height = 40
s_width = 100
s_height = 100

# Sprite configurations
# Format: (left, bottom, width, height, scale)
SCALE = 0.15
SPRITE_CONFIGS = {
    "creatures": {
        "plant_stage_1": (0, s_width, s_width, s_height, SCALE),    # First stage plant
        "plant_stage_2": (s_width, s_width, s_width, s_height, SCALE),   # Second stage plant
        "plant_stage_3": (2 * s_width, s_width, s_width, s_height, SCALE),   # Third stage plant
        "plant_stage_4": (0, 0, s_width, s_height, SCALE),  # Fully grown plant
        "herbivore": (0, 2 * s_height, s_width, s_height, .2),       # Herbivore creature
        "carnivore": (s_width, 2 * s_height, s_width, s_height, SCALE),      # Carnivore creature
        "smartie": (2 * s_width, 2 * s_height, s_width, s_height, SCALE),        # Smart creature
    }
}

