# Column layout traps and verification recipes

Observed on *Thomas' Calculus, 14th ed. in SI Units* (Pearson/LaTeX export), but the same
structure shows up in most two-column maths textbooks.

## Layout patterns

- The exercise area is **two columns**; short "find the limit" items are then laid out
  **two-up inside each column**, so the page is effectively 4 mini-columns.
  Odd/even problem numbers are paired side by side (`23` `24`, `39` `40`, ...).
  Split them by x, otherwise one crop contains two problems.
- Some problems' `a.`/`b.` sub-items **straddle** the mini-column boundary
  (e.g. `17. a. ... b. ...` runs across the whole left column). For those, use the
  full column x-range, not the mini-column.
- Figures are **vector art** — only a y band (plus x range) can find them; text blocks
  alone are useless.
- Figures are often **beside** body text: in 2.2 #3 the `h.`–`k.` items sit to the left of
  the graph at the same y. Isolate the figure by x-range or the text ends up inside the image.
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

This is worse than the positional shift, because it fails *silently* and it fails for every
consumer of the text: an LLM given a text dump, a diff against the extracted text, an ASCII-art
renderer. **Verifying a transcription against the text layer is circular** — the text layer is
what is wrong.

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

## Figure crop box

Start from a candidate box inside the figure, then grow it (1 pt per side per iteration,
capped by an allowed region) until no border has ink within ~1.6 pt:

```python
box = figure_box(doc, page_index, init=(128,196,250,250), limit=(118,190,258,254))
save_fig(doc, page_index, box, "fig/f22_1.png", dpi=400)
```

The `limit` is what stops the box from swallowing the neighbouring problem — always set it.
Use `min_ink>=2` when probing borders, otherwise single antialiased pixels make it grow forever.

## Verification (do not skip)

1. **Crop contact sheet**: 3-column grid of every crop at ~72 dpi, one JPEG. Look for
   wrong problem numbers, cut headings, missing last lines, missing `a.`/`b.` halves.
2. **Zoom sheet** for anything ambiguous: render the region at ≥900 px wide.
3. **Read the final PDF pages** — render at 150 dpi and actually view each page.

## Typesetting keepsakes

- `\needspace{n\baselineskip}` before a heading/instruction block stops it from being
  stranded at the bottom of a page away from its problems (needed ≈12 for a heading +
  2 short problems, ≈26 for a block with two display formulas).
- Prefer laying sub-items as a vertical `enumerate` rather than reproducing the book's
  two-up layout — it reads better and never collides.
- A 7-page, 46-problem set typeset this way yields ~7 000 characters of selectable text.
