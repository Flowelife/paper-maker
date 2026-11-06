"""Copy the cover of one Word document onto another (zip-level, .doc aware).

The copy is package-level: every block before the table of contents is cloned
together with *all* parts they reference (images, charts, embedded objects,
headers/footers of a dedicated cover section), so nothing is silently dropped.
"""

from __future__ import annotations

import hashlib
import os
import posixpath
import re
import shutil
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring

from . import office, styles as style_defs
from .ns import R, W, r, w, register_namespaces
from .package import CONTENT_TYPES, REL_TYPES, Package, serialize_xml

CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_CT = "{%s}" % CT_NS
REL_BASE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

REL_NUMBERING = REL_BASE + "/numbering"

IMAGE_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "bmp": "image/bmp", "tif": "image/tiff",
    "tiff": "image/tiff", "emf": "image/x-emf", "wmf": "image/x-wmf",
    "svg": "image/svg+xml",
}


def _read_parts(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()
                if not name.endswith("/")}


def _write_parts(parts: dict[str, bytes], path: Path) -> Path:
    tmp = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(parts):
            archive.writestr(name, parts[name])
    os.replace(tmp, path)
    return path


def ensure_docx(path: str | Path) -> Path:
    """Return a .docx path for ``path``, converting .doc via WPS/Word when needed."""
    path = Path(path)
    if path.suffix.lower() == ".docx":
        return path
    workdir = Path(tempfile.mkdtemp(prefix="papermaker-"))
    local = workdir / path.name
    shutil.copy2(path, local)
    converted = office.convert_document(local, "docx")
    if converted is None or not converted.exists():
        raise RuntimeError(
            f"无法处理 {path.name}: 需要本机安装 WPS 或 Microsoft Word 才能转换 .doc")
    return converted


# --------------------------------------------------------------------------
# document helpers
# --------------------------------------------------------------------------
def _compact(text: str) -> str:
    return re.sub(r"[\s\u3000]+", "", text)


def cover_boundary(children: list[Element]) -> int:
    """Index of the first block after the cover (TOC heading wins)."""
    for index, child in enumerate(children):
        if child.tag == w("p") and _compact("".join(child.itertext())) in ("目录", "目錄"):
            return index
    for index, child in enumerate(children):
        if child.tag != w("p"):
            continue
        ppr = child.find(w("pPr"))
        if ppr is None:
            continue
        outline = ppr.find(w("outlineLvl"))
        style = ppr.find(w("pStyle"))
        if outline is not None and outline.get(w("val")) == "0":
            return index
        if style is not None and (style.get(w("val")) or "").lower() in ("heading1", "1"):
            return index
    for index, child in enumerate(children):
        if child.find(w("pPr")) is not None and child.find(w("pPr")).find(w("sectPr")) is not None:
            return index
    return len(children)


def _sect_of(paragraph: Element):
    ppr = paragraph.find(w("pPr"))
    if ppr is None:
        return None
    return ppr.find(w("sectPr"))


def _first_section(children: list[Element]) -> tuple[int, Element] | tuple[None, None]:
    for index, child in enumerate(children):
        if child.tag == w("p"):
            sect = _sect_of(child)
            if sect is not None:
                return index, sect
    return None, None


def _rels_name(part: str) -> str:
    directory, _, name = part.rpartition("/")
    return f"{directory}/_rels/{name}.rels" if directory else f"_rels/{name}.rels"


def _resolve_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base = posixpath.dirname(source_part)
    return posixpath.normpath(posixpath.join(base, target))


