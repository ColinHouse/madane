"""Four-bar format test: Miku V4X sings the chorus hook a cappella.

The melody here is a placeholder; it only checks that VOCALOID5 loads the
generated file with the right voicebank and phonemes.
"""
from pathlib import Path

import vpr

E, S, Q = vpr.TPQ // 2, vpr.TPQ // 4, vpr.TPQ
Fs4, G4, A4, B4, Cs5, D5, E4 = 66, 67, 69, 71, 73, 74, 64

HOOK = [
    # 時の桜
    ("と", E, Fs4), ("き", E, G4), ("の", E, A4), ("さ", Q, D5), ("く", E, Cs5), ("ら", Q, B4),
    # 舞い散る中で
    ("ま", E, A4), ("い", E, B4), ("ち", E, Cs5), ("る", E, B4), ("な", E, A4), ("か", E, Fs4), ("で", Q, E4),
    # 言えなかった想いを
    ("い", E, A4), ("え", E, A4), ("な", E, B4), ("か", S, Cs5), (None, S, None),
    ("た", E, Cs5), ("お", E, B4), ("も", E, A4), ("い", S, Fs4), ("を", S, A4),
    # あなたが歌う
    ("あ", E, B4), ("な", E, Cs5), ("た", E, D5), ("が", E, Cs5), ("う", E, B4), ("た", E, A4), ("う", Q + E, B4),
]

notes, end = vpr.notes_from_events(HOOK)
part_len = 5 * vpr.BAR
song = vpr.project(
    title="pipeline_test",
    bpm=130,
    tracks=[vpr.track("Miku Original", [vpr.part(vpr.BAR, part_len, notes)])],
    length_ticks=vpr.BAR + part_len,
)

out = Path(__file__).resolve().parent.parent / "test" / "pipeline_test.vpr"
out.parent.mkdir(exist_ok=True)
vpr.write_vpr(out, song)
print(f"wrote {out} ({len(notes)} notes, last note ends at tick {end})")
