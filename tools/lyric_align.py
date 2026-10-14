"""Which sung syllable each character of a lyric line starts on.

The melody gives one syllable per note (particles as sung: わ お え, っ as a
rest, ー as a held vowel); the lyric line is written with kanji. A small
dynamic program matches them: kana match their own syllable, small kana join
the one before, っ takes none, a kanji takes as many syllables as one of its
readings, and a vowel the singer folds into the note before (the う of ろう)
may take none.
"""
READINGS = {
    "午": ["ご"], "前": ["ぜん"], "二": ["に"], "時": ["じ", "とき"], "青": ["あお"], "光": ["ひかり"],
    "初": ["はじ"], "鳴": ["な"], "音": ["おと", "おん"], "頼": ["たよ"], "揺": ["ゆ"], "声": ["こえ"],
    "今": ["いま"], "覚": ["おぼ"], "符": ["ぷ"], "並": ["なら"], "息": ["いき"], "継": ["つ"], "場": ["ば"],
    "所": ["しょ"], "私": ["わたし"], "描": ["か"], "桜": ["さくら"], "舞": ["ま"], "落": ["お"], "言": ["い"],
    "想": ["おも"], "歌": ["うた"], "重": ["おも"], "手": ["て"], "振": ["ふ"], "忙": ["いそが"], "紛": ["まぎ"],
    "日": ["ひ", "び"], "々": ["び"], "開": ["ひら"], "中": ["なか"], "同": ["おな"], "待": ["ま"],
    "大": ["お"], "人": ["とな"], "夜": ["よる"], "短": ["みじか"], "変": ["か"], "来": ["らい", "こ", "く"],
    "年": ["ねん"], "会": ["あ"], "春": ["はる"], "誰": ["だれ"], "部": ["へ"], "屋": ["や"], "残": ["のこ"],
    "何": ["なん"], "度": ["ど"], "巡": ["めぐ"], "回": ["まわ"], "残": ["のこ"],
}
SMALL = set("ゃゅょぁぃぅぇぉゎャュョァィゥェォ")
SKIP = set("　 「」﹁﹂、。")
SAME = {("は", "わ"), ("を", "お"), ("へ", "え"), ("う", "ー"), ("お", "ー"), ("い", "ー"), ("ー", "ー")}


def _mora_split(reading):
    """'ばしょ' -> ['ば', 'しょ'] (small kana stay with their mora)."""
    out = []
    for ch in reading:
        if ch in SMALL and out:
            out[-1] += ch
        else:
            out.append(ch)
    return out


def _kana_cost(ch, syl):
    if ch == syl[0] or (ch, syl) in SAME or (ch, syl[0]) in SAME:
        return 0.0
    return 2.0


def align(text, syllables):
    """Index of the first syllable for each character of `text` (None for a character with none)."""
    chars = list(text)
    n, m = len(chars), len(syllables)
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for i in range(n):
        ch = chars[i]
        for j in range(m + 1):
            c0 = cost[i][j]
            if c0 == INF:
                continue

            def relax(take, c):
                if j + take <= m and c0 + c < cost[i + 1][j + take]:
                    cost[i + 1][j + take] = c0 + c
                    back[i + 1][j + take] = (j, take)
            if ch in SKIP or ch in SMALL or ch == "っ" or ch == "ッ":
                relax(0, 0.0)
            elif ch in READINGS or not ("ぁ" <= ch <= "ヿ"):      # kanji (or anything that is not kana)
                for reading in READINGS.get(ch, []):
                    morae = _mora_split(reading)
                    k = len(morae)
                    if j + k <= m and all(s.startswith(r[0]) or (r, s) in SAME for r, s in zip(morae, syllables[j:j + k])):
                        relax(k, 0.0)
                for k in range(1, 5):
                    relax(k, 1.5 + 0.5 * k)
            else:                                                       # kana
                if j < m:
                    relax(1, _kana_cost(ch, syllables[j]))
                if ch in "あいうえお":
                    relax(0, 1.5)                                       # folded into the note before
    # walk back from the best end (all syllables used)
    starts = [None] * n
    j = m
    for i in range(n, 0, -1):
        if back[i][j] is None:
            break
        pj, take = back[i][j]
        starts[i - 1] = pj if take > 0 else None
        j = pj
    return starts


def char_times(text, syllables, onsets):
    """Onset time for every character: its first syllable's, or a neighbour's when it has none."""
    starts = align(text, syllables)
    times = [onsets[s] if s is not None and s < len(onsets) else None for s in starts]
    for i, ch in enumerate(text):                  # opening marks lead their word, the rest trail
        if times[i] is None and ch in "「﹁":
            times[i] = next((t for t in times[i + 1:] if t is not None), onsets[0])
    last = onsets[0]
    for i in range(len(times)):
        if times[i] is None:
            times[i] = last
        last = times[i]
    return times


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    sample = "午前二時の　青い光"
    syl = ["ご", "ぜ", "ん", "に", "じ", "の", "あ", "お", "い", "ひ", "か", "り"]
    print([(c, syl[s] if s is not None else "-") for c, s in zip(sample, align(sample, syl))])
