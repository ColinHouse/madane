"""Parse the song notation and lay out every part in ticks (480 per quarter)."""
import re
from dataclasses import dataclass

TPQ = 480
UNIT = TPQ // 4            # one 16th note
BAR = TPQ * 4
UNITS_PER_BAR = 16

_NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_TOKEN = re.compile(r"(?P<syl>_|[^\d]+?)(?P<dur>\d+)(?P<pitch>[A-G][#b]?-?\d)?")
_PITCH = re.compile(r"([A-G])([#b]?)(-?\d)")
_CHORD = re.compile(r"([A-G][#b]?)(maj7|m7|m6|7sus4|sus4|m|7)?(?:/([A-G][#b]?))?")
_QUALITY = {None: (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11),
            "m7": (0, 3, 7, 10), "m6": (0, 3, 7, 9), "sus4": (0, 5, 7), "7sus4": (0, 5, 7, 10)}


def pitch_class(name):
    return (_NOTE[name[0]] + name[1:].count("#") - name[1:].count("b")) % 12


def note_number(name):
    m = _PITCH.fullmatch(name)
    if not m:
        raise ValueError(f"bad pitch {name!r}")
    acc = {"#": 1, "b": -1, "": 0}[m[2]]
    return 12 * (int(m[3]) + 1) + _NOTE[m[1]] + acc


def parse_bar(text):
    """'と2A4 _2 ...' -> [(syllable or None, sixteenths, midi or None)]"""
    events = []
    for tok in text.split():
        m = _TOKEN.fullmatch(tok)
        if not m:
            raise ValueError(f"bad token {tok!r} in {text!r}")
        syl, dur, pitch = m["syl"], int(m["dur"]), m["pitch"]
        if syl == "_":
            events.append((None, dur, None))
        elif pitch is None:
            raise ValueError(f"missing pitch in {tok!r}")
        else:
            events.append((syl, dur, note_number(pitch)))
    total = sum(d for _, d, _ in events)
    if total != UNITS_PER_BAR:
        raise ValueError(f"bar adds up to {total}/16: {text!r}")
    return events


def parse_chord(name, transpose=0):
    m = _CHORD.fullmatch(name)
    if not m:
        raise ValueError(f"bad chord {name!r}")
    root = (pitch_class(m[1]) + transpose) % 12
    tones = [(root + i) % 12 for i in _QUALITY[m[2]]]
    bass = (pitch_class(m[3]) + transpose) % 12 if m[3] else root
    return tones, bass


@dataclass
class Note:
    start: int          # ticks
    length: int         # ticks
    pitch: int
    velocity: int = 90
    lyric: str = None


@dataclass
class Chord:
    start: int
    length: int
    tones: list
    bass: int
    feel: str
    bar: int            # bar index inside its section
    section_bars: int
    last_in_song: bool = False


@dataclass
class Section:
    name: str
    start: int          # ticks
    bars: int
    feel: str
    next_feel: str


def layout(sections):
    """Turn the song form into ticks.

    Returns sections, vocal parts [(name, start, length, [(lyric, ticks, midi)], feel)],
    chords and the instrumental hook notes.
    """
    marks, parts, chords, hook = [], [], [], []
    bar = 0
    for i, sec in enumerate(sections):
        n = len(sec["chords"])
        shift = sec.get("transpose", 0)
        start = bar * BAR
        for key in ("vocal", "hook"):
            if key in sec and len(sec[key]) != n:
                raise ValueError(f"{sec['name']}: {key} has {len(sec[key])} bars, chords have {n}")
        next_feel = sections[i + 1]["feel"] if i + 1 < len(sections) else None
        marks.append(Section(sec["name"], start, n, sec["feel"], next_feel))

        for b, symbol in enumerate(sec["chords"]):
            names = symbol.split()
            seg = BAR // len(names)
            for j, name in enumerate(names):
                tones, bass = parse_chord(name, shift)
                chords.append(Chord(start + b * BAR + j * seg, seg, tones, bass, sec["feel"], b, n))

        if "vocal" in sec:
            events = [(syl, dur * UNIT, None if p is None else p + shift)
                      for text in sec["vocal"] for syl, dur, p in parse_bar(text)]
            parts.append((sec["name"], start, n * BAR, events, sec["feel"]))

        if "hook" in sec:
            pos = start
            for text in sec["hook"]:
                for syl, dur, p in parse_bar(text):
                    if syl is not None:
                        hook.append(Note(pos, dur * UNIT, p + shift + sec.get("hook_octave", 0), 64))
                    pos += dur * UNIT
        bar += n
    chords[-1].last_in_song = True
    return marks, parts, chords, hook, bar


