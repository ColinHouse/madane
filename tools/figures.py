"""Silhouettes for the story PV: the producer (back view, seated or standing, waving)
and Miku (standing and singing, or sitting with her arms round her knees).

Every figure is a set of smooth outlines (cubic Béziers and tapered strips)
filled on a supersampled sheet, so the edges come out clean at any size.
Coordinates are figure units: feet (or the floor) at y = 0, up is negative.
"""
import math

import numpy as np
from PIL import Image, ImageDraw

SS = 3


def bez(p0, p1, p2, p3, n=32):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.asarray(p, float) for p in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def outline(*segs):
    return np.concatenate([np.asarray(s, float) for s in segs])


def taper(center, profile):
    """A band around a centreline whose width follows `profile` [(s, width), ...], s in 0..1."""
    c = np.asarray(center, float)
    d = np.gradient(c, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    seg = np.linalg.norm(np.diff(c, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)]) / max(1e-9, seg.sum())
    ps, pw = zip(*profile)
    w = np.interp(s, ps, pw)[:, None] / 2
    return np.concatenate([c + nrm * w, (c - nrm * w)[::-1]])


def mirror(pts):
    p = np.asarray(pts, float).copy()
    p[:, 0] = -p[:, 0]
    return p


class Sheet:
    """A supersampled L-mode surface. `place(x, y)` maps figure units to sheet pixels."""

    def __init__(self, w, h, scale, ox, oy, ss=SS):
        self.ss, self.w, self.h, self.k, self.ox, self.oy = ss, w, h, scale, ox, oy
        self.img = Image.new("L", (int(w * ss), int(h * ss)), 0)
        self.d = ImageDraw.Draw(self.img)

    def _p(self, pts):
        return [((self.ox + x * self.k) * self.ss, (self.oy + y * self.k) * self.ss) for x, y in np.asarray(pts, float)]

    def poly(self, pts, fill=255):
        self.d.polygon(self._p(pts), fill=fill)

    def ellipse(self, cx, cy, rx, ry, fill=255, angle=0.0):
        if angle:
            t = np.linspace(0, 2 * math.pi, 48, endpoint=False)
            ca, sa = math.cos(angle), math.sin(angle)
            x, y = rx * np.cos(t), ry * np.sin(t)
            self.poly(np.stack([cx + x * ca - y * sa, cy + x * sa + y * ca], 1), fill)
            return
        (x0, y0), (x1, y1) = self._p([(cx - rx, cy - ry), (cx + rx, cy + ry)])
        self.d.ellipse([x0, y0, x1, y1], fill=fill)

    def array(self):
        img = self.img.resize((int(self.w), int(self.h)), Image.LANCZOS)
        return np.ascontiguousarray(np.asarray(img, np.float32) / 255)


# ------------------------------------------------------------------------------ the producer
def _head(sh, top=-1000.0):
    """Back of a head with short hair (about 140 units tall), its crown at y = top."""
    d = top + 1000
    P = lambda pts: [(x, y + d) for x, y in pts]
    pts = outline(bez(*P([(-34, -858), (-60, -872), (-72, -930), (-64, -962)])),
                  bez(*P([(-64, -962), (-56, -996), (-26, -1006), (-2, -1002)])),
                  bez(*P([(-2, -1002), (20, -1010), (48, -1000), (60, -974)])),
                  bez(*P([(60, -974), (74, -940), (66, -884), (36, -858)])),
                  P([(32, -832), (-30, -832)]))
    sh.poly(pts)
    sh.ellipse(-30, -996 + d, 18, 10, angle=-0.4)        # a little untidy hair
    sh.ellipse(26, -1000 + d, 16, 9, angle=0.3)


