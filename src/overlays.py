"""
Debug overlays drawn on top of the world: each creature's field of view and an
energy bar. Everything lives in one SpriteList so it is a single draw call, and
nothing is synced while both overlays are off.
"""
import arcade
from PIL import Image, ImageDraw

RING_SIZE = 256
BAR_WIDTH, BAR_HEIGHT = 26, 4
BAR_BG = (30, 30, 30, 200)
FOV_COLORS = {
    "herbivores": (120, 255, 120),
    "omnivores": (255, 190, 80),
    "carnivores": (255, 90, 70),
    "smarties": (170, 140, 255),
}


def _ring_texture(rgb) -> arcade.Texture:
    image = Image.new("RGBA", (RING_SIZE, RING_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, RING_SIZE - 3, RING_SIZE - 3), fill=(*rgb, 22), outline=(*rgb, 150), width=3)
    return arcade.Texture(image, hash=f"fov-ring-{rgb}")


class Overlays:
    def __init__(self):
        self.show_fov = False
        self.show_energy = False
        self.sprites = arcade.SpriteList()
        self._rings = {layer: _ring_texture(rgb) for layer, rgb in FOV_COLORS.items()}
        self._attached = {}  # creature -> (ring, bar_bg, bar_fill)

    @property
    def enabled(self) -> bool:
        return self.show_fov or self.show_energy

    def configure(self, show_fov: bool, show_energy: bool) -> None:
        self.show_fov, self.show_energy = bool(show_fov), bool(show_energy)
        if not self.enabled:
            self.clear()

    def clear(self) -> None:
        self.sprites.clear()
        self._attached.clear()

    def update(self, world, creature_layers) -> None:
        if not self.enabled:
            return
        seen = set()
        for layer in creature_layers:
            ring_texture = self._rings.get(layer)
            for creature in world.scene[layer]:
                if not creature.alive:
                    continue
                seen.add(creature)
                parts = self._attached.get(creature)
                if parts is None:
                    parts = (
                        arcade.Sprite(ring_texture),
                        arcade.SpriteSolidColor(BAR_WIDTH, BAR_HEIGHT, color=BAR_BG),
                        arcade.SpriteSolidColor(BAR_WIDTH, BAR_HEIGHT, color=arcade.color.WHITE),
                    )
                    self.sprites.extend(parts)
                    self._attached[creature] = parts
                self._sync(creature, *parts)
        for creature in [c for c in self._attached if c not in seen]:
            for sprite in self._attached.pop(creature):
                sprite.remove_from_sprite_lists()

    def _sync(self, creature, ring, bar_bg, bar_fill) -> None:
        x, y = creature.center_x, creature.center_y
        ring.visible = self.show_fov
        if self.show_fov:
            ring.position = (x, y)
            diameter = 2 * creature.config["vision_range"]
            ring.size = (diameter, diameter)
        bar_bg.visible = bar_fill.visible = self.show_energy
        if self.show_energy:
            ratio = max(0.0, min(1.0, creature.energy / creature.config["max_energy"]))
            bar_y = y + creature.radius + 6
            bar_bg.position = (x, bar_y)
            width = max(BAR_WIDTH * ratio, 0.5)
            bar_fill.width = width
            bar_fill.position = (x - BAR_WIDTH / 2 + width / 2, bar_y)
            # red (empty) -> yellow -> green (full)
            bar_fill.color = (int(255 * min(1.0, 2 - 2 * ratio)), int(255 * min(1.0, 2 * ratio)), 40, 255)

    def draw(self) -> None:
        if self.enabled:
            self.sprites.draw()
