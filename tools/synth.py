"""Tiny numpy instruments for sketch demos (not the final arrangement)."""
import numpy as np
from scipy.signal import lfilter, oaconvolve

SR = 44100
_rng = np.random.default_rng(7)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _t(n):
    return np.arange(n) / SR


def _release(n, hold, rel):
    """1 for `hold` samples, then a linear fade over `rel` samples."""
    env = np.ones(n)
    if hold < n:
        end = min(n, hold + rel)
        env[hold:end] = np.linspace(1, 0, end - hold, endpoint=False)
        env[end:] = 0
    return env


def _lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    return lfilter([1 - a], [1, -a], x)


def ep(f, dur, vel):
    """FM electric piano."""
    hold, rel = int(dur * SR), int(0.25 * SR)
    n = hold + rel
    t = _t(n)
    index = 1.3 * np.exp(-t / 0.3) + 0.12
    s = np.sin(2 * np.pi * f * t + index * np.sin(2 * np.pi * f * t))
    s += 0.12 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t / 0.04)
    amp = np.exp(-t / 1.4) * np.minimum(1, t / 0.003)
    return s * amp * _release(n, hold, rel) * vel


def piano(f, dur, vel):
    """Additive piano: slightly stretched partials, higher ones dying faster."""
    hold, rel = int(dur * SR), int(0.3 * SR)
    tau = 2.6 * (261.6 / f) ** 0.5
    n = min(hold + rel, int(6 * tau * SR))
    t = _t(n)
    bright = 0.45 + 0.35 * vel
    s = np.zeros(n)
    for k in range(1, 16):
        fk = k * f * np.sqrt(1 + 0.0004 * k * k)
        if fk > 10000:
            break
        s += bright ** (k - 1) / k * np.sin(2 * np.pi * fk * t) * np.exp(-t * (1 + 0.6 * (k - 1)) / tau)
    s += 0.03 * _lowpass(_rng.standard_normal(n), 2500) * np.exp(-t / 0.012)
    return s * np.minimum(1, t / 0.002) * _release(n, hold, rel) * vel


def breath(level, seconds=0.32):
    """Soft inhale noise placed before a phrase."""
    n = int(seconds * SR)
    noise = lfilter([1, -1], [1, -0.95], _rng.standard_normal(n))
    noise = _lowpass(_lowpass(noise, 3500), 3500)
    return noise * np.sin(np.pi * _t(n) / seconds) ** 2 * level * 0.15


def bell(f, dur, vel):
    n = int((dur + 1.2) * SR)
    t = _t(n)
    s = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.9)
         + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.4)
         + 0.2 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t / 0.15))
    return s * np.minimum(1, t / 0.002) * vel


def bass(f, dur, vel):
    hold, rel = int(dur * SR), int(0.05 * SR)
    n = hold + rel
    t = _t(n)
    ph = 2 * np.pi * f * t
    s = np.tanh(1.4 * (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)))
    amp = (0.75 + 0.25 * np.exp(-t / 0.15)) * np.minimum(1, t / 0.006)
    return s * amp * _release(n, hold, rel) * vel


def pad(f, dur, vel):
    hold, rel = int(dur * SR), int(0.5 * SR)
    n = hold + rel
    t = _t(n)
    s = sum(2 * ((f * (1 + d) * t + _rng.random()) % 1.0) - 1 for d in (-0.006, 0.0, 0.006)) / 3
    s = _lowpass(_lowpass(s, 1200), 1200)
    return s * np.minimum(1, t / 0.35) * _release(n, hold, rel) * vel


def kick(vel):
    n = int(0.35 * SR)
    t = _t(n)
    ph = 2 * np.pi * np.cumsum(45 + 110 * np.exp(-t / 0.04)) / SR
    return np.sin(ph) * np.exp(-t / 0.16) * vel


