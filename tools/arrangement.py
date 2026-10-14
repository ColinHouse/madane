"""Full arrangement for まだね: piano, strings, bass, guitars, drums and (from
orchestra.py) harp, glockenspiel, solo violin, horns, flute and percussion.

Every part is generated from the chord list, the section layout and the sung
notes. Output: {track: [Note]} plus pitch-bend curves {track: [(tick, semis)]}
for the parts that bend (guitar lead, bass slides).
"""
import math
import random
import re

from music import BAR, TPQ, UNIT, Note, note_number

E, Q, H = TPQ // 2, TPQ, TPQ * 2
MAJOR = (0, 2, 4, 5, 7, 9, 11)
_rng = random.Random(11)

# GM drum notes used by the kit mapping
KICK, STICK, SNARE, HH, HH_PEDAL, HH_OPEN = 36, 37, 38, 42, 44, 46
CRASH, RIDE, TOM_HI, TOM_MID, TOM_LOW, REVERSE = 49, 51, 50, 47, 43, 59


def _vel(v, spread=4):
    return max(1, min(127, int(v + _rng.uniform(-spread, spread))))


def notes_in(tones, lo, hi):
    return [p for p in range(lo, hi + 1) if p % 12 in tones]


def scale(key_pc, lo, hi):
    return [p for p in range(lo, hi + 1) if (p - key_pc) % 12 in MAJOR]


def nearest(options, target):
    return min(options, key=lambda p: (abs(p - target), p))


class Song:
    def __init__(self, marks, chords, vocal, transposes, bpm):
        self.marks, self.chords, self.vocal, self.bpm = marks, chords, vocal, bpm
        self.tps = TPQ * bpm / 60                      # ticks per second
        self.section_of, self.shift = {}, {}
        for m, t in zip(marks, transposes):
            self.shift[m.name] = t
            for c in chords:
                if m.start <= c.start < m.start + m.bars * BAR:
                    self.section_of[id(c)] = (m, t)

    def section(self, c):
        return self.section_of[id(c)]

    def key(self, c):
        return (2 + self.section(c)[1]) % 12

    def mark(self, name):
        return next(m for m in self.marks if m.name == name)

    def chords_of(self, name):
        m = self.mark(name)
        return [c for c in self.chords if m.start <= c.start < m.start + m.bars * BAR]

    def vocal_onsets(self, a, b):
        return [n for n in self.vocal if a <= n.start < b]

    def bars(self, feel):
        for m in self.marks:
            if m.feel != feel:
                continue
            for b in range(m.bars):
                t0 = m.start + b * BAR
                yield m, b, t0, [c for c in self.chords if t0 <= c.start < t0 + BAR]


def _progress(song, c):
    m, _ = song.section(c)
    return (c.start - m.start) / (m.bars * BAR)


