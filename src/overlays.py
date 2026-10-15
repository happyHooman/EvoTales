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
        rows = []
        add = rows.append
        show_fov, show_energy = self.show_fov, self.show_energy
        half_w = BAR_WIDTH / 2
        for layer in self._layers:
            ring_color = tuple(c / 255 for c in FOV_COLORS.get(layer, (255, 255, 255))) + (1.0,)
            for c in self._world.scene[layer]:
                if not c.alive:
                    continue
                x, y = c.position
                cfg = c.config
                if show_fov:
                    d = 2 * cfg["vision_range"]
                    add((x, y, d, d) + ring_color + (RING,))
                if show_energy:
                    ratio = max(0.0, min(1.0, c.energy / cfg["max_energy"]))
                    by = y + c.radius + 6
                    add((x, by, BAR_WIDTH, BAR_HEIGHT) + BAR_BG + (RECT,))
                    w = max(BAR_WIDTH * ratio, 1.0)
                    # red (empty) -> yellow -> green (full)
                    add((x - half_w + w / 2, by, w, BAR_HEIGHT,
                         min(1.0, 2 - 2 * ratio), min(1.0, 2 * ratio), 0.15, 1.0, RECT))
        return np.array(rows, dtype="f4") if rows else np.zeros((0, FLOATS_PER_INSTANCE), "f4")

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
