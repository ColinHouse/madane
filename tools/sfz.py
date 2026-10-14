"""Tiny SFZ reader: enough for the FreePats kits (groups, regions, key/vel, rand)."""
import re
import sys
from pathlib import Path

_OPCODE = re.compile(r"(\w+)=(.*?)(?=\s+\w+=|$)")


def parse(path):
    """-> list of regions, each a dict of opcodes (group opcodes inherited) + 'comment'."""
    path = Path(path)
    glob, group, regions, comment = {}, {}, [], ""
    current = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("//"):
            text = line.lstrip("/ ").strip()
            if text and not text.startswith("+"):
                comment = text
            continue
        for header in re.findall(r"<(\w+)>", line):
            if header == "global":
                current = glob = {}
            elif header == "group":
                current = group = dict(glob, comment=comment)
            elif header == "region":
                current = dict(group)
                regions.append(current)
        line = re.sub(r"<\w+>", "", line).strip()
        if line and current is not None:
            for key, value in _OPCODE.findall(line):
                current[key] = value.strip()
    for r in regions:
        if "sample" in r:
            r["path"] = (path.parent / r["sample"].replace("\\", "/")).resolve()
        if "key" in r:
            r.setdefault("lokey", r["key"])
            r.setdefault("hikey", r["key"])
            r.setdefault("pitch_keycenter", r["key"])
    return regions


if __name__ == "__main__":
    regs = parse(sys.argv[1])
    groups = {}
    for r in regs:
        k = (r.get("comment", ""), r.get("lokey"), r.get("hikey"))
        groups.setdefault(k, []).append(r)
    for (comment, lo, hi), rs in groups.items():
        vels = sorted({(int(r.get("lovel", 0)), int(r.get("hivel", 127))) for r in rs})
        print(f"{comment:28s} key {lo}-{hi}  {len(rs):3d} regions  {len(vels)} vel layers "
              f"{vels[0]}..{vels[-1]}  e.g. {Path(rs[0]['sample']).name}")
