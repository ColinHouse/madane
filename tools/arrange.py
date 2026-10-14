"""Build the まだね arrangement in REAPER with real sampled instruments.

    python -I tools/arrange.py [version]

Instruments are ReaSamplOmatic5000 multisamples built from the downloaded
libraries (Salamander piano, VSCO-2 CE strings, harp, glockenspiel, solo violin,
horn, flute, timpani and percussion, FingerBassYR, MuldjordKit, FreePats FSBS
guitars). Python
writes a ReaScript with every sampler zone, note and envelope embedded; REAPER
builds the project, renders the mix, an instrumental and stems, and saves it.
If out/miku.wav (or out/miku_<version>.wav) exists it replaces the synth guide vocal.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # -I drops the script dir

import numpy as np
import soundfile
from scipy.io import wavfile

import arrangement
import build
import electro
import truepeak
import orchestra
import expression
import madane
import music
import reaper_run
import sfz
import synth

ROOT = Path(__file__).resolve().parent.parent
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
VERSION = ARGS[0] if ARGS else "v3"
TAKE = Path(ARGS[1]) if len(ARGS) > 1 else None             # optional stand-in vocal take
STEMS = "--quick" not in sys.argv                           # --quick: mix and instrumental only
WORK = ROOT / "reaper" / f"madane_{VERSION}"
GEN = ROOT / "reaper" / "samples"
OUT = ROOT / "out"
LIB = ROOT / "library"
SALAMANDER_SFZ = next(LIB.glob("salamander/**/SalamanderGrandPianoV3.sfz"))
BASS_SFZ = next(LIB.glob("fingerbass_tar/**/*.sfz"))
DRUM_SFZ = next(LIB.glob("muldjord_tar/**/*.sfz"))
STRINGS = {"Violins": LIB / "vsco2/Strings/Violin Section/susVib",
           "Viola": LIB / "vsco2/Strings/Viola Section/susvib",
           "Cello": LIB / "vsco2/Strings/Cello Section/susvib"}
GTR_DIRECT_SFZ = next(LIB.glob("guitar_direct/**/*.sfz"))
GTR_DIST_SFZ = next(LIB.glob("guitar_dist2/**/*.sfz"))
MORE = LIB / "vsco2_more"          # the VSCO-2 CE extras (2026-10-14)
ORCH = GEN / "orch"                # retuned / gain-matched copies made from them
SYNTH = GEN / "synth"              # tools/synths.py: pad, pluck, sub, electronic drums, riser

# track -> (fader dB, pan, reverb send dB or None)
MIX = {
    "Miku": (-2.5, 0.0, -16), "Miku Harmony": (-2.5, -0.25, -11), "Miku Ooh": (-2.5, 0.2, -8),
    "Miku Double": (-14.0, 0.0, -12),
    "Guide vocal (synth)": (0.0, 0.0, -16),
    "Piano": (-4.0, 0.0, -10), "Piano Rel": (-4.0, 0.0, -10),
    "Violins": (3.0, -0.45, -8), "Viola": (2.0, 0.2, -8), "Cello": (-4.0, 0.45, -9),
    "Bass": (-4.5, 0.0, None),
    "Gtr Lead": (-8.0, 0.05, -12), "Gtr Rhythm L": (-17.0, -0.75, -20),
    "Gtr Rhythm R": (-17.0, 0.75, -20), "Gtr Clean": (-27.0, 0.35, -10),
    "Drums": (-5.0, 0.0, -18),
    "Harp": (-4.0, -0.30, -9), "Glock": (-3.0, 0.35, -8), "Solo Violin": (4.0, 0.15, -8),
    "Horns": (-1.0, -0.20, -9), "Flute": (-7.0, 0.30, -8), "Spiccato": (-2.0, -0.10, -14),
    "Vln Trem": (-6.0, -0.40, -10), "Timpani": (0.0, 0.0, -12), "Orch FX": (-2.0, 0.0, -10),
    "Synth Pad": (-12.0, 0.0, -10), "Synth Pluck": (-12.0, 0.1, -12), "Sub": (-15.0, 0.0, None),
    "E-Drums": (-11.0, 0.0, -20),
}
PITCHBEND_RANGE = {"Gtr Lead": 4, "Bass": 5}       # semitones; RS5K pitchbend range per track
PLATE = {"Miku": -11, "Miku Harmony": -8, "Miku Ooh": -8, "Miku Double": -9, "Drums": -16,
         "Guide vocal (synth)": -11}   # plate sends (dB)
UNDER_LEAD = {"harmony": 10.0, "ooh": 14.0}          # dB the backing vocals sit under the lead
NOTE_NAMES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8,
              "A": 9, "A#": 10, "B": 11}


def zone(files, lo, hi, root, minv=1, maxv=127, gain=0.0, vol=0.0, attack=1, release=600,
         mode="2", rr=False, noteoff=True, voices=24, pbrange=2):
    return dict(files=[str(f) for f in files], lo=lo, hi=hi, root=root, minv=minv, maxv=maxv,
                gain=gain, vol=vol, attack=attack, release=release, mode=mode, rr=rr,
                noteoff=noteoff, voices=voices, pbrange=pbrange)


def guitar_zones(sfz_path, pbrange=2, gain=-6):
    """FSBS guitars: per key range, a soft and a hard layer, four round-robins each."""
    groups = {}
    for r in sfz.parse(sfz_path):
        key = (int(r["lokey"]), int(r["hikey"]), int(r["pitch_keycenter"]),
               max(1, int(r.get("lovel", 1))), int(r.get("hivel", 127)))
        groups.setdefault(key, []).append(r["path"])
    return [zone(files, lo, hi, root, v0, v1, gain=gain, release=220, rr=len(files) > 1,
                 voices=12, pbrange=pbrange) for (lo, hi, root, v0, v1), files in sorted(groups.items())]


# --- instruments -----------------------------------------------------------------
# Salamander layer per velocity, close to the recorded dynamics: the brightness comes
# from playing louder where the music is louder, plus an air shelf, not from swapping layers.
PIANO_LAYERS = [(4, 1, 36), (7, 37, 54), (10, 55, 70), (12, 71, 86), (14, 87, 104), (16, 105, 127)]


def piano_zones(used):
    zones = {}
    for r in sfz.parse(SALAMANDER_SFZ):
        m = re.search(r"(?:^|[\\/])([A-G]#?)(\d)v(\d+)\.wav$", r.get("sample", ""))
        if not m or r.get("trigger") == "release" or "lokey" not in r:
            continue
        root = 12 * (int(m[2]) + 1) + NOTE_NAMES[m[1]]      # the file name is the key center
        key = (int(r["lokey"]), int(r["hikey"]), root)
        zones.setdefault(key, {})[int(m[3])] = r["path"]
    out = []
    for (lo, hi, root), layers in sorted(zones.items()):
        if hi < min(used) or lo > max(used):
            continue
        for layer, v0, v1 in PIANO_LAYERS:
            out.append(zone([layers[layer]], lo, hi, root, v0, v1, gain=-10, release=700))
    return out


def piano_release_zones():
    """Salamander's string-resonance releases (soft and loud layers), played on note-off."""
    out = []
    for r in sfz.parse(SALAMANDER_SFZ):
        if r.get("trigger") != "release" or "harm" not in r.get("sample", ""):
            continue
        lo, hi = int(r["lokey"]), int(r["hikey"])
        root = int(r.get("pitch_keycenter", (lo + hi) // 2))
        v0, v1 = int(r.get("lovel", 1)), int(r.get("hivel", 127))
        out.append(zone([r["path"]], lo, hi, root, v0, v1, gain=-30, vol=float(r.get("volume", 0)),
                        noteoff=False, voices=6))
    return out


def piano_releases(notes, tps):
    """A release note at every piano note-off, quieter the longer the key was held (rt_decay)."""
    out = []
    for n in notes:
        held = n.length / tps
        v = int(n.velocity * 10 ** (-6 * held / 20))
        if v >= 8:
            out.append(music.Note(n.start + n.length, music.UNIT, n.pitch, v))
    return out


def string_zones(folder):
    samples = {}
    for f in folder.glob("*.wav"):
        m = re.search(r"_([A-G]#?)(\d)_v(\d)", f.name)
        note = 12 * (int(m[2]) + 2) + NOTE_NAMES[m[1]]       # VSCO-2 names middle C "C3"
        samples.setdefault(note, {}).setdefault("soft" if m[3] == "1" else "loud", []).append(f)
    notes = sorted(samples)
    out = []
    for i, n in enumerate(notes):
        lo = 0 if i == 0 else (notes[i - 1] + n) // 2 + 1
        hi = 127 if i == len(notes) - 1 else (n + notes[i + 1]) // 2
        for layer, (v0, v1) in (("soft", (1, 64)), ("loud", (65, 127))):
            files = sorted(samples[n].get(layer) or samples[n]["soft"])
            # the loud VSCO-2 layer is ~6 dB hotter; level it so crossing velocity 65 is smooth
            out.append(zone(files, lo, hi, n, v0, v1, gain=-5, vol=6 if layer == "soft" else 0,
                            attack=90, release=550, rr=len(files) > 1))
    return out


def bass_zones():
    """FingerBassYR covers D1–A2; the top zone is stretched to D3 so lines can climb."""
    regions = sfz.parse(BASS_SFZ)
    top = max(int(r["hikey"]) for r in regions)
    return [zone([r["path"]], int(r["lokey"]), 50 if int(r["hikey"]) == top else int(r["hikey"]),
                 int(r["pitch_keycenter"]), gain=-12, release=450, voices=8, pbrange=PITCHBEND_RANGE["Bass"])
            for r in regions]


KIT = {   # GM note -> MuldjordKit key
    arrangement.KICK: 48, arrangement.SNARE: 50, arrangement.STICK: 50, arrangement.HH: 52,
    arrangement.HH_OPEN: 53, arrangement.RIDE: 54, arrangement.CRASH: 59,
    arrangement.TOM_HI: 61, arrangement.TOM_MID: 62, arrangement.TOM_LOW: 64,
}
DRUM_VEL = [(1, 40), (41, 70), (71, 95), (96, 127)]


def drum_zones():
    groups = {}
    for r in sfz.parse(DRUM_SFZ):
        groups.setdefault(int(r["lokey"]), {}).setdefault(
            (int(r.get("lovel", 0)), int(r.get("hivel", 127))), []).append(r["path"])
    out = []
    for gm, key in KIT.items():
        layers = [groups[key][v] for v in sorted(groups[key])]
        if gm == arrangement.STICK:          # side-stick stand-in: the softest snare layers
            layers = layers[: max(2, len(layers) // 4)]
        picks = [layers[round(i * (len(layers) - 1) / 3)] for i in range(4)]
        for files, (v0, v1) in zip(picks, DRUM_VEL):
            out.append(zone(files, gm, gm, gm, v0, v1, gain=-6, mode="1", rr=len(files) > 1,
                            noteoff=False, voices=8))
    rev = GEN / "reverse_crash.wav"
    out.append(zone([rev], arrangement.REVERSE, arrangement.REVERSE, arrangement.REVERSE,
                    mode="1", noteoff=False, voices=2))
    return out


def make_reverse_crash(seconds=2.6):
    GEN.mkdir(parents=True, exist_ok=True)
    groups = {}
    for r in sfz.parse(DRUM_SFZ):
        if int(r["lokey"]) == KIT[arrangement.CRASH]:
            groups.setdefault(int(r.get("hivel", 127)), []).append(r["path"])
    data, sr = soundfile.read(groups[max(groups)][0], always_2d=True)
    data = data[: int(seconds * sr)][::-1]
    t = np.linspace(0, 1, len(data))[:, None]
    data = data * t ** 2.2
    data[-int(0.01 * sr):] *= np.linspace(1, 0, int(0.01 * sr))[:, None]
    wavfile.write(GEN / "reverse_crash.wav", sr, (data / np.abs(data).max() * 0.9).astype(np.float32))
    return len(data) / sr


# --- orchestral extras (VSCO-2 CE) ------------------------------------------------
def _note_of(name, octave, offset=0):
    return 12 * (int(octave) + 1) + NOTE_NAMES[name] + offset


def _spread(notes, lo_limit=0, hi_limit=127):
    """Sorted sample roots -> [(lo, hi, root)] splitting the keyboard between neighbours."""
    out = []
    for i, n in enumerate(notes):
        lo = lo_limit if i == 0 else (notes[i - 1] + n) // 2 + 1
        hi = hi_limit if i == len(notes) - 1 else (n + notes[i + 1]) // 2
        out.append((max(lo, lo_limit), min(hi, hi_limit), n))
    return out


def gained_copies(files, gain_db, tag):
    """Copies of quiet percussive samples with one common gain, so their relative levels stay."""
    ORCH.mkdir(parents=True, exist_ok=True)
    out = []
    for f in files:
        dst = ORCH / f"{tag}_{f.name}"
        if not dst.exists():
            x, sr = soundfile.read(str(f), always_2d=True)
            soundfile.write(str(dst), x * 10 ** (gain_db / 20), sr, subtype="FLOAT")
        out.append(dst)
    return out


def layered_zones(files, pattern, offset, layers, lo_limit=0, hi_limit=127, **kw):
    """Multisample from file names: `pattern` captures note, octave and (optionally) layer.

    layers: [(layer name or None, min velocity, max velocity)]; a missing layer
    falls back to the nearest one recorded for that note.
    """
    found = {}
    for f in files:
        m = re.search(pattern, f.name)
        if m:
            layer = m.group(3) if (m.lastindex or 0) >= 3 else None
            found.setdefault(_note_of(m[1], m[2], offset), {}).setdefault(layer, []).append(f)
    names = [l for l, _, _ in layers]
    out = []
    for lo, hi, n in _spread(sorted(found), lo_limit, hi_limit):
        if lo > hi:
            continue
        for i, (layer, v0, v1) in enumerate(layers):
            have = found[n]
            if layer not in have:     # nearest recorded layer
                layer = min(have, key=lambda l: abs(names.index(l) - i) if l in names else 99)
            fs = sorted(have[layer])
            out.append(zone(fs, lo, hi, n, v0, v1, rr=len(fs) > 1, **kw))
    return out


def harp_zones():
    files = gained_copies(sorted((MORE / "Strings/Harp").glob("*.wav")), 14, "harp")
    return layered_zones(files, r"KSHarp_([A-G]#?)(\d)_", 0, [(None, 1, 127)],
                         gain=-16, release=1500, noteoff=False, voices=32)


def glock_zones():
    files = gained_copies(sorted((MORE / "Percussion/Glock").glob("*.wav")), 14, "glock")
    return layered_zones(files, r"glock_medium_([A-G]#?)(\d)", 12, [(None, 1, 127)],
                         gain=-14, release=1500, noteoff=False, voices=8)


def violin_zones():
    files = sorted((MORE / "Strings/Solo Violin/Arco Vib").glob("*.wav"))
    return layered_zones(files, r"ArcoVib_([A-G]#?)(\d)_(p|f)", 0, [("p", 1, 45), ("f", 46, 127)],
                         gain=-4, attack=45, release=320, voices=4)


def horn_zones():
    files = sorted((MORE / "Brass/F Horn/sus").glob("*.wav"))
    return layered_zones(files, r"sus_([A-G]#?)(\d)_(v\d)", 12, [("v1", 1, 58), ("v2", 59, 84), ("v3", 85, 127)],
                         gain=-6, attack=70, release=380, voices=8)


def flute_zones():
    files = sorted((MORE / "Woodwinds/Flute/susvib").glob("*.wav"))
    return layered_zones(files, r"susvib_([A-G]#?)(\d)_", 12, [(None, 1, 127)],
                         gain=-8, attack=50, release=260, voices=4)


def spiccato_zones():
    """One section across registers: cellos up to D3, violas to D4, violins above."""
    out = []
    for folder, pat, lo, hi in (("Strings/Cello Section/spic", r"spic_([A-G]#?)(\d)_(v\d)", 0, 50),
                                ("Strings/Viola Section/spic", r"spic_([A-G]#?)(\d)_(v\d)", 51, 62),
                                ("Strings/Violin Section/Spic", r"Spic_([A-G]#?)(\d)_(v\d)", 63, 127)):
        files = sorted((MORE / folder).glob("*.wav"))
        out += layered_zones(files, pat, 12, [("v1", 1, 76), ("v2", 77, 127)], lo, hi,
                             gain=-6, release=120, noteoff=False, voices=8)
    return out


def tremolo_zones():
    files = sorted((MORE / "Strings/Violin Section/Trem").glob("*.wav"))
    return layered_zones(files, r"Trem_([A-G]#?)(\d)_(v\d)", 12, [("v1", 1, 70), ("v2", 71, 127)],
                         gain=-6, attack=120, release=500, voices=8)


TIMP_PRINCIPAL = {2: 46.8, 3: 49.45}     # measured principal tones of drums 2 (about B2) and 3 (C#3/D3)


def _retune(x, semis):
    from scipy.signal import resample_poly
    down = int(round(1000 * 2 ** (semis / 12)))
    return resample_poly(x, 1000, down, axis=0)


def timpani_zones():
    """Hits retuned to A2 Bb2 D3 Eb3, and crescendo rolls (a bar / half a bar) ending on the beat."""
    ORCH.mkdir(parents=True, exist_ok=True)
    out = []
    bar_s = build.seconds(music.BAR)
    for pitch in orchestra.TIMP_PITCHES:
        drum = 2 if pitch < 48 else 3
        shift = pitch - TIMP_PRINCIPAL[drum]
        for layer, v0, v1 in (("v1", 1, 60), ("v3", 61, 95), ("v4", 96, 127)):
            files = []
            for rr in ("rr1", "rr2"):
                src = MORE / f"Percussion/Timpani/Timpani{drum}_Hit_{layer}_{rr}_Sum.wav"
                if not src.exists():
                    src = MORE / f"Percussion/Timpani/Timpani{drum}_Hit_v3_{rr}_Sum.wav"
                dst = ORCH / f"timp_{pitch}_{layer}_{rr}.wav"
                if not dst.exists():
                    x, sr = soundfile.read(str(src), always_2d=True)
                    soundfile.write(str(dst), _retune(x, shift) * 10 ** (10 / 20), sr, subtype="FLOAT")
                files.append(dst)
            out.append(zone(files, pitch, pitch, pitch, v0, v1, gain=-14, mode="1", rr=True,
                            noteoff=False, voices=4))
        for key, seconds in ((pitch + orchestra.ROLL, bar_s), (pitch + orchestra.ROLL_HALF, bar_s / 2)):
            dst = ORCH / f"timp_roll_{pitch}_{seconds:.2f}s.wav"
            if not dst.exists():
                x, sr = soundfile.read(str(MORE / f"Percussion/Timpani/Rolls/Timpani{drum}_Roll_v5_rr1_Sum.wav"),
                                       always_2d=True)
                y = _retune(x[int(1.0 * sr):], shift)[: int(seconds * sr)]
                ramp = np.linspace(-30, 0, len(y))[:, None]            # crescendo, linear in dB
                y = y * 10 ** (ramp / 20)
                y[-int(0.03 * sr):] *= np.linspace(1, 0, int(0.03 * sr))[:, None]
                soundfile.write(str(dst), y * 10 ** (8 / 20), sr, subtype="FLOAT")
            out.append(zone([dst], key, key, key, gain=-6, mode="1", noteoff=False, voices=2))
    return out


def make_reverse_piano(name, pitches, seconds):
    """A Salamander chord, reversed, so it swells into the downbeat (ear candy)."""
    ORCH.mkdir(parents=True, exist_ok=True)
    dst = ORCH / f"revpiano_{name}.wav"
    if dst.exists():
        return dst
    zones = {}
    for r in sfz.parse(SALAMANDER_SFZ):
        m = re.search(r"(?:^|[\\/])([A-G]#?)(\d)v12\.wav$", r.get("sample", ""))
        if m and r.get("trigger") != "release" and "lokey" in r:
            zones[(int(r["lokey"]), int(r["hikey"]))] = (12 * (int(m[2]) + 1) + NOTE_NAMES[m[1]], r["path"])
    mix, sr = None, 44100
    for p in pitches:
        root, path = next(v for (lo, hi), v in zones.items() if lo <= p <= hi)
        x, sr = soundfile.read(str(path), always_2d=True)
        y = _retune(x, p - root)[: int((seconds + 0.6) * sr)]
        mix = y if mix is None else mix[: len(y)] + y[: len(mix)]
    y = mix[::-1][-int(seconds * sr):]                        # end exactly on the (reversed) attack
    y *= np.linspace(0, 1, len(y))[:, None] ** 1.5
    y[-int(0.004 * sr):] *= np.linspace(1, 0, int(0.004 * sr))[:, None]
    soundfile.write(str(dst), y / np.abs(y).max() * 0.5, sr, subtype="FLOAT")
    return dst


def make_sub_drop(seconds=2.4, sr=44100):
    """A falling sine 58 -> 32 Hz with a touch of second harmonic, for weight under big downbeats."""
    ORCH.mkdir(parents=True, exist_ok=True)
    dst = ORCH / "sub_drop.wav"
    if dst.exists():
        return dst
    t = np.arange(int(seconds * sr)) / sr
    f = 32 + 26 * np.exp(-t / 0.25)
    phase = 2 * np.pi * np.cumsum(f) / sr
    env = (1 - np.exp(-t / 0.004)) * np.exp(-t / 0.9)
    y = env * (np.sin(phase) + 0.25 * np.sin(2 * phase))
    y[-int(0.02 * sr):] *= np.linspace(1, 0, int(0.02 * sr))
    y = y / np.abs(y).max() * 0.7
    soundfile.write(str(dst), np.stack([y, y], axis=1), sr, subtype="FLOAT")
    return dst


def synth_zones(prefix, **kw):
    files = {int(f.stem.split("_")[1]): f for f in SYNTH.glob(f"{prefix}_*.wav")}
    return [zone([files[n]], lo, hi, n, **kw) for lo, hi, n in _spread(sorted(files))]


def electro_zones():
    one = lambda name, key, gain: zone([SYNTH / name], key, key, key, gain=gain, mode="1", noteoff=False, voices=6)
    return {"Synth Pad": synth_zones("pad", gain=-10, attack=350, release=1400, voices=16),
            "Synth Pluck": synth_zones("pluck", gain=-10, release=300, noteoff=False, voices=16),
            "Sub": synth_zones("sub", gain=-6, attack=15, release=200, voices=4),
            "E-Drums": [one("ekick.wav", electro.EKICK, -12), one("eclap.wav", electro.ECLAP, -12),
                        one("ehat.wav", electro.EHAT, -16), one("riser.wav", electro.RISER, -6)]}


def effects_zones():
    bell = gained_copies([MORE / "Percussion/BellTree_Stroke1_v1_Sum.wav"], 22, "bell")
    cym = [MORE / "Percussion/susCymb1-cresc-Median_v1.wav"]
    rev_d = make_reverse_piano("D", (43, 50, 57, 59, 66, 74), orchestra.REV_PIANO_S)     # Gmaj7 in D
    rev_eb = make_reverse_piano("Eb", (44, 51, 58, 60, 67, 75), orchestra.REV_PIANO_S)   # A♭maj7 in E♭
    one = lambda f, key, gain: zone([f], key, key, key, gain=gain, mode="1", noteoff=False, voices=2)
    return [zone(bell, orchestra.BELL, orchestra.BELL, orchestra.BELL, gain=-8, mode="1", noteoff=False, voices=3),
            one(cym[0], orchestra.CYM_SWELL, -10), one(rev_d, orchestra.REV_PIANO, -12),
            one(rev_eb, orchestra.REV_PIANO_UP, -12), one(make_sub_drop(), orchestra.SUB_HIT, -14)]


# --- envelopes -------------------------------------------------------------------
# a mix engineer's vocal ride: the voice sits back in sparse verses and up in the big choruses
VOCAL_RIDE = {"1A": -4.0, "1B": -1.0, "1サビ": 1.0, "2A": -1.0, "2B": -0.5, "2サビ": 2.0, "Cメロ": 1.0,
              "落ちサビ": -3.5, "ラスサビ": 2.5, "Outro": 0.0}


def vocal_ride(marks):
    pts = [(0, 0.0)]
    for m in marks:
        a, b = build.seconds(m.start), build.seconds(m.start + m.bars * music.BAR)
        db = VOCAL_RIDE.get(m.name, 0.0)
        pts += [(a, db), (b - 0.25, db)]
    return pts


def section_dip(marks, name, db):
    """A volume envelope that sits `db` lower for one section."""
    m = next(m for m in marks if m.name == name)
    a, b = build.seconds(m.start), build.seconds(m.start + m.bars * music.BAR)
    return [(0, 0), (a - 0.05, 0), (a, db), (b - 0.05, db), (b, 0)]


def string_envelope(marks, total_s):
    at = {m.name: build.seconds(m.start) for m in marks}
    return [(0, 0), (at["1B"], -9), (at["1サビ"], 0), (at["2B"], -6), (at["2サビ"], 1),
            (at["2サビ"] + 3, 0), (at["Cメロ"], -8), (at["落ちサビ"] - 0.4, 2), (at["落ちサビ"], -2),
            (at["Outro"], 0), (total_s, -30)]


# --- script generation -----------------------------------------------------------
def lua_value(v):
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "{" + ",".join(lua_value(x) for x in v) + "}"
    if isinstance(v, dict):
        return "{" + ",".join(f"{k}={lua_value(x)}" for k, x in v.items()) + "}"
    return "[[" + str(v) + "]]"


def lua_notes(notes):
    return "{" + ",".join(f"{{{n.start / music.TPQ:.4f},{n.length / music.TPQ:.4f},{n.pitch},{n.velocity}}}"
                          for n in notes) + "}"


TRACK_ORDER = ("Piano", "Piano Rel", "Violins", "Viola", "Cello", "Bass", "Gtr Lead", "Gtr Rhythm L",
               "Gtr Rhythm R", "Gtr Clean", "Drums", "Harp", "Glock", "Solo Violin", "Horns",
               "Flute", "Spiccato", "Vln Trem", "Timpani", "Orch FX", "Synth Pad", "Synth Pluck", "Sub",
               "E-Drums")


def lua_bends(points, semis_range):
    """Pitch-bend points (tick, semitones) -> {{qn, 14-bit value}, ...}."""
    out = []
    for t, s in points:
        v = int(round(8192 + max(-1.0, min(1.0, s / semis_range)) * 8191))
        out.append(f"{{{t / music.TPQ:.4f},{v}}}")
    return "{" + ",".join(out) + "}"


def write_script(path, marks, total_ticks, parts, zones, envelopes, vocal, bends):
    regions = [(build.seconds(m.start), build.seconds(m.start + m.bars * music.BAR), m.name) for m in marks]
    tracks = []
    for name in TRACK_ORDER:
        b = lua_bends(bends.get(name, []), PITCHBEND_RANGE.get(name, 2))
        tracks.append(f'{{name="{name}", zones={lua_value(zones[name])}, notes={lua_notes(parts[name])}, '
                      f'env={lua_value(envelopes.get(name, []))}, bends={b}}}')
    subs = {
        "@BPM@": str(madane.BPM), "@TOTAL_QN@": f"{total_ticks / music.TPQ:.4f}",
        "@END_S@": f"{build.seconds(total_ticks) + 5:.3f}", "@REGIONS@": lua_value(regions),
        "@TRACKS@": ",\n".join(tracks),
        "@MIX@": "{" + ",".join(f'["{k}"]={lua_value(v)}' for k, v in MIX.items()) + "}",
        "@WORK@": lua_value(WORK), "@OUT@": lua_value(OUT), "@VERSION@": VERSION,
        "@MIKU@": lua_value(vocal["miku"]) if vocal["miku"] else "nil",
        "@MIKU_ITEMS@": lua_value(vocal["items"]),
        "@GUIDE@": lua_value(vocal["guide"]) if vocal["guide"] else "nil",
        "@HARMONY@": lua_value(vocal["harmony"]) if vocal.get("harmony") else "nil",
        "@OOH@": lua_value(vocal["ooh"]) if vocal.get("ooh") else "nil",
        "@VOCAL_RIDE@": lua_value(vocal_ride(marks)),
        "@STEMS@": "true" if STEMS else "false",
        "@DOUBLE@": lua_value(vocal.get("double")) if vocal.get("double") else "nil",
        "@PLATE@": "{" + ",".join(f'["{k}"]={v}' for k, v in PLATE.items()) + "}",
    }
    lua = LUA
    for k, v in subs.items():
        lua = lua.replace(k, v)
    path.write_text(lua, encoding="utf-8")


LUA = r'''
-- Generated by tools/arrange.py
local WORK, OUT = @WORK@, @OUT@
local log = io.open(WORK .. "\\build_log.txt", "w")
local function say(s) log:write(os.date("%H:%M:%S ") .. s .. "\n"); log:flush() end
local TRACKS = {
@TRACKS@
}
local MIX = @MIX@

local function parse(s)
  if s:find("inf") then return s:find("-inf") and -1e9 or 1e9 end
  return tonumber(s:match("[-+]?%d+%.?%d*")) or 0
end
local function set(tr, fx, idx, target)
  local function at(v) local _, s = reaper.TrackFX_FormatParamValueNormalized(tr, fx, idx, v, ""); return parse(s) end
  local lo, hi, rising = 0.0, 1.0, at(1) >= at(0)
  for _ = 1, 40 do
    local mid = (lo + hi) / 2
    if (at(mid) < target) == rising then lo = mid else hi = mid end
  end
  reaper.TrackFX_SetParamNormalized(tr, fx, idx, (lo + hi) / 2)
end
local function db_norm(db) return 10 ^ (db / 20) / 2 end   -- REAPER's dB slider: amp = 2 * v

local function add_track(name)
  local i = reaper.CountTracks(0)
  reaper.InsertTrackAtIndex(i, true)
  local tr = reaper.GetTrack(0, i)
  reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", name, true)
  return tr
end
local function add_midi(tr, notes, bends)
  local item = reaper.CreateNewMIDIItemInProj(tr, 0, @TOTAL_QN@, true)
  local take = reaper.GetActiveTake(item)
  for _, n in ipairs(notes) do
    reaper.MIDI_InsertNote(take, false, false, reaper.MIDI_GetPPQPosFromProjQN(take, n[1]),
      reaper.MIDI_GetPPQPosFromProjQN(take, n[1] + n[2]), 0, n[3], n[4], true)
  end
  for _, b in ipairs(bends or {}) do              -- pitch bend: status 0xE0, LSB, MSB
    reaper.MIDI_InsertCC(take, false, false, reaper.MIDI_GetPPQPosFromProjQN(take, b[1]),
      0xE0, 0, b[2] & 0x7F, b[2] >> 7)
  end
  reaper.MIDI_Sort(take)
end
-- place part of an audio file: position in the song, offset into the file, length, fades
local function add_audio(tr, path, pos, offs, len)
  local item = reaper.AddMediaItemToTrack(tr)
  local take = reaper.AddTakeToMediaItem(item)
  local src = reaper.PCM_Source_CreateFromFile(path)
  reaper.SetMediaItemTake_Source(take, src)
  reaper.SetMediaItemTakeInfo_Value(take, "D_STARTOFFS", offs or 0)
  reaper.SetMediaItemInfo_Value(item, "D_POSITION", pos or 0)
  reaper.SetMediaItemInfo_Value(item, "D_LENGTH", len or reaper.GetMediaSourceLength(src))
  reaper.SetMediaItemInfo_Value(item, "D_FADEINLEN", 0.01)
  reaper.SetMediaItemInfo_Value(item, "D_FADEOUTLEN", 0.05)
end
-- pick an entry of an enum-style parameter by (part of) its displayed name
local function set_enum(tr, fx, idx, needle)
  for i = 0, 1000 do
    local v = i / 1000
    local _, s = reaper.TrackFX_FormatParamValueNormalized(tr, fx, idx, v, "")
    if s:find(needle, 1, true) then reaper.TrackFX_SetParamNormalized(tr, fx, idx, v); return s end
  end
  say("enum not found: " .. needle)
end
-- an enum entry by its exact displayed text (the 1175's ratios repeat as deprecated "Blown Capacitor" entries)
local function set_exact(tr, fx, idx, text)
  for i = 0, 1000 do
    local v = i / 1000
    local _, s = reaper.TrackFX_FormatParamValueNormalized(tr, fx, idx, v, "")
    if s == text then reaper.TrackFX_SetParamNormalized(tr, fx, idx, v); return s end
  end
  say("enum entry not found: " .. text)
end
local function sampler(tr, z)
  local fx = reaper.TrackFX_AddByName(tr, "ReaSamplOmatic5000 (Cockos)", false, -1)
  for i, f in ipairs(z.files) do reaper.TrackFX_SetNamedConfigParm(tr, fx, "FILE" .. (i - 1), f) end
  reaper.TrackFX_SetNamedConfigParm(tr, fx, "DONE", "")
  reaper.TrackFX_SetNamedConfigParm(tr, fx, "MODE", z.mode)
  reaper.TrackFX_SetParamNormalized(tr, fx, 3, z.lo / 127)
  reaper.TrackFX_SetParamNormalized(tr, fx, 4, z.hi / 127)
  if z.mode == "2" then reaper.TrackFX_SetParamNormalized(tr, fx, 5, 0.5 + (z.lo - z.root) / 160) end
  reaper.TrackFX_SetParamNormalized(tr, fx, 17, z.minv / 127)
  reaper.TrackFX_SetParamNormalized(tr, fx, 18, z.maxv / 127)
  reaper.TrackFX_SetParamNormalized(tr, fx, 2, db_norm(z.gain))
  reaper.TrackFX_SetParamNormalized(tr, fx, 0, db_norm(z.vol))
  reaper.TrackFX_SetParamNormalized(tr, fx, 9, z.attack / 2000)
  reaper.TrackFX_SetParamNormalized(tr, fx, 10, z.release / 2000)
  reaper.TrackFX_SetParamNormalized(tr, fx, 11, z.noteoff and 1 or 0)
  reaper.TrackFX_SetParamNormalized(tr, fx, 20, z.rr and 1 or 0)
  reaper.TrackFX_SetParamNormalized(tr, fx, 8, (z.voices - 1) / 63)
  reaper.TrackFX_SetParamNormalized(tr, fx, 16, z.pbrange / 12)
end
local function volume_envelope(tr, pts)
  if #pts == 0 then return end
  reaper.SetOnlyTrackSelected(tr)
  reaper.Main_OnCommand(40406, 0)            -- show (create) the track volume envelope
  local env = reaper.GetTrackEnvelopeByName(tr, "Volume")
  if not env then say("no volume envelope"); return end
  local mode = reaper.GetEnvelopeScalingMode(env)
  for _, p in ipairs(pts) do
    reaper.InsertEnvelopePoint(env, p[1], reaper.ScaleToEnvelopeMode(mode, 10 ^ (p[2] / 20)), 0, 0, false, true)
  end
  reaper.Envelope_SortPoints(env)
end
local function eq(tr, hp, shelf_hz, shelf_db)
  local fx = reaper.TrackFX_AddByName(tr, "ReaEQ (Cockos)", false, -1)
  reaper.TrackFX_SetNamedConfigParm(tr, fx, "BANDENABLED4", "1")   -- band 5 (high pass) is off by default
  set(tr, fx, 12, hp)
  if shelf_hz then set(tr, fx, 9, shelf_hz); set(tr, fx, 10, shelf_db) end
end
-- a REAPER-bundled JS effect, parameters as {index, displayed value}
local function js(tr, name, params)
  local fx = reaper.TrackFX_AddByName(tr, "JS: " .. name, false, -1)
  if fx < 0 then say("missing JS: " .. name); return fx end
  for _, p in ipairs(params or {}) do set(tr, fx, p[1], p[2]) end
  return fx
end
local function bus(name, vol_db)
  local tr = add_track(name)
  reaper.SetMediaTrackInfo_Value(tr, "D_VOL", 10 ^ (vol_db / 20))
  return tr
end
local function send(src, dst, db)
  local snd = reaper.CreateTrackSend(src, dst)
  reaper.SetTrackSendInfo_Value(src, 0, snd, "D_VOL", 10 ^ (db / 20))
end
-- bands: {freq param index (0 low shelf, 3 band 2, 6 band 3, 9 high shelf), Hz, dB}
local function eq_bands(tr, hp, bands)
  local fx = reaper.TrackFX_AddByName(tr, "ReaEQ (Cockos)", false, -1)
  if hp then reaper.TrackFX_SetNamedConfigParm(tr, fx, "BANDENABLED4", "1"); set(tr, fx, 12, hp) end
  for _, b in ipairs(bands) do set(tr, fx, b[1], b[2]); set(tr, fx, b[1] + 1, b[3]) end
end
local function comp(tr, thr, ratio, att, rel, makeup)
  local fx = reaper.TrackFX_AddByName(tr, "ReaComp (Cockos)", false, -1)
  set(tr, fx, 0, thr); set(tr, fx, 1, ratio); set(tr, fx, 2, att); set(tr, fx, 3, rel)
  set(tr, fx, 14, 6); set(tr, fx, 11, makeup or 0)
end

reaper.SetCurrentBPM(0, @BPM@, false)
for _, r in ipairs(@REGIONS@) do reaper.AddProjectMarker2(0, true, r[1], r[2], r[3], -1, 0) end

local vocals = {}
local miku = add_track("Miku"); vocals[#vocals + 1] = miku
if @MIKU@ then   -- the exported vocal, re-timed section group by section group
  for _, it in ipairs(@MIKU_ITEMS@) do add_audio(miku, @MIKU@, it[1], it[2], it[3]) end
end
if @HARMONY@ then
  local h = add_track("Miku Harmony"); vocals[#vocals + 1] = h
  add_audio(h, @HARMONY@)
end
if @OOH@ then
  local o = add_track("Miku Ooh"); vocals[#vocals + 1] = o
  add_audio(o, @OOH@)
end
local guide = nil
if @GUIDE@ then
  guide = add_track("Guide vocal (synth)"); vocals[#vocals + 1] = guide
  add_audio(guide, @GUIDE@)
end
local vdelay = bus("Vocal Delay", -10)                 -- a ping-pong quarter-note echo, filtered
js(vdelay, "sstillwell/delay_pong", {{0, 0}, {1, -9}, {3, 0}, {4, -120}, {5, 100}, {6, 0.25}})
eq_bands(vdelay, 450, {{9, 6000, -6}})
for _, tr in ipairs(vocals) do
  volume_envelope(tr, @VOCAL_RIDE@)
  local _, name = reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", "", false)
  if name == "Miku Harmony" or name == "Miku Ooh" then
    eq(tr, 160, 6500, -2)
    comp(tr, -22, 3, 8, 150, 2)
    js(tr, "loser/StereoEnhancer", {{0, 100}, {1, 600}, {2, 150}})
  else
    eq_bands(tr, 110, {{3, 300, -2.5}, {6, 4200, 2.5}, {9, 11000, 3}})
    local c = js(tr, "sstillwell/1175", {{0, -10}, {2, 2}, {3, 400}, {4, 120}})        -- fast, catches peaks
    set_exact(tr, c, 1, "4")
    comp(tr, -16, 2.5, 15, 250, 2)                                                       -- levels the phrases
    js(tr, "Liteon/deesser", {{3, 6800}, {4, 1.5}, {5, -32}, {6, 4}})
    js(tr, "loser/Exciter", {{0, 7000}, {2, 22}, {3, -14}})
    js(tr, "loser/Saturation", {{0, 12}})
  end
  send(tr, vdelay, name == "Miku" and -12 or -18)
end
if @DOUBLE@ then                                        -- a wide chorus double of the lead in the big choruses
  local d = add_track("Miku Double"); vocals[#vocals + 1] = d
  for _, it in ipairs(@DOUBLE@) do add_audio(d, @MIKU@, it[1], it[1], it[2]) end
  eq_bands(d, 150, {{9, 9000, 2}})
  comp(d, -24, 4, 5, 120, 2)
  js(d, "sstillwell/chorus_stereo", {{0, 18}, {1, 2}, {2, 0.35}, {4, 0}, {5, -120}, {6, 0.12}})
  js(d, "loser/StereoEnhancer", {{0, 100}, {1, 300}, {2, 200}})
  volume_envelope(d, @VOCAL_RIDE@)
end

local by_name = {}
for _, t in ipairs(TRACKS) do
  local tr = add_track(t.name)
  by_name[t.name] = tr
  for _, z in ipairs(t.zones) do sampler(tr, z) end
  add_midi(tr, t.notes, t.bends)
  volume_envelope(tr, t.env)
  say(t.name .. ": " .. #t.zones .. " sampler zones, " .. #t.notes .. " notes, " .. #t.bends .. " bends")
end

-- guitar tone chains
do  -- lead: DI -> distortion -> Marshall JCM800 amp/cab -> EQ -> dotted-eighth delay
  local tr = by_name["Gtr Lead"]
  local d = reaper.TrackFX_AddByName(tr, "JS: guitar/distortion", false, -1)
  set(tr, d, 0, 30); set(tr, d, 1, 5); set(tr, d, 2, -8)
  reaper.TrackFX_SetParamNormalized(tr, d, 3, 1)                    -- channel mode: stereo
  local a = reaper.TrackFX_AddByName(tr, "JS: guitar/amp-model", false, -1)
  say("lead amp: " .. tostring(set_enum(tr, a, 0, "JCM800")))
  eq(tr, 110, 6000, -3)
  comp(tr, -18, 3, 5, 80, 2)
  local dl = reaper.TrackFX_AddByName(tr, "ReaDelay (Cockos)", false, -1)
  set(tr, dl, 0, -14); set(tr, dl, 1, 0); set(tr, dl, 4, 1.5); set(tr, dl, 5, -9)
  set(tr, dl, 6, 5000); set(tr, dl, 7, 300)
end
for _, name in ipairs({"Gtr Rhythm L", "Gtr Rhythm R"}) do   -- already amped samples
  eq_bands(by_name[name], 90, {{3, 300, -2.5}, {9, 7000, -2}})
end
do  -- clean: DI -> chorus -> Fender Bassman amp/cab -> quarter-note delay
  local tr = by_name["Gtr Clean"]
  local ch = reaper.TrackFX_AddByName(tr, "JS: guitar/chorus", false, -1)
  set(tr, ch, 1, 2); set(tr, ch, 2, 0.6); set(tr, ch, 4, -6); set(tr, ch, 5, -2)
  local a = reaper.TrackFX_AddByName(tr, "JS: guitar/amp-model", false, -1)
  say("clean amp: " .. tostring(set_enum(tr, a, 0, "Bassman")))
  eq(tr, 120, 7000, -1)
  local dl = reaper.TrackFX_AddByName(tr, "ReaDelay (Cockos)", false, -1)
  set(tr, dl, 0, -16); set(tr, dl, 1, 0); set(tr, dl, 4, 2); set(tr, dl, 5, -12)
  set(tr, dl, 6, 4500); set(tr, dl, 7, 300)
end
do  -- piano: HPF 40, -3 dB at 300 Hz (band 2), +1.5 dB at 3.5 kHz (band 3), +4 dB air shelf
  local tr = by_name["Piano"]
  eq(tr, 40, 9000, 4)
  local fx = reaper.TrackFX_GetCount(tr) - 1
  set(tr, fx, 3, 300); set(tr, fx, 4, -3); set(tr, fx, 6, 3500); set(tr, fx, 7, 1.5)
  comp(tr, -20, 1.6, 25, 150, 1)
  js(tr, "loser/Saturation", {{0, 10}})
  js(tr, "loser/StereoEnhancer", {{0, 100}, {1, 350}, {2, 135}})
end
eq(by_name["Piano Rel"], 60, 9000, 3)
eq(by_name["Violins"], 150, 9000, 0.5)
js(by_name["Violins"], "loser/StereoEnhancer", {{0, 100}, {1, 400}, {2, 150}})
js(by_name["Harp"], "loser/StereoEnhancer", {{0, 100}, {1, 500}, {2, 160}})
js(by_name["Glock"], "loser/StereoEnhancer", {{0, 100}, {1, 800}, {2, 170}})
js(by_name["Spiccato"], "loser/StereoEnhancer", {{0, 100}, {1, 400}, {2, 140}})
eq_bands(by_name["Viola"], 120, {{3, 350, -2}, {9, 8000, -1}})
eq_bands(by_name["Cello"], 50, {{3, 300, -1.5}, {9, 7000, -2}})
eq_bands(by_name["Harp"], 80, {{3, 300, -3}, {9, 9000, 1.5}})
eq(by_name["Glock"], 600, 9000, -2); eq(by_name["Solo Violin"], 180, 7500, -1)
eq_bands(by_name["Horns"], 70, {{3, 300, -1.5}, {9, 4000, -3}})
eq(by_name["Flute"], 250, 8000, -1); eq(by_name["Spiccato"], 60, 7000, -1)
eq(by_name["Vln Trem"], 200, 7000, -2); eq(by_name["Timpani"], 30, 5000, -2)
do  -- the electronic layer
  local pad = by_name["Synth Pad"]
  eq_bands(pad, 160, {{3, 350, -2}, {9, 6000, -3}})
  js(pad, "sstillwell/chorus_stereo", {{0, 14}, {1, 2}, {2, 0.3}, {4, -8}, {5, 0}, {6, 0.1}})
  js(pad, "loser/StereoEnhancer", {{0, 100}, {1, 300}, {2, 170}})
  local pl = by_name["Synth Pluck"]
  eq(pl, 380, 9000, 1)
  js(pl, "sstillwell/delay_pong", {{0, 0}, {1, -7}, {3, -5}, {4, 0}, {5, 100}, {6, 0.1875}})
  js(pl, "loser/StereoEnhancer", {{0, 100}, {1, 600}, {2, 150}})
  eq(by_name["Sub"], 25, 220, -18)                     -- a high shelf far down acts as the low-pass
  local ed = by_name["E-Drums"]
  eq_bands(ed, 35, {{3, 400, -2}, {9, 10000, 2}})
  comp(ed, -18, 3, 3, 90, 2)
  js(ed, "loser/Saturation", {{0, 18}})
end
eq_bands(by_name["Bass"], 30, {{0, 70, 2.5}, {3, 250, -2}}); comp(by_name["Bass"], -20, 3, 10, 100, 2)
js(by_name["Bass"], "sstillwell/hugebooty", {{0, 22}, {1, 18}, {2, 80}})
js(by_name["Bass"], "loser/Saturation", {{0, 22}})       -- harmonics: the line reads on small speakers
eq_bands(by_name["Drums"], 30, {{0, 60, 2}, {3, 350, -2}, {9, 9000, 2}}); comp(by_name["Drums"], -16, 3, 15, 120, 2)
js(by_name["Drums"], "loser/Saturation", {{0, 15}})
do  -- parallel "crush" compression under the kit
  local crush = bus("Drum Crush", -12)
  set_exact(crush, js(crush, "sstillwell/1175", {{0, -32}, {2, 8}, {3, 100}, {4, 60}}), 1, "8")
  js(crush, "loser/Saturation", {{0, 35}})
  eq_bands(crush, 60, {{9, 7000, -3}})
  send(by_name["Drums"], crush, 0)
  send(by_name["E-Drums"], crush, -6)
end

local verb = add_track("Reverb")
local rv = reaper.TrackFX_AddByName(verb, "ReaVerbate (Cockos)", false, -1)
set(verb, rv, 0, 0); reaper.TrackFX_SetParamNormalized(verb, rv, 1, 0)
set(verb, rv, 2, 92); set(verb, rv, 3, 40); set(verb, rv, 5, 25); set(verb, rv, 6, 10000); set(verb, rv, 7, 280)
reaper.SetMediaTrackInfo_Value(verb, "D_VOL", 10 ^ (-6 / 20))
js(verb, "sstillwell/chorus_stereo", {{0, 22}, {1, 2}, {2, 0.25}, {4, -9}, {5, 0}, {6, 0.15}})
js(verb, "loser/StereoEnhancer", {{0, 110}, {1, 500}, {2, 165}})
local plate = add_track("Plate")
local pv = reaper.TrackFX_AddByName(plate, "ReaVerbate (Cockos)", false, -1)
set(plate, pv, 0, 0); reaper.TrackFX_SetParamNormalized(plate, pv, 1, 0)
set(plate, pv, 2, 55); set(plate, pv, 3, 30); set(plate, pv, 5, 45); set(plate, pv, 6, 12000); set(plate, pv, 7, 400)
reaper.SetMediaTrackInfo_Value(plate, "D_VOL", 10 ^ (-6 / 20))
js(plate, "loser/StereoEnhancer", {{0, 100}, {1, 500}, {2, 150}})
for name, db in pairs(@PLATE@) do
  for i = 0, reaper.CountTracks(0) - 1 do
    local tr = reaper.GetTrack(0, i)
    local _, n = reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", "", false)
    if n == name then
      local snd = reaper.CreateTrackSend(tr, plate)
      reaper.SetTrackSendInfo_Value(tr, 0, snd, "D_VOL", 10 ^ (db / 20))
    end
  end
end

for i = 0, reaper.CountTracks(0) - 1 do
  local tr = reaper.GetTrack(0, i)
  local _, name = reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", "", false)
  local m = MIX[name]
  if m then
    reaper.SetMediaTrackInfo_Value(tr, "D_VOL", 10 ^ (m[1] / 20))
    reaper.SetMediaTrackInfo_Value(tr, "D_PAN", m[2])
    if m[3] then
      local s = reaper.CreateTrackSend(tr, verb)
      reaper.SetTrackSendInfo_Value(tr, 0, s, "D_VOL", 10 ^ (m[3] / 20))
    end
  end
end
local master = reaper.GetMasterTrack(0)
eq_bands(master, 25, {{6, 3800, 1.5}, {9, 10000, 3.5}})   -- the samples are dark: presence and air
js(master, "sstillwell/expressbus", {{0, -10}, {1, 2}, {2, 1}})
js(master, "loser/Saturation", {{0, 6}})
js(master, "loser/StereoEnhancer", {{0, 100}, {1, 300}, {2, 115}})
local lim = reaper.TrackFX_AddByName(master, "ReaLimit (Cockos)", false, -1)
set(master, lim, 0, -5.8); set(master, lim, 1, -1.7)
say("tracks built: " .. reaper.CountTracks(0))

local function render(dir, pattern)
  reaper.GetSetProjectInfo_String(0, "RENDER_FILE", dir, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", pattern, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", "evaw", true)
  reaper.GetSetProjectInfo(0, "RENDER_SRATE", 44100, true)
  reaper.GetSetProjectInfo(0, "RENDER_CHANNELS", 2, true)
  reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_STARTPOS", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_ENDPOS", @END_S@, true)
  reaper.Main_OnCommand(42230, 0)
end
render(OUT, "madane_reaper_@VERSION@")
say("mix rendered")
for _, tr in ipairs(vocals) do reaper.SetMediaTrackInfo_Value(tr, "B_MUTE", 1) end
render(OUT, "madane_reaper_@VERSION@_inst")
say("instrumental rendered")
for i = 0, (@STEMS@ and reaper.CountTracks(0) or 0) - 1 do
  local tr = reaper.GetTrack(0, i)
  local _, name = reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", "", false)
  if name ~= "Reverb" and name ~= "Plate" and name ~= "Vocal Delay" and name ~= "Drum Crush"
     and reaper.CountTrackMediaItems(tr) > 0 then
    reaper.SetMediaTrackInfo_Value(tr, "B_MUTE", 0)
    reaper.SetMediaTrackInfo_Value(tr, "I_SOLO", 2)
    render(WORK .. "\\stems", (name:gsub("[^%w]", "_")))
    reaper.SetMediaTrackInfo_Value(tr, "I_SOLO", 0)
  end
end
say("stems rendered")
reaper.SetMediaTrackInfo_Value(miku, "B_MUTE", 0)
if guide then reaper.SetMediaTrackInfo_Value(guide, "B_MUTE", 0) end
reaper.GetSetProjectInfo_String(0, "RENDER_FILE", OUT, true)
reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", "madane_reaper_@VERSION@", true)
reaper.Main_SaveProject(0, false)
say("saved")
log:close()
reaper.Main_OnCommand(40004, 0)
'''


def active_rms(x, sr, floor_db=-50):
    mono = x.mean(axis=1)
    env = np.sqrt(np.convolve(mono ** 2, np.ones(441) / 441, mode="same"))
    return np.sqrt(np.mean(mono[env > 10 ** (floor_db / 20)] ** 2))


def level_vocal(src, ref, dst):
    """Match the exported vocal's sung loudness to the guide the mix was balanced on."""
    x, sr = soundfile.read(str(src), always_2d=True)
    g, gsr = soundfile.read(str(ref), always_2d=True)
    gain = active_rms(g, gsr) / active_rms(x, sr)
    soundfile.write(str(dst), x * gain, sr, subtype="FLOAT")    # float: peaks above 0 dBFS survive
    return 20 * np.log10(gain)


def dedupe_bends(points):
    """Sort pitch-bend points; at equal ticks the later-added point (next note) wins."""
    return sorted(dict((t, s) for t, s in points).items())


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    marks, parts_v, chords, hook, bars = music.layout(madane.SECTIONS)
    total = bars * music.BAR
    sections = build.sung_sections(parts_v)
    vocal_notes = [n for s in sections for n in s["notes"]]
    transposes = [s.get("transpose", 0) for s in madane.SECTIONS]
    parts, bends = arrangement.arrange(marks, chords, vocal_notes, transposes, hook,
                                       madane.GUITAR_LEAD, madane.BPM)
    bends = {k: dedupe_bends(v) for k, v in bends.items()}

    rev_len = make_reverse_crash()
    shift = int((build.seconds(music.BAR) - rev_len) * build.TICKS_PER_SECOND)
    for n in parts["Drums"]:
        if n.pitch == arrangement.REVERSE:
            n.start += shift
    parts["Bass"] = [music.Note(n.start, n.length, n.pitch - 12 if n.pitch > 50 else n.pitch, n.velocity)
                     for n in parts["Bass"]]

    parts["Piano Rel"] = piano_releases(parts["Piano"], build.TICKS_PER_SECOND)
    zones = {"Piano": piano_zones([n.pitch for n in parts["Piano"]]), "Piano Rel": piano_release_zones(),
             "Bass": bass_zones(),
             "Drums": drum_zones(),
             "Gtr Lead": guitar_zones(GTR_DIRECT_SFZ, pbrange=PITCHBEND_RANGE["Gtr Lead"]),
             "Gtr Rhythm L": guitar_zones(GTR_DIST_SFZ), "Gtr Rhythm R": guitar_zones(GTR_DIST_SFZ),
             "Gtr Clean": guitar_zones(GTR_DIRECT_SFZ, gain=-8)}
    for name, folder in STRINGS.items():
        zones[name] = string_zones(folder)
    zones.update({"Harp": harp_zones(), "Glock": glock_zones(), "Solo Violin": violin_zones(),
                  "Horns": horn_zones(), "Flute": flute_zones(), "Spiccato": spiccato_zones(),
                  "Vln Trem": tremolo_zones(), "Timpani": timpani_zones(), "Orch FX": effects_zones()})
    zones.update(electro_zones())
    env = string_envelope(marks, build.seconds(total) + 4)
    envelopes = {"Violins": env, "Viola": env, "Cello": env, "Synth Pad": bends.pop("__sidechain__"),
                 "Gtr Lead": section_dip(marks, "Solo", -3.0),           # the last chorus stays the peak
                 "Solo Violin": section_dip(marks, "落ちサビ", -7.0)}     # stays behind the voice there

    # The v4 melody's Miku take is exported on this song form, so it goes in as one item;
    # until it exists a synth guide sings the same notes (older takes hold older melodies).
    guide = WORK / f"guide_vocal_{VERSION}.wav"
    if not guide.exists():
        from arrange_synth import guide_vocal
        guide_vocal(sections, total, guide)
    miku = TAKE or OUT / "miku_v4.wav"
    if miku.exists():   # level it against the guide (same melody, so same loudness)
        leveled = WORK / "miku_leveled.wav"
        print(f"Miku vocal: {miku.name}, gain {level_vocal(miku, guide, leveled):+.1f} dB")
        vocal = {"miku": leveled, "items": [(0.0, 0.0, build.seconds(total) + 10.0)], "guide": None,
                 "double": [(build.seconds(m.start), build.seconds(m.bars * music.BAR) + 0.5)
                            for m in marks if m.feel in ("chorus", "chorus2", "last")]}
        x, sr = soundfile.read(str(leveled), always_2d=True)
        for key, path in (("harmony", OUT / "miku_harmony_v4.wav"), ("ooh", OUT / "miku_ooh_v4.wav")):
            if path.exists() and TAKE is None:    # the backing vocals only fit the v4 take
                h, hsr = soundfile.read(str(path), always_2d=True)
                gain = active_rms(x, sr) / active_rms(h, hsr) * 10 ** (-UNDER_LEAD[key] / 20)
                dst = WORK / f"miku_{key}_leveled.wav"
                soundfile.write(str(dst), h * gain, hsr, subtype="FLOAT")
                vocal[key] = dst
                print(f"{key}: {path.name}, {20 * np.log10(gain):+.1f} dB")
    else:
        print("no vocal take yet: the synth guide sings the melody")
        vocal = {"miku": None, "items": [], "guide": guide}

    script = WORK / f"build_{VERSION}.lua"
    write_script(script, marks, total, parts, zones, envelopes, vocal, bends)
    for old in [OUT / f"madane_reaper_{VERSION}.wav", OUT / f"madane_reaper_{VERSION}_inst.wav",
                *(WORK / "stems").glob("*.wav")]:
        old.unlink(missing_ok=True)
    print({k: f"{len(v)} zones" for k, v in zones.items()}, {k: len(v) for k, v in parts.items()})
    ok, secs, boot = reaper_run.run(script, WORK / f"madane_{VERSION}.rpp", timeout=3000)
    print(f"REAPER {'finished' if ok else 'TIMED OUT'} in {secs:.0f}s\n{boot}")
    log = WORK / "build_log.txt"
    if log.exists():
        print(log.read_text(encoding="utf-8"))
    for wav in (OUT / f"madane_reaper_{VERSION}.wav", OUT / f"madane_reaper_{VERSION}_inst.wav"):
        if wav.exists():
            spots, tp = truepeak.process(wav)             # inter-sample peaks under -1 dBTP
            print(f"{wav.name}: {spots} true-peak spots treated, now {tp:.2f} dBTP")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "224k",
                            str(wav.with_suffix(".mp3"))], check=True)


if __name__ == "__main__":
    main()
