"""
Debug overlays drawn on top of the world: each creature's field of view and an
energy bar. Everything is one instanced GPU draw: per frame we only gather a
few floats per creature into a numpy array (no sprite objects to move around,
which cost ~6 ms per frame at 2,000 creatures).
"""
import arcade
import numpy as np
from arcade.gl import BufferDescription

BAR_WIDTH, BAR_HEIGHT = 26, 4
BAR_BG = (30 / 255, 30 / 255, 30 / 255, 0.8)
FOV_COLORS = {
    "herbivores": (120, 255, 120),
    "smarties": (170, 140, 255),
    "carnivores": (255, 90, 70),
}
RECT, RING = 0.0, 1.0
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
    float d = length(v_uv);         // ring: faint fill, stronger outline
    if (d > 1.0) discard;
    float alpha = d > 1.0 - v_edge ? 0.6 : 0.09;
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
        return self.show_fov or self.show_energy

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
        if self.show_fov:
            ring = np.empty((len(rows), FLOATS_PER_INSTANCE), "f4")
            d = 2 * store.params["vision_range"][sp]
            colors = np.array([tuple(c / 255 for c in FOV_COLORS.get(layer, (255, 255, 255))) + (1.0,)
                               for layer in self._layers], "f4")
            ring[:, 0], ring[:, 1], ring[:, 2], ring[:, 3] = x, y, d, d
            ring[:, 4:8] = colors[sp]
            ring[:, 8] = RING
            parts.append(ring)
        if self.show_energy:
            ratio = np.clip(store.vitals.energy[rows] / store.params["max_energy"][sp], 0, 1)
            by = y + store.radius[rows] + 6
            bg = np.empty((len(rows), FLOATS_PER_INSTANCE), "f4")
            bg[:, 0], bg[:, 1], bg[:, 2], bg[:, 3] = x, by, BAR_WIDTH, BAR_HEIGHT
            bg[:, 4:8] = BAR_BG
            bg[:, 8] = RECT
            w = np.maximum(BAR_WIDTH * ratio, 1.0)
            fill = np.empty((len(rows), FLOATS_PER_INSTANCE), "f4")
            fill[:, 0], fill[:, 1], fill[:, 2], fill[:, 3] = x - BAR_WIDTH / 2 + w / 2, by, w, BAR_HEIGHT
            # red (empty) -> yellow -> green (full)
            fill[:, 4] = np.minimum(1.0, 2 - 2 * ratio)
            fill[:, 5] = np.minimum(1.0, 2 * ratio)
            fill[:, 6], fill[:, 7], fill[:, 8] = 0.15, 1.0, RECT
            parts += [bg, fill]
        return np.concatenate(parts)

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
