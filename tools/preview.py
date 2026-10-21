"""
Render a few frames of a preset headlessly (hidden window) to see what it looks like.

    .venv/bin/python tools/preview.py "Scenario - Predator cycles" --minutes 8 --out preview.png
    .venv/bin/python tools/preview.py defaults --minutes 8 --out preview.png   (the code defaults)
"""
import argparse
import json

from _headless import ROOT  # noqa: F401  (sets path / cwd)

import arcade  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import settings  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("preset")
    ap.add_argument("--minutes", type=float, default=8)
    ap.add_argument("--out", default="preview.png")
    ap.add_argument("--whole-map", action="store_true", help="zoom out to show the whole map")
    args = ap.parse_args()
    if args.preset == "defaults":
        overrides = {}
    else:
        with open(settings._preset_path(args.preset)) as f:
            overrides = json.load(f)
    # The window re-reads settings on setup: make it see this preset, not settings.json
    settings.load = lambda: overrides
    settings.apply(overrides)
    np.random.seed(1)
    from sim_window import SimulationWindow
    w = SimulationWindow(open_settings=False)
    w.set_visible(False)
    w.settings_watcher.poll = lambda: (None, False)
    w.setup()
    if args.whole_map:
        cc = w.camera_controller
        cc.camera.zoom = cc.min_zoom
        cc.center_camera()
    shots = []
    total = int(args.minutes * 3600)
    for i in range(total):
        w.on_update(1 / 60)
        if i in (total // 3, 2 * total // 3, total - 1):
            w._refresh_hud()
            w.on_draw()
            shots.append(arcade.get_image(0, 0, w.width, w.height))
    out = Image.new("RGB", (shots[0].width * len(shots), shots[0].height))
    for k, im in enumerate(shots):
        out.paste(im, (k * im.width, 0))
    out.resize((out.width // 2, out.height // 2)).save(args.out)
    print("stats:", dict(w.entity_manager.stats))


if __name__ == "__main__":
    main()
