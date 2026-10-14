"""Extract a tar archive with the 'data' safety filter (no absolute paths or ../).

    python -I tools/extract_tar.py <archive> <destination>
"""
import sys
import tarfile
from pathlib import Path

archive, dest = Path(sys.argv[1]), Path(sys.argv[2])
dest.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive) as tar:
    tar.extractall(dest, filter="data")
files = [p for p in dest.rglob("*") if p.is_file()]
print(f"{len(files)} files, {sum(p.stat().st_size for p in files) / 2**20:.0f} MB in {dest}")
