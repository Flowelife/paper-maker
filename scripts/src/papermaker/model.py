"""Paper JSON model: validation, inline markup parsing and numbering."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

CN_DIGITS = "一二三四五六七八九十"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class PaperError(Exception):
    """Raised for malformed paper documents (JSON or Markdown)."""


# --------------------------------------------------------------------------
# inline markup
# --------------------------------------------------------------------------
_TOKEN = re.compile(
    r"(\$[^$]+\$)"           # inline math
    r"|(\*\*.+?\*\*)"        # bold
    r"|(`[^`]+`)"            # inline code
    r"|(\[\d+(?:\s*[-,–，]\s*\d+)*\])"  # citation marker
)


@dataclass
class Segment:
    kind: str            # text | math | sup | ref
    text: str = ""
    latex: str = ""
    bold: bool = False
    italic: bool = False


def parse_inline(text: str) -> list[Segment]:
    """Split a paragraph into text / math / superscript-citation segments."""
    segments: list[Segment] = []
    pos = 0
    for match in _TOKEN.finditer(text):
        if match.start() > pos:
            segments.append(Segment("text", text[pos:match.start()]))
        token = match.group(0)
        if match.group(1):
            segments.append(Segment("math", latex=token[1:-1]))
        elif match.group(2):
            inner = parse_inline(token[2:-2])
            for seg in inner:
                seg.bold = True
                segments.append(seg)
        elif match.group(3):
            segments.append(Segment("text", token[1:-1]))
        else:
            segments.append(Segment("sup", token))
        pos = match.end()
    if pos < len(text):
        segments.append(Segment("text", text[pos:]))
    return segments


def plain_text(text: str) -> str:
    """Strip inline markup, used for bookmarks and diagnostics."""
    return "".join(
        seg.text if seg.kind != "math" else "$" + seg.latex + "$"
        for seg in parse_inline(text)
    )


# --------------------------------------------------------------------------
# block plan
# --------------------------------------------------------------------------
@dataclass
class Block:
    kind: str
    text: str = ""
    level: int = 0
    bookmark: str | None = None
    caption: str = ""
    src: str = ""
    width_cm: float | None = None
    header: list[list[str]] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    note: str = ""
    latex: str = ""
    tag: str = ""
    items: list[str] = field(default_factory=list)
    ordered: bool = False
    language: str = ""
    bold: bool = False


@dataclass
class Plan:
    cover: list[Block]
    toc_entries: list[tuple[int, str, str]]
    abstract: list[Block]
    body: list[Block]
    references: list[Block]
    appendix: list[Block]
    meta: dict[str, Any]


def _as_list(value: Any, what: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PaperError(f"{what} 应为数组，实际为 {type(value).__name__}")
    return value


def _require_str(value: Any, what: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PaperError(f"{what} 应为字符串，实际为 {type(value).__name__}")
    return value


# --------------------------------------------------------------------------
# numbering helpers
# --------------------------------------------------------------------------
RE_CHAPTER = re.compile(r"^第\s*([0-9一二三四五六七八九十百]+)\s*章[\s　]*")
RE_SECTION = re.compile(r"^\d+(?:\.\d+)*[\s　]+")
RE_H4 = re.compile(r"^[（(]\s*[一二三四五六七八九十]+\s*[）)][\s　]*")
RE_APPX = re.compile(r"^附\s*录\s*([A-Za-z])\s*[、.．]?\s*")
RE_APPX_NUM = re.compile(r"^([A-Za-z])\.(\d+)[\s　]+")


def cn_number(value: int) -> str:
    if value <= 10:
        return CN_DIGITS[value - 1]
    if value < 20:
        return "十" + CN_DIGITS[value - 11]
    tens, ones = divmod(value, 10)
    return CN_DIGITS[tens - 1] + "十" + (CN_DIGITS[ones - 1] if ones else "")


def cn_to_int(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    mapping = {ch: idx + 1 for idx, ch in enumerate(CN_DIGITS)}
    if not text or any(ch not in mapping for ch in text):
        return None
    if text == "十":
        return 10
    if len(text) == 1:
        return mapping[text]
    if text.startswith("十"):
        return 10 + mapping[text[1]]
    if "十" in text:
        head, _, tail = text.partition("十")
        return mapping[head] * 10 + (mapping[tail] if tail else 0)
    return None


class Numberer:
    def __init__(self, chapter_style: str = "arabic") -> None:
        self.chapter_style = chapter_style
        self.chapter = 0
        self.section = 0
        self.subsection = 0
        self.h4 = 0
        self.figure = 0
        self.table = 0
        self.equation = 0
        self.letter_index = 0

    # body ---------------------------------------------------------------
    def heading(self, level: int, raw: str) -> str:
        text = raw.strip()
        if level == 1:
            match = RE_CHAPTER.match(text)
            self.chapter = (cn_to_int(match.group(1)) if match else None) or self.chapter + 1
            if match:
                text = text[match.end():]
            self.section = self.subsection = self.h4 = 0
            self.figure = self.table = self.equation = 0
            number = cn_number(self.chapter) if self.chapter_style == "chinese" else self.chapter
            return f"第{number}章  {text.strip()}"
        if level == 2:
            self.section += 1
            self.subsection = self.h4 = 0
            text = RE_SECTION.sub("", text)
            return f"{self.chapter}.{self.section}  {text.strip()}"
        if level == 3:
            self.subsection += 1
            self.h4 = 0
            text = RE_SECTION.sub("", text)
            return f"{self.chapter}.{self.section}.{self.subsection}  {text.strip()}"
        self.h4 += 1
        text = RE_H4.sub("", text)
        return f"（{cn_number(self.h4)}）{text.strip()}"

    # appendix -----------------------------------------------------------
    def appendix_heading(self, level: int, raw: str) -> str:
        text = raw.strip()
        if level == 2:
            match = RE_APPX.match(text)
            if match:
                letter = match.group(1).upper()
                self.letter_index = LETTERS.index(letter) + 1
                text = text[match.end():]
            else:
                self.letter_index += 1
                letter = LETTERS[self.letter_index - 1]
            self.section = self.subsection = self.h4 = 0
            self.figure = self.table = self.equation = 0
            return f"附录{letter}  {text.strip()}"
        if level == 3:
            self.subsection += 1
            number = RE_APPX_NUM.sub("", text)
            letter = LETTERS[self.letter_index - 1] if self.letter_index else "A"
            return f"{letter}.{self.subsection}  {number.strip()}"
        if level == 4:
            self.h4 += 1
            text = RE_H4.sub("", text)
            return f"（{cn_number(self.h4)}）{text.strip()}"
        return f"第{self.chapter}章  {text}"

    def caption(self, kind: str, raw: str) -> str:
        prefix = "图" if kind == "figure" else "表"
        if kind == "figure":
            self.figure += 1
            number = self.figure
        else:
            self.table += 1
            number = self.table
        label = f"{prefix}{self.chapter}-{number}" if self.chapter else f"{prefix}{number}"
        text = raw.strip()
        text = re.sub(r"^(图|表)\s*[0-9A-Za-z]+[-–—][0-9]+[\s　]*", "", text)
        text = re.sub(r"^(图|表)[\s　]+", "", text)
        return f"{label}  {text}" if text else label

    def appendix_caption(self, kind: str, raw: str) -> str:
        prefix = "图" if kind == "figure" else "表"
        if kind == "figure":
            self.figure += 1
            number = self.figure
        else:
            self.table += 1
            number = self.table
        letter = LETTERS[self.letter_index - 1] if self.letter_index else "A"
        label = f"{prefix}{letter}-{number}"
        text = re.sub(r"^(图|表)\s*[0-9A-Za-z]+[-–—][0-9]+[\s　]*", "", raw.strip())
        text = re.sub(r"^(图|表)[\s　]+", "", text)
        return f"{label}  {text}" if text else label

    def equation_tag(self, explicit: str) -> str:
        self.equation += 1
        if explicit.strip():
            return explicit.strip()
        return f"{self.chapter}-{self.equation}" if self.chapter else str(self.equation)


# --------------------------------------------------------------------------
# plan construction
# --------------------------------------------------------------------------
def _table_block(raw: dict, ctx: str) -> Block:
    header = raw.get("header") or []
    rows = raw.get("rows") or []
    if not isinstance(header, list) or not isinstance(rows, list):
        raise PaperError(f"{ctx}: table.header/rows 应为二维数组")
    return Block(
        kind="table",
        caption=_require_str(raw.get("caption"), f"{ctx}.caption"),
        header=[[_require_str(cell, ctx) for cell in row] for row in header],
        rows=[[_require_str(cell, ctx) for cell in row] for row in rows],
        note=_require_str(raw.get("note"), f"{ctx}.note"),
        width_cm=raw.get("width_cm"),
    )


def _figure_block(raw: dict, ctx: str) -> Block:
    src = _require_str(raw.get("src"), f"{ctx}.src")
    if not src:
        raise PaperError(f"{ctx}: figure 缺少 src")
    width = raw.get("width_cm")
    return Block(
        kind="figure",
        src=src,
        caption=_require_str(raw.get("caption"), f"{ctx}.caption"),
        width_cm=float(width) if width else None,
    )


def _blocks(raw_blocks: Iterable[Any], numberer: Numberer, ctx: str,
            appendix: bool = False, bookmarks: list | None = None) -> list[Block]:
    blocks: list[Block] = []
    for index, raw in enumerate(raw_blocks):
        where = f"{ctx}[{index}]"
        if not isinstance(raw, dict):
            raise PaperError(f"{where}: 块应为对象")
        kind = raw.get("type") or ("paragraph" if "text" in raw else "")
        if kind in ("heading", "h"):
            level = int(raw.get("level") or 1)
            title = _require_str(raw.get("text") or raw.get("title"), f"{where}.text")
            if level == 1 and appendix:
                text = title
            elif appendix:
                text = numberer.appendix_heading(level, title)
            else:
                text = numberer.heading(level, title)
            bookmark = None
            if level <= 3 and bookmarks is not None:
                bookmark = f"_Toc{900000 + len(bookmarks)}"
                bookmarks.append((level, text, bookmark))
            blocks.append(Block(kind="heading", level=level, text=text,
                                bookmark=bookmark, bold=bool(raw.get("bold"))))
        elif kind == "paragraph":
            blocks.append(Block(kind="paragraph",
                                text=_require_str(raw.get("text"), f"{where}.text")))
        elif kind == "figure":
            block = _figure_block(raw, where)
            block.caption = (numberer.appendix_caption("figure", block.caption)
                             if appendix else numberer.caption("figure", block.caption))
            blocks.append(block)
        elif kind == "table":
            block = _table_block(raw, where)
            block.caption = (numberer.appendix_caption("table", block.caption)
                             if appendix else numberer.caption("table", block.caption))
            blocks.append(block)
        elif kind == "equation":
            latex = _require_str(raw.get("latex") or raw.get("text"), f"{where}.latex")
            tag = _require_str(raw.get("tag"), f"{where}.tag")
            from .omml import extract_tag

            latex, inline_tag = extract_tag(latex)
            tag = tag or inline_tag or ""
            blocks.append(Block(kind="equation", latex=latex,
                                tag=numberer.equation_tag(tag)))
        elif kind == "list":
            blocks.append(Block(kind="list",
                                items=[_require_str(i, f"{where}.items") for i in
                                       _as_list(raw.get("items"), f"{where}.items")],
                                ordered=bool(raw.get("ordered"))))
        elif kind == "code":
            blocks.append(Block(kind="code",
                                text=_require_str(raw.get("text"), f"{where}.text"),
                                language=_require_str(raw.get("language"), f"{where}.language")))
        elif kind == "note":
            blocks.append(Block(kind="note", text=_require_str(raw.get("text"), f"{where}.text")))
        elif kind == "pagebreak":
            blocks.append(Block(kind="pagebreak"))
        elif kind == "empty":
            blocks.append(Block(kind="empty"))
        else:
            raise PaperError(f"{where}: 未知块类型 {kind!r}")
    return blocks


def _cover_blocks(paper: dict) -> list[Block]:
    cover = paper.get("cover") or {}
    if not isinstance(cover, dict):
        raise PaperError("cover 应为对象")
    mode = str(cover.get("mode") or "template").lower()
    if mode == "none":
        return []
    if mode in ("copy", "template"):
        # the page and its section break are reserved here; the cover content
        # itself is imported from a template/copy source after the build
        return [Block(kind="empty")]
    meta = paper.get("meta") or {}
    blocks: list[Block] = []
    blocks.append(Block(kind="cover_image", src=_require_str(cover.get("emblem"), "cover.emblem"),
                        text=_require_str(cover.get("school_name"), "cover.school_name")))
    blocks.append(Block(kind="cover_line", text="", level=2))
    blocks.append(Block(kind="cover_course",
                        text=_require_str(cover.get("course_line") or
                                          f"《{meta.get('course', '')}》", "cover.course_line")))
    blocks.append(Block(kind="cover_line", text="", level=2))
    blocks.append(Block(kind="cover_title",
                        text=_require_str(cover.get("title") or meta.get("title", ""), "cover.title")))
    blocks.append(Block(kind="cover_line", text="", level=2))
    rows = cover.get("rows")
    if rows is None:
        rows = [
            ["学    号", meta.get("student_id", "")],
            ["姓    名", meta.get("author", "")],
            ["年    级", meta.get("grade", "")],
            ["院    别", meta.get("college", "")],
            ["专    业", meta.get("major", "")],
            ["指导教师", meta.get("advisor", "")],
            ["完成日期", meta.get("date", "")],
        ]
    clean_rows = []
    for row in _as_list(rows, "cover.rows"):
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            raise PaperError("cover.rows 每行应为 [标签, 值]")
        clean_rows.append([_require_str(row[0], "cover.rows"), _require_str(row[1], "cover.rows")])
    blocks.append(Block(kind="cover_table", rows=clean_rows))
    return blocks


def build_plan(paper: dict) -> Plan:
    if not isinstance(paper, dict):
        raise PaperError("论文 JSON 根节点应为对象")
    meta = paper.get("meta") or {}
    if not isinstance(meta, dict):
        raise PaperError("meta 应为对象")

    bookmarks: list[tuple[int, str, str]] = []
    abstract_blocks: list[Block] = []
    toc_entries: list[tuple[int, str, str]] = []

    front = paper.get("abstract") or {}
    special_level1: list[tuple[str, str]] = []

    def add_heading(level: int, text: str) -> str:
        bookmark = f"_Toc{900000 + len(toc_entries)}"
        toc_entries.append((level, text, bookmark))
        return bookmark

    for key, default_heading, label in (("zh", "摘要", "摘要"), ("en", "Abstract", "Abstract")):
        section = front.get(key) if isinstance(front, dict) else None
        if not section:
            continue
        heading = _require_str(section.get("heading") or default_heading, f"abstract.{key}.heading")
        if key == "zh":
            heading = "摘    要"
        bookmark = add_heading(1, heading)
        abstract_blocks.append(Block(kind="heading", level=1, text=heading, bookmark=bookmark))
        paragraphs = _as_list(section.get("paragraphs"), f"abstract.{key}.paragraphs")
        for para in paragraphs:
            abstract_blocks.append(Block(kind="paragraph", text=_require_str(para, f"abstract.{key}")))
        if not paragraphs and section.get("text"):
            abstract_blocks.append(Block(kind="paragraph",
                                         text=_require_str(section.get("text"), f"abstract.{key}.text")))
        keywords = _as_list(section.get("keywords"), f"abstract.{key}.keywords")
        if keywords:
            for _ in range(2):
                abstract_blocks.append(Block(kind="empty"))
            separator = "；" if key == "zh" else "; "
            label_text = _require_str(section.get("keyword_label"),
                                      f"abstract.{key}.keyword_label") or ("关键词：" if key == "zh" else "Keywords:")
            words = [_require_str(k, f"abstract.{key}.keywords") for k in keywords]
            if key == "en":
                words = [w[:1].upper() + w[1:] for w in words]
                text = label_text.rstrip() + " " + separator.join(words)
            else:
                text = label_text + separator.join(words)
            abstract_blocks.append(Block(kind="keywords", text=text,
                                         level=1 if key == "zh" else 2))

    numbering = paper.get("numbering") or {}
    chapter_style = str(numbering.get("chapter") or "arabic").lower()
    body_numberer = Numberer(chapter_style)
    body = _blocks(_as_list(paper.get("body"), "body"), body_numberer, "body",
                   bookmarks=bookmarks, appendix=False)

    references_block: list[Block] = []
    refs = paper.get("references")
    if refs:
        heading = _require_str(refs.get("heading") or "参考文献", "references.heading") or "参考文献"
        bookmark = add_heading(1, heading)
        references_block.append(Block(kind="heading", level=1, text=heading, bookmark=bookmark))
        items = _as_list(refs.get("items"), "references.items")
        for index, item in enumerate(items, start=1):
            text = _require_str(item, "references.items")
            if not re.match(r"^\[\d+\]", text.strip()):
                text = f"[{index}] {text}"
            references_block.append(Block(kind="reference", text=text))

    appendix_blocks: list[Block] = []
    appendix = paper.get("appendix")
    if appendix:
        heading = _require_str(appendix.get("heading") or "附录", "appendix.heading") or "附录"
        heading = "附    录"
        bookmark = add_heading(1, heading)
        appendix_blocks.append(Block(kind="heading", level=1, text=heading, bookmark=bookmark))
        appx_numberer = Numberer()
        appendix_blocks.extend(_blocks(_as_list(appendix.get("blocks"), "appendix.blocks"),
                                       appx_numberer, "appendix",
                                       bookmarks=bookmarks, appendix=True))

    cover = _cover_blocks(paper)
    return Plan(cover=cover, toc_entries=toc_entries, abstract=abstract_blocks,
                body=body, references=references_block, appendix=appendix_blocks, meta=meta)


def load_json(path: str | Path) -> dict:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PaperError(f"找不到文件: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PaperError(f"JSON 解析失败 {path}:{exc.lineno}:{exc.colno} {exc.msg}") from exc
    return data
