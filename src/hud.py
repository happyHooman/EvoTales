"""
Screen-space panels: a live population graph and an inspector for the creature
being followed (click a creature to follow it; click empty ground or press Esc
to stop).
"""
from collections import deque

import arcade
import numpy as np

from engine import ACTION_NAMES
from engine.store import GENES
from world.mapgen import BIOMES

SAMPLE_EVERY = 4.0   # simulated seconds between graph samples
HISTORY = 450        # samples kept (30 simulated minutes, long enough to see population waves)
GRAPH_W, GRAPH_H = 320, 130
SERIES_COLORS = {
    "plants": (60, 140, 60),
    "herbivores": (140, 230, 120),
    "smarties": (175, 145, 255),
    "carnivores": (255, 95, 75),
}
PANEL_BG = (20, 24, 30, 190)


class PopulationGraph:
    def __init__(self, layers):
        self.layers = layers
        self.visible = True
        self.history = {layer: deque(maxlen=HISTORY) for layer in layers}
        self._timer = 0.0
        self.labels = {layer: arcade.Text("", 0, 0, SERIES_COLORS[layer], 10) for layer in layers}

    def reset(self):
        for h in self.history.values():
            h.clear()

    def update(self, world, dt):
        self._timer -= dt
        if self._timer > 0:
            return
        self._timer = SAMPLE_EVERY
        for layer in self.layers:
            self.history[layer].append(world.population(layer))

    def draw(self, window_width):
        if not self.visible or not self.history[self.layers[0]]:
            return
        left, bottom = window_width - GRAPH_W - 10, 34
        arcade.draw_lrbt_rectangle_filled(left, left + GRAPH_W, bottom, bottom + GRAPH_H, PANEL_BG)
        plot_l, plot_r = left + 8, left + GRAPH_W - 92
        plot_b, plot_t = bottom + 8, bottom + GRAPH_H - 8
        for k, layer in enumerate(self.layers):
            values = np.array(self.history[layer], dtype=float)
            # Each series is scaled to its own peak, so small populations stay readable
            peak = max(values.max(), 1.0)
            xs = plot_l + (plot_r - plot_l) * np.arange(len(values)) / (HISTORY - 1)
            ys = plot_b + (plot_t - plot_b) * values / peak
            if len(values) > 1:
                arcade.draw_line_strip(list(zip(xs, ys)), SERIES_COLORS[layer], 2)
            label = self.labels[layer]
            label.text = f"{layer[:5]} {int(values[-1])}"
            label.x, label.y = plot_r + 8, plot_t - 12 - 16 * k
            label.draw()


class Inspector:
    """Follows one creature: camera tracks it, a panel shows its state and genes."""

    def __init__(self):
        self.uid = -1
        self.row = -1
        self.text = arcade.Text("", 10, 0, arcade.color.WHITE, 11, multiline=True, width=420)
        self._note = ""

    @property
    def active(self):
        return self.uid >= 0

    def pick(self, store, x, y, radius=30.0):
        """Follow the living creature nearest to world point (x, y), if any is close."""
        rows = store.living_rows()
        if not len(rows):
            return False
        d2 = (store.body.x[rows] - x) ** 2 + (store.body.y[rows] - y) ** 2
        j = int(np.argmin(d2))
        if d2[j] > radius * radius:
            return False
        self.row, self.uid = int(rows[j]), int(store.core.uid[rows[j]])
        store.watched_uid, store.watched_death = self.uid, None
        self._note = ""
        return True

    def stop(self, store=None):
        self.uid = self.row = -1
        if store is not None:
            store.watched_uid = -1

    def update(self, store):
        """Position to keep the camera on, or None."""
        if not self.active:
            return None
        r = self.row
        if not (store.used[r] and store.core.uid[r] == self.uid):
            self._note = f"gone ({store.watched_death or 'eaten'})"
            self.stop(store)
            return None
        if not store.alive[r]:
            self._note = f"dead: {store.watched_death}"
        return store.body.x[r], store.body.y[r]

    def draw(self, store, window_height):
        if not self.active:
            if self._note:
                self.text.text = f"Followed creature {self._note}. Click another to follow."
                self.text.y = window_height - 60
                self.text.draw()
            return
        r = self.row
        v, m = store.vitals, store.mind
        layer = store.species_type(r).layer_name
        state = ACTION_NAMES.get(int(m.action[r]), "?") if store.alive[r] else "dead"
        if store.alive[r] and m.running[r]:
            state += " (running)"
        if v.tired[r]:
            state += ", tired"
        if store.alive[r] and m.stand_timer[r] > 0:
            state += ", standing its ground"
        if store.alive[r] and m.crowd[r] > store.p("crowd_limit", r):
            state += f", crammed ({int(m.crowd[r])} too close)"
        # The genes that set this creature apart the most (each is x1.00 for its species)
        genes = sorted(GENES, key=lambda g: -abs(np.log(getattr(store.genes, g)[r])))[:4]
        gene_text = [f"{g.replace('_', ' ')} x{getattr(store.genes, g)[r]:.2f}" for g in genes]
        lines = [
            f"{layer[:-1]} #{self.uid}  gen {store.core.generation[r]}",
            f"{state} in {BIOMES[store.core.biome[r]]}" + (f"  - {self._note}" if self._note else ""),
            f"health  {v.health[r]:5.1f} / {store.p('max_health', r):.0f}",
            f"stamina {v.stamina[r]:5.1f} / {store.p('max_stamina', r):.0f}",
            f"food    {v.food[r]:5.1f} / {store.p('max_food', r):.0f}",
            f"attack  {float(store.attack_value(r)):5.1f} (max {store.p('attack', r):.0f})",
            "most unusual genes:",
            "  " + ",  ".join(gene_text[:2]),
            "  " + ",  ".join(gene_text[2:]),
            "Esc or click empty ground to stop following",
        ]
        self.text.text = "\n".join(lines)
        height = 19 * len(lines) + 14
        top = window_height - 50
        arcade.draw_lrbt_rectangle_filled(4, 434, top - height, top, PANEL_BG)
        self.text.y = top - 18
        self.text.draw()
