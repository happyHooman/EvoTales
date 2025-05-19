"""
Configuration for sprites and sprite sheets.
"""

# Sprite sheet paths
SPRITE_SHEETS = {
    "creatures": "assets/images/sprites2.png",
}

# Sprite configurations
# Format: (left, bottom, width, height)
SPRITE_CONFIGS = {
    "creatures": {
        "plant_stage_1": (0, 40, 40, 40),    # First stage plant
        "plant_stage_2": (40, 40, 40, 40),   # Second stage plant
        "plant_stage_3": (80, 40, 40, 40),   # Third stage plant
        "plant_stage_4": (0, 0, 40, 40),  # Fully grown plant
        "herbivore": (0, 80, 40, 40),       # Herbivore creature
        "carnivore": (40, 80, 40, 40),      # Carnivore creature
        "smartie": (80, 80, 40, 40),        # Smart creature
    }
} 