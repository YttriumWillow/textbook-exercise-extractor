---
name: textbook-exercise-extractor
description: 由大部头教材 PDF 与作业清单（章节 + 题号，如 "2.2: #1, 4(a)-(e), 9..."）生成一份作业题 PDF。默认用 LaTeX 重排，使公式成为真正可选中的矢量文本；也支持更快的裁剪合并模式。务必一并带上每道题所依赖的习题组说明段落。当用户给出作业题号清单与教材 PDF，或要求把教材题目汇总成一份 PDF 时使用。
agent_created: true
---

> 本文件是 `SKILL.md` 的**中文版**，内容与之一致，供中文阅读。
> 技能加载入口仍为 `SKILL.md`（加载器只识别该文件名）。

# 教材习题提取器

输入"作业清单（章节 + 题号）"与教材 PDF，输出一份只包含这些题目的 PDF。

**务必带上每道题所依赖的习题组说明。** 如果没有
`Limits of quotients — Find the limits in Exercises 23–42.`（商的极限 —— 求 23–42 题的极限）
这句说明，读者根本看不出孤零零的 `23.` 到底要做什么。这是此类任务最常见的失误点。

## 输出约定（用户规则）

**默认输出 PDF，且文件名必须带日期。**

```
{课程}_Homework{N}_{YYYY-MM-DD}.pdf      例：MAT1001_Homework1_2026-09-13.pdf
```

- 日期取**当前会话日期**，不要取文件修改时间。
- 只有用户**明确要求**其他格式时才换扩展名（`.md` / `.tex` / `.docx` / `.html`），
  无论哪种格式文件名都要保留日期。
- 若此前的产物文件名没有日期，重命名为带日期的形式。

## 按需安装（用户规则）

**不要提前装转换工具。** `pandoc` 只在用户**真的要** DOCX/HTML 输出时才装；
PDF / LaTeX 源 / Markdown 都不需要它。TeX 宏包同理 —— 等编译报错了再用 `tlmgr` 补，
不要预先装一堆。

## 工作目录纪律（用户规则，适用于所有任务）

**不要把临时文件写到工作区根目录。** 开工前先建一个临时目录
（`<workspace>/.scratch/` 或 `<workspace>/<job>_build/`），所有探测脚本、日志、dump、
墨迹剖面、校样图、中间 PDF 全部放进去。根目录只保留**最终交付物**
（以及可选的小源目录，如 `hw1_build/`）。收工删除临时目录；大体积下载放 `$env:TEMP`，用完即删。

## 先选模式

| | 模式 A — 裁剪合并 | 模式 B — LaTeX 重排 |
|---|---|---|
| 产物 | 原页面片段 | 重新排版的文字与公式 |
| 文本 | 不可选中 | 真正可选中、可搜索的矢量文本 |
| 风险 | 层叠分数会被裁剪框切断；嵌入页片段过多时预览卡顿 | 需要人工转写 |
| 适用 | 快速原样复制，或图形占主导 | **默认** —— 用户要"完整数学式子"、可选文本，或遇到裁剪/预览问题 |

## 核心原则：位置信息不要信文字层

许多排版书籍（LaTeX / InDesign 导出）的 span 与 line 包围盒对部分段落会**偏移 20–40 pt**，
靠 `"23."` 标记定位会静默选中错误的题目。凡涉位置，一律以
**200 dpi 灰度墨迹剖面**为准。

文字层在两方面**可靠**，可以放心用：
- **字符与上标** —— 上标表现为 `size≈6.1` 的 span 紧邻 `size≈9.0` 的基底 span
  （区分 `x^2` / `x^3`、`7^-` / `7^+`）。用它来敲定有歧义的指数。
- 定位习题组标题（`EXERCISES n.m`）。

## 工作流程

**1. 定位习题集。** 逐页记录匹配 `EXERCISES\s+\d+\.\d+` 的行及印刷页码，建立
`章节 -> 页码范围` 映射，并记下页偏移（印刷页 + k = PDF 页）。

**2. 看图。** 把每页习题区以 ~130 dpi 渲染并**实际查看**。记录：分几栏、各题落在哪个子栏、
图形在哪、有哪些说明横幅。

**3. 计算墨迹剖面。** 对栏区间 `(x0, x1)`：
`page.get_pixmap(dpi=200, colorspace=csGRAY, clip=Rect(x0,0,x1,H))`，
逐行统计暗像素（`<205`），输出 `GAP`（`行数 <= max(2, 0.012*width)`）与 `ink` 的极大游程。
这即为精确的 PDF 点坐标分界。

