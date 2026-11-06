"""Convert a Markdown paper draft into the paper-maker JSON model."""

from __future__ import annotations

import json
import re
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
CAPTION_RE = re.compile(r"^(图|表)\s*[0-9A-Za-z]+(?:[-–—][0-9]+)?[\s　]")
TABLE_SEP_RE = re.compile(r"^\|?[\s:|-]*-[\s:|-]*\|?$")
KEYWORDS_RE = re.compile(r"^\*\*\s*(关键词|Keywords|关键字)\s*\*\*\s*[:：]\s*(.*)$", re.I)
REFERENCE_RE = re.compile(r"^\[\d+\]")
SPECIAL = {"摘要": "zh", "abstract": "en", "目录": "toc", "封面信息": "cover",
           "参考文献": "refs", "附录": "appendix"}


def _compact(text: str) -> str:
    return re.sub(r"[\s　]+", "", text)


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells: list[str] = []
    current: list[str] = []
    in_math = False
    idx = 0
    while idx < len(line):
        ch = line[idx]
        if ch == "\\" and idx + 1 < len(line) and line[idx + 1] == "|":
            current.append("|")
            idx += 2
            continue
        if ch == "$":
            in_math = not in_math
        if ch == "|" and not in_math:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        idx += 1
    cells.append("".join(current).strip())
    return cells


def _join_lines(lines: list[str]) -> str:
    result = ""
    for line in lines:
        text = line.strip()
        if not text:
            continue
        if not result:
            result = text
            continue
        if _is_ascii_word(result[-1]) and _is_ascii_word(text[0]):
            result += " " + text
        else:
            result += text
    return result


def _is_ascii_word(ch: str) -> bool:
    return ch.isascii() and (ch.isalnum() or ch in ".,;:)]}\"'")


