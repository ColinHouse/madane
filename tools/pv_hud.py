"""まだね PV — the view from inside the screen (a soft cyber-HUD).

The song is someone talking to Miku through an editor. This video is the
other side of that screen: the piano roll she is sung from, the parameters
drawn for her, and the clock of the person who comes — and stops coming — at
2 a.m. Everything moves on the real song data (notes, curves, sections).
After the music ends the session asks whether to close; the answer is まだね.

    python -I tools/pv_hud.py <mix.wav> <out.mp4>
    python -I tools/pv_hud.py --stills <mix.wav> <dir> t1 t2 ...
"""
import datetime as dt
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
import expression
import madane
import music
import pv

W, H, FPS = 1920, 1080, 30
TAIL = 7.5                       # seconds of picture after the audio: the closing dialog
UF = Path.home() / "AppData/Local/Microsoft/Windows/Fonts"
MONO = str(UF / "JetBrainsMono-Regular.ttf")
MONO_B = str(UF / "JetBrainsMono-Bold.ttf")
JP = r"C:\Windows\Fonts\YuGothM.ttc"
JP_B = r"C:\Windows\Fonts\YuGothB.ttc"
ZH = r"C:\Windows\Fonts\msyhl.ttc"

BG = (5, 8, 14)
TEAL = (57, 197, 187)                 # Miku's colour
TEAL_HI = (150, 255, 240)
PINK = (255, 150, 192)
PINK_HI = (255, 205, 226)
AMBER = (255, 196, 110)
WHITE = (232, 244, 248)
GREY = (120, 136, 146)
LAVENDER = (190, 170, 255)

ROLL_X0, ROLL_X1, ROLL_Y0, ROLL_Y1 = 260, 1860, 250, 650
PLAY_X, PX_PER_S = 700, 165
P_LO, P_HI = 50, 90
DYN_Y0, DYN_Y1 = 664, 716
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def pitch_y(p):
    return ROLL_Y1 - (p - P_LO) / (P_HI - P_LO) * (ROLL_Y1 - ROLL_Y0)


def x_at(s, t):
    return PLAY_X + (s - t) * PX_PER_S


def name_of(p):
    return f"{NOTE_NAMES[int(p) % 12]}{int(p) // 12 - 1}"


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ramp(t, a, b):
    return clamp01((t - a) / (b - a)) if b != a else float(t >= a)


def text_mixed(g, xy, text, latin, japanese, fill):
    """Draw text whose Japanese runs need a different font from its ASCII runs."""
    x, y = xy
    runs, cur, cur_jp = [], "", None
    for ch in text:
        jp = ord(ch) > 0x2000
        if cur and jp != cur_jp:
            runs.append((cur, cur_jp))
            cur = ""
        cur, cur_jp = cur + ch, jp
    if cur:
        runs.append((cur, cur_jp))
    for run, jp in runs:
        font = japanese if jp else latin
        g.text((x, y - (3 if jp else 0)), run, font=font, fill=fill)
        x += font.getlength(run)
    return x


# --- song data -----------------------------------------------------------------
class Data:
    def __init__(self):
        marks, parts, chords, hook, bars = music.layout(madane.SECTIONS)
        s = build.seconds
        self.song_end = s(bars * music.BAR)
        self.secs = [(m.name, s(m.start), s(m.start + m.bars * music.BAR), m.feel) for m in marks]
        self.start = {name: a for name, a, _, _ in self.secs}
        self.feel = {name: feel for name, _, _, feel in self.secs}
        self.vocal, self.phrase_starts, dyn, cents = [], [], [], []
        for sec in build.sung_sections(parts):
            for ph in expression.phrases(sec["notes"]):
                self.vocal += [(s(n.start), s(n.start + n.length), n.pitch, n.lyric) for n in ph]
                self.phrase_starts.append(s(ph[0].start))
            for corners in sec["dyn"]:
                dyn += [(s(t), v) for t, v in corners]
            cents += [(s(t), c) for t, c in sec["cents"]]
        self.vocal.sort()
        dyn.sort()
        cents.sort()
        self.dyn_t, self.dyn_v = np.array([p[0] for p in dyn]), np.array([p[1] for p in dyn])
        self.cent_t, self.cent_v = np.array([p[0] for p in cents]), np.array([p[1] for p in cents])
        self.hook = [(s(n.start), s(n.start + n.length), n.pitch) for n in hook]
        song = arrangement.Song(marks, chords, [], [x.get("transpose", 0) for x in madane.SECTIONS], madane.BPM)
        gtr, bends = arrangement.lead_guitar(song, madane.GUITAR_LEAD)
        bends = sorted(bends)
        self.gtr = []                                   # (start, end, pitch, bend times, bend semitones)
        for n in gtr:
            pts = [(s(t), v) for t, v in bends if n.start <= t <= n.start + n.length]
            self.gtr.append((s(n.start), s(n.start + n.length), n.pitch,
                             np.array([p[0] for p in pts]), np.array([p[1] for p in pts])))
        _, self.lines = pv.timeline()
        quote = next(ln for ln in self.lines if "「あ」" in ln["jp"])
        self.first_a = next(a for a, _, _, syl in self.vocal if syl == "あ" and a >= quote["onsets"][0])

    def section(self, t):
        for sec in self.secs:
            if sec[1] <= t < sec[2]:
                return sec
        return self.secs[-1]

    def dyn_at(self, t):
        return float(np.interp(t, self.dyn_t, self.dyn_v))

    def cents_at(self, t):
        return np.interp(t, self.cent_t, self.cent_v, left=0, right=0)

    def near(self, t):
        """The few vocal notes around time t (binary search on end times)."""
        v = self.vocal
        lo, hi = 0, len(v)
        while lo < hi:
            mid = (lo + hi) // 2
            if v[mid][1] < t - 0.2:
                lo = mid + 1
            else:
                hi = mid
        return v[lo:lo + 3]


