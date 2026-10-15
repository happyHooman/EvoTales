"""
Procedural map generation, Minecraft-style: smooth noise fields for elevation,
temperature and moisture decide each tile's biome.

    tiles = generate(MAP_CONFIG)          # int array (rows, cols) of biome ids, row 0 = bottom
    image = render_ground(tiles, ...)     # PIL image to draw as the ground

Everything is numpy; a 200 x 150 tile map takes well under a second.
"""
import numpy as np
from PIL import Image

# Biome ids (order matters: index into BIOMES)
WATER, BEACH, GRASSLAND, FOREST, DESERT, SWAMP, TUNDRA = range(7)
BIOMES = ("water", "beach", "grassland", "forest", "desert", "swamp", "tundra")
BLOCKED_BIOMES = (WATER,)

# Ground colours (base, and the darker "speckle" colour) per biome
PALETTE = {
    WATER: ((70, 140, 200), (55, 120, 185)),
    BEACH: ((230, 214, 150), (214, 196, 130)),
    GRASSLAND: ((178, 210, 70), (160, 196, 60)),
    FOREST: ((70, 135, 60), (52, 112, 46)),
    DESERT: ((222, 196, 120), (204, 176, 100)),
    SWAMP: ((90, 110, 70), (70, 92, 60)),
    TUNDRA: ((214, 226, 230), (190, 205, 212)),
}


def fractal_noise(rows, cols, scale, octaves, rng):
    """Smooth value noise in [0, 1]: random lattices of decreasing size, bilinearly
    upsampled and summed."""
    total = np.zeros((rows, cols))
    amplitude, weight = 1.0, 0.0
    period = scale
    for _ in range(octaves):
        gr = int(np.ceil(rows / period)) + 2
        gc = int(np.ceil(cols / period)) + 2
        lattice = rng.random((gr, gc))
        y = np.arange(rows) / period
        x = np.arange(cols) / period
        y0, x0 = np.floor(y).astype(int), np.floor(x).astype(int)
        fy, fx = y - y0, x - x0
        fy = fy * fy * (3 - 2 * fy)  # smoothstep
        fx = fx * fx * (3 - 2 * fx)
        a = lattice[y0][:, x0]
        b = lattice[y0][:, x0 + 1]
        c = lattice[y0 + 1][:, x0]
        d = lattice[y0 + 1][:, x0 + 1]
        top = a + (b - a) * fx[None, :]
        bottom = c + (d - c) * fx[None, :]
        total += amplitude * (top + (bottom - top) * fy[:, None])
        weight += amplitude
        amplitude *= 0.5
        period = max(period / 2, 1.0)
    return total / weight


def generate(cfg):
    """Biome id per tile, shape (rows, cols)."""
    rows, cols = int(cfg["height_tiles"]), int(cfg["width_tiles"])
    rng = np.random.default_rng(int(cfg["seed"]))
    elevation = fractal_noise(rows, cols, cfg["terrain_scale"], 5, rng)
    temperature = fractal_noise(rows, cols, cfg["climate_scale"], 3, rng) + cfg["temperature_shift"]
    # Latitude: warmer toward the bottom (south) of the map, colder toward the top
    latitude = np.linspace(0.5, -0.5, rows)[:, None]
    temperature = temperature + cfg["latitude_strength"] * latitude
    moisture = fractal_noise(rows, cols, cfg["climate_scale"], 3, rng) + cfg["moisture_shift"]
    # Sharpen contrast a little: raw value noise clusters around 0.5
    elevation = np.clip((elevation - 0.5) * 1.8 + 0.5, 0, 1)
    temperature = np.clip((temperature - 0.5) * 2.0 + 0.5, 0, 1)
    moisture = np.clip((moisture - 0.5) * 2.0 + 0.5, 0, 1)

    tiles = np.full((rows, cols), GRASSLAND, dtype=np.int8)
    tiles[(moisture > 0.55)] = FOREST
    tiles[(temperature > 0.62) & (moisture < 0.42)] = DESERT
    tiles[(temperature > 0.5) & (moisture > 0.75)] = SWAMP
    tiles[temperature < 0.28] = TUNDRA
    water_level = cfg["water_level"]
    tiles[elevation < water_level + cfg["beach_width"]] = BEACH
    tiles[elevation < water_level] = WATER
    # A ring of water around the edge keeps creatures on the map
    tiles[0, :] = tiles[-1, :] = WATER
    tiles[:, 0] = tiles[:, -1] = WATER
    return tiles


def render_ground(tiles, tile_size, seed):
    """Ground picture: biome colours, a per-pixel speckle and soft blending at borders."""
    rows, cols = tiles.shape
    rng = np.random.default_rng(int(seed) + 1)
    base = np.zeros((len(BIOMES), 3), dtype=np.float32)
    dark = np.zeros((len(BIOMES), 3), dtype=np.float32)
    for b, (c1, c2) in PALETTE.items():
        base[b], dark[b] = c1, c2
    # Blend tile colours with their neighbours so borders aren't hard staircases
    colour = base[tiles]
    padded = np.pad(colour, ((1, 1), (1, 1), (0, 0)), mode="edge")
    soft = (padded[1:-1, 1:-1] * 4 + padded[:-2, 1:-1] + padded[2:, 1:-1]
            + padded[1:-1, :-2] + padded[1:-1, 2:]) / 8.0
    # Upsample to pixels with bilinear smoothing, then add speckle in each biome's darker colour
    smooth = Image.fromarray(np.clip(soft, 0, 255).astype(np.uint8), "RGB").resize(
        (cols * tile_size, rows * tile_size), Image.BILINEAR)
    pix = np.asarray(smooth, dtype=np.float32).copy()
    tile_of_pixel = np.repeat(np.repeat(tiles, tile_size, axis=0), tile_size, axis=1)
    speckle = rng.random(pix.shape[:2]) < 0.12
    pix[speckle] = dark[tile_of_pixel[speckle]]
    shade = 1.0 + (rng.random(pix.shape[:2]) - 0.5)[..., None] * 0.06
    pix = np.clip(pix * shade, 0, 255).astype(np.uint8)
    # Row 0 of `tiles` is the bottom of the world; images are top-down
    return Image.fromarray(pix[::-1], "RGB")