class _Rels:
    """Relationship part kept as plain tuples so serialisation stays namespace-clean."""

    def __init__(self, data: bytes | None):
        self.entries: list[tuple[str, str, str, bool]] = []
        if data:
            root = fromstring(data)
            for rel in root:
                self.entries.append((rel.get("Id"), rel.get("Type"), rel.get("Target"),
                                     rel.get("TargetMode") == "External"))
        numbers = [int(rid[3:]) for rid, *_ in self.entries
                   if rid and rid.startswith("rId") and rid[3:].isdigit()]
        self.next_id = max(numbers or [0]) + 1

    def add(self, rel_type: str, target: str, external: bool = False) -> str:
        rid = f"rId{self.next_id}"
        self.next_id += 1
        self.entries.append((rid, rel_type, target, external))
        return rid

    def get(self, rid: str):
        for entry in self.entries:
            if entry[0] == rid:
                return entry
        return None

    def targets(self) -> list[str]:
        return [entry[2] for entry in self.entries]

    def to_bytes(self) -> bytes:
        return _rels_bytes(self.entries)


def _rels_bytes(entries: list[tuple[str, str, str, bool]]) -> bytes:
    from xml.sax.saxutils import quoteattr

    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for rid, rel_type, target, external in entries:
        mode = ' TargetMode="External"' if external else ""
        lines.append(f"<Relationship Id={quoteattr(rid)} Type={quoteattr(rel_type)} "
                     f"Target={quoteattr(target)}{mode}/>")
    lines.append("</Relationships>")
    return "\n".join(lines).encode("utf-8")


class _ContentTypes:
    """Resolve the content type of an arbitrary part from [Content_Types].xml."""

    def __init__(self, data: bytes | None):
        self.defaults: dict[str, str] = {}
        self.overrides: dict[str, str] = {}
        if not data:
            return
        root = fromstring(data)
        for el in root:
            tag = el.tag.split("}")[-1]
            if tag == "Default":
                self.defaults[(el.get("Extension") or "").lower()] = el.get("ContentType") or ""
            elif tag == "Override":
                self.overrides[el.get("PartName") or ""] = el.get("ContentType") or ""

    def for_part(self, part: str) -> str | None:
        override = self.overrides.get("/" + part)
        if override:
            return override
        ext = part.rsplit(".", 1)[-1].lower() if "." in part else ""
        return self.defaults.get(ext)


class _PartImporter:
    """Copy parts (and their transitive relationships) from source to target."""

    def __init__(self, src_parts: dict[str, bytes], tgt_parts: dict[str, bytes]):
        self.src = src_parts
        self.tgt = tgt_parts
        self.content_types = _ContentTypes(src_parts.get("[Content_Types].xml"))
        self.needed_types: dict[str, str] = {}
        self.copied: dict[str, str] = {}
        self.hashes: dict[str, str] = {}
        for name, data in tgt_parts.items():
            if name.startswith("word/media/"):
                self.hashes.setdefault(hashlib.sha1(data).hexdigest(), name)

    def _unique_name(self, part: str) -> str:
        match = re.match(r"^(word/)(header|footer)(\d*)\.xml$", part)
        if match:
            index = 1
            while f"{match.group(1)}{match.group(2)}{index}.xml" in self.tgt:
                index += 1
            return f"{match.group(1)}{match.group(2)}{index}.xml"
        directory, _, name = part.rpartition("/")
        stem, dot, ext = name.rpartition(".")
        if not dot:
            stem, ext = name, ""
        suffix = f".{ext}" if ext else ""
        candidate = f"{directory}/cover_{stem}{suffix}" if directory else f"cover_{stem}{suffix}"
        index = 1
        while candidate in self.tgt:
            index += 1
            candidate = (f"{directory}/cover_{stem}{index}{suffix}"
                         if directory else f"cover_{stem}{index}{suffix}")
        return candidate

    def copy_part(self, part: str) -> str | None:
        if part in self.copied:
            return self.copied[part]
        data = self.src.get(part)
        if data is None:
            return None
        if part.startswith("word/media/"):
            digest = hashlib.sha1(data).hexdigest()
            existing = self.hashes.get(digest)
            if existing:
                self.copied[part] = existing
                return existing
        new_part = self._unique_name(part)
        self.tgt[new_part] = data
        self.copied[part] = new_part
        if part.startswith("word/media/"):
            self.hashes[hashlib.sha1(data).hexdigest()] = new_part
        content_type = self.content_types.for_part(part)
        if content_type:
            self.needed_types[new_part] = content_type
        rels_data = self.src.get(_rels_name(part))
        if rels_data:
            entries = []
            for rel in fromstring(rels_data):
                rid, rel_type = rel.get("Id"), rel.get("Type")
                target = rel.get("Target") or ""
                if rel.get("TargetMode") == "External":
                    entries.append((rid, rel_type, target, True))
                    continue
                child = _resolve_target(part, target)
                new_child = self.copy_part(child) if child in self.src else None
                if new_child is None:
                    entries.append((rid, rel_type, target, False))
                else:
                    entries.append((rid, rel_type,
                                    posixpath.relpath(new_child, posixpath.dirname(new_part)),
                                    False))
            if entries:
                self.tgt[_rels_name(new_part)] = _rels_bytes(entries)
        return new_part

    def target_for(self, caller: str, part: str) -> str | None:
        new_part = self.copy_part(part)
        if new_part is None:
            return None
        return posixpath.relpath(new_part, posixpath.dirname(caller) or ".")


