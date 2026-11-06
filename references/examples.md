# 使用示例

以下命令均在仓库根目录执行。

## 1. 最小示例（JSON）

`references/example-paper.json` 覆盖了标题、摘要、公式、三线表、图片、参考文献与附录：

```bash
python scripts/papermaker.py build references/example-paper.json -o out/example.docx
python scripts/papermaker.py inspect out/example.docx
```

期望：4 个分节（封面 / 目录 / 摘要 / 正文），封面为默认模板（黑河学院校徽 + 题目 + 字段表），
目录页码为 I、II、1、2…，正文含 OMML 公式与三线表。

导出 PDF 预览：

```bash
python scripts/papermaker.py finalize out/example.docx --pdf out/example.pdf
```

## 2. Markdown 初稿

```bash
# 先转 JSON 便于审校（可选）
python scripts/papermaker.py md2json test/课程设计论文_初稿.md -o out/paper.json

# 直接构建（默认套用 assets/cover.docx）
python scripts/papermaker.py build test/课程设计论文_初稿.md -o out/论文.docx
```

`md2json` 会识别标题、摘要/Abstract、目录、表格与表题/表注、图片与图题、`$$` 公式、
代码块、列表与封面信息表。

## 3. Markdown → DOCX（md2docx）

`references/example-paper.md` 是一份可直接转换的初稿（封面信息表、摘要/Abstract、目录、
三章正文、三线表、图片、公式、参考文献与附录）：

```bash
# 一步构建
python scripts/papermaker.py build references/example-paper.md -o out/from-md.docx

# 或先转 JSON 审校再构建
python scripts/papermaker.py md2json references/example-paper.md -o out/from-md.json
python scripts/papermaker.py build out/from-md.json -o out/from-md.docx
```

`md2json` 会把“封面信息”表映射到 `meta`（题目、课程、学院/专业/班级、学号/姓名、
指导教师、日期），表格的上一行 `表 2-1 …` 作为表题、下一行 `注：…` 作为表注，
图片后的 `图 2-1 …` 作为图题，`$$ … \tag{2-1} $$` 作为行间公式，`# 第 1 章` / `## 1.1`
自动编号。目录小节会被忽略（目录由域生成）。

构建结果：4 个分节，封面为默认模板并用 `meta` 填充，正文含居中三线表与 OMML 公式。

## 4. 复制某份成稿的封面

```bash
# 覆盖写入目标
python scripts/papermaker.py cover --from 课程设计论文_黄伟杰.docx --to out/论文.docx

# 输出到新文件
python scripts/papermaker.py cover --from A.docx --to B.docx -o out/C.docx
```

封面（含页眉里的校徽图片）会整体搬过去，目标正文与目录不受影响；目录页不会继承封面页眉。

构建时一并套用：

```bash
python scripts/papermaker.py build paper.json -o out/论文.docx --cover-from 学校模板.docx
```

## 5. 重新生成默认封面模板

```bash
python scripts/make_default_cover.py 课程设计论文_黄伟杰.docx -o assets/cover.docx
```

脚本保留校徽与图片，把标题替换为 `{{title}}`、课程名替换为 `《{{course}}》`、字段值替换为
`{{student_id}}` 等占位符，并保证不残留个人信息。之后 `build` 会用 `meta` 自动填充。

## 6. 自定义封面填写

```json
{
  "cover": {"mode": "copy", "source": "school-cover.docx", "fill": true}
}
```

`fill: true` 时用 `meta` 填充占位符；也可显式指定：

```json
{"cover": {"mode": "copy", "source": "school-cover.docx",
           "replacements": {"{{title}}": "我的论文题目", "{{author}}": "张三"}}}
```

## 7. 打包为单文件程序

```bash
python -m pip install pyinstaller
python scripts/build_exe.py            # 产物 dist/papermaker.exe（Windows）或 dist/papermaker
```

产物已内嵌 `assets/`，可脱离仓库运行；仓库本身不提交二进制。

## 8. 打包技能包与运行测试

```bash
# 技能包 zip（不含 test/、tests/、成稿等开发文件）
python scripts/package_skill.py            # 产物 paper-maker.zip

python -m unittest discover -s tests -v
```

测试覆盖：标题编号与规范化、行内公式/加粗/角标、OMML 结构、三线表、分节页码与空白页眉、
Markdown 解析、封面复制（正文图片 + 页眉图片）、默认封面占位符填充。
