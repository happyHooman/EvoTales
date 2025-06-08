from .entity import Entity
from sprite_manager import sprite_manager

class Herbivore(Entity):
    def __init__(self, x, y, entity_manager):
        texture = sprite_manager.get_texture("herbivore")
        super().__init__(texture, x, y)
        self.entity_manager = entity_manager

    def update(self, delta_time: float = 1/60):
        pass
