"""Locate bundled assets in a source checkout and in a frozen executable."""

from __future__ import annotations

import sys
from pathlib import Path


def _frozen_root() -> Path | None:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return None


def project_root() -> Path:
    frozen = _frozen_root()
    if frozen is not None:
        return frozen
    for parent in Path(__file__).resolve().parents:
        if (parent / "assets").is_dir() and (parent / "scripts").is_dir():
            return parent
    return Path(__file__).resolve().parents[3]


def asset_dir() -> Path:
    return project_root() / "assets"


def asset(name: str) -> Path:
    return asset_dir() / name


def default_cover() -> Path:
    """The bundled cover template (title and fields as ``{{placeholders}}``)."""
    return asset("cover.docx")
