"""まだね v4 — slow ballad: melody, lyrics and chords.

Melody bars are written as tokens like と2A4: sung syllable, length in 16th
notes, pitch. _2 is a rest, ー holds the previous vowel. Every bar adds up to
16. Particles are spelled as sung (は→わ, を→お, へ→え) and っ is a rest
(the VOCALOID writer shortens that gap to a 32nd).
Written in D major; a section's `transpose` shifts it.

v3 (譜割り, after "the words and the melody don't match"): breaths only where
the sentence pauses; a phrase's highest or longest note on the word that
matters, not on a particle or a weak mora; short words keep their pitch
accent where the melody allows; っ off the strong beats.

v4 (after "some lines sound recited, not sung"): no line runs more than a few
even eighths in a row — each has a held syllable or a dotted figure; ん is a
quick sixteenth; four dense lines lose a word (場所まで→場所も,
想いを/想いは→想い, ここに来なくなっても→来なくなっても).
"""

TITLE = "まだね"
BPM = 80

# --- chords (one per bar; two names split the bar in half) -----------------
HOOK_CHORDS = ["Gmaj7", "A", "F#m7", "Bm7"]
A_CHORDS = ["Bm", "Bm/A", "Gmaj7", "F#m7", "Em7", "D/F#", "Gmaj7", "Asus4 A"]
B_CHORDS = ["Gmaj7", "A/G", "F#m7 Bm7", "Em7 A7"]
CHORUS_CHORDS = ["Gmaj7", "A", "F#m7", "Bm7", "Em7", "F#m7", "Gmaj7 A7", "D"]
CHORUS2_CHORDS = CHORUS_CHORDS[:7] + ["Bm"]          # deceptive ending: sadder
BRIDGE_CHORDS = ["Gmaj7", "Gm6", "F#m7", "Bm7", "Em7", "F#7", "Bm7 Bm7/A", "Gmaj7 A7sus4"]
OCHI_CHORDS = CHORUS_CHORDS[:6] + ["Gmaj7", "A Bb7"]  # Bb7 pivots up to E♭
LAST_CHORDS = CHORUS_CHORDS + ["Gmaj7", "Asus4 A"]
OUTRO_CHORDS = ["Gmaj7", "A", "D", "D"]

REST = "_16"

# --- 1番 --------------------------------------------------------------------
VERSE_1A = [
    "_2 ご2F#4 ぜ1E4 ん1D4 に2F#4 じ4E4 の2D4 あ2E4",          # 午前二時の青い光: 二時 is held,
    "お2F#4 い2E4 ひ2D4 か2E4 り8B3",                          # and the line runs on to 光
    "_2 は1D4 じ1F#4 め2E4 て2D4 な3E4 ら1F#4 し2G4 た2A4",    # 初めて鳴らした
    "あ6B4 の2A4 お2E4 と6F#4",                                # 「あ」 rings: the first sound
    "_2 た1E4 よ1F#4 り3G4 な1F#4 く2E4 ゆ3D4 れ1E4 た2F#4",   # 頼りなく揺れた: it wavers
    "そ2E4 の2F#4 こ4A4 え2G4 お4F#4 _2",                       # その声を
    "_2 い2B4 ま2A4 も2G4 ま2F#4 だ4D4 _2",                     # 今もまだ
    "お1E4 ぼ1F#4 え3G4 て1F#4 い2E4 る2C#4 よ6E4",             # 覚えているよ
]
VERSE_1B = [
    "_2 ひ2F#4 と2A4 つ2G4 ず2A4 つ4B4 _2",                     # ひとつずつ: one step up at a time
    "お1A4 ん1B4 ぷ2C#5 お2A4 な2A4 ら1B4 べ1B4 て4C#5 _2",     # 音符を並べて
    "い1A4 き1B4 つ2C#5 ぎ2C#5 の2B4 ば2C#5 しょ4D5 も2C#5",   # 息継ぎの場所も — and she breathes
    "_2 わ1G4 た1A4 し2B4 が2A4 か3C#5 い1B4 た2A4 _2",          # right there; 描いた peaks on か
]
CHORUS_1 = [
    "と2D5 き2C#5 の2B4 さ4D5 く2C#5 ら2B4 が2A4",              # 時の桜が
    "ま2B4 い2A4 お2G4 ち2F#4 る6E4 _2",                        # 舞い落ちる
    "_2 い1A4 え1A4 な2B4 か2C#5 _1 た1C#5 お3D5 も1C#5 い2B4",  # 言えなかった想い
    "あ1B4 な1D5 た2C#5 が2B4 う2A4 た2B4 う4C#5 _2",            # あなたが歌う (ends on the 9th)
    "_2 さ2B4 よ2D5 な4E5 ら2D5 わ2B4 _2",                      # 「さよなら」は: the cry is held
    "お2A4 も3C#5 す1B4 ぎ2A4 る2F#4 か2E4 ら4F#4",             # 重すぎるから: heavy, so it sinks
    "_2 ま2A4 た2B4 ね3D5 _1 て2C#5 _2 て2B4",                  # 「またね」って — 手を
    "お2A4 ふ2E4 る2F#4 よ8D4 _2",                              # 振るよ
]

