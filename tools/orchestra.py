"""Orchestral colour for まだね v7: harp, glockenspiel, solo violin, horns, flute,
spiccato and tremolo strings, timpani and orchestral effects.

The first half stays the piano's, so these mostly decorate: the harp sweeps
into each chorus and ripples under it, the glockenspiel doubles the music box,
the solo violin takes the hook in the interlude and answers the voice in 2A,
and the horns, spiccato and timpani arrive with the second half.
"""
import re

from arrangement import E, H, Q, _counter, _guide_tones, _progress, _vel, nearest, notes_in, scale
from music import BAR, UNIT, Note, note_number

# keys on the timpani and effects tracks
TIMP_PITCHES = (45, 46, 50, 51)          # A2 Bb2 D3 Eb3 (retuned hits)
ROLL, ROLL_HALF = 24, 36                 # crescendo rolls (one bar / half a bar) for pitch p on key p + 24 / p + 36
BELL, CYM_SWELL = 60, 71                 # bell-tree stroke, suspended-cymbal swell
REV_PIANO, REV_PIANO_UP, SUB_HIT = 73, 74, 75   # reversed piano chord (D major / E♭ major), sub drop
REV_PIANO_S = 2.2                        # length of the reversed piano swell
BELL_LEAD, CYM_PEAK = 0.74, 3.81         # seconds from sample start to the stroke / swell peak


def _ticks(song, seconds):
    return int(round(seconds * song.tps))


