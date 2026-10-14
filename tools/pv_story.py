"""まだね PV — story version (故事向).

A short film in the producer's room, cut to the song:
  1A    2 a.m.; the monitor wakes; Miku's first 「あ」 lands on the piano roll.
  1B    notes go down one by one, breath marks drawn in.
  1サビ the sakura outside blooms; she sings; at dawn the producer waves 「またね」.
  間奏  the seasons go by in the window.
  2A    busy days, an empty chair, the folder nobody opens, where she waits.
  2B    nights get shorter; the producer stands in the doorway.
  2サビ a year later the folder is opened again.
  Solo  the years, traced by the guitar across the night sky.
  Cメロ the room after the producer has gone; the monitor wakes by itself
        and she sings to nobody.
  落ちサビ in grey.  ラスサビ every spring at once.  Outro 2 a.m. again.

Shots are flat silhouettes lit by a few light maps (monitor, window, lamp);
the lyrics run as subtitles, each character arriving on its sung syllable.

    python -I tools/pv_story.py <mix.wav> <out.mp4>
    python -I tools/pv_story.py --stills <mix.wav> <dir> t1 t2 ...
"""
import math
import random
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import soundfile
from numba import njit
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

import figures as F
import lyric_align
import pv_lyric as PL
import sdf
from pv_lyric import FPS, GOTHIC, H, LATIN, MINCHO, TAIL, TYPE, W, ZH, Canvas, clamp01, ease, ease_out, hexc, ramp

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "out" / "pv_story_cache"
VOCAL = ROOT / "reaper" / "madane_v15" / "miku_leveled.wav"
WW, WH = 2304, 1296            # the room is drawn 1.2x the frame, so the camera can push in and stay sharp
SS = 3                          # supersampling of the pre-drawn layers

TEAL = hexc("#39c5bb")
TEAL_HI = hexc("#9ff3ea")
SAKURA = hexc("#f6b3c8")
SAKURA_DEEP = hexc("#e57a9c")
INK = hexc("#f3f1f6")
BLACK = np.zeros(3, np.float32)

# room geometry (world pixels)
FLOOR = 1000
GLASS = (270, 200, 870, 780)             # window glass x0 y0 x1 y1
SCREEN = (1456, 486, 1924, 749)          # monitor screen
CLOCK = (1140, 330, 78)
SEATED_H, SEATED_CROWN = 735, 515        # the producer at the desk: scale (standing height) and crown height
STAND_X, STAND_FEET, STAND_H = 1400, 1225, 800
DOOR_H = 700
MIKU_ROOM_H, MIKU_SCREEN_H, MIKU_SMALL_H, MIKU_SIT_H = 330, 885, 216, 420
MIKU_ROOM_X = 980
CALENDAR = (2020, 170, 2200, 350)
CHAIR_X = 1690


