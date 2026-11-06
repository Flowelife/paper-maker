# 输入格式（paper JSON）

`build` 接受 `.json`；传入 `.md` 时会先按 `md2json` 规则解析成同一结构。所有字段除注明外均可省略。

## 根对象

```json
{
  "schema": "paper-maker/1",
  "meta": { "title": "…", "course": "…" },
  "cover": { "mode": "template" },
  "abstract": { "zh": { … }, "en": { … } },
  "toc": { "enabled": true, "title": "目    录", "depth": 3 },
  "numbering": { "chapter": "arabic" },
  "body": [ … ],
  "references": { "items": [ … ] },
  "appendix": { "blocks": [ … ] }
}
```

## meta

| 键 | 用途 |
| --- | --- |
| `title` | 封面题目、文档属性 |
| `course` | 封面课程名、页眉 `《{course}》 论文` |
| `author` / `student_id` / `grade` / `college` / `major` / `class` / `advisor` / `date` | 封面字段 |
| `header` | 页眉文字模板，支持 `{course}`、`{title}`；缺省 `《{course}》 论文`，置空字符串则不显示文字 |

页眉缺省为 `《{course}》 论文`；`meta.header` 可写 `"页眉：{course}"` 之类的模板，
命令行也可用 `--header "…"` 临时覆盖。
置为空字符串时不显示文字（仍保留下框线）。

## cover

| `mode` | 行为 |
| --- | --- |
| `template`（默认） | 使用 `cover.template` 或内置 `assets/cover.docx`，用 `meta` 填充 `{{placeholders}}` |
| `copy` | 复制 `cover.source` 指向文档的封面；`cover.fill=true` 时同样用 `meta` 填占位符，或由 `cover.replacements` 显式给出 |
| `generated` | 程序生成封面（课程名 + 题目 + 字段表） |
| `none` | 不要封面 |

模板占位符：`{{title}}` `{{course}}` `{{author}}` `{{student_id}}` `{{grade}}` `{{college}}`
`{{major}}` `{{class}}` `{{advisor}}` `{{date}}`。占位符应位于单个文本 run 内（默认模板满足）。

重新生成默认模板（清空标题与填写内容）：

```bash
python scripts/make_default_cover.py 成稿.docx -o assets/cover.docx
```

该脚本会保留校徽与图片、把标题/课程名/字段值替换为占位符，并确认没有残留个人信息。

## abstract

```json
"abstract": {
  "zh": {"heading": "摘要", "paragraphs": ["第一段…"], "keywords": ["关键词1", "关键词2"]},
  "en": {"heading": "Abstract", "paragraphs": ["…"], "keywords": ["keyword one"]}
}
```

- 中文标题固定渲染为 `摘    要`；英文为 `Abstract`（Times 加粗）。
- 关键词标签加粗，正文与关键词之间自动空两行；英文关键词首字母大写。
- `keyword_label` 可覆盖 `关键词：` / `Keywords:`。

## toc

`enabled`（默认 `true`）、`title`（默认 `目    录`）、`depth`（默认 3，写入 `TOC \o "1-{depth}"`）。

## numbering

`chapter`：`arabic`（默认，`第1章`）或 `chinese`（`第一章`）。

## body 块

全部块均为对象，`type` 必填：

| type | 字段 | 说明 |
| --- | --- | --- |
| `heading` | `level`(1–4)、`text` | 自动编号；输入中的编号会被剥离后重排 |
| `paragraph` | `text` | 正文段落；支持行内标记 |
| `equation` | `latex`、`tag` | 行间公式；`tag` 缺省按章编号；LaTeX 中的 `\tag{}` 亦被识别 |
| `figure` | `src`、`caption`、`width_cm` | 图片居中，题注在下自动编号 |
| `table` | `header`、`rows`、`caption`、`note` | `header` 为“行数组”，如 `[["列一","列二"]]`；单元格一律居中 |
| `list` | `items`、`ordered` | 无序用 `·`，有序用 `（1）（2）` |
| `code` | `text`、`language` | 等宽 10.5 磅、左对齐、逐行保留 |
| `note` | `text` | 图表说明，10.5 磅左对齐 |
| `pagebreak` | — | 强制分页 |
| `empty` | — | 空行 |

表格列宽按内容自动分配，总宽等于版心；表头与表内文字一律居中。

## 行内标记

| 写法 | 效果 |
| --- | --- |
| `$x_i$` | OMML 行内公式 |
| `**加粗**` | 加粗 run |
| `` `代码` `` | 去掉反引号，按正文字体显示 |
| `[3]`、`[3][4]`、`[3-5]` | 上标引用角标 |

公式支持 LaTeX 子集：分式、根式、上下标、求和/积分、定界符 `\left…\right`、重音
`\hat`/`\bar`/`\vec`/`\widehat`、`\text`/`\mathrm`/`\mathbf`/`\boldsymbol`/`\mathbb`、
希腊字母与常用符号、`cases`/`aligned`/`matrix` 环境。未知命令降级为直立文本，不中断构建。

## references / appendix

```json
"references": {"heading": "参考文献", "items": ["[1] 作者. 题名[J]. 期刊, 2020."]},
"appendix": {"heading": "附录", "blocks": [{"type": "heading", "level": 2, "text": "代码"}]}
```

- 参考文献条目缺 `[n]` 时按序号自动补；悬挂缩进 600 twips。
- 附录二级标题自动生成 `附录A  …`，三级为 `A.1  …`；附录图表编号为 `图A-1`。

## 图片路径

`src` 相对 JSON 所在目录解析；找不到时按文件名在同级 `assets/`、`figures/`、`images/`、
`output/`、`ouput/` 目录递归回退查找。支持 PNG/JPEG/GIF/BMP，DPI 从文件头读取（缺省 96）。

## Markdown 映射

| Markdown | 结果 |
| --- | --- |
| `# 第 1 章 绪论` / `## 1.1 背景` / `### 1.2.1 …` | 对应层级标题（编号被剥离重排） |
| `**关键词**：甲；乙` | 摘要关键词 |
| `\| … \|` 表格 + 上一行 `表 1-1 …` + 下一行 `注：…` | 表格、表题、表注（对齐行仅用于识别表头，单元格一律居中） |
| `![图 1-1 …](a.png)` + 下一行 `图 1-1 …` | 图片与图题 |
| `$$ … \tag{1-1} $$` | 行间公式 |
| ```` ```r ```` | 代码块 |
| `- ` / `1. ` | 列表 |
| `> ` | 普通段落 |
| `## 封面信息` 表格 | 映射到 `meta`（题目/课程/学院/专业/班级/学号/姓名/指导教师/日期） |
| `## 目录` 小节 | 忽略（目录由域生成） |
