---
name: textbook-exercise-extractor
description: "由大部头教材 PDF 与作业清单（章节 + 题号，如 \"2.2: #1, 4(a)-(e), 9...\"）生成一份作业题 PDF。用 LaTeX 重排，使公式成为真正可选中的矢量文本。务必一并带上每道题所依赖的习题组说明段落。当用户给出作业题号清单与教材 PDF，或要求把教材题目汇总成一份 PDF 时使用。"
agent_created: true
---

> 本文件是 `SKILL.md` 的**中文版**，内容与之一致，供中文阅读。
> 技能加载入口仍为 `SKILL.md`（加载器只识别该文件名）。

# 教材习题提取器

输入"作业清单（章节 + 题号）"与教材 PDF，输出一份只包含这些题目的 PDF，
用 LaTeX 重排，使公式成为真正可选中、可搜索的矢量文本。

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
校样图、中间 PDF 全部放进去。根目录只保留**最终交付物**
（以及可选的小源目录，如 `hw1_build/`）。收工删除临时目录；大体积下载放 `$env:TEMP`，用完即删。

## 输出要清晰简洁（用户规则）

模仿的是原书的**字体与配色**，绝不是它的物理版面。交付物是一份作业纸，读起来像原书，
**不是**原书的翻印本：

- 正文保持 10–11 pt、A4、**单栏**。原书那种 9 pt 双栏在作业纸上根本没法读 ——
  要抄的是字体和配色，不是分栏网格。
- 层级只用原书自己用的那几级：节横幅、蓝色无衬线小标题、题号。
  不加封面页、不加目录、不加额外的框和颜色。
- 每组说明段落**只排一次**，紧贴它覆盖的题目上方。
- `\needspace` 取值克制（§4–16 行）；20–34 会甩出半页空白。
- 图形保持原书比例（默认 `\fig[0.40]`）；不要为填满页面而放大某张图。
- 交付前比一下页数：超过原书题目页数的约 1.5 倍，说明排版太松。

## 核心原则：位置信息不要信文字层

许多排版书籍（LaTeX / InDesign 导出）的 span 与 line 包围盒对部分段落会**偏移 20–40 pt**，
靠 `"23."` 标记定位会静默选中错误的题目。定位图形时一律以
**200 dpi 灰度墨迹剖面**为准。

**数学公式内部**的包围盒错位没有固定偏移量，运算符的 x/y 完全没有意义 ——
实测同一个表达式里 `-` 与 `t` 报出的 x 坐标可以**完全相同**。只有正文体
（此处是 `TimesLTPro-*`）的字形位置可信；判断某题落在哪个子列时，要读**题号** span 的 `x`，
不要读旁边的公式。

**文字层连"这个字形到底是什么字符"也会撒谎。** 子集字体常被重编码，`get_text()`
会自信地报出与画出来不同的符号：本教材把斜体 `v` 映射成 `y`、把 `θ` 映射成 `u`，
于是"Suppose u and v are functions"变成"u and y"、`d/dx(uv)` 变成 `d/dx(uy)`。
这种损坏**不限于字母** —— 画出来的 `≤` 会变成省略号，`≠` 会变成数字 `3`。
所以**"拿转写稿和文字层对一遍"是循环论证**（错的就是文字层），
任何只建立在文字层之上的东西（让 LLM 读文本 dump、ASCII 半块渲染）都会继承全部这些错误。

文字层**可靠**的部分，可以放心用：
- **span 字号** —— 上标表现为 `size≈6.1` 的 span 紧邻 `size≈9.0` 的基底 span
  （区分 `x^2` / `x^3`、`7^-` / `7^+`）。用它来敲定有歧义的指数。
- **结构** —— 题号、页码映射、定位 `EXERCISES n.m`。
- **字体名** —— 常常就是破案线索：同一个普通拉丁字母若出自数学子集字体
  （`PearsonMATHPRO01`），而别处出自正文字体（`TimesLTPro-Italic`），那就是重编码。

字形真身要靠**看**字形、或与可信样本做形状比对：`scripts/glyphcheck.py`。
已观测到的映射表与实例见 `references/layout-pitfalls.md`。

