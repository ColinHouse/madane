"""Write VOCALOID5 project files (.vpr).

A .vpr is a zip archive holding Project/sequence.json. Positions and durations
are in ticks (480 per quarter note); tempo values are BPM * 100.
"""
import json
import zipfile

TPQ = 480
BAR = TPQ * 4

# Miku V4X voicebanks installed under C:\Program Files (x86)\VoiceDB\MikuV4x\<compID>
VOICES = {
    "original": ("BCNFCY43LB2LZCD4", "MIKU_V4X_Original_EVEC"),
    "soft": ("BFPL93T7GE3RWFC9", "MIKU_V4X_Soft_EVEC"),
    "solid": ("BKGHF6Y5PHTN4KD6", "MIKU_V4X_Solid_EVEC"),
    "sweet": ("BDGE8ZB2FCTKTDBA", "MIKU_V4X_Sweet"),
    "dark": ("BHNME578NG2S3HD8", "MIKU_V4X_Dark"),
}
LANG_JAPANESE = 0

# Kana -> VOCALOID Japanese phonemes (X-SAMPA style used by JPN voicebanks).
_BASE = {
    "あ": "a", "い": "i", "う": "M", "え": "e", "お": "o",
    "か": "k a", "き": "k' i", "く": "k M", "け": "k e", "こ": "k o",
    "が": "g a", "ぎ": "g' i", "ぐ": "g M", "げ": "g e", "ご": "g o",
    "さ": "s a", "し": "S i", "す": "s M", "せ": "s e", "そ": "s o",
    "ざ": "dz a", "じ": "dZ i", "ず": "dz M", "ぜ": "dz e", "ぞ": "dz o",
    "た": "t a", "ち": "tS i", "つ": "ts M", "て": "t e", "と": "t o",
    "だ": "d a", "ぢ": "dZ i", "づ": "dz M", "で": "d e", "ど": "d o",
    "な": "n a", "に": "J i", "ぬ": "n M", "ね": "n e", "の": "n o",
    "は": "h a", "ひ": "C i", "ふ": "p\\ M", "へ": "h e", "ほ": "h o",
    "ば": "b a", "び": "b' i", "ぶ": "b M", "べ": "b e", "ぼ": "b o",
    "ぱ": "p a", "ぴ": "p' i", "ぷ": "p M", "ぺ": "p e", "ぽ": "p o",
    "ま": "m a", "み": "m' i", "む": "m M", "め": "m e", "も": "m o",
    "や": "j a", "ゆ": "j M", "よ": "j o",
    "ら": "4 a", "り": "4' i", "る": "4 M", "れ": "4 e", "ろ": "4 o",
    "わ": "w a", "を": "o", "ん": "N\\",
}
# Palatalized consonants for き/し/ち… followed by a small ゃゅょぇ.
_YOON = {
    "き": "k'", "ぎ": "g'", "し": "S", "じ": "dZ", "ち": "tS", "に": "J",
    "ひ": "C", "び": "b'", "ぴ": "p'", "み": "m'", "り": "4'",
}
_SMALL_VOWEL = {"ゃ": "a", "ゅ": "M", "ょ": "o", "ぇ": "e"}
_SPECIAL = {
    "ふぁ": "p\\ a", "ふぃ": "p\\' i", "ふぇ": "p\\ e", "ふぉ": "p\\ o",
    "てぃ": "t' i", "でぃ": "d' i", "とぅ": "t M", "どぅ": "d M",
    "うぃ": "w i", "うぇ": "w e", "うぉ": "w o", "いぇ": "j e",
    "つぁ": "ts a", "つぃ": "ts i", "つぇ": "ts e", "つぉ": "ts o",
}
_LONG = ("ー", "-")


