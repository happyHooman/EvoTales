import arcade
import pymunk
from config import DEFAULT_DAMPING, GRAVITY, PLANT_CONFIG
from entities.plant import Plant
from entities.herbivore import Herbivore

TILE_SCALING = 1.0


class EntityManager():
    """
    Provides scene, physics, map. Lifecycle handlers live on entities:
    Plant.spawn(em, x, y), Herbivore.spawn(em), etc.
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

        Plant.spawn(self, seed_x, seed_y, growth_level=growth_level)
        return True

    def update(self, delta_time: float = 1/60):
        """Update all entities and physics. Skip static ground layer."""
        self.scene.update(delta_time, names=["plants", "herbivores"])
        self.scene.physics_engine.step()

    def get_map_size(self):
        return self.tile_map.width * self.tile_map.tile_width, self.tile_map.height * self.tile_map.tile_height
    
    def spawn_initial_population(self):
        Plant.spawn_initial(self)
        Herbivore.spawn(self)

        