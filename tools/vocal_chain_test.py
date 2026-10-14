"""Render one vocal excerpt through several FX chains in REAPER and compare them.

Each chain is Lua using the helpers of tools/arrange.py; the report gives the
output level against the input and how the gain reduction is spread (100 ms
blocks), so a chain can be calibrated before it goes into a whole build.

    python -I tools/vocal_chain_test.py <vocal.wav> <work dir> [start_s length_s]
"""
import sys
from pathlib import Path

import numpy as np
import soundfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arrange
import reaper_run

CHAINS = {
    "v12": 'eq(tr, 120, 6000, 1); comp(tr, -20, 3, 8, 150, 2)',
    "v13": '''eq_bands(tr, 110, {{3, 300, -2.5}, {6, 4200, 2.5}, {9, 11000, 3}})
      js(tr, "sstillwell/1175", {{0, -24}, {1, 4}, {2, 3}, {3, 400}, {4, 120}})
      js(tr, "sstillwell/fairlychildish", {{0, -20}, {1, 70}, {2, 2}})
      js(tr, "Liteon/deesser", {{3, 6800}, {4, 1.5}, {5, -32}, {6, 4}})
      js(tr, "loser/Exciter", {{0, 7000}, {2, 22}, {3, -14}})
      js(tr, "loser/Saturation", {{0, 12}})''',
    "fix": '''eq_bands(tr, 110, {{3, 300, -2.5}, {6, 4200, 2.5}, {9, 11000, 3}})
      local c = js(tr, "sstillwell/1175", {{0, -10}, {2, 2}, {3, 400}, {4, 120}})
      say("1175 ratio: " .. set_exact(tr, c, 1, "4"))
      comp(tr, -16, 2.5, 15, 250, 2)
      js(tr, "Liteon/deesser", {{3, 6800}, {4, 1.5}, {5, -32}, {6, 4}})
      js(tr, "loser/Exciter", {{0, 7000}, {2, 22}, {3, -14}})
      js(tr, "loser/Saturation", {{0, 12}})''',
}

TEST = r'''
local SRC, START, LEN = @SRC@, @START@, @LEN@
local function set_exact(tr, fx, idx, text)
  for i = 0, 1000 do
    local v = i / 1000
    local _, s = reaper.TrackFX_FormatParamValueNormalized(tr, fx, idx, v, "")
    if s == text then reaper.TrackFX_SetParamNormalized(tr, fx, idx, v); return s end
  end
  return "NOT FOUND"
end
local chains = @CHAINS@
for _, ch in ipairs(chains) do
  local tr = add_track(ch[1])
  add_audio(tr, SRC, 0, START, LEN)
  ch[2](tr)
end
for i = 0, reaper.CountTracks(0) - 1 do
  local tr = reaper.GetTrack(0, i)
  local _, name = reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", "", false)
  reaper.SetMediaTrackInfo_Value(tr, "I_SOLO", 2)
  reaper.GetSetProjectInfo_String(0, "RENDER_FILE", WORK, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", "chain_" .. name, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", "evaw", true)
  reaper.GetSetProjectInfo(0, "RENDER_SRATE", 44100, true)
  reaper.GetSetProjectInfo(0, "RENDER_CHANNELS", 2, true)
  reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_STARTPOS", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_ENDPOS", LEN, true)
  reaper.Main_OnCommand(42230, 0)
  reaper.SetMediaTrackInfo_Value(tr, "I_SOLO", 0)
  say("rendered " .. name)
end
log:close()
reaper.Main_SaveProject(0, false)              -- saved, so quitting asks nothing
reaper.Main_OnCommand(40004, 0)
'''


def helpers():
    """The helper functions of the build script (everything before the song is laid out)."""
    lua = arrange.LUA
    head = lua[:lua.index("reaper.SetCurrentBPM")]
    return head.replace("@TRACKS@", "").replace("@MIX@", "{}").replace("@TOTAL_QN@", "0")


def blocks(x, sr):
    m = x.mean(axis=1)
    blk = sr // 10
    n = len(m) // blk
    return np.sqrt((m[:n * blk].reshape(n, blk) ** 2).mean(axis=1) + 1e-20)


def main():
    src, work = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    start, length = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (55.0, 65.0)
    work.mkdir(parents=True, exist_ok=True)
    q = lambda p: "[[" + str(p) + "]]"
    chains = "{" + ",".join(f'{{"{k}", function(tr) {v} end}}' for k, v in CHAINS.items()) + "}"
    lua = (helpers().replace("@WORK@", q(work)).replace("@OUT@", q(work))
           + TEST.replace("@SRC@", q(src)).replace("@START@", str(start)).replace("@LEN@", str(length))
           .replace("@CHAINS@", chains))
    script = work / "chain_test.lua"
    script.write_text(lua, encoding="utf-8")
    ok, secs, boot = reaper_run.run(script, work / "chain_test.rpp", timeout=900)
    print(f"REAPER {'finished' if ok else 'TIMED OUT'} in {secs:.0f}s")
    log = work / "build_log.txt"
    if log.exists():
        print(log.read_text(encoding="utf-8"))
    x, sr = soundfile.read(str(src), always_2d=True)
    dry = blocks(x[int(start * sr):int((start + length) * sr)], sr)
    on = dry > 10 ** (-45 / 20)
    db = lambda v: 20 * np.log10(v)
    print(f"{'input':>6}: active RMS {db(np.sqrt((dry[on] ** 2).mean())):6.1f} dB")
    for name in CHAINS:
        p = work / f"chain_{name}.wav"
        if not p.exists():
            print(f"{name:>6}: missing")
            continue
        y, _ = soundfile.read(str(p), always_2d=True)
        wet = blocks(y, sr)
        n = min(len(wet), len(dry))
        d = db(wet[:n][on[:n]]) - db(dry[:n][on[:n]])
        print(f"{name:>6}: active RMS {db(np.sqrt((wet[:n][on[:n]] ** 2).mean())):6.1f} dB, peak {db(np.abs(y).max()):6.1f}, "
              f"gain p10/p50/p90 {np.percentile(d, 10):+5.1f} {np.percentile(d, 50):+5.1f} {np.percentile(d, 90):+5.1f} dB")


if __name__ == "__main__":
    main()