## 工作流程

**0. 先确认自己真的能"看图"。** 拿教材第一页习题调 `read_image`。若被拒绝并报
`model "<m>" does not declare image input`，说明该模型路由**没声明 `image` 输入模态** ——
去配置里补上（**当次运行立即生效，无需重启**），**不要**因此退回 ASCII 半块渲染。
顺手确认**子代理**是否也带这个工具（通常带）。完整方法、配置行、供应商真伪探测、
以及保证文字清晰的分块与裁剪尺寸：`references/visual-verification.md`。

以下全部步骤都建立在"你能看到渲染图"之上。这不是风格偏好 ——
历史上一次全程无视觉的构建把一道多项式的**符号整体写反**、还把一道题记到了错误的页上，
而这两个错误**靠文本层交叉验证永远发现不了**，因为错的就是文本层。

**1. 定位习题集。** 逐页记录匹配 `EXERCISES\s+\d+\.\d+` 的行及印刷页码，建立
`章节 -> 页码范围` 映射，并记下页偏移（印刷页 + k = PDF 页）。
偏移量要**对着页眉核对**，不要默认是 0；至少在两页上确认。
某题"找不到"时，先把相邻页扫一遍再下结论 —— 有一次构建为
`p171 #43: NOT FOUND` 白花时间，那道题其实在 p170。

**2. 看图。** 把每页习题区以 300 dpi 渲染，**分四象限**查看（整页 300 dpi 会被降采样）。
记录子列 x 位置、图形在哪、有哪些说明横幅。
图形可能落在与该题**相反**的那一栏；题干也常常在**另一栏顶部**续写 ——
所以要通看整页，不要只看题号附近那一小块。

**3. 把每道题转写为 LaTeX。** 指数对照 span dump 核对，根号/分式对照该区域高清渲染图核对，
**每一个字母都对着字形本身核对** —— 重编码字体会让画出来的 `v` 读成 `y`。
指数、分式线、重编码字母写错是最主要的静默错误来源。

**每道题依赖的组说明必须一起带上，并且要显式核对覆盖率。** 对每条说明，列出它声称覆盖的
题号区间，确认落在区间内的每道作业题都带上了它。漏一整段说明，
在自己复查自己的转写稿时是**看不见**的 —— 这正是独立复核能抓到的失误。

**4. 图形以 400 dpi 导出 PNG。** 用"四边无墨迹"自动扩展裁剪框（`scripts/figure_box.py`）。
图形常与正文**并排** —— 必须按 x 区间隔离，否则会把文字拖进图片。
裁完**每张都要看一眼**：混进相邻题目的一行字、或从书里带进来的重复题号，都很容易误发。

**5. 量原书排版，填 STYLE BLOCK。** 成品要像从原书里撕下来的一页，所以**去量原书**，
不要凭感觉：

```powershell
python scripts/style_probe.py -i "book.pdf" -p <习题页> --latex -o .scratch/style.tex
```

把它打印出来的整块内容粘贴覆盖 `assets/hw-template.tex`（或 `hw-template-zh.tex`）的
STYLE BLOCK。脚本直接读习题页本身，量出正文衬线体与字号、强调色、横幅（标签文字、底色、
所挂细线、节号颜色）以及页眉；它会在块上面打印各项普查结果，让你看见它到底看了什么。
两个开关完全由实测决定：原书没有横幅就 `\StyleBannerfalse`，页眉下面没有细线就
`\StyleHeadRulefalse` —— *Thomas' Calculus 14e SI* 正是"有横幅、页眉无细线"，
而此前一次构建给页眉加了一条原书根本没有的红色细线。模板自带的那组值只是一份样例，
**换书绝不能照抄**。

**6. 写 `.tex`**（模板 `assets/hw-template.tex`），显式写出说明段落，编译两遍。
`\needspace` 取值要克制（§4–16 行为宜）；取 20–34 会甩出半页空白、白白多出几页。

