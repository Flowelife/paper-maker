#!/usr/bin/env python3
"""Package paper-maker into a single-file executable with PyInstaller.

The repository ships sources only; run this on the target platform to produce
``dist/papermaker`` (``dist/papermaker.exe`` on Windows). Requires:

    python -m pip install pyinstaller
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = HERE / "papermaker.spec"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="打包 paper-maker 可执行文件")
    parser.add_argument("-o", "--output", default=str(ROOT / "dist"),
                        help="输出目录（默认 dist/）")
    parser.add_argument("--keep-build", action="store_true",
                        help="保留 build/ 中间目录")
    args = parser.parse_args(argv)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("错误: 未安装 PyInstaller，请先运行 python -m pip install pyinstaller",
              file=sys.stderr)
        return 2
    if not SPEC.is_file():
        print(f"错误: 找不到 {SPEC}", file=sys.stderr)
        return 1

    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--distpath", str(Path(args.output).resolve()), str(SPEC)]
    result = subprocess.call(command, cwd=str(ROOT))
    if result == 0 and not args.keep_build:
        shutil.rmtree(ROOT / "build", ignore_errors=True)
    if result == 0:
        target = Path(args.output) / ("papermaker.exe" if sys.platform == "win32" else "papermaker")
        print(f"已生成 {target}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
