import arcade
from config import DEFAULT_DAMPING, GRAVITY
from entities.plant import Plant
from entities.herbivore import Herbivore

TILE_SCALING = 1.0


class EntityManager():
    """
    Provides scene, physics, map. Lifecycle handlers live on entities:
    Plant.spawn(scene, map_size, x, y), Herbivore.spawn(scene, map_size), etc.
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

    def update(self, delta_time: float = 1/60):
        """Update all entities and physics. Skip static ground layer."""
        self.scene.update(delta_time, names=["plants", "herbivores"])
        self.scene.physics_engine.step()

    def get_map_size(self):
        return self.tile_map.width * self.tile_map.tile_width, self.tile_map.height * self.tile_map.tile_height
    
    def spawn_initial_population(self):
        Plant.spawn_initial(self.scene, self.map_size)
        Herbivore.spawn_initial(self.scene, self.map_size)

        