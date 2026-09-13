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
