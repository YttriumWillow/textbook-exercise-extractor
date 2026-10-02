# Column layout traps and verification recipes

Observed on *Thomas' Calculus, 14th ed. in SI Units* (Pearson/LaTeX export), but the same
structure shows up in most two-column maths textbooks.

## Layout patterns

- The exercise area is **two columns**; short "find the limit" items are then laid out
  **two-up inside each column**, so the page is effectively 4 mini-columns.
  Odd/even problem numbers are paired side by side (`23` `24`, `39` `40`, ...).
  Split them by x, otherwise one crop contains two problems.

  Measured on *Thomas' Calculus 14e SI* (page 612 × 783 pt), the four sub-column start x are:

  | page parity | left column | right column |
  |---|---|---|
  | even (verso) | **30**, 153 | **306**, 429 |
  | odd  (recto) | **54**, 177 | **330**, 453 |

  The 24 pt offset is the binding margin (recto pages have the wider inner margin). Odd numbers
  take the left sub-column of a column, even numbers the right one. When only the y of the
  problem number is known, `x` is what tells you which sub-column — so read `x` from the
  problem-number span (a `TimesLTPro-Bold` glyph, therefore trustworthy) and not from the
  formula next to it.

- Some problems' `a.`/`b.` sub-items **straddle** the mini-column boundary
  (e.g. `17. a. ... b. ...` runs across the whole left column). For those, use the
  full column x-range, not the mini-column.
- **A problem's tail can continue in the other column, or on the next page.** In one build,
  problem 26's statement ended at the bottom of the left column on p151 and *finished at the
  top of the right column on the same page* — the right column's first two lines belonged to
  26, not to the 27 below them. A crop of "the left column around y=690" showed the sentence
  apparently stopping mid-clause. Before declaring a statement complete, follow the column
  flow: bottom of left column → top of right column → next page's left column. Text-layer
  order does **not** follow this flow, so use it only to confirm, never to discover.
- Figures are **vector art** — only a y band (plus x range) can find them; text blocks
  alone are useless.
- Figures are often **beside** body text: in 2.2 #3 the `h.`–`k.` items sit to the left of
  the graph at the same y. Isolate the figure by x-range or the text ends up inside the image.
- **A figure may sit in the opposite column from its problem statement.** p149 puts problem
  15's stem at the bottom of the left column, the velocity graph at the *top of the right
  column*, and 15's `a.`–`d.` items directly under that graph — squeezed between it and
  problem 16. Do not assume "the figure is just below the stem"; sweep the whole page and
  match the figure's caption/axis labels against what the stem promises.
- Tall fractions / radicals can make a row look blank to a naive threshold — always use
  "run of blank rows" and an explicit per-job y-floor / y-ceiling.

## Ink profile recipe

```python
THRESH = 205                      # pixel value below this counts as ink
GAP_FRAC = 0.012                  # row is blank if ink pixels <= GAP_FRAC * strip width
th = max(2, int(GAP_FRAC * width_px))

pix = page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY, clip=Rect(x0, 0, x1, pageH))
counts = [sum(1 for v in row if v < THRESH) for row in rows]
# print maximal runs of (blank | ink) with their y in PDF points
```

Read the runs and take `y0`/`y1` from *inside* blank runs. Then confirm the mapping by
looking at the rendered page — never by marker coordinates.

## Reading superscripts (settling `x^2` vs `x^3`)

Dump spans for the region with `page.get_text("dict", clip=rect)` and print
`(size, y, x, text)`. A superscript shows up as a `size≈6.1` span next to a `size≈9.0` base:

```
size=9.0 y=97.45 x=353.68 'x'
size=6.1 y=96.93 x=357.87 '2'      ->  x^2
```

Radicals are font-mapped oddly: `A` ≈ ∛, `2` (size 8.1) ≈ √, `>` ≈ the fraction slash.
Confirm against a high-dpi render whenever the exponent matters.

Real examples that were mis-read at low resolution:
- 2.6 #23 is `∛((8x²−3)/(2x²+x))` — **x²**, not x³.
- 2.6 #43 is `lim_{x→7} 4/(x−7)²` — a **two-sided** limit, no `+`/`−` superscript.
  2.6 #39 is the one-sided `lim_{x→2⁻} 3/(x−2)`.