class MarkdownImporter:
    def __init__(self, text: str) -> None:
        self.lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        self.index = 0
        self.paper: dict = {
            "schema": "paper-maker/1",
            "meta": {},
            "cover": {},
            "abstract": {},
            "toc": {"enabled": True, "title": "目    录", "depth": 3},
            "body": [],
            "references": None,
            "appendix": None,
        }
        self.state = "front"
        self.target: list[dict] | None = None
        self.seen_body = False
        self.pending_heading_title: str | None = None

    # -- helpers -------------------------------------------------------
    def _emit(self, block: dict) -> None:
        if self.target is None:
            return
        if self.state == "abstract":
            self.target.append(str(block.get("text", "")))
            return
        self.target.append(block)

    def _ensure_body(self) -> list[dict]:
        if self.state == "appendix":
            if self.paper["appendix"] is None:
                self.paper["appendix"] = {"heading": "附录", "blocks": []}
            return self.paper["appendix"]["blocks"]
        self.paper["body"] = self.paper["body"] or []
        return self.paper["body"]

    # -- main ----------------------------------------------------------
    def convert(self) -> dict:
        while self.index < len(self.lines):
            line = self.lines[self.index]
            stripped = line.strip()
            if not stripped:
                self.index += 1
                continue
            if stripped.startswith("```"):
                self._parse_code()
                continue
            if stripped.startswith("$$"):
                self._parse_equation()
                continue
            if stripped.startswith("|") and self._is_table_start(self.index):
                self._parse_table()
                continue
            match = HEADING_RE.match(stripped)
            if match:
                self._parse_heading(len(match.group(1)), match.group(2).strip())
                continue
            if IMAGE_RE.match(stripped):
                self._parse_image(stripped)
                continue
            if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
                self.index += 1
                continue
            if LIST_RE.match(line):
                self._parse_list()
                continue
            if stripped.startswith(">"):
                self._parse_quote()
                continue
            self._parse_paragraph()
        self._postprocess()
        return self.paper

    # -- block parsers -------------------------------------------------
    def _parse_heading(self, level: int, text: str) -> None:
        compact = _compact(text)
        key = compact.lower()
        self.index += 1
        if key in SPECIAL:
            kind = SPECIAL[key]
            if kind == "zh":
                section = self.paper["abstract"].setdefault("zh", {"heading": "摘要",
                                                                   "paragraphs": []})
                self.target = section["paragraphs"]
                self.state = "abstract"
            elif kind == "en":
                section = self.paper["abstract"].setdefault("en", {"heading": "Abstract",
                                                                   "paragraphs": []})
                self.target = section["paragraphs"]
                self.state = "abstract"
            elif kind == "cover":
                self.target = None
                self.state = "cover"
            elif kind == "toc":
                self.target = None
                self.state = "toc"
            elif kind == "refs":
                self.paper["references"] = self.paper.get("references") or {
                    "heading": "参考文献", "items": []}
                self.target = None
                self.state = "refs"
            else:
                self.paper["appendix"] = self.paper.get("appendix") or {
                    "heading": "附录", "blocks": []}
                self.target = self.paper["appendix"]["blocks"]
                self.state = "appendix"
            return
        if self.state == "cover":
            self.state = "front"
        if level == 1 and not self.seen_body and not re.match(r"^第\s*\S+\s*章", text):
            # document title (front page), not a chapter
            self.paper["meta"].setdefault("title", text.strip())
            self.target = None
            return
        if self.state in ("abstract", "toc"):
            self.state = "front"
        if self.state == "refs" and not compact.startswith("附录"):
            self.state = "front"
        blocks = self._ensure_body()
        self.target = blocks
        if level == 1:
            self.seen_body = True
        blocks.append({"type": "heading", "level": min(level, 4), "text": text})

    def _parse_paragraph(self) -> None:
        collected: list[str] = []
        while self.index < len(self.lines):
            line = self.lines[self.index]
            stripped = line.strip()
            if not stripped:
                break
            if self._is_structural(stripped, self.index):
                break
            collected.append(line)
            self.index += 1
        if not collected:
            self.index += 1
            return
        text = _join_lines(collected)
        keywords = KEYWORDS_RE.match(text)
        if keywords:
            label, rest = keywords.group(1), keywords.group(2)
            words = [w.strip() for w in re.split(r"[；;]", rest) if w.strip()]
            if self.state == "abstract":
                section = "zh" if label in ("关键词", "关键字") else "en"
                target = self.paper["abstract"].setdefault(section, {"paragraphs": []})
                target["keywords"] = words
            else:
                self._emit({"type": "paragraph",
                            "text": ("关键词：" if label in ("关键词", "关键字")
                                     else "Keywords:") + rest.strip()})
            return
        if self.state == "refs" and REFERENCE_RE.match(text):
            self.paper["references"]["items"].append(text)
            return
        self._emit({"type": "paragraph", "text": text})

    def _parse_quote(self) -> None:
        collected = []
        while self.index < len(self.lines) and self.lines[self.index].strip().startswith(">"):
            collected.append(self.lines[self.index].strip()[1:].strip())
            self.index += 1
        if collected and self.target is not None:
            self._emit({"type": "paragraph", "text": _join_lines(collected)})

    def _parse_list(self) -> None:
        items: list[str] = []
        ordered = bool(re.match(r"^\s*\d+[.)]", self.lines[self.index]))
        while self.index < len(self.lines):
            match = LIST_RE.match(self.lines[self.index])
            if not match:
                break
            items.append(match.group(1).strip())
            self.index += 1
        if items and self.target is not None:
            self._emit({"type": "list", "ordered": ordered, "items": items})

    def _parse_code(self) -> None:
        fence = self.lines[self.index].strip()
        language = fence[3:].strip()
        self.index += 1
        body: list[str] = []
        while self.index < len(self.lines):
            if self.lines[self.index].strip().startswith("```"):
                self.index += 1
                break
            body.append(self.lines[self.index])
            self.index += 1
        if self.target is not None:
            self._emit({"type": "code", "language": language, "text": "\n".join(body)})

    def _parse_equation(self) -> None:
        opening = self.lines[self.index].strip()
        body: list[str] = []
        if opening != "$$" and opening.endswith("$$"):
            body.append(opening[2:-2])
            self.index += 1
        else:
            self.index += 1
            while self.index < len(self.lines):
                line = self.lines[self.index]
                if line.strip().endswith("$$"):
                    body.append(line.strip()[:-2])
                    self.index += 1
                    break
                body.append(line)
                self.index += 1
        latex = "\n".join(body).strip()
        if self.target is not None:
            self._emit({"type": "equation", "latex": latex})

    def _parse_image(self, line: str) -> None:
        match = IMAGE_RE.match(line)
        alt, src = match.group(1).strip(), match.group(2).strip()
        self.index += 1
        if self.target is None:
            return
        block = {"type": "figure", "src": src, "caption": alt}
        self._emit(block)

    def _is_table_start(self, index: int) -> bool:
        if index + 1 >= len(self.lines):
            return False
        separator = self.lines[index + 1].strip()
        if not separator.startswith("|"):
            return False
        return bool(TABLE_SEP_RE.match(separator)) and "-" in separator

    def _parse_table(self) -> None:
        header = split_row(self.lines[self.index])
        self.index += 2
        rows: list[list[str]] = []
        while self.index < len(self.lines):
            line = self.lines[self.index]
            if not line.strip().startswith("|"):
                break
            cells = split_row(line)
            if not any(cells):
                break
            rows.append(cells)
            self.index += 1
        width = len(header)
        normalized: list[list[str]] = []
        for row in rows:
            row = row[:width] + [""] * (width - len(row))
            normalized.append(row)
        if self.target is not None:
            self._emit({"type": "table", "caption": "", "header": [header],
                        "rows": normalized})

    # -- structure -----------------------------------------------------
    def _is_structural(self, stripped: str, index: int) -> bool:
        if HEADING_RE.match(stripped):
            return True
        if stripped.startswith("```") or stripped.startswith("$$"):
            return True
        if stripped.startswith("|") and self._is_table_start(index):
            return True
        if IMAGE_RE.match(stripped):
            return True
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            return True
        if LIST_RE.match(self.lines[index]):
            return True
        if stripped.startswith(">"):
            return True
        return False

    def _postprocess(self) -> None:
        for key in ("body",):
            self._fix_blocks(self.paper[key])
        if self.paper.get("appendix"):
            self._fix_blocks(self.paper["appendix"]["blocks"])

    def _fix_blocks(self, blocks: list[dict]) -> None:
        used: set[int] = set()
        for index, block in enumerate(blocks):
            if block.get("type") != "table":
                continue
            previous = blocks[index - 1] if index > 0 else None
            if (previous and previous.get("type") == "paragraph" and index - 1 not in used
                    and CAPTION_RE.match(previous.get("text", ""))):
                block["caption"] = previous["text"]
                used.add(index - 1)
        for index, block in enumerate(blocks):
            if block.get("type") == "figure":
                if index + 1 < len(blocks) and index + 1 not in used:
                    nxt = blocks[index + 1]
                    if nxt.get("type") == "paragraph" and CAPTION_RE.match(nxt.get("text", "")):
                        block["caption"] = nxt["text"]
                        used.add(index + 1)
        for index, block in enumerate(blocks):
            if block.get("type") != "table":
                continue
            if index + 1 < len(blocks) and index + 1 not in used:
                nxt = blocks[index + 1]
                if nxt.get("type") == "paragraph" and nxt.get("text", "").startswith("注："):
                    block["note"] = nxt["text"]
                    used.add(index + 1)
        for index, block in enumerate(blocks):
            if block.get("type") != "figure":
                continue
            cursor = index + 1
            while cursor < len(blocks) and cursor in used:
                cursor += 1
            if cursor < len(blocks):
                nxt = blocks[cursor]
                if nxt.get("type") == "paragraph" and nxt.get("text", "").startswith("注："):
                    nxt["type"] = "note"
        cleaned = [block for index, block in enumerate(blocks) if index not in used]
        blocks[:] = cleaned


