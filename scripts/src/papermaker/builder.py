"""Build a formatted DOCX from a resolved paper plan."""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import re
from pathlib import Path
from typing import Sequence
from xml.etree.ElementTree import Element, SubElement

from . import styles
from .model import Block, PaperError, Plan, parse_inline
from .ns import (CONTENT_WIDTH_TWIPS, MARGIN_TWIPS, PAGE_HEIGHT_TWIPS,
                 PAGE_WIDTH_TWIPS, a, pic, r, w, wp, xml_space,
                 register_namespaces)
from .omml import latex_to_omath
from .package import CONTENT_TYPES, REL_TYPES, Package
from .imaging import image_extent_cm

EMU_PER_CM = 360000
DEFAULT_MAX_FIGURE_CM = 14.0


def cm_to_emu(value: float) -> int:
    return int(round(value * EMU_PER_CM))


def _el(tag: str, attrs: dict | None = None) -> Element:
    el = Element(tag)
    if attrs:
        for key, value in attrs.items():
            el.set(key, str(value))
    return el


class DocumentBuilder:
    def __init__(self, plan: Plan, base_dir: Path, options: dict | None = None):
        register_namespaces()
        self.plan = plan
        self.base_dir = Path(base_dir)
        self.options = options or {}
        self.pkg = Package()
        self.doc = _el(w("document"))
        self.body = SubElement(self.doc, w("body"))
        self.image_cache: dict[str, tuple[str, str]] = {}
        self.bookmark_id = 100
        self.docpr_id = 1
        self.figures_root = self._figure_roots()
        self.max_figure_cm = float(self.options.get("max_figure_cm", DEFAULT_MAX_FIGURE_CM))

    # ------------------------------------------------------------------
    # part setup
    # ------------------------------------------------------------------
    def setup_parts(self) -> None:
        self.pkg.add_part("word/styles.xml", styles.STYLES_XML, CONTENT_TYPES["styles"])
        self.pkg.add_part("word/settings.xml", styles.SETTINGS_XML, CONTENT_TYPES["settings"])
        self.pkg.add_part("word/document.xml", b"", CONTENT_TYPES["document"])
        self.pkg.add_relationship("", REL_TYPES["officeDocument"], "word/document.xml")
        self.pkg.add_relationship("word/document.xml", REL_TYPES["styles"], "styles.xml")
        self.pkg.add_relationship("word/document.xml", REL_TYPES["settings"], "settings.xml")
        self.pkg.add_relationship("", REL_TYPES["core"], "docProps/core.xml")
        self.pkg.add_relationship("", REL_TYPES["app"], "docProps/app.xml")

        header_rel = self.pkg.add_relationship("word/document.xml", REL_TYPES["header"], "header1.xml")
        footer_rel = self.pkg.add_relationship("word/document.xml", REL_TYPES["footer"], "footer1.xml")
        self.header_rel = header_rel
        self.footer_rel = footer_rel
        self.empty_header_rel = self.pkg.add_relationship(
            "word/document.xml", REL_TYPES["header"], "header2.xml")
        self.empty_footer_rel = self.pkg.add_relationship(
            "word/document.xml", REL_TYPES["footer"], "footer2.xml")
        self.pkg.add_part("word/header1.xml", self._header_xml(), CONTENT_TYPES["header"])
        self.pkg.add_part("word/footer1.xml", self._footer_xml(), CONTENT_TYPES["footer"])
        self.pkg.add_part("word/header2.xml", self._empty_part_xml("hdr"), CONTENT_TYPES["header"])
        self.pkg.add_part("word/footer2.xml", self._empty_part_xml("ftr"), CONTENT_TYPES["footer"])
        self.pkg.add_part("docProps/core.xml", self._core_xml(), CONTENT_TYPES["core"])
        self.pkg.add_part("docProps/app.xml", self._app_xml(), CONTENT_TYPES["app"])

    def _header_text(self) -> str:
        """Header line; ``meta.header`` may use ``{course}`` / ``{title}``."""
        meta = self.plan.meta
        course = str(meta.get("course") or "")
        title = str(meta.get("title") or "")
        template = meta.get("header")
        if template is None:
            return f"《{course}》 论文" if course else ""
        text = str(template)
        if not text:
            return ""
        return text.replace("{course}", course).replace("{title}", title)

    def _header_xml(self) -> bytes:
        text = self._header_text()
        para = _el(w("p"))
        ppr = SubElement(para, w("pPr"))
        SubElement(ppr, w("pStyle")).set(w("val"), "Header")
        if text:
            run = SubElement(para, w("r"))
            rpr = SubElement(run, w("rPr"))
            self._fonts(rpr, east="宋体")
            sz = SubElement(rpr, w("sz"))
            sz.set(w("val"), "21")
            SubElement(rpr, w("szCs")).set(w("val"), "21")
            t = SubElement(run, w("t"))
            t.text = text
        hdr = _el(w("hdr"))
        hdr.append(para)
        return self._serialize(hdr)

    def _footer_xml(self) -> bytes:
        para = _el(w("p"))
        ppr = SubElement(para, w("pPr"))
        SubElement(ppr, w("pStyle")).set(w("val"), "Footer")
        self._field(para, "PAGE", "1", self._run_props(size=21))
        ftr = _el(w("ftr"))
        ftr.append(para)
        return self._serialize(ftr)

    @staticmethod
    def _empty_part_xml(kind: str) -> bytes:
        """An empty header/footer: referenced explicitly so nothing is inherited."""
        para = _el(w("p"))
        ppr = SubElement(para, w("pPr"))
        borders = SubElement(ppr, w("pBdr"))
        for side in ("top", "left", "bottom", "right"):
            border = SubElement(borders, w(side))
            border.set(w("val"), "none")
            border.set(w("sz"), "0")
            border.set(w("space"), "0")
        spacing = SubElement(ppr, w("spacing"))
        spacing.set(w("line"), "240")
        spacing.set(w("lineRule"), "auto")
        rpr = SubElement(ppr, w("rPr"))
        SubElement(rpr, w("sz")).set(w("val"), "21")
        root = _el(w(kind))
        root.append(para)
        return DocumentBuilder._serialize(root)

    def _core_xml(self) -> bytes:
        meta = self.plan.meta
        now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        title = (meta.get("title") or "").strip()
        author = (meta.get("author") or "").strip()
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{_escape(title)}</dc:title>"
            f"<dc:creator>{_escape(author)}</dc:creator>"
            f"<cp:lastModifiedBy>{_escape(author)}</cp:lastModifiedBy>"
            '<cp:revision>1</cp:revision>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
            "</cp:coreProperties>"
        )
        return xml.encode("utf-8")

    def _app_xml(self) -> bytes:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            "<Application>paper-maker</Application><AppVersion>1.0</AppVersion></Properties>"
        ).encode("utf-8")

    @staticmethod
    def _serialize(root: Element) -> bytes:
        from .package import serialize_xml

        return serialize_xml(root)

    # ------------------------------------------------------------------
    # primitives
    # ------------------------------------------------------------------
    @staticmethod
    def _fonts(rpr: Element, size: int | None = None, east: str | None = None,
               ascii_font: str | None = None) -> Element:
        fonts = SubElement(rpr, w("rFonts"))
        if ascii_font:
            fonts.set(w("ascii"), ascii_font)
            fonts.set(w("hAnsi"), ascii_font)
            fonts.set(w("cs"), ascii_font)
        if east:
            fonts.set(w("eastAsia"), east)
            fonts.set(w("hint"), "eastAsia")
        return fonts

    def _run_props(self, *, size: int | None = None, bold: bool = False,
                   east: str | None = None, ascii_font: str | None = None,
                   superscript: bool = False, italic: bool = False,
                   hint_east: bool = False) -> Element:
        rpr = _el(w("rPr"))
        if east or ascii_font or hint_east:
            fonts = self._fonts(rpr, east=east, ascii_font=ascii_font)
            if hint_east:
                fonts.set(w("hint"), "eastAsia")
        if bold:
            SubElement(rpr, w("b"))
            SubElement(rpr, w("bCs"))
        if italic:
            SubElement(rpr, w("i"))
        if superscript:
            SubElement(rpr, w("vertAlign")).set(w("val"), "superscript")
        if size:
            SubElement(rpr, w("sz")).set(w("val"), str(size))
            SubElement(rpr, w("szCs")).set(w("val"), str(size))
        return rpr

    def run(self, text: str, *, bold: bool = False, size: int | None = None,
            east: str | None = None, ascii_font: str | None = None,
            superscript: bool = False, italic: bool = False,
            hint_east: bool = False) -> Element:
        run = _el(w("r"))
        run.append(self._run_props(size=size, bold=bold, east=east,
                                   ascii_font=ascii_font, superscript=superscript,
                                   italic=italic, hint_east=hint_east))
        t = SubElement(run, w("t"))
        t.text = text
        t.set(xml_space(), "preserve")
        return run

    def para(self, *, style: str | None = None, jc: str | None = None,
             ind: dict | None = None, spacing: dict | None = None,
             keep_next: bool = False, keep_lines: bool = False,
             tabs: list[tuple[str, int, str | None]] | None = None,
             outline: int | None = None, page_break: bool = False) -> Element:
        para = _el(w("p"))
        ppr = SubElement(para, w("pPr"))
        if style:
            SubElement(ppr, w("pStyle")).set(w("val"), style)
        if keep_next:
            SubElement(ppr, w("keepNext"))
        if keep_lines:
            SubElement(ppr, w("keepLines"))
        if page_break:
            SubElement(ppr, w("pageBreakBefore"))
        if tabs:
            tab_el = SubElement(ppr, w("tabs"))
            for val, pos, leader in tabs:
                tb = SubElement(tab_el, w("tab"))
                tb.set(w("val"), val)
                tb.set(w("pos"), str(pos))
                if leader:
                    tb.set(w("leader"), leader)
        if spacing:
            sp = SubElement(ppr, w("spacing"))
            for key, value in spacing.items():
                sp.set(w(key), str(value))
        if ind:
            ind_el = SubElement(ppr, w("ind"))
            for key, value in ind.items():
                ind_el.set(w(key), str(value))
        if jc:
            SubElement(ppr, w("jc")).set(w("val"), jc)
        if outline is not None:
            SubElement(ppr, w("outlineLvl")).set(w("val"), str(outline))
        return para

    def _field(self, parent: Element, instr: str, cached: str,
               rpr: Element | None = None) -> None:
        for kind, payload in (("begin", None), ("instr", instr),
                              ("separate", None), ("text", cached), ("end", None)):
            run = _el(w("r"))
            if rpr is not None:
                run.append(_clone(rpr))
            if kind == "instr":
                instr_el = SubElement(run, w("instrText"))
                instr_el.text = " " + payload + " "
                instr_el.set(xml_space(), "preserve")
            elif kind == "text":
                t = SubElement(run, w("t"))
                t.text = payload
            else:
                SubElement(run, w("fldChar")).set(w("fldCharType"), kind)
            parent.append(run)

    def _bookmark(self, para: Element, name: str | None) -> None:
        self.bookmark_id += 1
        if not name:
            return
        start = _el(w("bookmarkStart"))
        start.set(w("id"), str(self.bookmark_id))
        start.set(w("name"), name)
        para.insert(1 if len(para) else 0, start)
        end = _el(w("bookmarkEnd"))
        end.set(w("id"), str(self.bookmark_id))
        para.append(end)

    # ------------------------------------------------------------------
    # inline content
    # ------------------------------------------------------------------
    def add_inline(self, para: Element, text: str, *, mode: str = "default",
                   bold: bool = False, size: int | None = None,
                   east: str | None = None, ascii_font: str | None = None) -> None:
        for seg in parse_inline(text):
            if seg.kind == "text":
                para.append(self.run(seg.text, bold=bold or seg.bold, size=size,
                                     east=east, ascii_font=ascii_font,
                                     italic=seg.italic))
            elif seg.kind == "math":
                para.append(latex_to_omath(seg.latex, display=False))
            elif seg.kind == "sup" and mode == "default":
                para.append(self.run(seg.text, superscript=True, size=size))
            elif seg.kind == "sup":
                para.append(self.run(seg.text, bold=bold, size=size))

    # ------------------------------------------------------------------
    # blocks
    # ------------------------------------------------------------------
    def render_blocks(self, blocks: Sequence[Block], *, appendix: bool = False) -> None:
        for block in blocks:
            if block.kind == "heading":
                self.render_heading(block)
            elif block.kind == "paragraph":
                para = self.para(style="BodyTextIndent")
                self.add_inline(para, block.text)
                self.body.append(para)
            elif block.kind == "figure":
                self.render_figure(block)
            elif block.kind == "table":
                self.render_table(block)
            elif block.kind == "equation":
                self.render_equation(block)
            elif block.kind == "list":
                self.render_list(block)
            elif block.kind == "code":
                self.render_code(block)
            elif block.kind == "reference":
                self.render_reference(block)
            elif block.kind == "note":
                self.render_note(block)
            elif block.kind == "keywords":
                self.render_keywords(block)
            elif block.kind == "empty":
                self.body.append(self.para())
            elif block.kind == "pagebreak":
                para = self.para()
                run = SubElement(para, w("r"))
                SubElement(run, w("br")).set(w("type"), "page")
                self.body.append(para)

    def render_heading(self, block: Block) -> None:
        if block.level == 1:
            para = self.para(style="Heading1")
            para.append(self.run(block.text, hint_east=True))
            self._bookmark(para, block.bookmark)
        elif block.level == 2:
            para = self.para(style="Heading2")
            para.append(self.run(block.text, hint_east=True))
            self._bookmark(para, block.bookmark)
        elif block.level == 3:
            para = self.para(style="Heading3")
            para.append(self.run(block.text, hint_east=True))
            self._bookmark(para, block.bookmark)
        else:
            para = self.para(style="Heading4")
            para.append(self.run(block.text))
            self._bookmark(para, block.bookmark)
        self.body.append(para)

    def render_special_heading(self, text: str, bookmark: str | None, *,
                               english: bool = False, outline: int = 0,
                               page_break: bool = True) -> None:
        para = self.para(style="Heading1", outline=outline)
        if not page_break:
            ppr = para.find(w("pPr"))
            SubElement(ppr, w("pageBreakBefore")).set(w("val"), "0")
        if english:
            para.append(self.run(text, bold=True, ascii_font="Times New Roman"))
        else:
            para.append(self.run(text, hint_east=True))
        self._bookmark(para, bookmark)
        self.body.append(para)

    def render_keywords(self, block: Block) -> None:
        text = block.text
        marker = "：" if block.level == 1 else ":"
        if marker in text:
            label, _, rest = text.partition(marker)
            label += marker
        else:
            label, rest = "", text
        para = self.para()
        if label:
            para.append(self.run(label, bold=True))
        self.add_inline(para, rest)
        self.body.append(para)

    def render_list(self, block: Block) -> None:
        for index, item in enumerate(block.items, start=1):
            bullet = f"（{index}）" if block.ordered else "·"
            para = self.para(ind={"left": "480", "hanging": "480"})
            if block.ordered:
                para.append(self.run(bullet))
            else:
                para.append(self.run("·\u3000"))
            self.add_inline(para, item)
            self.body.append(para)

    def render_code(self, block: Block) -> None:
        lines = block.text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        for line in lines:
            para = self.para(style="CodeBlock")
            if line:
                para.append(self.run(line.replace("\t", "    "), size=21,
                                     ascii_font="Consolas"))
            self.body.append(para)

    def render_reference(self, block: Block) -> None:
        text = block.text
        para = self.para(style="ReferenceEntry")
        match = re.match(r"(\[\d+\])\s*(.*)", text, re.S)
        if match:
            para.append(self.run(match.group(1)))
            tab = _el(w("r"))
            SubElement(tab, w("tab"))
            para.append(tab)
            self.add_inline(para, match.group(2), mode="plain")
        else:
            self.add_inline(para, text, mode="plain")
        self.body.append(para)

    def render_note(self, block: Block) -> None:
        para = self.para(style="TableText")
        self.add_inline(para, block.text, size=21)
        self.body.append(para)

    def render_equation(self, block: Block) -> None:
        para = self.para(style="Equation", keep_lines=True)
        tab_run = _el(w("r"))
        SubElement(tab_run, w("tab"))
        para.append(tab_run)
        para.append(latex_to_omath(block.latex))
        if block.tag:
            trailer = _el(w("r"))
            SubElement(trailer, w("tab"))
            para.append(trailer)
            tag = block.tag if block.tag.startswith("（") else f"（{block.tag}）"
            para.append(self.run(tag))
        self.body.append(para)

    # -- figures --------------------------------------------------------
    def render_figure(self, block: Block) -> None:
        path = self.resolve_asset(block.src)
        try:
            width_cm, height_cm = image_extent_cm(path)
        except Exception as exc:  # noqa: BLE001
            raise PaperError(f"无法读取图片 {path}: {exc}") from exc
        max_cm = block.width_cm or min(self.max_figure_cm, CONTENT_WIDTH_TWIPS / 1440 * 2.54)
        if width_cm > max_cm:
            height_cm = height_cm * max_cm / width_cm
            width_cm = max_cm
        rid, name = self.add_image(path)
        para = self.para(jc="center", keep_next=True)
        para.append(self._drawing(rid, name, cm_to_emu(width_cm), cm_to_emu(height_cm)))
        self.body.append(para)
        if block.caption:
            cap = self.para(style="FigureCaption")
            self.add_inline(cap, block.caption, size=21)
            self.body.append(cap)
        self.body.append(self.para())

    def _drawing(self, rid: str, name: str, cx: int, cy: int) -> Element:
        self.docpr_id += 1
        drawing = _el(w("drawing"))
        inline = SubElement(drawing, wp("inline"))
        for key in ("distT", "distB"):
            inline.set(key, "0")
        inline.set("distL", "0")
        inline.set("distR", "0")
        extent = SubElement(inline, wp("extent"))
        extent.set("cx", str(cx))
        extent.set("cy", str(cy))
        effect = SubElement(inline, wp("effectExtent"))
        for key in ("l", "t", "r", "b"):
            effect.set(key, "0")
        docpr = SubElement(inline, wp("docPr"))
        docpr.set("id", str(self.docpr_id))
        docpr.set("name", name)
        frame = SubElement(inline, wp("cNvGraphicFramePr"))
        SubElement(frame, a("graphicFrameLocks")).set("noChangeAspect", "1")
        graphic = SubElement(inline, a("graphic"))
        data = SubElement(graphic, a("graphicData"))
        data.set("uri", "http://schemas.openxmlformats.org/drawingml/2006/picture")
        picture = SubElement(data, pic("pic"))
        nv = SubElement(picture, pic("nvPicPr"))
        cnv = SubElement(nv, pic("cNvPr"))
        cnv.set("id", str(self.docpr_id))
        cnv.set("name", name)
        cnvpic = SubElement(nv, pic("cNvPicPr"))
        SubElement(cnvpic, a("picLocks")).set("noChangeAspect", "1")
        fill = SubElement(picture, pic("blipFill"))
        SubElement(fill, a("blip")).set(r("embed"), rid)
        stretch = SubElement(fill, a("stretch"))
        SubElement(stretch, a("fillRect"))
        sppr = SubElement(picture, pic("spPr"))
        xfrm = SubElement(sppr, a("xfrm"))
        off = SubElement(xfrm, a("off"))
        off.set("x", "0")
        off.set("y", "0")
        ext = SubElement(xfrm, a("ext"))
        ext.set("cx", str(cx))
        ext.set("cy", str(cy))
        geom = SubElement(sppr, a("prstGeom"))
        geom.set("prst", "rect")
        SubElement(geom, a("avLst"))
        return drawing

    def _figure_roots(self) -> list[Path]:
        roots = [self.base_dir, self.base_dir.parent]
        for name in ("output", "ouput", "figures", "images", "assets"):
            candidate = self.base_dir / name
            if candidate.is_dir():
                roots.append(candidate)
        return [root for root in roots if root.exists()]

    def resolve_asset(self, src: str) -> Path:
        candidate = Path(src)
        if not candidate.is_absolute():
            candidate = (self.base_dir / src)
        if candidate.exists():
            return candidate
        normalized = Path(str(src).replace("\\", "/"))
        name = normalized.name
        for root in self.figures_root:
            direct = root / name
            if direct.exists():
                return direct
            for dirpath, _dirnames, filenames in os.walk(root):
                if name in filenames:
                    return Path(dirpath) / name
        raise PaperError(f"找不到图片: {src}（已尝试 {self.base_dir} 及同级目录）")

    def add_image(self, path: Path) -> tuple[str, str]:
        data = path.read_bytes()
        digest = hashlib.sha1(data).hexdigest()
        if digest in self.image_cache:
            return self.image_cache[digest]
        ext = path.suffix.lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"
        name = f"image{len(self.image_cache) + 1}.{ext}"
        part = f"word/media/{name}"
        self.pkg.add_image(part, data)
        rid = self.pkg.add_relationship("word/document.xml", REL_TYPES["image"], f"media/{name}")
        self.image_cache[digest] = (rid, name)
        return rid, name

    # -- tables ---------------------------------------------------------
    def render_table(self, block: Block) -> None:
        if block.caption:
            cap = self.para(style="FigureCaption", keep_next=True)
            self.add_inline(cap, block.caption, size=21)
            self.body.append(cap)
        self.body.append(self._table_element(block))
        if block.note:
            note = self.para(style="TableText")
            self.add_inline(note, block.note, size=21)
            self.body.append(note)
        self.body.append(self.para())

    def _table_element(self, block: Block) -> Element:
        columns = len(block.header[0]) if block.header else 0
        columns = max(columns, *(len(row) for row in block.rows), 0) if block.rows else columns
        columns = max(columns, 1)
        table = _el(w("tbl"))
        tblpr = SubElement(table, w("tblPr"))
        width = SubElement(tblpr, w("tblW"))
        width.set(w("w"), "5000")
        width.set(w("type"), "pct")
        SubElement(tblpr, w("jc")).set(w("val"), "center")
        borders = SubElement(tblpr, w("tblBorders"))
        self._border(borders, "top", "single", 12)
        self._border(borders, "left", "none", 0)
        self._border(borders, "bottom", "single", 12)
        self._border(borders, "right", "none", 0)
        self._border(borders, "insideH", "none", 0)
        self._border(borders, "insideV", "none", 0)
        layout = SubElement(tblpr, w("tblLayout"))
        layout.set(w("type"), "autofit")
        cellmar = SubElement(tblpr, w("tblCellMar"))
        for side, value in (("top", 0), ("left", 108), ("bottom", 0), ("right", 108)):
            SubElement(cellmar, w(side)).set(w("w"), str(value))
            cellmar[-1].set(w("type"), "dxa")

        widths = self._column_widths(block, columns)
        grid = SubElement(table, w("tblGrid"))
        for value in widths:
            SubElement(grid, w("gridCol")).set(w("w"), str(value))

        rows: list[tuple[list[str], bool]] = []
        if block.header:
            rows.append((block.header[0], True))
            rows.extend((row, False) for row in block.rows)
        else:
            rows.extend((row, False) for row in block.rows)

        for row, is_header in rows:
            table.append(self._table_row(row, is_header, widths))
        return table

    @staticmethod
    def _border(parent: Element, side: str, val: str, size: int) -> None:
        border = SubElement(parent, w(side))
        border.set(w("val"), val)
        border.set(w("sz"), str(size))
        border.set(w("space"), "0")
        border.set(w("color"), "000000" if val != "none" else "auto")

    @staticmethod
    def _column_widths(block: Block, columns: int) -> list[int]:
        weights = [1.0] * columns
        for row in ([block.header[0]] if block.header else []) + block.rows:
            for index, cell in enumerate(row[:columns]):
                text = re.sub(r"\$[^$]*\$|\*\*|`", "", str(cell))
                width = sum(2.0 if ord(ch) > 0x2E80 else 1.0 for ch in text)
                weights[index] = max(weights[index], min(width, 42))
        total = sum(weights) or columns
        widths = [max(600, int(CONTENT_WIDTH_TWIPS * weight / total)) for weight in weights]
        scale = CONTENT_WIDTH_TWIPS / sum(widths)
        return [int(width * scale) for width in widths]

    def _table_row(self, row: list[str], header: bool, widths: list[int]) -> Element:
        tr = _el(w("tr"))
        trpr = SubElement(tr, w("trPr"))
        SubElement(trpr, w("cantSplit"))
        if header:
            SubElement(trpr, w("tblHeader"))
        for index, cell_text in enumerate(row):
            tc = SubElement(tr, w("tc"))
            tcpr = SubElement(tc, w("tcPr"))
            tcw = SubElement(tcpr, w("tcW"))
            tcw.set(w("w"), str(widths[index] if index < len(widths) else 1000))
            tcw.set(w("type"), "dxa")
            if header:
                tcb = SubElement(tcpr, w("tcBorders"))
                self._border(tcb, "bottom", "single", 6)
                SubElement(tcpr, w("vAlign")).set(w("val"), "center")
            para = _el(w("p"))
            ppr = SubElement(para, w("pPr"))
            SubElement(ppr, w("pStyle")).set(w("val"), "TableText")
            SubElement(ppr, w("keepNext"))
            SubElement(ppr, w("jc")).set(w("val"), "center")
            self.add_inline(para, cell_text, size=21)
            tc.append(para)
        return tr

    # ------------------------------------------------------------------
    # cover
    # ------------------------------------------------------------------
    def render_cover(self) -> None:
        for block in self.plan.cover:
            if block.kind == "cover_image":
                if block.src:
                    self._cover_emblem(block.src)
                elif block.text:
                    para = self.para(style="CoverLine")
                    para.append(self.run(block.text, bold=True, size=44, east="黑体"))
                    self.body.append(para)
                for _ in range(2):
                    self.body.append(self.para(style="CoverLine"))
            elif block.kind == "cover_line":
                self.body.append(self.para(style="CoverLine"))
                self.body.append(self.para(style="CoverLine"))
            elif block.kind == "cover_course":
                para = self.para(style="CoverLine")
                para.append(self.run(block.text, size=44))
                self.body.append(para)
            elif block.kind == "cover_title":
                para = self.para(style="CoverLine")
                para.append(self.run(block.text, bold=True, size=44, east="黑体"))
                self.body.append(para)
            elif block.kind == "cover_table":
                self.body.append(self._cover_table(block.rows))

    def _cover_emblem(self, src: str) -> None:
        path = self.resolve_asset(src)
        width_cm, height_cm = image_extent_cm(path)
        max_cm = 8.0
        if width_cm > max_cm:
            height_cm = height_cm * max_cm / width_cm
            width_cm = max_cm
        rid, name = self.add_image(path)
        para = self.para(style="CoverLine")
        para.append(self._drawing(rid, name, cm_to_emu(width_cm), cm_to_emu(height_cm)))
        self.body.append(para)

    def _cover_table(self, rows: list[list[str]]) -> Element:
        table = _el(w("tbl"))
        tblpr = SubElement(table, w("tblPr"))
        width = SubElement(tblpr, w("tblW"))
        width.set(w("w"), str(5638))
        width.set(w("type"), "dxa")
        SubElement(tblpr, w("jc")).set(w("val"), "center")
        layout = SubElement(tblpr, w("tblLayout"))
        layout.set(w("type"), "fixed")
        borders = SubElement(tblpr, w("tblBorders"))
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            self._border(borders, side, "none", 0)
        cellmar = SubElement(tblpr, w("tblCellMar"))
        for side, value in (("top", 0), ("left", 108), ("bottom", 0), ("right", 108)):
            SubElement(cellmar, w(side)).set(w("w"), str(value))
            cellmar[-1].set(w("type"), "dxa")
        grid = SubElement(table, w("tblGrid"))
        for value in (1738, 3900):
            SubElement(grid, w("gridCol")).set(w("w"), str(value))
        for label, value in rows:
            tr = _el(w("tr"))
            trpr = SubElement(tr, w("trPr"))
            SubElement(trpr, w("cantSplit"))
            height = SubElement(trpr, w("trHeight"))
            height.set(w("val"), "524")
            height.set(w("hRule"), "atLeast")
            for index, (text, is_label) in enumerate(((label, True), (value, False))):
                tc = SubElement(tr, w("tc"))
                tcpr = SubElement(tc, w("tcPr"))
                tcw = SubElement(tcpr, w("tcW"))
                tcw.set(w("w"), str(1738 if index == 0 else 3900))
                tcw.set(w("type"), "dxa")
                tcb = SubElement(tcpr, w("tcBorders"))
                for side in ("top", "left", "right"):
                    self._border(tcb, side, "nil", 0)
                if is_label:
                    self._border(tcb, "bottom", "nil", 0)
                else:
                    self._border(tcb, "bottom", "single", 4)
                SubElement(tcpr, w("vAlign")).set(w("val"), "bottom")
                para = _el(w("p"))
                ppr = SubElement(para, w("pPr"))
                SubElement(ppr, w("keepNext"))
                SubElement(ppr, w("spacing")).set(w("line"), "240")
                ppr.find(w("spacing")).set(w("lineRule"), "auto")
                SubElement(ppr, w("jc")).set(w("val"), "center")
                text_value = text
                if is_label and not text_value.endswith("："):
                    text_value = _pad_label(text_value) + "："
                para.append(self.run(text_value, bold=is_label, size=28))
                tc.append(para)
            table.append(tr)
        return table

    # ------------------------------------------------------------------
    # front matter / sections
    # ------------------------------------------------------------------
    def render_toc(self, entries: Sequence[tuple[int, str, str]], title: str,
                   depth: int) -> None:
        para = self.para(style="Heading1", outline=9)
        para.append(self.run(title))
        self.body.append(para)

        levels = [entry for entry in entries if entry[0] <= depth]
        if not levels:
            para = self.para(style="TOC1")
            self._field(para, 'TOC \\o "1-%d" \\h \\u' % depth, "")
            self.body.append(para)
            return
        for index, (level, text, bookmark) in enumerate(levels):
            para = self.para(style=f"TOC{min(level, 3)}")
            if index == 0:
                self._field_start(para, 'TOC \\o "1-%d" \\h \\u' % depth)
            self._toc_hyperlink(para, text, bookmark)
            if index == len(levels) - 1:
                end = _el(w("r"))
                SubElement(end, w("fldChar")).set(w("fldCharType"), "end")
                para.append(end)
            self.body.append(para)

    def _field_start(self, para: Element, instr: str) -> None:
        for kind, text in (("begin", None), ("instr", instr), ("separate", None)):
            run = _el(w("r"))
            if kind == "instr":
                el = SubElement(run, w("instrText"))
                el.text = " " + text + " "
                el.set(xml_space(), "preserve")
            else:
                SubElement(run, w("fldChar")).set(w("fldCharType"), kind)
            para.append(run)

    def _toc_hyperlink(self, para: Element, text: str, bookmark: str) -> None:
        for kind, instruction in (("begin", None), ("instr", f" HYPERLINK \\l {bookmark} "), ("separate", None)):
            run = _el(w("r"))
            if kind == "instr":
                el = SubElement(run, w("instrText"))
                el.text = instruction
                el.set(xml_space(), "preserve")
            else:
                SubElement(run, w("fldChar")).set(w("fldCharType"), kind)
            para.append(run)
        para.append(self.run(text))
        tab = _el(w("r"))
        SubElement(tab, w("tab"))
        para.append(tab)
        self._field(para, f" PAGEREF {bookmark} \\h ", "1")
        end = _el(w("r"))
        SubElement(end, w("fldChar")).set(w("fldCharType"), "end")
        para.append(end)

    def section_break(self, *, header_rel: str | None, footer_rel: str | None,
                      number_format: str, start: int) -> Element:
        sect = _el(w("sectPr"))
        if header_rel:
            ref = SubElement(sect, w("headerReference"))
            ref.set(w("type"), "default")
            ref.set(r("id"), header_rel)
        if footer_rel:
            ref = SubElement(sect, w("footerReference"))
            ref.set(w("type"), "default")
            ref.set(r("id"), footer_rel)
        self._page_setup(sect, number_format, start)
        para = _el(w("p"))
        ppr = SubElement(para, w("pPr"))
        ppr.append(sect)
        return para

    def final_section(self, number_format: str, start: int) -> Element:
        sect = _el(w("sectPr"))
        for kind, rid in (("headerReference", self.header_rel), ("footerReference", self.footer_rel)):
            ref = SubElement(sect, w(kind))
            ref.set(w("type"), "default")
            ref.set(r("id"), rid)
        self._page_setup(sect, number_format, start)
        return sect

    @staticmethod
    def _page_setup(sect: Element, number_format: str, start: int) -> None:
        pgsz = SubElement(sect, w("pgSz"))
        pgsz.set(w("w"), str(PAGE_WIDTH_TWIPS))
        pgsz.set(w("h"), str(PAGE_HEIGHT_TWIPS))
        pgmar = SubElement(sect, w("pgMar"))
        for key, value in (("top", MARGIN_TWIPS), ("right", MARGIN_TWIPS),
                           ("bottom", MARGIN_TWIPS), ("left", MARGIN_TWIPS),
                           ("header", 851), ("footer", 992), ("gutter", 284)):
            pgmar.set(w(key), str(value))
        ab = SubElement(sect, w("pgBorders"))
        ab.set(w("offsetFrom"), "text")
        for side in ("top", "left", "bottom", "right"):
            border = SubElement(ab, w(side))
            border.set(w("val"), "none")
            border.set(w("sz"), "0")
            border.set(w("space"), "0")
            border.set(w("color"), "auto")
        pg = SubElement(sect, w("pgNumType"))
        pg.set(w("fmt"), number_format)
        pg.set(w("start"), str(start))
        cols = SubElement(sect, w("cols"))
        cols.set(w("space"), "720")
        cols.set(w("num"), "1")
        grid = SubElement(sect, w("docGrid"))
        grid.set(w("linePitch"), "312")
        grid.set(w("charSpace"), "0")

    # ------------------------------------------------------------------
    # assembly
    # ------------------------------------------------------------------
    def build(self) -> Package:
        self.setup_parts()
        plan = self.plan
        if plan.cover:
            self.render_cover()
            # the cover gets its own section so that a copied template header
            # (school logo) cannot leak onto the table-of-contents pages
            self.body.append(self.section_break(header_rel=self.empty_header_rel,
                                                footer_rel=self.empty_footer_rel,
                                                number_format="upperRoman", start=1))
        toc_conf = self.options.get("toc") or {}
        if toc_conf.get("enabled", True):
            self.render_toc(plan.toc_entries, toc_conf.get("title", "目    录"),
                            int(toc_conf.get("depth", 3)))
        self.body.append(self.section_break(header_rel=self.empty_header_rel,
                                            footer_rel=self.empty_footer_rel,
                                            number_format="upperRoman", start=1))
        abstract_heading = None
        for block in plan.abstract:
            if block.kind == "heading":
                english = block.text.strip().lower().startswith("abstract")
                self.render_special_heading(block.text, block.bookmark, english=english)
            else:
                self._render_block_single(block)
        self.body.append(self.section_break(header_rel=self.header_rel,
                                            footer_rel=self.footer_rel,
                                            number_format="upperRoman", start=1))
        self.render_blocks(plan.body)
        if plan.references:
            for block in plan.references:
                if block.kind == "heading":
                    self.render_special_heading(block.text, block.bookmark)
                else:
                    self._render_block_single(block)
        if plan.appendix:
            for block in plan.appendix:
                if block.kind == "heading":
                    if block.level == 1:
                        self.render_special_heading(block.text, block.bookmark)
                    else:
                        self.render_heading(block)
                else:
                    self._render_block_single(block)
        self.body.append(self.final_section("decimal", start=1))
        self.pkg.add_part("word/document.xml", self._serialize(self.doc))
        return self.pkg

    def _render_block_single(self, block: Block) -> None:
        self.render_blocks([block])


def _clone(element: Element) -> Element:
    from copy import deepcopy

    return deepcopy(element)


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _pad_label(label: str) -> str:
    """Insert the four-character spacing used by template cover labels."""
    label = label.strip()
    compact = label.replace(" ", "")
    if len(compact) == 2:
        return compact[0] + "    " + compact[1]
    if len(compact) == 3:
        return compact[0] + "  " + compact[1] + "  " + compact[2]
    return compact


def build_docx(paper_plan: Plan, out_path: str | Path, base_dir: Path,
               options: dict | None = None) -> Path:
    builder = DocumentBuilder(paper_plan, base_dir, options)
    package = builder.build()
    return package.save(out_path)
