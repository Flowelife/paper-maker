#!/usr/bin/env python3
"""Pack the skill (SKILL.md, scripts/, references/, assets/) into a zip.

    python scripts/package_skill.py           # -> paper-maker.zip
    python scripts/package_skill.py -o build/papermaker-skill.zip

Development-only files (test/, tests/, design.md, the source thesis) are not
included, so the archive is exactly the distributable skill.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INCLUDE = ("SKILL.md", "scripts", "references", "assets")
SKIP_PARTS = {"__pycache__", "build", "dist", ".git", ".work"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".tmp"}


def _iter_files(directory: Path) -> list[Path]:
    files = []
    for path in sorted(directory.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if path.suffix in SKIP_SUFFIXES:
            continue
        files.append(path)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="打包技能为 zip")
    parser.add_argument("-o", "--output", default=str(ROOT / "paper-maker.zip"),
                        help="输出文件（默认 paper-maker.zip）")
    args = parser.parse_args(argv)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    count = 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in INCLUDE:
            target = ROOT / name
            if target.is_file():
                archive.write(target, name)
                count += 1
            elif target.is_dir():
                for path in _iter_files(target):
                    archive.write(path, path.relative_to(ROOT).as_posix())
                    count += 1
            else:
                print(f"警告: 缺少 {name}")
    size = output.stat().st_size / 1024
    print(f"已打包 {count} 个文件 -> {output}（{size:.1f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
