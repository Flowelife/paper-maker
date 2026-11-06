#!/usr/bin/env python3
"""Run paper-maker from source: no installation, no compiled binary.

    python scripts/papermaker.py build paper.json -o out/paper.docx
    python scripts/papermaker.py cover --from cover.docx --to paper.docx
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(HERE / "src"))

from papermaker.cli import main as cli_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