def _clone_cover(children: list[Element]) -> list[Element]:
    """Deep-copy cover blocks, dropping bookmarks and section breaks."""
    blocks: list[Element] = []
    for child in children:
        if child.tag == w("sectPr"):
            # a body-level sectPr is section structure, not cover content
            continue
        block = deepcopy(child)
        for element in list(block.iter()):
            if element.tag in (w("bookmarkStart"), w("bookmarkEnd")):
                for parent in block.iter():
                    if element in list(parent):
                        parent.remove(element)
        # a copied cover must not carry the source's section break: it would
        # split the target's cover from its own last paragraph
        if block.tag == w("p"):
            ppr = block.find(w("pPr"))
            sect = ppr.find(w("sectPr")) if ppr is not None else None
            if sect is not None:
                ppr.remove(sect)
                if len(ppr) == 0 and all(e.tag == w("pPr") for e in block):
                    continue
        blocks.append(block)
    return blocks


def _rewrite_rel_ids(blocks: list[Element], mapping: dict[str, str]) -> None:
    if not mapping:
        return
    for block in blocks:
        for element in block.iter():
            for key, value in list(element.attrib.items()):
                if key.startswith("{%s}" % R) and value in mapping:
                    element.set(key, mapping[value])


def _fill_placeholders(blocks: list[Element], values: dict[str, str]) -> None:
    tokens = {"{{%s}}" % key: str(value) for key, value in values.items()}
    for block in blocks:
        for element in block.iter(w("t")):
            if not element.text or "{{" not in element.text:
                continue
            text = element.text
            for token, value in tokens.items():
                text = text.replace(token, value)
            element.text = text


def cover_values(meta: dict) -> dict[str, str]:
    """Values injected into the bundled cover template."""
    if not isinstance(meta, dict):
        return {}
    keys = ("title", "course", "author", "student_id", "grade", "college",
            "major", "class", "advisor", "date")
    return {key: str(meta.get(key) or "") for key in keys}


