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
    "initial_count": 200,
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
    "regrow_time": 10.0,    # seconds after grazing before a plant can be eaten again (any stage)
    "winter_wither": 0.08,  # chance per second (scaled by how cold it is) to drop a growth stage
}

# Map: "generated" builds a fresh world from noise (biomes); "tiled" loads the
# hand-made Tiled map in assets/maps. Changes apply on restart (Regenerate).
MAP_CONFIG = {
    "source": "generated",
    "seed": 7,
    "width_tiles": 200,
    "height_tiles": 150,
    "tile_size": 16,             # pixels per tile
    "terrain_scale": 40,         # tiles per hill/lake feature (bigger = broader)
    "climate_scale": 70,         # tiles per climate zone
    "water_level": 0.3,          # 0..1: more = more lakes
    "beach_width": 0.03,
    "temperature_shift": 0.0,    # + warmer (more desert/swamp), - colder (more tundra)
    "moisture_shift": 0.0,       # + wetter (more forest/swamp), - drier (more desert)
    "latitude_strength": 0.4,    # how much colder the top of the map is than the bottom
}

# How well plants grow in each biome: growth speed, and the chance a seed takes root
BIOME_CONFIG = {
    "grassland_plants": 1.0, "forest_plants": 1.3, "desert_plants": 0.15,
    "swamp_plants": 1.5, "tundra_plants": 0.35, "beach_plants": 0.2,
}

# Per species, per biome: multipliers on ANY creature parameter (missing = 1.0).
# This is what gives each species a home ground and places it struggles.
# "visibility" is how far away others can spot it (forests hide; open sand shows).
SPECIES_BIOME_CONFIG = {
    "herbivores": {   # open-country grazers
        "grassland": {"walk_speed": 1.1, "digest_rate": 1.2},
        "forest": {"walk_speed": 0.85, "vision_range": 0.6, "visibility": 0.7},
        "desert": {"alive_stamina_cost": 1.4, "food_drain": 1.3, "visibility": 1.3},
        "swamp": {"walk_speed": 0.6, "walk_stamina_cost": 1.5},
        "tundra": {"food_drain": 1.5, "walk_speed": 0.9},
        "beach": {"vision_range": 1.2, "visibility": 1.3},
    },
    "smarties": {     # forest dwellers, at home in cover and wetlands
        "grassland": {"visibility": 1.1},
        "forest": {"vision_range": 0.9, "visibility": 0.5, "digest_rate": 1.3, "heal_rate": 1.3},
        "desert": {"alive_stamina_cost": 1.6, "food_drain": 1.5},
        "swamp": {"walk_speed": 0.9, "visibility": 0.6},
        "tundra": {"food_drain": 1.7, "walk_speed": 0.85},
        "beach": {"visibility": 1.3},
    },
    "carnivores": {   # stalkers: ambush from cover, tireless in the cold, lost in the mud
        "grassland": {"vision_range": 1.15},
        "forest": {"visibility": 0.5, "sprint_range": 0.8, "vision_range": 0.75},
        "desert": {"alive_stamina_cost": 1.5, "walk_stamina_cost": 1.3},
        "swamp": {"walk_speed": 0.6, "walk_stamina_cost": 1.6},
        "tundra": {"food_drain": 1.0, "walk_speed": 1.05, "max_stamina": 1.2},
        "beach": {"visibility": 1.4},
    },
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
    # Inheritance: newborns copy the parent's genes (one per feature: speed, vision,
    # stamina pool, stomach, digestion, activity costs, recovery, thresholds,
    # reproduction - see engine/store.py GENES) with a random change of about this
    # fraction; founders vary too
    "mutation_rate": 0.06,
    "founder_variation": 0.1,
    "visibility": 1.0,             # how far away others can spot it (x their vision)
    # Environment
    "night_vision": 0.5,           # fraction of vision kept at midnight
    "winter_hunger": 0.5,          # extra food drain in deep winter (x season_strength)
    # Fighting: hunters bite living prey; prey bites back (stronger in a herd)
    # Attack value: health one bite takes off, at full health and stamina. The bite
    # weakens with the biter's condition: x (0.3 + 0.7 health fraction)
    # x (0.3 + 0.7 stamina fraction). Used for hunting, biting back and rival fights.
    "attack": 0,
    "rival_bite": 0.4,             # fraction of the attack value used against its own kind
    "attack_cooldown": 1.0,        # seconds between bites
    "herd_radius": 60,             # how close peers count as "the herd"
    "herd_bonus": 0.5,             # each herd peer nearby adds this much to the defense bite
    "crowd_penalty": 0.0,          # hunters see prey in a crowd as this much further away, per peer
    "herd_cohesion": 0.0,          # 0..1: how strongly roaming creatures drift toward their herd
    # Alarm calls: prey running from a predator calls out to its own species
    "call_range": 0,               # how far a call carries, px (0 = this species doesn't call)
    "alarm_duration": 3.0,         # seconds peers flee after hearing a call
    # Crowding: personal space is a resource too
    "personal_space": 30,          # px; peers of its own kind closer than this crowd it
    "crowd_limit": 4,              # more peers than this inside personal space = crammed
    "crowd_damage": 0.3,           # health lost per second per peer over the limit
    "aggression": 0.3,             # chance per decision that a crammed creature bites a too-close peer
    # Squabbles over the same food item
    "dominance": 1.0,              # species weight in squabbles (x its current attack value)
    "contest_range": 25,           # how close to the food a rival must be to squabble
    "yield_time": 4.0,             # seconds a loser stays away from that food
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
    "attack": 4,
    "herd_bonus": 0.6,
    "call_range": 120,
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
    "attack": 45,
    "crowd_limit": 1,              # loners
    "dominance": 2.0,
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
    "attack": 15,
    "crowd_limit": 3,
    "dominance": 1.3,
    "call_range": 140,
    "crowd_penalty": 0.3,
    "herd_cohesion": 0.2,
    "diet": ["plants", "herbivores"],  # herbivores (nutrition 80) beat any plant (max 50)
    "nutrition": 100,
}
