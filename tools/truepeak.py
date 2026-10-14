"""The last mastering step: keep inter-sample (true) peaks under a ceiling.

ReaLimit holds the sample peaks, but bright transients still overshoot between
samples by a dB or so. Those spots are few, so instead of limiting the whole
song harder each one gets a short gain dip (raised-cosine, 2 ms in, 40 ms out),
measured on a 4x oversampled copy and repeated until the ceiling holds.

    python -I tools/truepeak.py in.wav [out.wav] [ceiling_dBTP]
"""
import sys

import numpy as np
import soundfile
from scipy.signal import resample_poly

OS = 4


def true_peaks(x):
    """Per-sample true peak (max over the oversampled points that follow each sample, all channels)."""
    up = np.abs(resample_poly(x, OS, 1, axis=0)).max(axis=1)
    n = len(x)
    return up[:n * OS].reshape(n, OS).max(axis=1)


def limit(x, sr, ceiling_db=-1.0, attack=0.002, release=0.040):
    c = 10 ** (ceiling_db / 20)
    a, r = max(1, int(attack * sr)), max(1, int(release * sr))
    spots = 0
    for _ in range(6):
        tp = true_peaks(x)
        idx = np.where(tp > c)[0]
        if len(idx) == 0:
            break
        spots += len(idx)
        gain = np.ones(len(x))
        for i in idx:
            need = c / tp[i] * 0.998
            lo, hi = max(0, i - a), min(len(x), i + r + 1)
            t = np.arange(lo, hi)
            w = np.where(t <= i, 0.5 - 0.5 * np.cos(np.pi * (t - (i - a)) / a),
                         0.5 + 0.5 * np.cos(np.pi * (t - i) / r))
            gain[lo:hi] = np.minimum(gain[lo:hi], 1 - (1 - need) * w)
        x = x * gain[:, None]
    return x, spots


def process(src, dst=None, ceiling_db=-1.0):
    info = soundfile.info(str(src))
    x, sr = soundfile.read(str(src), always_2d=True)
    y, spots = limit(x, sr, ceiling_db)
    soundfile.write(str(dst or src), y, sr, subtype=info.subtype)
    after = 20 * np.log10(true_peaks(y).max())
    return spots, after


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    ceiling = float(sys.argv[3]) if len(sys.argv) > 3 else -1.0
    spots, after = process(src, dst, ceiling)
    print(f"{spots} over-ceiling samples treated; true peak now {after:.2f} dBTP")