# --- story: clock, status, how much HUD survives ----------------------------------
BASE = dt.datetime(2026, 4, 1, 2, 0, 0)
RETURN_DAYS = 731                      # 2サビ: the producer comes back, two springs later
GONE_RATE = 6.4                        # Cメロ: days away grow as (seconds into the section) ** 1.6 * rate
RESTORE = dt.datetime(2031, 4, 1, 2, 0, 0)


def clock(d, t):
    name, a, b, _ = d.section(t)
    if name in ("2A", "2B"):                       # days rush past while the folder stays shut
        days = int((t - d.start["2A"]) / (d.start["2サビ"] - d.start["2A"]) * RETURN_DAYS)
        when = BASE + dt.timedelta(days=days, minutes=random.Random(int(t * 3)).randint(0, 59))
        hidden = int(t * 2) % 5 == 0
        return when.strftime("%Y.%m.%d"), "--:--:--" if hidden else when.strftime("%H:%M:%S"), \
            "IDLE", f"LAST OPENED  {days}d ago"
    if name in ("2サビ", "Solo"):
        when = BASE + dt.timedelta(days=RETURN_DAYS, seconds=t - d.start["2サビ"])
        return when.strftime("%Y.%m.%d"), when.strftime("%H:%M:%S"), "ONLINE", "SESSION  resumed"
    if name == "Cメロ":
        gone = int((t - a) ** 1.6 * GONE_RATE)
        when = BASE + dt.timedelta(days=RETURN_DAYS + gone)
        return when.strftime("%Y.%m.%d"), "--:--:--", "OFFLINE", f"LAST ONLINE  {gone:,}d ago"
    if name == "落ちサビ":
        return "----.--.--", "--:--:--", "ARCHIVED", "WAITING"
    if t >= d.start["ラスサビ"]:
        when = RESTORE + dt.timedelta(seconds=t - d.start["ラスサビ"])
        return when.strftime("%Y.%m.%d"), when.strftime("%H:%M:%S"), "ONLINE", "SESSION  restored"
    when = BASE + dt.timedelta(seconds=t)
    return when.strftime("%Y.%m.%d"), when.strftime("%H:%M:%S"), "ONLINE", f"SESSION  {int(t)//60:02d}:{int(t)%60:02d}"


def hud_alpha(d, t):
    """How much of the interface is visible."""
    name, a, b, _ = d.section(t)
    if t < 12:
        return ramp(t, 9.5, 12.0)
    if name == "Cメロ":                               # the room empties: panels flicker out
        fade = 1 - 0.75 * ramp(t, a + 12, b)
        flick = 0.35 if random.Random(int(t * 12)).random() < 0.08 + 0.25 * ramp(t, a + 16, b) else 1.0
        return fade * flick
    if name == "落ちサビ":
        return 0.25 * (1 - ramp(t, a, a + 0.6))
    if name == "ラスサビ":
        return ramp(t, a, a + 0.8)
    if name == "Outro":
        return 1 - 0.6 * ramp(t, a, a + 3)
    return 1.0


def mono_amount(d, t):
    """落ちサビ fades to monochrome: only the voice is left."""
    a, b = d.start["落ちサビ"], d.start["ラスサビ"]
    return ramp(t, a, a + 1.5) * (1 - ramp(t, b - 0.05, b))


