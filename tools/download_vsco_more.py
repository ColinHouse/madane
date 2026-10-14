"""Download the extra VSCO-2 CE instruments approved by the user (2026-10-14).

Files go into library/vsco2_more/<repo path>; the repo tree listing is fetched
from the GitHub API.

    python -I tools/download_vsco_more.py
"""
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "library"
DEST = LIB / "vsco2_more"
LOG = LIB / "download_log.txt"
TREE = "https://api.github.com/repos/sgossner/VSCO-2-CE/git/trees/master?recursive=1"
RAW = "https://raw.githubusercontent.com/sgossner/VSCO-2-CE/master/"
WANT = re.compile(r"^(Strings/Harp/|Percussion/Glock/|Percussion/BellTree_Stroke|Percussion/susCymb1-cresc-"
                  r"|Percussion/Timpani/|Strings/Violin Section/Spic/|Strings/Viola Section/spic/"
                  r"|Strings/Cello Section/spic/|Strings/Violin Section/Trem/|Strings/Solo Violin/Arco Vib/"
                  r"|Brass/F Horn/sus/|Woodwinds/Flute/susvib/)", re.I)


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "curl"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def fetch(entry):
    out = DEST / entry["path"]
    if out.exists() and out.stat().st_size == entry.get("size", -1):
        return True
    out.parent.mkdir(parents=True, exist_ok=True)
    url = RAW + "/".join(urllib.parse.quote(p) for p in entry["path"].split("/"))
    for attempt in range(4):
        try:
            out.write_bytes(get(url))
            return True
        except Exception as e:                      # retry transient network errors
            err = e
            time.sleep(2 + attempt * 3)
    log(f"FAILED {entry['path']}: {err}")
    return False


def main():
    tree = json.loads(get(TREE))
    files = [e for e in tree["tree"] if e["type"] == "blob" and WANT.match(e["path"])
             and e["path"].lower().endswith((".wav", ".flac"))]
    total = sum(e.get("size", 0) for e in files)
    log(f"vsco2_more: {len(files)} files, {total / 1e6:.1f} MB")
    with ThreadPoolExecutor(6) as pool:
        ok = sum(pool.map(fetch, files))
    log(f"vsco2_more done: {ok}/{len(files)} ok")
    print(f"{ok}/{len(files)} files")


if __name__ == "__main__":
    main()