# --------------------------------------------------------------------------
# styles / numbering
# --------------------------------------------------------------------------
def _import_styles(src_styles: Element, tgt_styles: Element,
                   used: set[str]) -> dict[str, str]:
    tgt_by_id = {style.get(w("styleId")): style for style in tgt_styles.findall(w("style"))}
    tgt_by_name: dict[str, str] = {}
    for style_id, style in tgt_by_id.items():
        name = style.find(w("name"))
        if name is not None:
            tgt_by_name.setdefault((name.get(w("val")) or "").lower(), style_id)
    src_by_id = {style.get(w("styleId")): style for style in src_styles.findall(w("style"))}

    mapping: dict[str, str] = {}
    queue = [sid for sid in used if sid]
    imported: list[Element] = []
    while queue:
        style_id = queue.pop(0)
        if style_id in mapping:
            continue
        src_style = src_by_id.get(style_id)
        if src_style is None:
            mapping[style_id] = style_id
            continue
        name_el = src_style.find(w("name"))
        name = (name_el.get(w("val")) if name_el is not None else style_id) or style_id
        existing = tgt_by_id.get(style_id)
        if existing is not None and (existing.find(w("name")) is not None and
                                     (existing.find(w("name")).get(w("val")) or "").lower()
                                     == name.lower()):
            mapping[style_id] = style_id
            continue
        if name.lower() in tgt_by_name:
            mapping[style_id] = tgt_by_name[name.lower()]
            continue
        new_id = style_id
        if new_id in tgt_by_id:
            new_id = f"Imported{style_id}"
        clone = deepcopy(src_style)
        clone.set(w("styleId"), new_id)
        tgt_styles.append(clone)
        tgt_by_id[new_id] = clone
        tgt_by_name[name.lower()] = new_id
        mapping[style_id] = new_id
        imported.append(clone)
        for link in ("basedOn", "next", "link"):
            ref = clone.find(w(link))
            if ref is not None:
                queue.append(ref.get(w("val")))

    for clone in imported:
        for link in ("basedOn", "next", "link"):
            ref = clone.find(w(link))
            if ref is not None and ref.get(w("val")) in mapping:
                ref.set(w("val"), mapping[ref.get(w("val"))])
    return mapping


def _rewrite_styles(blocks: list[Element], mapping: dict[str, str]) -> None:
    if not mapping:
        return
    for block in blocks:
        for element in block.iter():
            if element.tag in (w("pStyle"), w("rStyle"), w("tblStyle"), w("numStyleLink")):
                value = element.get(w("val"))
                if value in mapping and mapping[value] != value:
                    element.set(w("val"), mapping[value])


def _used_style_ids(blocks: list[Element]) -> set[str]:
    used: set[str] = set()
    for block in blocks:
        for element in block.iter():
            if element.tag in (w("pStyle"), w("rStyle"), w("tblStyle")):
                value = element.get(w("val"))
                if value:
                    used.add(value)
    return used


def _import_numbering(src_data: bytes, tgt_data: bytes | None,
                      used: set[str]) -> tuple[bytes, dict[str, str]]:
    if not used:
        return tgt_data or b"", {}
    src_root = fromstring(src_data)
    if tgt_data:
        tgt_root = fromstring(tgt_data)
    else:
        tgt_root = Element(w("numbering"))

    src_abstract = {el.get(w("abstractNumId")): el
                    for el in src_root.findall(w("abstractNum"))}
    src_nums = {el.get(w("numId")): el for el in src_root.findall(w("num"))}
    tgt_num_ids = [int(el.get(w("numId"))) for el in tgt_root.findall(w("num"))
                   if (el.get(w("numId")) or "").isdigit()]
    tgt_abs_ids = [int(el.get(w("abstractNumId"))) for el in tgt_root.findall(w("abstractNum"))
                   if (el.get(w("abstractNumId")) or "").isdigit()]
    next_num = max(tgt_num_ids or [0]) + 1
    next_abs = max(tgt_abs_ids or [0]) + 1

    mapping: dict[str, str] = {}
    for num_id in used:
        num = src_nums.get(num_id)
        if num is None:
            continue
        abs_ref = num.find(w("abstractNumId"))
        abs_id = abs_ref.get(w("val")) if abs_ref is not None else None
        abstract = src_abstract.get(abs_id)
        if abstract is None:
            continue
        new_abs = deepcopy(abstract)
        new_abs.set(w("abstractNumId"), str(next_abs))
        new_num = deepcopy(num)
        new_num.set(w("numId"), str(next_num))
        new_num.find(w("abstractNumId")).set(w("val"), str(next_abs))
        insert_at = next((i for i, child in enumerate(list(tgt_root))
                          if child.tag == w("num")), len(tgt_root))
        tgt_root.insert(insert_at, new_abs)
        tgt_root.append(new_num)
        mapping[num_id] = str(next_num)
        next_abs += 1
        next_num += 1

    return serialize_xml(tgt_root), mapping


