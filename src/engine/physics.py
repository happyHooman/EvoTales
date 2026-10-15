"""
PhysicsEngine: the only writer of store.body (x, y, vx, vy, heading, speed).

Each step it reads store.command (the heading and speed behaviour asked for) and,
for every living creature at once:
1. turns the heading toward the commanded heading, at most turn_rate * dt,
2. sets the speed and velocity,
3. moves, sliding along walls/water instead of entering them,
4. pushes apart bodies that overlap (bodies are solid discs).

It also answers geometry questions for the other systems (free_heading).
"""
import math

import numpy as np

TWO_PI = 2 * math.pi


def wrap_angle(a):
    """Angle difference into (-pi, pi]."""
    return (a + math.pi) % TWO_PI - math.pi


class PhysicsEngine:
    def __init__(self, store, world):
        self.store = store
        self.world = world

    def step(self, rows, dt):
        if not len(rows):
            return
        self._turn_and_accelerate(rows, dt)
        self._move(rows, dt)
        self._separate(rows)

    def _turn_and_accelerate(self, rows, dt):
        s, body, cmd = self.store, self.store.body, self.store.command
        diff = wrap_angle(cmd.heading[rows] - body.heading[rows])
        max_turn = s.p("turn_rate", rows) * dt
        heading = (body.heading[rows] + np.clip(diff, -max_turn, max_turn)) % TWO_PI
        speed = cmd.speed[rows]
        body.heading[rows] = heading
        body.speed[rows] = speed
        body.vx[rows] = speed * np.cos(heading)
        body.vy[rows] = speed * np.sin(heading)

    def _move(self, rows, dt):
        """Integrate positions; slide along walls/water instead of entering them."""
        body, blocked_at = self.store.body, self.world.blocked_at
        x, y = body.x[rows], body.y[rows]
        nx = x + body.vx[rows] * dt
        ny = y + body.vy[rows] * dt
        blocked = blocked_at(nx, ny)
        if blocked.any():
            bx = blocked_at(nx, y)   # try moving along x only
            by = blocked_at(x, ny)   # or along y only
            nx = np.where(blocked & bx, x, nx)
            ny = np.where(blocked & by, y, ny)
            still = blocked_at(nx, ny)
            nx = np.where(still, x, nx)
            ny = np.where(still, y, ny)
        body.x[rows] = nx
        body.y[rows] = ny

    def _separate(self, rows):
        """Push apart creatures whose bodies overlap. Neighbours are found by sorting
        creatures into cells and looking up adjacent cells with searchsorted."""
        if len(rows) < 2:
            return
        body = self.store.body
        x, y, r = body.x[rows], body.y[rows], self.store.radius[rows]
        cell = float(2 * r.max())
        cx = np.floor(x / cell).astype(np.int64)
        cy = np.floor(y / cell).astype(np.int64)
        key = cx * 100003 + cy
        order = np.argsort(key, kind="stable")
        skey = key[order]
        pi_list, pj_list = [], []
        for ox, oy in ((0, 0), (1, -1), (1, 0), (1, 1), (0, 1)):
            nkey = (cx + ox) * 100003 + (cy + oy)
            lo = np.searchsorted(skey, nkey, side="left")
            hi = np.searchsorted(skey, nkey, side="right")
            counts = hi - lo
            total = counts.sum()
            if total == 0:
                continue
            i = np.repeat(np.arange(len(rows)), counts)
            starts = np.repeat(lo - np.cumsum(counts) + counts, counts)
            j = order[np.arange(total) + starts]
            if ox == 0 and oy == 0:
                keep = j > i  # each same-cell pair once
                i, j = i[keep], j[keep]
            pi_list.append(i)
            pj_list.append(j)
        if not pi_list:
            return
        i = np.concatenate(pi_list)
        j = np.concatenate(pj_list)
        dx = x[j] - x[i]
        dy = y[j] - y[i]
        d = np.sqrt(dx * dx + dy * dy)
        overlap = r[i] + r[j] - d
        m = overlap > 0
        if not m.any():
            return
        i, j, dx, dy, d, overlap = i[m], j[m], dx[m], dy[m], d[m], overlap[m]
        d = np.where(d < 1e-6, 1e-6, d)
        push = 0.5 * overlap / d
        px = np.zeros(len(rows))
        py = np.zeros(len(rows))
        np.add.at(px, i, -dx * push)
        np.add.at(py, i, -dy * push)
        np.add.at(px, j, dx * push)
        np.add.at(py, j, dy * push)
        nx, ny = x + px, y + py
        ok = ~self.world.blocked_at(nx, ny)
        body.x[rows] = np.where(ok, nx, x)
        body.y[rows] = np.where(ok, ny, y)

    # --------------------------------------------------------------- queries

    def pairs_within(self, rows, radius):
        """Every pair of `rows` closer than `radius`, once each, as local indices
        (i, j) into rows plus their distance. Found by sorting into cells and
        looking up neighbouring cells, so it scales with local density."""
        body = self.store.body
        x, y = body.x[rows], body.y[rows]
        empty = (np.zeros(0, int), np.zeros(0, int), np.zeros(0))
        if len(rows) < 2 or radius <= 0:
            return empty
        cx = np.floor(x / radius).astype(np.int64)
        cy = np.floor(y / radius).astype(np.int64)
        key = cx * 100003 + cy
        order = np.argsort(key, kind="stable")
        skey = key[order]
        pi_list, pj_list = [], []
        for ox, oy in ((0, 0), (1, -1), (1, 0), (1, 1), (0, 1)):
            nkey = (cx + ox) * 100003 + (cy + oy)
            lo = np.searchsorted(skey, nkey, side="left")
            hi = np.searchsorted(skey, nkey, side="right")
            counts = hi - lo
            total = counts.sum()
            if total == 0:
                continue
            i = np.repeat(np.arange(len(rows)), counts)
            starts = np.repeat(lo - np.cumsum(counts) + counts, counts)
            j = order[np.arange(total) + starts]
            if ox == 0 and oy == 0:
                keep = j > i
                i, j = i[keep], j[keep]
            pi_list.append(i)
            pj_list.append(j)
        if not pi_list:
            return empty
        i, j = np.concatenate(pi_list), np.concatenate(pj_list)
        d = np.hypot(x[j] - x[i], y[j] - y[i])
        near = d <= radius
        return i[near], j[near], d[near]

    def free_heading(self, rows, base, offsets):
        """First direction among base+offsets with no wall/water just ahead, per row
        (NaN when every option is blocked). Read-only."""
        s = self.store
        probe = s.radius[rows] + s.p("wall_probe_distance", rows)
        angles = base[:, None] + offsets[None, :]
        ca, sa = np.cos(angles), np.sin(angles)
        x, y = s.body.x[rows][:, None], s.body.y[rows][:, None]
        pr = probe[:, None]
        blocked = (self.world.blocked_at(x + pr * ca, y + pr * sa)
                   | self.world.blocked_at(x + 2 * pr * ca, y + 2 * pr * sa))
        free = ~blocked
        first = np.argmax(free, axis=1)
        result = angles[np.arange(len(rows)), first]
        return np.where(free.any(axis=1), result, np.nan)