**7. 两级校验。**
  - 先把输出 PDF 逐页渲染（200 dpi，上下半幅，避免被降采样）并**实际读完**：
    题目齐全、公式正常、无 `??`、页底无孤立标题。
  - 再**每个小节开一个子代理独立复核**：给转写稿、该小节的页位图、字形陷阱表，
    要求逐题给出 `✅ / ❌ / ⚠️ 无法判定` 的结论。方法见 `references/visual-verification.md`。
    实测 39 题的构建中，这一轮报出**零数学错误，但抓到 2 处结构性遗漏** ——
    正是转写者自己看不见的那一类问题。

**8. 呈现结果**。

## 中文教材支持

- 英文：`pdflatex` + `article`（更快，且完全不依赖 fontconfig）。
- 中文 / 中英混排：换 `xelatex` + `ctexart`，并 `tlmgr install ctex cjk xecjk zhnumber`。
  `ctex` 会自动选用 Windows 的 SimSun / SimHei，**已实测通过**：
  中文正文用宋体、公式用 Computer Modern，PDF 文字层仍可正常提取中文。
  模板见 `assets/hw-template-zh.tex`。

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

**先找本机是否已有 TeX Live —— 绝不要装第二份。** 已装但没进 `PATH` 的 TeX Live
在 `pdflatex` 看来就是"没装"，所以下结论前先把盘扫一遍：

```powershell
where.exe pdflatex
Get-ChildItem 'C:\Program Files\texlive','D:\Program Files\texlive' -ErrorAction SilentlyContinue
```

只要在任意盘、任意年份找到一份，**就不要再装**。改把它自己的 `bin\windows` 加进用户
`PATH`，并告知用户**新开一个终端**（已在运行的 shell 仍持有旧的 `PATH`）：

```powershell
$texBin = 'D:\Program Files\texlive\<year>\bin\windows'   # ← 你找到的那份
$k   = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
$cur = [string]$k.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
if (($cur -split ';') -notcontains $texBin) {
  # 保留 ExpandString —— 直接用 [Environment]::SetEnvironmentVariable 会把值降级成
  # REG_SZ，从而破坏 PATH 里任何 %VAR% 引用。
  $k.SetValue('Path', $cur.TrimEnd(';') + ';' + $texBin,
              [Microsoft.Win32.RegistryValueKind]::ExpandString)
}
$k.Close()
```

只有确实一份都没有时才安装 —— **默认装到系统软件默认位置**
（Windows 上为 `C:/Program Files/texlive/<年份>`），并尽量控制体积：

- `selected_scheme scheme-small`（或 `scheme-basic` + 少量显式宏包）。
- profile 里设 `tlpdbopt_install_docfiles 0` 与 `tlpdbopt_install_srcfiles 0`。
- 装完删除安装器。

**安装前先检查剩余空间。** 若默认盘空间不足（`scheme-small` 需预留 ≥ 4 GB），
**停下来询问用户要装到哪里**，不要擅自换盘。例外：用户明确指定位置时（如"装到 D 盘"）
按其指定执行。

完整步骤与装后修复见 `references/installing-tex-windows.md`。

## 详细资料

- **先让自己"看得见"**：`references/visual-verification.md`
- Windows 装 TeX（无需管理员）：`references/installing-tex-windows.md`
- 分栏排版陷阱与校验方法：`references/layout-pitfalls.md`
- 脚本：`scripts/crop_rect.py`（整页分块 + 按 point 裁剪，用来看图）、`scripts/figure_box.py`（图形裁剪）、
  `scripts/tex2md.py`（LaTeX → Markdown）、`scripts/glyphcheck.py`（文字层说谎时判定字形真身）、
  `scripts/style_probe.py`（量原书的字体、配色、横幅与页眉，直接打印可粘贴的 STYLE BLOCK）

## 环境备注（Windows）

- Bash 可能不可用 —— 用 PowerShell 工具；当工具返回空时，把标准输出重定向到文件再读。
- 使用托管 Python 的 venv，在其中 `pip install pymupdf`。
- `page.get_pixmap(dpi=...)` 的 dpi 必须是 **int**，不能是 float。