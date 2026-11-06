"""Structural summary of a DOCX, used by `papermaker inspect`."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree.ElementTree import fromstring

from .ns import M, R, W, WP
from .ns import m, r, w, wp


def _text(node) -> str:
    return "".join(node.itertext())


def summarize(path: str | Path) -> dict:
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        document = fromstring(archive.read("word/document.xml"))
        styles_xml = archive.read("word/styles.xml") if "word/styles.xml" in archive.namelist() else None
        names = set(archive.namelist())
    body = document.find(w("body"))
    style_names: dict[str, str] = {}
    style_outline: dict[str, int] = {}
    if styles_xml is not None:
        styles = fromstring(styles_xml)
        for style in styles.findall(w("style")):
            style_id = style.get(w("styleId"))
            name_el = style.find(w("name"))
            style_names[style_id] = name_el.get(w("val")) if name_el is not None else ""
            ppr = style.find(w("pPr"))
            if ppr is not None:
                lvl = ppr.find(w("outlineLvl"))
                if lvl is not None and lvl.get(w("val")) is not None:
                    style_outline[style_id] = int(lvl.get(w("val")))

    headings: list[dict] = []
    sections: list[dict] = []
    counts = {"paragraphs": 0, "tables": 0, "images": 0, "equations": 0, "display_equations": 0}
    for child in body:
        if child.tag == w("p"):
            counts["paragraphs"] += 1
            ppr = child.find(w("pPr"))
            style_id = ""
            outline = None
            if ppr is not None:
                style_el = ppr.find(w("pStyle"))
                style_id = style_el.get(w("val")) if style_el is not None else ""
                outline_el = ppr.find(w("outlineLvl"))
                if outline_el is not None:
                    outline = int(outline_el.get(w("val")))
                elif style_id in style_outline:
                    outline = style_outline[style_id]
            text = _text(child).strip()
            if outline is not None and outline < 4 and text:
                headings.append({"level": outline + 1, "text": text,
                                 "style": style_names.get(style_id, style_id)})
            if child.find(".//" + m("oMath")) is not None:
                counts["equations"] += 1
                if style_names.get(style_id) == "居中公式":
                    counts["display_equations"] += 1
            if child.find(".//" + w("drawing")) is not None:
                counts["images"] += 1
            if ppr is not None:
                sect = ppr.find(w("sectPr"))
                if sect is not None:
                    sections.append(_sect_info(sect))
        elif child.tag == w("tbl"):
            counts["tables"] += 1
    final = body.find(w("sectPr"))
    if final is not None:
        sections.append(_sect_info(final))
    return {"file": str(path), "counts": counts, "headings": headings, "sections": sections}


def _sect_info(sect) -> dict:
    info = {
        "headers": [ref.get(r("id")) for ref in sect.findall(w("headerReference"))],
        "footers": [ref.get(r("id")) for ref in sect.findall(w("footerReference"))],
    }
    pgnum = sect.find(w("pgNumType"))
    if pgnum is not None:
        info["page_format"] = pgnum.get(w("fmt"), "decimal")
        info["page_start"] = pgnum.get(w("start"))
    pgsz = sect.find(w("pgSz"))
    if pgsz is not None:
        info["page_size"] = [pgsz.get(w("w")), pgsz.get(w("h"))]
    return info


def ensure_docx(path: str | Path) -> Path:
    path = Path(path)
    if path.suffix.lower() == ".docx":
        return path
    from . import office

    converted = office.convert_document(path, "docx")
    if converted is None:
        raise RuntimeError(f"无法处理 {path.name}: .doc 需要本机安装 WPS 或 Word")
    return converted
