"""まだね v3 (archived 2026-10-14) — the melody out/miku_v3.wav was exported from.

Melody bars are written as tokens like と2A4: sung syllable, length in 16th
notes, pitch. _2 is a rest, ー holds the previous vowel. Every bar adds up to
16. Particles are spelled as sung (は→わ, を→お, へ→え) and っ is a rest.
Written in D major; a section's `transpose` shifts it.

v3 text setting (譜割り) rules, after "the words and the melody don't match":
breaths fall only where the sentence pauses (never inside 午前二時の青い光);
a phrase's highest or longest note goes to the word that matters, not to a
particle (を/で/は) or a weak mora (ん, the い of 描いた); short words keep
their pitch accent where the melody allows (今 HL, 声 HL, 私 LHH, まだ HL);
っ never lands on a strong beat; ごめんね gets room and a sigh instead of
being rushed.
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
    "_2 ご2F#4 ぜ1E4 ん1D4 に2E4 じ2D4 の2D4 あ2F#4 お2A4",     # 午前二時の青い光: one breath,
    "い2F#4 ひ2E4 か2F#4 り8B3 _2",                            # the light sinks to the root
    "_2 は1D4 じ1F#4 め2E4 て2D4 な2E4 ら2F#4 し2G4 た2A4",    # 初めて鳴らした: climbs to…
    "あ4B4 の2A4 お2E4 と6F#4 _2",                              # …「あ」, the top of the line
    "_2 た1E4 よ1F#4 り2G4 な2F#4 く2E4 ゆ2D4 れ2E4 た2F#4",   # 頼りなく揺れた: wavers
    "そ2E4 の2F#4 こ4A4 え2G4 お4F#4 _2",                       # その声を: the weight is on 声
    "_2 い2B4 ま2A4 も2G4 ま2F#4 だ4D4 _2",                     # 今もまだ
    "お1E4 ぼ1F#4 え2G4 て2F#4 い2E4 る2C#4 よ6E4",             # 覚えているよ
]
VERSE_1B = [
    "_2 ひ2F#4 と2A4 つ2G4 ず2A4 つ4B4 _2",                     # ひとつずつ: one step up at a time
    "お1A4 ん1B4 ぷ2C#5 お2A4 な2A4 ら2B4 べ2B4 て2C#5 _2",     # 音符を並べて
    "い1A4 き1B4 つ2C#5 ぎ2C#5 の2B4 ば2C#5 しょ2D5 ま2C#5 で2B4",  # 息継ぎの場所まで — and she
    "_2 わ1G4 た1A4 し2B4 が2A4 か3C#5 い1B4 た2A4 _2",          # breathes right there; 描いた peaks on か
]
CHORUS_1 = [
    "と2D5 き2C#5 の2B4 さ4D5 く2C#5 ら2B4 が2A4",              # 時の桜が
    "ま2B4 い2A4 お2G4 ち2F#4 る6E4 _2",                        # 舞い落ちる
    "_2 い1A4 え1A4 な2B4 か1C#5 _1 た2C#5 お2D5 も2C#5 い1B4 お1A4",  # 言えなかった想いを
    "あ1B4 な1D5 た2C#5 が2B4 う2A4 た2B4 う4C#5 _2",            # あなたが歌う (ends on the 9th)
    "_2 さ2B4 よ2D5 な2E5 ら2D5 わ4B4 _2",                      # 「さよなら」は
    "お2A4 も2C#5 す2B4 ぎ2A4 る2F#4 か2E4 ら4F#4",             # 重すぎるから: heavy, so it sinks
    "_2 ま2A4 た2B4 ね3D5 _1 て2C#5 _2 て2B4",                  # 「またね」って — 手を
    "お2A4 ふ2E4 る2F#4 よ8D4 _2",                              # 振るよ
]

# --- 2番 --------------------------------------------------------------------
VERSE_2A = [
    "_2 い2F#4 そ1E4 が1D4 し2E4 さ2D4 に2D4 ま2F#4 ぎ2A4",     # 忙しさに紛れた日々: one breath
    "れ2F#4 た2E4 ひ2F#4 び8B3 _2",
    "_2 ひ1D4 ら1E4 か2F#4 な2G4 い2A4 ま2B4 ま2A4 の2F#4",     # 開かないままの
    "ふぉ2A4 る2G4 だ2E4 の2F#4 な2F#4 か4E4 _2",               # フォルダの中 (left unresolved)
    "_2 あ1E4 な1G4 た2F#4 わ2E4 い2G4 ま2E4 も2D4 _2",         # あなたは今も、
    "お2D4 な2E4 じ2F#4 こ4A4 え2G4 で4F#4",                    # 同じ声で (声 as in 1A)
    "_2 わ2G4 た2A4 し2B4 お2A4 ま3B4 _1 て2A4",                # 私を待って
    "い2E4 た2F#4 ん2E4 だ2D4 ね6C#4 _2",                       # いたんだね: sus4 → 3rd
]
VERSE_2B = [
    "_2 お1F#4 と1G4 な2A4 に2G4 な2A4 る2B4 ほ2C#5 ど2B4",      # 大人になるほど
    "よ1A4 る1G4 が2A4 み2B4 じ2C#5 か2B4 く2A4 て2C#5 _2",     # 夜が短くて
    "_2 ご2D5 め2C#5 ん2B4 ね3A4 さ1A4 え2B4 _2",               # (a beat of hesitation) ごめんねさえ
    "う1B4 ま1A4 く2G4 い2A4 え2B4 な2C#5 い4A4 _2",            # うまく言えない
]
CHORUS_2 = CHORUS_1[:2] + [
    "_2 か1A4 わ1A4 ら2B4 な2C#5 い2C#5 こ2D5 え2C#5 で2B4",    # 変わらない声で
    CHORUS_1[3],                                                # あなたが歌う
    CHORUS_1[4],                                                # 「さよなら」は
    "ま2D5 だ2C#5 い2B4 え2C#5 な2B4 い6A4",                   # まだ言えない (まだ HL)
    "_2 ら2A4 い2B4 ね2D5 ん2C#5 も4B4 _2",                     # 来年も
    "こ1F#4 こ1G4 で2A4 あ2G4 お2F#4 ー2E4 ね6D4",              # ここで会おうね
]

# --- Cメロ / 落ちサビ / ラスサビ / Outro ------------------------------------
BRIDGE = [
    "_2 い1F#4 つ1E4 か2D4 わ1G4 た1A4 し2B4 が4A4 _2",         # いつか私が
    "こ1Bb4 こ1A4 に2G4 こ2A4 な1Bb4 く1A4 な2G4 _1 て1E4 も4D4",  # ここに来なくなっても
    "_2 あ2B4 な2C#5 た2B4 わ2A4 き3C#5 _1 と2C#5",             # あなたはきっと
    "こ1B4 こ1C#5 で2B4 ま2D5 つ1C#5 ん1B4 だ2A4 ろ4F#4 _2",    # ここで待つんだろう (peak on 待)
    "_2 は2C#5 る2B4 が2B4 く2E5 る2D5 た2B4 び2D5",            # 春が来るたび
    "あ1C#5 の1D5 ひ2E5 の2D5 こ2C#5 え2A#4 で4C#5 _2",         # あの日の声で
    "だ2D5 れ2C#5 も2B4 い2B4 な2A4 い2B4 へ1F#4 や3A4",        # 誰もいない部屋で
    "で2G4 う2F#4 た2G4 う2A4 の1G4 か1F#4 な4E4 _2",           # 歌うのかな
]
OCHI = CHORUS_1[:2] + [
    "_2 い1A4 え1A4 な2B4 か1C#5 _1 た2C#5 お2D5 も2C#5 い1B4 わ1A4",  # 言えなかった想いは
    "も2B4 ー2A4 う2B4 た2C#5 に2B4 な1A4 _1 た4B4",            # もう 歌になった
    "_2 わ2G4 た2A4 し2B4 が2A4 い2B4 つ2A4 か2G4",             # 私がいつか
    "い2A4 な2B4 く2C#5 な1B4 _1 て2B4 も4C#5 _2",              # いなくなっても
    "_2 こ2C#5 の2D5 こ4E5 え2D5 だ2C#5 け1B4 わ1A4",           # この声だけは (the top on 声)
    "こ1C#5 こ1B4 に2A4 の2A4 こ2B4 る6Bb4 _2",                 # ここに残る
]
LAST = CHORUS_1 + [
    "_2 な2D5 ん2C#5 ど4B4 は2C#5 る2B4 が2A4",                  # 何度 春が
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