def convert_markdown(text: str) -> dict:
    importer = MarkdownImporter(text)
    paper = importer.convert()
    _apply_cover_meta(paper, importer.lines)
    return paper


META_KEYS = {
    "论文题目": "title", "题目": "title", "课程名称": "course",
    "学院": "college", "院别": "college", "专业": "major", "班级": "class",
    "学号": "student_id", "姓名": "author", "指导教师": "advisor",
    "指导老师": "advisor", "日期": "date", "完成日期": "date",
}


def _apply_cover_meta(paper: dict, lines: list[str]) -> None:
    """Read the cover-information table that Markdown drafts usually carry."""
    start = None
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line.strip())
        if match and "封面" in match.group(2):
            start = index + 1
            break
    if start is None:
        return
    index = start
    while index < len(lines) and not lines[index].strip().startswith("|"):
        if HEADING_RE.match(lines[index].strip()):
            return
        index += 1
    if index >= len(lines):
        return
    header = split_row(lines[index])
    index += 2
    meta = paper.setdefault("meta", {})
    while index < len(lines) and lines[index].strip().startswith("|"):
        row = split_row(lines[index])
        index += 1
        if len(row) < 2:
            continue
        label = _compact(row[0])
        value = row[1].strip()
        if not value:
            continue
        if "学号" in label or "姓名" in label:
            parts = re.split(r"[／/]", value)
            if len(parts) >= 2:
                meta.setdefault("student_id", parts[0].strip())
                meta.setdefault("author", parts[1].strip())
                continue
        if "学院" in label or "班级" in label:
            parts = re.split(r"[／/]", value)
            for part, key in zip(parts, ("college", "major", "class")):
                if part.strip():
                    meta.setdefault(key, part.strip())
            continue
        for needle, key in META_KEYS.items():
            if needle in label:
                meta.setdefault(key, value)
                break


def markdown_to_paper(md_path: str | Path) -> dict:
    path = Path(md_path)
    text = path.read_text(encoding="utf-8")
    paper = convert_markdown(text)
    paper.setdefault("meta", {}).setdefault("title", path.stem)
    return paper


def write_json(paper: dict, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.write_text(json.dumps(paper, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
