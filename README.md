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

把整个目录复制到**宿主 harness 的技能目录**即可。两个 harness 的路径不同，别装错：

| Harness | 用户级（所有工作区） | 项目级（仅该项目） |
|---|---|---|
| **dsh** | `~/.dsh/skills/` | `<项目根>/.dsh/skills/` |
| workbuddy | `~/.workbuddy/skills/` | `<workspace>/.workbuddy/skills/` |

Copy the whole folder into `~/.dsh/skills/` or `<project>/.dsh/skills/` (dsh), or
`~/.workbuddy/skills/` / `<workspace>/.workbuddy/skills/` (workbuddy).

dsh 侧补充：

- dsh 只扫描这些根目录的**顶层**——目录包 `<name>/SKILL.md` 或平铺 `<name>.md`；
  刻意为不递归查找嵌套的 `SKILL.md`，所以别把 skill 再套一层子目录。
- `<项目根>` 指最近的含 `.git` 的祖先目录；找不到就用当前工作目录。
- 装好后可用 `skill_search` 确认能被发现，再用 `skill_load` 加载正文。
- dsh 还支持 `.agents/skills/`（项目级与用户级），优先级低于上面的 `.dsh/skills/`。

### frontmatter 约定 / Frontmatter rules

| 键 | 说明 |
|---|---|
| `name` | 必填，小写字母/数字/连字符 |
| `description` | 必填，模型据此判断何时加载该 skill |
| `whenToUse` / `metadata` | 可选 |
| `disable-model-invocation` / `user-invocable` | 可选，YAML 布尔值 |

⚠️ **dsh 用严格 YAML 解析 frontmatter，解析失败会把整个 skill 静默丢弃**（只在日志里
warn 一行）。常见坑：`description` 里出现 `": "` 或 `" #"`（例如 `如 "2.2: #1"`），
未加引号的 plain scalar 会解析失败 —— 必须写成双引号标量，内部引号转义为 `\"`：

```yaml
description: "…（如 \"2.2: #1, 4(a)-(e), 9...\"）…"
```

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

- Python + PyMuPDF：`pip install pymupdf`（读取与渲染 PDF、图形提取都需要它）
- TeX：`pdflatex` 足够处理英文；中文需 `xelatex` + `ctex`
  - **装前先确认本机是否已有 TeX Live** —— 已装但没进 `PATH` 的情况很常见，那也算已装：
    `where.exe pdflatex`，再查 `C:\Program Files\texlive`、`D:\Program Files\texlive`
  - 已有就把它的 `bin\windows` 加进用户 `PATH` 即可，**不要重复安装**（脚本见 SKILL.md）
  - 确需安装时装到系统软件目录 `C:/Program Files/texlive/<year>`，`scheme-small`
  - 装前检查剩余空间（预留 ≥ 4 GB），不足则**停下来询问用户**
- pandoc（**仅** DOCX / HTML 输出需要；用户没提就不要装）

## 参考输出 / Reference output

MAT1001 Homework 1：46 道题 → 7 页 PDF（约 7 000 个可选字符，9 张函数图像取自原书）；
同源 Markdown 174 行。