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
    "winter_wither": 0.08,  # chance per second (scaled by how cold it is) to drop a growth stage
}

# Day/night and seasons
ENVIRONMENT_CONFIG = {
    "day_length": 120.0,      # seconds per full day
    "year_length": 1440.0,    # seconds per year (four seasons)
    "start_time": 40.0,       # morning of day 1, early spring
    "season_strength": 0.7,   # plant growth swings this much above/below normal (and winter cold)
    "night_darkness": 0.55,   # how dark the screen gets at midnight
}

# Creature configuration.
# CREATURE_DEFAULTS holds shared values; each species dict overrides what it needs
# (merged in Creature.__init_subclass__). Rates are per second unless noted.
#
# Three bars per creature:
#   health   - drops from starving, from running on empty (burning muscle) and from
#              wounds; recovers while relaxing (like sleep). Zero health = death.
#   stamina  - pays for everything the creature does: being alive, walking, running
#              (run_speed_multiplier x faster for run_stamina_multiplier x the cost),
#              healing. Refilled by digesting food. Empty = can't run, and further
#              costs come out of health.
#   food     - the hunger bar. Eating fills it; being alive drains it slowly; above
#              the starving line it digests into stamina; below it, health drops.
CREATURE_DEFAULTS = {
    "initial_count": 0,
    "max_population": 30,
    "bounds_padding": 40,
    # Movement
    "walk_speed": 30,              # pixels per second
    "run_speed_multiplier": 1.5,   # running is 50% faster...
    "run_stamina_multiplier": 2.0,  # ...but costs twice the walking stamina
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
    # Bars
    "max_health": 100,
    "max_stamina": 100,
    "max_food": 150,
    "birth_food": 50,              # born as adults with a little food to go find more
    "birth_stamina_ratio": 0.6,
    # Stamina costs
    "alive_stamina_cost": 0.4,
    "walk_stamina_cost": 1.0,      # while walking; running costs run_stamina_multiplier x more
    # Food / digestion
    "food_drain": 0.3,             # being alive slowly empties the food bar
    "digest_rate": 2.0,            # food per second turned into stamina (while stamina isn't full)
    "digest_efficiency": 1.0,      # stamina gained per unit of food
    "starve_ratio": 0.1,           # below this fraction of max_food: starving
    "starve_damage": 1.0,          # health lost per second while starving
    "muscle_burn": 0.5,            # health lost per stamina point owed when stamina is empty
    # Relaxing heals (like sleep), at a price
    "heal_rate": 1.5,              # health per second while relaxing and hurt
    "heal_stamina_cost": 1.0,
    "heal_food_cost": 0.5,
    # Moods
    "hungry_ratio": 0.6,           # starts foraging below this fraction of max_food...
    "full_ratio": 0.95,            # ...and keeps foraging until this fraction
    "relaxed_ratio": 0.85,         # relaxes when food is above this (or when hurt / tired)
    "rest_ratio": 0.15,            # tired below this fraction of stamina: rests even if hungry...
    "rested_ratio": 0.7,           # ...until stamina is back at this fraction
    "eat_range": 10,               # extra reach beyond touching, in pixels
    "sprint_range": 10000,         # hunters stalk at a walk and sprint once prey is this close
    # Hunger beats fear: a foraging creature may go for food with a predator in sight
    # (unless that predator is chasing it). The chance grows with hunger, from 0 at the
    # hungry line to hunger_boldness when the food bar is empty; re-rolled every
    # boldness_interval seconds.
    "hunger_boldness": 0.8,
    "boldness_interval": 2.0,
    # Reproduction
    "reproduction_interval": 30.0,  # seconds between births
    "reproduction_food_threshold": 120,
    "reproduction_health_ratio": 0.9,
    "reproduction_food_cost": 55,
    # Inheritance: newborns copy the parent's genes (size, speed, stamina, vision,
    # boldness) with a random change of about this fraction; founders vary too
    "mutation_rate": 0.06,
    "founder_variation": 0.1,
    # Environment
    "night_vision": 0.5,           # fraction of vision kept at midnight
    "winter_hunger": 0.5,          # extra food drain in deep winter (x season_strength)
    # Fighting: hunters bite living prey; prey bites back (stronger in a herd)
    "attack_damage": 0,            # health a bite takes off prey
    "defense_damage": 0,           # health a caught prey's bite takes off the hunter
    "attack_cooldown": 1.0,        # seconds between bites
    "herd_radius": 60,             # how close peers count as "the herd"
    "herd_bonus": 0.5,             # each herd peer nearby adds this much to the defense bite
    "crowd_penalty": 0.0,          # hunters see prey in a crowd as this much further away, per peer
    "herd_cohesion": 0.0,          # 0..1: how strongly roaming creatures drift toward their herd
    # Food chain: layers this creature eats. Threats are derived from other species' diets.
    "diet": [],
    "nutrition": 60,               # food a predator gains from eating this creature
    "corpse_duration": 20.0,       # seconds a dead body stays around and can still be eaten
    "reintroduce_after": 60.0,     # an extinct species gets new founders after this many s (0 = never)
}

# Herbivores: slow but enduring
HERBIVORE_CONFIG = {
    "initial_count": 15,
    "max_population": 60,
    "walk_speed": 30,              # runs at 45
    "max_stamina": 120,
    "defense_damage": 4,
    "herd_bonus": 0.6,
    "herd_cohesion": 0.4,
    "diet": ["plants"],
    "nutrition": 80,
}

# Carnivores: fast sprinters with a small stamina pool, so long chases fail
CARNIVORE_CONFIG = {
    "initial_count": 4,
    "max_population": 12,
    "walk_speed": 44,              # runs at 66, faster than smarties and herbivores
    "turn_rate": 3.5,
    "vision_range": 260,
    "max_health": 140,
    "max_stamina": 24,
    "run_stamina_multiplier": 3.0,  # sprinting is expensive for them
    "sprint_range": 160,           # stalk, then sprint
    "max_food": 220,
    "birth_food": 80,
    "alive_stamina_cost": 0.4,
    "walk_stamina_cost": 0.8,
    "digest_rate": 2.0,            # must beat walking cost, or hunters tire out just patrolling
    "food_drain": 0.3,
    "reproduction_interval": 40.0,
    "reproduction_food_threshold": 180,
    "reproduction_food_cost": 80,
    "attack_damage": 45,
    "defense_damage": 10,
    "night_vision": 0.9,           # night hunters
    "crowd_penalty": 0.4,
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
    "max_stamina": 90,
    "sprint_range": 140,
    "max_food": 180,
    "birth_food": 60,
    "food_drain": 0.35,
    "reproduction_interval": 35.0,
    "reproduction_food_threshold": 145,
    "reproduction_food_cost": 65,
    "attack_damage": 15,
    "defense_damage": 8,
    "crowd_penalty": 0.3,
    "herd_cohesion": 0.2,
    "diet": ["plants", "herbivores"],  # herbivores (nutrition 80) beat any plant (max 50)
    "nutrition": 100,
}
