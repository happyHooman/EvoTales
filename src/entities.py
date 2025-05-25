import arcade
from sprite_manager import SpriteManager
from config import DEFAULT_DAMPING, GRAVITY

TILE_SCALING = 1.0

class Entity:
    def __init__(self, sprite, x, y):
        self.x = x
        self.y = y
        self.sprite = sprite


class EntityManager():
    """
    Manages all entities in the simulation, extending arcade.Scene
    to provide entity-specific functionality.
    """
    def __init__(self):
        layer_options = {
            "ground": {
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
        self.plants = arcade.SpriteList()
        self.scene.add_sprite_list("plants", self.plants)
        self.sprite_manager = SpriteManager()
        self.sprite_manager.load_all_sprite_sheets()
        self.map_size = self.tile_map.width * self.tile_map.tile_width, self.tile_map.height * self.tile_map.tile_height
        
    def add_entity(self, entity, layer_name: str):
        """Add an entity to a specific layer"""
        self.add_sprite(layer_name, entity)
        # Add to physics engine if the entity should have physics
        if hasattr(entity, 'use_physics') and entity.use_physics:
            self.physics_engine.add_sprite(entity)

    def add_plant(self, plant):
        plant_sprite = self.sprite_manager.create_sprite(plant)
        plant_sprite.center_x = self.map_size[0] / 2
        plant_sprite.center_y = self.map_size[1] / 2
        self.plants.append(plant_sprite)
        self.scene.add_sprite("plants", plant_sprite)

    def update(self, delta_time: float = 1/60):
        """Update all entities and physics"""
        self.physics_engine.step()

    def get_map_size(self):
        return self.tile_map.width * self.tile_map.tile_width, self.tile_map.height * self.tile_map.tile_height
    

    def generate_initial_population(self):
        self.add_plant("plant_stage_1")