# --- 2番 --------------------------------------------------------------------
VERSE_2A = [
    "_2 い2F#4 そ1E4 が1D4 し2F#4 さ2E4 に4D4 ま2E4",          # 忙しさに紛れた日々
    "ぎ2F#4 れ2E4 た2D4 ひ2E4 び8B3",
    "_2 ひ1D4 ら1E4 か2F#4 な2G4 い3A4 ま1B4 ま2A4 の2F#4",     # 開かないままの
    "ふぉ4A4 る2G4 だ2E4 の2F#4 な2E4 か4F#4",                 # フォルダの中
    "_2 あ1E4 な1G4 た3F#4 わ1E4 い2G4 ま2E4 も2D4 _2",         # あなたは今も、
    "お2D4 な2E4 じ2F#4 こ4A4 え2G4 で4F#4",                    # 同じ声で (声 as in 1A)
    "_2 わ2G4 た2A4 し2B4 お2A4 ま3B4 _1 て2A4",                # 私を待って
    "い2E4 た2F#4 ん1E4 だ3D4 ね6C#4 _2",                       # いたんだね: sus4 → 3rd
]
VERSE_2B = [
    "_2 お1F#4 と1G4 な4A4 に2G4 な2A4 る1B4 ほ1C#5 ど2B4",      # 大人になるほど
    "よ1A4 る1G4 が2A4 み3B4 じ1C#5 か2B4 く1A4 て3C#5 _2",     # 夜が短くて
    "_2 ご2D5 め3C#5 ん1B4 ね3A4 さ1A4 え2B4 _2",               # (a beat of hesitation) ごめんねさえ
    "う1B4 ま1A4 く2G4 い3A4 え1B4 な2C#5 い4A4 _2",            # うまく言えない
]
CHORUS_2 = CHORUS_1[:2] + [
    "_2 か1A4 わ1A4 ら2B4 な2C#5 い1C#5 こ3D5 え2C#5 で2B4",    # 変わらない声で
    CHORUS_1[3],                                                # あなたが歌う
    CHORUS_1[4],                                                # 「さよなら」は
    "ま3D5 だ1C#5 い2B4 え2C#5 な2B4 い6A4",                   # まだ言えない (まだ HL, leaning)
    "_2 ら2A4 い2B4 ね3D5 ん1C#5 も4B4 _2",                     # 来年も
    "こ1F#4 こ1G4 で2A4 あ2G4 お2F#4 ー2E4 ね6D4",              # ここで会おうね
]

# --- Cメロ / 落ちサビ / ラスサビ / Outro ------------------------------------
BRIDGE = [
    "_2 い1F#4 つ1E4 か2D4 わ1G4 た1A4 し2B4 が4A4 _2",         # いつか私が
    "こ2Bb4 な2A4 く2G4 な3A4 _1 て2E4 も4D4",                  # 来なくなっても
    "_2 あ2B4 な2C#5 た2B4 わ2A4 き3C#5 _1 と2C#5",             # あなたはきっと
    "こ1B4 こ1C#5 で2B4 ま3D5 つ1C#5 ん1B4 だ1A4 ろ4F#4 _2",    # ここで待つんだろう (待 leans)
    "_2 は3C#5 る1B4 が2B4 く4E5 る2D5 た1B4 び1D5",            # 春が来るたび: 来 is held
    "あ1C#5 の1D5 ひ2E5 の2D5 こ2C#5 え2A#4 で4C#5 _2",         # あの日の声で
    "だ3D5 れ1C#5 も2B4 い2B4 な1A4 い1B4 へ2F#4 や4A4",        # 誰もいない部屋で
    "で2G4 う2F#4 た2G4 う2A4 の1G4 か1F#4 な4E4 _2",           # 歌うのかな
]
OCHI = CHORUS_1[:2] + [
    "_2 い1A4 え1A4 な2B4 か2C#5 _1 た1C#5 お3D5 も1C#5 い2B4",  # 言えなかった想い
    "も3B4 ー1A4 う2B4 た2C#5 に2B4 な1A4 _1 た4B4",            # もう 歌になった
    "_2 わ1G4 た1A4 し2B4 が2A4 い3B4 つ1A4 か4G4",             # 私がいつか
    "い2A4 な2B4 く2C#5 な1B4 _1 て2B4 も4C#5 _2",              # いなくなっても
    "_2 こ2C#5 の2D5 こ4E5 え2D5 だ2C#5 け1B4 わ1A4",           # この声だけは (the top on 声)
    "こ1C#5 こ1B4 に2A4 の2A4 こ2B4 る6Bb4 _2",                 # ここに残る
]
LAST = CHORUS_1 + [
    "_2 な3D5 ん1C#5 ど4B4 は2C#5 る2B4 が2A4",                  # 何度 春が
    "め2G4 ぐ1A4 _1 て2B4 も8A4 _2",                            # 巡っても
]
OUTRO_VOCAL = [
    "_2 さ2F#4 よ2G4 な4A4 ら2B4 わ4A4",                        # さよならは
    "_8 ま4F#4 だ4E4",                                          # まだ
    "ね12D4 _4",                                                # ね
    REST,
]