def _upper_body(sh, top=-1000.0, hem=-490.0, arms="down"):
    """Hoodie: sloping shoulders, rounded deltoids, arms merged into the body."""
    d = top + 1000
    P = lambda pts: [(x, y + d) for x, y in pts]
    right = outline(bez(*P([(30, -850), (70, -842), (118, -830), (146, -806)])),
                    bez(*P([(146, -806), (170, -786), (176, -752), (168, -722)])),
                    bez((168, -722 + d), (150, -660 + d), (134, -580 + d), (132, hem + 30)),
                    bez((132, hem + 30), (130, hem + 8), (112, hem), (90, hem)), [(0, hem + 4)])
    sh.poly(np.concatenate([mirror(right)[::-1], right]))
    sh.ellipse(0, -826 + d, 96, 30)                      # the hood lying on the back
    for side in (-1, 1):
        sh.ellipse(side * 140, -790 + d, 42, 38)         # shoulders
        if arms == "down" or (arms == "wave_left" and side == -1):
            c = bez((side * 150, -790 + d), (side * 178, -700 + d), (side * 180, -600 + d), (side * 166, hem + 8), 24)
            sh.poly(taper(c, [(0, 74), (0.5, 60), (1, 50)]))
            sh.ellipse(side * 164, hem - 18, 27, 36)
        elif arms == "forward":                           # reaching to the desk: only the upper arm shows
            c = bez((side * 150, -790 + d), (side * 184, -720 + d), (side * 188, -650 + d), (side * 176, -560 + d), 16)
            sh.poly(taper(c, [(0, 74), (1, 64)]))


def _legs(sh, hem=-490.0):
    for side in (-1, 1):
        c = bez((side * 58, hem - 30), (side * 64, -330), (side * 60, -180), (side * 56, -40), 24)
        sh.poly(taper(c, [(0, 120), (0.45, 92), (1, 66)]))
        sh.poly(outline(bez((side * 20, -46), (side * 18, -20), (side * 30, 0), (side * 60, 0)),
                        bez((side * 60, 0), (side * 96, 0), (side * 100, -24), (side * 92, -46))))
    sh.ellipse(0, hem - 4, 92, 26)


def producer_standing(height, wave=False):
    """Back view; returns (mask, origin_xy, elbow_xy or None). `height` = pixels from the feet to the crown."""
    k = height / 1000.0
    w, h = int(700 * k), int(1080 * k)
    ox, oy = w / 2, h - 30 * k
    sh = Sheet(w, h, k, ox, oy)
    _head(sh)
    _upper_body(sh, arms="wave_left" if wave else "down")
    _legs(sh)
    elbow = None
    if wave:                                             # the upper arm lifted out to the side
        sh.poly(taper(np.linspace((150, -796), (252, -874), 10), [(0, 74), (1, 60)]))
        sh.ellipse(252, -874, 30, 30)
        elbow = (ox + 252 * k, oy - 874 * k)
    return sh.array(), (ox, oy), elbow


def forearm(height):
    """The waving forearm and open hand, pointing up from the elbow; returns (mask, pivot_xy)."""
    k = height / 1000.0
    n = int(440 * k)
    sh = Sheet(n, n, k, n / 2, n - 40 * k)
    sh.poly(taper(bez((0, 0), (4, -60), (10, -120), (12, -170), 12), [(0, 58), (1, 46)]))
    sh.poly(outline(bez((-16, -168), (-30, -200), (-28, -246), (0, -262)),          # a mitten of a hand
                    bez((0, -262), (30, -270), (44, -230), (38, -168))))
    sh.poly(taper(bez((-18, -186), (-36, -196), (-48, -214), (-54, -232), 8), [(0, 22), (1, 14)]))   # thumb
    return sh.array(), (n / 2, n - 40 * k)


def producer_seated(height):
    """Head and shoulders of the producer at the desk (the chair hides the rest).
    `height` is the standing height in pixels, which sets the scale; the crown sits at the sheet's top + pad."""
    k = height / 1000.0
    w, h = int(760 * k), int(620 * k)
    ox, oy = w / 2, h
    sh = Sheet(w, h, k, ox, oy)
    top = -580
    _head(sh, top=top)
    _upper_body(sh, top=top, hem=0, arms="forward")
    return sh.array(), (ox, oy)


