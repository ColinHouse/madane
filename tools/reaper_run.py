"""Run a ReaScript in a fresh REAPER instance and wait for it to finish.

The script is handed a project file that already exists, so it can save in
place and quit without REAPER asking where to save. It is loaded through a
small bootstrap that logs syntax or runtime errors and quits, instead of
leaving an error dialog open.
"""
import subprocess
import sys
import time
from pathlib import Path

REAPER = Path(r"C:\Program Files\REAPER (x64)\reaper.exe")
EMPTY_PROJECT = '<REAPER_PROJECT 0.1 "7.82/win64" 0\n  TEMPO 80 4 4\n>\n'
BOOTSTRAP = r'''
local log = io.open([[{log}]], "w")
local function finish(msg)
  log:write(msg .. "\n"); log:close()
  reaper.Main_SaveProject(0, false)
  reaper.Main_OnCommand(40004, 0)
end
local chunk, err = loadfile([[{script}]])
if not chunk then return finish("SYNTAX ERROR: " .. tostring(err)) end
log:write("loaded\n"); log:flush()
local ok, e = xpcall(chunk, debug.traceback)
if not ok then return finish("RUNTIME ERROR: " .. tostring(e)) end
log:write("ok\n"); log:close()
'''


def run(script, project, timeout=600):
    """Returns (finished, seconds, bootstrap log text)."""
    script, project = Path(script), Path(project)
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_text(EMPTY_PROJECT, encoding="utf-8")
    log = script.with_suffix(".bootstrap.txt")
    log.unlink(missing_ok=True)
    boot = script.with_name(script.stem + "_boot.lua")
    boot.write_text(BOOTSTRAP.format(log=log, script=script), encoding="utf-8")
    proc = subprocess.Popen([str(REAPER), "-newinst", "-nosplash", "-ignoreerrors",
                             str(project), str(boot)])
    start = time.time()
    try:
        proc.wait(timeout=timeout)
        finished = True
    except subprocess.TimeoutExpired:
        proc.kill()
        finished = False
    text = log.read_text(encoding="utf-8") if log.exists() else "(no bootstrap log)"
    return finished, time.time() - start, text


if __name__ == "__main__":
    ok, secs, text = run(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 600)
    print(f"{'finished' if ok else 'TIMED OUT (killed)'} after {secs:.0f}s\n{text}")