def _rewrite_numbering(blocks: list[Element], mapping: dict[str, str]) -> None:
    if not mapping:
        return
    for block in blocks:
        for element in block.iter():
            if element.tag == w("numId"):
                value = element.get(w("val"))
                if value in mapping:
                    element.set(w("val"), mapping[value])


# --------------------------------------------------------------------------
# content types
# --------------------------------------------------------------------------
def _ensure_content_types(parts: dict[str, bytes], needed: dict[str, str]) -> None:
    data = parts.get("[Content_Types].xml")
    if data is None:
        raise RuntimeError("目标文档缺少 [Content_Types].xml")
    text = data.decode("utf-8")
    changed = False
    for part, content_type in needed.items():
        if content_type.startswith("image/"):
            ext = part.rsplit(".", 1)[-1].lower()
            if f'Extension="{ext}"' not in text:
                text = text.replace(
                    "</Types>",
                    f'<Default Extension="{ext}" ContentType="{content_type}"/></Types>')
                changed = True
            continue
        part_name = "/" + part
        if f'PartName="{part_name}"' not in text:
            text = text.replace(
                "</Types>",
                f'<Override PartName="{part_name}" ContentType="{content_type}"/></Types>')
            changed = True
    if "word/numbering.xml" in parts and "/word/numbering.xml" not in text:
        text = text.replace(
            "</Types>",
            '<Override PartName="/word/numbering.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>')
        changed = True
    if changed:
        parts["[Content_Types].xml"] = text.encode("utf-8")


# --------------------------------------------------------------------------
# copy
# --------------------------------------------------------------------------
def _import_block_relationships(blocks: list[Element], src_rels: _Rels,
                                tgt_rels: _Rels, importer: _PartImporter) -> None:
    """Repoint every r:* attribute of the cloned blocks at target relationships."""
    rewritten: dict[str, str] = {}
    for block in blocks:
        for element in block.iter():
            for key, value in list(element.attrib.items()):
                if not key.startswith("{%s}" % R):
                    continue
                if value in rewritten:
                    element.set(key, rewritten[value])
                    continue
                rel = src_rels.get(value)
                if rel is None:
                    continue
                _rid, rel_type, target, external = rel
                if external:
                    new_id = tgt_rels.add(rel_type, target, external=True)
                else:
                    source_part = _resolve_target("word/document.xml", target)
                    new_target = importer.target_for("word/document.xml", source_part)
                    if new_target is None:
                        continue
                    new_id = tgt_rels.add(rel_type, new_target)
                rewritten[value] = new_id
                element.set(key, new_id)


def _copy_cover_headers(src_children: list[Element], src_end: int,
                        src_rels: _Rels, tgt_rels: _Rels,
                        importer: _PartImporter, style_map: dict[str, str],
                        tgt_sect: Element | None) -> bool:
    """Bring the source's dedicated cover-section header/footer across."""
    if tgt_sect is None:
        return False
    index, src_sect = _first_section(src_children)
    if src_sect is None or index is None or index >= src_end:
        return False
    copied_any = False
    for kind in ("headerReference", "footerReference"):
        existing = tgt_sect.findall(w(kind))
        for ref in existing:
            tgt_sect.remove(ref)
        position = 0 if kind == "headerReference" else len(tgt_sect.findall(w("headerReference")))
        for offset, ref in enumerate(src_sect.findall(w(kind))):
            rid = ref.get(r("id"))
            rel = src_rels.get(rid) if rid else None
            if rel is None:
                continue
            _rid, rel_type, target, external = rel
            if external:
                continue
            source_part = _resolve_target("word/document.xml", target)
            new_target = importer.target_for("word/document.xml", source_part)
            if new_target is None:
                continue
            new_ref = deepcopy(ref)
            new_ref.set(r("id"), tgt_rels.add(rel_type, new_target))
            tgt_sect.insert(position + offset, new_ref)
            copied_any = True
            part_copy = importer.copied.get(source_part)
            if part_copy and part_copy in importer.tgt:
                part_root = fromstring(importer.tgt[part_copy])
                _rewrite_styles([part_root], style_map)
                importer.tgt[part_copy] = serialize_xml(part_root)
    return copied_any