def section_notes(start, events, velocity=90):
    notes, pos = [], start
    for syl, length, pitch in events:
        if syl is not None:
            notes.append(Note(pos, length, pitch, velocity, syl))
        pos += length
    return notes


def vocal_notes(parts):
    return [n for _, start, _, events, _ in parts for n in section_notes(start, events)]


# --- demo arrangement (ballad) ------------------------------------------------
FEELS = {
    "intro":     dict(piano="arp", pad=False, bass=None, drums=None, vel=52),
    "verse":     dict(piano="arp", pad=False, bass=None, drums=None, vel=44),
    "verse2":    dict(piano="arp", pad=True, bass=None, drums=None, vel=48),
    "pre":       dict(piano="block", pad=True, bass="whole", drums=None, vel=56),
    "chorus":    dict(piano="arp", pad=True, bass="whole", drums=None, vel=66),
    "interlude": dict(piano="arp", pad=True, bass="whole", drums=None, vel=58),
    "chorus2":   dict(piano="arp", pad=True, bass="half", drums="halftime", vel=68),
    "bridge":    dict(piano="block", pad=True, bass="whole", drums="halftime", vel=60),
    "ochi":      dict(piano="whole", pad=False, bass=None, drums=None, vel=40),
    "last":      dict(piano="arp", pad=True, bass="half", drums="halftime", vel=76),
    "outro":     dict(piano="arp", pad=True, bass="whole", drums=None, vel=44),
}
FEELS["introband"] = FEELS["interlude"]       # sketch-demo stand-ins for the v5 form
FEELS["solo"] = FEELS["chorus2"]


def _window(tones, low):
    """Place each pitch class in [low, low+11] -> a close voicing."""
    return sorted(low + (pc - low) % 12 for pc in tones)


def _near(pc, prev, low=33, high=50):
    options = [p for p in range(low, high + 1) if p % 12 == pc]
    return min(options, key=lambda p: abs(p - prev))


def accompaniment(chords):
    """Piano (left-hand bass note + right hand), string pad and bass notes."""
    piano, pad, bass = [], [], []
    prev_bass = 38
    for c in chords:
        f = FEELS[c.feel]
        vel = f["vel"]
        voicing = _window(c.tones, 55)
        root = _near(c.bass, prev_bass)
        prev_bass = root
        style = "whole" if c.last_in_song else f["piano"]
        hold = c.length + (BAR if c.last_in_song else 0)

        piano.append(Note(c.start, hold, root + 12 if root < 40 else root, vel - 2))
        if style == "arp":
            tones = voicing + [voicing[0] + 12]
            order = [0, 1, 2, 3, 2, 1, 2, 3]
            for k in range(c.length // (TPQ // 2)):
                piano.append(Note(c.start + k * TPQ // 2, TPQ, tones[order[k] % len(tones)],
                                  vel - (4 if k % 2 == 0 else 12)))
        elif style == "block":
            for k in range(0, c.length, TPQ * 2):
                for p in voicing:
                    piano.append(Note(c.start + k, TPQ * 2, p, vel - 6))
        else:
            for p in voicing:
                piano.append(Note(c.start, hold, p, vel - 6))

        if f["pad"] or c.last_in_song:
            for p in _window(c.tones, 50):
                pad.append(Note(c.start, hold, p, 60))

        if f["bass"]:
            if f["bass"] == "whole" or c.last_in_song:
                bass.append(Note(c.start, hold, root, 80))
            else:
                for k in range(0, c.length, TPQ * 2):
                    bass.append(Note(c.start + k, TPQ * 2 - 40, root, 80))
    return piano, pad, bass


def drums(marks):
    """[(tick, kind, velocity)] with kind in kick/snare/hat/crash."""
    hits = []
    for sec in marks:
        style = FEELS[sec.feel]["drums"]
        for b in range(sec.bars):
            t0 = sec.start + b * BAR
            if style == "halftime":
                if b == 0 and sec.feel == "last":
                    hits.append((t0, "crash", 80))
                hits += [(t0, "kick", 78), (t0 + 8 * UNIT, "snare", 60)]
                hits += [(t0 + u * UNIT, "hat", 42 if u % 4 == 0 else 32) for u in range(0, 16, 2)]
            if b == sec.bars - 1 and sec.next_feel == "last":
                hits += [(t0 + u * UNIT, "snare", 34 + 5 * (u - 8)) for u in range(8, 16)]
    return hits
