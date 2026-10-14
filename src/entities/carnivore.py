from .creature import Creature
from config import CARNIVORE_CONFIG


class Carnivore(Creature):
    layer_name = "carnivores"
    texture_name = "carnivore"
    config = CARNIVORE_CONFIG
