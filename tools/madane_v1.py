"""まだね — melody, lyrics and chords.

Melody bars are written as tokens like と2A4: sung syllable, length in 16th
notes, pitch. _2 is a rest, ー holds the previous vowel. Every bar adds up to
16. Particles are spelled as sung (は→わ, を→お, へ→え) and っ is a rest.
Everything is written in D major; a section's `transpose` shifts it.
"""

TITLE = "まだね"
BPM = 130

# --- chords (one per bar; two names split the bar in half) -----------------
HOOK_CHORDS = ["G", "A", "F#m", "Bm", "G", "A", "D", "A"]
A_CHORDS = ["D", "A/C#", "Bm", "F#m/A", "G", "D/F#", "Em7", "A"]
B_CHORDS = ["Gmaj7", "A", "F#m7", "Bm7", "Em7", "F#m7", "Gmaj7", "A7sus4 A7"]
CHORUS_CHORDS = ["G", "A", "F#m", "Bm", "G", "A", "F#7", "Bm",
                 "G", "A", "F#m", "Bm", "Em7", "A7", "D", "D"]
BRIDGE_CHORDS = ["Bm", "G", "D/F#", "A", "Em7", "F#m7", "Gmaj7", "A7sus4 A7"]
OCHI_CHORDS = ["G", "A", "F#m", "Bm", "G", "A", "Em7", "A Bb7"]
OUTRO_CHORDS = ["G", "A", "F#m", "Bm", "G", "A", "D", "D"]

REST = "_16"

# --- 1番 --------------------------------------------------------------------
VERSE_1A = [
    "ふ1E4 る1F#4 い2E4 い1D4 や1F#4 ほ2E4 ん1D4 ご1D4 し2E4 に2F#4 _2",   # 古いイヤホン越しに
    "は1E4 じ1E4 め1F#4 て1E4 き2C#4 い1D4 た1E4 そ2E4 の1F#4 こ1E4 え4C#4",  # 初めて聴いたその声
    "_1 い1D4 ま1D4 で1F#4 も2F#4 む1E4 ね1D4 の2B3 お1D4 く1E4 で2F#4 _2",  # 今でも胸の奥で
    "ち1C#4 い1D4 さ2E4 く1F#4 ふ1E4 る2D4 え1C#4 て1D4 い2E4 る4E4",         # 小さく震えている
    "が1D4 め1D4 ん2E4 の1F#4 む1G4 こ2A4 ー1A4 が1B4 わ2A4 の2G4 _2",       # 画面の向こう側の
    "ま1A4 だ1A4 み2B4 ぬ2A4 け2F#4 し2E4 き2D4 に4E4",                       # まだ見ぬ景色に
    "_1 と1E4 ど1F#4 か2G4 な1F#4 い1E4 と2D4 し1E4 _1 て1F#4 も2G4 _2",     # 届かないと知っても
    "あ1F#4 こ1G4 が2A4 れ1B4 て1A4 い2G4 た2F#4 ん2E4 だ4E4",                # 憧れていたんだ
]
VERSE_1B = [
    "_2 は1B4 じ1B4 ま2A4 り2B4 わ2D5 け1C#5 ー1C#5 や2B4 く1A4 で1B4",       # 始まりは「契約」で
    "ちょ2A4 _1 と1A4 て2B4 れ1A4 く1G4 さ2F#4 い1E4 け1F#4 ど4E4",          # ちょっと照れくさいけど
    "い2A4 ま2A4 め1B4 の1C#5 ま1B4 え1A4 で4F#4 _2 あ1A4 の1B4",             # 今 目の前で / あの
    "ひ2C#5 の1B4 ゆ1C#5 め2D5 が2C#5 さ2D5 い1C#5 て1B4 る4A4",              # 日の夢が咲いてる
    "は1B4 れ1B4 の1B4 ひ1A4 も2B4 _2 あ1C#5 め1C#5 の1C#5 ひ1B4 も2C#5 _2",  # 晴れの日も 雨の日も
    "あ1D5 な1D5 た2C#5 わ2C#5 そ2B4 こ1A4 に1B4 い2C#5 て4C#5",              # あなたはそこにいて
    "へ1D5 た1C#5 な2B4 わ1B4 た1C#5 し2D5 の1D5 う1C#5 た2B4 お2A4 _2",     # 下手な私の歌を
    "う2A4 た1B4 _1 て2C#5 く2D5 れ2C#5 た2B4 ね4C#5",                        # 歌ってくれたね
]
CHORUS_1 = [
    "と2A4 き2B4 の2C#5 さ4D5 く2C#5 ら4B4",                                  # 時の桜
    "ま2C#5 い2B4 ち2A4 る2F#4 な2A4 か2B4 で4A4",                            # 舞い散る中で
    "い1A4 え1A4 な2B4 か1C#5 _1 た2C#5 お2B4 も2A4 い2F#4 お2A4",           # 言えなかった想いを
    "あ2B4 な2C#5 た2D5 が2C#5 う2B4 た2A4 う4B4",                            # あなたが歌う
    "い1A4 き1B4 づ1C#5 か1D5 い2D5 も2C#5 こ2B4 ど2C#5 ー2C#5 も2B4",       # 息遣いも鼓動も
    "か2C#5 ん2C#5 じ2D5 る2C#5 の2B4 に6A4",                                 # 感じるのに
    "ふ1A#4 れ1A#4 ら1B4 れ1C#5 な2C#5 い2B4 きょ2D5 り2C#5 が2B4 む1A#4 ね1B4",  # 触れられない距離が胸
    "お2D5 し2C#5 め2B4 つ2A4 け2C#5 る6B4",                                  # を締め付ける
    "さ2B4 よ2C#5 な4D5 ら4E5 の4D5",                                         # 「さよなら」の
    "お2C#5 も2D5 さ2C#5 よ2B4 り6A4 _2",                                     # 重さより
    "ま2A4 た2C#5 ね4E5 の2D5 ほ2C#5 ー2C#5 が2B4",                           # 「またね」のほうが
    "す4D5 き8B4 _4",                                                         # 好き
    "な2B4 ん2B4 ど4D5 は2C#5 る2B4 が4A4",                                   # 何度 春が
    "め2G4 ぐ1A4 _1 て2B4 も6C#5 _4",                                         # 巡っても
    "こ2D5 こ2C#5 で4B4 あ2A4 お2G4 ー4F#4",                                  # ここで会おう
    "ね4E4 ー8D4 _4",                                                         # ね
]

