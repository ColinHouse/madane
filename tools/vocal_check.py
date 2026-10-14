"""Measure an exported vocal against the score it was rendered from.

For every note: median pitch error (cents) and level; for every rest: how much
sound is left in it and whether that sound is breath noise; for every pair of
notes that should be legato: how deep the level dips at the join.

    python -I tools/vocal_check.py out/miku.wav v2        (old melody, v2 form)
    python -I tools/vocal_check.py out/miku_v3.wav v3     (current melody and form)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import soundfile

import build
import madane
import madane_v2
import music
import vpr

SMOOTH = set("a i M e o n m J N N' m' j w 4 4' N\\".split())   # onsets with no closure


def envelope(x, sr, win=0.01):
    hop = int(sr * win)
    n = len(x) // hop
    frames = x[:n * hop].reshape(n, hop)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9), hop


def f0(x, sr, fmin=150, fmax=1000):
    """Autocorrelation pitch of one frame (Hz) or None when unvoiced."""
    x = x - x.mean()
    if np.sqrt((x ** 2).mean()) < 1e-4:
        return None
    n = len(x)
    spec = np.fft.rfft(x * np.hanning(n), 2 * n)
    ac = np.fft.irfft(np.abs(spec) ** 2)[:n]
    ac /= ac[0] + 1e-12
    lo, hi = int(sr / fmax), int(sr / fmin)
    k = lo + int(np.argmax(ac[lo:hi]))
    if ac[k] < 0.45:
        return None
    a, b, c = ac[k - 1], ac[k], ac[k + 1]
    shift = 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
    return sr / (k + shift)


def hf_ratio(x, sr):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    return float(spec[freqs > 3000].sum() / (spec.sum() + 1e-12))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    path = sys.argv[1]
    form = madane_v2.SECTIONS_V2 if (sys.argv[2] if len(sys.argv) > 2 else "v3") == "v2" else madane.SECTIONS
    x, sr = soundfile.read(path, always_2d=True)
    x = x.mean(axis=1)
    env, hop = envelope(x, sr)
    _, parts, *_ = music.layout(form)
    notes = []
    for name, start, length, events, feel in parts:
        for n in music.section_notes(start, events):
            notes.append((name, build.seconds(n.start), build.seconds(n.start + n.length), n.pitch, n.lyric))
    notes.sort(key=lambda n: n[1])
    peak = np.percentile(env, 99)

    print(f"{'sec':6s} {'time':>7s} {'syl':4s} {'midi':>4s} {'cents':>6s} {'dB':>6s}")
    bad_pitch = []
    for name, a, b, p, syl in notes:
        mid0, mid1 = a + 0.3 * (b - a), b - 0.2 * (b - a)
        frames = []
        t = mid0
        while t + 0.046 <= mid1 or not frames:
            seg = x[int(t * sr):int(t * sr) + 2048]
            if len(seg) == 2048:
                hz = f0(seg, sr)
                if hz:
                    frames.append(1200 * np.log2(hz / (440 * 2 ** ((p - 69) / 12))))
            t += 0.02
            if t > mid1:
                break
        cents = float(np.median(frames)) if frames else float("nan")
        # octave errors from the detector are not tuning errors
        if not np.isnan(cents):
            cents = (cents + 600) % 1200 - 600
        lvl = float(env[int(a / (hop / sr)):max(int(a / (hop / sr)) + 1, int(b / (hop / sr)))].mean()) - peak
        if np.isnan(cents) or abs(cents) > 60:
            bad_pitch.append((name, a, syl, p, cents, lvl))

    print("\n-- notes whose sustained pitch is off by > 60 cents (or unvoiced) --")
    for name, a, syl, p, cents, lvl in bad_pitch:
        print(f"{name:6s} {a:7.2f} {syl:4s} {p:4d} {cents:6.0f} {lvl:6.1f}")

    print("\n-- rests: level left inside (dB re peak) and breath-noise share --")
    for (n0, n1) in zip(notes, notes[1:]):
        gap = n1[1] - n0[2]
        if gap <= 0.01:
            continue
        a, b = n0[2] + 0.03, n1[1] - 0.03
        if b - a < 0.02:
            continue
        seg = x[int(a * sr):int(b * sr)]
        lvl = 20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9) - peak
        hf = hf_ratio(seg, sr) if len(seg) > 256 else 0
        kind = "っ" if gap < 0.3 else "breath"
        flag = "  <-- sound in the rest" if lvl > -30 else ""
        print(f"{n0[0]:6s} {n0[2]:7.2f} {kind:6s} gap {gap:4.2f}s  after {n0[4]:3s} before {n1[4]:3s} "
              f"{lvl:6.1f} dB  hf {hf:4.2f}{flag}")

    print("\n-- legato joins into vowels/nasals/glides that dip more than 12 dB --")
    phs, prev = [], None
    for n in notes:
        prev = vpr.phoneme(n[4], prev)
        phs.append(prev)
    for i, (n0, n1) in enumerate(zip(notes, notes[1:])):
        if abs(n1[1] - n0[2]) > 0.01:
            continue
        head = phs[i + 1].split()[0]
        if head not in SMOOTH:
            continue
        j = int(n0[2] / (hop / sr))
        around = env[max(0, j - 5):j + 6]
        left = env[int((n0[1] + 0.5 * (n0[2] - n0[1])) / (hop / sr)):j - 4]
        right = env[j + 5:int((n1[1] + 0.5 * (n1[2] - n1[1])) / (hop / sr))]
        if len(around) == 0 or len(left) == 0 or len(right) == 0:
            continue
        dip = min(left.mean(), right.mean()) - around.min()
        if dip > 12:
            print(f"{n0[0]:6s} {n0[2]:7.2f}  {n0[4]}->{n1[4]} ({head})  dip {dip:5.1f} dB")


if __name__ == "__main__":
    main()