# --- static layers -------------------------------------------------------------------
def background():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.zeros((H, W, 3), np.float32) + np.array(BG, np.float32)
    glow = np.exp(-(((xx - W * 0.42) / (W * 0.55)) ** 2 + ((yy - H * 0.45) / (H * 0.6)) ** 2))
    img += glow[..., None] * np.array((10, 26, 32), np.float32)
    grid = ((xx % 48) < 1) | ((yy % 48) < 1)
    img[grid] += np.array((7, 16, 20), np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def finish_mask():
    """Vignette x scanlines, applied to every final frame (0..256 scale)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = 1 - 0.5 * np.clip(np.hypot((xx / W - 0.5) / 0.7, (yy / H - 0.5) / 0.7) - 0.35, 0, 1)
    scan = 1 - 0.07 * ((np.arange(H) % 3) == 0)[:, None]
    return (vig * scan * 256).astype(np.uint16)[..., None]


def audio_features(path):
    """Per-frame spectrum bands and loudness (computed once, shared with the workers)."""
    x, sr = soundfile.read(path, always_2d=True)
    mono = x.mean(axis=1)
    hop = sr // FPS
    n = len(mono) // hop
    rms = np.sqrt((mono[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    return pv.spectrum_frames(mono, sr), rms / (np.percentile(rms, 98) + 1e-9), len(mono) / sr


# --- renderer ------------------------------------------------------------------------
class HUD:
    def __init__(self, spec, level, audio_s):
        self.d = Data()
        self.spec, self.level, self.audio_s = spec, level, audio_s
        self.bg = background()
        grey = self.bg.mean(axis=2, keepdims=True)
        self.bg_grey = np.repeat(grey, 3, axis=2).astype(np.uint8)
        self.mask = finish_mask()
        f = ImageFont.truetype
        self.f = dict(mono14=f(MONO, 14), mono16=f(MONO, 16), mono18=f(MONO, 18), mono22=f(MONO, 22),
                      monob20=f(MONO_B, 20), monob28=f(MONO_B, 28), syl=f(JP, 15), syl26=f(JP, 26),
                      jp50=f(JP, 50), jp36=f(JP, 36), jp76=f(JP_B, 76), title=f(JP_B, 168), big_a=f(JP_B, 380),
                      zh24=f(ZH, 24), zh30=f(ZH, 30), dlg=f(JP, 34), btn=f(JP_B, 30), sec=f(JP_B, 26),
                      jp20=f(JP, 20), jp24=f(JP, 24))
        self.petals = self._petals()

    # sakura: each note in a chorus (voice, guitar, piano hook) releases petals at the playhead
    def _petals(self):
        rng = random.Random(3)
        per = {"1サビ": 3, "2サビ": 4, "ラスサビ": 6, "Solo": 3, "Intro B": 2, "間奏": 2, "落ちサビ": 1}
        sources = [(a, p, False) for a, _, p, _ in self.d.vocal] + [(g[0], g[2], True) for g in self.d.gtr] + \
                  [(a, p, False) for a, _, p in self.d.hook]
        out = []
        for a, p, gold in sources:
            name = self.d.section(a)[0]
            for _ in range(per.get(name, 0)):
                out.append(dict(t0=a, y0=pitch_y(p), vx=rng.uniform(-150, -50), vy=rng.uniform(-60, 45),
                                life=rng.uniform(2.2, 4.2), rot=rng.uniform(0, 6.28), spin=rng.uniform(-4, 4),
                                size=rng.uniform(6, 13), slow=name == "落ちサビ", gold=gold))
        return out

    def frame(self, k):
        t = k / FPS
        d = self.d
        name, a, b, feel = d.section(t)
        accent = AMBER if name == "Cメロ" else WHITE if name == "落ちサビ" else TEAL
        hud = hud_alpha(d, t) if t < d.song_end else 0.0
        lvl = float(self.level[min(k, len(self.level) - 1)]) if t < self.audio_s else 0.0
        mono = mono_amount(d, t)
        bg = self.bg if mono <= 0 else self.bg_grey if mono >= 1 else \
            (self.bg * (1 - mono) + self.bg_grey * mono).astype(np.uint8)
        base = Image.fromarray(bg).convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g = ImageDraw.Draw(ov, "RGBA")

        roll = ramp(t, 9.0, 12.0)
        if name == "落ちサビ":
            roll = 0.85
        if t >= d.start["Outro"]:
            roll *= 1 - 0.75 * ramp(t, d.start["Outro"], d.start["Outro"] + 3)
        self._roll(g, t, roll, hud, accent, mono > 0.5)
        self._petals_draw(g, t)
        if hud > 0.01:
            self._panels(g, t, k, hud, accent, name, lvl)
        self._lyrics(g, t, mono > 0.5)
        self._story(g, t, name)
        base.alpha_composite(ov)
        arr = np.asarray(base.convert("RGB")).copy()

        # glitches: a light tick at section seams, the emptying room, the restore
        burst = 0.0
        for _, sa, _, _ in d.secs[2:]:
            if 0 <= t - sa < 0.15:
                burst = max(burst, 0.35 * (1 - (t - sa) / 0.15))
        if name == "Cメロ":
            r = random.Random(k)
            if r.random() < 0.05 + 0.3 * ramp(t, a + 16, b):
                burst = max(burst, r.uniform(0.4, 1.0))
        if name == "ラスサビ" and t - a < 0.7:
            flash = 1 - (t - a) / 0.7
            arr = np.clip(arr.astype(np.int16) + int(110 * flash), 0, 255).astype(np.uint8)
            burst = max(burst, flash)
        if burst > 0:
            arr = self._glitch(arr, k, burst)
        sh = 1 + int(2 * burst)                                     # chromatic fringe
        out = arr.copy()
        out[:, sh:, 0] = arr[:, :-sh, 0]
        out[:, :-sh, 2] = arr[:, sh:, 2]
        out = (out.astype(np.uint16) * self.mask >> 8).astype(np.uint8)
        end = self.audio_s + TAIL
        if t > end - 1.8:
            out = (out * clamp01((end - t) / 1.8)).astype(np.uint8)
        return out.tobytes()

    @staticmethod
    def _glitch(arr, k, amount):
        r = random.Random(k * 7 + 1)
        out = arr.copy()
        for _ in range(int(3 + 9 * amount)):
            y = r.randrange(0, H - 40)
            hgt = r.randrange(4, 38)
            out[y:y + hgt] = np.roll(arr[y:y + hgt], int(r.uniform(-60, 60) * amount), axis=1)
        if amount > 0.5:
            out[..., 1] = np.roll(out[..., 1], int(4 * amount), axis=0)
        return out

    # --- piano roll -------------------------------------------------------------
    def _roll(self, g, t, A, hud, accent, mono):
        if A <= 0.01:
            return
        d, f = self.d, self.f
        bar = 4 * 60 / madane.BPM
        t0, t1 = t - (PLAY_X - ROLL_X0) / PX_PER_S, t + (ROLL_X1 - PLAY_X) / PX_PER_S
        grid_a = int(55 * A * max(hud, 0.25))
        for i in range(int(t0 / bar), int(t1 / bar) + 2):        # bars and beats
            for j in range(4):
                x = x_at(i * bar + j * bar / 4, t)
                if ROLL_X0 <= x <= ROLL_X1:
                    g.line([(x, ROLL_Y0), (x, ROLL_Y1)], fill=accent + (grid_a if j == 0 else grid_a // 3,))
                    if j == 0 and hud > 0.05:
                        g.text((x + 4, ROLL_Y0 + 4), f"{i + 1:03d}", font=f["mono14"], fill=GREY + (int(140 * A * hud),))
        for p in range(P_LO, P_HI + 1):
            if p % 12 == 0:
                y = pitch_y(p)
                g.line([(ROLL_X0, y), (ROLL_X1, y)], fill=accent + (grid_a // 2,))
                if hud > 0.05:
                    g.text((ROLL_X0 - 40, y - 9), name_of(p), font=f["mono14"], fill=GREY + (int(150 * A * hud),))
        g.rectangle([ROLL_X0, ROLL_Y0, ROLL_X1, ROLL_Y1], outline=accent + (int(90 * A * max(hud, 0.3)),))

        # breath marks between phrases ("I drew even the places you breathe")
        br_hi = d.start["1B"] + 6 <= t < d.start["1B"] + 12.5
        for s in d.phrase_starts:
            x = x_at(s - 0.19, t)
            if ROLL_X0 < x < ROLL_X1:
                c = PINK if br_hi else GREY
                g.text((x - 10, ROLL_Y1 - 26), "BR", font=f["mono14"], fill=c + (int((230 if br_hi else 110) * A),))
                g.arc([x - 7, ROLL_Y1 - 46, x + 7, ROLL_Y1 - 32], 200, 340, fill=c + (int(160 * A),), width=2)
        for s0, s1, p in d.hook:                                  # the piano / music-box hook
            self._note(g, t, s0, s1, p, LAVENDER, A * 0.85)
        for s0, s1, p, bt, bv in d.gtr:                           # the lead guitar, with its bends
            self._note(g, t, s0, s1, p, PINK, A, curve=(bt, bv) if len(bt) > 1 else None)
        col_v = WHITE if mono else accent
        for s0, s1, p, lyric in d.vocal:
            self._note(g, t, s0, s1, p, col_v, A, lyric, vibrato=True)
        g.line([(PLAY_X, ROLL_Y0 - 14), (PLAY_X, ROLL_Y1 + 6)], fill=TEAL_HI + (int(220 * A),), width=2)
        g.polygon([(PLAY_X - 7, ROLL_Y0 - 22), (PLAY_X + 7, ROLL_Y0 - 22), (PLAY_X, ROLL_Y0 - 12)],
                  fill=TEAL_HI + (int(220 * A),))
        if hud > 0.05:
            beat = (t % bar) / (bar / 4)
            g.text((PLAY_X + 10, ROLL_Y0 - 30), f"{int(t // bar) + 1:03d}.{int(beat) + 1}.{int((beat % 1) * 4) + 1}",
                   font=f["mono16"], fill=TEAL_HI + (int(200 * A * hud),))
        if hud > 0.05 and not mono:                               # the dynamics lane, drawn while she sings
            pts = []
            for x in range(ROLL_X0, ROLL_X1 + 1, 8):
                s = t + (x - PLAY_X) / PX_PER_S
                singing = any(n[0] - 0.05 <= s <= n[1] + 0.1 for n in d.near(s))
                y = DYN_Y1 - clamp01((d.dyn_at(s) - 30) / 60) * (DYN_Y1 - DYN_Y0) if singing else DYN_Y1
                pts.append((x, y))
            g.line(pts, fill=accent + (int(170 * A * hud),), width=2)
            g.text((ROLL_X0 - 52, DYN_Y0 + 14), "DYN", font=f["mono14"], fill=GREY + (int(160 * A * hud),))
            g.line([(ROLL_X0, DYN_Y1), (ROLL_X1, DYN_Y1)], fill=accent + (int(60 * A * hud),))

    def _note(self, g, t, s0, s1, p, col, A, lyric=None, vibrato=False, curve=None):
        x0, x1 = x_at(s0, t), x_at(s1, t)
        if x1 < ROLL_X0 or x0 > ROLL_X1:
            return
        x0, x1 = max(x0, ROLL_X0), min(x1, ROLL_X1)
        y = pitch_y(p)
        active, past = s0 <= t <= s1, s1 < t
        if active:
            g.rounded_rectangle([x0 - 2, y - 13, x1 + 2, y + 13], 5, fill=col + (int(60 * A),))
            g.rounded_rectangle([x0, y - 9, x1, y + 9], 4, fill=col + (int(235 * A),))
        elif past:
            g.rounded_rectangle([x0, y - 9, x1, y + 9], 4, fill=col + (int(80 * A),))
        else:
            g.rounded_rectangle([x0, y - 9, x1, y + 9], 4, outline=col + (int(200 * A),), width=2)
        if lyric and x1 - x0 > 14:
            g.text((x0 + 4, y - 9), lyric, font=self.f["syl"], fill=((10, 18, 22) if active else WHITE) + (int(230 * A),))
        if (vibrato or curve is not None) and (active or past):   # the drawn pitch curve, up to the playhead
            xs = np.arange(x0, min(x1, PLAY_X) + 1, 4.0)
            if len(xs) < 2:
                return
            secs = t + (xs - PLAY_X) / PX_PER_S
            semis = self.d.cents_at(secs) / 100 if vibrato else np.interp(secs, curve[0], curve[1])
            if np.abs(semis).max() < 0.03:                         # a held-straight note: nothing to draw
                return
            ys = y - semis * (ROLL_Y1 - ROLL_Y0) / (P_HI - P_LO)
            g.line(list(zip(xs.tolist(), ys.tolist())), fill=PINK_HI + (int(230 * A),), width=2)

    # --- panels -----------------------------------------------------------------
    def _panels(self, g, t, k, A, accent, name, lvl):
        d, f = self.d, self.f
        date, clk, status, sub = clock(d, t)
        g.line([(40, 86), (W - 40, 86)], fill=accent + (int(120 * A),))
        g.text((40, 40), "// VOICE.SESSION  madane.vpr", font=f["monob20"], fill=WHITE + (int(220 * A),))
        g.text((40, 64), "MIKU_V4X_Soft   80.00 BPM   D maj", font=f["mono14"], fill=GREY + (int(200 * A),))
        sec = f"[ {name} ]"
        g.text((W / 2 - f["sec"].getlength(sec) / 2, 44), sec, font=f["sec"], fill=accent + (int(230 * A),))
        g.text((W - 40 - f["monob28"].getlength(clk), 36), clk, font=f["monob28"], fill=WHITE + (int(230 * A),))
        st_col = {"ONLINE": TEAL_HI, "IDLE": GREY, "OFFLINE": AMBER, "ARCHIVED": GREY}.get(status, WHITE)
        lit = status != "OFFLINE" or int(t * 2) % 2 == 0
        txt = f"{date}   * {status}"
        g.text((W - 40 - f["mono16"].getlength(txt), 68), txt, font=f["mono16"], fill=st_col + (int(220 * A * lit),))
        g.text((W - 40 - f["mono14"].getlength(sub), 96), sub, font=f["mono14"], fill=GREY + (int(200 * A),))
        bands = self.spec[min(k, len(self.spec) - 1)] if t < self.audio_s else np.zeros(self.spec.shape[1])
        x0, y1 = 1480, 214
        for i in range(32):
            v = float(bands[int(i * len(bands) / 32)])
            g.rectangle([x0 + i * 11.5, y1 - 2 - v ** 1.4 * 76, x0 + i * 11.5 + 7, y1], fill=accent + (int(170 * A),))
        g.text((x0, y1 + 6), "SPECTRUM", font=f["mono14"], fill=GREY + (int(170 * A),))
        cur = next((n for n in d.near(t) if n[0] <= t <= n[1]), None)
        colour = build.VOICE_COLOR.get(d.feel[name], build.DEFAULT_COLOR)
        rows = [("NOTE", name_of(cur[2]) if cur else "--"), ("LYRIC", cur[3] if cur else "--"),
                ("PIT", f"{float(d.cents_at(t)) / 100:+.2f}"), ("DYN", f"{d.dyn_at(t):.0f}" if cur else "--"),
                ("BRE", str(colour["Breathiness"])), ("VEL", "64"), ("OPE", "127"), ("BPM", "80.00")]
        for i, (key, val) in enumerate(rows):
            y = ROLL_Y0 + 6 + i * 48
            g.text((40, y), key, font=f["mono14"], fill=GREY + (int(190 * A),))
            font = f["syl26"] if key == "LYRIC" and cur else f["monob20"]
            g.text((40, y + 16), val, font=font, fill=(TEAL_HI if key in ("NOTE", "LYRIC") else WHITE) + (int(230 * A),))
        for i, side in enumerate((0.96, 1.0)):
            hgt = clamp01(lvl * side) * 300
            g.rectangle([1880 + i * 12, ROLL_Y1 - hgt, 1888 + i * 12, ROLL_Y1], fill=accent + (int(170 * A),))
        y, span = 1018, W - 240
        g.line([(120, y), (W - 120, y)], fill=GREY + (int(110 * A),), width=2)
        g.line([(120, y), (120 + span * min(1.0, t / d.song_end), y)], fill=accent + (int(230 * A),), width=3)
        for _, sa, _, _ in d.secs:
            x = 120 + span * sa / d.song_end
            g.line([(x, y - 6), (x, y + 6)], fill=GREY + (int(160 * A),))
        total = int(d.song_end)
        g.text((120, y + 10), f"{int(t // 60):02d}:{int(t % 60):02d} / {total // 60:02d}:{total % 60:02d}",
               font=f["mono14"], fill=GREY + (int(200 * A),))

    # --- lyrics: typed by the singer's timing ----------------------------------------
    @staticmethod
    def _typed(ln, t):
        chars = list(ln["jp"])
        sung = [i for i, c in enumerate(chars) if c not in "　 「」"]
        ons = ln["onsets"]
        shown = 0
        for j, ci in enumerate(sung):
            if ons[min(len(ons) - 1, j * len(ons) // len(sung))] <= t:
                shown = ci + 1
        while 0 < shown < len(chars) and chars[shown] in "」　 ":   # closing marks come with their word
            shown += 1
        return "".join(chars[:shown]), shown >= len(chars)

    def _lyrics(self, g, t, mono):
        f, lines = self.f, self.d.lines
        cur = None
        for i, ln in enumerate(lines):
            if ln["onsets"][0] - 0.3 <= t:
                cur = i
        if cur is None:
            return
        ln = lines[cur]
        nxt = lines[cur + 1]["onsets"][0] - 0.3 if cur + 1 < len(lines) else 1e9
        fade = 1 - ramp(t, ln["end"] + 2.5, ln["end"] + 3.2) if t < nxt else 1.0
        if ln["section"] == "Outro":
            if t > ln["end"] + 0.9:                    # the dialog takes over
                fade *= 1 - ramp(t, ln["end"] + 0.9, ln["end"] + 1.4)
            text, done = self._typed(ln, t)
            x = W / 2 - f["jp76"].getlength(ln["jp"]) / 2
            g.text((x, 470), text, font=f["jp76"], fill=WHITE + (int(245 * fade),))
            if not done or int(t * 2.5) % 2 == 0:
                cx = x + f["jp76"].getlength(text) + 6
                g.rectangle([cx, 478, cx + 8, 552], fill=TEAL_HI + (int(230 * fade),))
            g.text((W / 2 - f["zh30"].getlength(ln["zh"]) / 2, 576), ln["zh"], font=f["zh30"],
                   fill=GREY + (int(220 * fade * ramp(t, ln["onsets"][0], ln["onsets"][0] + 1)),))
            return
        if cur > 0 and lines[cur - 1]["section"] == ln["section"]:     # the previous line, scrolled up
            a = int(120 * (1 - ramp(t, ln["onsets"][0] + 1.5, ln["onsets"][0] + 2.5)) * fade)
            if a > 0:
                g.text((200, 752), "  " + lines[cur - 1]["jp"], font=f["jp36"], fill=GREY + (a,))
        text, done = self._typed(ln, t)
        prompt = WHITE if mono else TEAL_HI
        g.text((200, 806), ">", font=f["jp50"], fill=prompt + (int(200 * fade),))
        g.text((246, 806), text, font=f["jp50"], fill=WHITE + (int(245 * fade),))
        if not done or int(t * 2.5) % 2 == 0:
            cx = 246 + f["jp50"].getlength(text) + 6
            g.rectangle([cx, 812, cx + 6, 862], fill=prompt + (int(220 * fade),))
        za = int(200 * fade * ramp(t, ln["onsets"][0] + 0.2, ln["onsets"][0] + 1.0))
        g.text((248, 878), ln["zh"], font=f["zh24"], fill=GREY + (za,))
        if ln["jp"].startswith("ごめんね") and text.startswith("ごめんね"):   # the word that won't come out right
            r = random.Random(int(t * 20))
            if r.random() < 0.5:
                g.text((246 + r.uniform(-4, 4), 806 + r.uniform(-3, 3)), "ごめんね", font=f["jp50"], fill=AMBER + (90,))

    # --- petals --------------------------------------------------------------------------
    def _petals_draw(self, g, t):
        for p in self.petals:
            age = t - p["t0"]
            if not (0 <= age <= p["life"]):
                continue
            sp = 0.35 if p["slow"] else 1.0
            x = PLAY_X + p["vx"] * age * sp
            y = p["y0"] + p["vy"] * age * sp + 18 * (age * sp) ** 2
            if not (ROLL_X0 - 80 < x < W and 0 < y < H):
                continue
            a = clamp01(age / 0.15) * (1 - age / p["life"])
            rot = p["rot"] + p["spin"] * age * sp
            s, flip = p["size"], 0.45 + 0.55 * abs(math.cos(rot * 0.7))
            pts = []
            for ang, rad in ((0, 1.0), (0.55, 0.62), (1.3, 0.3), (math.pi - 1.3, 0.3), (math.pi - 0.55, 0.62),
                             (math.pi, 1.0), (math.pi + 0.35, 0.75), (2 * math.pi - 0.35, 0.75)):
                px, py = math.cos(ang) * rad * s, math.sin(ang) * rad * s * flip
                pts.append((x + px * math.cos(rot) - py * math.sin(rot), y + px * math.sin(rot) + py * math.cos(rot)))
            g.polygon(pts, fill=((255, 214, 160) if p["gold"] else PINK_HI) + (int(200 * a),))

    # --- story beats --------------------------------------------------------------------
    def _story(self, g, t, name):
        f, d = self.f, self.d
        if t < 12.5:                                                   # boot
            boot = ["> voice.sys boot .................. ok", "> mount /projects/madane",
                    "> load voicebank  MIKU_V4X_Soft ...... ok", "> tempo 80.00   key D   bars 90",
                    "> 02:00 AM  - session start"]
            fade = 1 - ramp(t, 10.5, 12.3)
            for i, line in enumerate(boot):
                n = int(clamp01((t - 0.5 - i * 0.95) / 0.7) * len(line))
                if n:
                    g.text((64, 120 + i * 30), line[:n], font=f["mono18"], fill=(TEAL_HI if i == 4 else GREY) + (int(230 * fade),))
            if t >= 5.0:                                               # the title decodes
                title = "まだね"
                rng = random.Random(int(t * 24))
                pool = "アイウエオカキクケコサシスセソ01#%&ミクの声"
                solved = int(clamp01((t - 5.0) / 2.4) * len(title) + 0.001)
                text = title[:solved] + "".join(rng.choice(pool) for _ in range(len(title) - solved))
                a = int(250 * fade * ramp(t, 5.0, 5.6))
                g.text((W / 2 - f["title"].getlength(title) / 2, 300), text, font=f["title"], fill=WHITE + (a,))
                sub_w = f["mono22"].getlength("feat. ") + f["jp24"].getlength("初音ミク")
                text_mixed(g, (W / 2 - sub_w / 2, 520), "feat. 初音ミク", f["mono22"], f["jp24"],
                           TEAL_HI + (int(a * ramp(t, 7.4, 8.4)),))
        age = t - d.first_a                                            # the first sound she was given
        if -0.1 <= age <= 3.0:
            a = clamp01(age / 0.25) * (1 - clamp01((age - 1.6) / 1.4))
            grow = int(max(age, 0) * 10)
            g.text((1360 - grow, 230 - grow), "あ", font=f["big_a"], fill=TEAL + (int(70 * a),),
                   stroke_width=3, stroke_fill=TEAL_HI + (int(200 * a),))
            g.text((1380, 640), "> first sound", font=f["mono16"], fill=TEAL_HI + (int(220 * a),))
        if name == "1B" and d.start["1B"] + 6 <= t < d.start["1B"] + 12:
            g.text((ROLL_X1 - 300, ROLL_Y1 + 6), "breaths: drawn by hand", font=f["mono14"], fill=PINK + (200,))
        if name == "落ちサビ":
            msg = "( only the voice remains )"
            g.text((W / 2 - f["mono16"].getlength(msg) / 2, 186), msg, font=f["mono16"],
                   fill=GREY + (int(150 * ramp(t, d.start["落ちサビ"] + 1, d.start["落ちサビ"] + 3)),))
        if name == "ラスサビ" and t - d.start["ラスサビ"] < 4:
            msg = "> session restored   2031.04.01 02:00"
            a = int(220 * (1 - ramp(t, d.start["ラスサビ"] + 3, d.start["ラスサビ"] + 4)))
            g.text((W / 2 - f["mono18"].getlength(msg) / 2, 186), msg, font=f["mono18"], fill=TEAL_HI + (a,))
        if t >= d.start["Outro"]:
            self._ending(g, t)

    def _ending(self, g, t):
        f = self.f
        t_dlg = self.d.lines[-1]["end"] + 1.2           # once the last ね has faded
        if t < t_dlg:
            return
        a = ramp(t, t_dlg, t_dlg + 0.35)
        g.rectangle([0, 0, W, H], fill=(0, 0, 0, int(120 * a)))
        x0, y0, x1, y1 = W / 2 - 330, 420, W / 2 + 330, 660
        click = t_dlg + 4.2                              # the pointer hesitates at はい first
        closing = ramp(t, click + 0.35, click + 0.7)
        cx, cy = W / 2, (y0 + y1) / 2
        if closing < 1:
            sc = 1 - 0.15 * closing
            bx0, by0, bx1, by1 = cx + (x0 - cx) * sc, cy + (y0 - cy) * sc, cx + (x1 - cx) * sc, cy + (y1 - cy) * sc
            da = a * (1 - closing)
            g.rectangle([bx0, by0, bx1, by1], fill=(8, 16, 20, int(235 * da)), outline=TEAL + (int(230 * da),), width=2)
            g.rectangle([bx0, by0, bx1, by0 + 34], fill=TEAL + (int(70 * da),))
            g.text((bx0 + 14, by0 + 7), "SYSTEM", font=f["mono16"], fill=WHITE + (int(230 * da),))
            msg = "セッションを終了しますか？"
            g.text((cx - f["dlg"].getlength(msg) / 2 * sc, by0 + 62), msg, font=f["dlg"], fill=WHITE + (int(240 * da),))
            for label, bx in (("はい", cx - 160), ("まだね", cx + 160)):
                hover = label == "まだね" and t > click - 0.9
                pressed = label == "まだね" and click <= t < click + 0.3
                w = 190 * sc
                rect = [bx - w / 2, by1 - 86 * sc, bx + w / 2, by1 - 30 * sc]
                g.rectangle(rect, fill=TEAL + (int((240 if pressed else 110 if hover else 20) * da),),
                            outline=TEAL_HI + (int(220 * da),), width=2)
                g.text((bx - f["btn"].getlength(label) / 2, rect[1] + 10 * sc), label, font=f["btn"],
                       fill=((5, 10, 12) if pressed else WHITE) + (int(240 * da),))
            path = [(t_dlg + 0.4, (W / 2 + 420, 900)), (t_dlg + 1.4, (W / 2 - 150, y1 - 50)),
                    (t_dlg + 2.9, (W / 2 - 146, y1 - 52)), (click - 0.15, (W / 2 + 165, y1 - 52))]
            px, py = path[0][1]
            for (ta, pa), (tb, pb) in zip(path, path[1:]):
                if ta <= t:
                    u = clamp01((t - ta) / (tb - ta))
                    u = u * u * (3 - 2 * u)
                    px, py = pa[0] + (pb[0] - pa[0]) * u, pa[1] + (pb[1] - pa[1]) * u
            if t >= t_dlg + 0.4:
                g.polygon([(px, py), (px, py + 28), (px + 8, py + 21), (px + 14, py + 33), (px + 18, py + 31),
                           (px + 12, py + 19), (px + 22, py + 19)], fill=WHITE + (int(240 * da),), outline=(0, 0, 0, 200))
        if t >= click + 0.6:                                          # the session goes on; credits as a log
            log = ["// session continues", "// まだね", "// vocal     初音ミク V4X",
                   "// piano     Salamander Grand Piano - Alexander Holm (CC-BY 3.0)",
                   "// drums     MuldjordKit - Lars Muldjord (CC-BY 4.0)",
                   "// orchestra VSCO-2 CE (CC0)   guitar & bass  FreePats (CC0)",
                   "// arrangement, mix & video  Claude"]
            for i, line in enumerate(log):
                n = int(clamp01((t - click - 0.6 - i * 0.4) / 0.35) * len(line))
                if n:
                    text_mixed(g, (64, 720 + i * 34), line[:n], f["mono18"], f["jp20"],
                               (TEAL_HI if i < 2 else GREY) + (230,))
            if int(t * 2.5) % 2 == 0:
                g.rectangle([64, 722 + len(log) * 34, 76, 746 + len(log) * 34], fill=TEAL_HI + (230,))


_R = None


def _init(spec, level, audio_s):
    global _R
    _R = HUD(spec, level, audio_s)


def _render(k):
    return _R.frame(k)


def main():
    if sys.argv[1] == "--stills":
        audio, outdir, times = sys.argv[2], Path(sys.argv[3]), [float(x) for x in sys.argv[4:]]
        outdir.mkdir(parents=True, exist_ok=True)
        r = HUD(*audio_features(audio))
        for t in times:
            img = np.frombuffer(r.frame(int(t * FPS)), np.uint8).reshape(H, W, 3)
            Image.fromarray(img).save(outdir / f"hud_{t:06.1f}.jpg", quality=90)
        print("stills written to", outdir)
        return
    audio, out = sys.argv[1], sys.argv[2]
    spec, level, audio_s = audio_features(audio)
    frames = int((audio_s + TAIL) * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", audio, "-af", "apad", "-c:v", "libx264", "-preset", "faster",
           "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(6, initializer=_init, initargs=(spec, level, audio_s)) as pool:
        for k, buf in enumerate(pool.imap(_render, range(frames), chunksize=8)):
            enc.stdin.write(buf)
            if k % (FPS * 15) == 0:
                print(f"{k / FPS:6.1f}s / {frames / FPS:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("wrote", out)


if __name__ == "__main__":
    main()
