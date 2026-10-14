from arcade import Sprite


class Entity(Sprite):
    """Base for plants and animals. Manages own lifecycle via spawn/despawn."""

    layer_name: str = ""
    use_physics: bool = True

    def __init__(self, texture, x, y, world, *args, **kwargs):
        super().__init__(
            texture,
            center_x=x,
            center_y=y,
            scale=texture.properties.get("scale", 1.0),
            *args,
            **kwargs,
        )
        self.world = world
        self.scene = world.scene
        self.alive = True

    def _register(self, physics_params: dict | None = None) -> None:
        """Register self with scene and physics. Subclasses pass their own physics_params."""
        if not self.layer_name:
            raise NotImplementedError("Subclass must set layer_name")
        self.scene.add_sprite(self.layer_name, self)
        if self.use_physics and physics_params:
            self.scene.physics_engine.add_sprite(self, **physics_params)

    def despawn(self) -> None:
        """Mark dead and let the world remove it after the current update pass."""
        if self.alive:
            self.alive = False
            self.world.queue_removal(self)

    def _remove_now(self) -> None:
        # Also detaches from the physics engine (arcade tracks it on the sprite)
        self.remove_from_sprite_lists()
