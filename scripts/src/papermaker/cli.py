"""Command line interface for paper-maker."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .builder import build_docx
from .model import PaperError, build_plan, load_json
from .mdimport import markdown_to_paper, write_json
from .resources import default_cover


def _eprint(message: str) -> None:
    print(message, file=sys.stderr)


def _load_paper(path: Path) -> dict:
    if path.suffix.lower() in (".md", ".markdown"):
        return markdown_to_paper(path)
    return load_json(path)


def cmd_md2json(args: argparse.Namespace) -> int:
    paper = markdown_to_paper(Path(args.source))
    out = write_json(paper, Path(args.output))
    print(f"已生成 {out}")
    return 0


def _prepare_cover(paper: dict, args: argparse.Namespace, paper_dir: Path) -> str:
    """Normalise ``cover.mode``, materialise the template path, return the mode."""
    cover = dict(paper.get("cover") or {})
    mode = str(cover.get("mode") or "template").lower()
    if args.cover_from:
        cover["source"] = str(Path(args.cover_from))
        mode = "copy"
    if mode == "template":
        configured = cover.get("template")
        template = Path(configured) if configured else default_cover()
        if configured and not template.is_absolute():
            template = paper_dir / template
        if not template.is_file():
            _eprint(f"提示: 默认封面模板 {template} 不存在，改用程序生成的封面。")
            mode = "generated"
        else:
            cover["template_path"] = str(template)
    cover["mode"] = mode
    paper["cover"] = cover
    return mode


def _apply_cover(paper: dict, mode: str, out: Path, paper_dir: Path) -> None:
    from .cover import copy_cover, cover_values

    cover = paper.get("cover") or {}
    replacements = None
    if mode == "template":
        source_path = Path(cover["template_path"])
        replacements = cover_values(paper.get("meta") or {})
    elif mode == "copy":
        configured = cover.get("source")
        if not configured:
            return
        source_path = Path(configured)
        if not source_path.is_absolute():
            source_path = paper_dir / source_path
        if cover.get("fill"):
            replacements = cover_values(paper.get("meta") or {})
        elif isinstance(cover.get("replacements"), dict):
            replacements = {str(k): str(v) for k, v in cover["replacements"].items()}
    else:
        return
    copy_cover(source_path, out, out, replacements=replacements)
    print(f"已应用封面: {source_path.name} -> {out.name}")


def cmd_build(args: argparse.Namespace) -> int:
    source = Path(args.source)
    paper = _load_paper(source)
    if args.header is not None:
        paper.setdefault("meta", {})["header"] = args.header
    paper_dir = source.resolve().parent
    cover_mode = _prepare_cover(paper, args, paper_dir)
    plan = build_plan(paper)
    options = {"max_figure_cm": args.max_figure_cm}
    toc = paper.get("toc") or {}
    if not toc.get("enabled", True):
        plan.toc_entries = [entry for entry in plan.toc_entries if entry[0] > 99]
    options["toc"] = {"enabled": bool(toc.get("enabled", True)),
                      "title": toc.get("title", "目    录"),
                      "depth": int(toc.get("depth", 3))}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    build_docx(plan, out, source.resolve().parent, options)
    print(f"已生成 {out}")
    _apply_cover(paper, cover_mode, out, paper_dir)
    if args.refresh != "never":
        from .finalize import refresh_document

        ok = refresh_document(out)
        if not ok:
            _eprint("提示: 未找到 WPS/Word 自动化接口，目录页码将在打开文档时更新。")
    print("完成。")
    return 0


def cmd_cover(args: argparse.Namespace) -> int:
    from .cover import copy_cover

    source = Path(args.source)
    target = Path(args.target)
    output = Path(args.output) if args.output else target
    result = copy_cover(source, target, output)
    print(f"已将封面从 {source.name} 复制到 {result}")
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    from .finalize import refresh_document

    path = Path(args.source)
    ok = refresh_document(path, pdf=Path(args.pdf) if args.pdf else None)
    if not ok:
        _eprint("未找到可用的 WPS/Word 自动化接口，无法更新目录与页码。")
        return 2
    print(f"已更新域与目录: {path}")
    if args.pdf:
        print(f"已导出 PDF: {args.pdf}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    from .inspect import summarize
    from .cover import ensure_docx

    path = Path(args.source)
    docx_path = ensure_docx(path)
    info = summarize(docx_path)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="papermaker",
        description="由结构化 JSON（或 Markdown 初稿）生成符合课程模板的论文 DOCX。",
    )
    parser.add_argument("--version", action="version", version=f"paper-maker {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="由 paper.json 或 paper.md 构建 docx")
    build.add_argument("source", help="结构化 JSON 或 Markdown 文件")
    build.add_argument("-o", "--output", required=True, help="输出 docx 路径")
    build.add_argument("--cover-from", help="从该 docx/doc 复制封面")
    build.add_argument("--max-figure-cm", type=float, default=14.0,
                       help="图片最大宽度（厘米，默认 14）")
    build.add_argument("--refresh", choices=["auto", "always", "never"], default="auto",
                       help="是否用 WPS/Word 更新目录页码（默认 auto）")
    build.add_argument("--header",
                       help="页眉文字，支持 {course}/{title}；默认《课程名》 论文")
    build.set_defaults(func=cmd_build)

    md2json = sub.add_parser("md2json", help="Markdown 初稿转结构化 JSON")
    md2json.add_argument("source")
    md2json.add_argument("-o", "--output", required=True)
    md2json.set_defaults(func=cmd_md2json)

    cover = sub.add_parser("cover", help="把 A 文档的封面复制到 B 文档")
    cover.add_argument("--from", dest="source", required=True, help="封面来源 docx/doc")
    cover.add_argument("--to", dest="target", required=True, help="目标 docx/doc")
    cover.add_argument("-o", "--output", help="输出路径（默认覆盖目标）")
    cover.set_defaults(func=cmd_cover)

    finalize = sub.add_parser("finalize", help="更新域与目录（需要 WPS 或 Word）")
    finalize.add_argument("source")
    finalize.add_argument("--pdf", help="同时导出 PDF")
    finalize.set_defaults(func=cmd_finalize)

    inspect = sub.add_parser("inspect", help="输出 docx 结构摘要（调试用）")
    inspect.add_argument("source")
    inspect.set_defaults(func=cmd_inspect)
    return parser


def _configure_streams() -> None:
    """Write UTF-8 when output is redirected; keep the console's own encoding."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PaperError as exc:
        _eprint(f"错误: {exc}")
        return 1
    except FileNotFoundError as exc:
        _eprint(f"错误: 找不到文件 {exc.filename or exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