**4. 按页面图像把游程映射到题目**，绝不要按标记坐标映射。

**5a. 模式 A — 裁剪合并。** 任务表 `(page, strip_x0, strip_x1, y0, y1, section, label)`，
`y0`/`y1` 取在真实 GAP 游程内；随后 `out.new_page()` +
`cur.show_pdf_page(target, src, pno, clip=rect)`。工具见 `scripts/extract.py`。

**5b. 模式 B — 重排（首选）。**
1. 把每道题转写为 LaTeX；指数对照 span dump 核对，根号/分式对照该区域高清渲染图核对。
2. 图形以 400 dpi 导出 PNG。用"四边无墨迹"自动扩展裁剪框（`scripts/figure_box.py`）。
   图形常与正文**并排** —— 必须按 x 区间隔离，否则会把文字拖进图片。
3. 写 `.tex`，显式写出说明段落（模板 `assets/hw-template.tex`），编译两遍。
4. 校验：渲染输出页逐页查看 —— 题目齐全、公式正常、无 `??`、页底无孤立标题。

**6. 呈现结果**，并说明所用模式。

## 中文教材支持

- **模式 A 与语言无关** —— 裁剪合并对任何语言都能直接用。
- **模式 B 需要换引擎**：英文用 `pdflatex` + `article`，中文改用 `xelatex` + `ctexart`，
  并安装 `tlmgr install ctex cjk xecjk zhnumber`。`ctex` 会自动选用 Windows 的
  SimSun / SimHei，**已实测通过**：中文正文用宋体、公式用 Computer Modern，
  PDF 文字层仍可正常提取中文。
  模板见 `assets/hw-template-zh.tex`。
- 纯英文文档仍建议用 `pdflatex`（更快，且完全不依赖 fontconfig）。

## 输出格式（可指定，默认 PDF）

| 格式 | 做法 |
|---|---|
| **PDF**（默认） | 编译 `.tex`：英文 `pdflatex`，中文 `xelatex` |
| **LaTeX 源** | 直接交付 `.tex`，方便用户二次编辑 |
| **Markdown** | `scripts/tex2md.py`：保留 `$…$` / `$$…$$`，小问转成 `a. b. c.` |
| **DOCX / HTML** | 先 `tex2md.py`，再 `pandoc -f markdown -t docx`（或 `-t html5 -s --mathjax`） |

**坑**：pandoc 的 LaTeX reader 会**静默丢弃自定义宏**（实测把全部 `\instr{}` 说明段落都丢了）。
所以**绝不能**让 pandoc 直接读 `.tex`，必须先过一遍 `tex2md.py`。
PDF / LaTeX 源 / Markdown 都不需要 pandoc；**只有用户明确要 DOCX / HTML 时才装它**
（见上文"按需安装"）。

```powershell
python scripts/tex2md.py hw1.tex -o hw1.md
pandoc hw1.md -f markdown -t docx  -o hw1.docx
pandoc hw1.md -f markdown -t html5 -s --mathjax -o hw1.html
```

## 安装 TeX（用户规则）

**默认装到系统软件默认位置** —— Windows 上为 `C:/Program Files/texlive/<年份>`，
并尽量控制体积：

- `selected_scheme scheme-small`（或 `scheme-basic` + 少量显式宏包）。
- profile 里设 `tlpdbopt_install_docfiles 0` 与 `tlpdbopt_install_srcfiles 0`。
- 装完删除安装器。

**安装前先检查剩余空间。** 若默认盘空间不足（`scheme-small` 需预留 ≥ 4 GB），
**停下来询问用户要装到哪里**，不要擅自换盘。例外：用户明确指定位置时（如"装到 D 盘"）
按其指定执行。

完整步骤与装后修复见 `references/installing-tex-windows.md`。

## 详细资料

- Windows 装 TeX（无需管理员）：`references/installing-tex-windows.md`
- 分栏排版陷阱与校验方法：`references/layout-pitfalls.md`
- 脚本：`scripts/extract.py`（模式 A）、`scripts/figure_box.py`（图形裁剪）、
  `scripts/tex2md.py`（LaTeX → Markdown）

## 环境备注（Windows）

- Bash 可能不可用 —— 用 PowerShell 工具；当工具返回空时，把标准输出重定向到文件再读。
- 使用托管 Python 的 venv，在其中 `pip install pymupdf`。
- `page.get_pixmap(dpi=...)` 的 dpi 必须是 **int**，不能是 float。
