"""Electronic sounds for まだね, synthesized offline as multisamples for RS5K.

supersaw pad, filtered pluck, sine sub, 808-style kick, clap, hat, noise riser,
and a vocal chop cut from Miku's first 「あ」. Everything is band-limited
(wavetables built per note) so nothing aliases.

    python -I tools/synths.py        -> reaper/samples/synth/*.wav
"""
import sys
from pathlib import Path

import numpy as np
import soundfile
from scipy.signal import butter, lfilter, sosfilt

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "reaper" / "samples" / "synth"
PAD_NOTES = list(range(48, 88, 3))        # C3 .. B5
PLUCK_NOTES = list(range(60, 100, 3))
SUB_NOTES = list(range(24, 52, 3))
RNG = np.random.default_rng(42)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def saw_table(f0, n=4096, top=15000.0):
    """One cycle of a band-limited saw for fundamentals around f0."""
    k = np.arange(1, max(1, int(top / f0)) + 1)
    ph = np.arange(n) / n * 2 * np.pi
    return (np.sin(np.outer(ph, k)) / k).sum(axis=1) * (2 / np.pi)


def square_table(f0, n=4096, top=15000.0):
    k = np.arange(1, max(1, int(top / f0)) + 1, 2)
    ph = np.arange(n) / n * 2 * np.pi
    return (np.sin(np.outer(ph, k)) / k).sum(axis=1) * (4 / np.pi)


def osc(table, f, seconds, phase=0.0):
    n = len(table)
    t = np.arange(int(seconds * SR)) / SR
    pos = ((f * t + phase) % 1.0) * n
    i = pos.astype(np.int64)
    frac = pos - i
    return table[i] * (1 - frac) + table[(i + 1) % n] * frac


def swept_lowpass(x, cutoff, q=0.9, block=64):
    """A 2-pole low-pass whose cutoff follows the array `cutoff` (Hz per sample)."""
    y = np.zeros_like(x)
    zi = np.zeros(2)
    for a in range(0, len(x), block):
        fc = float(np.clip(cutoff[min(a, len(cutoff) - 1)], 40, SR * 0.45))
        w = np.tan(np.pi * fc / SR)
        k = 1 / q
        a0 = 1 + k * w + w * w
        b = np.array([w * w, 2 * w * w, w * w]) / a0
        aa = np.array([1, 2 * (w * w - 1) / a0, (1 - k * w + w * w) / a0])
        y[a:a + block], zi = lfilter(b, aa, x[a:a + block], zi=zi)
    return y


def swept_bandpass(x, center, q=1.6, block=64):
    y = np.zeros_like(x)
    zi = np.zeros(2)
    for a in range(0, len(x), block):
        fc = float(np.clip(center[min(a, len(center) - 1)], 40, SR * 0.45))
        w0 = 2 * np.pi * fc / SR
        al = np.sin(w0) / (2 * q)
        b = np.array([al, 0, -al])
        aa = np.array([1 + al, -2 * np.cos(w0), 1 - al])
        y[a:a + block], zi = lfilter(b / aa[0], aa / aa[0], x[a:a + block], zi=zi)
    return y


def write(name, stereo, peak=0.5):
    stereo = np.asarray(stereo, np.float64)
    if stereo.ndim == 1:
        stereo = np.stack([stereo, stereo], axis=1)
    stereo = stereo / (np.abs(stereo).max() + 1e-12) * peak
    soundfile.write(str(OUT / name), stereo.astype(np.float32), SR, subtype="FLOAT")


def pad(m, seconds=8.0):
    """Seven detuned saws spread across the stereo field, low-passed warm."""
    f0 = hz(m)
    table = saw_table(f0 * 1.01)
    detune = [-14, -9, -4, 0, 4, 9, 14]
    pans = [-0.9, 0.6, -0.4, 0.0, 0.4, -0.6, 0.9]
    left = np.zeros(int(seconds * SR))
    right = np.zeros_like(left)
    for d, pan in zip(detune, pans):
        v = osc(table, f0 * 2 ** (d / 1200), seconds, RNG.random())
        left += v * np.sqrt((1 - pan) / 2)
        right += v * np.sqrt((1 + pan) / 2)
    sos = butter(2, min(2600.0, f0 * 9), "lowpass", fs=SR, output="sos")
    hp = butter(1, 120, "highpass", fs=SR, output="sos")
    return np.stack([sosfilt(hp, sosfilt(sos, left)), sosfilt(hp, sosfilt(sos, right))], axis=1)