def to_hiragana(text):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def phoneme(kana, prev_phoneme=None):
    """Phoneme string for one sung syllable; ー repeats the previous vowel."""
    k = to_hiragana(kana)
    if k in _LONG:
        if not prev_phoneme:
            raise ValueError("long vowel mark with no previous syllable")
        return prev_phoneme.split()[-1]
    if k in _SPECIAL:
        return _SPECIAL[k]
    if len(k) == 2 and k[0] in _YOON and k[1] in _SMALL_VOWEL:
        return f"{_YOON[k[0]]} {_SMALL_VOWEL[k[1]]}"
    if k in _BASE:
        return _BASE[k]
    raise ValueError(f"unknown kana: {kana!r}")


_VOWEL_KANA = {"a": "あ", "i": "い", "M": "う", "e": "え", "o": "お"}
_N_BEFORE = (  # ん assimilates to the following consonant
    (("p", "b", "m"), "m"), (("p'", "b'", "m'"), "m'"),
    (("t", "d", "n", "ts", "dz", "4", "4'"), "n"), (("tS", "dZ", "J"), "J"),
    (("k", "g"), "N"), (("k'", "g'"), "N'"),
)


def _n_variant(next_phoneme):
    head = next_phoneme.split()[0] if next_phoneme else ""
    for heads, variant in _N_BEFORE:
        if head in heads:
            return variant
    return "N\\"


def note(lyric, pos, duration, number, phoneme_str, velocity=64, vibrato=(0, 0),
         protected=False):
    return {
        "lyric": lyric,
        "phoneme": phoneme_str,
        "isProtected": protected,
        "pos": pos,
        "duration": duration,
        "number": number,
        "velocity": velocity,
        "exp": {"opening": 127},
        "singingSkill": {"duration": 158, "weight": {"pre": 64, "post": 64}},
        "vibrato": {"type": vibrato[0], "duration": vibrato[1]},
    }


SOKUON_GAP = 120          # a sixteenth at 480 ticks per quarter


def notes_from_events(events, start=0):
    """events: [(lyric, duration, midi_number)]; lyric None is a rest.

    A long-vowel mark becomes the vowel's kana, and ん takes the nasal that
    matches the next syllable; both get locked phonemes.
    """
    out, pos, prev = [], start, None
    for lyric, duration, number in events:
        if lyric is not None:
            ph = phoneme(lyric, prev)
            if lyric in _LONG:
                out.append(note(_VOWEL_KANA[ph], pos, duration, number, ph, protected=True))
            else:
                out.append(note(lyric, pos, duration, number, ph))
            prev = ph
        pos += duration
    for cur, nxt in zip(out, out[1:] + [None]):
        if cur["lyric"] == "ん":
            cur["phoneme"] = _n_variant(nxt["phoneme"] if nxt else None)
            cur["isProtected"] = True
        # っ is written as a sixteenth rest; sung, the stop is only about a 32nd
        if nxt and nxt["pos"] - (cur["pos"] + cur["duration"]) == SOKUON_GAP:
            cur["duration"] += SOKUON_GAP // 2
    return out, pos


def _default_midi_effects():
    # Mirrors the "No Effect" style preset shipped with VOCALOID5 5.0.2.
    return [
        {"id": "SingingSkill", "isBypassed": True, "isFolded": False, "parameters": [
            {"name": "Amount", "value": 5},
            {"name": "Name", "value": "75F04D2B-D8E4-44b8-939B-41CD101E08FD"},
            {"name": "Skill", "value": 5}]},
        {"id": "VoiceColor", "isBypassed": True, "isFolded": False, "parameters": [
            {"name": "Air", "value": 0}, {"name": "Breathiness", "value": 0},
            {"name": "Character", "value": 0}, {"name": "Exciter", "value": 0},
            {"name": "Growl", "value": 0}, {"name": "Mouth", "value": 0},
            {"name": "VoiceBID", "value": ""}, {"name": "VoiceBlend", "value": 0}]},
        {"id": "RobotVoice", "isBypassed": True, "isFolded": False, "parameters": [
            {"name": "Mode", "value": 1}]},
        {"id": "DefaultLyric", "isBypassed": True, "isFolded": False, "parameters": [
            {"name": "CHS", "value": "a"}, {"name": "ENG", "value": "Ooh"},
            {"name": "ESP", "value": "a"}, {"name": "JPN", "value": "あ"},
            {"name": "KOR", "value": "아"}]},
        {"id": "Breath", "isBypassed": True, "isFolded": False, "parameters": [
            {"name": "Exhalation", "value": 5}, {"name": "Mode", "value": 1},
            {"name": "Type", "value": 0}]},
    ]


