"""Optional WPS / Microsoft Word automation used for field refresh and .doc."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

PROG_IDS = ("KWPS.Application", "Word.Application")

WD_FORMAT_DOC = 0
WD_FORMAT_DOCX = 16
WD_FORMAT_PDF = 17


def _dispatch():
    try:
        import win32com.client  # type: ignore
    except Exception:  # noqa: BLE001
        return None, None
    for prog in PROG_IDS:
        try:
            app = win32com.client.DispatchEx(prog)
        except Exception:  # noqa: BLE001
            continue
        return app, prog
    return None, None


def _prepare(app) -> None:
    try:
        app.Visible = False
    except Exception:  # noqa: BLE001
        pass
    try:
        app.DisplayAlerts = 0
    except Exception:  # noqa: BLE001
        pass


def available() -> bool:
    app, _prog = _dispatch()
    if app is None:
        return False
    try:
        app.Quit()
    except Exception:  # noqa: BLE001
        pass
    return True


def update_fields(path: str | Path, *, save: bool = True,
                  pdf: str | Path | None = None) -> bool:
    """Refresh TOC/PAGE fields (and optionally export PDF). False if no engine."""
    path = Path(path).resolve()
    app, _prog = _dispatch()
    if app is None:
        return False
    doc = None
    try:
        _prepare(app)
        doc = app.Documents.Open(str(path))
        for index in range(1, int(doc.TablesOfContents.Count) + 1):
            doc.TablesOfContents(index).Update()
        doc.Fields.Update()
        doc.Repaginate()
        if pdf is not None:
            doc.SaveAs2(str(Path(pdf).resolve()), FileFormat=WD_FORMAT_PDF)
        if save:
            doc.Save()
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            app.Quit()
        except Exception:  # noqa: BLE001
            pass


def convert_document(path: str | Path, fmt: str = "docx") -> Path | None:
    """Convert .doc <-> .docx through the installed office suite."""
    path = Path(path).resolve()
    app, _prog = _dispatch()
    if app is None:
        return None
    target = path.with_suffix("." + fmt)
    if target == path:
        target = path.with_name(path.stem + "_converted." + fmt)
    doc = None
    try:
        _prepare(app)
        doc = app.Documents.Open(str(path))
        doc.SaveAs2(str(target), FileFormat=WD_FORMAT_DOCX if fmt == "docx" else WD_FORMAT_DOC)
        return target
    except Exception:  # noqa: BLE001
        return None
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            app.Quit()
        except Exception:  # noqa: BLE001
            pass
