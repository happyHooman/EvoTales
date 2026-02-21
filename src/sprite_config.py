"""
Configuration for sprites and sprite sheets.
"""

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
SPRITE_CONFIGS = {
    "creatures": {
        "plant_stage_1": (0, s_width, s_width, s_height, 0.4),    # First stage plant
        "plant_stage_2": (s_width, s_width, s_width, s_height, 0.4),   # Second stage plant
        "plant_stage_3": (2 * s_width, s_width, s_width, s_height, 0.4),   # Third stage plant
        "plant_stage_4": (0, 0, s_width, s_height, 0.4),  # Fully grown plant
        "herbivore": (0, 2 * s_height, s_width, s_height, 0.4),       # Herbivore creature
        "carnivore": (s_width, 2 * s_height, s_width, s_height, 0.4),      # Carnivore creature
        "smartie": (2 * s_width, 2 * s_height, s_width, s_height, 0.4),        # Smart creature
    }
}

