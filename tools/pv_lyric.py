"""まだね PV — lyric motion graphics (リリックモーション) on a geometric stage.

Big Mincho lyrics arrive syllable by syllable on the sung notes, in layouts that
change line to line (horizontal, vertical, split, hero). Behind them, flat
geometry tells the story and moves with the band: the 2 a.m. clock, the
monitor's light, notes joined one by one, sakura petals, the unopened folders,
the guitar line traced in light. Shapes are anti-aliased signed-distance
drawings (tools/sdf.py); text that crosses the big circle knocks out to paper.

    python -I tools/pv_lyric.py <mix.wav> <out.mp4>
    python -I tools/pv_lyric.py --stills <mix.wav> <dir> t1 t2 ...
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
from PIL import Image, ImageDraw, ImageFont

import arrangement
import build
import lyric_align
import madane
import music
import pv
import sdf

W, H, FPS = 1920, 1080, 30
TAIL = 4.0                                  # picture after the audio ends
FONTS = Path(r"C:\Windows\Fonts")
MINCHO = str(FONTS / "yumindb.ttf")
GOTHIC = str(FONTS / "YuGothM.ttc")
ZH = str(FONTS / "msyhl.ttc")
LATIN = str(FONTS / "bahnschrift.ttf")


def hexc(s):
    s = s.lstrip("#")
    return np.array([int(s[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ramp(t, a, b):
    return clamp01((t - a) / (b - a)) if b != a else float(t >= a)


def ease(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def mix(a, b, k):
    return (a * (1 - k) + b * k).astype(np.float32)


# --- palettes ----------------------------------------------------------------------
def P(top, bottom, ink, accent, accent2, mute, petal=None, light=False):
    d = dict(top=hexc(top), bottom=hexc(bottom), ink=hexc(ink), accent=hexc(accent), accent2=hexc(accent2),
             mute=hexc(mute), light=light)
    d["petal"] = hexc(petal) if petal else d["accent"]
    d["paper"] = mix(d["top"], d["bottom"], 0.5)
    return d


PALETTES = {
    "night": P("#0a1424", "#14263c", "#eaf2f8", "#39c5bb", "#8fb8ff", "#5d7088", "#f2a7c3"),
    "dawn": P("#161b36", "#3a2d55", "#f3eef8", "#f2a7c3", "#39c5bb", "#8a7fae"),
    "paper": P("#f5f0e9", "#ece2d6", "#1c1c24", "#e0506f", "#2aa198", "#a69a8d", "#f3b7c6", light=True),
    "mist": P("#eef2f3", "#d5e1e5", "#22313a", "#2aa198", "#e0789a", "#8ea2aa", "#f0b3c3", light=True),
    "fade": P("#2a2f35", "#3b4148", "#e3e6e8", "#9aa7b0", "#c6a77a", "#6c767e"),
    "ember": P("#1b1512", "#2c1f18", "#f4e9dc", "#ffb35c", "#e0506f", "#7a6252"),
    "bloom": P("#f8d9e1", "#efb3c5", "#2a1020", "#c2185b", "#1e3a5f", "#b56f88", "#fff1f5", light=True),
    "stage": P("#060609", "#11111a", "#ffffff", "#ff4f8b", "#39c5bb", "#3a3a4a"),
    "dusk": P("#0f182b", "#2a2137", "#f1e6d8", "#ffb35c", "#6b7fd7", "#5a5a78"),
    "mono": P("#040404", "#0c0c0c", "#f2f2f2", "#ffffff", "#9a9a9a", "#4a4a4a", "#e8e8e8"),
    "spring": P("#fffaf7", "#fde0e8", "#1a1424", "#e0506f", "#2aa198", "#b07a8c", "#fbd3de", light=True),
    "night2": P("#0a1424", "#1d2240", "#f4f0f6", "#f2a7c3", "#39c5bb", "#66708e"),
}
SECTION_LOOK = {   # section -> (palette, transition into it)
    "Intro": ("night", None), "Intro B": ("night", "fade"), "1A": ("night", "fade"), "1B": ("dawn", "fade"),
    "1サビ": ("paper", "circle"), "間奏": ("mist", "fade"), "2A": ("fade", "fade"), "2B": ("ember", "fade"),
    "2サビ": ("bloom", "circle"), "Solo": ("stage", "circle"), "Cメロ": ("dusk", "fade"),
    "落ちサビ": ("mono", "fade"), "ラスサビ": ("spring", "flash"), "Outro": ("night2", "fade"),
}
GRADIENTS = {}


def gradient(name):
    if name not in GRADIENTS:
        p = PALETTES[name]
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        x = np.linspace(0, 1, W, dtype=np.float32)[None, :, None]
        g = p["top"] * (1 - y) + p["bottom"] * y
        g = g * (1 - 0.06 * (x - 0.5) ** 2)
        GRADIENTS[name] = np.ascontiguousarray(np.broadcast_to(g, (H, W, 3)), dtype=np.float32)
    return GRADIENTS[name]


# --- drawing -------------------------------------------------------------------------------
class Canvas:
    def __init__(self, base):
        self.c = base
        self.knock = (0.0, 0.0, 0.0, np.zeros(3, np.float32))     # text knock-out circle

    def circle(self, cx, cy, r, col, op=1.0, glow=0.0):
        sdf.circle(self.c, float(cx), float(cy), float(r), col, float(op), float(glow))

    def ring(self, cx, cy, r, width, col, op=1.0, a0=0.0, span=7.0, glow=0.0):
        sdf.ring(self.c, float(cx), float(cy), float(r), float(width), col, float(op), float(a0), float(span), float(glow))

    def line(self, x0, y0, x1, y1, width, col, op=1.0, glow=0.0):
        sdf.line(self.c, float(x0), float(y0), float(x1), float(y1), float(width), col, float(op), float(glow))

    def polyline(self, pts, width, col, op=1.0, glow=0.0, fade_tail=False):
        n = len(pts)
        if n < 2:
            return
        xs = np.array([p[0] for p in pts], np.float64)
        ys = np.array([p[1] for p in pts], np.float64)
        ops = np.array([op * (0.15 + 0.85 * i / max(1, n - 2)) if fade_tail else op for i in range(n - 1)], np.float64)
        sdf.polyline(self.c, xs, ys, ops, float(width), col, float(glow))

    def rect(self, cx, cy, w, h, col, op=1.0, angle=0.0, stroke=0.0):
        sdf.rect(self.c, float(cx), float(cy), float(w), float(h), float(angle), col, float(op), float(stroke))

    def petal(self, cx, cy, size, angle, col, op=1.0):
        sdf.petal(self.c, float(cx), float(cy), float(size), float(angle), col, float(op))

    def glyph(self, sprite, x, y, col, op=1.0):
        kx, ky, kr, kcol = self.knock
        sdf.glyph(self.c, sprite, int(round(x)), int(round(y)), col, float(op), float(kx), float(ky), float(kr), kcol)


class Type:
    """Glyph sprites (alpha arrays) per font and size."""
    VERT = {"「": "﹁", "」": "﹂", "、": "︑", "。": "︒"}
    SMALL = set("ぁぃぅぇぉっゃゅょゎァィゥェォッャュョ")

    def __init__(self):
        self.fonts, self.cache = {}, {}

    def font(self, path, size):
        if (path, size) not in self.fonts:
            self.fonts[(path, size)] = ImageFont.truetype(path, size)
        return self.fonts[(path, size)]

    def sprite(self, path, size, ch):
        key = (path, size, ch)
        if key not in self.cache:
            pad = size // 4
            img = Image.new("L", (size + 2 * pad, int(size * 1.5) + 2 * pad))
            ImageDraw.Draw(img).text((pad, pad), ch, font=self.font(path, size), fill=255)
            self.cache[key] = (np.ascontiguousarray(np.asarray(img, np.float32) / 255), pad)
        return self.cache[key]

    def width(self, path, size, text):
        return self.font(path, size).getlength(text)

    def text(self, cv, path, size, text, x, y, col, op=1.0, spacing=0.0, align="left"):
        if op <= 0.002:
            return
        wpx = sum(self.width(path, size, ch) + spacing for ch in text) - spacing
        x = x - wpx / 2 if align == "center" else x - wpx if align == "right" else x
        for ch in text:
            sp, pad = self.sprite(path, size, ch)
            cv.glyph(sp, x - pad, y - pad, col, op)
            x += self.width(path, size, ch) + spacing


TYPE = Type()


# --- song data ----------------------------------------------------------------------------
class Song:
    def __init__(self):
        marks, parts, chords, hook, bars = music.layout(madane.SECTIONS)
        s = build.seconds
        self.end = s(bars * music.BAR)
        self.secs = [(m.name, s(m.start), s(m.start + m.bars * music.BAR), m.feel) for m in marks]
        self.names = [x[0] for x in self.secs]
        self.start = {n: a for n, a, _, _ in self.secs}
        self.stop = {n: b for n, _, b, _ in self.secs}
        sections = build.sung_sections(parts)
        self.vocal = sorted((s(n.start), s(n.start + n.length), n.pitch, n.lyric) for sec in sections for n in sec["notes"])
        arr, _ = arrangement.arrange(marks, chords, [n for sec in sections for n in sec["notes"]],
                                     [x.get("transpose", 0) for x in madane.SECTIONS], hook, madane.GUITAR_LEAD, madane.BPM)
        ev = lambda name, keys=None: np.array(sorted(s(n.start) for n in arr[name] if keys is None or n.pitch in keys))
        self.kick = ev("Drums", {arrangement.KICK})
        self.snare = ev("Drums", {arrangement.SNARE})
        self.crash = ev("Drums", {arrangement.CRASH})
        self.bass = sorted((s(n.start), s(n.start + n.length), n.pitch) for n in arr["Bass"])
        self.violin = sorted((s(n.start), s(n.start + n.length), n.pitch) for n in arr["Solo Violin"])
        song = arrangement.Song(marks, chords, [], [x.get("transpose", 0) for x in madane.SECTIONS], madane.BPM)
        gtr, bends = arrangement.lead_guitar(song, madane.GUITAR_LEAD)
        self.gtr = sorted((s(n.start), s(n.start + n.length), n.pitch) for n in gtr)
        bt = sorted(bends)
        self.bend_t = np.array([s(t) for t, _ in bt]) if bt else np.zeros(2)
        self.bend_v = np.array([v for _, v in bt]) if bt else np.zeros(2)
        self.hook = sorted((s(n.start), s(n.start + n.length), n.pitch) for n in hook)
        self.gliss = [s(m.start) for m in marks if m.feel in ("chorus", "chorus2", "last", "interlude")]
        _, self.lines = pv.timeline()
        quote = next(ln for ln in self.lines if "「あ」" in ln["jp"])
        self.first_a = next(a for a, _, _, syl in self.vocal if syl == "あ" and a >= quote["onsets"][0])
        self.phrase_starts, prev = [], -10.0
        for a, b, p, syl in self.vocal:
            if a - prev > 0.35:
                self.phrase_starts.append(a)
            prev = b

    def section(self, t):
        for sec in self.secs:
            if sec[1] <= t < sec[2]:
                return sec
        return self.secs[-1]

    @staticmethod
    def since(events, t, window):
        i = int(np.searchsorted(events, t, side="right")) - 1
        if i < 0:
            return None
        dt = t - events[i]
        return dt if dt <= window else None


# --- lyric layouts ----------------------------------------------------------------------------
LAYOUT = {
    "1A": ["low", "vright", "low", "vright"], "1B": ["midleft", "vleft"],
    "1サビ": ["hero", "split", "center", "vright"], "2A": ["low", "vleft", "midleft", "vleft"],
    "2B": ["center", "center"], "2サビ": ["hero", "split", "center", "vright"],
    "Cメロ": ["midleft", "vleft", "low", "midleft"], "落ちサビ": ["quiet"] * 4,
    "ラスサビ": ["hero", "split", "center", "vright", "hero"], "Outro": ["finale"],
}
HIGHLIGHT = ["「あ」", "声", "桜", "さよなら", "ごめんね", "春", "誰も", "残る", "まだ", "歌", "あなた", "またね"]


def _row(text, x, y, font, size):
    out = []
    for ch in text:
        out.append((ch, x, y, font, size, False))
        x += TYPE.width(font, size, ch)
    return out


def source_index(chars, jp):
    """Index in `jp` of every laid-out character (layouts drop the spaces and swap in vertical forms)."""
    out, j = [], 0
    for c in chars:
        while j < len(jp) - 1 and c[0] != jp[j] and c[0] != Type.VERT.get(jp[j], jp[j]):
            j += 1
        out.append(j)
        j = min(j + 1, len(jp) - 1)
    return out


def layout_line(ln, template):
    """[(char, x, y, font, size, vertical)] and where the translation goes."""
    jp, out = ln["jp"], []
    if template == "hero":
        size, font = 132, MINCHO
        y = 290
        for k, part in enumerate(jp.split("　")):
            wpx = TYPE.width(font, size, part)
            out += _row(part, W / 2 - wpx / 2 + (-170 if k == 0 else 170), y, font, size)
            y += size * 1.35
        zh = (W / 2 + 170, y + 30, "center")
    elif template in ("vright", "vleft"):
        size, font = 76, MINCHO
        x = 1530 if template == "vright" else 290
        y0 = y = 150
        for ch in jp:
            if ch == "　":
                x -= size * 1.25
                y = y0 + size * 1.4
                continue
            out.append((Type.VERT.get(ch, ch), x, y, font, size, True))
            y += size * 1.08
        zh = (x - 40, 960, "right") if template == "vright" else (x + 150, 960, "left")
    elif template == "split":
        size, font = 88, MINCHO
        parts = jp.split("　")
        out += _row(parts[0], 1000 - TYPE.width(font, size, parts[0]) / 2, 210, font, size)
        if len(parts) > 1:
            out += _row(parts[1], W - 170 - TYPE.width(font, size, parts[1]), 520, font, size)
        zh = (W - 170, 690, "right")
    elif template == "low":
        out += _row(jp, 180, 720, MINCHO, 70)
        zh = (184, 832, "left")
    elif template == "midleft":
        out += _row(jp, 180, 400, MINCHO, 84)
        zh = (184, 530, "left")
    elif template == "quiet":
        size = 80
        wpx = TYPE.width(MINCHO, size, jp)
        out += _row(jp, W / 2 - wpx / 2, 480, MINCHO, size)
        zh = (W / 2, 600, "center")
    elif template == "finale":
        size = 108
        wpx = TYPE.width(MINCHO, size, jp)
        out += _row(jp, 600 - wpx / 2, 430, MINCHO, size)
        zh = (600, 590, "center")
    else:                                                       # center
        size = 96
        wpx = TYPE.width(MINCHO, size, jp)
        out += _row(jp, W / 2 - wpx / 2, 470, MINCHO, size)
        zh = (W / 2, 612, "center")
    return out, zh


# --- renderer -------------------------------------------------------------------------------------
class PV:
    def __init__(self, audio_s):
        self.s = Song()
        self.audio_s = audio_s
        rng = np.random.default_rng(7)               # one still grain, like paper (and kind to the encoder)
        self.grain = [np.ascontiguousarray(rng.normal(0, 40, (H // 2, W // 2)).clip(-127, 127).astype(np.int8))]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.vig = np.ascontiguousarray(1 - 0.32 * np.clip(np.hypot((xx / W - 0.5) * 1.25, (yy / H - 0.5) * 1.25) - 0.25, 0, 1) ** 1.6,
                                        dtype=np.float32)
        self.out = np.zeros((H, W, 3), np.uint8)
        self.lines, counters = [], {}
        for ln in self.s.lines:
            k = counters.get(ln["section"], 0)
            counters[ln["section"]] = k + 1
            tpl = LAYOUT.get(ln["section"], ["center"])
            chars, zh = layout_line(ln, tpl[k % len(tpl)])
            # every character arrives on the note that sings it (a kanji on its first syllable)
            jp = ln["jp"]
            jp_times = lyric_align.char_times(jp, ln["syls"], ln["onsets"])
            src = source_index(chars, jp)
            times = [jp_times[j] for j in src]
            marked = set()
            for word in HIGHLIGHT:
                j = jp.find(word)
                while j >= 0:
                    marked.update(range(j, j + len(word)))
                    j = jp.find(word, j + 1)
            hl = [j in marked for j in src]
            self.lines.append(dict(ln=ln, chars=chars, times=times, zh=zh, hl=hl))
        for i, L in enumerate(self.lines):
            nxt = self.lines[i + 1]["ln"]["onsets"][0] if i + 1 < len(self.lines) else 1e9
            L["out"] = min(L["ln"]["end"] + 1.6, nxt - 0.2)
        self.lines[-1]["out"] = 1e9                     # the last words stay until the picture fades
        self.petals = self._petals()
        rnd = random.Random(3)
        self.dust = [(rnd.uniform(900, 1800), rnd.uniform(150, 1000), rnd.uniform(0.6, 2.2), rnd.uniform(0, 6.3))
                     for _ in range(50)]

    def _petals(self):
        rng = random.Random(11)
        out = []
        for name, density in (("1サビ", 34), ("2サビ", 52), ("ラスサビ", 96), ("落ちサビ", 16), ("間奏", 12), ("Outro", 10)):
            a, b = self.s.start[name], self.s.stop[name]
            for _ in range(int(density * (b - a) / 24)):
                out.append(dict(t0=rng.uniform(a - 3, b), x=rng.uniform(-100, W + 250), life=rng.uniform(7, 11),
                                size=rng.uniform(9, 21), vx=rng.uniform(-70, -20), vy=rng.uniform(55, 105),
                                rot=rng.uniform(0, 6.3), spin=rng.uniform(-1.4, 1.4), sway=rng.uniform(0.5, 1.4),
                                sec=name))
        return out

    # --- background and section transitions
    def background(self, t):
        name, a, b, _ = self.s.section(t)
        pal, trans = SECTION_LOOK[name]
        cur = gradient(pal).copy()
        i = self.s.names.index(name)
        if i == 0 or trans is None:
            return cur, pal
        prev = gradient(SECTION_LOOK[self.s.names[i - 1]][0])
        dt = t - a
        if trans == "fade" and dt < 0.9:
            k = ease(dt / 0.9)
            return (prev * (1 - k) + cur * k).astype(np.float32), pal
        if trans in ("circle", "flash") and dt < 0.8:
            sdf.circle_wipe(cur, prev, W * 0.5, H * 0.5, ease_out(dt / 0.8) * math.hypot(W, H) * 0.62)
            if trans == "flash" and dt < 0.5:
                cur += (1 - cur) * ((1 - dt / 0.5) * 0.85)
            return cur, pal
        return cur, pal

    def frame(self, k):
        t = k / FPS
        bg, pal_name = self.background(t)
        cv = Canvas(bg)
        pal = PALETTES[pal_name]
        name, a, b, feel = self.s.section(t)
        self.motif(cv, t, name, a, b, pal)
        self.petals_draw(cv, t, pal)
        self.lyrics(cv, t, pal)
        self.furniture(cv, t, name, pal)
        self.title(cv, t, pal)
        self.ending(cv, t, pal)
        end = self.audio_s + TAIL
        fade = clamp01(t / 0.8) * clamp01((end - t) / 2.5)
        sdf.finish(cv.c, self.grain[k % len(self.grain)], 0.00045 if pal["light"] else 0.0006, self.vig, fade, self.out)
        return self.out.tobytes()

    # --- section motifs
    def motif(self, cv, t, name, a, b, pal):
        s = self.s
        kick = s.since(s.kick, t, 0.6)
        pulse = math.exp(-kick * 7) if kick is not None else 0.0
        if name in ("Intro", "Intro B", "Outro"):
            self.clock(cv, t, pal, pulse, intro=name != "Outro")
        elif name == "1A":
            self.monitor(cv, t, a, b, pal)
        elif name == "1B":
            self.constellation(cv, t, a, b, pal)
        elif name in ("1サビ", "2サビ", "ラスサビ"):
            self.bloom(cv, t, a, b, pal, pulse, big=name == "ラスサビ", band=name != "1サビ")
        elif name == "間奏":
            k = ease(ramp(t, a, a + 1.5)) * (1 - ramp(t, b - 1.5, b))
            TYPE.text(cv, MINCHO, 210, "時の桜が", 120, 120, pal["accent"], 0.07 * k)
            TYPE.text(cv, MINCHO, 210, "舞い落ちる", W - 120, 640, pal["accent"], 0.07 * k, align="right")
            self.trace(cv, t, s.violin, pal["accent"], pal, base_y=760, scale=17, width=4, glide=0.12)
        elif name in ("2A", "Cメロ"):
            self.folders(cv, t, a, b, pal, drift=name == "Cメロ", pulse=pulse)
        elif name == "2B":
            self.walls(cv, t, a, b, pal)
        elif name == "Solo":
            self.solo(cv, t, a, b, pal, pulse)
        elif name == "落ちサビ":
            cv.ring(W / 2, H / 2, 300 * (1 + 0.015 * math.sin(t * 1.3)), 1.6, pal["accent"], 0.5)
        g = next((g for g in s.gliss if 0 <= g - t < 1.4), None)
        if g is not None:                                     # the harp sweeps in: a fan of lines
            k = 1 - (g - t) / 1.4
            for i in range(14):
                ang = -math.pi / 2 + (i - 6.5) * 0.11
                ln = 950 * ease_out(clamp01(k * 1.4 - i * 0.04))
                cv.line(W / 2, H + 40, W / 2 + math.cos(ang) * ln, H + 40 + math.sin(ang) * ln, 1.4,
                        pal["accent2"], 0.35 * (1 - 0.5 * k))

    def clock(self, cv, t, pal, pulse, intro=True):
        cx, cy, r = (1320 if intro else 1440), 540, 300 * (1 + 0.012 * pulse)
        draw = ease(ramp(t, 0.5, 5.0)) if intro else 1.0
        cv.ring(cx, cy, r, 2.2, pal["ink"], 0.85, a0=0.0, span=draw * 2 * math.pi - 1e-4 if draw < 1 else 7.0)
        cv.ring(cx, cy, r + 54, 1.0, pal["mute"], 0.5 * draw)
        for i in range(12):
            ang = i / 12 * 2 * math.pi
            show = ramp(t, 1.0 + i * 0.35, 1.6 + i * 0.35) if intro else 1.0
            r0, r1 = r - (24 if i % 3 == 0 else 12), r - 2
            cv.line(cx + math.sin(ang) * r0, cy - math.cos(ang) * r0, cx + math.sin(ang) * r1, cy - math.cos(ang) * r1,
                    2.0 if i % 3 == 0 else 1.2, pal["ink"], 0.7 * show)
        hands = ramp(t, 4.0, 6.0) if intro else 1.0
        minute = (t - (0 if intro else self.s.start["Outro"])) / 60 * 2 * math.pi * (1 if intro else 4)
        hour = 2 / 12 * 2 * math.pi + minute / 12
        cv.line(cx, cy, cx + math.sin(hour) * r * 0.5, cy - math.cos(hour) * r * 0.5, 5, pal["ink"], 0.9 * hands)
        cv.line(cx, cy, cx + math.sin(minute) * r * 0.78, cy - math.cos(minute) * r * 0.78, 2.4, pal["accent"], 0.9 * hands)
        cv.circle(cx, cy, 7, pal["accent"], hands)
        for s0, s1, p in self.s.hook:                         # music-box notes land on the dial
            if s0 <= t < s0 + 4.0:
                ang = (p % 12) / 12 * 2 * math.pi
                k = (t - s0) / 4.0
                rr = r + 26 + 30 * ease_out(k)
                cv.circle(cx + math.sin(ang) * rr, cy - math.cos(ang) * rr, 5 + 3 * (1 - k), pal["accent"], 1 - k, glow=6)
        kick = self.s.since(self.s.kick, t, 0.6)
        if kick is not None:                                   # kick rings once the band is in
            cv.ring(cx, cy, r + 60 + 260 * ease_out(kick / 0.6), 1.5, pal["accent2"], 0.4 * (1 - kick / 0.6))

    def monitor(self, cv, t, a, b, pal):
        x0, y0, x1, y1 = 1260, 150, 1720, 930
        k = ease(ramp(t, a, a + 2))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cv.circle(cx, cy, 260, pal["accent2"], 0.05 * k, glow=320)            # the screen's light in the room
        cv.rect(cx, cy, x1 - x0, y1 - y0, pal["accent2"], 0.06 * k)
        cv.rect(cx, cy, x1 - x0, y1 - y0, pal["accent2"], 0.55 * k, stroke=1.6)
        cv.line(200, 960, W - 120, 960, 1.0, pal["mute"], 0.5 * k)            # the desk
        for i, (dx, dy, sp, ph) in enumerate(self.dust):                      # dust in the light
            y = dy - (t - a) * 14 * sp
            y = 150 + (y - 150) % 850
            tw = 0.5 + 0.5 * math.sin(t * sp * 1.7 + ph)
            cv.circle(dx + 12 * math.sin(t * 0.4 * sp + ph), y, 1.4 + sp * 0.5, pal["ink"], 0.28 * k * tw)
        age = t - self.s.first_a
        if -0.05 <= age < 3.4:                                 # the first sound she was given leaves the screen,
            sp, pad = TYPE.sprite(MINCHO, 520, "あ")              # clear of the words written on it
            op = clamp01(age / 0.25) * (1 - ramp(age, 2.2, 3.4))
            drift = ease_out(age / 3.4)
            cv.glyph(sp, cx - 620 - pad - 50 * drift, cy - 330 - pad - 20 * drift, pal["accent"], 0.85 * op)

    def constellation(self, cv, t, a, b, pal):
        """ひとつずつ 音符を並べて: each sung note becomes a point, joined in order."""
        notes = [n for n in self.s.vocal if a <= n[0] < b and n[0] <= t]
        pts = []
        for s0, s1, p, syl in notes:
            x = 900 + (s0 - a) / (b - a) * 880
            y = 820 - (p - 62) * 24
            pts.append((x, y, s0))
        for (x0, y0, s0), (x1, y1, s1) in zip(pts, pts[1:]):
            k = ease_out((t - s1) / 0.3)
            cv.line(x0, y0, x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, 1.2, pal["ink"], 0.45)
        for i, (x, y, s0) in enumerate(pts):
            k = ease_out((t - s0) / 0.3)
            breath = s0 in self.s.phrase_starts
            cv.circle(x, y, (6 if breath else 4) * k, pal["accent"] if breath else pal["ink"], 0.9, glow=4 if breath else 0)
            if breath:                                         # the breath marks she drew
                cv.ring(x, y - 34, 18, 1.8, pal["accent"], 0.8 * k, a0=5.2, span=1.9)

    def bloom(self, cv, t, a, b, pal, pulse, big=False, band=True):
        cx, cy = (520, 560) if not big else (W / 2, H / 2)
        r = (360 if not big else 430) * (1 + 0.03 * pulse) * (0.9 + 0.1 * ease_out(ramp(t, a, a + 1)))
        cv.ring(cx, cy, r + 150, 1.0, pal["mute"], 0.35)
        for i in range(48):                                    # a slow dial of ticks behind the sun
            ang = i / 48 * 2 * math.pi + t * 0.05
            cv.line(cx + math.sin(ang) * (r + 140), cy - math.cos(ang) * (r + 140),
                    cx + math.sin(ang) * (r + 150), cy - math.cos(ang) * (r + 150), 1.0, pal["mute"], 0.45)
        cv.circle(cx, cy, r, pal["accent"], 0.95)
        cv.ring(cx, cy, r + 26, 1.4, pal["ink"], 0.45)
        cv.ring(cx, cy, r + 60 + 40 * pulse, 1.0, pal["ink"], 0.22 + 0.3 * pulse)
        cv.knock = (cx, cy, r, pal["paper"])
        if band:
            snare = self.s.since(self.s.snare, t, 0.5)
            if snare is not None:                              # snare: bars sweep across
                k = snare / 0.5
                for i in range(3):
                    cv.rect((k * 1.5 - 0.25 + i * 0.16) * W, H * 0.5, 22, H * 1.7, pal["accent2"], 0.18 * (1 - k), angle=0.5)
            crash = self.s.since(self.s.crash, t, 1.2)
            if crash is not None:
                cv.ring(cx, cy, r + 80 + 520 * ease_out(crash / 1.2), 2.6, pal["ink"], 0.32 * (1 - crash / 1.2))
            self.guitar_strokes(cv, t, pal)
        for s0, s1, p in self.s.bass:                          # bass notes tick along the floor
            if a <= s0 <= t < s0 + 0.6:
                k = (t - s0) / 0.6
                x = 160 + ((s0 - a) % 6.0) / 6.0 * (W - 320)
                cv.circle(x, 1000 - (p - 28) * 4, 5 * (1 - k) + 2, pal["ink"], 0.55 * (1 - k))

    def guitar_strokes(self, cv, t, pal):
        for i, (s0, s1, p) in enumerate(self.s.gtr):
            if not (s0 <= t < s1 + 0.9):
                continue
            k = clamp01((t - s0) / max(0.05, s1 - s0))
            y = 1000 - (p - 60) * 20
            x0 = 1060 + (i % 4) * 60
            pts = []
            for j in range(int(3 + 22 * k)):
                st = s0 + j / 24 * (s1 - s0)
                pts.append((x0 + j / 24 * 640, y - float(np.interp(st, self.s.bend_t, self.s.bend_v)) * 20))
            if len(pts) > 1:
                cv.polyline(pts, 2.4 if pal["light"] else 3.0, pal["ink"], 0.7 * (1 - clamp01((t - s1) / 0.9)),
                            glow=0 if pal["light"] else 4)

    def trace(self, cv, t, notes, col, pal, base_y, scale, width, window=5.0, px=260.0, sparks=False, glide=0.35):
        """A melody as one continuous, smoothed line scrolling right to left; the head glows."""
        times = np.arange(t - window, t, 1 / 60)
        pitch = np.full(len(times), np.nan)
        for s0, s1, p in notes:
            if s1 < t - window - 0.5 or s0 > t:
                continue
            sel = (times >= s0) & (times < s1 + 0.06)
            pitch[sel] = p
        if np.isnan(pitch).all():
            return
        bend = np.interp(times, self.s.bend_t, self.s.bend_v) if notes is self.s.gtr else 0.0
        y = base_y - (pitch + bend - 64) * scale
        # glide: a short one-pole smoothing, restarted after every gap
        sm, out = None, []
        for tt, yy in zip(times, y):
            if np.isnan(yy):
                if len(out) > 1:
                    cv.polyline(out, width, col, 0.9, glow=5, fade_tail=True)
                sm, out = None, []
                continue
            sm = yy if sm is None else sm + (yy - sm) * glide
            out.append((W * 0.74 - (t - tt) * px, sm + 4 * math.sin(tt * 9.0) * (notes is self.s.violin)))
        if len(out) > 1:
            cv.polyline(out, width, col, 0.9, glow=5, fade_tail=True)
            cv.circle(out[-1][0], out[-1][1], 8, col, 1.0, glow=10)
        if sparks:
            for i, (s0, s1, p) in enumerate(notes):
                if s0 <= t < s0 + 0.8:
                    age = (t - s0) / 0.8
                    hx = W * 0.74 - (t - s0) * px
                    hy = base_y - (p - 64) * scale
                    rnd = random.Random(i)
                    for _ in range(7):
                        ang, sp = rnd.uniform(0, 6.3), rnd.uniform(60, 180)
                        cv.circle(hx + math.cos(ang) * sp * age, hy + math.sin(ang) * sp * age, 2.2 * (1 - age),
                                  col, 0.9 * (1 - age))

    def folders(self, cv, t, a, b, pal, drift=False, pulse=0.0):
        k = ease(ramp(t, a, a + 2.0))
        prog = (t - a) / (b - a)
        for i in range(5):
            for j in range(3):
                cx, cy, ang, op = 1060 + i * 160, 300 + j * 200, 0.0, 1.0
                if drift:                                      # the room empties: the folders drift away
                    rnd = random.Random(i * 7 + j)
                    d = ease(clamp01(prog * 1.3 - rnd.random() * 0.3))
                    cx += rnd.uniform(-1, 1) * 260 * d
                    cy += rnd.uniform(-1, 1) * 150 * d + 130 * d
                    ang, op = rnd.uniform(-1, 1) * 0.9 * d, 1 - 0.85 * d
                center = i == 2 and j == 1
                col = pal["accent2"] if center else pal["mute"]
                ca, sa = math.cos(ang), math.sin(ang)
                cv.rect(cx, cy, 116, 80, col, 0.7 * k * op, angle=ang, stroke=1.6)
                tx, ty = -32, -46                                # the folder tab
                cv.rect(cx + tx * ca - ty * sa, cy + tx * sa + ty * ca, 46, 14, col, 0.7 * k * op, angle=ang, stroke=1.4)
                if center:
                    glow = 0.22 + 0.12 * math.sin(t * 2.2) + 0.3 * pulse
                    cv.rect(cx, cy, 116, 80, col, glow * k * op, angle=ang)
        if not drift:                                          # days falling past
            for n in range(12):
                rnd = random.Random(n)
                x = rnd.uniform(960, W - 80)
                y = (t * 200 * rnd.uniform(0.7, 1.3) + rnd.uniform(0, H)) % (H + 80) - 40
                cv.line(x, y, x, y + 54, 1.0, pal["mute"], 0.35 * k)

    def walls(self, cv, t, a, b, pal):
        h = 70 + 160 * ease((t - a) / (b - a))
        cv.rect(W / 2, h / 2, W, h, pal["mute"], 0.32)
        cv.rect(W / 2, H - h / 2, W, h, pal["mute"], 0.32)
        cv.line(0, h, W, h, 1.4, pal["accent"], 0.7)
        cv.line(0, H - h, W, H - h, 1.4, pal["accent"], 0.7)

    def solo(self, cv, t, a, b, pal, pulse):
        self.trace(cv, t, self.s.gtr, pal["accent"], pal, base_y=640, scale=19, width=4, sparks=True)
        for s0, s1, p in self.s.bass:                          # the bass sixteenths as a dotted line
            if t - 2.2 <= s0 <= t and s0 >= a:
                cv.circle(W * 0.74 - (t - s0) * 260, 1000 - (p - 28) * 5, 3.2, pal["accent2"], 0.85)
        kick = self.s.since(self.s.kick, t, 0.6)
        if kick is not None:
            cv.ring(W * 0.74, 640, 30 + 320 * ease_out(kick / 0.6), 2.0, pal["accent"], 0.45 * (1 - kick / 0.6))
        crash = self.s.since(self.s.crash, t, 1.2)
        if crash is not None:
            for i in range(24):                                # a burst on the crash
                ang = i / 24 * 2 * math.pi
                r0, r1 = 120 + 600 * ease_out(crash / 1.2), 160 + 700 * ease_out(crash / 1.2)
                cv.line(W * 0.74 + math.cos(ang) * r0, 640 + math.sin(ang) * r0,
                        W * 0.74 + math.cos(ang) * r1, 640 + math.sin(ang) * r1, 1.6, pal["ink"], 0.5 * (1 - crash / 1.2))

    # --- petals
    def petals_draw(self, cv, t, pal):
        col = pal["petal"]
        for p in self.petals:
            age = t - p["t0"]
            if not (0 <= age <= p["life"]):
                continue
            x = p["x"] + p["vx"] * age + 40 * math.sin(age * p["sway"])
            y = -40 + p["vy"] * age
            op = clamp01(age / 0.6) * clamp01((p["life"] - age) / 1.0)
            cv.petal(x, y, p["size"], p["rot"] + p["spin"] * age, col, 0.8 * op)

    # --- lyrics
    def lyrics(self, cv, t, pal):
        for L in self.lines:
            if t < L["times"][0] - 0.35 or t > L["out"] + 0.6:
                continue
            out_k = ramp(t, L["out"], L["out"] + 0.6)
            for i, (ch, x, y, font, size, vertical) in enumerate(L["chars"]):
                k = ease_out((t - L["times"][i] + 0.20) / 0.30)       # all but there when it is sung
                if k <= 0:
                    continue
                sp, pad = TYPE.sprite(font, size, ch)
                dx, dy = (size * 0.12, -size * 0.18) if ch in Type.SMALL and vertical else (0, 0)
                lift = 18 * (1 - k) + 14 * ease(out_k)
                hl = L["hl"][i] and pal is not PALETTES["mono"]
                cv.glyph(sp, x - pad + dx, y - pad + dy - lift, pal["accent"] if hl else pal["ink"], k * (1 - out_k))
            zx, zy, align = L["zh"]
            zk = ease_out((t - L["times"][0] - 0.4) / 0.6) * (1 - out_k)
            TYPE.text(cv, ZH, 30, L["ln"]["zh"], zx, zy, pal["mute"] if pal is not PALETTES["mono"] else pal["accent2"],
                      0.95 * zk, align=align)

    def furniture(self, cv, t, name, pal):
        """Small typographic details: title mark, time, section, rules."""
        op = 0.55 * ramp(t, 11.0, 12.5) * (1 - ramp(t, self.s.end, self.s.end + 1.0))
        if op <= 0:
            return
        TYPE.text(cv, LATIN, 20, "MADANE", 60, 48, pal["ink"], op, spacing=4)
        TYPE.text(cv, LATIN, 20, f"{int(t // 60):02d}:{int(t % 60):02d}", 60, 1012, pal["ink"], op, spacing=4)
        TYPE.text(cv, GOTHIC, 20, name, W - 60, 46, pal["ink"], op, spacing=2, align="right")
        cv.line(60, 84, 260, 84, 1.0, pal["ink"], op * 0.8)
        prog = min(1.0, t / self.s.end)
        cv.line(160, 1024, 160 + 400 * prog, 1024, 1.2, pal["accent"], op)
        cv.line(160 + 400 * prog, 1024, 560, 1024, 1.0, pal["ink"], op * 0.3)

    CREDITS = ["まだね", "vocal   初音ミク V4X", "music, arrangement & video   Claude",
               "piano   Salamander Grand Piano — Alexander Holm (CC-BY 3.0)",
               "drums   MuldjordKit — Lars Muldjord (CC-BY 4.0)",
               "orchestra   VSCO-2 Community Edition (CC0)    guitar & bass   FreePats (CC0)"]

    def ending(self, cv, t, pal):
        last = self.lines[-1]
        if t < last["ln"]["end"]:
            return
        x = last["chars"][-1][1] + TYPE.width(MINCHO, last["chars"][-1][4], last["chars"][-1][0]) + 14
        y = last["chars"][-1][2] + 18
        if int((t - last["ln"]["end"]) * 2.2) % 2 == 0:            # the session goes on
            cv.rect(x, y + 50, 6, 100, pal["accent"], 0.9)
        c0 = last["ln"]["end"] + 1.5
        for i, line in enumerate(self.CREDITS):
            k = ease_out(ramp(t, c0 + i * 0.35, c0 + i * 0.35 + 0.8))
            font = MINCHO if i == 0 else LATIN
            size = 34 if i == 0 else 19
            parts = line.split("初音ミク")
            xx = 120
            for j, part in enumerate(parts):
                TYPE.text(cv, font, size, part, xx, 800 + i * 34 + (0 if i else -12), pal["ink"] if i == 0 else pal["mute"],
                          0.9 * k, spacing=1)
                xx += sum(TYPE.width(font, size, ch) + 1 for ch in part)
                if j < len(parts) - 1:
                    TYPE.text(cv, GOTHIC, size, "初音ミク", xx, 800 + i * 34 - 2, pal["mute"], 0.9 * k)
                    xx += TYPE.width(GOTHIC, size, "初音ミク")

    def title(self, cv, t, pal):
        if t >= 11.8:
            return
        k = 1 - ramp(t, 10.4, 11.8)
        x = 200
        for i, ch in enumerate("まだね"):
            kk = ease_out(ramp(t, 5.0 + i * 0.35, 6.2 + i * 0.35))
            sp, pad = TYPE.sprite(MINCHO, 180, ch)
            cv.glyph(sp, x - pad, 380 - pad - 20 * (1 - kk), pal["ink"], kk * k)
            x += TYPE.width(MINCHO, 180, ch)
        sub = ramp(t, 7.0, 8.0) * k
        x = TYPE.width(LATIN, 30, "feat. ")
        TYPE.text(cv, LATIN, 30, "feat. ", 206, 640, pal["accent"], sub, spacing=2)
        TYPE.text(cv, GOTHIC, 30, "初音ミク", 206 + x + 12, 636, pal["accent"], sub, spacing=2)
        cv.line(206, 700, 206 + 340 * ease_out(ramp(t, 7.2, 8.6)), 700, 1.0, pal["accent"], 0.8 * k)


_R = None


def _init(audio_s):
    global _R
    _R = PV(audio_s)


def _render(k):
    return _R.frame(k)


def main():
    if sys.argv[1] == "--stills":
        audio, outdir, times = sys.argv[2], Path(sys.argv[3]), [float(x) for x in sys.argv[4:]]
        outdir.mkdir(parents=True, exist_ok=True)
        r = PV(soundfile.info(audio).duration)
        for t in times:
            img = np.frombuffer(r.frame(int(t * FPS)), np.uint8).reshape(H, W, 3)
            Image.fromarray(img).save(outdir / f"lyric_{t:06.1f}.jpg", quality=92)
        print("stills written to", outdir)
        return
    audio, out = sys.argv[1], Path(sys.argv[2])
    audio_s = soundfile.info(audio).duration
    frames = int((audio_s + TAIL) * FPS)
    silent = out.with_name(out.stem + "_video.mp4")
    log = out.with_suffix(".log")
    # 1) picture only; 2) the audio is muxed in afterwards (padded with silence to the picture's length)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "faster", "-crf", "20",
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
