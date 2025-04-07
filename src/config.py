# Window settings (visible area)
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
SCREEN_TITLE = "EvoTales"

# World settings remain unchanged
WORLD_WIDTH = 3000
WORLD_HEIGHT = 3000

# Camera settings
CAMERA_SETTINGS = {
    "ZOOM_IN": "zoom_in",
    "ZOOM_OUT": "zoom_out",
    "ZOOM_FACTOR": 1.2,
    "PAN_RATE": 300,
    "MIN_ZOOM": 0.1,
    "MAX_ZOOM": 4.0,
    "PADDING": 20.0,
}

# Walking creature configuration
WALKING_CREATURE_CONFIG = {
    "default": {
        "base_speed": 50,                   # Base walking speed (pixels per second)
        "max_speed": 120,                   # Maximum speed (for running)
        "energy_consumption_factor": 0.0005,  # Factor for energy consumption proportional to speed² and mass
        "base_energy_consumption": 0.1,     # Energy consumed per update when stationary
        "vision_range": 150,                # Default vision range in pixels
        "vision_angle": 90,                 # Default vision angle in degrees
        "reproduction_energy_threshold": 100,  # Default energy threshold for reproduction
        "reproduction_delay": 5.0,          # Default seconds between reproductions
        "energy_cost_reproduction": 25,     # Default energy cost for reproduction
    },
    "herbivore": {
        "vision_range": 200,
        "vision_angle": 90,
        "reproduction_energy_threshold": 150,
        "reproduction_delay": 5.0,
        "energy_cost_reproduction": 30,
    },
    "carnivore": {
        "vision_range": 250,
        "vision_angle": 100,
        "reproduction_energy_threshold": 200,
        "reproduction_delay": 7.0,
        "energy_cost_reproduction": 40,
    },
    "smarty": {
        "vision_range": 300,
        "vision_angle": 110,
        "reproduction_energy_threshold": 180,
        "reproduction_delay": 6.0,
        "energy_cost_reproduction": 35,
    },
}