def snare(vel):
    n = int(0.25 * SR)
    t = _t(n)
    noise = lfilter([1, -1], [1, -0.5], _rng.standard_normal(n))
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.06)
    return (0.5 * noise * np.exp(-t / 0.09) + 0.6 * tone) * vel * 0.8


def hat(vel):
    n = int(0.08 * SR)
    noise = lfilter([1, -1], [1, 0.3], _rng.standard_normal(n))
    return noise * np.exp(-_t(n) / 0.018) * vel * 0.4


def crash(vel):
    n = int(1.8 * SR)
    noise = lfilter([1, -1], [1, 0.2], _rng.standard_normal(n))
    return noise * np.exp(-_t(n) / 0.6) * vel * 0.25


DRUMS = {"kick": kick, "snare": snare, "hat": hat, "crash": crash}


def lead_line(notes, n_total, cents, level):
    """Continuous-phase 'voice' for a melody with glides and re-articulation.

    notes: [(start_s, dur_s, midi)] sorted by start; cents and level are
    per-sample pitch offsets and loudness (the same curves sent to Vocaloid).
    """
    freq = np.zeros(n_total)
    gate = np.zeros(n_total)
    prev_end, prev_f = -SR, None
    for start, dur, midi in notes:
        s, e = int(start * SR), min(n_total, int((start + dur) * SR))
        if e <= s:
            continue
        f = hz(midi)
        seg = np.full(e - s, f)
        env = np.ones(e - s)
        if prev_f is not None and s - prev_end < int(0.01 * SR):
            g = min(len(seg), int(0.06 * SR))
            seg[:g] = prev_f * (f / prev_f) ** (np.arange(g) / g)
            d = min(len(env), int(0.03 * SR))
            env[:d] = 1 - 0.35 * np.sin(np.pi * np.arange(d) / d)
        else:
            a = min(len(env), int(0.04 * SR))
            env[:a] = np.linspace(0, 1, a)
        freq[s:e] = seg
        gate[s:e] = env
        r_end = min(n_total, e + int(0.08 * SR))
        freq[e:r_end] = f
        gate[e:r_end] = np.linspace(1, 0, r_end - e, endpoint=False)
        prev_end, prev_f = e, f
    freq *= 2 ** (cents / 1200)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    tone = sum(a * np.sin(k * phase) for k, a in enumerate((1, 0.5, 0.28, 0.14, 0.07, 0.04), 1))
    air = _lowpass(_rng.standard_normal(n_total), 4000) * 0.04
    return (tone + air) * gate * level


def reverb(send, seconds=2.2, decay=0.55):
    n = int(seconds * SR)
    t = _t(n)
    rng = np.random.default_rng(3)
    wet = []
    for _ in range(2):
        ir = _lowpass(rng.standard_normal(n) * np.exp(-t / decay), 5000)
        ir[: int(0.012 * SR)] = 0
        ir /= np.sqrt(np.sum(ir ** 2))
        wet.append(oaconvolve(send, ir)[: len(send)])
    return np.stack(wet, axis=1)


class Mixer:
    def __init__(self, seconds):
        self.n = int(seconds * SR)
        self.dry = np.zeros((self.n, 2), dtype=np.float32)
        self.send = np.zeros(self.n, dtype=np.float32)

    def add(self, signal, start_s, gain=1.0, pan=0.0, send=0.0):
        s = int(start_s * SR)
        if s >= self.n:
            return
        x = signal[: self.n - s] * gain
        theta = (pan + 1) * np.pi / 4
        self.dry[s:s + len(x), 0] += (x * np.cos(theta)).astype(np.float32)
        self.dry[s:s + len(x), 1] += (x * np.sin(theta)).astype(np.float32)
        if send:
            self.send[s:s + len(x)] += (x * send).astype(np.float32)

    def master(self, wet_gain=0.22):
        mix = self.dry + wet_gain * reverb(self.send.astype(np.float64)).astype(np.float32)
        mix /= np.max(np.abs(mix)) + 1e-9
        return np.tanh(1.6 * mix) / np.tanh(1.6) * 0.95
