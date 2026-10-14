"""Lyric PV for まだね: night-sky palettes per section, falling sakura, karaoke lyrics.

    python -I tools/pv.py <audio.wav> <out.mp4>          full render
    python -I tools/pv.py --stills <audio.wav> <dir> t1 t2 ...   preview frames
"""
import math
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import soundfile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import build
import madane
import music

W, H, FPS = 1920, 1080, 30
FONTS = Path(r"C:\Windows\Fonts")
JP_FONT = str(FONTS / "yumindb.ttf")
JP_LIGHT = str(FONTS / "yuminl.ttf")
ZH_FONT = str(FONTS / "msyhl.ttc")

# Japanese line, Chinese translation — in singing order (two bars per line).
LYRICS = {
    "1A": [("午前二時の　青い光", "凌晨两点，屏幕的蓝光"),
           ("初めて鳴らした　「あ」の音", "第一次让你发出的那个“啊”"),
           ("頼りなく揺れた　その声を", "那个摇摇晃晃、怯生生的声音"),
           ("今もまだ　覚えているよ", "我到现在都还记得")],
    "1B": [("ひとつずつ　音符を並べて", "一个一个排好音符"),
           ("息継ぎの場所も　私が描いた", "连你换气的地方，都是我画上去的")],
    "1サビ": [("時の桜が　舞い落ちる", "时光的樱花飘落"),
             ("言えなかった想い　あなたが歌う", "我说不出口的心意，由你来唱"),
             ("「さよなら」は　重すぎるから", "“再见”太沉重了"),
             ("「またね」って　手を振るよ", "所以我挥挥手说“回头见”")],
    "2A": [("忙しさに　紛れた日々", "被忙碌淹没的日子里"),
           ("開かないままの　フォルダの中", "在那个一直没打开的文件夹里"),
           ("あなたは今も　同じ声で", "你还是用同样的声音"),
           ("私を待って　いたんだね", "一直在等我吧")],
    "2B": [("大人になるほど　夜が短くて", "越长大，夜晚越短"),
           ("ごめんねさえ　うまく言えない", "连一句“对不起”都说不好")],
    "2サビ": [("時の桜が　舞い落ちる", "时光的樱花飘落"),
             ("変わらない声で　あなたが歌う", "你用不曾改变的声音唱着"),
             ("「さよなら」は　まだ言えない", "“再见”我还说不出口"),
             ("来年も　ここで会おうね", "明年也在这里见面吧")],
    "Cメロ": [("いつか私が　来なくなっても", "就算有一天，我不再来这里"),
             ("あなたはきっと　ここで待つんだろう", "你一定还会在这里等着吧"),
             ("春が来るたび　あの日の声で", "每到春天，就用那天的声音"),
             ("誰もいない部屋で　歌うのかな", "在空无一人的房间里唱歌吗")],
    "落ちサビ": [("時の桜が　舞い落ちる", "时光的樱花飘落"),
               ("言えなかった想い　もう歌になった", "说不出口的心意，已经变成了歌"),
               ("私がいつか　いなくなっても", "就算有一天我不在了"),
               ("この声だけは　ここに残る", "只有这个声音会留在这里")],
    "ラスサビ": [("時の桜が　舞い落ちる", "时光的樱花飘落"),
               ("言えなかった想い　あなたが歌う", "我说不出口的心意，由你来唱"),
               ("「さよなら」は　重すぎるから", "“再见”太沉重了"),
               ("「またね」って　手を振るよ", "所以我挥挥手说“回头见”"),
               ("何度　春が巡っても", "不管春天轮回多少次")],
    "Outro": [("さよならは　まだね", "说再见？还早呢。")],
}
CREDITS = ["「まだね」", "Vocal　初音ミク V4X", "Piano　Salamander Grand Piano / Alexander Holm (CC-BY 3.0)",
           "Drums　MuldjordKit / Lars Muldjord (CC-BY 4.0)",
           "Strings　VSCO-2 Community Edition (CC0)", "Guitar & Bass　FreePats FSBS / FingerBassYR (CC0)"]

