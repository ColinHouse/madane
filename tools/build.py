"""Build まだね: tuned Vocaloid project, MIDI and a sketch demo.

    python tools/build.py [version]
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from scipy.io import wavfile

import expression
import madane
import midifile
import music
import synth
import vpr

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
VERSION = sys.argv[1] if len(sys.argv) > 1 else "v2"

VOICE = "soft"
SKILL = dict(Name=vpr.SKILLS["ballad"], Amount=3, Skill=5)    # as in the Moonlight preset
BREATH = dict(Exhalation=2, Mode=1, Type=0)
DEFAULT_COLOR = dict(Air=0, Breathiness=14, Character=-7, Exciter=-17)
VOICE_COLOR = {
    "verse": dict(Air=4, Breathiness=20, Character=-7, Exciter=-17),
    "verse2": dict(Air=4, Breathiness=20, Character=-7, Exciter=-17),
    "ochi": dict(Air=10, Breathiness=30, Character=-7, Exciter=-20),
    "outro": dict(Air=10, Breathiness=32, Character=-7, Exciter=-20),
}
TICKS_PER_SECOND = music.TPQ * madane.BPM / 60


def seconds(tick):
    return tick / TICKS_PER_SECOND


def clock(tick):
    s = seconds(tick)
    return f"{int(s // 60)}:{s % 60:04.1f}"


def sung_sections(parts):
    out = []
    for name, start, length, events, feel in parts:
        notes = music.section_notes(start, events)
        dyn, cents = expression.expression(notes, feel, madane.BPM)
        out.append(dict(name=name, start=start, length=length, events=events, feel=feel,
                        notes=notes, dyn=dyn, cents=cents))
    return out


def _events(pairs):
    """[(pos, value)] -> controller events sorted by position, last value wins."""
    merged = dict(sorted(pairs, key=lambda p: p[0]))
    return [{"pos": int(p), "value": int(v)} for p, v in sorted(merged.items())]


def accent(n, section_start):
    """A singer leans on downbeats and long notes and passes lightly over quick ones and ん."""
    pos = (n.start - section_start) % music.BAR
    a = 3 if pos % (2 * music.TPQ) == 0 else 1 if pos % music.TPQ == 0 else 0
    if n.length >= 4 * music.UNIT:
        a += 2
    if n.length <= music.UNIT:
        a -= 4
    if n.lyric in ("ん", "ー"):
        a -= 3
    return a


def part_controllers(s):
    start, length = s["start"], s["length"]
    pitch = [(t - start, round(c / 200 * 8191)) for t, c in s["cents"] if 0 <= t - start <= length]
    bumps = [(n.start, min(n.length, 2 * music.TPQ), accent(n, start)) for n in s["notes"]]

    def accented(t, v):              # each note's accent fades over its first half-beat or so
        for t0, span, a in bumps:
            if t0 <= t < t0 + span:
                return v + a * (1 - (t - t0) / span)
        return v
    dynamics = [(t - start, max(0, min(127, round(accented(t, v)))))
                for corners in s["dyn"] for t, v in expression.sample_points(corners)
                if 0 <= t - start <= length]
    return [
        {"name": "pitchBendSens", "events": [{"pos": 0, "value": 2}]},
        {"name": "pitchBend", "events": _events([(0, 0)] + pitch)},
        {"name": "dynamics", "events": _events(dynamics)},
    ]


def build_vpr(sections, total_ticks, path):
    parts = []
    for s in sections:
        notes, _ = vpr.notes_from_events(s["events"])
        fx = vpr.midi_effects(skill=SKILL, breath=BREATH,
                              voice_color=VOICE_COLOR.get(s["feel"], DEFAULT_COLOR))
        parts.append(vpr.part(s["start"], s["length"], notes, VOICE, part_controllers(s), fx))
    song = vpr.project(madane.TITLE, madane.BPM, [vpr.track("Miku Soft", parts)], total_ticks)
    vpr.write_vpr(path, song)
    return sum(len(p["notes"]) for p in parts)


def build_midi(marks, sections, hook, piano, pad, bass, hits, path):
    meta = midifile.Track(madane.TITLE)
    meta.tempo(madane.BPM)
    for sec in marks:
        meta.marker(sec.start, sec.name)
    tracks = [meta]
    lead = [n for s in sections for n in s["notes"]]
    for name, ch, notes in (("Vocal (melody)", 0, lead), ("Piano melody", 1, hook),
                            ("Piano", 2, piano), ("Strings", 3, pad), ("Bass", 4, bass)):
        tr = midifile.Track(name, ch)
        for n in notes:
            tr.note(n.start, n.length, n.pitch, n.velocity, n.lyric)
        tracks.append(tr)
    drum_keys = {"kick": 36, "snare": 38, "hat": 42, "crash": 49}
    dr = midifile.Track("Drums", 9)
    for tick, kind, vel in hits:
        dr.note(tick, music.UNIT, drum_keys[kind], vel)
    tracks.append(dr)
    midifile.write(path, tracks)


def curves(sections, n):
    """Per-sample pitch offsets (cents) and loudness from the expression curves."""
    sr = synth.SR
    cents, level = np.zeros(n), np.zeros(n)
    for s in sections:
        a, b = int(seconds(s["start"]) * sr), min(n, int(seconds(s["start"] + s["length"]) * sr))
        ticks = np.arange(a, b) / sr * TICKS_PER_SECOND
        if s["cents"]:
            cents[a:b] = np.interp(ticks, [t for t, _ in s["cents"]], [c for _, c in s["cents"]],
                                   left=0, right=0)
        for corners in s["dyn"]:
            a = int(seconds(corners[0][0]) * sr)
            b = min(n, int((seconds(corners[-1][0]) + 0.1) * sr))
            values = np.interp(np.arange(a, b) / sr * TICKS_PER_SECOND,
                               [t for t, _ in corners], [v for _, v in corners])
            level[a:b] = (np.clip(values, 0, 127) / 64) ** 1.5
    return cents, level


def render(sections, hook, piano, pad, bass, hits, total_ticks, path):
    mix = synth.Mixer(seconds(total_ticks) + 4.0)
    vel = lambda n: (n.velocity / 127) ** 1.5

    cents, level = curves(sections, mix.n)
    lead = [(seconds(n.start), seconds(n.length), n.pitch) for s in sections for n in s["notes"]]
    mix.add(synth.lead_line(lead, mix.n, cents, level), 0.0, gain=0.26, send=0.32)
    for s in sections:
        soft = s["feel"] in ("verse", "ochi", "outro")
        for ph in expression.phrases(s["notes"]):
            t = seconds(ph[0].start) - 0.36
            if t > 0:
                mix.add(synth.breath(0.6 if soft else 0.9), t, gain=0.5, send=0.2)

    for n in hook:
        mix.add(synth.piano(synth.hz(n.pitch), seconds(n.length), vel(n)), seconds(n.start),
                gain=0.32, pan=0.1, send=0.35)
    for n in piano:
        mix.add(synth.piano(synth.hz(n.pitch), seconds(n.length), vel(n)), seconds(n.start),
                gain=0.26, pan=-0.15, send=0.3)
    for n in pad:
        mix.add(synth.pad(synth.hz(n.pitch), seconds(n.length), vel(n)), seconds(n.start),
                gain=0.1, pan=0.25, send=0.45)
    for n in bass:
        mix.add(synth.bass(synth.hz(n.pitch), seconds(n.length), vel(n)), seconds(n.start), gain=0.22)
    pans = {"kick": 0.0, "snare": 0.05, "hat": 0.4, "crash": -0.3}
    gains = {"kick": 0.4, "snare": 0.18, "hat": 0.06, "crash": 0.08}
    for tick, kind, v in hits:
        mix.add(synth.DRUMS[kind]((v / 127) ** 1.5), seconds(tick),
                gain=gains[kind], pan=pans[kind], send=0.15 if kind == "snare" else 0.0)

    audio = mix.master(wet_gain=0.28)
    wavfile.write(path, synth.SR, (audio * 32767).astype(np.int16))


def main():
    OUT.mkdir(exist_ok=True)
    marks, parts, chords, hook, bars = music.layout(madane.SECTIONS)
    total = bars * music.BAR
    sections = sung_sections(parts)
    piano, pad, bass = music.accompaniment(chords)
    hits = music.drums(marks)

    n_notes = build_vpr(sections, total, OUT / f"madane_{VERSION}.vpr")
    build_midi(marks, sections, hook, piano, pad, bass, hits, OUT / f"madane_{VERSION}.mid")

    wav = OUT / f"madane_demo_{VERSION}.wav"
    render(sections, hook, piano, pad, bass, hits, total, wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "192k",
                    str(wav.with_suffix(".mp3"))], check=True)

    pitches = [n.pitch for s in sections for n in s["notes"]]
    cues = [f"{clock(s.start)}  {s.name}" for s in marks] + [f"{clock(total)}  (end)"]
    (OUT / f"cues_{VERSION}.txt").write_text("\n".join(cues) + "\n", encoding="utf-8")
    print(f"{bars} bars, {seconds(total):.1f}s, {n_notes} sung notes, "
          f"vocal range {min(pitches)}-{max(pitches)} (MIDI)")
    print("\n".join(cues))


if __name__ == "__main__":
    main()
