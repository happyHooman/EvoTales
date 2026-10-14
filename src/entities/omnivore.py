from .creature import Creature
from config import OMNIVORE_CONFIG


class Omnivore(Creature):
    layer_name = "omnivores"
    texture_name = "omnivore"
    config = OMNIVORE_CONFIG
