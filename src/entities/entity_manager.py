import random
import arcade
import pymunk
from config import DEFAULT_DAMPING, GRAVITY, PLANT_CONFIG
from entities.plant import Plant
from entities.herbivore import Herbivore

TILE_SCALING = 1.0


class EntityManager():
    """
    Manages all entities in the simulation, extending arcade.Scene
    to provide entity-specific functionality.
    """
    def __init__(self):
        layer_options = {
            "ground": {
                "use_spatial_hash": True
            },
            "plants": {
                "use_spatial_hash": True
            }
        }
        self.tile_map = arcade.load_tilemap(
            "assets/maps/uniform_map.json",
            scaling=TILE_SCALING,
            layer_options=layer_options
        )
        self.scene = arcade.Scene.from_tilemap(self.tile_map)
        self.scene.physics_engine = arcade.PymunkPhysicsEngine(damping=DEFAULT_DAMPING, gravity=GRAVITY)
        self.map_size = self.tile_map.width * self.tile_map.tile_width, self.tile_map.height * self.tile_map.tile_height
        
    def handle_seed_drop(self, seed_x: float, seed_y: float, *, growth_level: int = 1) -> bool:
        map_width, map_height = self.map_size
        padding = PLANT_CONFIG["bounds_padding"]
        min_spacing = PLANT_CONFIG["min_spacing"]
        min_spacing_sq = min_spacing * min_spacing

        if not (padding <= seed_x <= map_width - padding and padding <= seed_y <= map_height - padding):
            return False

        query_bb = pymunk.BB(
            seed_x - min_spacing,
            seed_y - min_spacing,
            seed_x + min_spacing,
            seed_y + min_spacing,
        )
        for shape in self.scene.physics_engine.space.bb_query(query_bb, pymunk.ShapeFilter()):
            sprite = self.scene.physics_engine.get_sprite_for_shape(shape)
            if not isinstance(sprite, Plant):
                continue
            dx = sprite.center_x - seed_x
            dy = sprite.center_y - seed_y
            if dx * dx + dy * dy < min_spacing_sq:
                return False

        self.add_plant(seed_x, seed_y, growth_level=growth_level)
        return True

    def add_entity(self, entity, layer_name: str):
        """Add an entity to a specific layer"""
        self.scene.add_sprite(layer_name, entity)
        # Add to physics engine if the entity should have physics
        if hasattr(entity, 'use_physics') and entity.use_physics:
            self.scene.physics_engine.add_sprite(entity)

    def add_plant(self, x: float | None = None, y: float | None = None, *args, **kwargs):
        plant_x = x if x is not None else self.map_size[0] / 2
        plant_y = y if y is not None else self.map_size[1] / 2
        plant = Plant(plant_x, plant_y, entity_manager=self, *args, **kwargs)
        self.scene.add_sprite("plants", plant)
        self.scene.physics_engine.add_sprite(
            plant,
            collision_type="plant",
            body_type=arcade.PymunkPhysicsEngine.STATIC
        )

    def add_herbivore(self, x: float | None = None, y: float | None = None, *args, **kwargs):
        herbivore_x = x if x is not None else self.map_size[0] / 2
        herbivore_y = y if y is not None else self.map_size[1] / 2
        herbivore = Herbivore(herbivore_x, herbivore_y, entity_manager=self, *args, **kwargs)
        self.scene.add_sprite("herbivores", herbivore)
        self.scene.physics_engine.add_sprite(herbivore)

    def update(self, delta_time: float = 1/60):
        """Update all entities and physics"""
        self.scene.update(delta_time)
        self.scene.physics_engine.step()

    def get_map_size(self):
        return self.tile_map.width * self.tile_map.tile_width, self.tile_map.height * self.tile_map.tile_height
    
    def spawn_initial_population(self):
        Plant.spawn_initial(self)
        self.add_herbivore()

        