# --- 2番 --------------------------------------------------------------------
VERSE_2A = [
    "す1E4 こ1F#4 し2E4 ず1D4 つ1F#4 せ2E4 が1D4 の1D4 び2E4 て2F#4 _2",     # 少しずつ背が伸びて
    "み1E4 え1E4 る1F#4 け1E4 し2C#4 き1D4 も1E4 か2E4 わ1F#4 _1 た4C#4",    # 見える景色も変わった
    "_1 あ1D4 な1D4 た1F#4 だ2F#4 け1E4 か1D4 わ2B3 ら1D4 ず1E4 に2F#4 _2",  # あなただけ変わらずに
    "あ1C#4 の1D4 ひ2E4 の1F#4 こ1E4 え2D4 の1C#4 ま1D4 ま2E4 で4E4",         # あの日の声のままで
    "あ1D4 る1D4 き2E4 だ1F#4 す1G4 た2A4 び1A4 い1B4 つ2A4 か2G4 _2",       # 歩き出すたび いつか
    "お1A4 い1A4 て2B4 い2A4 き2F#4 そ2E4 ー2D4 で4E4",                       # 置いていきそうで
    "_1 こ1E4 わ1F#4 く2G4 て1F#4 も1E4 き2D4 め1E4 た1E4 ん1F#4 だ2G4 _2",  # 怖くても決めたんだ
    "あ1F#4 な1G4 た2A4 と1B4 あ1A4 る2G4 く1F#4 _1 て6E4",                   # あなたと歩くって
]
VERSE_2B = [
    "_2 い1B4 く1B4 つ2A4 も2B4 の2D5 よ1C#5 る1C#5 お2B4 こ1A4 え1B4",       # いくつもの夜を越え
    "か2A4 き1A4 か1A4 け2B4 の1A4 ま1G4 ま2F#4 の1E4 う1F#4 た4E4",          # 書きかけのままの歌
    "ふ2A4 る2A4 い1B4 ふぁ1C#5 い1B4 る1A4 わ4F#4 _2 た1A4 い1B4",           # 古いファイルは / タイ
    "む2C#5 か1B4 ぷ1C#5 せ2D5 る2C#5 み2D5 た1C#5 い1B4 で4A4",              # ムカプセルみたいで
    "ひ1B4 ら1B4 く1B4 た1A4 び2B4 _2 あ1C#5 の1C#5 は1C#5 る1B4 が2C#5 _2",  # 開くたび あの春が
    "ふ1D5 わ1D5 り2C#5 と2C#5 め2B4 お1A4 さ1B4 ま2C#5 す4C#5",              # ふわりと目を覚ます
    "こ1D5 と1C#5 ば2B4 に1B4 で1C#5 き2D5 な1D5 い1C#5 こ2B4 と2A4 _2",     # 言葉にできないこと
    "あ2A4 な1B4 た1B4 に2C#5 た2D5 く2C#5 す2B4 よ4C#5",                     # あなたに託すよ
]
CHORUS_2 = CHORUS_1[:4] + [
    "お1A4 な1B4 じ1C#5 そ1D5 ら2D5 み2C#5 あ1B4 げ1B4 る2C#5 ひ2C#5 お2B4",  # 同じ空 見上げる日を
    "し2C#5 ん2C#5 じ2D5 て2C#5 る8A4",                                       # 信じてる
    "ど1A#4 れ1A#4 だ1B4 け1C#5 じ2C#5 か1B4 ん1B4 が2D5 か1C#5 か1B4 _1 て1A#4 も2B4",  # どれだけ時間がかかっても
    "き4D5 _2 と10B4",                                                        # きっと
] + CHORUS_1[8:12] + [
    "あ2B4 し2B4 た2D5 も2D5 こ2C#5 こ2B4 で4A4",                             # 明日もここで
    "つ2G4 づ2A4 き2B4 お6C#5 _4",                                            # 続きを
    "う2D5 た1C#5 _1 て4B4 い2A4 こ2G4 ー4F#4",                               # 歌っていこう
    "ー4E4 ー8D4 _4",
]