def pluck(m, seconds=1.6):
    f0 = hz(m)
    t = np.arange(int(seconds * SR)) / SR
    x = 0.7 * osc(saw_table(f0), f0, seconds) + 0.35 * osc(square_table(f0), f0 * 1.003, seconds, 0.3)
    x = swept_lowpass(x, 700 + 7500 * np.exp(-t / 0.10), q=1.1)
    x *= np.exp(-t / 0.30) * np.minimum(1, t / 0.002)
    return np.stack([x, np.roll(x, 7)], axis=1)


def sub(m, seconds=4.0):
    t = np.arange(int(seconds * SR)) / SR
    x = np.sin(2 * np.pi * hz(m) * t) + 0.08 * np.sin(4 * np.pi * hz(m) * t)
    return x * np.minimum(1, t / 0.015)


def ekick(seconds=0.8):
    t = np.arange(int(seconds * SR)) / SR
    f = 48 + 110 * np.exp(-t / 0.035)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.32) * np.minimum(1, t / 0.002)
    click = sosfilt(butter(2, 2500, "highpass", fs=SR, output="sos"), RNG.normal(0, 1, len(t))) * np.exp(-t / 0.002)
    return np.tanh(1.6 * (body + 0.25 * click))


def eclap(seconds=0.5):
    t = np.arange(int(seconds * SR)) / SR
    bp = butter(2, [900, 4200], "bandpass", fs=SR, output="sos")
    out = np.zeros((len(t), 2))
    for ch in range(2):
        noise = sosfilt(bp, RNG.normal(0, 1, len(t)))
        env = np.zeros(len(t))
        for start in (0.0, 0.009, 0.019):
            tt = np.clip(t - start, 0, None)
            env += (t >= start) * np.exp(-tt / 0.006)
        tail = np.clip(t - 0.025, 0, None)
        env += (t >= 0.025) * 0.6 * np.exp(-tail / 0.12)
        out[:, ch] = noise * env
    return out


def ehat(seconds=0.15):
    t = np.arange(int(seconds * SR)) / SR
    hp = butter(4, 7000, "highpass", fs=SR, output="sos")
    return np.stack([sosfilt(hp, RNG.normal(0, 1, len(t))) * np.exp(-t / 0.03) for _ in range(2)], axis=1)


def riser(seconds=3.0):
    """Band-passed noise sweeping up, with a rising tone underneath; it ends on the downbeat."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    center = 400 * (9000 / 400) ** (t / seconds)
    amp = (t / seconds) ** 2.4
    out = np.zeros((n, 2))
    for ch in range(2):
        out[:, ch] = swept_bandpass(RNG.normal(0, 1, n), center, q=1.4) * amp
    tone = np.sin(2 * np.pi * np.cumsum(220 * 4 ** (t / seconds)) / SR) * amp * 0.25
    out += tone[:, None]
    out[-int(0.008 * SR):] *= np.linspace(1, 0, int(0.008 * SR))[:, None]
    return out


def vocal_chop(miku_wav, start, length):
    """Miku's first sustained 「あ」, trimmed with short fades (her first sound becomes an instrument)."""
    x, sr = soundfile.read(str(miku_wav), always_2d=True)
    seg = x[int((start + 0.04) * sr):int((start + length) * sr)].copy()
    fade = int(0.012 * sr)
    seg[:fade] *= np.linspace(0, 1, fade)[:, None]
    seg[-fade * 4:] *= np.linspace(1, 0, fade * 4)[:, None]
    return seg


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for m in PAD_NOTES:
        write(f"pad_{m}.wav", pad(m), peak=0.45)
    for m in PLUCK_NOTES:
        write(f"pluck_{m}.wav", pluck(m), peak=0.6)
    for m in SUB_NOTES:
        write(f"sub_{m}.wav", sub(m), peak=0.7)
    write("ekick.wav", ekick(), peak=0.85)
    write("eclap.wav", eclap(), peak=0.6)
    write("ehat.wav", ehat(), peak=0.4)
    write("riser.wav", riser(), peak=0.55)
    if len(sys.argv) > 2:
        write("chop_a.wav", vocal_chop(sys.argv[1], float(sys.argv[2]), float(sys.argv[3])), peak=0.7)
    print("wrote", len(list(OUT.glob("*.wav"))), "samples to", OUT)


if __name__ == "__main__":
    main()
