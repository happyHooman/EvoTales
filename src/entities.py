import arcade
from sprite_manager import SpriteManager
from config import DEFAULT_DAMPING, GRAVITY

TILE_SCALING = 1.0

sprite_manager = SpriteManager()
sprite_manager.load_all_sprite_sheets()

class Entity(arcade.Sprite):
    def __init__(self, texture, x, y, *args, **kwargs):
        super().__init__(texture, center_x=x, center_y=y, *args, **kwargs)


class Plant(Entity):
    def __init__(self, x, y, growth_level=1):
        self.max_growth_level = 4 # Define max growth level
        self.max_growth_timer = 3   # Time in seconds for next stage
        self.growth_timer = self.max_growth_timer
        
        # Create a list of sprite names for each growth stage
        texture_names = [f'plant_stage_{i}' for i in range(1, self.max_growth_level + 1)]
        # Use the new get_texture method from sprite_manager
        self.growth_textures = sprite_manager.get_texture(texture_names)

        # Ensure all textures were loaded successfully (self.growth_textures might contain None)
        if not self.growth_textures or any(t is None for t in self.growth_textures):
            print(f"Error: Failed to load one or more textures for Plant at ({x},{y}). Check sprite names and configs.")
            # Fallback: initialize with no texture or a default one if available
            initial_texture = None
        else:
            initial_texture_index = max(0, min(growth_level - 1, len(self.growth_textures) - 1))
            initial_texture = self.growth_textures[initial_texture_index]
        
        super().__init__(initial_texture, x, y) # Scale will be default 1.0 unless Entity.__init__ is updated
                                              # or we pass scale to arcade.Sprite constructor differently.

        self.growth_level = growth_level
        self.full_grown = self.growth_level >= self.max_growth_level
        # self.growth_timer = 30 # Time in seconds for next stage # This line is now handled by initializing from max_growth_timer

    def set_growth_level(self, new_growth_level: int):
        self.full_grown = new_growth_level >= self.max_growth_level
        requested_level = min(max(new_growth_level, 1), self.max_growth_level)
        texture_index = max(0, min(requested_level - 1, len(self.growth_textures) - 1))
        
        # Ensure texture_index is valid and the texture exists
        if texture_index < len(self.growth_textures) and self.growth_textures[texture_index] is not None:
            if self.growth_level != requested_level or self.texture != self.growth_textures[texture_index]:
                self.growth_level = requested_level
                self.full_grown = self.growth_level >= self.max_growth_level
                self.texture = self.growth_textures[texture_index] # Plant IS a Sprite, so set self.texture
                self.growth_timer = self.max_growth_timer
        else:
            print(f"Warning: Could not set growth level {requested_level}. Texture not available.")

    def update(self, delta_time: float = 1/60):
        self.grow(delta_time)

    def grow(self, delta_time: float = 1/60):
        if not self.full_grown:
            self.growth_timer -= delta_time
            if self.growth_timer <= 0:
                # Use set_growth_level to update texture and reset timer
                self.set_growth_level(self.growth_level + 1)



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
        # self.plants = arcade.SpriteList()
        # self.scene.add_sprite_list("plants", self.plants)
        self.map_size = self.tile_map.width * self.tile_map.tile_width, self.tile_map.height * self.tile_map.tile_height
        
    def add_entity(self, entity, layer_name: str):
        """Add an entity to a specific layer"""
        self.scene.add_sprite(layer_name, entity)
        # Add to physics engine if the entity should have physics
        if hasattr(entity, 'use_physics') and entity.use_physics:
            self.scene.physics_engine.add_sprite(entity)

    def add_plant(self):
        plant = Plant(self.map_size[0] / 2, self.map_size[1] / 2)
        self.scene.add_sprite("plants", plant)

    def update(self, delta_time: float = 1/60):
        """Update all entities and physics"""
        self.scene.update(delta_time)
        self.scene.physics_engine.step()

    def get_map_size(self):
        return self.tile_map.width * self.tile_map.tile_width, self.tile_map.height * self.tile_map.tile_height
    
    def generate_initial_population(self):
        self.add_plant()