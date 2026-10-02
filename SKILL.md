---
name: textbook-exercise-extractor
description: "Build a homework/problem-set PDF from a large textbook PDF, given an assignment list of section + problem numbers (e.g. \"2.2: #1, 4(a)-(e), 9...\"). Re-typesets the problems with LaTeX so formulas become real selectable vector text. Always also pull in the exercise-set instruction paragraph each problem depends on. Use when a user hands over a homework list and a textbook PDF, or asks to collect textbook problems into one PDF."
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

Inside a maths formula the boxes are shifted *without* a consistent offset, so an operator's
reported x/y is meaningless — the `-` and the `t` of one expression have been seen reporting
identical x. Only plain-text-font glyphs (`TimesLTPro-*` here) have trustworthy positions; read
the problem-number span's `x` to decide which sub-column a problem is in, never the formula's.

**The text layer also lies about *which character* a glyph is.** Subset fonts are often
re-encoded, so `get_text()` reports a different symbol than the one drawn. On *Thomas' Calculus
14e SI* the maths font maps a drawn italic `v` to the codepoint `y` and a drawn `\theta` to `u`,
which silently turns "Suppose u and v are functions" into "u and y" and `d/dx(uv)` into
`d/dx(uy)`. The corruption is not confined to letters — a drawn `\le` comes back as an ellipsis
and a drawn `\ne` as the digit `3`. Checking a transcription against the text layer is therefore
circular, and anything built only on the text layer — an LLM reading a transcript, an ASCII-art
renderer — inherits every one of those errors.

The text layer *is* reliable for:
- **Span sizes** — a superscript is a `size≈6.1` span next to a `size≈9.0` base span
  (`x^2` vs `x^3`, `7^-` vs `7^+`). Use it to settle ambiguous exponents.
- **Structure** — problem numbering, page mapping, and locating `EXERCISES n.m`.
- **Font names** — often the tell. A plain Latin letter drawn from a maths subset font
  (`PearsonMATHPRO01`) while the same letter elsewhere comes from the text font
  (`TimesLTPro-Italic`) means the codepoint is a re-encoding.

For character identity, look at the glyph or compare its shape against a specimen you already
trust: `scripts/glyphcheck.py`. Observed mappings, both automated tests and worked examples are
in `references/layout-pitfalls.md`.

## Workflow

**0. Make sure you can actually see the pages.** Call `read_image` on the PDF's first exercise
page. If it is refused with `model "<m>" does not declare image input`, the model route is
missing the `image` modality — fix the config (it takes effect immediately, no restart) rather
than falling back to ASCII art. Check whether *subagents* have the tool too; they usually do.
Full recipe, the config line, a provider control-probe, and the tile/crop sizes that keep text
legible: `references/visual-verification.md`.

Everything below assumes you can look at a rendering. This is not a stylistic preference —
a build done without it reversed the signs of a polynomial and mis-filed a problem's page, and
neither error was detectable by cross-checking the text layer, because the text layer was the
thing that was wrong.

**1. Locate the exercise sets.** For every page, log lines matching `EXERCISES\s+\d+\.\d+`
with the printed folio; build `section -> page range`. Note the offset (printed page + k = PDF page),
and **verify** it against a page header rather than assuming 0 — then confirm it on at least two
pages. When a problem is "not found", sweep the neighbouring pages before reporting it missing;
one build lost time on a `p171 #43: NOT FOUND` for a problem that was on p170.

**2. Look at the pages.** Render each exercise page at 300 dpi and view it in quadrants
(a whole-page 300 dpi image gets downsampled). Record the sub-column x positions, where the
figures are, and which instruction banners exist. Figures can sit in the *opposite* column from
their problem's stem, and a statement can continue at the top of the other column — so look at
the whole page, not just the region around the number.

**3. Transcribe each problem to LaTeX.** Cross-check exponents against the span dump,
radicals/fractions against a high-dpi render of that region, and **every single letter against
the glyph itself** — a re-encoded font makes a drawn `v` read as `y`. Mistakes on exponents,
fraction bars and re-encoded letters are the dominant source of silent errors.

