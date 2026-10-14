# まだね

> 当我把 VOCALOID 和 REAPER 交给 Claude

一首写给初音ミク的抒情曲（80 BPM，4:35）。Astrology 写了一小段日文歌词作为引子，然后把 VOCALOID 和 REAPER 交给了 Claude Opus 5.5。旋律、编曲、混音和故事 PV 都由 Claude 在一次对话里完成：它写 VOCALOID 工程文件和 REAPER 脚本，用 Python 合成电子音色，逐帧渲染 PV。

Claude 听不见声音。每一版都靠两样东西判断：测量（响度、频谱、立体声宽度、人声和伴奏的比例、每个音符的音高），以及 Astrology 的耳朵。导出人声那一步也是 Astrology 在 VOCALOID 里替它按的。

## Staff

- 原词・企划：Astrology
- 歌词改写・作曲・编曲・混音・PV：Claude（Anthropic）
- 演唱：初音ミク V4X（VOCALOID5）

![PV](docs/pv.jpg)

## 下载

[Releases](https://github.com/ColinHouse/madane/releases/latest)：完整版和伴奏 mp3、1080p PV、VOCALOID5 工程（.vpr）。

歌词（日中对照）在 [lyrics/madane_lyrics.md](lyrics/madane_lyrics.md)。

## 怎么做的

| 环节 | 文件 |
|---|---|
| 旋律和歌词（音节 + 时值 + 音高的音符串） | `tools/madane.py` |
| 生成 VOCALOID5 工程：音符、换气、力度和句尾 | `tools/build.py`、`tools/vpr.py`、`tools/expression.py` |
| 和声与「う」铺底 | `tools/harmony.py` |
| 在 VOCALOID5 里导出人声 WAV | 手动 |
| 编曲：钢琴、弦乐、竖琴、乐队、电子层 | `tools/arrangement.py`、`tools/orchestra.py`、`tools/electro.py` |
| 用 Lua 脚本搭 REAPER 工程（RS5K 采样器、JS 效果器）并渲染 | `tools/arrange.py`、`tools/reaper_run.py` |
| 合成器音色（supersaw、拨弦、超低音、电子鼓、上升音效） | `tools/synths.py` |
| 母带最后一步：真峰值控制 | `tools/truepeak.py` |
| 检查：响度、频谱、人声比例、音高误差、效果器链增益 | `tools/loudness.py`、`tools/analyze.py`、`tools/vocal_check.py`、`tools/vocal_chain_test.py` |
| 故事 PV：光照、剪影、逐音节字幕 | `tools/pv_story.py`、`tools/figures.py`、`tools/sdf.py`、`tools/lyric_align.py` |

```
python -I tools/build.py v4         # out/madane_v4.vpr → 在 VOCALOID5 里导出 out/miku_v4.wav
python -I tools/arrange.py v15      # out/madane_reaper_v15.wav（需要 REAPER 和采样库）
python -I tools/pv_story.py out/madane_reaper_v15.wav out/madane_pv_story.mp4
```

需要 Windows、Python 3.11（numpy、scipy、soundfile、numba、Pillow）、ffmpeg、REAPER 7、VOCALOID5 和初音ミク V4X。采样库用 `tools/download_library.ps1` 和 `tools/download_vsco_more.py` 下载到 `library/`。

`tools/` 里也留着中间版本（`madane_v1.py`～`madane_v3.py`、`pv_lyric.py`、`pv_hud.py`），能看出每一轮改了什么。

## 音源与致谢

- 钢琴：Salamander Grand Piano — Alexander Holm（CC BY 3.0），经 [FreePats](https://freepats.zenvoid.org/) 获取
- 鼓：[MuldjordKit](https://github.com/freepats/muldjordkit) — Lars Muldjord（CC BY 4.0）
- 管弦乐：[VSCO-2 Community Edition](https://github.com/sgossner/VSCO-2-CE)（CC0）
- 吉他、贝斯：[FreePats](https://freepats.zenvoid.org/)（CC0），贝斯为 [FingerBassYR](https://github.com/freepats/electric-bass-YR)
- 合成器音色：由 `tools/synths.py` 生成

初音ミク © Crypton Future Media, INC. www.piapro.net
VOCALOID is a trademark of Yamaha Corporation.

## 许可

`tools/` 里的代码使用 MIT 许可（见 [LICENSE](LICENSE)）。歌曲本身（歌词、音频、PV）不在 MIT 范围内，保留所有权利。

---

**English.** *まだね* ("not yet") is a VOCALOID ballad written to Hatsune Miku. Astrology wrote a short Japanese lyric as the seed and handed VOCALOID and REAPER to Claude Opus 5.5, which wrote the melody, arrangement, mix and story PV in a single conversation, generating VOCALOID5 project files, REAPER Lua scripts, Python-synthesised instruments and a frame-by-frame PV renderer. Claude cannot hear audio: every version was judged by measurements and by Astrology's ears.
