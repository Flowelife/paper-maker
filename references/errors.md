# 报错与排查

程序以非零退出码表示失败，错误写到 stderr：

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 输入/资源错误（JSON、图片、模板、文件缺失） |
| 2 | `finalize` 找不到 WPS/Word 自动化接口 |

## 输入与结构

**`JSON 解析失败 文件:行:列 说明`**
JSON 语法错误。用 `python -m json.tool paper.json` 定位；常见原因是尾逗号或中文引号。

**`body[3]: 未知块类型 'table2'`**
`type` 拼写错误。合法值见 `references/input-schema.md` 的块类型表。

**`abstract.zh 应为字符串，实际为 dict`**
`abstract.zh.paragraphs` 内应为字符串数组，不是块对象。

**`table.header/rows 应为二维数组`**
`header` 必须是“行数组”：`[["列一","列二"]]`，不能写成 `["列一","列二"]`。

**`找不到文件: xxx`**
路径相对于当前工作目录；`build` 的图片相对于 JSON 所在目录。

## 图片

**`找不到图片: figures/a.png（已尝试 … 及同级目录）`**
确认 `src` 写法；程序会在 JSON 同级及父级的 `assets/`、`figures/`、`images/`、`output/`、
`ouput/` 目录按文件名递归回退。仍失败时改用绝对路径。

**`无法读取图片 xxx: 不支持的图片格式`**
仅支持 PNG/JPEG/GIF/BMP。EMF/WMF/SVG 需先转为 PNG。

## 封面

**`提示: 默认封面模板 … 不存在，改用程序生成的封面。`**
`assets/cover.docx` 缺失（例如只拷贝了 `scripts/`）。恢复模板：

```bash
python scripts/make_default_cover.py 成稿.docx -o assets/cover.docx
```

**`无法处理 x.doc: 需要本机安装 WPS 或 Microsoft Word 才能转换 .doc`**
`.doc` 依赖 COM 转换；让用户另存为 `.docx`，或安装 WPS/Office。

**`已生成 docx，但 .doc 回写失败（需要 WPS 或 Word）`**
目标为 `.doc` 时回写失败；改为输出 `.docx`。

**`x.docx 中未找到封面内容`**
来源文档没有可用的封面区域。程序以“目录”标题为界；没有目录时需保证封面在前且存在段落标题样式。

**封面里的图片缺失**
- 来源封面若是独立分节且图片在页眉，程序会连同页眉部件复制；目标封面必须自成节（`build` 生成的文档满足）。
- 用 Word 查看时若仍缺失，检查图片是否被“浮于文字上方”锚定在目录之后的段落——这类锚点不在封面区域内。

## 目录与页码

**`提示: 未找到 WPS/Word 自动化接口，目录页码将在打开文档时更新。`**
正常提示。文档已写入 `updateFields`，用 WPS/Word 打开即刷新；也可稍后执行
`finalize out.docx --pdf out.pdf`。

**`未找到可用的 WPS/Word 自动化接口，无法更新目录与页码。`（退出码 2）**
`finalize` 需要本机 WPS 或 Word。确认已安装并能被 COM 调用（WPS 的 ProgID 为 `KWPS.Application`）。

**目录页码全是 1**
域尚未更新。执行 `finalize`，或在 WPS/Word 中 `Ctrl+A` → `F9` 更新域。

## 打包

**`错误: 未安装 PyInstaller`**
`python -m pip install pyinstaller`。

**打包后的程序找不到 `assets/cover.docx`**
`scripts/papermaker.spec` 已把 `assets/` 打进包；若自行改动 spec，需保留
`datas=[(assets_dir, "assets")]`。运行时会从 `sys._MEIPASS/assets` 读取。

## 版式自检

```bash
python scripts/papermaker.py inspect out/论文.docx
```

输出标题层级、分节数量、每节页码格式与页眉页脚引用。四项分节依次为
封面 / 目录 / 摘要 / 正文；前两节的页眉页脚应为空部件。