## The text layer lies about characters too (re-encoded subset fonts)

Span *sizes* are trustworthy; the *character* attached to a glyph is not. Subset fonts ship with
their own cmap, and on *Thomas' Calculus 14e SI* the maths subset (`PearsonMATHPRO01`) is
re-encoded, so `get_text()` confidently reports the wrong symbol:

| drawn glyph | `get_text()` says | what it silently corrupts |
|---|---|---|
| italic `v` | `y` | "Suppose u and **v** are functions" → "u and y"; `d/dx(uv)` → `d/dx(uy)`; `v(0) = -1` → `y(0) = -1` |
| `θ` | `u` | `r = ((θ−1)(θ²+θ+1))/θ³` → `r = ((u−1)(u²+u+1))/u³` |
| `π` | `p` | `x₀ = π/2` → `x0 = p>2` |
| `√` | `2` (size ≈8.1) | `y = √(3x−1)` → `y = 2x − 1` |
| fraction slash `/` | `>` | `x^{1/5}` → `x1>5` |
| `(`, `)` | `a`, `b` | `w = ((1+3z)/3z)(3−z)` → `w = a1 + 3z ... b(3 - z)` |
| `∛` | `A` | `∛(...)` → `A(...)` |
| `≤` | `…` (U+2026) | `0 ≤ t ≤ 3` → `0 … t … 3` |
| `≠` | `3` | `m a constant ≠ 0` → `m a constant 3 0` |

This is worse than the positional shift, because it fails *silently* and it fails for every
consumer of the text: an LLM given a text dump, a diff against the extracted text, an ASCII-art
renderer. **Verifying a transcription against the text layer is circular** — the text layer is
what is wrong.

Note that the traps are not limited to letters: a relational operator can come back as a
*completely unrelated* codepoint (`≤` → an ellipsis, `≠` → a digit). So "it extracted as a
plausible maths character" is not evidence that it is the right one.

### Bounding boxes inside the maths font are shifted too

The re-encoding also displaces the glyph boxes. Inside a formula, spans from
`PearsonMATHPRO*` can land on coordinates that do not match where the ink is drawn — the `-`
and the `t` of one expression have been observed reporting *identical* x. So:

- **Only `TimesLTPro-*` (plain text font) glyph positions are trustworthy.**
- Never locate an operator, a fraction bar, or a radical by its reported x/y.
- Sizes remain usable (superscript detection still works); it is position *of maths glyphs*
  that is unsafe.

Practical consequence: to crop a tight box around a formula, pick the box from a **render**, or
from the surrounding trustworthy text span — never from the coordinates of the maths span itself.

### How to settle a letter

The trap is systematic per font, so the fix is mechanical. Two tests decide almost every case,
and `scripts/glyphcheck.py` implements both:

1. **Descender test** (`glyphcheck.py chars`) — a `y` has a descender, a `v` does not. The tool
   prints, per character, the fraction of ink below the baseline. In the real case:
   suspect reported `y` → `desc=0.01`, font `PearsonMATHPRO01` → *flagged, no descender*;
   a genuine `y` (`y = x³ + 7`) → `desc=0.32`, font `TimesLTPro-Italic`.
   It also flags the inverse (a letter that is not `y g p q j` but *does* have a descender).
2. **Shape match** (`glyphcheck.py match`) — rasterise the suspect and a specimen of the claimed
   letter, normalise by font size and anchor both on the baseline, then take the IoU. Keep the
   baseline anchor: cropping to the ink and stretching to a square destroys exactly the cue that
   separates `v` from `y`. Measured on the real case: two genuine italic `y`s → **IoU 1.00**;
   the suspect (really a `v`) against genuine italic `y`s → **IoU 0.23**.

When no trustworthy specimen exists (the font may map *every* `v` to `y`, so you cannot find a
reference by searching for `v`), fall back to shape reasoning plus the font name:
- `v` sits on the baseline, no descender; `θ` has a crossbar; both are "what else could it be"
  obvious once seen. `glyphcheck.py sheet` renders the suspect next to references for a look.