# ------------------------------------------------------------------------- geometry helpers
def bez(p0, p1, p2, p3, n=28):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.asarray(p, float) for p in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def strip(center, w0, w1):
    """A band of width w0 -> w1 around a centreline, as a polygon."""
    c = np.asarray(center, float)
    d = np.gradient(c, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    w = np.linspace(w0, w1, len(c))[:, None] / 2
    return np.concatenate([c + nrm * w, (c - nrm * w)[::-1]])


class Sheet:
    """A supersampled PIL surface addressed in world pixels."""

    def __init__(self, w, h, mode="L", fill=0, ss=SS):
        self.ss, self.w, self.h = ss, w, h
        self.img = Image.new(mode, (int(w * ss), int(h * ss)), fill)
        self.d = ImageDraw.Draw(self.img)

    def _p(self, pts):
        return [(float(x) * self.ss, float(y) * self.ss) for x, y in pts]

    def poly(self, pts, fill=255):
        self.d.polygon(self._p(pts), fill=fill)

    def rect(self, x0, y0, x1, y1, fill=255, r=0):
        box = [x0 * self.ss, y0 * self.ss, x1 * self.ss, y1 * self.ss]
        if r:
            self.d.rounded_rectangle(box, radius=r * self.ss, fill=fill)
        else:
            self.d.rectangle(box, fill=fill)

    def ellipse(self, cx, cy, rx, ry, fill=255):
        self.d.ellipse([(cx - rx) * self.ss, (cy - ry) * self.ss, (cx + rx) * self.ss, (cy + ry) * self.ss], fill=fill)

    def capsule(self, p0, p1, w, fill=255):
        self.d.line(self._p([p0, p1]), fill=fill, width=max(1, int(round(w * self.ss))))
        for x, y in (p0, p1):
            self.ellipse(x, y, w / 2, w / 2, fill)

    def chain(self, pts, w, fill=255):
        for a, b in zip(pts[:-1], pts[1:]):
            self.capsule(a, b, w, fill)

    def array(self):
        img = self.img.resize((int(self.w), int(self.h)), Image.LANCZOS)
        a = np.asarray(img, np.float32) / 255
        return np.ascontiguousarray(a)


def rgb255(c):
    return tuple(int(round(v * 255)) for v in c)


# ------------------------------------------------------------------------------- the room
WALL, WALL2 = hexc("#3a4566"), hexc("#323c5a")
FLOORC, RUG = hexc("#2a2f45"), hexc("#3d3550")
WOOD, WOOD2 = hexc("#5a4a46"), hexc("#43373a")
FRAME, CURTAIN = hexc("#d9d6dc"), hexc("#5b6a8e")
METAL, DARK = hexc("#22252e"), hexc("#14151b")
BOX, BOX2 = hexc("#9b7b5c"), hexc("#7f644c")


def room_layers(state):
    """Albedo (RGB) and a mask that is 0 where the room is see-through (window glass, screen)."""
    S = Sheet(WW, WH, "RGB", rgb255(WALL))
    M = Sheet(WW, WH, "L", 255)
    s = S
    # wall: a darker band low down, skirting board, floor
    s.rect(0, 860, WW, FLOOR, rgb255(WALL2))
    s.rect(0, FLOOR - 18, WW, FLOOR, rgb255(hexc("#4a5576")))
    s.rect(0, FLOOR, WW, WH, rgb255(FLOORC))
    s.ellipse(1720, 1130, 620, 95, rgb255(RUG))
    # curtains, window frame, sill
    for x0, x1 in ((170, 300), (840, 970)):
        s.rect(x0, 150, x1, 860, rgb255(CURTAIN))
        for k in range(1, 4):
            xx = x0 + (x1 - x0) * k / 4
            s.rect(xx - 3, 150, xx + 3, 860, rgb255(CURTAIN * 0.82))
    s.rect(140, 138, 1000, 156, rgb255(METAL))
    x0, y0, x1, y1 = GLASS
    s.rect(x0 - 24, y0 - 24, x1 + 24, y1 + 24, rgb255(FRAME))
    s.rect(240, y1 + 24, 900, y1 + 50, rgb255(FRAME * 0.9))
    M.rect(x0, y0, x1, y1, 0)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    s.rect(mx - 9, y0, mx + 9, y1, rgb255(FRAME)); M.rect(mx - 9, y0, mx + 9, y1, 255)
    s.rect(x0, my - 9, x1, my + 9, rgb255(FRAME)); M.rect(x0, my - 9, x1, my + 9, 255)
    # wall clock, calendar, shelf with books
    cx, cy, r = CLOCK
    s.ellipse(cx, cy, r + 10, r + 10, rgb255(METAL))
    s.ellipse(cx, cy, r, r, rgb255(hexc("#e9e6ee")))
    x0, y0, x1, y1 = CALENDAR
    s.rect(x0, y0, x1, y1, rgb255(hexc("#ece8ef")))
    s.rect(x0, y0, x1, y0 + 34, rgb255(hexc("#c9475f")))
    s.rect(1980, 380, 2290, 394, rgb255(WOOD))
    rng = random.Random(4)
    x = 1995
    while x < 2270:
        w = rng.randint(16, 30)
        h = rng.randint(58, 92)
        s.rect(x, 380 - h, x + w, 380, rgb255(hexc(rng.choice(["#6b5f8e", "#8e5f6b", "#5f7f8e", "#a08a5f", "#4f5f7f"]))))
        x += w + rng.randint(1, 5)
    # desk
    s.rect(1300, 780, 2200, 806, rgb255(WOOD))
    s.rect(1320, 806, 1350, FLOOR, rgb255(WOOD2))
    s.rect(1960, 806, 2180, FLOOR, rgb255(WOOD2))
    for yy in (860, 930):
        s.rect(1972, yy, 2168, yy + 4, rgb255(WOOD2 * 0.75))
        s.rect(2050, yy - 26, 2090, yy - 20, rgb255(METAL))
    # monitor, stand, keyboard, lamp, mug, plant
    s.rect(1440, 470, 1940, 760, rgb255(DARK), r=8)
    M.rect(*SCREEN, 0)
    s.rect(1670, 760, 1710, 780, rgb255(METAL))
    s.ellipse(1690, 780, 90, 8, rgb255(METAL))
    s.rect(1560, 772, 1820, 781, rgb255(METAL))
    s.ellipse(1360, 778, 46, 8, rgb255(METAL))
    s.capsule((1360, 776), (1395, 560), 10, rgb255(METAL))
    s.capsule((1395, 560), (1465, 505), 10, rgb255(METAL))
    s.poly([(1440, 488), (1500, 480), (1526, 530), (1452, 540)], rgb255(METAL))
    if state != "empty":
        s.rect(1990, 732, 2034, 780, rgb255(hexc("#e8e4ea")), r=6)
        s.capsule((2034, 745), (2046, 762), 7, rgb255(hexc("#e8e4ea")))
    pot = hexc("#b8705a")
    s.poly([(2098, 730), (2162, 730), (2154, 780), (2106, 780)], rgb255(pot))
    leaf = hexc("#5f8f6a") if state != "empty" else hexc("#8a7a5a")
    for ang, ln in ((-60, 70), (-95, 82), (-125, 66), (-40, 52), (-145, 50)):
        a = math.radians(ang + (25 if state == "empty" else 0))
        bx, by = 2130, 730
        ex, ey = bx + math.cos(a) * ln, by + math.sin(a) * ln * (0.55 if state == "empty" else 1)
        s.poly(strip(bez((bx, by), (bx + (ex - bx) * .3, by + (ey - by) * .7), (ex - 6, ey + 4), (ex, ey), 12), 14, 2), rgb255(leaf))
    if state == "busy":
        rng = random.Random(9)
        for k in range(6):
            x = 1340 + k * 18 + rng.randint(-6, 6)
            s.rect(x, 760 - k * 4, x + 120, 772 - k * 4, rgb255(hexc("#eceaf0") * (0.92 + 0.02 * k)))
        s.rect(1838, 742, 1862, 780, rgb255(hexc("#6fb0c9")), r=4)
        s.rect(1870, 750, 1892, 780, rgb255(hexc("#c96f8a")), r=4)
        s.rect(1050, 905, 1230, FLOOR + 10, rgb255(hexc("#3b3f52")), r=12)
        s.rect(1110, 880, 1170, 905, rgb255(hexc("#3b3f52")), r=10)
    if state == "empty":
        for (x0, y0, x1, y1) in ((930, 860, 1150, FLOOR + 6), (1150, 890, 1300, FLOOR + 6), (960, 740, 1130, 860)):
            s.rect(x0, y0, x1, y1, rgb255(BOX))
            s.rect(x0, y0, x1, y0 + 10, rgb255(BOX2))
            s.rect((x0 + x1) / 2 - 14, y0, (x0 + x1) / 2 + 14, y1, rgb255(hexc("#c9a77f")))
    return S.array(), M.array()


def chair_layer(state):
    """The office chair seen from behind, drawn over whoever sits in it."""
    S = Sheet(WW, WH, "RGB", (0, 0, 0))
    M = Sheet(WW, WH, "L", 0)
    x = CHAIR_X if state != "empty" else CHAIR_X + 20
    top = 700 if state != "empty" else 745
    col = rgb255(hexc("#262a3a"))
    for sh in (S, M):
        f = col if sh is S else 255
        sh.rect(x - 105, top, x + 105, 885, f, r=34)
        sh.rect(x - 12, 885, x + 12, 960, f)
        sh.poly([(x - 120, 968), (x + 120, 968), (x + 100, 954), (x - 100, 954)], f)
        for wx in (x - 112, x - 40, x + 40, x + 112):
            sh.ellipse(wx, 975, 13, 10, f)
        sh.rect(x - 140, 818, x - 118, 840, f, r=6)
        sh.rect(x + 118, 818, x + 140, 840, f, r=6)
    if state == "busy":                                   # a jacket left over the chair back
        jk = rgb255(hexc("#4b4f68"))
        for sh in (S, M):
            f = jk if sh is S else 255
            sh.poly([(x - 118, top + 6), (x + 118, top + 6), (x + 128, top + 210), (x + 60, top + 236), (x - 70, top + 228), (x - 126, top + 196)], f)
    return S.array(), M.array()


# --------------------------------------------------------------------------------- figures
def glow(mask, sigma):
    g = gaussian_filter(mask, sigma)
    return np.ascontiguousarray(g / max(1e-6, g.max()), dtype=np.float32)


# ------------------------------------------------------------------------------- the window
def branch(seed=11):
    """A sakura branch reaching in from the upper left, in unit coordinates of the view.
    Returns segments (x0, y0, x1, y1, width) and blossom anchors (x, y, size)."""
    rng = random.Random(seed)
    segs, buds = [], []

    def grow(x, y, ang, ln, w, depth):
        x1, y1 = x + math.cos(ang) * ln, y + math.sin(ang) * ln
        segs.append((x, y, x1, y1, w))
        if depth == 0 or w < 0.0025:
            buds.append((x1, y1, rng.uniform(0.7, 1.2)))
            return
        if depth <= 3:
            for _ in range(rng.randint(1, 3)):
                k = rng.uniform(0.3, 1.0)
                buds.append((x + (x1 - x) * k + rng.uniform(-.01, .01), y + (y1 - y) * k + rng.uniform(-.01, .01),
                             rng.uniform(0.5, 1.0)))
        for side in (-1, 1):
            if rng.random() < (0.92 if depth > 2 else 0.8):
                grow(x1, y1, ang + side * rng.uniform(0.25, 0.65) + rng.uniform(-0.15, 0.15),
                     ln * rng.uniform(0.62, 0.8), w * 0.68, depth - 1)

    grow(-0.08, 0.06, 0.42, 0.34, 0.034, 7)
    grow(-0.06, 0.32, 0.12, 0.22, 0.02, 5)
    return segs, buds


def branch_mask(w, h, segs):
    s = Sheet(w, h)
    for x0, y0, x1, y1, wd in segs:
        s.capsule((x0 * w, y0 * h), (x1 * w, y1 * h), max(1.2, wd * w))
    return s.array()


def skyline(w, h, seed=5):
    """Distant buildings along the bottom of the view; returns the mask and lit windows (x, y, phase)."""
    rng = random.Random(seed)
    s = Sheet(w, h)
    lights = []
    x = -10
    while x < w:
        bw = rng.uniform(0.05, 0.11) * w
        bh = rng.uniform(0.12, 0.3) * h
        s.rect(x, h - bh, x + bw, h)
        for _ in range(int(bw * bh / (w * h) * 900)):
            lights.append((x + rng.uniform(0.15, 0.85) * bw, h - bh + rng.uniform(0.1, 0.9) * bh, rng.random() * 6.28))
        x += bw + rng.uniform(0, 0.02) * w
    return s.array(), lights


# ------------------------------------------------------------------------------ assets
def build_assets():
    CACHE.mkdir(parents=True, exist_ok=True)
    save = lambda name, a: np.save(CACHE / f"{name}.npy", np.ascontiguousarray(a, dtype=np.float32))
    for state in ("tidy", "busy", "empty"):
        alb, mask = room_layers(state)
        save(f"room_{state}", alb)
        save(f"room_{state}_a", mask)
        ch, cm = chair_layer(state)
        save(f"chair_{state}", ch)
        save(f"chair_{state}_a", cm)
    def put(name, mask, x0, y0, rim=False):
        save(name, mask)
        np.save(CACHE / f"{name}_xy.npy", np.array([x0, y0], np.float32))
        if rim:
            save(name + "_rim", np.clip(mask - gaussian_filter(mask, 5), 0, 1) * 2.2)

    k = SEATED_H / 1000.0
    m, (ox, oy) = F.producer_seated(SEATED_H)
    put("p_seated", m, CHAIR_X - ox, SEATED_CROWN - oy + 580 * k, rim=True)
    for name, wave in (("p_stand", False), ("p_wave", True)):
        m, (ox, oy), elbow = F.producer_standing(STAND_H, wave=wave)
        x0, y0 = STAND_X - ox, STAND_FEET - oy
        put(name, m, x0, y0, rim=True)
        if elbow:
            np.save(CACHE / "p_elbow.npy", np.array([x0 + elbow[0], y0 + elbow[1]], np.float32))
    m, pv = F.forearm(STAND_H)
    save("p_forearm", m)
    np.save(CACHE / "p_forearm_pv.npy", np.array(pv, np.float32))
    m, o, _ = F.producer_standing(DOOR_H)
    save("p_door", m)
    np.save(CACHE / "p_door_o.npy", np.array(o, np.float32))
    for name, hgt in (("miku_room", MIKU_ROOM_H), ("miku_screen", MIKU_SCREEN_H), ("miku_small", MIKU_SMALL_H)):
        for pose in ("sing", "wave"):
            m, o, elbow = F.miku_standing(hgt, pose)
            nm = name + ("_wave" if pose == "wave" else "")
            save(nm, m)
            save(nm + "_glow", glow(m, max(3.0, hgt / 60)))
            np.save(CACHE / f"{nm}_o.npy", np.array(o, np.float32))
            if elbow:
                np.save(CACHE / f"{nm}_elbow.npy", np.array(elbow, np.float32))
        m, pv = F.miku_forearm(hgt)
        save(name + "_forearm", m)
        np.save(CACHE / f"{name}_forearm_pv.npy", np.array(pv, np.float32))
    m, o = F.miku_sitting(MIKU_SIT_H)
    save("miku_sit", m)
    save("miku_sit_glow", glow(m, 14))
    np.save(CACHE / "miku_sit_o.npy", np.array(o, np.float32))
    segs, buds = branch()
    gx0, gy0, gx1, gy1 = GLASS
    save("branch_room", branch_mask(gx1 - gx0, gy1 - gy0, segs))
    save("branch_big", branch_mask(W, H, segs))
    np.save(CACHE / "buds.npy", np.array(buds, np.float32))
    sk, lights = skyline(gx1 - gx0, gy1 - gy0)
    save("sky_room", sk)
    np.save(CACHE / "lights_room.npy", np.array(lights, np.float32))
    sk, lights = skyline(W, H)
    save("sky_big", sk)
    np.save(CACHE / "lights_big.npy", np.array(lights, np.float32))
    # light maps (world resolution)
    yy, xx = np.mgrid[0:WH, 0:WW].astype(np.float32)
    blob = lambda cx, cy, sx, sy: np.exp(-(((xx - cx) / sx) ** 2 + ((yy - cy) / sy) ** 2))
    mon = 0.95 * blob(1690, 600, 430, 300) + 0.7 * blob(1690, 792, 380, 40) + 0.22 * blob(1690, 760, 1100, 620)
    save("L_monitor", mon)
    beam = Sheet(WW, WH, ss=1)
    x0, y0, x1, y1 = GLASS
    beam.poly([(x0 + 40, FLOOR), (x1 + 20, FLOOR), (x1 + 420, WH), (x0 + 300, WH)])
    beam.poly([(x0, y1 + 50), (x1, y1 + 50), (x1 + 60, 880), (x0 + 40, 880)], fill=110)
    bm = gaussian_filter(beam.array(), 24)
    win = 0.85 * bm + 0.45 * blob((x0 + x1) / 2, (y0 + y1) / 2, 520, 470) + 0.12
    save("L_window", win)
    lamp = Sheet(WW, WH, ss=1)
    lamp.poly([(1452, 520), (1520, 515), (1660, 784), (1330, 784)])
    lm = 0.6 * gaussian_filter(lamp.array(), 20) + 0.8 * blob(1500, 785, 200, 24) + 0.25 * blob(1490, 600, 330, 260)
    save("L_lamp", lm)


class Assets:
    def __init__(self):
        self.a = {}

    def __getitem__(self, name):
        if name not in self.a:
            self.a[name] = np.load(CACHE / f"{name}.npy", mmap_mode="r")
        return self.a[name]


# ------------------------------------------------------------------------- numba kernels
@njit(cache=True, fastmath=True)
def light_room(alb, alpha, maps, cols, amb, out):
    Hh, Ww = alb.shape[0], alb.shape[1]
    n = maps.shape[0]
    for y in range(Hh):
        for x in range(Ww):
            a = alpha[y, x]
            for k in range(3):
                l = amb[k]
                for i in range(n):
                    l += maps[i, y, x] * cols[i, k]
                out[y, x, k] = alb[y, x, k] * l * a


@njit(cache=True, fastmath=True)
def blend_mask(c, mask, x0, y0, col, op):
    """Alpha-blend a flat colour through `mask` placed with its top-left at (x0, y0)."""
    Hh, Ww = c.shape[0], c.shape[1]
    mh, mw = mask.shape[0], mask.shape[1]
    for j in range(mh):
        y = y0 + j
        if y < 0 or y >= Hh:
            continue
        for i in range(mw):
            x = x0 + i
            if x < 0 or x >= Ww:
                continue
            a = mask[j, i] * op
            if a <= 0.0:
                continue
            for k in range(3):
                c[y, x, k] += (col[k] - c[y, x, k]) * a


@njit(cache=True, fastmath=True)
def max_mask(alpha, mask, x0, y0):
    Hh, Ww = alpha.shape[0], alpha.shape[1]
    for j in range(mask.shape[0]):
        y = y0 + j
        if y < 0 or y >= Hh:
            continue
        for i in range(mask.shape[1]):
            x = x0 + i
            if 0 <= x < Ww and mask[j, i] > alpha[y, x]:
                alpha[y, x] = mask[j, i]


@njit(cache=True, fastmath=True)
def add_mask(c, mask, x0, y0, col, op):
    Hh, Ww = c.shape[0], c.shape[1]
    mh, mw = mask.shape[0], mask.shape[1]
    for j in range(mh):
        y = y0 + j
        if y < 0 or y >= Hh:
            continue
        for i in range(mw):
            x = x0 + i
            if x < 0 or x >= Ww:
                continue
            a = mask[j, i] * op
            if a <= 0.0:
                continue
            for k in range(3):
                c[y, x, k] += col[k] * a


@njit(cache=True, fastmath=True)
def blend_layer(c, rgb, mask, op):
    Hh, Ww = c.shape[0], c.shape[1]
    for y in range(Hh):
        for x in range(Ww):
            a = mask[y, x] * op
            if a <= 0.0:
                continue
            for k in range(3):
                c[y, x, k] += (rgb[y, x, k] - c[y, x, k]) * a


@njit(cache=True, fastmath=True)
def resample(src, out, x0, y0, s):
    """Bilinear: out pixel (x, y) samples src at (x0 + x*s, y0 + y*s)."""
    Hh, Ww = out.shape[0], out.shape[1]
    sh, sw = src.shape[0], src.shape[1]
    for y in range(Hh):
        fy = y0 + (y + 0.5) * s - 0.5
        iy = int(math.floor(fy))
        wy = fy - iy
        if iy < 0:
            iy, wy = 0, 0.0
        if iy >= sh - 1:
            iy, wy = sh - 2, 1.0
        for x in range(Ww):
            fx = x0 + (x + 0.5) * s - 0.5
            ix = int(math.floor(fx))
            wx = fx - ix
            if ix < 0:
                ix, wx = 0, 0.0
            if ix >= sw - 1:
                ix, wx = sw - 2, 1.0
            for k in range(3):
                a = src[iy, ix, k] * (1 - wx) + src[iy, ix + 1, k] * wx
                b = src[iy + 1, ix, k] * (1 - wx) + src[iy + 1, ix + 1, k] * wx
                out[y, x, k] = a * (1 - wy) + b * wy


@njit(cache=True, fastmath=True)
def vgrad(c, x0, y0, x1, y1, top, bottom):
    for y in range(max(0, y0), min(c.shape[0], y1)):
        k = (y - y0) / max(1, (y1 - y0 - 1))
        for x in range(max(0, x0), min(c.shape[1], x1)):
            for ch in range(3):
                c[y, x, ch] = top[ch] * (1 - k) + bottom[ch] * k


@njit(cache=True, fastmath=True)
def grade(c, lift, gain, sat):
    for y in range(c.shape[0]):
        for x in range(c.shape[1]):
            l = 0.2126 * c[y, x, 0] + 0.7152 * c[y, x, 1] + 0.0722 * c[y, x, 2]
            for k in range(3):
                v = l + (c[y, x, k] - l) * sat
                c[y, x, k] = lift[k] + v * gain[k]


# ----------------------------------------------------------------------- looks / lighting
LOOKS = {   # ambient, monitor, window, lamp light colours, sky (top, bottom), sun/moon
    "dark":   dict(amb="#0b0e18", mon="#000000", win="#2c3c66", lamp="#000000", sky=("#070b1c", "#1a2546")),
    "night":  dict(amb="#121729", mon="#7fa2ff", win="#3c4f86", lamp="#000000", sky=("#070b1c", "#1d2a52")),
    "night_lamp": dict(amb="#141a2c", mon="#7fa2ff", win="#3c4f86", lamp="#ffb466", sky=("#070b1c", "#1d2a52")),
    "teal":   dict(amb="#10202a", mon="#5fe0d0", win="#3c4f86", lamp="#000000", sky=("#070b1c", "#1d2a52")),
    "dawn":   dict(amb="#3a2c40", mon="#6f8ad8", win="#ffb08a", lamp="#000000", sky=("#3b2e66", "#ffb59a")),
    "day":    dict(amb="#7a8090", mon="#000000", win="#e8eef6", lamp="#000000", sky=("#9fb3c8", "#e1e8ef")),
    "moon":   dict(amb="#0d1220", mon="#000000", win="#7f95c9", lamp="#000000", sky=("#060a18", "#1b2850")),
    "spring": dict(amb="#a4909c", mon="#86b8ff", win="#fff1e6", lamp="#000000", sky=("#a9d4f2", "#fde6ee")),
}


def look_vals(name):
    d = LOOKS[name]
    return {k: (hexc(v) if isinstance(v, str) else (hexc(v[0]), hexc(v[1]))) for k, v in d.items()}


# ----------------------------------------------------------------------------- the shots
B = 3.0          # one bar at 80 BPM


def shots():
    """(start, kind, params, transition into it)."""
    N = dict(look="night")
    return [
        (0.0, "room", dict(look="dark", monitor=0.0, producer="seated", cam=((1.0, .5, .52), (1.03, .52, .52))), "black"),
        (12.0, "room", dict(look="night", power_on=12.0, producer="seated", screen="idle",
                            cam=((1.03, .52, .52), (1.12, .62, .5))), "cut"),
        (24.0, "room", dict(look="night", producer="seated", screen="roll", clock=True,
                            cam=((1.18, .55, .4), (1.2, .58, .4))), "fade"),
        (30.0, "screen", dict(mode="first_note"), "fade"),
        (36.0, "screen", dict(mode="scope"), "cut"),
        (42.0, "room", dict(look="night_lamp", producer="seated", screen="roll", lamp_on=42.4,
                            cam=((1.2, .64, .5), (1.06, .55, .5))), "fade"),
        (48.0, "screen", dict(mode="roll_build"), "fade"),
        (54.0, "screen", dict(mode="roll_breath"), "cut"),
        (60.0, "window", dict(look="dawn", season="spring", bloom=(60.0, 64.0), petals=0.6), "flash"),
        (66.0, "screen", dict(mode="miku"), "fade"),
        (72.0, "room", dict(look="dawn", producer="stand", screen="miku", cam=((1.1, .55, .55), (1.14, .58, .55))), "fade"),
        (78.0, "room", dict(look="dawn", producer="wave", screen="miku_wave", sleep=82.6,
                            cam=((1.14, .58, .55), (1.18, .6, .55))), "cut"),
        (84.0, "window", dict(look="cycle", season="cycle", violin=True, calendar=True), "fade"),
        (96.0, "room", dict(look="day", state="busy", monitor=0.0, producer=None, phone=True,
                            cam=((1.06, .55, .52), (1.1, .6, .52))), "fade"),
        (102.0, "screen", dict(mode="desktop"), "fade"),
        (108.0, "folder", dict(mode="pulse"), "fade"),
        (114.0, "folder", dict(mode="miku"), "cut"),
        (120.0, "room", dict(look="night", state="busy", monitor=0.0, producer="ghost", timelapse=True,
                             cam=((1.08, .5, .5), (1.08, .5, .5))), "fade"),
        (126.0, "door", dict(), "fade"),
        (132.0, "window", dict(look="night", season="spring", bloom=(132.0, 133.5), petals=1.2), "flash"),
        (138.0, "screen", dict(mode="folder_open"), "cut"),
        (144.0, "room", dict(look="teal", state="busy", producer="seated", screen="miku", petals_in=1.0,
                             cam=((1.04, .5, .52), (1.1, .55, .52))), "fade"),
        (150.0, "room", dict(look="teal", state="busy", producer="seated", screen="miku", note=151.0,
                             cam=((1.2, .74, .45), (1.2, .78, .45))), "cut"),
        (156.0, "solo", dict(), "flash"),
        (180.0, "room", dict(look="moon", state="empty", monitor=0.0, producer=None, dust=True,
                             cam=((1.02, .5, .52), (1.06, .5, .52))), "fade"),
        (186.0, "room", dict(look="moon", state="empty", producer=None, flicker=187.2, screen="miku_small", dust=True,
                             cam=((1.16, .66, .48), (1.2, .7, .48))), "cut"),
        (192.0, "window", dict(look="moon", season="spring", bloom=(0.0, 0.1), petals=0.5, dusty=True), "fade"),
        (198.0, "room", dict(look="teal", state="empty", producer=None, screen="miku_small", miku_room=True, dust=True,
                             cam=((1.06, .4, .52), (1.12, .34, .52))), "fade"),
        (204.0, "window", dict(look="moon", season="spring", bloom=(0.0, 0.1), petals=0.7, mono=True), "fade"),
        (210.0, "folder", dict(mode="line", mono=True), "fade"),
        (216.0, "room", dict(look="moon", state="empty", producer=None, mono=True, dust=True,
                             cam=((1.12, .62, .55), (1.18, .66, .55))), "fade"),
        (222.0, "screen", dict(mode="miku", mono=True), "fade"),
        (228.0, "window", dict(look="spring", season="spring", bloom=(0.0, 0.1), petals=2.4), "flash"),
        (234.0, "room", dict(look="spring", producer="seated", screen="miku", miku_room=True, petals_in=1.5,
                             cam=((1.04, .45, .52), (1.08, .5, .52))), "cut"),
        (240.0, "screen", dict(mode="roll_all"), "cut"),
        (246.0, "room", dict(look="spring", producer="wave", screen="miku_wave", miku_room="wave", petals_in=1.5,
                             cam=((1.06, .5, .52), (1.1, .52, .52))), "cut"),
        (252.0, "window", dict(look="cycle_fast", season="cycle_fast", calendar=True), "cut"),
        (258.0, "room", dict(look="night", producer="seated", screen="first_note_again",
                             cam=((1.2, .62, .48), (1.0, .5, .52))), "fade"),
    ]


SEASON_ORDER = ("spring", "summer", "autumn", "winter")


def season_at(t, p, a):
    s = p.get("season", "spring")
    if s == "cycle":
        k = clamp01((t - a) / 11.0) * 4
        return SEASON_ORDER[min(3, int(k))], k % 1
    if s == "cycle_fast":
        k = clamp01((t - a) / 5.6) * 5
        return (SEASON_ORDER + ("spring",))[min(4, int(k))], k % 1
    return s, 0.0


# ----------------------------------------------------------------------------- renderer
class Story:
    def __init__(self, audio_s):
        self.audio_s = audio_s
        self.s = PL.Song()
        self.A = Assets()
        self.shots = shots()
        self.starts = [x[0] for x in self.shots]
        self.world = np.zeros((WH, WW, 3), np.float32)
        self.alb = np.zeros((WH, WW, 3), np.float32)
        self.alpha = np.zeros((WH, WW), np.float32)
        self.out = np.zeros((H, W, 3), np.uint8)
        rng = np.random.default_rng(7)
        self.grain = np.ascontiguousarray(rng.normal(0, 40, (H // 2, W // 2)).clip(-127, 127).astype(np.int8))
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        vig = 1 - 0.38 * np.clip(np.hypot((xx / W - 0.5) * 1.2, (yy / H - 0.5) * 1.35) - 0.22, 0, 1) ** 1.5
        band = 1 - 0.42 * np.clip((yy - (H - 300)) / 300, 0, 1) ** 1.4          # darker under the subtitles
        self.vig = np.ascontiguousarray(vig * band, dtype=np.float32)
        self.maps = np.ascontiguousarray(np.stack([self.A["L_monitor"], self.A["L_window"], self.A["L_lamp"]]))
        v, sr = soundfile.read(str(VOCAL), always_2d=True)
        v = v.mean(axis=1)
        self.vsr = 11025
        self.voice = v[::4].astype(np.float32)                          # 44.1k -> 11k is plenty for drawing
        hop = sr // 60
        cs = np.concatenate([[0.0], np.cumsum(v.astype(np.float64) ** 2)])
        n = (len(v) - hop) // hop
        idx = np.arange(n) * hop
        env = np.sqrt((cs[idx + hop] - cs[idx]) / hop)
        self.env = (env / (np.percentile(env, 99) + 1e-9)).clip(0, 1.5).astype(np.float32)
        self.beams = {}
        self.lines = []
        for ln in self.s.lines:
            times = lyric_align.char_times(ln["jp"], ln["syls"], ln["onsets"])
            self.lines.append(dict(ln=ln, times=times))
        for i, L in enumerate(self.lines):
            nxt = self.lines[i + 1]["times"][0] if i + 1 < len(self.lines) else 1e9
            L["out"] = min(L["ln"]["end"] + 1.4, nxt - 0.45)            # gone before the next line begins
        self.lines[-1]["out"] = 1e9
        self.buds = np.array(self.A["buds"])
        rnd = random.Random(3)
        self.petal_seeds = [(rnd.random(), rnd.random(), rnd.uniform(0.6, 1.4), rnd.random() * 6.28) for _ in range(160)]
        self.dust = [(rnd.random(), rnd.random(), rnd.uniform(0.5, 1.6), rnd.random() * 6.28) for _ in range(90)]
        self.notes = [n for n in self.s.vocal]                          # (start, end, pitch, syllable)
        self.shadow = {}

    # --- helpers
    def envelope(self, t):
        i = int(t * 60)
        return float(self.env[i]) if 0 <= i < len(self.env) else 0.0

    def shot_at(self, t):
        i = max(0, int(np.searchsorted(self.starts, t, side="right")) - 1)
        return i

    def section(self, t):
        return self.s.section(t)[0]

    # --- the window view (used in the room and full frame)
    def outside(self, cv, x0, y0, w, h, t, p, big, a):
        lk = p.get("look", "night")
        season, sk = season_at(t, p, a)
        mono = p.get("mono", False)
        if lk in ("cycle", "cycle_fast"):
            ph = (t - a) / (2.4 if lk == "cycle" else 1.1)
            day = 0.5 + 0.5 * math.sin(ph * 2 * math.pi)
            n, d = look_vals("night"), look_vals("day")
            top = n["sky"][0] * (1 - day) + d["sky"][0] * day
            bot = n["sky"][1] * (1 - day) + d["sky"][1] * day
        else:
            top, bot = look_vals(lk)["sky"]
            day = 1.0 if lk in ("day", "spring") else 0.35 if lk == "dawn" else 0.0
        if mono:
            g = lambda c: np.full(3, 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2], np.float32)
            top, bot = g(top), g(bot)
        vgrad(cv.c, int(x0), int(y0), int(x0 + w), int(y0 + h), top.astype(np.float32), bot.astype(np.float32))
        if day < 0.5:                                                      # moon
            mx, my = x0 + w * 0.72, y0 + h * 0.2
            cv.circle(mx, my, h * 0.055, hexc("#f4f1e4"), 0.95 * (1 - day * 2), glow=h * 0.02)
        sky = self.A["sky_big" if big else "sky_room"]
        bcol = (top * 0.35 + bot * 0.25).astype(np.float32) * (0.6 + 0.4 * day)
        blend_mask(cv.c, sky, int(x0), int(y0), bcol, 1.0)
        if day < 0.6:
            lights = self.A["lights_big" if big else "lights_room"]
            for lx, ly, ph in lights:
                tw = 0.6 + 0.4 * math.sin(t * 0.7 + ph)
                cv.circle(x0 + lx, y0 + ly, 1.6 if big else 0.9, hexc("#ffd59a"), 0.7 * tw * (1 - day))
        # the branch, then its blossoms / leaves / snow
        bm = self.A["branch_big" if big else "branch_room"]
        wood = hexc("#1b1418") if day < 0.5 else hexc("#3a2a2c")
        blend_mask(cv.c, bm, int(x0), int(y0), wood, 1.0)
        bloom = 1.0
        if "bloom" in p:
            b0, b1 = p["bloom"]
            bloom = ease(ramp(t, b0, b1)) if b1 > 1 else 1.0
        col = {"spring": SAKURA, "summer": hexc("#4f8f5a"), "autumn": hexc("#d9733f"), "winter": hexc("#f2f4f8")}[season]
        if mono:
            col = np.full(3, 0.85, np.float32)
        scale = (h / 1080.0) if big else (h / 580.0) * 0.55
        for i, (bx, by, bs) in enumerate(self.buds):
            if season == "winter" and i % 3:
                continue
            pop = clamp01(bloom * 1.25 - (i % 17) / 17 * 0.25)
            if pop <= 0:
                continue
            r = (9 + 7 * bs) * scale * (0.4 + 0.6 * pop)
            cx, cy = x0 + bx * w, y0 + by * h
            sway = math.sin(t * 0.9 + i) * 1.5 * scale
            shade = col * (0.82 + 0.18 * ((i * 7) % 5) / 4)
            if season == "spring" and big:
                for k in range(5):
                    ang = k * 1.2566 + i
                    cv.petal(cx + sway + math.cos(ang) * r * 0.55, cy + math.sin(ang) * r * 0.55, r * 0.9, ang + 1.57,
                             shade, 0.95)
                cv.circle(cx + sway, cy, r * 0.22, hexc("#d9587f") if not mono else np.full(3, .5, np.float32), 0.9)
            else:
                cv.circle(cx + sway, cy, r, shade, 0.9)
                cv.circle(cx + sway + r * 0.5, cy - r * 0.3, r * 0.7, shade * 1.06, 0.8)
        # weather
        n = int(len(self.petal_seeds) * min(1.0, p.get("petals", 0.0) if season == "spring" else 0.6 if season != "summer" else 0))
        pcol = {"spring": SAKURA, "autumn": hexc("#d9733f"), "winter": hexc("#ffffff"), "summer": SAKURA}[season]
        if mono:
            pcol = np.full(3, 0.88, np.float32)
        for i in range(n):
            u, v, sp, ph = self.petal_seeds[i]
            fall = (v + (t * 0.05 * sp)) % 1.0
            px = x0 + ((u + 0.15 * math.sin(t * 0.5 * sp + ph) + fall * 0.25) % 1.0) * w
            py = y0 + fall * h
            if season == "winter":
                cv.circle(px, py, 2.4 * sp * scale * 2, pcol, 0.85)
            else:
                cv.petal(px, py, 9 * sp * scale * 1.8, t * 1.3 * sp + ph, pcol, 0.9)

    # --- the screen UI: drawn at any scale into (x0, y0, w, h)
    def ui(self, cv, x0, y0, w, h, t, mode, a, mono=False, small=False):
        s = w / 1920.0
        bg = hexc("#0d1222")
        vgrad(cv.c, int(x0), int(y0), int(x0 + w), int(y0 + h), hexc("#10172b"), hexc("#0a0e1a"))
        if mode in ("desktop",):
            return self.desktop(cv, x0, y0, w, h, t, a, small)
        if mode == "off":
            return
        teal = TEAL if not mono else np.full(3, 0.75, np.float32)
        if mode in ("miku", "miku_wave", "miku_small", "folder_open"):
            self.ui_stage(cv, x0, y0, w, h, t, mode, a, mono, small)
            return
        # title bar
        cv.rect(x0 + w / 2, y0 + 26 * s, w, 52 * s, hexc("#161e36"))
        if not small:
            TYPE.text(cv, GOTHIC, max(8, int(22 * s)), "まだね.vpr  —  Track 1  Miku", x0 + 26 * s, y0 + 8 * s, hexc("#8b97b8"), 0.9)
        # piano roll window
        top, bottom = y0 + 70 * s, y0 + h - (220 * s if mode != "scope" else 60 * s)
        left = x0 + 120 * s
        if mode == "scope":
            self.scope(cv, x0, y0 + 60 * s, w, h - 60 * s, t, teal, small)
            return
        lo, hi = 60, 82
        rows = hi - lo
        rh = (bottom - top) / rows
        for k in range(rows):
            p = hi - 1 - k
            black = (p % 12) in (1, 3, 6, 8, 10)
            cv.rect(left + (x0 + w - left) / 2, top + (k + 0.5) * rh, x0 + w - left, rh - 1, hexc("#151c33") if black else hexc("#1a2340"))
            cv.rect(x0 + 60 * s, top + (k + 0.5) * rh, 120 * s, rh - 1, hexc("#2a2f40") if black else hexc("#d8dbe6"))
        span = {"roll_all": 270.0, "first_note": 8.0, "first_note_again": 8.0}.get(mode, 9.0)
        if mode in ("roll", "roll_build", "roll_breath", "idle", "first_note_again"):
            view0 = t - span * 0.35
        elif mode == "first_note":
            view0 = a - 0.2
        else:
            view0 = 0.0
        px = lambda tt: left + (tt - view0) / span * (x0 + w - left)
        bar0 = math.floor(view0 / B) * B
        step = 8 if mode == "roll_all" else 1
        for k in range(0, int(span / B) + 2, step):
            bx = px(bar0 + k * B)
            if left <= bx <= x0 + w:
                cv.line(bx, top, bx, bottom, max(1.0, 1.4 * s), hexc("#2c3757"), 0.9)
        # notes
        for (n0, n1, pitch, syl) in self.notes:
            if n1 < view0 or n0 > view0 + span:
                continue
            if mode == "first_note":
                if not (n0 <= a + 3.2 and n0 >= self.s.first_a - 0.01):
                    continue
                if n0 > self.s.first_a + 0.01:
                    continue
            show = 1.0
            if mode == "roll_build":
                show = ease_out((t - n0 + 0.25) / 0.25)
                if show <= 0:
                    continue
            if mode == "first_note":
                show = ease_out((t - (a + 1.2)) / 0.4)
            yy = top + (hi - 0.5 - min(hi - 1, max(lo, pitch))) * rh
            xa, xb = px(n0), px(n1)
            if mode == "first_note":
                xb = xa + (xb - xa) * ease_out((t - (a + 1.2)) / 1.2)
            playing = n0 <= t < n1
            col = teal * (1.0 if playing else 0.55 if mode != "roll_all" else 0.85)
            cv.rect((xa + xb) / 2, yy, max(2.0, xb - xa - 2 * s), rh * 0.86, col, show * 0.95)
            if playing:
                cv.rect((xa + xb) / 2, yy, max(2.0, xb - xa - 2 * s), rh * 0.86, TEAL_HI, 0.25 * show)
            if not small and rh > 14 and mode != "roll_all":
                fs = max(10, int(rh * 0.62))
                TYPE.text(cv, GOTHIC, fs, syl if syl != "ー" else "-", xa + 6 * s, yy - fs * 0.62, hexc("#0b1020"), 0.9 * show)
        if mode == "roll_breath":                                    # breath marks in the rests
            for (n0, n1, pitch, syl), nxt in zip(self.notes[:-1], self.notes[1:]):
                if nxt[0] - n1 > 0.3 and view0 <= n1 <= view0 + span:
                    k = ease_out((t - n1) / 0.35)
                    if k > 0:
                        bx = px((n1 + nxt[0]) / 2)
                        by = top + 30 * s
                        TYPE.text(cv, MINCHO, max(10, int(64 * s)), "V", bx - 16 * s, by, hexc("#f2a7c3"), 0.9 * k)
        if mode not in ("roll_all",):
            phx = px(t)
            cv.line(phx, top, phx, bottom, max(1.0, 2.4 * s), hexc("#f2a7c3"), 0.9, glow=2 * s)
        if mode == "first_note_again" and t > self.notes[-1][1] + 0.6:   # after the last word, a new first note
            k = ease_out((t - self.notes[-1][1] - 0.6) / 1.5)
            yy = top + (hi - 0.5 - 71) * rh
            xa = px(t) + 30 * s
            cv.rect(xa + 60 * s * k, yy, max(2.0, 120 * s * k), rh * 0.86, teal, 0.95)
            if not small:
                TYPE.text(cv, GOTHIC, max(10, int(rh * 0.62)), "あ", xa + 6 * s, yy - rh * 0.4, hexc("#0b1020"), k)
        if mode == "first_note":                                    # the cursor drawing the first note
            k = ramp(t, a + 0.3, a + 1.2)
            n0 = self.s.first_a
            cx = px(n0) + 10 * s
            pitch = next(p for (s0, s1, p, _) in self.notes if abs(s0 - n0) < 0.01)
            cy = top + (hi - 0.5 - pitch) * rh
            if t < a + 2.6:
                ax, ay = cx + (1 - ease(k)) * 300 * s, cy + (1 - ease(k)) * 180 * s
                cv.line(ax, ay, ax + 18 * s, ay + 26 * s, 3 * s, INK, 0.9)
                cv.line(ax, ay, ax, ay + 32 * s, 3 * s, INK, 0.9)
        # the waveform lane
        lane_top = bottom + 30 * s
        lane_h = y0 + h - lane_top - 20 * s
        cv.rect(x0 + w / 2, lane_top + lane_h / 2, w - 40 * s, lane_h, hexc("#0e1426"))
        n = 160
        pts_u, pts_d = [], []
        for i in range(n):
            tt = t - 4.0 + 4.0 * i / (n - 1)
            e = self.envelope(tt) if tt <= t else 0.0
            xx = x0 + 30 * s + (w - 60 * s) * i / (n - 1)
            pts_u.append((xx, lane_top + lane_h / 2 - e * lane_h * 0.42))
            pts_d.append((xx, lane_top + lane_h / 2 + e * lane_h * 0.42))
        cv.polyline(pts_u, max(1.0, 2.0 * s), teal, 0.9)
        cv.polyline(pts_d, max(1.0, 2.0 * s), teal, 0.6)

    def scope(self, cv, x0, y0, w, h, t, teal, small):
        """Her voice as it is: 30 ms of the waveform, big."""
        i = int(t * self.vsr)
        seg = self.voice[max(0, i - 100):i + 100]
        if len(seg) < 10:
            return
        for k in range(1, 8):                                       # graticule
            cv.line(x0 + w * k / 8, y0, x0 + w * k / 8, y0 + h, 1.0, hexc("#1c2642"), 0.9)
        for k in range(1, 6):
            cv.line(x0, y0 + h * k / 6, x0 + w, y0 + h * k / 6, 1.0, hexc("#1c2642"), 0.9)
        amp = 1.25
        pts = [(x0 + w * k / (len(seg) - 1), y0 + h / 2 - float(seg[k]) * amp * h * 0.5) for k in range(len(seg))]
        cv.polyline(pts, max(1.5, 4 * w / 1920), teal, 0.95, glow=6 * w / 1920)

    def ui_stage(self, cv, x0, y0, w, h, t, mode, a, mono, small):
        """Miku on the screen, singing."""
        s = w / 1920.0
        e = self.envelope(t)
        teal = TEAL if not mono else np.full(3, 0.78, np.float32)
        cx = x0 + w * (0.62 if mode != "miku_small" else 0.5)
        for k in range(7):                                     # light behind her
            ang = -1.57 + (k - 3) * 0.22 + 0.05 * math.sin(t * 0.4 + k)
            cv.line(cx, y0 + h * 0.98, cx + math.cos(ang) * h * 1.2, y0 + h * 0.98 + math.sin(ang) * h * 1.2,
                    40 * s, teal, 0.05 + 0.04 * e)
        if mode == "folder_open":
            k = ease(ramp(t, a, a + 2.5))
            fw, fh = w * (0.18 + 0.82 * k), h * (0.16 + 0.84 * k)
            cv.rect(x0 + w / 2, y0 + h / 2, fw, fh, hexc("#1a2340"), 0.9)
            if k < 0.98:
                return
        name = ("miku_small" if small else "miku_screen") + ("_wave" if mode == "miku_wave" else "")
        m, g, o = self.A[name], self.A[name + "_glow"], self.A[name + "_o"]
        base = MIKU_SMALL_H if small else MIKU_SCREEN_H
        zk = (h * 0.82) / base
        if abs(zk - 1) > 0.004:                               # the screen shot pushes in a little
            m, g, o = resize_mask(m, zk), resize_mask(g, zk), o * zk
        bob = math.sin(t * 2 * math.pi / 3.0) * h * 0.006
        mx, my = int(cx - o[0]), int(y0 + h * 0.96 - o[1] + bob)
        add_mask(cv.c, g, mx, my, teal * 0.55, 0.6 + 0.5 * e)
        blend_mask(cv.c, m, mx, my, teal * (0.85 + 0.15 * e), 1.0)
        if mode == "miku_wave":
            base_name = name.replace("_wave", "")
            el = self.A[name + "_elbow"] * zk
            fa, pv = self.A[base_name + "_forearm"], self.A[base_name + "_forearm_pv"]
            if abs(zk - 1) > 0.004:
                fa, pv = resize_mask(fa, zk), pv * zk
            arm = rotate_mask(fa, math.sin((t - a) * 2 * math.pi / 0.75) * 0.35, pv)
            blend_mask(cv.c, arm, int(mx + el[0] - pv[0]), int(my + el[1] - pv[1]), (TEAL_HI if not mono else INK) * 0.95, 1.0)

    def desktop(self, cv, x0, y0, w, h, t, a, small):
        s = w / 1920.0
        vgrad(cv.c, int(x0), int(y0), int(x0 + w), int(y0 + h), hexc("#2b3a5c"), hexc("#1a2238"))
        names = ["会議資料_最終版(2).pptx", "月次報告_10月.xlsx", "未読メール  128", "来週の予定", "見積書_修正.pdf", "メモ"]
        rng = random.Random(2)
        for i, nm in enumerate(names):
            wx = x0 + (180 + i * 150 + rng.randint(-40, 40)) * s
            wy = y0 + (120 + i * 90 + rng.randint(-20, 20)) * s
            ww_, hh_ = 860 * s, 520 * s
            cv.rect(wx + ww_ / 2 + 8 * s, wy + hh_ / 2 + 10 * s, ww_, hh_, BLACK, 0.35)
            cv.rect(wx + ww_ / 2, wy + hh_ / 2, ww_, hh_, hexc("#e9ecf2"))
            cv.rect(wx + ww_ / 2, wy + 22 * s, ww_, 44 * s, hexc("#c9cfdb"))
            if not small:
                TYPE.text(cv, GOTHIC, max(8, int(22 * s)), nm, wx + 18 * s, wy + 6 * s, hexc("#2a3042"), 0.9)
            for k in range(7):
                cv.rect(wx + 40 * s + (ww_ - 80 * s) * (0.35 + 0.3 * ((k * 37 + i) % 5) / 4) / 2, wy + (90 + k * 52) * s,
                        (ww_ - 80 * s) * (0.35 + 0.3 * ((k * 37 + i) % 5) / 4), 12 * s, hexc("#b9c0cf"))
        # the folder, small, in the corner nobody looks at
        fx, fy = x0 + w - 230 * s, y0 + h - 300 * s
        k = 0.5 + 0.5 * math.sin(t * 1.4)
        cv.rect(fx, fy, 120 * s, 86 * s, hexc("#d8b86a"))
        cv.rect(fx - 30 * s, fy - 50 * s, 60 * s, 18 * s, hexc("#d8b86a"))
        cv.rect(fx, fy + 6 * s, 120 * s, 74 * s, hexc("#e7c97c"))
        cv.circle(fx, fy + 4 * s, 18 * s, TEAL, 0.25 + 0.25 * k, glow=12 * s)
        if not small:
            TYPE.text(cv, GOTHIC, max(8, int(26 * s)), "まだね", fx, fy + 56 * s, INK, 0.95, align="center")
        # dust over everything
        for i, (u, v, sp, ph) in enumerate(self.dust[:40]):
            cv.circle(x0 + u * w, y0 + ((v + t * 0.01 * sp) % 1) * h, 1.6 * sp * max(0.5, s * 2), INK, 0.25)

    # --- shots -------------------------------------------------------------------------------
    def shot_room(self, t, p, a, b):
        A = self.A
        state = p.get("state", "tidy")
        lk = look_vals(p.get("look", "night"))
        mono = p.get("mono", False)
        alb, alpha = self.alb, self.alpha
        alb[:] = A[f"room_{state}"]
        alpha[:] = A[f"room_{state}_a"]
        # figures go into the albedo so the lights fall on them (and they hide the screen and window
        # behind them); the chair goes over a seated one
        prod = p.get("producer")
        if prod == "ghost":
            ph = (t - a) * 1.7
            prod = "seated" if (math.sin(ph * 2.3) + math.sin(ph * 3.7)) > 0.6 else None
        fig = {"seated": "p_seated", "stand": "p_stand", "wave": "p_wave"}.get(prod)
        if fig:
            m, (fx, fy) = A[fig], A[fig + "_xy"]
            blend_mask(alb, m, int(fx), int(fy), hexc("#0c0d13"), 1.0)
            max_mask(alpha, m, int(fx), int(fy))
        arm = None
        if prod == "wave":                                         # the forearm swings from the elbow
            pv = A["p_forearm_pv"]
            arm = rotate_mask(A["p_forearm"], math.sin((t - a) * 2 * math.pi / 0.75) * 0.32, pv)
            ex, ey = A["p_elbow"]
            ax, ay = int(ex - pv[0]), int(ey - pv[1])
            blend_mask(alb, arm, ax, ay, hexc("#0c0d13"), 1.0)
            max_mask(alpha, arm, ax, ay)
        blend_layer(alb, A[f"chair_{state}"], A[f"chair_{state}_a"], 1.0)
        max_mask(alpha, A[f"chair_{state}_a"], 0, 0)
        # lights
        mon = 1.0 if p.get("screen") else 0.0
        if "monitor" in p:
            mon = p["monitor"]
        if "power_on" in p:
            mon = ramp(t, p["power_on"], p["power_on"] + 0.25) * (0.75 + 0.25 * ramp(t, p["power_on"] + 0.25, p["power_on"] + 2))
        if "sleep" in p:
            mon *= 1 - ramp(t, p["sleep"], p["sleep"] + 0.8)
        if "flicker" in p:
            f0 = p["flicker"]
            fl = 1.0 if t > f0 + 1.0 else (1.0 if (t > f0 and int((t - f0) * 14) % 3 != 1) else 0.0)
            mon = fl * (0.9 + 0.1 * math.sin(t * 40))
        e = self.envelope(t)
        mcol = lk["mon"]
        if p.get("screen", "").startswith("miku"):
            mcol = mcol * 0.4 + TEAL * 0.9 * (0.8 + 0.4 * e)
        lamp = 0.0
        if "lamp_on" in p:
            lamp = ramp(t, p["lamp_on"], p["lamp_on"] + 0.15)
        cols = np.ascontiguousarray(np.stack([mcol * mon * 1.25, lk["win"] * 1.0, lk["lamp"] * lamp]), dtype=np.float32)
        amb = lk["amb"].astype(np.float32) * 1.6
        if p.get("timelapse"):
            day = 0.5 + 0.5 * math.sin((t - a) * 2 * math.pi / 1.3)
            amb = (amb * (1 - day) + look_vals("day")["amb"] * day).astype(np.float32)
            cols[1] = (lk["win"] * (1 - day) + look_vals("day")["win"] * day)
        light_room(alb, alpha, self.maps, cols, amb, self.world)
        world = self.world
        cvw = Canvas(world)
        # what shows through: the window and the screen
        gx0, gy0, gx1, gy1 = GLASS
        tmp = np.zeros((gy1 - gy0, gx1 - gx0, 3), np.float32)
        self.outside(Canvas(tmp), 0, 0, gx1 - gx0, gy1 - gy0, t, dict(p, petals=p.get("petals_in", 0.4)), False, a)
        hole = 1.0 - alpha[gy0:gy1, gx0:gx1, None]
        world[gy0:gy1, gx0:gx1] += tmp * hole
        sx0, sy0, sx1, sy1 = SCREEN
        if mon > 0.01:
            scr = np.zeros((sy1 - sy0, sx1 - sx0, 3), np.float32)
            self.ui(Canvas(scr), 0, 0, sx1 - sx0, sy1 - sy0, t, p.get("screen", "idle"), a, mono, small=True)
            world[sy0:sy1, sx0:sx1] += scr * mon * (1.0 - alpha[sy0:sy1, sx0:sx1, None])
        # rim light on the producer from the screen
        if fig and mon > 0.01:
            fx, fy = A[fig + "_xy"]
            add_mask(world, A[fig + "_rim"], int(fx), int(fy), mcol * mon * 0.55, 1.0)
            if arm is not None:
                rim = np.ascontiguousarray(np.clip(arm - gaussian_filter(arm, 5), 0, 1) * 2.2, dtype=np.float32)
                add_mask(world, rim, ax, ay, mcol * mon * 0.55, 1.0)
        # small lit things: clock hands, calendar, a sticky note, the lamp bulb
        cx, cy, r = CLOCK
        lev = float(self.maps[0, cy, cx] * cols[0].mean() + self.maps[1, cy, cx] * cols[1].mean() + amb.mean())
        hand = hexc("#1a1c26") * min(1.0, 0.3 + lev)
        clock_t = 2.0 + (t - a) / 3600 * 60
        if p.get("timelapse"):
            clock_t = 2.0 + (t - a) * 2.0
        hr = clock_t / 12 * 2 * math.pi
        mn = (clock_t % 1.0) * 2 * math.pi
        cvw.line(cx, cy, cx + math.sin(hr) * r * 0.5, cy - math.cos(hr) * r * 0.5, 7, hand, 1.0)
        cvw.line(cx, cy, cx + math.sin(mn) * r * 0.8, cy - math.cos(mn) * r * 0.8, 4, hand, 1.0)
        x0, y0, x1, y1 = CALENDAR
        month = {"tidy": "4", "busy": "11", "empty": "4"}[state]
        TYPE.text(cvw, LATIN, 80, month, (x0 + x1) / 2, y0 + 52, hexc("#2a2c38") * min(1.0, 0.25 + lev), 0.9, align="center")
        if lamp > 0:
            cvw.circle(1488, 528, 16, hexc("#ffe2b0"), lamp, glow=16)
        if "note" in p:
            k = ease_out((t - p["note"]) / 0.5)
            if k > 0:
                cvw.rect(1890, 520 + (1 - k) * 30, 92, 92, hexc("#f6e27a") * 0.8, k, angle=0.06)
                TYPE.text(cvw, MINCHO, 26, "来年も", 1890, 500 + (1 - k) * 30, hexc("#3a3020"), k, align="center")
        if p.get("phone"):
            buzz = 1.0 if int(t * 2.2) % 4 == 0 else 0.0
            cvw.rect(1450 + buzz * math.sin(t * 90) * 3, 772, 70, 12, hexc("#101218"), 1.0)
            if buzz:
                cvw.rect(1450, 765, 66, 4, hexc("#9ad1ff"), 0.9)
        # Miku in the room, singing to nobody
        if p.get("miku_room"):
            wave = p["miku_room"] == "wave"
            nm = "miku_room_wave" if wave else "miku_room"
            m, g, o = A[nm], A[nm + "_glow"], A[nm + "_o"]
            k = ease(ramp(t, a + 0.5, a + 3.0))
            mx, my = int(MIKU_ROOM_X - o[0]), int(FLOOR + 6 - o[1])
            col = TEAL if not mono else np.full(3, 0.8, np.float32)
            add_mask(world, g, mx, my, col * 0.5, k * (0.6 + 0.4 * e))
            add_mask(world, m, mx, my, col * 0.75, k * 0.85)
            if wave:
                el, pv = A[nm + "_elbow"], A["miku_room_forearm_pv"]
                arm = rotate_mask(A["miku_room_forearm"], math.sin((t - a) * 2 * math.pi / 0.75) * 0.35, pv)
                add_mask(world, arm, int(mx + el[0] - pv[0]), int(my + el[1] - pv[1]), TEAL_HI * 0.8, k * 0.9)
        # petals blowing in, dust in the light
        if p.get("petals_in"):
            n = int(60 * p["petals_in"])
            for i in range(n):
                u, v, sp, ph = self.petal_seeds[i]
                q = ((t - a) * 0.06 * sp + v) % 1.0
                px = gx1 - 40 + q * 1500 + math.sin(t * sp + ph) * 60
                py = gy0 + 200 + q * 600 + math.sin(t * 0.7 * sp + ph * 2) * 120
                cvw.petal(px, py, 13 * sp, t * 1.5 * sp + ph, SAKURA if not mono else np.full(3, .85, np.float32), 0.9)
        if p.get("dust"):
            for u, v, sp, ph in self.dust:
                dx = 300 + u * 1100
                dy = 300 + ((v - (t - a) * 0.008 * sp) % 1) * 700
                lit = self.maps[1, int(dy), int(dx)]
                cvw.circle(dx + math.sin(t * 0.3 * sp + ph) * 20, dy, 1.6 * sp, INK, 0.5 * float(lit))
        if mono:
            grade(world, np.zeros(3, np.float32), np.ones(3, np.float32), 0.0)
            if p.get("screen") or p.get("miku_room"):
                pass
        # camera
        (z0, cx0, cy0), (z1, cx1, cy1) = p.get("cam", ((1.0, .5, .5), (1.0, .5, .5)))
        k = ease((t - a) / max(0.1, b - a))
        z = z0 + (z1 - z0) * k
        ccx, ccy = cx0 + (cx1 - cx0) * k, cy0 + (cy1 - cy0) * k
        cw = WW / z                                         # crop width in world px (z=1: the whole room)
        sc = cw / W
        chh = H * sc
        x0 = min(max(0.0, ccx * WW - cw / 2), WW - cw)
        y0 = min(max(0.0, ccy * WH - chh / 2), WH - chh)
        out = np.empty((H, W, 3), np.float32)
        resample(world, out, x0, y0, sc)
        return out

    def shot_window(self, t, p, a, b):
        c = np.zeros((H, W, 3), np.float32)
        cv = Canvas(c)
        self.outside(cv, 0, 0, W, H, t, p, True, a)
        # the window frame at the edges
        fr = hexc("#1a1e2c") if p.get("look") not in ("spring", "day") else hexc("#cfcbd6")
        cv.rect(W / 2, 18, W, 36, fr)
        cv.rect(W / 2, H - 18, W, 36, fr)
        cv.rect(30, H / 2, 60, H, fr)
        cv.rect(W - 30, H / 2, 60, H, fr)
        cv.rect(W * 0.5, H / 2, 22, H, fr)
        if p.get("dusty"):
            for u, v, sp, ph in self.dust:
                cv.circle(u * W, v * H, 6 * sp, hexc("#c9c3b8"), 0.06)
            c *= 0.85
            c += 0.06
        if p.get("calendar"):
            season, sk = season_at(t, p, a)
            span = 11.0 if p.get("season") == "cycle" else 5.6
            m = 4 + int(clamp01((t - a) / span) * 12)
            mm = (m - 1) % 12 + 1
            TYPE.text(cv, LATIN, 150, f"{mm}", W - 140, 70, INK, 0.9, align="right")
            TYPE.text(cv, LATIN, 30, "MONTH", W - 140, 236, INK, 0.6, align="right")
        if p.get("violin"):
            self.violin_line(cv, t)
        return c

    def violin_line(self, cv, t):
        pts = []
        for (s0, s1, pitch) in self.s.violin:
            if s1 < t - 6 or s0 > t:
                continue
            for k in range(6):
                tt = s0 + (min(s1, t) - s0) * k / 5
                if tt > t:
                    break
                x = W * 0.78 - (t - tt) * 240
                y = H * 0.62 - (pitch - 74) * 16 + math.sin(tt * 9) * 4
                pts.append((x, y))
        if len(pts) > 1:
            cv.polyline(pts, 4, INK, 0.85, glow=8, fade_tail=True)

    def shot_screen(self, t, p, a, b):
        c = np.zeros((H, W, 3), np.float32)
        cv = Canvas(c)
        mode = p["mode"]
        z = 1.0 + 0.03 * ease((t - a) / max(0.1, b - a))
        self.ui(cv, -(z - 1) * W / 2, -(z - 1) * H / 2, W * z, H * z, t, mode, a, p.get("mono", False))
        # the first sound: a ripple of light when she sings it
        if mode == "first_note":
            age = t - self.s.first_a
            if 0 <= age < 2.5:
                cv.ring(W * 0.42, H * 0.45, 40 + age * 700, 6 * (1 - age / 2.5), TEAL, 0.8 * (1 - age / 2.5), glow=10)
                c += (TEAL * 0.12 * max(0.0, 1 - age / 0.8))[None, None, :]
        if mode == "scope":
            pass
        # the bezel edge and a soft reflection
        cv.rect(W / 2, H / 2, W - 6, H - 6, hexc("#05060a"), 1.0, stroke=10)
        if p.get("mono"):
            grade(c, np.zeros(3, np.float32), np.ones(3, np.float32), 0.0)
            if mode == "miku":
                self.ui_stage(Canvas(c), -(z - 1) * W / 2, -(z - 1) * H / 2, W * z, H * z, t, "miku", a, False, False)
        return c

    def shot_folder(self, t, p, a, b):
        c = np.zeros((H, W, 3), np.float32)
        cv = Canvas(c)
        mono = p.get("mono", False)
        vgrad(c, 0, 0, W, H, hexc("#0a0f1e"), hexc("#141b30") if not mono else hexc("#141414"))
        teal = TEAL if not mono else np.full(3, 0.8, np.float32)
        e = self.envelope(t)
        rng = random.Random(8)
        for i in range(40):                                       # her old notes floating in the dark
            u, v = rng.random(), rng.random()
            x = (u * W + (t - a) * 6 * (0.5 + rng.random())) % (W + 200) - 100
            y = v * H + math.sin(t * 0.3 + i) * 12
            cv.rect(x, y, rng.uniform(40, 160), 14, teal * 0.6, 0.18)
        if p["mode"] == "pulse":
            n = 240
            pts = []
            for i in range(n):
                tt = t - 6.0 + 6.0 * i / (n - 1)
                pts.append((W * i / (n - 1), H * 0.5 - self.envelope(tt) * 120 * math.sin(i * 0.9)))
            cv.polyline(pts, 3, teal, 0.9, glow=8)
        if p["mode"] == "line":                                   # the melody she is singing, drawn as it goes
            pts = []
            for (n0, n1, pitch, syl) in self.notes:
                if n1 < t - 7.0 or n0 > t:
                    continue
                for q in range(6):
                    tt = n0 + (min(n1, t) - n0) * q / 5
                    pts.append((W * 0.82 - (t - tt) * 230, H * 0.52 - (pitch - 69) * 26))
            if len(pts) > 1:
                cv.polyline(pts, 4, teal, 0.95, glow=10, fade_tail=True)
                cv.circle(pts[-1][0], pts[-1][1], 8, INK, 0.9, glow=12)
        if p["mode"] in ("miku", "pulse"):
            k = 1.0 if p["mode"] == "miku" else 0.25 + 0.25 * e
            m, g, o = self.A["miku_sit"], self.A["miku_sit_glow"], self.A["miku_sit_o"]
            mx, my = int(W * 0.47 - o[0]), int(H * 0.8 - o[1])
            add_mask(c, g, mx, my, teal * 0.45, k * (0.5 + 0.6 * e))
            blend_mask(c, m, mx, my, teal * 0.8, k)
            cv.ring(W * 0.5, H * 0.66, 260 + 40 * e, 2, teal, 0.3 * k, glow=6)
        return c

    def shot_door(self, t, p, a, b):
        c = np.zeros((H, W, 3), np.float32)
        cv = Canvas(c)
        vgrad(c, 0, 0, W, H, hexc("#0b0e18"), hexc("#10131f"))
        k = ease(ramp(t, a, a + 4.0))
        rise = ramp(t, b - 3.0, b)
        dx0, dx1, dy0, dy1 = W * 0.42, W * 0.58, H * 0.12, H * 0.9
        warm = hexc("#ffcf96")
        glowc = warm * (0.55 + 0.45 * rise)
        open_w = (dx1 - dx0) * (0.15 + 0.85 * k)
        cv.rect(dx0 + open_w / 2, (dy0 + dy1) / 2, open_w, dy1 - dy0, glowc, 1.0)
        cv.rect((dx0 + dx1) / 2, (dy0 + dy1) / 2, dx1 - dx0 + 30, dy1 - dy0 + 30, hexc("#1c2030"), 1.0, stroke=15)
        key = int(k * 24)
        if key not in self.beams:                              # the light on the floor, for 25 door angles
            ow = (dx1 - dx0) * (0.15 + 0.85 * key / 24)
            img = Image.new("L", (W, H))
            ImageDraw.Draw(img).polygon([(dx0, dy1), (dx0 + ow, dy1), (dx0 + ow * 2.6 + 200, H), (dx0 - 120, H)], fill=255)
            self.beams[key] = np.ascontiguousarray(gaussian_filter(np.asarray(img, np.float32) / 255, 12))
        add_mask(c, self.beams[key], 0, 0, glowc * 0.35, 1.0)
        m, o = self.A["p_door"], self.A["p_door_o"]
        blend_mask(c, m, int((dx0 + dx1) / 2 - o[0]), int(dy1 + 6 - o[1]), hexc("#06070a"), 1.0)
        c += (warm * 0.25 * rise ** 3)[None, None, :]
        return c

    def shot_solo(self, t, p, a, b):
        c = np.zeros((H, W, 3), np.float32)
        cv = Canvas(c)
        self.outside(cv, 0, 0, W, H, t, dict(look="night", season="spring", petals=0.8, bloom=(0.0, 0.1)), True, a)
        c *= 0.75
        pts = []
        for (s0, s1, pitch) in self.s.gtr:
            if s1 < t - 5 or s0 > t:
                continue
            for k in range(5):
                tt = s0 + (min(s1, t) - s0) * k / 4
                if tt > t:
                    break
                bend = float(np.interp(tt, self.s.bend_t, self.s.bend_v))
                pts.append((W * 0.74 - (t - tt) * 300, H * 0.6 - (pitch + bend - 64) * 18))
        if len(pts) > 1:
            cv.polyline(pts, 5, TEAL_HI, 0.95, glow=12, fade_tail=True)
            hx, hy = pts[-1]
            cv.circle(hx, hy, 9, INK, 1.0, glow=14)
        kick = self.s.since(self.s.kick, t, 0.5)
        if kick is not None:
            c += (TEAL * 0.08 * (1 - kick / 0.5))[None, None, :]
        year = 1 + int((t - a) / B)
        TYPE.text(cv, LATIN, 40, f"YEAR {year}", 90, 70, INK, 0.75)
        return c

    def render_shot(self, i, t):
        a, kind, p, _ = self.shots[i]
        b = self.shots[i + 1][0] if i + 1 < len(self.shots) else self.audio_s + TAIL
        return getattr(self, "shot_" + kind)(t, p, a, b)

    # --- lyrics as subtitles
    def subtitles(self, cv, t):
        for L in self.lines:
            ln = L["ln"]
            if t < L["times"][0] - 0.3 or t > L["out"] + 0.5:
                continue
            out_k = ramp(t, L["out"], L["out"] + 0.25)
            jp = ln["jp"]
            size = 54
            widths = [TYPE.width(MINCHO, size, ch) for ch in jp]
            x = W / 2 - sum(widths) / 2
            y = H - 196
            for ch, wch, tc in zip(jp, widths, L["times"]):
                k = ease_out((t - tc + 0.2) / 0.3) * (1 - out_k)
                if k > 0 and ch != "　":
                    sp, pad = TYPE.sprite(MINCHO, size, ch)
                    sh = self.shadow_sprite(MINCHO, size, ch)
                    cv.glyph(sh, x - pad, y - pad + 3, BLACK, 0.7 * k)
                    cv.glyph(sp, x - pad, y - pad - 8 * (1 - k), INK, k)
                x += wch
            zk = ease_out((t - L["times"][0] - 0.3) / 0.5) * (1 - out_k)
            TYPE.text(cv, ZH, 26, ln["zh"], W / 2, H - 110, hexc("#d9dbe6"), 0.85 * zk, align="center")

    def shadow_sprite(self, font, size, ch):
        key = (font, size, ch)
        if key not in self.shadow:
            sp, pad = TYPE.sprite(font, size, ch)
            self.shadow[key] = np.ascontiguousarray(np.clip(gaussian_filter(sp, 4) * 1.6, 0, 1), dtype=np.float32)
        return self.shadow[key]

    def title(self, cv, t):
        k = ease(ramp(t, 14.5, 16.0)) * (1 - ease(ramp(t, 21.0, 23.0)))
        if k <= 0:
            return
        TYPE.text(cv, MINCHO, 120, "まだね", 150, 640, INK, 0.95 * k, spacing=8)
        TYPE.text(cv, GOTHIC, 26, "初音ミク", 156, 800, hexc("#c9d3ea"), 0.9 * k)
        TYPE.text(cv, LATIN, 18, "VOCALOID ORIGINAL", 156, 842, hexc("#9aa6c4"), 0.8 * k, spacing=3)

    CREDITS = ["まだね", "vocal   初音ミク V4X", "original lyrics & concept   Astrology",
               "lyrics, music, arrangement, mix & video   Claude",
               "piano   Salamander Grand Piano — Alexander Holm (CC-BY 3.0)",
               "drums   MuldjordKit — Lars Muldjord (CC-BY 4.0)",
               "orchestra   VSCO-2 Community Edition (CC0)    guitar & bass   FreePats (CC0)"]

    def credits(self, cv, t):
        c0 = 266.0
        k = ease(ramp(t, c0 - 0.6, c0 + 0.8))
        if k > 0:
            panel = self.panel()
            cv.c *= (1 - k * (0.35 + 0.5 * panel))[:, :, None]
        for i, line in enumerate(self.CREDITS):
            k = ease_out(ramp(t, c0 + i * 0.35, c0 + i * 0.35 + 0.8))
            if k <= 0:
                continue
            font = MINCHO if i == 0 else LATIN
            size = 52 if i == 0 else 23
            y = 360 + i * 46 + (0 if i else -24)
            parts = line.split("初音ミク")
            xx = 120
            for j, part in enumerate(parts):
                TYPE.text(cv, font, size, part, xx, y, INK, 0.9 * k, spacing=1)
                xx += sum(TYPE.width(font, size, ch) + 1 for ch in part)
                if j < len(parts) - 1:
                    TYPE.text(cv, GOTHIC, size, "初音ミク", xx, y - 2, INK, 0.9 * k)
                    xx += TYPE.width(GOTHIC, size, "初音ミク")

    def panel(self):
        if not hasattr(self, "_panel"):
            xx = np.linspace(0, 1, W, dtype=np.float32)[None, :]
            yy = np.ones((H, 1), np.float32)
            self._panel = np.ascontiguousarray(np.clip(1.2 - xx * 2.2, 0, 1) ** 1.3 * yy)
        return self._panel

    def frame(self, k):
        t = k / FPS
        i = self.shot_at(t)
        a, kind, p, trans = self.shots[i]
        c = self.render_shot(i, t)
        dt = t - a
        if trans == "fade" and i > 0 and dt < 0.7:
            prev = self.render_shot(i - 1, t)
            q = ease(dt / 0.7)
            c = (prev * (1 - q) + c * q).astype(np.float32)
        elif trans == "flash" and dt < 0.45:
            c += (1 - dt / 0.45) ** 2 * (0.8 if p.get("look") != "spring" else 0.45)
        elif trans == "black":
            c *= ease(ramp(t, 0.0, 3.5))
        cv = Canvas(np.ascontiguousarray(c, dtype=np.float32))
        self.title(cv, t)
        self.subtitles(cv, t)
        self.credits(cv, t)
        end = self.audio_s + TAIL
        fade = clamp01((end - t) / 2.5)
        sdf.finish(cv.c, self.grain, 0.0005, self.vig, fade, self.out)
        return self.out.tobytes()


def resize_mask(m, k):
    m = np.asarray(m, np.float32)
    img = Image.fromarray((m * 255).astype(np.uint8))
    img = img.resize((max(1, int(m.shape[1] * k)), max(1, int(m.shape[0] * k))), Image.LANCZOS)
    return np.ascontiguousarray(np.asarray(img, np.float32) / 255)


def rotate_mask(m, ang, pivot):
    img = Image.fromarray((np.asarray(m, np.float32) * 255).astype(np.uint8))
    img = img.rotate(-math.degrees(ang), resample=Image.BICUBIC, center=(float(pivot[0]), float(pivot[1])))
    return np.ascontiguousarray(np.asarray(img, np.float32) / 255)


_R = None


def _init(audio_s):
    global _R
    _R = Story(audio_s)


def _render(k):
    return _R.frame(k)


def main():
    if sys.argv[1] == "--stills":
        audio, outdir, times = sys.argv[2], Path(sys.argv[3]), [float(x) for x in sys.argv[4:] if not x.startswith("--")]
        outdir.mkdir(parents=True, exist_ok=True)
        if not (CACHE / "room_tidy.npy").exists() or "--rebuild" in sys.argv:
            build_assets()
        r = Story(soundfile.info(audio).duration)
        for t in times:
            img = np.frombuffer(r.frame(int(round(t * FPS))), np.uint8).reshape(H, W, 3)
            Image.fromarray(img).save(outdir / f"story_{t:06.1f}.jpg", quality=92)
        print("stills written to", outdir)
        return
    audio, out = sys.argv[1], Path(sys.argv[2])
    build_assets()
    audio_s = soundfile.info(audio).duration
    frames = int((audio_s + TAIL) * FPS)
    silent = out.with_name(out.stem + "_video.mp4")
    log = out.with_suffix(".log")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "faster", "-crf", "19",
           "-pix_fmt", "yuv420p", "-an", str(silent)]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(6, initializer=_init, initargs=(audio_s,)) as pool, open(log, "w") as lg:
        for k, buf in enumerate(pool.imap(_render, range(frames), chunksize=4)):
            enc.stdin.write(buf)
            if k % (FPS * 10) == 0:
                print(f"{k / FPS:6.1f}s / {frames / FPS:.0f}s", file=lg, flush=True)
    enc.stdin.close()
    enc.wait()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", audio, "-c:v", "copy",
                    "-af", f"apad=whole_dur={frames / FPS:.3f}", "-c:a", "aac", "-b:a", "256k", "-t", f"{frames / FPS:.3f}",
                    str(out)], check=True)
    silent.unlink()
    print("wrote", out)


if __name__ == "__main__":
    main()
