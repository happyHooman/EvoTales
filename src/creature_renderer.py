"""
Draws every creature straight from the creature store's numpy arrays: one instanced
draw call per species, no sprite objects. Per frame the only work is slicing
the arrays into an instance buffer.
"""
import arcade
import numpy as np
from arcade.gl import BufferDescription

from sprite_config import SPRITE_ANGLE_OFFSET
from sprite_manager import sprite_manager

CORPSE_COLOR = (80 / 255, 80 / 255, 80 / 255, 200 / 255)
FLOATS_PER_INSTANCE = 8  # center(2) angle(1) scale(1) color(4)

VERTEX_SHADER = """
#version 330
uniform WindowBlock {
    mat4 projection;
    mat4 view;
} window;
uniform vec2 half_size;

in vec2 in_corner;      // unit quad, -1..1
in vec2 in_center;
in float in_angle;      // radians, counter-clockwise
in float in_scale;      // the creature's size gene
in vec4 in_color;

out vec2 v_uv;
out vec4 v_color;

void main() {
    vec2 local = in_corner * half_size * in_scale;
    float c = cos(in_angle), s = sin(in_angle);
    vec2 pos = in_center + vec2(c * local.x - s * local.y, s * local.x + c * local.y);
    gl_Position = window.projection * window.view * vec4(pos, 0.0, 1.0);
    v_uv = vec2(in_corner.x * 0.5 + 0.5, 0.5 - in_corner.y * 0.5);  // image rows are top-down
    v_color = in_color;
}
"""

FRAGMENT_SHADER = """
#version 330
uniform sampler2D tex;
in vec2 v_uv;
in vec4 v_color;
out vec4 out_color;

void main() {
    vec4 texel = texture(tex, v_uv);
    if (texel.a < 0.01) discard;
    out_color = texel * v_color;
}
"""


class CreatureRenderer:
    def __init__(self, species_types):
        self.species_types = list(species_types)
        self._ready = False

    def _setup(self, ctx):
        self.program = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER)
        self.corners = ctx.buffer(data=np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4"))
        self.textures, self.half_sizes = [], []
        for s in self.species_types:
            tex = sprite_manager.get_texture(s.texture_name)
            image = tex.image.convert("RGBA")
            gl_tex = ctx.texture(image.size, components=4, data=image.tobytes())
            gl_tex.filter = ctx.LINEAR, ctx.LINEAR
            scale = tex.properties.get("scale", 1.0)
            self.textures.append(gl_tex)
            self.half_sizes.append((image.width * scale / 2, image.height * scale / 2))
        self.capacity = 0
        self._allocate(ctx, 4096)
        self._ready = True

    def _allocate(self, ctx, capacity):
        self.capacity = capacity
        self.instances = ctx.buffer(reserve=capacity * FLOATS_PER_INSTANCE * 4, usage="stream")
        self.geometry = ctx.geometry(
            [BufferDescription(self.corners, "2f", ["in_corner"]),
             BufferDescription(self.instances, "2f 1f 1f 4f", ["in_center", "in_angle", "in_scale", "in_color"],
                               instanced=True)],
            mode=ctx.TRIANGLE_STRIP,
        )

    def draw(self, store):
        ctx = arcade.get_window().ctx
        if not self._ready:
            self._setup(ctx)
        n = store.count
        if n == 0:
            return
        used = store.used[:n]
        species = store.species[:n]
        alive = store.alive[:n]
        body = store.body
        ctx.enable(ctx.BLEND)
        for s, texture in enumerate(self.textures):
            rows = np.nonzero(used & (species == s))[0]
            count = len(rows)
            if count == 0:
                continue
            if count > self.capacity:
                self._allocate(ctx, int(count * 1.5))
            data = np.empty((count, FLOATS_PER_INSTANCE), dtype="f4")
            data[:, 0] = body.x[rows]
            data[:, 1] = body.y[rows]
            # Sprite art faces down; rotate so it faces the heading
            data[:, 2] = body.heading[rows] + SPRITE_ANGLE_OFFSET
            data[:, 3] = store.genes.size[rows]
            data[:, 4:8] = 1.0
            dead = ~alive[rows]
            if dead.any():
                data[dead, 4:8] = CORPSE_COLOR
            self.instances.write(data.tobytes())
            texture.use(0)
            self.program["tex"] = 0
            self.program["half_size"] = self.half_sizes[s]
            self.geometry.render(self.program, instances=count)