SKILLS = {  # MIDIEffect\SingingSkill\*.json
    "ballad": "F65E4AE3-A594-4008-ACE4-A93423F8E30C",
    "soulful": "75F04D2B-D8E4-44b8-939B-41CD101E08FD",
}


def midi_effects(skill=None, voice_color=None, breath=None):
    """Part MIDI effects; a dict switches that effect on with those values."""
    fx = _default_midi_effects()
    for effect_id, values in (("SingingSkill", skill), ("VoiceColor", voice_color),
                              ("Breath", breath)):
        if values is None:
            continue
        effect = next(e for e in fx if e["id"] == effect_id)
        effect["isBypassed"] = False
        for p in effect["parameters"]:
            if p["name"] in values:
                p["value"] = values[p["name"]]
    return fx


def _automation(value=0, folded=True, height=40.0):
    return {"isFolded": folded, "height": height, "events": [{"pos": 0, "value": value}]}


def part(pos, duration, notes, voice="original", controllers=None, effects=None):
    comp_id, _ = VOICES[voice]
    p = {
        "pos": pos,
        "duration": duration,
        "styleName": "No Effect",
        "voice": {"compID": comp_id, "langID": LANG_JAPANESE},
        "midiEffects": effects or _default_midi_effects(),
        "notes": notes,
    }
    if controllers:
        p["controllers"] = controllers
    return p


def track(name, parts, color=0):
    return {
        "type": 0,
        "name": name,
        "color": color,
        "busNo": 0,
        "isFolded": False,
        "height": 0.0,
        "volume": _automation(),
        "panpot": _automation(),
        "isMuted": False,
        "isSoloMode": False,
        "parts": parts,
    }


def project(title, bpm, tracks, length_ticks):
    used = {p["voice"]["compID"] for t in tracks for p in t["parts"]}
    voices = [{"compID": cid, "name": name} for cid, name in VOICES.values() if cid in used]
    tempo = int(round(bpm * 100))
    return {
        "version": {"major": 5, "minor": 0, "revision": 0},
        "vender": "Yamaha Corporation",
        "title": title,
        "masterTrack": {
            "samplingRate": 44100,
            "loop": {"isEnabled": False, "begin": 0, "end": length_ticks},
            "tempo": {
                "isFolded": False, "height": 0.0,
                "global": {"isEnabled": False, "value": tempo},
                "events": [{"pos": 0, "value": tempo}],
            },
            "timeSig": {"isFolded": False, "events": [{"bar": 0, "numer": 4, "denom": 4}]},
            "volume": _automation(folded=False, height=0.0),
        },
        "voices": voices,
        "tracks": tracks,
    }


def check(proj):
    """Fail loudly on overlapping notes, or notes/curves outside their part."""
    for t in proj["tracks"]:
        for p in t["parts"]:
            end = 0
            for n in sorted(p["notes"], key=lambda n: n["pos"]):
                if n["pos"] < end:
                    raise ValueError(f"overlapping note at {n['pos']} ({n['lyric']})")
                end = n["pos"] + n["duration"]
            if end > p["duration"]:
                raise ValueError(f"notes run past part end ({end} > {p['duration']})")
            for c in p.get("controllers", []):
                positions = [e["pos"] for e in c["events"]]
                if positions != sorted(set(positions)):
                    raise ValueError(f"{c['name']}: positions not strictly increasing")
                if positions and (positions[0] < 0 or positions[-1] > p["duration"]):
                    raise ValueError(f"{c['name']}: events outside the part")


def write_vpr(path, proj):
    check(proj)
    data = json.dumps(proj, ensure_ascii=False).encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Project/sequence.json", data)