def build_cover_template(source: str | Path, output: str | Path, edit) -> Path:
    """Write a standalone docx holding only the cover of *source*.

    ``edit(blocks)`` receives the cloned cover blocks (XML elements) and may
    rewrite their text; the result is used as the bundled cover template.
    """
    from .builder import DocumentBuilder

    register_namespaces()
    source_path = Path(source)
    src_docx = ensure_docx(source_path)
    src_parts = _read_parts(src_docx)
    src_doc = fromstring(src_parts["word/document.xml"])
    children = list(src_doc.find(w("body")))
    blocks = _clone_cover(children[:cover_boundary(children)])
    if not blocks:
        raise RuntimeError(f"{source_path.name} 中未找到封面内容")
    edit(blocks)

    src_rels = _Rels(src_parts.get("word/_rels/document.xml.rels"))
    tgt_rels = _Rels(None)
    importer = _PartImporter(src_parts, {})

    style_root = fromstring(style_defs.STYLES_XML)
    if src_parts.get("word/styles.xml"):
        style_map = _import_styles(fromstring(src_parts["word/styles.xml"]),
                                   style_root, _used_style_ids(blocks))
        _rewrite_styles(blocks, style_map)

    _import_block_relationships(blocks, src_rels, tgt_rels, importer)

    used_nums = {el.get(w("val")) for block in blocks for el in block.iter()
                 if el.tag == w("numId") and el.get(w("val"))}
    numbering = None
    if used_nums and "word/numbering.xml" in src_parts:
        numbering, num_map = _import_numbering(src_parts["word/numbering.xml"],
                                               None, used_nums)
        _rewrite_numbering(blocks, num_map)

    doc = Element(w("document"))
    body = SubElement(doc, w("body"))
    for block in blocks:
        body.append(block)
    body.append(Element(w("p")))
    sect = SubElement(body, w("sectPr"))
    DocumentBuilder._page_setup(sect, "decimal", 1)

    pkg = Package()
    pkg.add_part("word/styles.xml", serialize_xml(style_root), CONTENT_TYPES["styles"])
    pkg.add_part("word/settings.xml", style_defs.SETTINGS_XML, CONTENT_TYPES["settings"])
    pkg.add_relationship("", REL_TYPES["officeDocument"], "word/document.xml")
    pkg.add_relationship("word/document.xml", REL_TYPES["styles"], "styles.xml")
    pkg.add_relationship("word/document.xml", REL_TYPES["settings"], "settings.xml")
    if numbering:
        pkg.add_part("word/numbering.xml", numbering,
                     "application/vnd.openxmlformats-officedocument."
                     "wordprocessingml.numbering+xml")
        pkg.add_relationship("word/document.xml", REL_NUMBERING, "numbering.xml")
    for name, data in importer.tgt.items():
        if name.startswith("word/media/"):
            pkg.add_image(name, data)
        else:
            pkg.add_part(name, data, importer.needed_types.get(name))
    # imported ids may collide with the structural ones, so allocate fresh ids
    remap = {rid: pkg.add_relationship("word/document.xml", rel_type, target, external)
             for rid, rel_type, target, external in tgt_rels.entries}
    _rewrite_rel_ids(blocks, remap)
    pkg.add_part("word/document.xml", serialize_xml(doc), CONTENT_TYPES["document"])
    return pkg.save(output)


