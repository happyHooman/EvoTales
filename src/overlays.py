"""
Debug overlays drawn on top of the world: each creature's field of view and its
health / stamina / food bars. Everything is one instanced GPU draw: per frame we only gather a
few floats per creature into a numpy array (no sprite objects to move around,
which cost ~6 ms per frame at 2,000 creatures).
"""
import arcade
import numpy as np
from arcade.gl import BufferDescription

BAR_WIDTH, BAR_HEIGHT = 26, 3
BAR_BG = (30 / 255, 30 / 255, 30 / 255, 0.8)
HEALTH_COLOR = (0.9, 0.2, 0.2, 1.0)
STAMINA_COLOR = (1.0, 0.85, 0.2, 1.0)
FOOD_COLOR = (0.35, 0.85, 0.3, 1.0)
FOV_COLORS = {
    "herbivores": (120, 255, 120),
    "smarties": (170, 140, 255),
    "carnivores": (255, 90, 70),
}
RECT, RING, CALL = 0.0, 1.0, 2.0
FLOATS_PER_INSTANCE = 9  # center(2) size(2) color(4) shape(1)

VERTEX_SHADER = """
#version 330
uniform WindowBlock {
    mat4 projection;
    mat4 view;
} window;

in vec2 in_corner;      // unit quad, -1..1
in vec2 in_center;
in vec2 in_size;
in vec4 in_color;
in float in_shape;

out vec2 v_uv;
out vec4 v_color;
out float v_shape;
out float v_edge;

void main() {
    v_uv = in_corner;
    v_color = in_color;
    v_shape = in_shape;
    v_edge = 3.0 / max(in_size.x, 1.0) * 2.0;  // ~3 world px of outline, in uv units
    vec2 pos = in_center + in_corner * in_size * 0.5;
    gl_Position = window.projection * window.view * vec4(pos, 0.0, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330
in vec2 v_uv;
in vec4 v_color;
in float v_shape;
in float v_edge;
out vec4 out_color;

void main() {
    if (v_shape < 0.5) {            // rectangle
        out_color = v_color;
        return;
    }
    float d = length(v_uv);
    if (d > 1.0) discard;
    if (v_shape > 1.5) {            // alarm call: thin ring that fades out
        if (d < 1.0 - v_edge) discard;
        out_color = v_color;
        return;
    }
    float alpha = d > 1.0 - v_edge ? 0.6 : 0.09;   // field of view: faint fill, stronger outline
    out_color = vec4(v_color.rgb, alpha);
}
"""


class Overlays:
    def __init__(self):
        self.show_fov = False
        self.show_energy = False
        self._world = None
        self._layers = ()
        self._program = None
        self._geometry = None
        self._instances = None
        self._capacity = 0

    @property
    def enabled(self) -> bool:
        return True  # alarm call ripples are always shown

    def configure(self, show_fov: bool, show_energy: bool) -> None:
        self.show_fov, self.show_energy = bool(show_fov), bool(show_energy)

    def update(self, world, creature_layers) -> None:
        self._world, self._layers = world, creature_layers

    def _setup(self, ctx, capacity: int) -> None:
        if self._program is None:
            self._program = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER)
            self._corners = ctx.buffer(data=np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4"))
        self._capacity = max(capacity, 1024)
        self._instances = ctx.buffer(reserve=self._capacity * FLOATS_PER_INSTANCE * 4, usage="stream")
        self._geometry = ctx.geometry(
            [BufferDescription(self._corners, "2f", ["in_corner"]),
             BufferDescription(self._instances, "2f 2f 4f 1f",
                               ["in_center", "in_size", "in_color", "in_shape"], instanced=True)],
            mode=ctx.TRIANGLE_STRIP,
        )

    def _gather(self) -> np.ndarray:
        """Instance rows for every living creature, built with array operations."""
        store = self._world.creatures.store
        rows = store.living_rows()
        if not len(rows):
            return np.zeros((0, FLOATS_PER_INSTANCE), "f4")
        x, y, sp = store.body.x[rows], store.body.y[rows], store.species[rows]
        parts = []
        # Alarm calls: an expanding, fading ring around the caller
        calling = store.mind.call_flash[rows] > 0
        if calling.any():
            from engine.behaviour import CALL_FLASH
            c = rows[calling]
            t = 1.0 - store.mind.call_flash[c] / CALL_FLASH        # 0 -> 1 over the flash
            ring = np.empty((len(c), FLOATS_PER_INSTANCE), "f4")
            d = 2 * store.p("call_range", c) * (0.3 + 0.7 * t)
            ring[:, 0], ring[:, 1], ring[:, 2], ring[:, 3] = store.body.x[c], store.body.y[c], d, d
            ring[:, 4:7] = (1.0, 0.95, 0.6)
            ring[:, 7] = 1.0 - t
            ring[:, 8] = CALL
            parts.append(ring)
        if self.show_fov:
            ring = np.empty((len(rows), FLOATS_PER_INSTANCE), "f4")
            d = 2 * store.p("vision_range", rows)
            colors = np.array([tuple(c / 255 for c in FOV_COLORS.get(layer, (255, 255, 255))) + (1.0,)
                               for layer in self._layers], "f4")
            ring[:, 0], ring[:, 1], ring[:, 2], ring[:, 3] = x, y, d, d
            ring[:, 4:8] = colors[sp]
            ring[:, 8] = RING
            parts.append(ring)
        if self.show_energy:
            # Three bars above each creature: health (top), stamina, food (bottom)
            vit, P = store.vitals, store.params
            top = y + store.radius[rows] + 6
            for k, (values, maximum, color) in enumerate((
                    (vit.health[rows], store.p("max_health", rows), HEALTH_COLOR),
                    (vit.stamina[rows], store.p("max_stamina", rows), STAMINA_COLOR),
                    (vit.food[rows], store.p("max_food", rows), FOOD_COLOR))):
                ratio = np.clip(values / maximum, 0, 1)
                by = top + (2 - k) * (BAR_HEIGHT + 1)
                bg = np.empty((len(rows), FLOATS_PER_INSTANCE), "f4")
                bg[:, 0], bg[:, 1], bg[:, 2], bg[:, 3] = x, by, BAR_WIDTH, BAR_HEIGHT
                bg[:, 4:8] = BAR_BG
                bg[:, 8] = RECT
                w = np.maximum(BAR_WIDTH * ratio, 0.5)
                fill = np.empty((len(rows), FLOATS_PER_INSTANCE), "f4")
                fill[:, 0], fill[:, 1], fill[:, 2], fill[:, 3] = x - BAR_WIDTH / 2 + w / 2, by, w, BAR_HEIGHT
                fill[:, 4:8] = color
                fill[:, 8] = RECT
                parts += [bg, fill]
        return np.concatenate(parts) if parts else np.zeros((0, FLOATS_PER_INSTANCE), "f4")

    def draw(self) -> None:
        if not self.enabled or self._world is None:
            return
        data = self._gather()
        count = len(data)
        if count == 0:
            return
        ctx = arcade.get_window().ctx
        if self._geometry is None or count > self._capacity:
            self._setup(ctx, int(count * 1.5))
        self._instances.write(data.tobytes())
        ctx.enable(ctx.BLEND)
        self._geometry.render(self._program, instances=count)