# --- piano (kept in the background; the guitars and strings carry the energy) ---
def _lh_broken(c, vel, step=E):
    root = nearest(notes_in([c.bass], 31, 43), 38)
    up = sorted(set(notes_in(c.tones, root + 6, root + 20)))[:4]
    shape = [root] + up + up[-2::-1]
    return [Note(c.start + k * step, c.length - k * step if k == 0 else min(c.length - k * step, 2 * Q),
                 shape[k % len(shape)], _vel(vel - (0 if k == 0 else 10))) for k in range(c.length // step)]


def _rh_arp(c, vel, lo=57, hi=74, step=E):
    tones = notes_in(c.tones, lo, hi)[:5]
    order = [0, 1, 2, 3, 2, 1, 2, 3] if step == E else [0, 1, 2, 3, 4, 3, 2, 1]
    per_beat = Q // step
    accent = lambda k: 6 if k % (2 * per_beat) == 0 else 2 if k % per_beat == 0 else -4
    return [Note(c.start + k * step, max(step, c.length - k * step), tones[order[k % 8] % len(tones)],
                 _vel(vel + accent(k))) for k in range(c.length // step)]


def _chord(t, length, tones, vel, lo=55, hi=71):
    return [Note(t + 15 * i, length, p, _vel(vel)) for i, p in enumerate(notes_in(tones, lo, hi)[:4])]


def _run(t, length, pitches, v0, v1, hold=Q):
    n = len(pitches)
    step = length / n
    return [Note(int(t + i * step), int(step) + (hold if i == n - 1 else E), p,
                 _vel(v0 + (v1 - v0) * i / max(1, n - 1), 2)) for i, p in enumerate(pitches)]


def _fill(c, t, vel, top=86):
    tones = notes_in(c.tones, 69, top)[::-1][:5]
    if len(tones) < 4:
        return []
    rhythm = [(0, UNIT), (UNIT, UNIT), (2 * UNIT, UNIT), (3 * UNIT, 5 * UNIT)]
    return [Note(t + off, ln + E, p, _vel(vel - 5 * i)) for i, ((off, ln), p) in enumerate(zip(rhythm, tones))]


def piano(song, hook):
    out = []
    for c in song.chords:
        feel = c.feel
        root = nearest(notes_in([c.bass], 31, 43), 38)
        if feel == "intro":
            out.append(Note(c.start, c.length, root, _vel(38)))
            out += _chord(c.start, c.length, c.tones, 34, lo=57, hi=71)
        elif feel in ("introband", "solo"):
            out += [Note(c.start, c.length, root, _vel(54)), Note(c.start, c.length, root + 12, _vel(48))]
            for k in range(0, c.length, H):
                out += _chord(c.start + k, H, c.tones, 46)
        elif feel == "interlude":
            out += _lh_broken(c, 46)
        elif feel == "verse":
            out.append(Note(c.start, c.length, root, _vel(48)))
            out += _rh_arp(c, 48)
        elif feel == "verse2":
            out += _lh_broken(c, 40)
            out += _rh_arp(c, 36, lo=62, hi=81, step=UNIT)
        elif feel == "pre":
            v = 46 + 12 * _progress(song, c)
            for k in range(0, c.length, H):
                out += [Note(c.start + k, H, root, _vel(v)), Note(c.start + k, H, root + 12, _vel(v - 6))]
                out += _chord(c.start + k, H, c.tones, v - 4)
        elif feel in ("chorus", "chorus2"):
            out += _lh_broken(c, 62)
            out += _rh_arp(c, 62 if feel == "chorus" else 66, lo=55, hi=72)   # under the voice
        elif feel == "bridge":
            prog = _progress(song, c)
            out += _lh_broken(c, 42 + 18 * prog)
            out += _rh_arp(c, 38 + 20 * prog, lo=62, hi=86, step=UNIT)
        elif feel == "ochi":
            out.append(Note(c.start, c.length, root, _vel(34)))
            high = notes_in(c.tones, 74, 98)
            for k in range(c.length // Q):
                out.append(Note(c.start + k * Q, H, high[[0, 2, 4, 2][k % 4] % len(high)], _vel(36)))
        elif feel == "last":
            out.append(Note(c.start, c.length, root - 12 if root - 12 >= 28 else root, _vel(72)))
            out += _lh_broken(c, 66)
            for k in range(0, c.length, H):
                out += _chord(c.start + k, H, c.tones, 66, lo=55, hi=72)
        elif feel == "outro":
            if c.last_in_song:
                roll = notes_in(c.tones, 38, 86)
                out += [Note(c.start + i * 40, 2 * BAR, p, _vel(48 - i)) for i, p in enumerate(roll)]
            else:
                out += _lh_broken(c, 38)

    for n in hook:            # intro: music-box melody; intro B / interlude: the piano sings in octaves
        soft = n.pitch >= 80
        out.append(Note(n.start, n.length + E, n.pitch, _vel(58 if soft else 66)))
        if not soft:
            out.append(Note(n.start, n.length + E, n.pitch - 12, _vel(50)))

    for m, b, t0, cs in song.bars("verse"):          # a few quiet answers, verse 1 only
        if b in (1, 5) and cs and len(song.vocal_onsets(t0 + 2 * Q, t0 + BAR)) <= 1:
            out += _fill(cs[-1], t0 + 2 * Q, 40)
    for m, b, t0, cs in song.bars("chorus"):         # and in the first chorus, bars 2 and 6
        if b in (1, 5) and cs and len(song.vocal_onsets(t0 + 2 * Q, t0 + BAR)) <= 1:
            out += _fill(cs[-1], t0 + 2 * Q, 54, top=91)

    for m in song.marks:
        end = m.start + m.bars * BAR
        if m.name == "1B":                           # gentle climb into the first chorus
            out += _run(end - 2 * Q, 2 * Q, scale(2, 62, 81), 38, 66)
        if m.feel == "interlude":
            out += _run(end - 2 * Q, 2 * Q, scale(2, 62, 81)[::-1][:10], 52, 34)
        if m.feel == "bridge":
            out += _run(end - 2 * Q, 2 * Q, notes_in([9, 1, 4, 7], 57, 88)[::-1], 58, 40)
        if m.feel == "ochi":                         # Bb7 arpeggio up into the key change
            out += _run(end - 2 * Q, 2 * Q, notes_in([10, 2, 5, 8], 58, 89), 42, 72)
    return [_humanize(song, n) for n in out]


_CEILING = {"chorus": 92, "chorus2": 96, "last": 100, "bridge": 88}


def _humanize(song, n):
    """Two-bar phrase swell, ±8 ms timing, and a per-section velocity ceiling."""
    m = next(m for m in reversed(song.marks) if m.start <= n.start)
    phase = ((n.start - m.start) % (2 * BAR)) / (2 * BAR)
    v = n.velocity * (1 + 0.08 * math.sin(math.pi * phase))
    v = min(v, _CEILING.get(m.feel, 76))
    t = max(0, n.start + int(_rng.uniform(-5, 5)))
    return Note(t, n.length, n.pitch, max(1, int(v)))


# --- strings ---------------------------------------------------------------------
RANGES = {"Cello": (36, 60), "Viola": (48, 72), "Violins": (55, 88)}


def _sustain(chords, voice, target, vel, lo=None, hi=None):
    lo0, hi0 = RANGES[voice]
    lo, hi = lo or lo0, hi or hi0
    out, prev = [], target
    for c in chords:
        p = nearest(notes_in(c.tones, lo, hi), prev)
        out.append(Note(c.start, c.length, p, _vel(vel, 3)))
        prev = p
    return out


def _guide_tones(chords, lo, hi, vel, start=62):
    """Inner voice on 3rds and 7ths, which move by step from chord to chord."""
    out, prev = [], start
    for c in chords:
        root = c.tones[0]
        guides = [p for p in range(lo, hi + 1) if p % 12 in c.tones and (p - root) % 12 in (3, 4, 10, 11)]
        p = nearest(guides or notes_in(c.tones, lo, hi), prev)
        out.append(Note(c.start, c.length, p, _vel(vel, 3)))
        prev = p
    return out


def _counter(chords, lo, hi, vel, start=None):
    """A slow countermelody: half notes on chord tones, moving by step where it can."""
    out, prev, direction = [], start or (lo + hi) // 2, 1
    for c in chords:
        for k in range(0, c.length, H):
            options = notes_in(c.tones, lo, hi)
            steps = [p for p in options if 0 < (p - prev) * direction <= 4]
            p = steps[0] if direction > 0 and steps else steps[-1] if steps else nearest(options, prev)
            if p >= hi - 2 or p <= lo + 2:
                direction = -direction
            out.append(Note(c.start + k, min(H, c.length - k), p, _vel(vel, 3)))
            prev = p
    return out


def strings(song):
    cello, viola, violins = [], [], []
    by = {m.name: song.chords_of(m.name) for m in song.marks}
    intro = by["Intro"]
    violins += _sustain(intro[1:], "Violins", 81, 36, lo=76, hi=88)
    cello += _sustain(intro[2:], "Cello", 45, 42)
    for name, base in (("Intro B", 64), ("1サビ", 62), ("2サビ", 70), ("間奏", 56), ("Solo", 66)):
        cs = by[name]
        cello += _sustain(cs, "Cello", 45, base)
        viola += _guide_tones(cs, 55, 69, base - 6)
        if name in ("1サビ", "Intro B"):
            violins += _sustain(cs, "Violins", 78, base - 4, lo=72, hi=88)
        elif name == "2サビ":
            violins += _sustain(cs, "Violins", 76, base - 8, lo=69, hi=81)
        elif name == "Solo":
            violins += _counter(cs, 74, 88, base - 2, start=78)
    cello += _sustain(by["1B"], "Cello", 45, 50)
    viola += _guide_tones(by["1B"], 55, 69, 44)
    cello += _counter(by["2A"], 40, 57, 48, start=50)
    viola += _guide_tones(by["2A"], 55, 69, 40)
    for v, part, tgt in ((cello, "Cello", 45), (viola, "Viola", 62), (violins, "Violins", 74)):
        v += _sustain(by["2B"], part, tgt, 58)
    bridge = by["Cメロ"]
    cello += _sustain(bridge, "Cello", 45, 60)
    viola += _guide_tones(bridge, 55, 69, 56)
    prev = 69
    for c in bridge:
        prev = min((p for p in notes_in(c.tones, prev + 1, prev + 7)), default=prev)
        violins.append(Note(c.start, c.length, prev, _vel(54 + (c.start - bridge[0].start) / BAR * 4)))
    violins += _sustain(by["落ちサビ"][:4], "Violins", 81, 34, lo=76, hi=88)
    last = by["ラスサビ"]
    cello += _sustain(last, "Cello", 45, 72)
    viola += _guide_tones(last, 55, 69, 66)
    line = _counter(last, 76, 91, 74, start=79)
    violins += line + [Note(n.start, n.length, n.pitch - 12, n.velocity - 8) for n in line]
    outro = by["Outro"]
    cello += _sustain(outro, "Cello", 43, 48)
    viola += _guide_tones(outro, 55, 69, 42)
    violins += _sustain(outro, "Violins", 79, 40, lo=72, hi=88)
    return {"Cello": cello, "Viola": viola, "Violins": violins}


# --- bass: a singing line -----------------------------------------------------------
# Roots on the strong beats, passing notes that walk (diatonically or chromatically)
# into the next chord, octave pops, ghost notes, slides, and fills only where the
# voice holds or breathes (the end of each two-bar line). The solo gets a sixteenth
# groove with runs; the last chorus is the busiest.
BASS_LO, BASS_HI = 28, 50


def _bass_root(c, prev):
    return nearest(notes_in([c.bass], BASS_LO, BASS_HI), prev)


def _toward(song, c, frm, target, n, chromatic=False):
    """n notes stepping from frm toward target (target itself excluded)."""
    if chromatic:
        step = 1 if target >= frm else -1
        return [target - step * (n - i) for i in range(n)]
    sc = scale(song.key(c), BASS_LO - 5, BASS_HI + 5)
    if target >= frm:
        line = [p for p in sc if frm <= p < target][-n:]
    else:
        line = [p for p in sc if target < p <= frm][::-1][-n:]
    while len(line) < n:
        line.insert(0, frm)
    return line


def _fit(p):
    while p > BASS_HI:
        p -= 12
    while p < BASS_LO:
        p += 12
    return p


FILLS = ("up", "down", "chromatic", "octave")


def _bass_fill(song, c, target, t, root, kind, units=4, vel=80):
    """Sixteenths over the last `units` of a chord, landing on `target` at the next downbeat."""
    if kind == "up":
        line = _toward(song, c, target - 7, target, units)
    elif kind == "down":
        line = _toward(song, c, target + 7, target, units)
    elif kind == "chromatic":
        line = [root, root + 7 if root + 7 <= BASS_HI else root - 5] * units
        line = line[:max(0, units - 3)] + _toward(song, c, target, target, 3, chromatic=True)
    else:                                                     # octave pop, fifth, approach
        hi = root + 12 if root + 12 <= BASS_HI else root
        line = ([root, hi, root + 7 if root + 7 <= BASS_HI else root - 5] * units)[:units - 1] + [target - 1]
    return [Note(t + i * UNIT, UNIT - 12, _fit(p), _vel(vel - 2 * i if kind == "down" else vel + 2 * i, 3))
            for i, p in enumerate(line[:units])]


def _line_end(m, c):
    """True on the second bar of a two-bar line (where the melody holds or breathes)."""
    return ((c.start - m.start) // BAR) % 2 == 1 and (c.start - m.start + c.length) % BAR == 0


def bass(song):
    out, slides, prev = [], [], 38
    n_fill = 0
    for i, c in enumerate(song.chords):
        nxt = song.chords[i + 1] if i + 1 < len(song.chords) else None
        root = _bass_root(c, prev)
        prev = root
        m, _ = song.section(c)
        feel = c.feel
        bar_idx = (c.start - m.start) // BAR
        target = _bass_root(nxt, root) if nxt else root
        units = c.length // UNIT
        fifth = root + 7 if root + 7 <= BASS_HI else root - 5
        octave = root + 12 if root + 12 <= BASS_HI else root - 12 if root - 12 >= BASS_LO else root
        add = lambda off, ln, p, v: out.append(Note(c.start + off * UNIT, ln * UNIT - 14, _fit(p), _vel(v, 3)))
        ghost = lambda off, p: out.append(Note(c.start + off * UNIT, UNIT // 2, _fit(p), _vel(34, 4)))
        fill_at = lambda u, kind, v=80: out.extend(_bass_fill(song, c, target, c.start + (units - u) * UNIT, root, kind, u, v))
        line_end = _line_end(m, c) and nxt is not None
        bar_end = (c.start - m.start + c.length) % BAR == 0

        if feel in ("verse", "ochi") or (feel == "intro" and bar_idx < 2):
            continue
        if feel == "intro":                                    # enters with a slide
            add(0, units - 1, root, 66)
            slides.append((c.start, -5))
        elif feel in ("introband", "interlude"):
            add(0, 8, root, 80)
            if units > 8:
                add(8, 4, fifth, 70)
                if bar_idx == m.bars - 1 and bar_end:
                    fill_at(4, "up", 76)
                else:
                    for k, p in enumerate(_toward(song, c, fifth, target, 2)):
                        add(12 + 2 * k, 2, p, 68)
        elif feel == "pre":
            last = bar_idx == m.bars - 1
            if m.name == "2B":                                 # eighth-note pedal, then a walk up
                if last and bar_end and units == 8:                # the final half bar walks into 2サビ
                    for k, p in enumerate(_toward(song, c, root, target, 3, chromatic=True)):
                        add(2 * k, 2, p, 74 + 4 * k)
                else:
                    for k in range(units // 2):
                        add(2 * k, 2, root, 82 if k % 2 == 0 else 66)
            else:
                fill = bar_idx % 2 == 1 and bar_end and units > 4
                add(0, units - (4 if fill else 0), root, 76)
                if fill:
                    fill_at(4, "up", 70)
        elif feel == "verse2":
            add(0, 8 if units > 8 else units, root, 78)
            if units > 8:
                if line_end and bar_idx % 4 == 3:
                    add(8, 4, fifth, 70)
                    fill_at(4, FILLS[n_fill % 4], 74); n_fill += 1
                else:
                    add(8, 6, fifth, 70)
                    add(14, 2, _toward(song, c, fifth, target, 1)[0], 66)
        elif feel == "chorus":                                 # melodic eighths
            add(0, 6 if units > 8 else units - 2, root, 86)
            if units > 8:
                add(6, 2, fifth, 70)
                add(8, 4, octave if bar_idx % 2 == 0 else root, 80)
                if line_end and bar_idx % 4 == 3:
                    fill_at(4, FILLS[n_fill % 4], 78); n_fill += 1
                else:
                    for k, p in enumerate(_toward(song, c, root, target, 2)):
                        add(12 + 2 * k, 2, p, 70)
            else:
                add(units - 2, 2, _toward(song, c, root, target, 1)[0], 70)
            if bar_idx == 0:
                slides.append((c.start, -3))
        elif feel in ("chorus2", "last"):                      # syncopated groove with pops and fills
            busy = feel == "last"
            add(0, 3, root, 90)
            ghost(3, root)
            if units > 8:
                add(4, 2, octave, 74)
                add(6, 2, root, 78)
                add(8, 3, root if bar_idx % 2 == 0 else fifth, 84)
                ghost(11, root)
                if line_end and (busy or bar_idx % 4 == 3):
                    fill_at(4, FILLS[n_fill % 4], 82); n_fill += 1
                else:
                    add(12, 2, fifth, 72)
                    add(14, 2, _toward(song, c, fifth, target, 1)[0], 70)
            else:
                add(4, 2, octave, 74)
                add(6, 2, _toward(song, c, root, target, 1)[0], 72)
            if bar_idx in (0, 4) or (busy and bar_idx == 8):
                slides.append((c.start, -4))
        elif feel == "solo":                                   # the bass gets to show off
            pattern = [root, root, octave, root, fifth, root, octave, fifth]
            run = bar_idx % 2 == 1 and bar_end
            for u in range(0 if units > 8 else 0, units - (4 if run else 0)):
                p = pattern[u % 8]
                if u % 4 == 3 and u < units - 1:
                    ghost(u, p)
                else:
                    add(u, 1, p, 88 if u % 4 == 0 else 72)
            if run:
                fill_at(4, "down" if bar_idx % 4 == 1 else "chromatic", 86)
            if bar_idx % 4 == 0:
                slides.append((c.start, -5))
        elif feel == "bridge":                                 # walking quarters, then eighths
            prog = _progress(song, c)
            if prog < 0.75:
                if target == root:                             # same root next: move inside the chord
                    walk = [root, fifth, octave if octave != root else root + 5, root + 2]
                else:
                    walk = [root] + _toward(song, c, root, target, units // 4 - 1, chromatic=prog > 0.4)
                    if len(set(walk)) < len(walk):             # no room to walk: arpeggiate, then approach
                        tones = [p for p in notes_in(c.tones, root + 1, root + 12)]
                        walk = ([root] + tones)[: units // 4 - 1] + [target + (1 if target < root else -1)]
                for k, p in enumerate(walk[: units // 4]):
                    add(4 * k, 4, p, 74 + 4 * k)
            else:
                for k in range(units // 2):
                    add(2 * k, 2, root if k % 2 == 0 else octave, 80)
        elif feel == "outro":
            add(0, units - 1, root, 70)
            if c.last_in_song:
                slides.append((c.start, -2))
    return out, slides


def bass_bends(slides, song):
    """Slide-in curves: start N semitones low, glide to pitch over ~90 ms."""
    pts, glide = [], int(0.09 * song.tps)
    for t, semis in slides:
        for k in range(0, glide + 1, 10):
            x = k / glide
            pts.append((t + k, semis * (1 - x) ** 2))
        pts.append((t + glide + 10, 0.0))
    return pts


# --- guitars -----------------------------------------------------------------------
_GTOK = re.compile(r"(?P<mod>[bBr/\\h]?)(?P<pitch>[A-G][#b]?\d):(?P<dur>[\d.]+)(?P<vib>~?)")
LEAD_SCALE = {"2サビ": 0.82, "ラスサビ": 0.88, "Outro": 0.6}     # fills stay behind the voice


def lead_guitar(song, parts):
    """Parse the lead notation; returns (notes, pitch-bend points in semitones)."""
    notes, bends = [], []
    tps = song.tps
    for name, bars in parts.items():
        m = song.mark(name)
        shift = song.shift[name]
        for b, text in enumerate(bars):
            pos = float(m.start + b * BAR)
            for tok in text.split():
                if tok.startswith("_"):
                    pos += float(tok[1:]) * UNIT
                    continue
                g = _GTOK.fullmatch(tok)
                if not g:
                    raise ValueError(f"bad guitar token {tok!r} in {name}")
                target = note_number(g["pitch"]) + shift
                dur, mod, vib = float(g["dur"]) * UNIT, g["mod"], bool(g["vib"])
                played = target - (2 if mod == "b" else 1 if mod == "B" else 0)
                start, length = round(pos), round(dur)
                vel = 64 if mod == "h" else 96 if dur >= 2 * UNIT else 84
                vel *= LEAD_SCALE.get(name, 1.0)
                notes.append(Note(start, length, played, _vel(vel, 3)))
                bends += _guitar_curve(start, length, mod, vib, tps)
                pos += dur
            if abs(pos - (m.start + (b + 1) * BAR)) > 3:
                raise ValueError(f"{name} bar {b + 1}: guitar bar is {(pos - m.start - b * BAR) / UNIT:.2f}/16")
    return notes, bends


def _guitar_curve(start, length, mod, vib, tps):
    """Pitch offset (semitones vs the played note) sampled every 10 ticks."""
    def at(t):                                    # t in seconds from note start
        if mod in ("b", "B"):
            d = 2.0 if mod == "b" else 1.0
            x = min(1.0, max(0.0, (t - 0.03) / 0.12))
            base = d * (0.5 - 0.5 * math.cos(math.pi * x))
        elif mod == "r":
            hold = min(0.35 * length / tps, 0.25)
            x = min(1.0, max(0.0, (t - hold) / 0.14))
            base = 2.0 * (1 - (0.5 - 0.5 * math.cos(math.pi * x)))
        elif mod in ("/", "\\"):
            x = min(1.0, t / 0.07)
            base = (-3.0 if mod == "/" else 3.0) * (1 - x) ** 2
        else:
            base = 0.0
        if vib:
            onset = max(0.3 * length / tps, 0.12) + (0.12 if mod in ("b", "B") else 0)
            if t > onset:
                depth = 0.32 * min(1.0, (t - onset) / 0.15)
                wobble = math.sin(2 * math.pi * 5.8 * (t - onset))
                base += -depth * (0.5 - 0.5 * wobble) if mod in ("b", "B") else depth * wobble
        return base
    if mod in ("", "h") and not vib:
        return [(start, 0.0)]
    return [(start + k, at(k / tps)) for k in range(0, length, 10)] + [(start + length, at(length / tps))]


def rhythm_guitar(song, seed):
    """Power chords (root, fifth, octave): sustained or eighth-note pulses."""
    rng = random.Random(seed)
    out = []
    for c in song.chords:
        if c.feel not in ("chorus2", "solo", "last"):
            continue
        root = nearest(notes_in([c.tones[0]], 40, 51), 45)
        chord = [root, root + 7, root + 12]
        jitter = lambda: int(rng.uniform(-6, 6))
        if c.feel == "chorus2":
            for k in range(0, c.length, H):
                for i, p in enumerate(chord):
                    out.append(Note(c.start + k + 8 * i + jitter(), min(H, c.length) - 40, p, int(rng.uniform(84, 96))))
        else:
            for k in range(c.length // E):
                accent = k % 2 == 0
                for i, p in enumerate(chord):
                    out.append(Note(c.start + k * E + 5 * i + jitter(), int(E * 0.7), p,
                                    int(rng.uniform(96, 104) if accent else rng.uniform(80, 90))))
    return out


def clean_guitar(song):
    out = []
    for c in song.chords:
        if c.feel != "bridge":                      # the harp has the first half's arpeggios
            continue
        tones = notes_in(c.tones, 52, 76)[:6]
        if len(tones) < 3:
            continue
        if c.feel == "chorus":                    # sparse: two notes per half bar
            for k in range(0, c.length, H):
                out += [Note(c.start + k, H, tones[-1], _vel(54)), Note(c.start + k + Q, Q, tones[-2], _vel(48))]
            continue
        order = [0, 2, 1, 3, 2, 4, 3, 1]
        for k in range(c.length // E):
            out.append(Note(c.start + k * E, Q, tones[order[k % 8] % len(tones)], _vel(58 if k % 2 == 0 else 50)))
    return out


# --- drums -------------------------------------------------------------------------
def drums(song):
    out = []
    hit = lambda t, n, v: out.append(Note(int(t), UNIT, n, _vel(v, 5)))

    fills = [[SNARE, SNARE, TOM_HI, TOM_HI, TOM_MID, TOM_MID, TOM_LOW, TOM_LOW],
             [SNARE, TOM_HI, SNARE, TOM_HI, TOM_MID, SNARE, TOM_LOW, TOM_LOW],
             [TOM_HI, TOM_HI, TOM_MID, TOM_HI, TOM_MID, TOM_LOW, SNARE, SNARE]]
    count = [0]

    def tom_fill(t0, start_unit=8, v0=66):
        shape = fills[count[0] % len(fills)]
        count[0] += 1
        for i, n in enumerate(shape[: 16 - start_unit]):
            hit(t0 + (start_unit + i) * UNIT, n, v0 + 3 * i)
            if n == SNARE and i % 2 == 1:
                hit(t0 + (start_unit + i) * UNIT, KICK, 60 + 2 * i)

    for m in song.marks:
        for b in range(m.bars):
            t0 = m.start + b * BAR
            last_bar = b == m.bars - 1
            if m.feel == "intro" and b == m.bars - 1:
                tom_fill(t0, 8, 50)
            elif m.feel == "introband":                # gentle: the piano carries the hook
                if b == 0:
                    hit(t0, CRASH, 62)
                hit(t0, KICK, 70); hit(t0 + 8 * UNIT, STICK, 56)
                for u in range(0, 16, 2):
                    if not (b == 0 and u == 0):
                        hit(t0 + u * UNIT, HH, 40 if u % 4 == 0 else 30)
                if last_bar:
                    tom_fill(t0, 12, 46)
            elif m.feel == "verse2":
                hit(t0, KICK, 62)
                hit(t0 + 8 * UNIT, STICK, 58)
                for u in range(0, 16, 2):
                    hit(t0 + u * UNIT, HH, 44 if u % 4 == 0 else 32)
            elif m.feel == "pre" and m.name == "2B":
                hit(t0, KICK, 70)
                if last_bar:                          # build: sixteenth snares, then a breath
                    for u in range(8, 14):
                        hit(t0 + u * UNIT, SNARE, 46 + 7 * (u - 8))
                    hit(t0 + 8 * UNIT, KICK, 74)
                else:
                    hit(t0 + 8 * UNIT, KICK, 62)
                for u in range(0, 16 if not last_bar else 8, 2):
                    hit(t0 + u * UNIT, HH, 50 if u % 4 == 0 else 36)
            elif m.feel in ("chorus2", "last"):
                big = m.feel == "last"
                if b % 4 == 0:
                    hit(t0, CRASH, 96 if big else 84)
                hit(t0, KICK, 92); hit(t0 + 6 * UNIT, KICK, 66); hit(t0 + 8 * UNIT, SNARE, 92 if big else 84)
                if big:
                    hit(t0 + 10 * UNIT, KICK, 60); hit(t0 + 14 * UNIT, SNARE, 34)
                for u in (7, 15):                        # ghost notes lead into the backbeat
                    hit(t0 + u * UNIT, SNARE, 24)
                cym = RIDE if big and b >= 4 else HH
                step = 1 if big and 4 <= b < 8 else 2          # sixteenth hats drive the back half
                for u in range(0, 16, step):
                    if not (b % 4 == 0 and u == 0):
                        hit(t0 + u * UNIT, HH if step == 1 else cym,
                            58 if u % 4 == 0 else 46 if u % 2 == 0 else 30)
                if b % 2 == 1:
                    hit(t0 + 14 * UNIT, HH_OPEN, 50)
            elif m.feel == "solo":                    # double-time backbeat to drive the solo
                if b % 4 == 0:
                    hit(t0, CRASH, 96)
                for u in (0, 6, 10):
                    hit(t0 + u * UNIT, KICK, 90 if u == 0 else 72)
                for u in (4, 12):
                    hit(t0 + u * UNIT, SNARE, 90)
                for u in range(0, 16, 2):
                    if not (b % 4 == 0 and u == 0):
                        hit(t0 + u * UNIT, RIDE, 62 if u % 4 == 0 else 48)
            elif m.feel == "bridge":
                hit(t0, KICK, 74 + 2 * b)
                if b >= 4:
                    hit(t0 + 8 * UNIT, SNARE, 70 + 3 * b)
                    for u in range(0, 16, 2):                    # a floor-tom groove that builds
                        if u not in (0, 8):
                            hit(t0 + u * UNIT, TOM_LOW, 46 + 4 * (b - 4) + (8 if u % 4 == 0 else 0))
                for u in range(0, 16, 4):
                    hit(t0 + u * UNIT, RIDE, 52 + 2 * b)
            fill = (m.feel in ("chorus2", "bridge", "solo") and last_bar) or \
                   (m.feel == "last" and b in (3, 7)) or (m.feel == "solo" and b == 3)
            if fill:
                tom_fill(t0)
            if last_bar and m.next_feel == "last":
                for u in range(8, 16):
                    hit(t0 + u * UNIT, SNARE, 40 + 6 * (u - 8))
                    hit(t0 + u * UNIT + UNIT // 2, SNARE, 36 + 6 * (u - 8))
        if m.feel in ("ochi", "outro", "verse"):      # crash rings into the quieter section
            if m.feel != "verse":
                hit(m.start, CRASH, 70)
    return out


# Before these choruses everything but the harp sweep, the swells and the drum
# pickup stops for a moment, so the chorus lands on silence.
BREAKS = {"1サビ": Q, "2サビ": E}
_BREAK_PARTS = ("Piano", "Violins", "Viola", "Cello", "Bass", "Gtr Clean", "Horns", "Flute",
                "Spiccato", "Solo Violin", "Vln Trem", "Synth Pad", "Synth Pluck", "Sub")


def _breaks(song, parts):
    for name, span in BREAKS.items():
        t1 = song.mark(name).start
        t0 = t1 - span
        for track in _BREAK_PARTS:
            kept = []
            for n in parts.get(track, []):
                if t0 <= n.start < t1:
                    continue                                   # nothing new starts in the gap
                if n.start < t0 < n.start + n.length:          # held notes let go before it
                    n = Note(n.start, max(UNIT, t0 - n.start - 20), n.pitch, n.velocity)
                kept.append(n)
            parts[track] = kept
        parts["Drums"] = [n for n in parts["Drums"] if not (t0 <= n.start < t1 and n.pitch == HH)]


_LEGATO = ("Violins", "Viola", "Cello", "Horns", "Flute", "Solo Violin")


def _feel(parts):
    """Sustained lines overlap a little at each change; drums sit slightly off the grid."""
    rng = random.Random(5)
    for track in _LEGATO:
        parts[track] = [Note(n.start, n.length + 40, n.pitch, n.velocity) for n in parts[track]]
    loose = {HH: 6, HH_OPEN: 6, RIDE: 6, SNARE: 3, KICK: 2}
    parts["Drums"] = [Note(max(0, n.start + int(rng.uniform(-loose.get(n.pitch, 0), loose.get(n.pitch, 0)))),
                           n.length, n.pitch, n.velocity) for n in parts["Drums"]]


def arrange(marks, chords, vocal, transposes, hook, lead_parts, bpm):
    import electro                                  # both import this module's helpers
    import orchestra
    song = Song(marks, chords, vocal, transposes, bpm)
    parts = {"Piano": piano(song, hook)}
    parts.update(strings(song))
    parts["Bass"], slides = bass(song)
    lead, lead_bends = lead_guitar(song, lead_parts)
    parts["Gtr Lead"] = lead
    parts["Gtr Rhythm L"] = rhythm_guitar(song, 1)
    parts["Gtr Rhythm R"] = rhythm_guitar(song, 2)
    parts["Gtr Clean"] = clean_guitar(song)
    parts["Drums"] = drums(song)
    orch = orchestra.orchestra(song, hook)
    last = song.mark("ラスサビ")
    a, b = last.start, last.start + last.bars * BAR
    parts["Violins"] = [n for n in parts["Violins"] if not a <= n.start < b] + orch.pop("Violins Last")
    parts.update(orch)
    el, duck = electro.electro(song, parts["Drums"])
    parts.update(el)
    for name in ("2サビ", "ラスサビ"):                 # the pluck takes over the harp's ripples there
        m = song.mark(name)
        parts["Harp"] = [n for n in parts["Harp"] if not m.start <= n.start < m.start + m.bars * BAR]
    _breaks(song, parts)
    _feel(parts)
    bends = {"Gtr Lead": lead_bends, "Bass": bass_bends(slides, song), "__sidechain__": duck}
    return parts, bends
