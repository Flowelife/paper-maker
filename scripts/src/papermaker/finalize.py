"""Refresh document fields (TOC page numbers) through the office suite."""

from __future__ import annotations

from pathlib import Path

from . import office


def refresh_document(path: str | Path, *,
                     pdf: str | Path | None = None) -> bool:
    path = Path(path)
    if path.suffix.lower() == ".doc":
        return False
    return office.update_fields(path, save=True, pdf=pdf)