# ------------------------------------------------------------------------------------- Miku
def _tail(sh, side, root, c1, c2, tip, profile):
    c = bez((side * root[0], root[1]), (side * c1[0], c1[1]), (side * c2[0], c2[1]), (side * tip[0], tip[1]), 48)
    sh.poly(taper(c, profile))


def _flared_sleeve(sh, elbow, wrist, w0=30, w1=64):
    sh.poly(taper(np.linspace(elbow, wrist, 8), [(0, w0), (1, w1)]))


def miku_standing(height, pose="sing"):
    """Front view, 1000 units tall; returns (mask, origin_xy, elbow_xy or None).
    pose: 'sing' (hand to her chest), 'wave' (upper arm only: the forearm is miku_forearm), 'still'."""
    k = height / 1000.0
    w, h = int(760 * k), int(1060 * k)
    ox, oy = w / 2, h - 24 * k
    sh = Sheet(w, h, k, ox, oy)
    for side in (-1, 1):                               # twin tails, long and full
        _tail(sh, side, (76, -952), (236, -1012), (318, -560), (178, -150),
              [(0, 44), (0.1, 112), (0.42, 136), (0.78, 84), (1, 6)])
        sh.ellipse(side * 74, -956, 15, 24, angle=side * 0.5)          # hair ties
    sh.ellipse(0, -868, 60, 70)                        # face
    crown = outline(bez((-82, -858), (-96, -936), (-62, -1004), (0, -1006)),
                    bez((0, -1006), (62, -1004), (96, -936), (82, -858)),
                    bez((82, -858), (60, -900), (20, -918), (0, -910)),
                    bez((0, -910), (-20, -918), (-60, -900), (-82, -858)))
    sh.poly(crown)
    for side in (-1, 1):                               # side locks framing the face
        sh.poly(taper(bez((side * 70, -900), (side * 80, -850), (side * 74, -800), (side * 66, -752), 16),
                      [(0, 30), (1, 6)]))
    sh.poly([(-13, -806), (13, -806), (14, -770), (-14, -770)])        # neck
    torso = outline(bez((-14, -790), (-40, -786), (-64, -780), (-72, -762)),
                    bez((-72, -762), (-76, -744), (-62, -722), (-58, -716)),
                    bez((-58, -716), (-50, -680), (-40, -650), (-42, -628)),
                    [(42, -628)],
                    bez((42, -628), (40, -650), (50, -680), (58, -716)),
                    bez((58, -716), (62, -722), (76, -744), (72, -762)),
                    bez((72, -762), (64, -780), (40, -786), (14, -790)))
    sh.poly(torso)
    hem = [(-152, -508), (-114, -524), (-76, -506), (-38, -524), (0, -506), (38, -524), (76, -506), (114, -524), (152, -508)]
    sh.poly([(-48, -636), (48, -636)] + hem[::-1])      # pleated skirt
    # arms: her right hangs down, her left either to her chest (sing) or up (wave)
    sh.poly(taper(bez((-70, -764), (-82, -720), (-86, -690), (-88, -664), 10), [(0, 30), (1, 24)]))
    _flared_sleeve(sh, (-88, -668), (-100, -566))
    sh.ellipse(-100, -548, 14, 18)
    elbow = None
    if pose == "wave":
        sh.poly(taper(bez((70, -764), (104, -776), (140, -786), (170, -792), 10), [(0, 30), (1, 26)]))
        sh.ellipse(170, -792, 14, 14)
        elbow = (ox + 170 * k, oy - 792 * k)
    elif pose == "sing":
        sh.poly(taper(bez((70, -764), (92, -730), (104, -700), (106, -684), 10), [(0, 30), (1, 24)]))
        _flared_sleeve(sh, (104, -686), (40, -722), 28, 56)
        sh.ellipse(28, -726, 15, 17)
    else:
        sh.poly(taper(bez((70, -764), (82, -720), (86, -690), (88, -664), 10), [(0, 30), (1, 24)]))
        _flared_sleeve(sh, (88, -668), (100, -566))
        sh.ellipse(100, -548, 14, 18)
    for side, shift in ((-1, -6), (1, 8)):             # legs and thigh-high boots
        x = side * 36 + shift
        sh.poly(taper(bez((x, -530), (x - side * 2, -470), (x - side * 4, -420), (x - side * 4, -380), 8), [(0, 62), (1, 54)]))
        boot = bez((x - side * 4, -470), (x - side * 6, -300), (x - side * 2, -150), (x, -34), 24)
        sh.poly(taper(boot, [(0, 78), (0.1, 60), (0.55, 50), (1, 42)]))
        sh.poly([(x - 22, -40), (x + 20, -40), (x + 24, -6), (x + 28, 0), (x - 26, 0), (x - 24, -8)])
    return sh.array(), (ox, oy), elbow


