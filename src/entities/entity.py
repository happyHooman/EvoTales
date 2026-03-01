from arcade import Sprite


class Entity(Sprite):
    """Base for plants and animals. Manages own lifecycle via spawn/despawn."""

    layer_name: str = ""
    use_physics: bool = True

    def __init__(self, texture, x, y, *args, **kwargs):
        super().__init__(
            texture,
            center_x=x,
            center_y=y,
            scale=texture.properties.get("scale", 1.0),
            *args,
            **kwargs,
        )

    def _register(self) -> None:
        """Register self with scene and physics. Called by subclasses at end of __init__."""
        if not self.layer_name:
            raise NotImplementedError("Subclass must set layer_name")
        em = self.entity_manager
        em.scene.add_sprite(self.layer_name, self)
        physics_params = (
            self.config.get("physics", {})
            if hasattr(self, "config") and isinstance(self.config, dict)
            else {}
        )
        if self.use_physics and physics_params:
            em.scene.physics_engine.add_sprite(self, **physics_params)

    def despawn(self) -> None:
        """Remove self from scene and physics. Requires entity_manager on self."""
        physics = self.entity_manager.scene.physics_engine
        if self in physics.sprites:
            physics.remove_sprite(self)
        self.remove_from_sprite_lists()