# --- harp --------------------------------------------------------------------------
def _ripple(c, lo, hi, step, vel, start=0, up_only=False):
    """Arpeggio across the chord: up and back down (or up only), one note per step."""
    tones = notes_in(c.tones, lo, hi)
    seq = tones if up_only else tones + tones[-2:0:-1]
    out = []
    for k in range(start // step, c.length // step):
        p = seq[k % len(seq)]
        out.append(Note(c.start + k * step, 4 * step, p, _vel(vel - (0 if k % 4 == 0 else 6), 3)))
    return out


def _gliss(t_end, seconds_long, song, key_pc, lo, hi, v0, v1, up=True):
    """A harp glissando through the scale that lands on t_end."""
    notes = scale(key_pc, lo, hi)
    if not up:
        notes = notes[::-1]
    span = _ticks(song, seconds_long)
    step = span / len(notes)
    return [Note(int(t_end - span + i * step), H, p, _vel(v0 + (v1 - v0) * i / (len(notes) - 1), 2))
            for i, p in enumerate(notes)]


def _strum(t, tones, lo, hi, vel, gap=24):
    """A rolled chord, bottom to top."""
    return [Note(t + i * gap, BAR, p, _vel(vel - i, 2)) for i, p in enumerate(notes_in(tones, lo, hi))]


def harp(song):
    out = []
    for c in song.chords:
        f = c.feel
        m, _ = song.section(c)
        bar = (c.start - m.start) // BAR
        if f == "intro":                                  # slow rising arpeggio under the music box
            out += _ripple(c, 50, 79, E, 46, up_only=True)
        elif f == "introband":
            out += _ripple(c, 62, 86, UNIT, 40)
        elif f == "verse":                                # a rolled chord at each bar, nothing more
            if c.start % BAR == 0:
                out += _strum(c.start, c.tones, 50, 74, 42)
        elif f == "verse2":
            out += _ripple(c, 55, 79, E, 44)
        elif f == "pre":
            out += _ripple(c, 57, 81, E, 42 + int(14 * _progress(song, c)), up_only=True)
        elif f in ("chorus", "chorus2", "last"):
            v = {"chorus": 46, "chorus2": 50, "last": 56}[f]
            out += _ripple(c, 74, 96, UNIT, v)                 # above the voice
        elif f == "interlude":
            out += _ripple(c, 62, 88, UNIT, 44)
        elif f == "bridge" and bar >= 4:
            out += _ripple(c, 64, 91, UNIT, 40 + 3 * bar)
        elif f == "ochi":                                 # only harp and piano around the voice
            out += _ripple(c, 69, 93, E, 38)
        elif f == "outro" and not c.last_in_song:
            out += _ripple(c, 62, 88, E, 40)
    for m in song.marks:                                  # sweeps into the big sections
        key = (2 + song.shift[m.name]) % 12
        if m.feel in ("chorus", "chorus2", "last", "interlude"):
            out += _gliss(m.start, 0.9 if m.feel == "interlude" else 1.4, song, key, 55, 91, 38, 70)
    last = song.chords[-1]
    out += _gliss(last.start, 1.2, song, (2 + song.shift[song.marks[-1].name]) % 12, 62, 91, 30, 52)
    out += _strum(last.start, last.tones, 38, 96, 54, gap=40)
    return out


# --- glockenspiel ---------------------------------------------------------------------
def glock(song, hook):
    out = [Note(n.start, n.length, n.pitch, _vel(52)) for n in hook if n.pitch >= 76]   # the music box
    for m in song.marks:
        if m.feel in ("chorus2", "last"):                # a ping on every other downbeat
            for c in song.chords_of(m.name):
                if (c.start - m.start) % (2 * BAR) == 0:
                    top = notes_in(c.tones, 86, 98)
                    out.append(Note(c.start, Q, top[0], _vel(48 if m.feel == "chorus2" else 56)))
        if m.feel == "outro":
            c = song.chords_of(m.name)[-2]
            out += [Note(c.start + i * Q, H, p, _vel(44 - 4 * i)) for i, p in enumerate(notes_in(c.tones, 87, 99)[::-1][:3])]
    return out


# --- solo violin ------------------------------------------------------------------------
_TOK = re.compile(r"(?P<pitch>[A-G][#b]?\d):(?P<dur>[\d.]+)")

# answers in the gaps of the 2A melody, one string of tokens per bar (D major)
VIOLIN_2A = [
    "_16",
    "_8 F#5:2 E5:2 D5:2 C#5:2",
    "B4:6 _10",
    "_10 C#5:2 E5:2 A5:2",
    "G5:6 F#5:2 _8",
    "_12 F#5:2 A5:2",
    "B5:6 A5:2 _8",
    "_8 E5:2 F#5:2 G5:2 A5:2",
]
VIOLIN_OCHI = ["B5:16", "C#6:16", "A5:16", "F#5:8 A5:8", "G5:16", "A5:8 C#6:8", "B5:8 D6:8", "C#6:8 D6:8"]
# 2サビ: the solo violin answers at the end of every line, while the voice holds or breathes
VIOLIN_2SABI = [
    "_16",
    "_8 E6:2 C#6:2 A5:4",            # after 舞い落ちる: the petals falling
    "_16",
    "_10 F#5:2 A5:2 D6:2",           # after あなたが歌う, rising into 「さよなら」
    "D6:4 _8 B5:2 E6:2",
    "E6:4 _6 C#6:2 A5:2 F#5:2",      # after まだ言えない
    "G5:8 _4 A5:2 C#6:2",
    "D6:8 C#6:2 B5:2 A5:2 F#5:2",    # under ね, and down into the solo
]
# ラスサビ: the whole section takes the same answers (and doubles them an octave down)
VIOLINS_LAST = [
    "B5:8 D6:8",
    "_8 E6:2 C#6:2 A5:4",
    "A5:8 C#6:8",
    "_10 F#5:2 A5:2 D6:2",
    "D6:4 _8 B5:2 E6:2",
    "E6:4 _8 C#6:2 E6:2",
    "D6:8 _4 C#6:2 E6:2",
    "D6:6 C#6:2 B5:2 A5:2 F#5:4",    # under 振るよ
    "G5:8 B5:8",
    "D6:8 C#6:8",                    # Asus4 -> A
]


def _line(song, name, bars, vel):
    m = song.mark(name)
    out = []
    for b, text in enumerate(bars):
        pos = m.start + b * BAR
        for tok in text.split():
            if tok.startswith("_"):
                pos += int(float(tok[1:]) * UNIT)
                continue
            g = _TOK.fullmatch(tok)
            length = int(float(g["dur"]) * UNIT)
            out.append(Note(pos, length + 30, note_number(g["pitch"]) + song.shift[name], _vel(vel, 3)))
            pos += length
    return out


def solo_violin(song, hook):
    i0, i1 = song.mark("間奏").start, song.mark("間奏").start + song.mark("間奏").bars * BAR
    out = [Note(n.start, n.length + 20, n.pitch + 12, _vel(70 if n.length >= Q else 62, 3))
           for n in hook if i0 <= n.start < i1]           # the violin sings the hook in the interlude
    out += _line(song, "2A", VIOLIN_2A, 58)
    out += _line(song, "2サビ", VIOLIN_2SABI, 68)
    out += _line(song, "落ちサビ", VIOLIN_OCHI, 50)
    return out


def violins_last(song):
    line = _line(song, "ラスサビ", VIOLINS_LAST, 80)
    return line + [Note(n.start, n.length, n.pitch - 12, n.velocity - 10) for n in line]


# --- horns, flute, spiccato, tremolo --------------------------------------------------
def horns(song):
    out = []
    for name, vel in (("2サビ", 62), ("Solo", 66), ("ラスサビ", 76)):
        cs = song.chords_of(name)
        out += _guide_tones(cs, 57, 69, vel, start=62)
        out += _guide_tones(cs, 50, 60, vel - 6, start=55)
    bridge = song.chords_of("Cメロ")[4:]
    out += [Note(n.start, n.length, n.pitch, _vel(54 + 4 * i)) for i, n in enumerate(_guide_tones(bridge, 57, 69, 54))]
    for c in song.chords_of("Outro")[-2:]:
        out += [Note(c.start, c.length, p, _vel(46)) for p in notes_in(c.tones, 51, 63)[:3]]
    return out


def flute(song, hook):
    out = []
    b0, b1 = song.mark("Intro B").start + 2 * BAR, song.mark("Intro B").start + 4 * BAR
    out += [Note(n.start, n.length, n.pitch + 12, _vel(52)) for n in hook if b0 <= n.start < b1]
    for name, vel in (("1サビ", 50), ("ラスサビ", 58)):
        cs = song.chords_of(name)
        out += _counter(cs[len(cs) // 2:], 79, 91, vel, start=83)
    return out


def _string_run(song, t_end, key_pc, lo, hi, beats, v0, v1):
    """Sixteenth-note scale run that lands on t_end (the next downbeat)."""
    notes = [p for p in scale(key_pc, lo, hi)][-beats * 4:]
    t0 = t_end - len(notes) * UNIT
    return [Note(t0 + i * UNIT, UNIT, p, _vel(v0 + (v1 - v0) * i / max(1, len(notes) - 1), 2))
            for i, p in enumerate(notes)]


def spiccato(song):
    out = []
    for name, beats in (("Solo", 1), ("ラスサビ", 2)):
        m = song.mark(name)
        out += _string_run(song, m.start, (2 + song.shift[name]) % 12, 62, 86, beats, 60, 96)
    for c in song.chords:
        m, _ = song.section(c)
        bar = (c.start - m.start) // BAR
        if not (c.feel in ("chorus2", "solo", "last") or (c.feel == "bridge" and bar >= 4)):
            continue
        root = nearest(notes_in([c.tones[0]], 38, 49), 43)
        fifth = root + 7
        upper = notes_in(c.tones, 62, 74)
        base = {"chorus2": 56, "solo": 66, "last": 68, "bridge": 50 + 3 * bar}[c.feel]
        for k in range(c.length // E):
            t = c.start + k * E
            accent = k % 4 == 0
            out.append(Note(t, E - 20, root if k % 2 == 0 else fifth, _vel(base + (12 if accent else 0), 3)))
            if c.feel in ("solo", "last"):
                out.append(Note(t, E - 20, upper[k % len(upper)], _vel(base - 6 + (10 if accent else 0), 3)))
    return out


def tremolo(song):
    out = []
    for c in song.chords_of("Cメロ")[4:]:
        prog = _progress(song, c)
        out += [Note(c.start, c.length, p, _vel(44 + int(40 * prog), 2)) for p in notes_in(c.tones, 74, 86)[:3]]
    pivot = song.chords_of("落ちサビ")[-1]             # the Bb7 that lifts into E♭
    out += [Note(pivot.start, pivot.length, p, _vel(70, 2)) for p in notes_in(pivot.tones, 74, 86)[:3]]
    return out


# --- timpani and effects ------------------------------------------------------------------
def timpani(song):
    out = []
    hit = lambda t, p, v: out.append(Note(t, H, p, _vel(v, 2)))
    for name, pitch, vel in (("2サビ", 50, 84), ("Solo", 50, 90), ("ラスサビ", 51, 104)):
        hit(song.mark(name).start, pitch, vel)
    roll = lambda t, key, v: out.append(Note(t, BAR, key, v))   # rolls are pre-shaped crescendos
    roll(song.mark("2サビ").start - BAR, 45 + ROLL, 64)              # A2 under 2B's last bar
    roll(song.mark("ラスサビ").start - BAR // 2, 46 + ROLL_HALF, 100)   # Bb2 under the Bb7 pivot
    last = song.marks[-1]
    hit(last.start + (last.bars - 2) * BAR, 51, 60)
    return out


def effects(song):
    """Bell tree and suspended-cymbal swells, placed so they peak on the downbeat."""
    out = []
    for m in song.marks:
        if m.feel in ("chorus", "chorus2", "last"):
            out.append(Note(m.start - _ticks(song, CYM_PEAK), Q, CYM_SWELL, 100 if m.feel == "last" else 84))
            out.append(Note(m.start - _ticks(song, BELL_LEAD), Q, BELL, 90))
        if m.feel in ("intro", "ochi"):
            out.append(Note(m.start + (Q if m.feel == "intro" else 0), Q, BELL, 70))
    last = song.chords[-1]
    out.append(Note(last.start + BAR, Q, BELL, 64))
    for m in song.marks:
        if m.feel in ("chorus", "chorus2", "last"):
            key = REV_PIANO_UP if song.shift[m.name] else REV_PIANO
            out.append(Note(m.start - _ticks(song, REV_PIANO_S), Q, key, 70 if m.feel == "chorus" else 88))
        if m.name in ("2サビ", "Solo", "ラスサビ"):
            out.append(Note(m.start, Q, SUB_HIT, 100 if m.name == "ラスサビ" else 84))
    return out


def orchestra(song, hook):
    return {"Harp": harp(song), "Glock": glock(song, hook), "Solo Violin": solo_violin(song, hook),
            "Horns": horns(song), "Flute": flute(song, hook), "Spiccato": spiccato(song),
            "Vln Trem": tremolo(song), "Timpani": timpani(song), "Orch FX": effects(song),
            "Violins Last": violins_last(song)}
