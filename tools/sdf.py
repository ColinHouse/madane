"""Anti-aliased 2D drawing into a float RGB canvas (H, W, 3) via signed distances.

Each primitive walks only its bounding box and skips pixels outside its band,
so thin rings and lines stay cheap at full HD. Compiled with numba.
"""
import math

import numpy as np
from numba import njit


@njit(cache=True, fastmath=True)
def _blend(c, y, x, a, r, g, b):
    if a <= 0.0:
        return
    c[y, x, 0] += (r - c[y, x, 0]) * a
    c[y, x, 1] += (g - c[y, x, 1]) * a
    c[y, x, 2] += (b - c[y, x, 2]) * a


@njit(cache=True, fastmath=True)
def _bounds(c, x0, y0, x1, y1):
    H, W = c.shape[0], c.shape[1]
    return max(0, int(x0)), max(0, int(y0)), min(W, int(math.ceil(x1))), min(H, int(math.ceil(y1)))


@njit(cache=True, fastmath=True)
def circle(c, cx, cy, rad, col, op, glow):
    pad = 2.0 + glow * 3.0
    xa, ya, xb, yb = _bounds(c, cx - rad - pad, cy - rad - pad, cx + rad + pad, cy + rad + pad)
    for y in range(ya, yb):
        dy = y + 0.5 - cy
        for x in range(xa, xb):
            dx = x + 0.5 - cx
            d = math.sqrt(dx * dx + dy * dy) - rad
            if d > pad:
                continue
            a = 0.5 - d
            if a < 0.0:
                a = 0.0
            if glow > 0.0 and d > 0.0:
                gl = 0.45 * math.exp(-d * d / (2.0 * glow * glow))
                if gl > a:
                    a = gl
            _blend(c, y, x, min(a, 1.0) * op, col[0], col[1], col[2])


@njit(cache=True, fastmath=True)
def ring(c, cx, cy, rad, width, col, op, a0, span, glow):
    """span >= 2*pi draws the full ring; otherwise an arc clockwise from a0 (0 = 12 o'clock)."""
    pad = width + 2.0 + glow * 3.0
    xa, ya, xb, yb = _bounds(c, cx - rad - pad, cy - rad - pad, cx + rad + pad, cy + rad + pad)
    full = span >= 2.0 * math.pi
    for y in range(ya, yb):
        dy = y + 0.5 - cy
        for x in range(xa, xb):
            dx = x + 0.5 - cx
            dist = math.sqrt(dx * dx + dy * dy)
            d = abs(dist - rad) - width * 0.5
            if d > pad:
                continue
            a = 0.5 - d
            if a < 0.0:
                a = 0.0
            if glow > 0.0 and d > 0.0:
                gl = 0.35 * math.exp(-d * d / (2.0 * glow * glow))
                if gl > a:
                    a = gl
            if not full:
                ang = math.atan2(dx, -dy) % (2.0 * math.pi)
                rel = (ang - a0) % (2.0 * math.pi)
                k = (span - rel) * rad / 1.5
                if k <= 0.0:
                    continue
                if k < 1.0:
                    a *= k
            _blend(c, y, x, min(a, 1.0) * op, col[0], col[1], col[2])


@njit(cache=True, fastmath=True)
def line(c, x0, y0, x1, y1, width, col, op, glow):
    pad = width + 2.0 + glow * 3.0
    xa, ya, xb, yb = _bounds(c, min(x0, x1) - pad, min(y0, y1) - pad, max(x0, x1) + pad, max(y0, y1) + pad)
    vx, vy = x1 - x0, y1 - y0
    vv = vx * vx + vy * vy + 1e-9
    for y in range(ya, yb):
        py = y + 0.5 - y0
        for x in range(xa, xb):
            px = x + 0.5 - x0
            h = (px * vx + py * vy) / vv
            if h < 0.0:
                h = 0.0
            elif h > 1.0:
                h = 1.0
            ex, ey = px - vx * h, py - vy * h
            d = math.sqrt(ex * ex + ey * ey) - width * 0.5
            if d > pad:
                continue
            a = 0.5 - d
            if a < 0.0:
                a = 0.0
            if glow > 0.0 and d > 0.0:
                gl = 0.4 * math.exp(-d * d / (2.0 * glow * glow))
                if gl > a:
                    a = gl
            _blend(c, y, x, min(a, 1.0) * op, col[0], col[1], col[2])


@njit(cache=True, fastmath=True)
def rect(c, cx, cy, w, h, angle, col, op, stroke):
    rad = math.sqrt(w * w + h * h) * 0.5 + 2.0
    xa, ya, xb, yb = _bounds(c, cx - rad, cy - rad, cx + rad, cy + rad)
    ca, sa = math.cos(angle), math.sin(angle)
    for y in range(ya, yb):
        dy = y + 0.5 - cy
        for x in range(xa, xb):
            dx = x + 0.5 - cx
            lx = dx * ca + dy * sa
            ly = -dx * sa + dy * ca
            qx, qy = abs(lx) - w * 0.5, abs(ly) - h * 0.5
            ox, oy = max(qx, 0.0), max(qy, 0.0)
            d = math.sqrt(ox * ox + oy * oy) + min(max(qx, qy), 0.0)
            if stroke > 0.0:
                d = abs(d + stroke * 0.5) - stroke * 0.5
            a = 0.5 - d
            if a <= 0.0:
                continue
            _blend(c, y, x, min(a, 1.0) * op, col[0], col[1], col[2])


