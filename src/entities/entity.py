import arcade


class Entity(arcade.Sprite):

    def __init__(self, texture, x, y, *args, **kwargs):
        super().__init__(
            texture,
            center_x=x,
            center_y=y,
            scale=texture.properties.get("scale", 1.0),
            *args,
            **kwargs,
        )

