from arcade import PymunkPhysicsEngine

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
    "PAN_RATE": 400,
    "MIN_ZOOM": 0.1,
    "MAX_ZOOM": 4.0,
    "PADDING": 20.0,
}

# Plant configuration
PLANT_CONFIG = {
    "initial_count": 100,
    "min_spacing": 30,
    "bounds_padding": 20,
    "seed_min_distance": 50,
    "seed_range": 500,
    "max_growth_level": 4,
    "max_growth_timer": 10,
    "reproduction_delay": 20,
    "growth_textures": [
        "plant_stage_1",
        "plant_stage_2",
        "plant_stage_3",
        "plant_stage_4",
    ],
    "reproduction": {
        "factor": 1.2,
        "max_fails": 5,
        "max_successes": 3,
    },
    "provided_energy": [10, 20, 30, 50],
    "min_edible_level": 2,  # grazing resets a plant to stage 1; seedlings can't be eaten
    "physics": {
        "collision_type": "plant",
        "body_type": PymunkPhysicsEngine.STATIC,
    },
}

# Creature configuration.
# CREATURE_DEFAULTS holds shared values; each species dict overrides what it needs
# (merged in Creature.__init_subclass__). Rates are per second unless noted.
_CREATURE_PHYSICS = {
    "moment_of_inertia": PymunkPhysicsEngine.MOMENT_INF,
    "damping": 0.9,
}

CREATURE_DEFAULTS = {
    "initial_count": 0,
    "max_population": 30,
    "bounds_padding": 40,
    # Movement
    "wander_speed": 25,        # pixels per second while wandering
    "run_speed": 60,           # pixels per second while chasing / fleeing
    "turn_rate": 3.0,          # radians per second (smooth turning)
    "wander_turn_interval": 4.0,  # seconds between random heading changes
    "wall_probe_distance": 28,  # how far ahead to look for water/walls
    # Senses and brain
    "vision_range": 200,
    "think_interval": 0.2,     # seconds between brain decisions (steering runs every frame)
    # Energy
    "initial_energy": 60,
    "max_energy": 150,
    "base_energy_drain": 0.5,  # per second, even when resting
    "move_energy_factor": 0.0002,  # extra drain per second = factor * speed^2
    "hungry_ratio": 0.7,       # looks for food below this fraction of max_energy
    "eat_range": 10,           # extra reach beyond touching, in pixels
    # Life cycle
    "max_age": 300,            # seconds
    "reproduction_energy_threshold": 120,
    "reproduction_cooldown": 20.0,
    "energy_cost_reproduction": 50,
    "child_energy": 40,
    # Diet: layer names this creature eats, and layers it runs away from
    "diet": [],
    "threats": [],
    "nutrition": 50,           # energy a predator gains when eating this creature
    "physics": _CREATURE_PHYSICS,
}

HERBIVORE_CONFIG = {
    "initial_count": 12,
    "max_population": 60,
    "wander_speed": 25,
    "run_speed": 65,
    "turn_rate": 3.0,
    "vision_range": 200,
    "max_age": 240,
    "reproduction_energy_threshold": 110,
    "diet": ["plants"],
    "threats": ["carnivores"],
    "nutrition": 70,
}

CARNIVORE_CONFIG = {
    "initial_count": 3,
    "max_population": 12,
    "wander_speed": 30,
    "run_speed": 75,
    "turn_rate": 3.5,
    "vision_range": 250,
    "initial_energy": 100,
    "max_energy": 200,
    "base_energy_drain": 0.7,
    "max_age": 360,
    "reproduction_energy_threshold": 170,
    "reproduction_cooldown": 30.0,
    "energy_cost_reproduction": 80,
    "child_energy": 70,
    "diet": ["herbivores", "smarties"],
    "nutrition": 90,
}

SMARTIE_CONFIG = {
    "initial_count": 4,
    "max_population": 20,
    "wander_speed": 22,
    "run_speed": 60,
    "turn_rate": 2.5,
    "vision_range": 300,
    "max_age": 420,
    "reproduction_energy_threshold": 130,
    "reproduction_cooldown": 25.0,
    "diet": ["plants"],
    "threats": ["carnivores"],
    "nutrition": 80,
}

# Physics settings
DEFAULT_DAMPING = .6
GRAVITY = (0, 0)
