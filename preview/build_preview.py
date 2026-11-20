"""Build the hosted browser preview into an output folder.

Usage: python preview/build_preview.py <out_dir>   (run `VITE_PREVIEW=1 npx vite build --outDir <out_dir>` first)
Writes <out_dir>/engine.json containing the engine source, curriculum and self-written shims.
"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
out = Path(sys.argv[1])
files = {}
for base, prefix in ((root / "backend" / "app", "app"), (root / "preview" / "shims", "shims")):
    for f in sorted(base.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts and f.suffix in {".py", ".json"}:
            files[f"{prefix}/{f.relative_to(base).as_posix()}"] = f.read_text(encoding="utf-8")
boot = (root / "preview" / "engine_boot.py").read_text(encoding="utf-8")
(out / "engine.json").write_text(json.dumps({"files": files, "boot": boot}, ensure_ascii=False), encoding="utf-8")
print(f"engine.json: {len(files)} files")