**Carry the exercise-set instruction for every problem**, and check coverage explicitly: for
each instruction line, list the problem range it claims and confirm every assigned problem in
that range has its instruction present. A missing instruction paragraph is invisible when you
re-read your own transcript — this is the failure mode an independent reviewer catches.

**4. Extract figures as 400 dpi PNG.** Grow the crop box until no ink touches any border
(`scripts/figure_box.py`). Figures are often **side by side with body text** — isolate
them by x-range or you will drag text into the image. Then look at each crop: one stray line of
the neighbouring problem, or a duplicated problem number carried in from the book, is easy to
ship by accident.

**5. Write the `.tex`** with explicit instruction paragraphs (template:
`assets/hw-template.tex`) and compile twice. Keep `\needspace` modest (§4–16 lines); values in
the 20–34 range dump half a page of whitespace and add pages.

**6. Verify on two levels.**
  - Render the output pages (200 dpi, top/bottom halves so nothing is downscaled) and read them
    all: every problem present, formulas render, no `??`, no heading stranded at a page bottom.
  - Then spawn **one cross-checking subagent per section**, each given the transcript, its page
    tiles and the glyph-trap table, returning per-problem `✅ / ❌ / ⚠️ cannot determine` verdicts.
    Recipe: `references/visual-verification.md`. On a 39-problem build this found zero maths
    errors but two missing structural elements — which is exactly the class of thing the author
    of a transcript cannot see.

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

**Look for an existing TeX Live FIRST — never install a second one.** A TeX Live that is
installed but missing from `PATH` still looks "not installed" to `pdflatex`, so search the
disk before concluding anything:

```powershell
where.exe pdflatex
Get-ChildItem 'C:\Program Files\texlive','D:\Program Files\texlive' -ErrorAction SilentlyContinue
```

If one exists on any drive / any year, **do not install another.** Add its `bin\windows`
to the user `PATH` instead, and tell the user to open a **new** terminal (an already-running
shell keeps the old `PATH`):

```powershell
$texBin = 'D:\Program Files\texlive\<year>\bin\windows'   # ← the one you found
$k   = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
$cur = [string]$k.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
if (($cur -split ';') -notcontains $texBin) {
  # keep ExpandString — a plain [Environment]::SetEnvironmentVariable call can
  # downgrade the value to REG_SZ and break any %VAR% inside PATH.
  $k.SetValue('Path', $cur.TrimEnd(';') + ';' + $texBin,
              [Microsoft.Win32.RegistryValueKind]::ExpandString)
}
$k.Close()
```

Only if nothing is found, install — **default target is the OS standard location**
(`C:/Program Files/texlive/<year>` on Windows) — and keep it small:

- `selected_scheme scheme-small` (or `scheme-basic` + a few explicit packages).
- `tlpdbopt_install_docfiles 0` / `tlpdbopt_install_srcfiles 0` in the profile.
- Delete the installer afterwards.

**Check free space before installing.** If the default drive does not have enough room
(allow ≥ 4 GB for `scheme-small`), **stop and ask the user where to install** — do not
silently fall back to another drive. Exception: install elsewhere when the user says so
explicitly (e.g. "install on D:").

Full steps and post-install fixes: `references/installing-tex-windows.md`.

## Details

- **Getting and using a vision tool (read this first)**: `references/visual-verification.md`
- Installing TeX on Windows (no admin): `references/installing-tex-windows.md`
- Column layout traps, verification recipes: `references/layout-pitfalls.md`
- Scripts: `scripts/crop_rect.py` (page tiles + point-box crops, for looking at pages),
  `scripts/figure_box.py` (figure crops), `scripts/tex2md.py` (LaTeX → Markdown),
  `scripts/glyphcheck.py` (settle what a glyph really is when the text layer lies)

## Environment notes (Windows)

- Bash may be broken — use the PowerShell tool and redirect stdout to a file when it returns nothing.
- Figure extraction needs PyMuPDF: `pip install pymupdf`. Use the harness's managed venv if
  it provides one, otherwise the plain interpreter works fine (verified on Python 3.12 +
  pymupdf 1.28.2).
- `page.get_pixmap(dpi=...)` requires an **int**, not a float.