# palette: top, bottom, glow colour, glow centre, glow radius, screen-light strength, light rays
PALETTES = {
    "night":  ((9, 12, 30), (26, 38, 72), (110, 140, 215), (0.78, 0.22), 0.45, 0.60, 0.0),
    "sakura": ((26, 13, 44), (82, 40, 84), (242, 168, 200), (0.74, 0.26), 0.58, 0.18, 0.0),
    "lonely": ((11, 16, 30), (34, 46, 70), (140, 160, 200), (0.80, 0.20), 0.40, 0.50, 0.0),
    "solo":   ((30, 9, 18), (112, 38, 40), (255, 150, 110), (0.70, 0.30), 0.62, 0.10, 0.6),
    "violet": ((10, 6, 20), (46, 22, 62), (160, 110, 222), (0.76, 0.24), 0.50, 0.15, 0.0),
    "mono":   ((11, 11, 15), (38, 38, 46), (222, 222, 232), (0.76, 0.24), 0.40, 0.10, 0.0),
    "bright": ((46, 16, 54), (128, 62, 98), (255, 214, 226), (0.70, 0.22), 0.70, 0.12, 1.0),
    "outro":  ((7, 9, 22), (20, 28, 54), (100, 130, 200), (0.78, 0.22), 0.40, 0.45, 0.0),
}
SECTION_LOOK = {   # palette, petal count, petal speed
    "Intro": ("night", 14, 1.0), "Intro B": ("sakura", 56, 1.1), "1A": ("night", 18, 0.9),
    "1B": ("night", 26, 1.0), "1サビ": ("sakura", 72, 1.1), "間奏": ("sakura", 60, 1.1),
    "2A": ("lonely", 20, 0.9), "2B": ("lonely", 28, 1.0), "2サビ": ("sakura", 84, 1.15),
    "Solo": ("solo", 104, 1.35), "Cメロ": ("violet", 30, 0.8), "落ちサビ": ("mono", 26, 0.35),
    "ラスサビ": ("bright", 136, 1.2), "Outro": ("outro", 40, 0.7),
}
MAX_PETALS = 140
VISUALIZER = {"Intro B": 0.55, "間奏": 0.55, "Solo": 1.0}   # spectrum line in instrumental parts
BANDS = 48


def spectrum_frames(mono, sr):
    """Per-video-frame log-band levels in 0..1 with a slow fall, for the visualizer."""
    n_fft, hop = 4096, sr // FPS
    freqs = np.fft.rfftfreq(n_fft, 1 / sr)
    edges = np.geomspace(60, 12000, BANDS + 1)
    which = np.digitize(freqs, edges) - 1
    win = np.hanning(n_fft)
    frames = len(mono) // hop
    out = np.zeros((frames, BANDS))
    padded = np.concatenate([mono, np.zeros(n_fft)])
    for a in range(0, frames, 400):
        idx = np.arange(a, min(frames, a + 400))[:, None] * hop + np.arange(n_fft)[None, :]
        mag = np.abs(np.fft.rfft(padded[idx] * win, axis=1))
        for b in range(BANDS):
            sel = which == b
            if sel.any():
                out[a:a + len(idx), b] = mag[:, sel].mean(axis=1)
    db = 20 * np.log10(out + 1e-9)
    db -= np.percentile(db, 99, axis=0)[None, :]
    v = np.clip((db + 42) / 42, 0, 1)
    for k in range(1, frames):
        v[k] = np.maximum(v[k], v[k - 1] - 0.05)
    return v


# --- timeline ------------------------------------------------------------------
def timeline():
    marks, parts, *_ = music.layout(madane.SECTIONS)
    secs = [(m.name, build.seconds(m.start), build.seconds(m.start + m.bars * music.BAR)) for m in marks]
    lines = []
    for name, start, length, events, feel in parts:
        notes = music.section_notes(start, events)
        for i, (jp, zh) in enumerate(LYRICS[name]):
            a, b = start + 2 * i * music.BAR, start + (2 * i + 2) * music.BAR
            if name == "Outro":
                a, b = start, start + 3 * music.BAR
            sung = [n for n in notes if a <= n.start < b]
            lines.append(dict(jp=jp, zh=zh, chorus="サビ" in name, section=name, row=i % 2,
                              onsets=[build.seconds(n.start) for n in sung], syls=[n.lyric for n in sung],
                              end=build.seconds(sung[-1].start + sung[-1].length)))
    # each line is previewed (dim) on its row before it is sung, without colliding
    # with the previous line that used the same row
    for i, ln in enumerate(lines):
        same = [p for p in lines[:i] if p["row"] == ln["row"]]
        ln["show"] = max(ln["onsets"][0] - 2.0, same[-1]["end"] + 0.9 if same else 0.0)
    for i, ln in enumerate(lines):
        later = [p for p in lines[i + 1:] if p["row"] == ln["row"]]
        ln["hide"] = min(ln["end"] + 0.8, later[0]["show"] - 0.05 if later else 1e9)
    return secs, lines