def copy_cover(source: str | Path, target: str | Path,
               output: str | Path | None = None,
               replacements: dict[str, str] | None = None) -> Path:
    """Replace the cover of ``target`` with the cover blocks of ``source``."""
    register_namespaces()
    source_path = Path(source)
    target_path = Path(target)
    output_path = Path(output) if output else target_path
    target_is_doc = output_path.suffix.lower() == ".doc"

    src_docx = ensure_docx(source_path)
    tgt_docx = ensure_docx(target_path)

    src_parts = _read_parts(src_docx)
    tgt_parts = _read_parts(tgt_docx)

    src_doc = fromstring(src_parts["word/document.xml"])
    tgt_doc = fromstring(tgt_parts["word/document.xml"])

    src_body = src_doc.find(w("body"))
    tgt_body = tgt_doc.find(w("body"))
    src_children = list(src_body)
    tgt_children = list(tgt_body)

    src_end = cover_boundary(src_children)
    tgt_end = cover_boundary(tgt_children)

    blocks = _clone_cover(src_children[:src_end])
    if not blocks:
        raise RuntimeError(f"{source_path.name} 中未找到封面内容")
    if replacements:
        _fill_placeholders(blocks, replacements)

    src_rels = _Rels(src_parts.get("word/_rels/document.xml.rels"))
    tgt_rels = _Rels(tgt_parts.get("word/_rels/document.xml.rels"))
    importer = _PartImporter(src_parts, tgt_parts)

    # styles must be known before header/footer parts are rewritten
    style_map: dict[str, str] = {}
    if src_parts.get("word/styles.xml") and tgt_parts.get("word/styles.xml"):
        src_styles = fromstring(src_parts["word/styles.xml"])
        tgt_styles = fromstring(tgt_parts["word/styles.xml"])
        style_map = _import_styles(src_styles, tgt_styles, _used_style_ids(blocks))
        _rewrite_styles(blocks, style_map)
        tgt_parts["word/styles.xml"] = serialize_xml(tgt_styles)

    _import_block_relationships(blocks, src_rels, tgt_rels, importer)

    used_nums = {el.get(w("val")) for block in blocks for el in block.iter()
                 if el.tag == w("numId") and el.get(w("val"))}
    if used_nums and "word/numbering.xml" in src_parts:
        numbering, num_map = _import_numbering(src_parts["word/numbering.xml"],
                                               tgt_parts.get("word/numbering.xml"),
                                               used_nums)
        _rewrite_numbering(blocks, num_map)
        if numbering:
            tgt_parts["word/numbering.xml"] = numbering
            if not any(target.lstrip("/") == "word/numbering.xml"
                       for target in tgt_rels.targets()):
                tgt_rels.add(REL_NUMBERING, "numbering.xml")

    # target cover section paragraph (kept in place, it terminates the cover)
    insert_at = tgt_end
    cover_sect: Element | None = None
    if tgt_end > 0:
        last = tgt_children[tgt_end - 1]
        if last.tag == w("p") and _sect_of(last) is not None:
            cover_sect = _sect_of(last)
            insert_at = tgt_end - 1
    if cover_sect is None:
        for child in tgt_children[:tgt_end]:
            if child.tag == w("p") and _sect_of(child) is not None:
                cover_sect = _sect_of(child)
                break
    _copy_cover_headers(src_children, src_end, src_rels, tgt_rels,
                        importer, style_map, cover_sect)

    for child in tgt_children[:insert_at]:
        tgt_body.remove(child)
    for offset, block in enumerate(blocks):
        tgt_body.insert(offset, block)

    tgt_parts["word/document.xml"] = serialize_xml(tgt_doc)
    tgt_parts["word/_rels/document.xml.rels"] = tgt_rels.to_bytes()
    _ensure_content_types(tgt_parts, importer.needed_types)

    if target_is_doc:
        workdir = Path(tempfile.mkdtemp(prefix="papermaker-"))
        staged = workdir / (output_path.stem + ".docx")
        _write_parts(tgt_parts, staged)
        converted = office.convert_document(staged, "doc")
        if converted is None:
            raise RuntimeError("已生成 docx，但 .doc 回写失败（需要 WPS 或 Word）")
        shutil.move(str(converted), str(output_path))
        return output_path
    return _write_parts(tgt_parts, output_path)
