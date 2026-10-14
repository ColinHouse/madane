"""The electronic layer for まだね: supersaw pad, pluck arpeggio, sub, layered
electronic drums and risers.

It thickens the acoustic arrangement rather than replacing it: the pad sits
under the choruses (ducking on the kick in the big ones), the pluck takes over
the harp's ripples in 2サビ and ラスサビ, and the electronic drums double the kit
where the band plays full. (A vocal chop of Miku's first 「あ」 answering the
intro hook was dropped: pitched an octave above the hook it squealed.)
"""
from arrangement import BAR, E, H, Q, UNIT, _progress, _vel, nearest, notes_in, scale
from music import Note

EKICK, ECLAP, EHAT, RISER = 36, 38, 42, 50      # keys on the "E-Drums" track
RISER_S = 3.0                                    # the riser sample: a bar long, peaking at its end


def _voicing(c, prev, lo=55, hi=79, n=4):
    tones = notes_in(c.tones, lo, hi)
    best = sorted(tones, key=lambda p: abs(p - prev))[:n]
    return sorted(best)


def pad(song):
    out = []
    level = {"pre": 44, "chorus": 52, "interlude": 40, "chorus2": 66, "solo": 58, "last": 80, "outro": 46}
    prev = 66
    for c in song.chords:
        m, _ = song.section(c)
        v = level.get(c.feel)
        if c.feel == "bridge" and (c.start - m.start) // BAR >= 4:
            v = int(44 + 30 * _progress(song, c))
        if v is None or (c.feel == "pre" and m.name == "1B" and (c.start - m.start) // BAR < 2):
            continue
        notes = _voicing(c, prev)
        prev = sum(notes) / len(notes)
        out += [Note(c.start, c.length + 40, p, _vel(v, 2)) for p in notes]
    return out


def pluck(song):
    """Eighth-note arpeggio high up, with the ping-pong delay filling the sixteenths."""
    out = []
    for c in song.chords:
        if c.feel not in ("chorus2", "solo", "last"):
            continue
        tones = notes_in(c.tones, 74, 91)
        order = [0, 2, 1, 3, 2, 4, 3, 1]
        base = {"chorus2": 60, "solo": 66, "last": 72}[c.feel]
        for k in range(c.length // E):
            p = tones[order[k % 8] % len(tones)]
            out.append(Note(c.start + k * E, E, p, _vel(base + (10 if k % 4 == 0 else 0), 3)))
    return out


def sub(song):
    out = []
    for c in song.chords:
        if c.feel not in ("chorus2", "solo", "last"):
            continue
        root = nearest(notes_in([c.bass], 26, 40), 33)
        out.append(Note(c.start, c.length - 20, root, _vel(84, 2)))
    return out


def edrums(song, kicks):
    """Electronic kick under every acoustic kick in the full sections, claps on the backbeat, sixteenth hats."""
    out = []
    full = {m.name for m in song.marks if m.feel in ("chorus2", "solo", "last")}
    for m in song.marks:
        if m.name not in full:
            continue
        a, b = m.start, m.start + m.bars * BAR
        out += [Note(t, Q, EKICK, _vel(v, 3)) for t, v in kicks if a <= t < b]
        for bar in range(m.bars):
            t0 = a + bar * BAR
            out.append(Note(t0 + 2 * Q, Q, ECLAP, _vel(86 if m.feel != "solo" else 92, 3)))
            if m.feel == "solo":
                out.append(Note(t0 + Q, Q, ECLAP, _vel(80, 3)))
                out.append(Note(t0 + 3 * Q, Q, ECLAP, _vel(80, 3)))
            for u in range(16):
                out.append(Note(t0 + u * UNIT, UNIT, EHAT, _vel(54 if u % 4 == 2 else 34, 4)))
    for name in ("2サビ", "Solo", "ラスサビ"):                     # risers end on the downbeat
        t = song.mark(name).start
        out.append(Note(t - int(RISER_S * song.tps), Q, RISER, 96))
    return out


def sidechain(song, kicks):
    """Volume points (seconds, dB) that duck the pad on each kick in the full sections."""
    pts = [(0.0, 0.0)]
    full = [m for m in song.marks if m.feel in ("chorus2", "last")]
    for t, _ in kicks:
        if any(m.start <= t < m.start + m.bars * BAR for m in full):
            s = t / song.tps
            pts += [(s - 0.004, 0.0), (s + 0.012, -7.0), (s + 0.24, 0.0)]
    return sorted(pts)


def electro(song, drums):
    kicks = sorted((n.start, n.velocity) for n in drums if n.pitch == 36)
    return {"Synth Pad": pad(song), "Synth Pluck": pluck(song), "Sub": sub(song),
            "E-Drums": edrums(song, kicks)}, sidechain(song, kicks)