- Compare **font names** across the page: in this book a genuine Latin letter in the same context
  comes from `TimesLTPro-Italic` (155 italic `y` and 32 `u` across the nine exercise pages
  sampled), while the re-encoded ones come from `PearsonMATHPRO01` on those same pages (28 `y`
  that are really `v`, 20 `u` that are really `θ`). Operators legitimately use the maths font;
  a *plain letter* using it is the anomaly.

Sizes and positions stay usable for exponents throughout — it is only identity that is unsafe.

### Real cases from the MAT1001 Homework 2 build

| problem | text layer / first pass produced | actually printed |
|---|---|---|
| 3.3 #21 | `y = (1−t)(1+t²)⁻¹` | `v = (1−t)(1+t²)⁻¹` |
| 3.3 #35 | `r = ((u−1)(u²+u+1))/u³` | `r = ((θ−1)(θ²+θ+1))/θ³` |
| 3.3 #39 | "Suppose `u` and `y` are functions", `d/dx(uy)` | "Suppose `u` and `v`", `d/dx(uv)`, `d/dx(u/v)`, `d/dx(v/u)`, `d/dx(7v−2u)` |

Three near-misses that the same pass confirmed as *correct* — do not "fix" these: 3.3 #29 really
is `x⁴/2 − (3/2)x² − x`; 3.3 #17 really is `(2x+5)/(3x−2)`; 3.1 #23's stem really does read
"The number after t hours is shown in the accompanying figure."

### Real cases from the MAT1001 Homework 3 build (visual pass, 39 problems)

This build was done **with** a working vision tool, and is the reference for how accurate a
visual pass is: four reviewer subagents independently checked every problem and found **zero
maths errors**. The interesting part is what the *previous, vision-less* pass had got wrong:

| problem | vision-less record | actually printed |
|---|---|---|
| 3.4 #3 | `s = t³ − 3t² + 3t` | **`s = −t³ + 3t² − 3t, 0 ≤ t ≤ 3`** — signs reversed throughout |
| 3.7 #43 | "p171, `NOT FOUND`" | on **p170**; p171's banner is 3.8 Related Rates |
| 3.4 #15 | figure location unrecorded | stem at the bottom of p149's *left* column, graph at the top of its *right* column, `a.`–`d.` under the graph |
| 3.4 #26 | statement recorded as truncated | continues at the **top of p151's right column**: "…for males of constant height h = 180 cm. Does S increase more rapidly…" |

Both of the first two are invisible to any text-layer cross-check — the signs came back
"plausibly" wrong, and "not found" is a false negative you only disprove by looking. That is the
whole argument for §0 of `references/visual-verification.md`.

The same build also confirmed a genuine **printing defect** worth leaving alone: the 3.6
instruction really is printed as
`In Exercises 1–8, given y = f(u) and u = g(x), find dy/dx = dy/dx = f'(g(x))g'(x).`
— `dy/dx =` is duplicated in the book. Verified at 600 dpi; reproduce it, do not silently fix it,
and note it in the delivery notes so the user does not think you made a typo.

## Figure crop box

Start from a candidate box inside the figure, then grow it (1 pt per side per iteration,
capped by an allowed region) until no border has ink within ~1.6 pt:

```python
box = figure_box(doc, page_index, init=(128,196,250,250), limit=(118,190,258,254))
save_fig(doc, page_index, box, "fig/f22_1.png", dpi=400)
```

The `limit` is what stops the box from swallowing the neighbouring problem — always set it.
Use `min_ink>=2` when probing borders, otherwise single antialiased pixels make it grow forever.

### Two things to look at in every crop before you ship it

1. **Stray text from the neighbouring problem.** A figure that sits in a column has body text
   above and below it, and one extra line of that text ruins the image. Crop, then *look*:
   a strip reading "...the body reverse direction?" above a velocity graph, or
   "...shown here." above a curve, means the y band is one line too generous. Trim and re-check.
   Do not rely on the auto-fit alone — the gap between a figure and the next text line can be
   smaller than the ink threshold's tolerance.
