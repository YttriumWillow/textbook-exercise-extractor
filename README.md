# textbook-exercise-extractor

从大部头教材 PDF 中，按"章节 + 题号"的作业清单生成作业题文档的 Agent Skill。
由 *Thomas' Calculus, 14th ed. in SI Units* 的 MAT1001 Homework 1 任务沉淀而来。

An Agent Skill that turns an assignment list (`section + problem numbers`) plus a textbook
PDF into one clean document of exactly those problems, re-typeset with LaTeX.

## 目录结构 / Layout

```
textbook-exercise-extractor/
├── SKILL.md                             # 主入口（英文，规范 frontmatter）
├── SKILL.zh-CN.md                       # 中文版（同一 skill 的中文镜像）
├── README.md                            # 本文件
├── scripts/
│   ├── figure_box.py                    # 图形裁剪框自动 fit（四边无墨迹）
│   └── tex2md.py                        # LaTeX → Markdown（保留公式与 a./b./c. 小问）
├── references/
│   ├── installing-tex-windows.md        # Windows 免管理员安装 TeX Live（清华镜像）
│   └── layout-pitfalls.md               # 分栏陷阱、上标判读、校验方法
└── assets/
    ├── hw-template.tex                  # LaTeX 模板（英文，pdflatex）
    └── hw-template-zh.tex               # LaTeX 模板（中文，xelatex + ctex）
```

## 安装 / Install

把整个目录复制到技能目录即可：

- 用户级：`~/.workbuddy/skills/`
- 项目级：`<workspace>/.workbuddy/skills/`

Copy the whole folder into `~/.workbuddy/skills/` or `<workspace>/.workbuddy/skills/`.

## 做法 / How it works

- 题目按作业清单从教材**逐题转写为 LaTeX**，公式是真文本、矢量排版，可选中可搜索。
- 图形从原书 400 dpi 提取；自动扩展裁剪框直到四边无墨迹，与正文并排时按 x 区间隔离。
- 习题组说明段落（如 `Find the limits in Exercises 23–42.`）必须一起写进 `.tex`。

## 语言支持 / Language support

| 教材语言 | 做法 |
|---|---|
| 英文 | `pdflatex` + `article`（更快，无 fontconfig 依赖） |
| 中文 / 中英混排 | `xelatex` + `ctexart`（`tlmgr install ctex cjk xecjk zhnumber`）<br>已实测：SimSun/SimHei 渲染正常，中文可被正常复制 |

## 输出约定 / Output conventions

- 默认输出 **PDF**，文件名**必须带日期**：`{Course}_Homework{N}_{YYYY-MM-DD}.pdf`
  （例：`MAT1001_Homework1_2026-09-13.pdf`）
- 只有用户明确要求时才换扩展名（`.md` / `.tex` / `.docx` / `.html`），日期一律保留

## 输出格式 / Output formats

默认 PDF，可指定其他格式：

| 格式 | 依赖 | 做法 |
|---|---|---|
| **PDF**（默认） | TeX | 编译 `.tex`（英文 pdflatex / 中文 xelatex） |
| **LaTeX 源** | — | 直接交付 `.tex` |
| **Markdown** | — | `python scripts/tex2md.py hw.tex -o hw.md` |
| **DOCX** | pandoc | `pandoc hw.md -f markdown -t docx -o hw.docx` |
| **HTML** | pandoc | `pandoc hw.md -f markdown -t html5 -s --mathjax -o hw.html` |

> ⚠️ 不要让 pandoc 直接读 `.tex`：它会静默丢弃 `\instr{}` 等自定义宏的内容。
> 必须先经 `tex2md.py` 转成 Markdown。

## 依赖 / Requirements

- Python + `pymupdf`（读取与渲染 PDF；图形提取需要它）
- TeX：`pdflatex` 足够处理英文；中文需 `xelatex` + `ctex`
  - 默认装到系统软件目录 `C:/Program Files/texlive/<year>`，`scheme-small`
  - 装前检查剩余空间（预留 ≥ 4 GB），不足则**停下来询问用户**
- pandoc（**仅** DOCX / HTML 输出需要；用户没提就不要装）

## 参考输出 / Reference output

MAT1001 Homework 1：46 道题 → 7 页 PDF（约 7 000 个可选字符，9 张函数图像取自原书）；
同源 Markdown 174 行。