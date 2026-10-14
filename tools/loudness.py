"""Integrated loudness (ITU-R BS.1770-4 / EBU R128), true-peak estimate and crest factor.

    python -I tools/loudness.py file.wav [file2.wav ...]
"""
import sys

import numpy as np
import soundfile
from scipy.signal import lfilter, resample_poly


def k_weight(x, sr):
    """The two BS.1770 pre-filters (high shelf + RLB high-pass), designed for any sample rate."""
    f0, g, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = np.tan(np.pi * f0 / sr)
    vh = 10 ** (g / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    b1 = [(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0]
    a1 = [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    f0, q = 38.13547087602444, 0.5003270373238773
    k = np.tan(np.pi * f0 / sr)
    a0 = 1 + k / q + k * k
    b2 = [1, -2, 1]
    a2 = [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    return lfilter(b2, a2, lfilter(b1, a1, x, axis=0), axis=0)


def integrated_lufs(x, sr):
    y = k_weight(x, sr)
    block, hop = int(0.4 * sr), int(0.1 * sr)
    n = (len(y) - block) // hop + 1
    ms = np.array([(y[i * hop:i * hop + block] ** 2).mean(axis=0).sum() for i in range(n)])
    lk = -0.691 + 10 * np.log10(ms + 1e-12)
    gated = ms[lk > -70]
    rel = -0.691 + 10 * np.log10(gated.mean()) - 10
    final = ms[(lk > -70) & (lk > rel)]
    return -0.691 + 10 * np.log10(final.mean())


def true_peak_db(x):
    up = resample_poly(x, 4, 1, axis=0)
    return 20 * np.log10(np.abs(up).max() + 1e-12)


def main():
    for path in sys.argv[1:]:
        x, sr = soundfile.read(path, always_2d=True)
        lufs = integrated_lufs(x, sr)
        rms = 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)
        peak = 20 * np.log10(np.abs(x).max() + 1e-12)
        print(f"{path}: {lufs:6.1f} LUFS  true-peak {true_peak_db(x):5.1f} dBTP  crest {peak - rms:4.1f} dB")


if __name__ == "__main__":
    main()
