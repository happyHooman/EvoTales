from .creature import Creature
from config import SMARTIE_CONFIG


class Smarty(Creature):
    layer_name = "smarties"
    texture_name = "smartie"
    config = SMARTIE_CONFIG
    can_have_brain = True  # the only species that may get a brain beyond instinct
