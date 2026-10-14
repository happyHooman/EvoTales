from .creature import Creature
from config import HERBIVORE_CONFIG


class Herbivore(Creature):
    layer_name = "herbivores"
    texture_name = "herbivore"
    config = HERBIVORE_CONFIG