2. **The problem number printed inside the image.** These books print the bold number *above*
   each figure. If your `.tex` already emits `\prob{47.}`, the cropped image carrying its own
   "47." duplicates the label and looks like a mistake. Either crop above the number
   (check that you are not clipping the y-axis arrow — the number and the axis often overlap in
   x, so trim in **y** only) or accept it deliberately.

Verified boxes from a 39-problem build (PDF points, page 612 × 783), as starting points:

| figure | page | x0 y0 x1 y1 |
|---|---|---|
| velocity graph | 149 | 398 60 518 151 |
| three-curve A/B/C graph | 150 | 383 448 502 617 |
| curve with tangents at P and Q | 157 | 50 110 172 250 |
| 365-day temperature curve | 165 | 76 315 310 437 |
| figure-eight curve | 170 | 96 556 218 688 |

## Verification (do not skip)

1. **Crop contact sheet**: 3-column grid of every crop at ~72 dpi, one JPEG. Look for
   wrong problem numbers, cut headings, missing last lines, missing `a.`/`b.` halves.
2. **Zoom sheet** for anything ambiguous: render the region at ≥900 px wide.
3. **Read the final PDF pages** — render at 150–200 dpi, split each page into top/bottom halves
   so nothing is downscaled, and actually view each page. Check: every problem present, numbering
   continuous, formulas render, no `??`, no heading stranded at a page bottom, figures clear and
   correctly placed.
4. **Independent cross-check by subagents** — one per section, each given the transcript, the
   page tiles and the glyph-trap table, returning a per-problem `✅ / ❌ / ⚠️` verdict.
   Recipe and rationale: `references/visual-verification.md`.

A useful self-check before step 3: extract the text of the finished PDF and assert that every
problem's number and a distinctive fragment of its statement appears on some page. Cheap, and it
catches a problem that silently failed to make it into the `.tex`:

```python
full = ' '.join(p.get_text() for p in pymupdf.open("hw.pdf"))
for frag in ["43. The eight", "86. Temperatur", "53. lim", "61. By computi"]:
    assert frag in full, frag
```

## Typesetting keepsakes

- `\needspace{n\baselineskip}` before a heading/instruction block stops it from being
  stranded at the bottom of a page away from its problems (needed ≈12 for a heading +
  2 short problems, ≈26 for a block with two display formulas).
- **Do not over-reserve.** The obvious failure of too small a `\needspace` is a stranded
  heading; the less obvious one is that too large a value dumps half a page of whitespace. A
  7-page build went to 8 pages with ~50 % blank areas on three pages because several long
  problems carried `\needspace{30}`–`\needspace{34}`. Measured sweet spot:

  | block | `\needspace` |
  |---|---|
  | a heading + instruction, or a one-line problem | 8–12 |
  | a normal multi-line problem | 10–13 |
  | a problem that must not be split from its figure | 14–16 |
  | a section heading (so the first problem follows it) | 20–24 |

  `\needspace` reserves space *for the next `n` lines*, not for the whole block — a 40-line
  problem with `\needspace{13}` still breaks across pages, which is correct and desirable.
- Put a modest `\needspace` inside the `\prob` macro itself (≈4 lines) so a bare number never
  lands on the last line of a page.
- Numeric data tables (e.g. "the functions have the following values at x = 0 and x = 1") need
  their own environment so they stay centred and independent of the surrounding list spacing:

  ```latex
  \newenvironment{dtable}%
    {\par\smallskip\centering$\begin{array}{@{}c@{\hspace{1.6em}}c@{\hspace{1.6em}}c@{}}}%
    {\end{array}$\par\smallskip}
  ```

  and a `\needspace` on the *problem*, so the stem, its table and its sub-items do not separate.
- Prefer laying sub-items as a vertical `enumerate` rather than reproducing the book's
  two-up layout — it reads better and never collides.
- Compile **twice** and assert the log is clean: `grep -c Overfull hw.log` should print `0`.
- A 7-page, 39-problem set typeset this way yields ~28 000 bytes of PDF with ~7 000 characters
  of selectable text.
