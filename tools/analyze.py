"""Loudness / balance report for a rendered mix and its stems.

    python -I tools/analyze.py <mix.wav> [stems_dir]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import soundfile

import madane
import music

BANDS = [(20, 120, "low"), (120, 500, "lowmid"), (500, 2000, "mid"), (2000, 6000, "himid"), (6000, 18000, "high")]


def load(path):
    x, sr = soundfile.read(str(path), always_2d=True)
    return x, sr


def db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12)


def sections():
    marks = music.layout(madane.SECTIONS)[0]
    bar = 4 * 60 / madane.BPM
    return [(m.name, m.start / music.BAR * bar, (m.start / music.BAR + m.bars) * bar) for m in marks]


def band_share(x, sr):
    mono = x.mean(axis=1)
    spec = np.abs(np.fft.rfft(mono[: sr * 120])) ** 2
    f = np.fft.rfftfreq(min(len(mono), sr * 120), 1 / sr)
    total = spec.sum()
    return {name: 100 * spec[(f >= a) & (f < b)].sum() / total for a, b, name in BANDS}


def main():
    mix, sr = load(sys.argv[1])
    peak = np.abs(mix).max()
    print(f"mix: peak {20 * np.log10(peak):.1f} dBFS, RMS {db(mix):.1f} dBFS, {len(mix) / sr:.1f}s")
    print("spectrum share %:", {k: round(v, 1) for k, v in band_share(mix, sr).items()})
    stems = {}
    if len(sys.argv) > 2:
        for p in sorted(Path(sys.argv[2]).glob("*.wav")):
            stems[p.stem] = load(p)[0]
    names = list(stems)
    print(f"{'section':10s} {'MIX':>6s} " + " ".join(f"{n[:9]:>9s}" for n in names))
    for name, a, b in sections():
        i, j = int(a * sr), int(b * sr)
        row = [db(mix[i:j])] + [db(stems[n][i:j]) for n in names]
        print(f"{name:10s} " + " ".join(f"{v:9.1f}" if k else f"{v:6.1f}" for k, v in enumerate(row)))


if __name__ == "__main__":
    main()