def miku_forearm(height):
    """Her waving forearm, flared sleeve and hand, pointing up from the elbow; returns (mask, pivot_xy)."""
    k = height / 1000.0
    n = int(300 * k)
    sh = Sheet(n, n, k, n / 2, n - 30 * k)
    sh.poly(taper(np.linspace((0, 0), (6, -118), 8), [(0, 28), (1, 58)]))
    sh.ellipse(8, -142, 17, 23)
    return sh.array(), (n / 2, n - 30 * k)


def miku_sitting(height):
    """Side view, facing right, arms round her knees; `height` = pixels from the floor to the top of the head."""
    k = height / 520.0
    w, h = int(980 * k), int(600 * k)
    ox, oy = w * 0.55, h - 20 * k
    sh = Sheet(w, h, k, ox, oy)
    # twin tails falling down her back and pooling on the floor
    for dx, wid in ((0, 1.0), (26, 0.8)):
        c = outline(bez((40 + dx, -470), (-110 + dx, -500), (-150 + dx, -220), (-250 + dx, -26), 36),
                    bez((-250 + dx, -26), (-300 + dx, 0), (-380 + dx, 0), (-430 + dx * 2, -2), 16))
        sh.poly(taper(c, [(0, 40 * wid), (0.15, 104 * wid), (0.55, 96 * wid), (0.8, 46 * wid), (1, 10)]))
    # back and seat
    sh.poly(outline(bez((10, -372), (-48, -350), (-84, -250), (-82, -120)),
                    bez((-82, -120), (-80, -60), (-70, -18), (-40, -6)),
                    [(60, -6), (70, -80), (40, -300)]))
    sh.poly([(-90, -40), (40, -66), (70, -20), (-70, -2)])     # skirt over the hips
    # thigh up to the knee, shin down to the boot
    sh.poly(taper(bez((-20, -40), (40, -150), (100, -250), (150, -296), 12), [(0, 74), (1, 56)]))
    sh.poly(taper(bez((158, -292), (166, -200), (170, -110), (174, -30), 12), [(0, 54), (0.3, 62), (1, 44)]))
    sh.poly([(150, -30), (196, -30), (232, -8), (236, 0), (150, 0)])
    # head resting on the knees, hair
    sh.ellipse(98, -388, 62, 66, angle=0.25)
    sh.poly(outline(bez((40, -340), (20, -420), (60, -478), (120, -472)),
                    bez((120, -472), (166, -462), (176, -410), (162, -370)),
                    [(110, -400)]))
    sh.ellipse(52, -470, 16, 24, angle=-0.4)           # hair tie
    # arm round the shins, flared sleeve at the wrist
    sh.poly(taper(bez((14, -352), (60, -320), (90, -280), (110, -246), 10), [(0, 30), (1, 26)]))
    _flared_sleeve(sh, (110, -246), (184, -214), 28, 56)
    sh.ellipse(196, -214, 16, 14)
    return sh.array(), (ox, oy)