# --- Cメロ / 落ちサビ / ラスサビ / Outro ------------------------------------
BRIDGE = [
    "_2 ど2F#4 ー2F#4 し1E4 て1F#4 こ2B4 ん2A4 な2F#4 に2E4",                  # どうしてこんなに
    "せ2G4 つ2F#4 な2E4 い2D4 ん2E4 だ2F#4 ろ2E4 ー2D4",                       # 切ないんだろう
    "あ1D4 な1E4 た1F#4 と1A4 す2B4 ご1A4 し1F#4 た2A4 ひ2B4 び2C#5 が2D5",   # あなたと過ごした日々が
    "こ2C#5 た2B4 え2A4 な2B4 の2C#5 に6A4",                                  # 答えなのに
    "_2 こ1B4 の1B4 お2B4 も2A4 い2B4 も2C#5 い1D5 つ1C#5 か2B4",             # この想いもいつか
    "か2C#5 ぜ2D5 に2E5 の1D5 _1 て8C#5",                                      # 風に乗って
    "が1D5 め1D5 ん2C#5 の2B4 む2A4 こ2B4 ー2D5 え4C#5",                       # 画面の向こうへ
    "と2B4 ど2C#5 く2D5 か2E5 な8E5",                                          # 届くかな
]
OCHI = CHORUS_1[:2] + [
    "い1A4 え1A4 な2B4 か1C#5 _1 た2C#5 お2B4 も2A4 い2F#4 が2A4",           # 言えなかった想いが
    "あ2B4 ざ2C#5 や2D5 か2C#5 に2B4 さ2A4 く4B4",                            # 鮮やかに咲く
    "あ2A4 な2B4 た2C#5 の2D5 こ2D5 え2C#5 が4B4",                            # あなたの声が
    "き2C#5 こ2C#5 え2D5 る2C#5 か2B4 ぎ2A4 り4A4",                           # 聴こえる限り
    "も2A4 ど2B4 れ2C#5 な2D5 い2D5 み2C#5 ち2B4 も2A4",                      # 戻れない道も
    "あ2A4 る2B4 い2C#5 て2D5 い2D5 け2C5 る4Bb4",                            # 歩いていける
]
CHORUS_LAST = CHORUS_1[:5] + [
    "か2C#5 ん2C#5 じ2D5 る2C#5 か2B4 ら6A4",                                 # 感じるから
    "ふ1A#4 れ1A#4 ら1B4 れ1C#5 な2C#5 い2B4 きょ2D5 り2C#5 さ2B4 え1A#4 も1B4",  # 触れられない距離さえも
    "い2D5 と2C#5 し2B4 く2C#5 て8B4",                                        # 愛しくて
] + CHORUS_1[8:]
OUTRO_VOCAL = [REST] * 4 + [
    "さ2F#4 よ2G4 な4A4 ら4B4 わ4A4",                                         # さよならは
    "_8 ま4F#4 だ4E4",                                                        # まだ
    "ね12D4 _4",                                                              # ね
    REST,
]

# Instrumental hook for the intro/interlude/outro (lyrics ignored).
HOOK = CHORUS_1[:4] + CHORUS_1[8:10] + [REST, REST]

# --- song form --------------------------------------------------------------
# feel: how the demo arrangement plays the section.
SECTIONS = [
    dict(name="Intro", chords=HOOK_CHORDS, hook=HOOK, feel="intro"),
    dict(name="1A", chords=A_CHORDS, vocal=VERSE_1A, feel="verse"),
    dict(name="1B", chords=B_CHORDS, vocal=VERSE_1B, feel="pre"),
    dict(name="1サビ", chords=CHORUS_CHORDS, vocal=CHORUS_1, feel="chorus"),
    dict(name="間奏", chords=HOOK_CHORDS, hook=HOOK, feel="interlude"),
    dict(name="2A", chords=A_CHORDS, vocal=VERSE_2A, feel="verse2"),
    dict(name="2B", chords=B_CHORDS, vocal=VERSE_2B, feel="pre"),
    dict(name="2サビ", chords=CHORUS_CHORDS, vocal=CHORUS_2, feel="chorus"),
    dict(name="Cメロ", chords=BRIDGE_CHORDS, vocal=BRIDGE, feel="bridge"),
    dict(name="落ちサビ", chords=OCHI_CHORDS, vocal=OCHI, feel="ochi"),
    dict(name="ラスサビ", chords=CHORUS_CHORDS, vocal=CHORUS_LAST, feel="chorus", transpose=1),
    dict(name="Outro", chords=OUTRO_CHORDS, vocal=OUTRO_VOCAL, hook=CHORUS_1[:4] + [REST] * 4,
         feel="outro", transpose=1),
]