def look_at(secs, t, fade=1.5):
    """Blend weights between the current and previous section looks."""
    for k, (name, a, b) in enumerate(secs):
        if a <= t < b or k == len(secs) - 1:
            cur = SECTION_LOOK[name]
            prev = SECTION_LOOK[secs[k - 1][0]] if k else cur
            w = min(1.0, (t - a) / fade + 0.0) if k else 1.0
            return prev, cur, max(0.0, w)
    return SECTION_LOOK[secs[0][0]], SECTION_LOOK[secs[0][0]], 1.0


# --- static layers ------------------------------------------------------------------
def palette_image(p):
    top, bottom, glow, (gx, gy), gr, screen, _ = p
    y = np.linspace(0, 1, H)[:, None, None]
    img = np.array(top)[None, None, :] * (1 - y) + np.array(bottom)[None, None, :] * y
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx / W - gx) * 1.6) ** 2 + (yy / H - gy) ** 2)
    img = img + np.array(glow)[None, None, :] * (np.exp(-(d / gr) ** 2) * 0.55)[..., None]
    light = np.exp(-((H - yy) / (H * 0.22)) ** 2) * np.exp(-((xx / W - 0.5) / 0.45) ** 2)
    img = img + np.array((70, 120, 230))[None, None, :] * (light * screen)[..., None]
    vig = 1 - 0.55 * np.clip(np.sqrt(((xx / W - 0.5) / 0.75) ** 2 + ((yy / H - 0.5) / 0.75) ** 2) - 0.35, 0, 1)
    return np.clip(img * vig[..., None], 0, 255).astype(np.float32)


def rays_image():
    yy, xx = np.mgrid[0:H, 0:W]
    ang = np.arctan2(yy - (-0.3 * H), xx - 1.25 * W)
    beams = (0.5 + 0.5 * np.cos(ang * 22)) ** 6 * np.clip(1 - np.hypot(xx - 1.25 * W, yy + 0.3 * H) / (1.7 * W), 0, 1)
    return (beams[..., None] * np.array((255, 236, 220))[None, None, :] * 0.22).astype(np.float32)


def petal_sprites():
    """Pre-rendered petals: [depth][rotation step][flip step] -> RGBA image."""
    base = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.ellipse((24, 18, 104, 118), fill=(255, 205, 222, 255))
    d.polygon([(64, 10), (52, 30), (76, 30)], fill=(0, 0, 0, 0))          # the notch
    inner = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(inner).ellipse((44, 50, 84, 112), fill=(255, 168, 196, 150))
    base = Image.alpha_composite(base, inner.filter(ImageFilter.GaussianBlur(10)))
    sizes, blurs, alphas = (14, 24, 40), (1.2, 0.0, 2.2), (0.5, 0.9, 0.7)
    out = []
    for size, blur, alpha in zip(sizes, blurs, alphas):
        rot = []
        for r in range(24):
            flips = []
            for f in (1.0, 0.72, 0.45, 0.2):
                im = base.resize((max(2, int(128 * f)), 128)).rotate(r * 15, expand=True, resample=Image.BICUBIC)
                im = im.resize((max(2, int(im.width * size / 128)), max(2, int(im.height * size / 128))), Image.LANCZOS)
                if blur:
                    pad = Image.new("RGBA", (im.width + 8, im.height + 8), (0, 0, 0, 0))
                    pad.paste(im, (4, 4))
                    im = pad.filter(ImageFilter.GaussianBlur(blur))
                a = np.array(im)
                a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
                flips.append(Image.fromarray(a))
            rot.append(flips)
        out.append(rot)
    return out


