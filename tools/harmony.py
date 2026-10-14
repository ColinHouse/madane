"""Backing vocals for まだね: a harmony a third below the melody (下ハモ) in the
choruses, and a soft 「う」 pad under the last chorus, written as a second
VOCALOID project so it can be exported on its own.

    python -I tools/harmony.py        -> out/madane_v4_harmony.vpr

Export it from 0:00 like the lead, as out/miku_harmony_v4.wav.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build
import expression
import madane
import music
import vpr
from arrangement import nearest, notes_in, scale

OUT = Path(__file__).resolve().parent.parent / "out"
HARMONY_FROM = {"1サビ": 2, "2サビ": 0, "ラスサビ": 0}    # section -> bar where the harmony joins
DYN_DROP = 10                                          # sits under the lead
VIBRATO = 0.6                                          # and moves less
VOICE_COLOR = dict(Air=8, Breathiness=30, Character=-7, Exciter=-20)


def chord_at(chords, tick):
    return next(c for c in reversed(chords) if c.start <= tick)


def third_below(p, chord, key_pc, long_note):
    """Parallel diatonic thirds; a long note settles on a chord tone a third/fourth under p."""
    below = [q for q in scale(key_pc, p - 12, p - 1)]
    third = below[-2]
    if not long_note or third % 12 in chord.tones:
        return third
    options = [q for q in range(p - 5, p - 2) if q % 12 in chord.tones]
    return max(options) if options else third


def harmony_events(name, start, events, chords, key_pc):
    first = start + HARMONY_FROM[name] * music.BAR
    out, pos = [], start
    for syl, length, pitch in events:
        if syl is None or pos < first:
            out.append((None, length, None))
        else:
            out.append((syl, length, third_below(pitch, chord_at(chords, pos), key_pc, length >= 4 * music.UNIT)))
        pos += length
    return out


def pad_events(start, bars, chords):
    """One 「う」 per chord on smooth chord tones around D4–A4, breathing every two bars."""
    out, prev = [], 66
    for c in [c for c in chords if start <= c.start < start + bars * music.BAR]:
        p = nearest(notes_in(c.tones, 62, 70), prev)
        prev = p
        breath = (c.start + c.length - start) % (2 * music.BAR) == 0
        out.append(("う", c.length - (2 * music.UNIT if breath else 0), p))
        if breath:
            out.append((None, 2 * music.UNIT, None))
    return out


def section(name, start, length, events, feel, soft=0.0):
    notes = music.section_notes(start, events)
    dyn, cents = expression.expression(notes, feel, madane.BPM)
    dyn = [[(t, v - DYN_DROP - soft) for t, v in corners] for corners in dyn]
    cents = [(t, c * VIBRATO) for t, c in cents]
    return dict(name=name, start=start, length=length, events=events, feel=feel,
                notes=notes, dyn=dyn, cents=cents)


def vpr_parts(sections, color):
    parts = []
    for s in sections:
        notes, _ = vpr.notes_from_events(s["events"])
        fx = vpr.midi_effects(skill=build.SKILL, breath=build.BREATH, voice_color=color)
        parts.append(vpr.part(s["start"], s["length"], notes, build.VOICE, build.part_controllers(s), fx))
    return parts


def main():
    marks, parts, chords, hook, bars = music.layout(madane.SECTIONS)
    shift = {s["name"]: s.get("transpose", 0) for s in madane.SECTIONS}
    harmony, pad = [], []
    for name, start, length, events, feel in parts:
        key_pc = (2 + shift[name]) % 12
        if name in HARMONY_FROM:
            harmony.append(section(name, start, length, harmony_events(name, start, events, chords, key_pc), feel))
        if name == "ラスサビ":
            m = next(m for m in marks if m.name == name)
            pad.append(section(name, start, length, pad_events(start, m.bars, chords), "ochi", soft=4))
    tracks = [vpr.track("Miku Harmony", vpr_parts(harmony, VOICE_COLOR)),
              vpr.track("Miku Ooh", vpr_parts(pad, dict(VOICE_COLOR, Breathiness=40)))]
    path = OUT / "madane_v4_harmony.vpr"
    vpr.write_vpr(path, vpr.project(madane.TITLE + " (harmony)", madane.BPM, tracks, bars * music.BAR))
    n = sum(len(p["notes"]) for t in tracks for p in t["parts"])
    print(f"wrote {path.name}: {n} notes in {len(harmony)} harmony sections + pad")
    sys.stdout.reconfigure(encoding="utf-8")
    for s in harmony:                      # a readable check of the harmony against the lead
        lead = next(e for e in parts if e[0] == s["name"])
        mel = [p for syl, _, p in lead[3] if syl]
        har = [p for syl, _, p in s["events"] if syl]
        sung = [p for p in har]
        print(s["name"], "intervals under the lead:",
              " ".join(str(m - h) for m, h in zip([p for (syl, _, p), (hs, _, _) in zip(lead[3], s["events"]) if syl and hs],
                                                   sung)))


if __name__ == "__main__":
    main()
