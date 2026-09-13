---
name: textbook-exercise-extractor
description: Build a homework/problem-set PDF from a large textbook PDF, given an assignment list of section + problem numbers (e.g. "2.2: #1, 4(a)-(e), 9..."). Re-typesets the problems with LaTeX so formulas become real selectable vector text. Always also pull in the exercise-set instruction paragraph each problem depends on. Use when a user hands over a homework list and a textbook PDF, or asks to collect textbook problems into one PDF.
agent_created: true
---

# Textbook Exercise Extractor

Given an assignment list (`section + problem numbers`) and a textbook PDF, produce one PDF
containing exactly those problems, re-typeset with LaTeX so formulas become real selectable
vector text.

**Always also include the exercise-set instruction a problem depends on.** Without
`Limits of quotients — Find the limits in Exercises 23–42.` the reader cannot tell what a
bare `23.` is asking for. This is the single most common way these builds go wrong.

## Output conventions (user rule)

**Default format is PDF, and the filename must carry a date.**

```
{Course}_Homework{N}_{YYYY-MM-DD}.pdf      e.g. MAT1001_Homework1_2026-09-13.pdf
```

- Derive the date from the current session date, not from the file's mtime.
- Only use another extension (`.md`, `.tex`, `.docx`, `.html`) when the user explicitly
  asks for that format; keep the date in the name either way.
- If a previous build exists without a date, rename it to the dated form.

## Install only what is needed (user rule)

Do not install conversion tooling speculatively. `pandoc` is **only** installed when the
user actually asks for DOCX/HTML output; PDF / LaTeX-source / Markdown need no pandoc.
Same for TeX packages — add them via `tlmgr` when a build fails, not ahead of time.

## Workspace discipline (user rule — applies to every task)

Never write scratch files into the workspace root. Create one scratch dir first
(`<workspace>/.scratch/` or `<workspace>/<job>_build/`) and put every probe script, log,
dump, profile, and intermediate PDF in it. Only the final deliverable (and an
optional small source folder such as `hw1_build/`) belongs at the root. Delete the scratch
dir when done; large downloads go to `$env:TEMP` and are removed after use.

## Core principle: do not trust the PDF text layer for positions

In many typeset books (LaTeX / InDesign exports) span and line bounding boxes are shifted by
20–40 pt for some paragraphs, so locating a problem by its `"23."` marker silently selects the
wrong problem. For anything positional use **200 dpi grayscale ink profiles as ground truth**
when locating figures.

The text layer *is* reliable for:
- **Characters and superscripts** — a superscript is a `size≈6.1` span next to a `size≈9.0`
  base span (`x^2` vs `x^3`, `7^-` vs `7^+`). Use it to settle ambiguous exponents.
- Finding the exercise-set headings (`EXERCISES n.m`).

## Workflow

**1. Locate the exercise sets.** For every page, log lines matching `EXERCISES\s+\d+\.\d+`
with the printed folio; build `section -> page range`. Note the offset (printed page + k = PDF page).

**2. Look at the pages.** Render each exercise page at ~130 dpi and view it. Record the number
of columns, where the figures are, and which instruction banners exist. This tells you what
to transcribe and what figures to extract.

**3. Transcribe each problem to LaTeX.** Cross-check exponents against the span dump and
radicals/fractions against a high-dpi render of that region. Mistakes on exponents and
fraction bars are the dominant source of silent errors.

**4. Extract figures as 400 dpi PNG.** Grow the crop box until no ink touches any border
(`scripts/figure_box.py`). Figures are often **side by side with body text** — isolate
them by x-range or you will drag text into the image.

**5. Write the `.tex`** with explicit instruction paragraphs (template:
`assets/hw-template.tex`) and compile twice.

**6. Verify** by rendering the output pages and reading them: every problem present,
formulas render, no `??`, no heading stranded at a page bottom.

**7. Present the result.**

## Language support (CJK textbooks)

- English: `pdflatex` + `article` (fast, no fontconfig dependency).
- Chinese / mixed CJK: switch to `xelatex` + `ctexart`, then
  `tlmgr install ctex cjk xecjk zhnumber`. `ctex` picks the Windows system CJK fonts
  (SimSun / SimHei) automatically — verified working. Template: `assets/hw-template-zh.tex`.
- Mixed CJK + maths renders correctly: CJK body text in SimSun, maths in Computer Modern,
  and the PDF text layer still extracts the Chinese as real text.

## Output formats

Ask which one the user wants; default to PDF.

| Format | How |
|---|---|
| **PDF** (default) | compile the `.tex` — `pdflatex` (English) or `xelatex` (CJK) |
| **LaTeX source** | the `.tex` itself — hand it over so the user can edit |
| **Markdown** | `scripts/tex2md.py` — keeps `$…$` / `$$…$$`, turns sub-items into `a. b. c.` |
| **DOCX / HTML** | `tex2md.py` → `pandoc -f markdown -t docx` (or `-t html5 -s --mathjax`) |

Pandoc's **LaTeX reader silently drops custom macros** (it threw away every `\instr{}`
paragraph), so never point pandoc straight at the `.tex` — always go through
`tex2md.py` first.

Pandoc is not required for PDF / LaTeX-source / Markdown. **Install it only after the user
explicitly asks for DOCX or HTML** — see "Install only what is needed" above.

```powershell
python scripts/tex2md.py hw1.tex -o hw1.md
pandoc hw1.md -f markdown -t docx  -o hw1.docx
pandoc hw1.md -f markdown -t html5 -s --mathjax -o hw1.html
```

## Installing TeX (user rule)

**Default target is the OS standard location** — `C:/Program Files/texlive/<year>` on
Windows — and keep it small:

- `selected_scheme scheme-small` (or `scheme-basic` + a few explicit packages).
- `tlpdbopt_install_docfiles 0` / `tlpdbopt_install_srcfiles 0` in the profile.
- Delete the installer afterwards.

**Check free space before installing.** If the default drive does not have enough room
(allow ≥ 4 GB for `scheme-small`), **stop and ask the user where to install** — do not
silently fall back to another drive. Exception: install elsewhere when the user says so
explicitly (e.g. "install on D:").

Full steps and post-install fixes: `references/installing-tex-windows.md`.

## Details

- Installing TeX on Windows (no admin): `references/installing-tex-windows.md`
- Column layout traps, verification recipes: `references/layout-pitfalls.md`
- Scripts: `scripts/figure_box.py` (figure crops), `scripts/tex2md.py` (LaTeX → Markdown)

## Environment notes (Windows)

- Bash may be broken — use the PowerShell tool and redirect stdout to a file when it returns nothing.
- Use the managed Python venv and `pip install pymupdf` there.
- `page.get_pixmap(dpi=...)` requires an **int**, not a float.