def text_layer(text, font_path, size, color, glow=None):
    font = ImageFont.truetype(font_path, size)
    box = font.getbbox(text)
    w, h = box[2] - box[0] + 60, box[3] - box[1] + 60
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((30 - box[0], 30 - box[1]), text, font=font, fill=color)
    if glow:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((30 - box[0], 30 - box[1]), text, font=font, fill=glow)
        img = Image.alpha_composite(g.filter(ImageFilter.GaussianBlur(9)), img)
    # x positions of each character's right edge, for the karaoke wipe
    edges, x = [], 30
    for ch in text:
        x += font.getlength(ch)
        edges.append(x)
    return np.array(img).astype(np.float32), edges


# --- renderer -------------------------------------------------------------------
class Renderer:
    def __init__(self, audio_path):
        self.secs, self.lines = timeline()
        x, sr = soundfile.read(audio_path, always_2d=True)
        hop = sr // FPS
        mono = x.mean(axis=1)
        env = np.sqrt(np.convolve(mono ** 2, np.ones(hop) / hop, mode="same"))[::hop]
        self.level = env / (np.percentile(env, 98) + 1e-9)
        self.duration = len(mono) / sr
        self.spec = spectrum_frames(mono, sr)
        self.bg = {k: palette_image(p) for k, p in PALETTES.items()}
        self.rays = rays_image()
        self.sprites = petal_sprites()
        rng = np.random.default_rng(5)
        n = MAX_PETALS
        self.p = dict(x0=rng.uniform(-100, W + 100, n), y0=rng.uniform(0, H + 200, n),
                      v=rng.uniform(55, 120, n), amp=rng.uniform(20, 70, n), f=rng.uniform(0.15, 0.5, n),
                      ph=rng.uniform(0, 2 * np.pi, n), rot=rng.uniform(-160, 160, n), r0=rng.uniform(0, 360, n),
                      flip=rng.uniform(0.3, 1.1, n), depth=rng.choice([0, 1, 1, 2], n))
        self.p["depth"][rng.permutation(n)[: n // 6]] = 2
        # cumulative "petal time" so slow-motion sections slow the fall smoothly
        ts = np.arange(0, self.duration + 10, 1 / FPS)
        speed = np.array([self._mix(look_at(self.secs, t), 2) for t in ts])
        self.ptime = np.cumsum(speed) / FPS
        self.stars = (rng.uniform(0, W, 260).astype(int), rng.uniform(0, H * 0.7, 260).astype(int),
                      rng.uniform(0, 2 * np.pi, 260), rng.uniform(0.3, 1.0, 260))
        self.text_cache = {}
        self.title = text_layer("まだね", JP_FONT, 150, (255, 255, 255, 255), (255, 170, 200, 200))
        self.feat = text_layer("feat. 初音ミク", JP_LIGHT, 40, (235, 238, 250, 255))
        self.credits = [text_layer(c, JP_LIGHT if i else JP_FONT, 44 if i == 0 else 28,
                                   (240, 240, 250, 255)) for i, c in enumerate(CREDITS)]

    @staticmethod
    def _mix(blend, idx):
        prev, cur, w = blend
        return prev[idx] * (1 - w) + cur[idx] * w

    def _line_layers(self, i):
        if i not in self.text_cache:
            ln = self.lines[i]
            size = 64 if ln["chorus"] else 58
            if ln["section"] == "Outro":
                size = 84
            dim = text_layer(ln["jp"], JP_FONT, size, (225, 230, 245, 95))
            lit = text_layer(ln["jp"], JP_FONT, size, (255, 255, 255, 255), (255, 175, 205, 210))
            zh = text_layer(ln["zh"], ZH_FONT, 28, (230, 232, 245, 190))
            self.text_cache[i] = (dim, lit, zh)
        return self.text_cache[i]

    def frame(self, k):
        t = k / FPS
        blend = look_at(self.secs, t)
        prev, cur, w = blend
        img = self.bg[PALETTES_KEY(prev)] * (1 - w) + self.bg[PALETTES_KEY(cur)] * w
        lvl = float(self.level[min(k, len(self.level) - 1)])
        rays = PALETTES[prev[0]][6] * (1 - w) + PALETTES[cur[0]][6] * w
        if rays > 0:
            img = img + self.rays * rays * (0.75 + 0.35 * lvl)
        img = img * (0.94 + 0.08 * lvl)
        sx, sy, sph, sb = self.stars                  # twinkling stars
        tw = (0.5 + 0.5 * np.sin(t * 1.3 + sph)) * sb * 120 * (1 - 0.6 * w * (cur[0] in ("bright", "solo")))
        img[sy, sx] += tw[:, None]
        frame = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")

        count = self._mix(blend, 1)
        pt = self.ptime[min(k, len(self.ptime) - 1)]
        p = self.p
        for i in range(MAX_PETALS):
            vis = min(1.0, count - i)
            if vis <= 0:
                continue
            depth = p["depth"][i]
            scale = (0.6, 1.0, 1.5)[depth]
            y = (p["y0"][i] + p["v"][i] * scale * pt) % (H + 200) - 100
            x = p["x0"][i] + p["amp"][i] * math.sin(2 * math.pi * p["f"][i] * pt + p["ph"][i]) + 40 * pt * 0.15
            x = (x + 100) % (W + 200) - 100
            rot = int(((p["r0"][i] + p["rot"][i] * pt) % 360) / 15) % 24
            flip = int(abs(math.sin(math.pi * p["flip"][i] * pt + p["ph"][i])) * 3.99)
            spr = self.sprites[depth][rot][flip]
            if vis < 1:
                a = np.array(spr)
                a[..., 3] = (a[..., 3] * vis).astype(np.uint8)
                spr = Image.fromarray(a)
            frame.alpha_composite(spr, (int(x - spr.width / 2), int(y - spr.height / 2)))
        self._visualizer(frame, k, t, cur)
        arr = np.array(frame).astype(np.float32)

        self._lyrics(arr, t)
        self._title(arr, t)
        self._credits(arr, t)
        if t > self.duration - 3:                      # fade to black at the very end
            arr[..., :3] *= max(0.0, (self.duration - t) / 3)
        return np.clip(arr[..., :3], 0, 255).astype(np.uint8).tobytes()

    def _vis_level(self, t):
        for k, (name, a, b) in enumerate(self.secs):
            if a <= t < b:
                base = VISUALIZER.get(name, 0.0)
                prev = VISUALIZER.get(self.secs[k - 1][0], 0.0) if k else 0.0
                nxt = VISUALIZER.get(self.secs[k + 1][0], 0.0) if k + 1 < len(self.secs) else 0.0
                lvl = base
                if prev != base:
                    lvl = prev + (base - prev) * min(1.0, (t - a) / 1.0)
                if nxt < base and t > b - 1.0:
                    lvl = min(lvl, base * (b - t) / 1.0)
                return lvl
        return 0.0

    def _visualizer(self, frame, k, t, look):
        lvl = self._vis_level(t)
        if lvl <= 0.01:
            return
        bands = self.spec[min(k, len(self.spec) - 1)]
        kernel = np.exp(-0.5 * (np.arange(-3, 4) / 1.3) ** 2)
        bands = np.convolve(np.pad(bands, 3, mode="edge"), kernel / kernel.sum(), mode="valid")
        fine = np.linspace(0, BANDS - 1, BANDS * 4)                 # smooth, flowing curve
        bands = np.interp(fine, np.arange(BANDS), bands)
        glow = PALETTES[look[0]][2]
        color = tuple(min(255, int(c * 0.6 + 110)) for c in glow)
        span, cy, h0 = W * 0.42, 210, 6
        offs = (fine + 0.5) / BANDS * span
        hs = h0 + bands ** 1.5 * 130
        xs = np.concatenate([W / 2 - offs[::-1], W / 2 + offs])
        hs = np.concatenate([hs[::-1], hs])
        top = list(zip(xs, cy - hs))
        bot = list(zip(xs, cy + hs * 0.45))
        layer = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for width, alpha in ((18, 34), (8, 80), (3, 220)):
            a = int(alpha * lvl)
            d.line(top, fill=color + (a,), width=width, joint="curve")
            d.line(bot, fill=color + (int(a * 0.6),), width=max(1, width - 2), joint="curve")
        frame.alpha_composite(layer, (0, int(H * 0.47) - 210))

    def _blit(self, dst, layer, cx, cy, alpha, clip_x=None, feather=14.0):
        img, _ = layer
        h, w = img.shape[:2]
        x0, y0 = int(cx - w / 2), int(cy - h / 2)
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
        if xa >= xb or ya >= yb or alpha <= 0:
            return
        src = img[ya - y0:yb - y0, xa - x0:xb - x0]
        a = src[..., 3:4] / 255 * alpha
        if clip_x is not None:
            cols = np.arange(xa - x0, xb - x0)
            a = a * np.clip((clip_x - cols) / feather + 0.5, 0, 1)[None, :, None]
        dst[ya:yb, xa:xb, :3] = dst[ya:yb, xa:xb, :3] * (1 - a) + src[..., :3] * a

    def _lyrics(self, arr, t):
        for i, ln in enumerate(self.lines):
            start, end = ln["show"], ln["hide"]
            if not (start <= t <= end):
                continue
            fade_in = min(1.0, (t - start) / 0.45)
            fade_out = min(1.0, (end - t) / 0.45)
            alpha = max(0.0, min(fade_in, fade_out))
            drift = (1 - fade_in) * 14 - (1 - fade_out) * 14
            dim, lit, zh = self._line_layers(i)
            if ln["section"] == "Outro":
                cy = H * 0.5
            else:
                cy = H * (0.69 if ln["row"] == 0 else 0.83) + drift
            # karaoke: map characters to syllable onsets in order
            chars = [c for c in ln["jp"] if c not in "　 「」"]
            n_chars, ons = len(chars), ln["onsets"]
            done = 0
            for j in range(n_chars):
                if ons[min(len(ons) - 1, j * len(ons) // n_chars)] <= t:
                    done = j + 1
            edges, idx, x_clip = lit[1], 0, 0.0
            for pos, ch in enumerate(ln["jp"]):
                if ch not in "　 「」":
                    idx += 1
                if idx >= done:
                    x_clip = edges[pos] if done else 0.0
                    break
            else:
                x_clip = edges[-1] + 40
            if t > ln["end"]:
                x_clip = edges[-1] + 40
            self._blit(arr, dim, W / 2, cy, alpha)
            if x_clip > 0:
                self._blit(arr, lit, W / 2, cy, alpha, clip_x=x_clip)
            size = 84 if ln["section"] == "Outro" else 64 if ln["chorus"] else 58
            self._blit(arr, zh, W / 2, cy + int(size * 0.92) + 4, alpha * 0.9)

    def _title(self, arr, t):
        a = min(1.0, max(0.0, (t - 1.0) / 1.5)) * min(1.0, max(0.0, (11.0 - t) / 1.5))
        if a > 0:
            self._blit(arr, self.title, W / 2, H * 0.42 - 6 * t / 11, a)
            self._blit(arr, self.feat, W / 2, H * 0.42 + 120, a * 0.9)

    def _credits(self, arr, t):
        start = self.duration - 9.5
        a = min(1.0, max(0.0, (t - start) / 1.5))
        if a > 0:
            for i, layer in enumerate(self.credits):
                self._blit(arr, layer, W / 2, H * 0.30 + i * 62 + (20 if i else 0), a * (1.0 if i == 0 else 0.85))


def PALETTES_KEY(look):
    return look[0]


_R = None


def _init(audio):
    global _R
    _R = Renderer(audio)


def _render(k):
    return _R.frame(k)


def main():
    if sys.argv[1] == "--stills":
        audio, outdir, times = sys.argv[2], Path(sys.argv[3]), [float(x) for x in sys.argv[4:]]
        outdir.mkdir(parents=True, exist_ok=True)
        r = Renderer(audio)
        for t in times:
            img = np.frombuffer(r.frame(int(t * FPS)), np.uint8).reshape(H, W, 3)
            Image.fromarray(img).save(outdir / f"still_{t:06.1f}.jpg", quality=90)
        print("stills written to", outdir)
        return
    audio, out = sys.argv[1], sys.argv[2]
    info = soundfile.info(audio)
    frames = int(info.duration * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(7, initializer=_init, initargs=(audio,)) as pool:
        for k, buf in enumerate(pool.imap(_render, range(frames), chunksize=6)):
            enc.stdin.write(buf)
            if k % (FPS * 20) == 0:
                print(f"{k / FPS:6.1f}s / {frames / FPS:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("wrote", out)


if __name__ == "__main__":
    main()
