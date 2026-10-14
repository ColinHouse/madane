"""まだね v2 (archived 2026-10-14) — the melody out/miku.wav was exported from.

Melody bars are written as tokens like と2A4: sung syllable, length in 16th
notes, pitch. _2 is a rest, ー holds the previous vowel. Every bar adds up to
16. Particles are spelled as sung (は→わ, を→お, へ→え) and っ is a rest.
Every line ends on a held note followed by a rest of at least an eighth (the
breath). Written in D major; a section's `transpose` shifts it.
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
    "_2 ご2D4 ぜ1D4 ん1C#4 に2D4 じ2E4 の4F#4 _2",            # 午前二時の
    "あ2F#4 お1E4 い1D4 ひ2E4 か2D4 り6B3 _2",                  # 青い光
    "_2 は1D4 じ1E4 め2F#4 て2G4 な2A4 ら2B4 し2A4 た2F#4",     # 初めて鳴らした
    "あ4A4 の2G4 お2E4 と6F#4 _2",                              # 「あ」の音
    "_2 た1E4 よ1F#4 り2G4 な2F#4 く2E4 ゆ2F#4 れ2E4 た2D4",    # 頼りなく揺れた
    "そ2E4 の2F#4 こ3A4 え1G4 お6F#4 _2",                       # その声を
    "_2 い2B4 ま2A4 も2G4 ま2F#4 だ4D4 _2",                     # 今もまだ
    "お1E4 ぼ1F#4 え2G4 て2F#4 い2E4 る2C#4 よ6E4",             # 覚えているよ
]
VERSE_1B = [
    "_2 ひ2G4 と2A4 つ2B4 ず2A4 つ4G4 _2",                      # ひとつずつ
    "お1A4 ん1A4 ぷ2B4 お2C#5 な2B4 ら2A4 べ2B4 て4C#5",        # 音符を並べて
    "_2 い1C#5 き1C#5 つ2B4 ぎ2A4 の2B4 ば2C#5 しょ2D5 ま1C#5 で1B4",  # 息継ぎの場所まで
    "わ1B4 た1A4 し2G4 が2A4 か2B4 い2C#5 た4A4 _2",            # 私が描いた
]
CHORUS_1 = [
    "と2D5 き2C#5 の2B4 さ4D5 く2C#5 ら2B4 が2A4",              # 時の桜が
    "ま2B4 い2A4 お2G4 ち2F#4 る6E4 _2",                        # 舞い落ちる
    "_2 い1A4 え1A4 な2B4 か1C#5 _1 た2C#5 お2D5 も2C#5 い1B4 お1A4",  # 言えなかった想いを
    "あ1B4 な1C#5 た2D5 が2C#5 う2B4 た2A4 う4B4 _2",            # あなたが歌う
    "_2 さ2B4 よ2D5 な2E5 ら2D5 わ4B4 _2",                      # 「さよなら」は
    "お2C#5 も2D5 す2C#5 ぎ2B4 る2A4 か2B4 ら4C#5",             # 重すぎるから
    "_2 ま3A4 た1B4 ね4D5 _1 て1C#5 て2B4 お2A4",               # 「またね」って 手を
    "ふ2G4 る2E4 よ10D4 _2",                                    # 振るよ
]

# --- 2番 --------------------------------------------------------------------
VERSE_2A = [
    "_2 い2D4 そ1D4 が1C#4 し2D4 さ2E4 に4F#4 _2",              # 忙しさに
    "ま2F#4 ぎ1E4 れ1D4 た2E4 ひ2D4 び6B3 _2",                  # 紛れた日々
    "_2 ひ1D4 ら1E4 か2F#4 な2G4 い2A4 ま2B4 ま2A4 の2F#4",     # 開かないままの
    "ふぉ2A4 る2G4 だ2E4 の2F#4 な2E4 か4F#4 _2",               # フォルダの中
    "_2 あ1E4 な1F#4 た2G4 わ2F#4 い2E4 ま2F#4 も4E4",          # あなたは今も
    "お2E4 な2F#4 じ2A4 こ2A4 え2G4 で4F#4 _2",                 # 同じ声で
    "_2 わ2B4 た2A4 し2G4 お2F#4 ま3G4 _1 て2F#4",              # 私を待って
    "い2E4 た2F#4 ん2E4 だ2C#4 ね6E4 _2",                       # いたんだね
]
VERSE_2B = [
    "_2 お1G4 と1G4 な2A4 に2B4 な2A4 る2B4 ほ2C#5 ど2B4",      # 大人になるほど
    "よ1A4 る1A4 が2B4 み2C#5 じ2B4 か2A4 く2B4 て4C#5",        # 夜が短くて
    "_2 ご1C#5 め1C#5 ん2B4 ね2A4 さ2B4 え4C#5 _2",             # ごめんねさえ
    "う1B4 ま1A4 く2G4 い2A4 え2B4 な2C#5 い4A4 _2",            # うまく言えない
]
CHORUS_2 = CHORUS_1[:2] + [
    "_2 か1A4 わ1A4 ら2B4 な2C#5 い2C#5 こ2D5 え2C#5 で2B4",    # 変わらない声で
    CHORUS_1[3],                                                # あなたが歌う
    CHORUS_1[4],                                                # 「さよなら」は
    "ま2C#5 だ2D5 い2C#5 え2B4 な2B4 い6A4",                   # まだ言えない
    "_2 ら2A4 い2B4 ね2D5 ん2C#5 も4B4 _2",                     # 来年も
    "こ1A4 こ1G4 で2F#4 あ2E4 お2F#4 ー2E4 ね6D4",              # ここで会おうね
]

# --- Cメロ / 落ちサビ / ラスサビ / Outro ------------------------------------
BRIDGE = [
    "_2 い1D4 つ1E4 か2F#4 わ1G4 た1A4 し2B4 が4A4 _2",         # いつか私が
    "こ1Bb4 こ1A4 に2G4 こ1A4 な1Bb4 く1A4 な1G4 _1 て1E4 も4D4 _2",  # ここに来なくなっても
    "_2 あ2C#5 な2C#5 た2B4 わ2A4 き3C#5 _1 と2B4",             # あなたはきっと
    "こ1A4 こ1B4 で2D5 ま2C#5 つ1B4 ん1A4 だ2B4 ろ4F#4 _2",     # ここで待つんだろう
    "_2 は2B4 る2B4 が2D5 く2E5 る2D5 た2B4 び2D5",             # 春が来るたび
    "あ1C#5 の1D5 ひ2E5 の2D5 こ2C#5 え2A#4 で4C#5 _2",         # あの日の声で
    "_2 だ2D5 れ2C#5 も2B4 い2B4 な2A4 い1B4 へ1A4 や1F#4 で1F#4",  # 誰もいない部屋で
    "う2G4 た2A4 う2B4 の2A4 か2G4 な4E4 _2",                   # 歌うのかな
]
OCHI = CHORUS_1[:2] + [
    "_2 い1A4 え1A4 な2B4 か1C#5 _1 た2C#5 お2D5 も2C#5 い1B4 わ1A4",  # 言えなかった想いは
    "も1B4 ー1C#5 う2D5 た2C#5 に2B4 な1A4 _1 た4B4 _2",        # もう歌になった
    "_2 わ2G4 た2A4 し2B4 が2A4 い2G4 つ2A4 か2B4",             # 私がいつか
    "い2C#5 な2B4 く2A4 な1A4 _1 て2B4 も4C#5 _2",              # いなくなっても
    "_2 こ2D5 の2C#5 こ2B4 え2A4 だ2B4 け2C#5 わ2D5",           # この声だけは
    "こ1C#5 こ1B4 に2A4 の2B4 こ2A4 る6Bb4 _2",                 # ここに残る
]
LAST = CHORUS_1 + [
    "_2 な2B4 ん2B4 ど4D5 は2C#5 る2B4 が2A4",                  # 何度 春が
    "め2G4 ぐ1A4 _1 て2B4 も8A4 _2",                            # 巡っても
]
OUTRO_VOCAL = [
    "_2 さ2F#4 よ2G4 な4A4 ら2B4 わ4A4",                        # さよならは
    "_8 ま4F#4 だ4E4",                                          # まだ
    "ね12D4 _4",                                                # ね
    REST,
]

HOOK = CHORUS_1[:4]          # piano plays the chorus opening in the intro/interlude

# --- song form --------------------------------------------------------------
# v2 form: the timeline the Miku vocal was exported on.
SECTIONS_V2 = [
    dict(name="Intro", chords=HOOK_CHORDS, hook=HOOK, feel="intro"),
    dict(name="1A", chords=A_CHORDS, vocal=VERSE_1A, feel="verse"),
    dict(name="1B", chords=B_CHORDS, vocal=VERSE_1B, feel="pre"),
    dict(name="1サビ", chords=CHORUS_CHORDS, vocal=CHORUS_1, feel="chorus"),
    dict(name="間奏", chords=HOOK_CHORDS, hook=HOOK, feel="interlude"),
    dict(name="2A", chords=A_CHORDS, vocal=VERSE_2A, feel="verse2"),
    dict(name="2B", chords=B_CHORDS, vocal=VERSE_2B, feel="pre"),
    dict(name="2サビ", chords=CHORUS2_CHORDS, vocal=CHORUS_2, feel="chorus2"),
    dict(name="Cメロ", chords=BRIDGE_CHORDS, vocal=BRIDGE, feel="bridge"),
    dict(name="落ちサビ", chords=OCHI_CHORDS, vocal=OCHI, feel="ochi"),
    dict(name="ラスサビ", chords=LAST_CHORDS, vocal=LAST, feel="last", transpose=1),
    dict(name="Outro", chords=OUTRO_CHORDS, vocal=OUTRO_VOCAL, feel="outro", transpose=1),
]

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
