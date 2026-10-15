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
# Energy is spent on being alive, walking, running and reproducing. Running is
# run_speed_multiplier times faster than walking and costs run_energy_multiplier
# times the walking energy. Relaxing creatures drift very slowly and only pay
# the cost of being alive.
_CREATURE_PHYSICS = {
    "moment_of_inertia": PymunkPhysicsEngine.MOMENT_INF,
    "damping": 0.9,
}

CREATURE_DEFAULTS = {
    "initial_count": 0,
    "max_population": 30,
    "bounds_padding": 40,
    # Movement
    "walk_speed": 30,              # pixels per second
    "run_speed_multiplier": 1.5,   # running is 50% faster...
    "run_energy_multiplier": 2.0,  # ...but costs twice the walking energy
    "relax_speed_ratio": 0.15,     # relaxing speed as a fraction of walk_speed
    "turn_rate": 3.0,              # radians per second (smooth turning)
    "wander_turn_interval": 4.0,   # seconds between random heading changes when roaming
    "wall_probe_distance": 28,     # how far ahead to look for water/walls
    "avoid_horizon": 1.5,          # seconds of look-ahead for other creatures' paths (0 = off)
    "avoid_margin": 6,             # extra clearance wanted when passing, in pixels
    "avoid_turn": 0.9,             # max heading change (radians) to pass someone
    # Senses
    "vision_range": 200,
    "think_interval": 0.2,         # seconds between decisions (steering runs every frame)
    # Energy
    "max_energy": 150,
    "birth_energy": 45,            # born as adults with a little energy to find food
    "alive_energy_cost": 0.3,      # per second, always
    "walk_energy_cost": 0.5,       # per second while walking (running costs more, see above)
    "hungry_ratio": 0.6,           # starts foraging below this fraction of max_energy...
    "full_ratio": 0.95,            # ...and keeps foraging until this fraction
    "relaxed_ratio": 0.85,         # relaxes above this fraction when not foraging
    "eat_range": 10,               # extra reach beyond touching, in pixels
    # Hunger beats fear: a foraging creature may go for food with a predator in sight
    # (unless that predator is chasing it). The chance grows from 0 at the hungry
    # threshold to hunger_boldness at zero energy, re-rolled every boldness_interval s.
    "hunger_boldness": 0.8,
    "boldness_interval": 2.0,
    # Reproduction
    "reproduction_interval": 30.0,  # seconds between births
    "reproduction_energy_threshold": 120,
    "reproduction_energy_cost": 55,
    # Food chain: layers this creature eats. Threats are derived from other species' diets.
    "diet": [],
    "nutrition": 60,               # energy a predator gains from eating this creature
    "corpse_duration": 20.0,       # seconds a dead body stays around and can still be eaten
    "physics": _CREATURE_PHYSICS,
}

HERBIVORE_CONFIG = {
    "initial_count": 15,
    "max_population": 60,
    "walk_speed": 30,              # runs at 45
    "diet": ["plants"],
    "nutrition": 80,
}

CARNIVORE_CONFIG = {
    "initial_count": 4,
    "max_population": 12,
    "walk_speed": 44,              # runs at 66, faster than smarties and herbivores
    "turn_rate": 3.5,
    "vision_range": 260,
    "max_energy": 220,
    "birth_energy": 70,
    "alive_energy_cost": 0.4,
    "walk_energy_cost": 0.6,
    "reproduction_interval": 40.0,
    "reproduction_energy_threshold": 180,
    "reproduction_energy_cost": 80,
    "diet": ["herbivores", "smarties"],
    "nutrition": 90,
}

# Smarties are the omnivores: plants and herbivores, hunted by carnivores.
# They are the only species that may get a brain beyond instinct.
SMARTIE_CONFIG = {
    "initial_count": 6,
    "max_population": 25,
    "walk_speed": 36,              # runs at 54, faster than herbivores
    "turn_rate": 2.5,
    "vision_range": 260,
    "max_energy": 180,
    "birth_energy": 55,
    "alive_energy_cost": 0.35,
    "walk_energy_cost": 0.55,
    "reproduction_interval": 35.0,
    "reproduction_energy_threshold": 145,
    "reproduction_energy_cost": 65,
    "diet": ["plants", "herbivores"],  # herbivores (nutrition 80) beat any plant (max 50)
    "nutrition": 100,
}

# Physics settings
DEFAULT_DAMPING = .6
GRAVITY = (0, 0)
