"""Phrase-level expression shared by the Vocaloid project and the demo.

Phrases are split at rests of an eighth note or longer (the breath points).
Each phrase swells toward its highest note and fades on its last note, and
long notes get a delayed vibrato that sinks slightly at phrase ends.
"""
import math

from music import TPQ, UNIT

BREATH_GAP = 2 * UNIT

BASE_DYNAMICS = {"verse": 54, "verse2": 56, "pre": 62, "chorus": 70, "chorus2": 72,
                 "bridge": 68, "ochi": 46, "last": 78, "outro": 44}
VIBRATO_CENTS = {"verse": 26, "verse2": 28, "pre": 30, "chorus": 36, "chorus2": 38,
                 "bridge": 36, "ochi": 24, "last": 40, "outro": 22}
VIBRATO_HZ = 5.4
MIN_VIBRATO_NOTE = 3 * UNIT
# How far a line's last note fades. Choruses keep singing through their line
# ends so the lines join up; a section's final line fades further.
END_FADE = {"verse": 16, "verse2": 16, "pre": 14, "chorus": 10, "chorus2": 10,
            "bridge": 12, "ochi": 16, "last": 10, "outro": 24}
SECTION_END_FADE = 20
END_SINK_CENTS = 12          # the slight pitch sag on a line's last note


def phrases(notes):
    """Group time-ordered notes into phrases separated by breath rests."""
    out, cur = [], []
    for n in notes:
        if cur and n.start - (cur[-1].start + cur[-1].length) >= BREATH_GAP:
            out.append(cur)
            cur = []
        cur.append(n)
    if cur:
        out.append(cur)
    return out


def dynamics_points(phrase, base, fade=16):
    """(tick, value) corners: swell to the top note, hold the last note, then fade."""
    start, last = phrase[0].start, phrase[-1]
    end = last.start + last.length
    top = max(phrase, key=lambda n: (n.pitch, -n.start))
    pts = [(start, base - 6), (top.start + top.length // 2, base + 6)]
    if last.start > pts[-1][0]:
        pts.append((last.start, base + 2))
    fade_from = max(pts[-1][0], last.start + last.length // 2)
    pts += [(fade_from, base + 2), (end, base - fade)]
    return pts


def sample_points(points, step=30):
    """Linear interpolation of corner points every `step` ticks."""
    out = []
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        for t in range(t0, t1, step):
            out.append((t, round(v0 + (v1 - v0) * (t - t0) / max(1, t1 - t0))))
    out.append(points[-1])
    return out


def note_cents(note, feel, phrase_end, bpm, step=10):
    """[(tick, cents)] pitch offsets for one note (empty when it stays flat)."""
    if note.length < MIN_VIBRATO_NOTE:
        return []
    ticks_per_second = TPQ * bpm / 60
    onset = max(int(note.length * 0.35), 150)
    depth = VIBRATO_CENTS[feel]
    tail = min(120, note.length // 4)
    out = []
    for t in range(onset, note.length, step):
        ramp = min(1.0, (t - onset) / 200)
        cents = depth * ramp * math.sin(2 * math.pi * VIBRATO_HZ * (t - onset) / ticks_per_second)
        if phrase_end and t > note.length - tail:
            k = (t - (note.length - tail)) / tail
            cents = cents * (1 - k) - END_SINK_CENTS * k
        out.append((note.start + t, cents))
    out.append((note.start + note.length, 0.0))
    return [(note.start, 0.0)] + out


def expression(notes, feel, bpm):
    """Dynamics corner points and pitch offsets for a section's sung notes."""
    dyn, cents = [], []
    lines = phrases(notes)
    for ph in lines:
        fade = SECTION_END_FADE if ph is lines[-1] else END_FADE[feel]
        dyn.append(dynamics_points(ph, BASE_DYNAMICS[feel], max(fade, END_FADE[feel])))
        for n in ph:
            cents += note_cents(n, feel, n is ph[-1], bpm)
    return dyn, cents
