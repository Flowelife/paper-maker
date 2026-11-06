"""Minimal OOXML (OPC) package writer."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .ns import REL_BASE

IMAGE_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "emf": "image/x-emf",
    "wmf": "image/x-wmf",
    "svg": "image/svg+xml",
}

REL_TYPES = {
    "officeDocument": REL_BASE + "/officeDocument",
    "styles": REL_BASE + "/styles",
    "settings": REL_BASE + "/settings",
    "fontTable": REL_BASE + "/fontTable",
    "theme": REL_BASE + "/theme",
    "header": REL_BASE + "/header",
    "footer": REL_BASE + "/footer",
    "image": REL_BASE + "/image",
    "numbering": REL_BASE + "/numbering",
    "footnotes": REL_BASE + "/footnotes",
    "endnotes": REL_BASE + "/endnotes",
    "core": "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
    "app": REL_BASE + "/extended-properties",
}

CONTENT_TYPES = {
    "document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    "styles": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
    "settings": "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml",
    "fontTable": "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml",
    "header": "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
    "footer": "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
    "numbering": "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml",
    "core": "application/vnd.openxmlformats-package.core-properties+xml",
    "app": "application/vnd.openxmlformats-officedocument.extended-properties+xml",
}


class Package:
    def __init__(self) -> None:
        self.parts: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}
        self.defaults: dict[str, str] = {
            "rels": "application/vnd.openxmlformats-package.relationships+xml",
            "xml": "application/xml",
        }
        self.rels: dict[str, list[tuple[str, str, str, bool]]] = {}
        self._rid = 0

    # -- parts -------------------------------------------------------------
    def add_part(self, name: str, data: bytes | str, content_type: str | None = None) -> str:
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.parts[name] = data
        if content_type:
            self.content_types[name] = content_type
        return name

    def add_image(self, name: str, data: bytes) -> str:
        ext = name.rsplit(".", 1)[-1].lower()
        self.defaults.setdefault(ext, IMAGE_TYPES.get(ext, "application/octet-stream"))
        self.parts[name] = data
        return name

    def next_rid(self) -> str:
        self._rid += 1
        return f"rId{self._rid}"

    def add_relationship(self, source: str, rel_type: str, target: str,
                         external: bool = False, rid: str | None = None) -> str:
        if rid is None:
            rid = self.next_rid()
        elif rid.startswith("rId") and rid[3:].isdigit():
            self._rid = max(self._rid, int(rid[3:]))
        self.rels.setdefault(source, []).append((rid, rel_type, target, external))
        return rid

    # -- serialisation -----------------------------------------------------
    def _content_types_xml(self) -> bytes:
        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        ]
        for ext, ctype in sorted(self.defaults.items()):
            lines.append(f'<Default Extension="{ext}" ContentType="{ctype}"/>')
        for part, ctype in sorted(self.content_types.items()):
            lines.append(f'<Override PartName="/{part}" ContentType="{ctype}"/>')
        lines.append("</Types>")
        return "\n".join(lines).encode("utf-8")

    def _rels_xml(self, source: str) -> bytes:
        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        ]
        for rid, rtype, target, external in self.rels.get(source, []):
            mode = ' TargetMode="External"' if external else ""
            lines.append(
                f"<Relationship Id={quoteattr(rid)} Type={quoteattr(rtype)} "
                f"Target={quoteattr(target)}{mode}/>"
            )
        lines.append("</Relationships>")
        return "\n".join(lines).encode("utf-8")

    @staticmethod
    def _rels_name(part: str) -> str:
        if part == "":
            return "_rels/.rels"
        directory, _, name = part.rpartition("/")
        prefix = f"{directory}/" if directory else ""
        return f"{prefix}_rels/{name}.rels"

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        order = ["word/document.xml", "word/styles.xml", "word/settings.xml"]
        names = [n for n in order if n in self.parts]
        names += [n for n in sorted(self.parts) if n not in names]
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", self._content_types_xml())
            for part in [""] + sorted(s for s in self.rels if s):
                if self.rels.get(part):
                    zf.writestr(self._rels_name(part), self._rels_xml(part))
            for name in names:
                zf.writestr(name, self.parts[name])
        return path


def serialize_xml(root) -> bytes:
    """Serialise an element as UTF-8 with a Word-compatible declaration."""
    from xml.etree.ElementTree import tostring

    return (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            + tostring(root, encoding="utf-8", xml_declaration=False))


def escape_text(text: str) -> str:
    return escape(text)