@njit(cache=True, fastmath=True)
def petal(c, cx, cy, size, angle, col, op):
    """A sakura petal: an ellipse with a notch at its tip."""
    rad = size + 2.0
    xa, ya, xb, yb = _bounds(c, cx - rad, cy - rad, cx + rad, cy + rad)
    ca, sa = math.cos(angle), math.sin(angle)
    for y in range(ya, yb):
        dy = y + 0.5 - cy
        for x in range(xa, xb):
            dx = x + 0.5 - cx
            lx = (dx * ca + dy * sa) / size
            ly = (-dx * sa + dy * ca) / size
            d = (math.sqrt((lx / 0.55) ** 2 + (ly / 0.95) ** 2) - 1.0) * size * 0.55
            notch = math.sqrt(lx * lx + (ly - 1.02) ** 2) * size - size * 0.2
            if -notch > d:
                d = -notch
            a = 0.5 - d
            if a <= 0.0:
                continue
            _blend(c, y, x, min(a, 1.0) * op, col[0], col[1], col[2])


@njit(cache=True, fastmath=True)
def glyph(c, sprite, x, y, col, op, kx, ky, kr, kcol):
    """Blit an alpha sprite; inside the knockout circle (kr > 0) it takes kcol instead."""
    H, W = c.shape[0], c.shape[1]
    sh, sw = sprite.shape[0], sprite.shape[1]
    for j in range(sh):
        yy = y + j
        if yy < 0 or yy >= H:
            continue
        for i in range(sw):
            xx = x + i
            if xx < 0 or xx >= W:
                continue
            a = sprite[j, i]
            if a <= 0.0:
                continue
            r, g, b = col[0], col[1], col[2]
            if kr > 0.0:
                dx, dy = xx + 0.5 - kx, yy + 0.5 - ky
                inside = kr - math.sqrt(dx * dx + dy * dy) + 0.5
                if inside > 0.0:
                    m = min(inside, 1.0)
                    r = r + (kcol[0] - r) * m
                    g = g + (kcol[1] - g) * m
                    b = b + (kcol[2] - b) * m
            _blend(c, yy, xx, min(a, 1.0) * op, r, g, b)


@njit(cache=True, fastmath=True)
def finish(c, grain, gscale, vig, fade, out):
    """Grain (int8, half resolution), vignette and fade into uint8 RGB."""
    H, W = c.shape[0], c.shape[1]
    for y in range(H):
        gy = y >> 1
        for x in range(W):
            n = grain[gy, x >> 1] * gscale
            v = vig[y, x] * fade
            for k in range(3):
                val = (c[y, x, k] + n) * v
                if val < 0.0:
                    val = 0.0
                elif val > 1.0:
                    val = 1.0
                out[y, x, k] = np.uint8(val * 255.0 + 0.5)


@njit(cache=True, fastmath=True)
def circle_wipe(c, prev, cx, cy, rad):
    """Outside the circle the previous background shows through (for section wipes)."""
    H, W = c.shape[0], c.shape[1]
    for y in range(H):
        dy = y + 0.5 - cy
        for x in range(W):
            dx = x + 0.5 - cx
            m = (rad - math.sqrt(dx * dx + dy * dy)) / 3.0
            if m >= 1.0:
                continue
            if m < 0.0:
                m = 0.0
            for k in range(3):
                c[y, x, k] = prev[y, x, k] + (c[y, x, k] - prev[y, x, k]) * m


@njit(cache=True, fastmath=True)
def polyline(c, xs, ys, ops, width, col, glow):
    """A whole path at once (distance to the nearest segment), so joints never double up.

    ops[i] is the opacity of segment i (for lines that fade toward their tail)."""
    n = xs.shape[0]
    if n < 2:
        return
    pad = width + 2.0 + glow * 3.0
    xa, ya, xb, yb = _bounds(c, xs.min() - pad, ys.min() - pad, xs.max() + pad, ys.max() + pad)
    for y in range(ya, yb):
        py0 = y + 0.5
        for x in range(xa, xb):
            px0 = x + 0.5
            best, bop = 1e9, 0.0
            for i in range(n - 1):
                x0, y0 = xs[i], ys[i]
                vx, vy = xs[i + 1] - x0, ys[i + 1] - y0
                # quick reject: outside this segment's padded box
                if px0 < min(x0, x0 + vx) - pad or px0 > max(x0, x0 + vx) + pad:
                    continue
                if py0 < min(y0, y0 + vy) - pad or py0 > max(y0, y0 + vy) + pad:
                    continue
                px, py = px0 - x0, py0 - y0
                h = (px * vx + py * vy) / (vx * vx + vy * vy + 1e-9)
                if h < 0.0:
                    h = 0.0
                elif h > 1.0:
                    h = 1.0
                ex, ey = px - vx * h, py - vy * h
                d = math.sqrt(ex * ex + ey * ey)
                if d < best:
                    best, bop = d, ops[i]
            d = best - width * 0.5
            if d > pad:
                continue
            a = 0.5 - d
            if a < 0.0:
                a = 0.0
            if glow > 0.0 and d > 0.0:
                gl = 0.4 * math.exp(-d * d / (2.0 * glow * glow))
                if gl > a:
                    a = gl
            _blend(c, y, x, min(a, 1.0) * bop, col[0], col[1], col[2])