HOOK = CHORUS_1[:4]          # piano plays the chorus opening in the intro/interlude

# --- electric guitar lead ----------------------------------------------------
# Tokens: [mod]PITCH:DUR[~], DUR in 16ths. mod: b = bend up a whole step into
# the note, B = half-step bend, r = release from a whole step above, / and \ =
# slide in from 3 semitones below/above, h = legato (hammer-on/pull-off).
# ~ = vibrato. _DUR = rest.
SEXT = 0.6667
# The first half of the song belongs to the piano; the guitar enters at 2サビ.
GUITAR_LEAD = {
    "2サビ": [REST, "_8 E5:1 F#5:1 A5:2 bB5:4~", REST, REST,
             REST, "_8 C#5:1 E5:1 F#5:2 bA5:4~", REST, REST],
    "Solo": [
        "_2 bB4:6~ A4:2 hB4:2 D5:4~",
        "C#5:3 hD5:1 C#5:2 A4:2 /E5:8~",
        "_1 E5:1 F#5:2 E5:2 C#5:2 bE5:8~",
        "D5:2 C#5:2 B4:2 A4:2 F#4:2 A4:2 hB4:4~",
        "B4:1 D5:1 E5:1 F#5:1 G5:2 F#5:1 E5:1 D5:2 E5:1 F#5:1 rA5:4~",
        " ".join(f"{p}:{SEXT}" for p in "C#5 E5 F#5 A5 F#5 E5 C#5 E5 F#5 A5 C#6 A5".split()) + " bC#6:8~",
        "D6:4~ C#6:2 B5:2 A5:2 hB5:1 A5:1 G5:2 E5:2",
        "bF#5:8~ E5:2 D5:2 A4:4",
    ],
    "ラスサビ": [REST, "_8 E5:1 F#5:1 A5:2 bB5:4~", REST, REST,
              REST, "_8 C#5:1 E5:1 F#5:2 bA5:4~", REST, REST,
              "_8 D5:1 E5:1 F#5:1 A5:1 bB5:4~", REST],
    "Outro": [REST, REST, REST, "_4 bF#5:12~"],
}

INTRO_B_CHORDS = ["Gmaj7", "A", "F#m7 Bm7", "Em7 A7sus4"]

# v5 form: 8-bar intro (soft, then the band with the guitar hook) and an
# 8-bar guitar solo between 2サビ and Cメロ.
SECTIONS = [
    dict(name="Intro", chords=HOOK_CHORDS, hook=HOOK, hook_octave=12, feel="intro"),
    dict(name="Intro B", chords=INTRO_B_CHORDS, hook=HOOK, feel="introband"),
    dict(name="1A", chords=A_CHORDS, vocal=VERSE_1A, feel="verse"),
    dict(name="1B", chords=B_CHORDS, vocal=VERSE_1B, feel="pre"),
    dict(name="1サビ", chords=CHORUS_CHORDS, vocal=CHORUS_1, feel="chorus"),
    dict(name="間奏", chords=HOOK_CHORDS, hook=HOOK, feel="interlude"),
    dict(name="2A", chords=A_CHORDS, vocal=VERSE_2A, feel="verse2"),
    dict(name="2B", chords=B_CHORDS, vocal=VERSE_2B, feel="pre"),
    dict(name="2サビ", chords=CHORUS2_CHORDS, vocal=CHORUS_2, feel="chorus2"),
    dict(name="Solo", chords=CHORUS_CHORDS, feel="solo"),
    dict(name="Cメロ", chords=BRIDGE_CHORDS, vocal=BRIDGE, feel="bridge"),
    dict(name="落ちサビ", chords=OCHI_CHORDS, vocal=OCHI, feel="ochi"),
    dict(name="ラスサビ", chords=LAST_CHORDS, vocal=LAST, feel="last", transpose=1),
    dict(name="Outro", chords=OUTRO_CHORDS, vocal=OUTRO_VOCAL, feel="outro", transpose=1),
]
