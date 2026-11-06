---
name: paper-maker
description: 由结构化 JSON（或 Markdown 初稿）生成符合课程模板的中文论文 DOCX；支持把一份文档的封面（含页眉图片）完整复制到另一份文档（兼容 .doc），并内置黑河学院默认封面模板。当用户要求“生成/排版论文”“把 markdown 论文转成 word”“套用论文格式”“复制封面”时使用。
---

# paper-maker

把结构化数据稳定转换为格式正确的论文文档：字体字号、标题编号、三线表、OMML 公式、
分节页码、目录域全部由程序写入，正文内容只描述结构。**不要手工改 Word 格式**，
改输入后用本工具重建。

仓库即 Skill 包，只包含源码与脚本，不附带二进制。运行时仅依赖 Python 标准库；
`.doc` 转换与目录页码刷新需要本机安装 WPS 或 Microsoft Word（缺失时仍可生成 docx）。

## 目录结构

```
SKILL.md                 本文件
scripts/                 完整脚本程序
  papermaker.py          入口（CLI）
  build_exe.py           打包为单文件程序
  package_skill.py       打包技能为 zip
  make_default_cover.py  从成稿重新生成默认封面模板
  src/papermaker/        实现
references/              使用细节
  format-spec.md         版式规范与验收对照
  input-schema.md        JSON 字段、块类型、行内标记、Markdown 映射
  errors.md              报错与排查
  examples.md            典型命令示例（含 Markdown → DOCX 完整案例）
  example-paper.md       Markdown 初稿示例
  example-paper.json     结构化 JSON 示例
assets/                  资源
  cover.docx             默认封面模板（占位符版，无个人信息）
  demo.png               示例图片
```

## 快速开始

```bash
# 由 JSON 构建（默认套用 assets/cover.docx，并用 meta 填充）
python scripts/papermaker.py build paper.json -o out/论文.docx

# 由 Markdown 初稿直接构建
python scripts/papermaker.py build test/课程设计论文_初稿.md -o out/论文.docx

# 刷新目录页码并导出 PDF（需要 WPS/Word）
python scripts/papermaker.py finalize out/论文.docx --pdf out/论文.pdf

# 自检：标题层级、分节、页码格式
python scripts/papermaker.py inspect out/论文.docx
```

## 命令

| 子命令 | 作用 |
| --- | --- |
| `build <json|md> -o out.docx` | 生成论文；`--cover-from A` 复制封面；`--header "…"` 自定义页眉；`--refresh auto\|always\|never` 控制目录刷新；`--max-figure-cm` 图片宽度上限（默认 14） |
| `md2json <md> -o paper.json` | Markdown → 结构化 JSON |
| `cover --from A --to B [-o C]` | 复制封面；A/B 可为 `.docx` 或 `.doc` |
| `finalize out.docx [--pdf out.pdf]` | 更新域与目录，可选导出 PDF |
| `inspect out.docx` | 结构摘要（调试/自检） |

## 工作流

1. 整理输入：把题目、课程、姓名、学号、指导教师等写入 `meta`；正文按块描述。
   Markdown 初稿可先 `md2json` 再人工补 `meta`。
2. `build` 生成 docx。若需要学校模板封面，用 `--cover-from 模板.docx` 或
   `cover.mode = "copy"`。
3. `inspect` 检查四个分节与页码格式，确认封面/目录页没有页眉页脚。
4. `finalize` 刷新目录并导出 PDF 供人工复核。

## 版式（程序保证）

一级标题黑体小二居中分页，二级/三级黑体小三/四号，四级宋体小四（不加粗）首行缩进；正文
宋体 + Times New Roman 小四、首行缩进 2 字符、行距 1.3；图表标题与表内文字五号，表格
单元格与表头一致居中；三线表上下 1.5 磅、表头下 0.75 磅、宽度等于版心、表下空一行；
公式为 OMML 标准公式对象，右端 `（章-序）` 编号；页眉默认 `《{course}》 论文`，可用
`meta.header`（支持 `{course}`/`{title}`）自定义；封面与目录使用空白页眉页脚；
摘要页码 I、II，正文页码 1、2、3；目录为 `TOC \o "1-3" \h \u` 域并在打开时更新。
详见 `references/format-spec.md`。

## 默认封面

`assets/cover.docx` 由成稿封面脱敏生成：保留校徽与图片，标题、课程名与各字段改为
`{{title}}`、`{{course}}`、`{{student_id}}` 等占位符，构建时用 `meta` 填充。
需要换模板时：

```bash
python scripts/make_default_cover.py 新成稿.docx -o assets/cover.docx
```

## 打包

```bash
python -m pip install pyinstaller
python scripts/build_exe.py
```

产物写入 `dist/`（已内嵌 `assets/`），仓库不提交；请在目标平台现打包。

## 打包技能

```bash
python scripts/package_skill.py          # -> paper-maker.zip
```

仅包含 `SKILL.md`、`scripts/`、`references/`、`assets/`，解压后即可运行。

## 注意

- 标题只写文字不写编号（`{"level": 1, "text": "绪论"}`），编号由程序生成；
  输入已带编号会被规范化。
- 图片路径相对 JSON 所在目录解析，找不到时在 `assets/`、`figures/` 等目录按文件名回退。
- 目录页码为空或全为 1 时执行 `finalize`，或在 WPS/Word 中更新域。
- 更多细节见 `references/`：格式规范、输入字段、报错排查、完整示例。
