#!/usr/bin/env python3
"""Extract the cover of an existing thesis and store it as the bundled template.

The title, the course line and every filled-in field are replaced with
``{{placeholders}}`` so the repository never carries personal data:

    python scripts/make_default_cover.py 课程设计论文_黄伟杰.docx -o assets/cover.docx

Placeholders are filled at build time from ``meta`` (see ``references/``).
"""

from __future__ import annotations

import argparse
import re
import sys
from copy import deepcopy
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from papermaker.cover import build_cover_template  # noqa: E402
from papermaker.ns import w  # noqa: E402

FIELD_KEYS = {
    "学号": "student_id",
    "姓名": "author",
    "年级": "grade",
    "院别": "college",
    "专业": "major",
    "班级": "class",
    "指导教师": "advisor",
    "指导老师": "advisor",
    "完成日期": "date",
    "日期": "date",
}

TITLE_SIZE = "44"


def _text(element: Element) -> str:
    return "".join(element.itertext()).strip()


def _set_text(paragraph: Element, text: str) -> None:
    """Replace the paragraph's runs with a single run, keeping its formatting."""
    rpr = None
    for run in paragraph.findall(w("r")):
        found = run.find(w("rPr"))
        if found is not None:
            rpr = deepcopy(found)
            break
    for child in list(paragraph):
        if child.tag != w("pPr"):
            paragraph.remove(child)
    run = SubElement(paragraph, w("r"))
    if rpr is not None:
        run.append(rpr)
    SubElement(run, w("t")).text = text


def _is_centered(paragraph: Element) -> bool:
    ppr = paragraph.find(w("pPr"))
    if ppr is None:
        return False
    jc = ppr.find(w("jc"))
    return jc is not None and jc.get(w("val")) == "center"


def _largest_run_size(paragraph: Element) -> int:
    sizes = []
    for run in paragraph.findall(w("r")):
        rpr = run.find(w("rPr"))
        if rpr is None:
            continue
        size = rpr.find(w("sz"))
        if size is not None and (size.get(w("val")) or "").isdigit():
            sizes.append(int(size.get(w("val"))))
    return max(sizes or [0])


def edit_cover(blocks: list[Element]) -> None:
    """Blank the title, the course line and every filled-in cover field."""
    replaced: list[str] = []
    for block in blocks:
        if block.tag == w("p"):
            text = _text(block)
            if not text:
                continue
            if re.fullmatch(r"《.*》", text):
                _set_text(block, "《{{course}}》")
                replaced.append("course")
            elif _is_centered(block) and _largest_run_size(block) >= int(TITLE_SIZE) \
                    and len(text) > 6:
                _set_text(block, "{{title}}")
                replaced.append("title")
    for block in blocks:
        if block.tag != w("tbl"):
            continue
        for row in block.findall(w("tr")):
            cells = row.findall(w("tc"))
            if len(cells) < 2:
                continue
            label = re.sub(r"[\s\u3000:：]+", "", _text(cells[0]))
            key = FIELD_KEYS.get(label)
            if not key:
                continue
            paragraphs = cells[1].findall(w("p"))
            if not paragraphs:
                continue
            _set_text(paragraphs[0], "{{%s}}" % key)
            replaced.append(key)
    if "title" not in replaced:
        raise SystemExit("未识别到标题段落，请检查源文档封面结构")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成默认封面模板")
    parser.add_argument("source", help="含封面的成稿（docx/doc）")
    parser.add_argument("-o", "--output", default=str(HERE.parent / "assets" / "cover.docx"),
                        help="输出路径（默认 assets/cover.docx）")
    args = parser.parse_args(argv)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    build_cover_template(args.source, out, edit_cover)
    print(f"已生成默认封面模板 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
