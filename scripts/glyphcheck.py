# -*- coding: utf-8 -*-
"""glyphcheck — settle what a glyph actually IS when the PDF's text layer lies.

WHY THIS EXISTS
---------------
Some textbooks (Pearson LaTeX/InDesign exports in particular) ship **subset fonts
whose cmap is re-encoded**: the glyph that is drawn is not the character the text
layer reports. Observed on *Thomas' Calculus, 14th ed. in SI Units*:

    drawn        reported by get_text()      consequence if trusted
    ---------    -----------------------     ------------------------------------
    v (italic)   'y'                         "Suppose u and y are functions"  (is v)
    theta        'u'                         r = ((u-1)(u^2+u+1))/u^3         (is theta)
    pi           'p'                         x0 = p>2                         (is pi/2)
    radical      '2' (size ~8.1)             y = 2x - 1                       (is sqrt)
    fraction /   '>'                         x1>5                             (is x^(1/5))
    ( ) braces   'a','b','e'                 w = a1 + 3z ... b(3 - z)         (are parens)
    cube root    'A'

So on such a file the text layer is reliable for *structure* (numbering, page
positions, span sizes that reveal super/subscripts) but **not for character
identity**. Anything derived only from the text layer — including an LLM reading a
transcript of it, or an ASCII-art renderer — silently inherits the wrong symbol.

Verifying against the text layer is therefore circular. You must look at the glyph,
or compare its shape against a glyph of known identity.

MODES
-----
  chars   per-character dump: codepoint, bbox, size, font, and a **descender test**
          (does the ink fall below the baseline?). A v/y mix-up is decided instantly:
          y has a descender, v does not.
  sheet   labelled side-by-side high-dpi crops -> one PNG, for looking at with vision.
  match   numeric shape comparison (IoU of normalised ink) of a suspect glyph against
          reference glyphs, for sessions that have no image tool.

CROP SPEC (used by sheet/match)
-------------------------------
  <label>:<page>:search:<phrase>            whole matched phrase
  <label>:<page>:char:<phrase>:<index>      one character of the match (0-based)
  <label>:<page>:box:<x0,y0,x1,y1>          explicit rect in PDF points

`<page>` is a 0-based page index. Phrases must not contain ':'.

EXAMPLES
--------
  # what does the text layer claim, and does the glyph have a descender?
  python glyphcheck.py chars BOOK.pdf --page 140 --search "u and"

  # look at the suspect glyph next to a known y and a known v
  python glyphcheck.py sheet BOOK.pdf -o cmp.png --dpi 1200 \
      --crop "suspect:140:char:u and ? are:6" \
      --crop "known-y:140:char:y = x3 + 7:0" \
      --crop "known-v:140:search:derivatives"

  # no vision in this session? ask for numbers
  python glyphcheck.py match BOOK.pdf \
      --suspect "suspect:140:char:u and ? are:6" \
      --against "known-y:140:char:y = x3 + 7:0" \
      --against "known-v-roman:140:search:derivatives"

Requires PyMuPDF. Console note: run with PYTHONIOENCODING=utf-8 on Windows (GBK
consoles mangle or crash on non-ASCII), or pass --out to write a UTF-8 file.
"""
from __future__ import annotations

import argparse
import os
import sys

import pymupdf

INK_THRESHOLD = 205          # pixel value below this counts as ink
DEFAULT_DPI = 1200
DEFAULT_PAD = 1.5            # points of padding around a glyph


# --------------------------------------------------------------------------
# glyph geometry
# --------------------------------------------------------------------------
def search_rect(page, phrase, pad=0.0):
    """Rect of the first occurrence of `phrase` on `page`, or None.

    PyMuPDF can return a multi-word phrase as several adjacent segment rects, so
    union every hit that shares the first hit's line. Hits on other lines (the same
    phrase further down the page) are deliberately excluded.
    """
    hits = page.search_for(phrase)
    if not hits:
        return None
    first = hits[0]
    r = first
    for h in hits[1:]:
        if h.y0 < first.y1 - 1 and h.y1 > first.y0 + 1:
            r = r | h
    if pad:
        r = pymupdf.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad)
    return r


def char_boxes(page, clip):
    """Every character in `clip` as (char, bbox, size, font, baseline_y)."""
    out = []
    d = page.get_text("rawdict", clip=clip)
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                baseline = span["origin"][1] if "origin" in span else None
                for ch in span.get("chars", []):
                    if ch["c"].strip() == "":
                        continue
                    out.append({
                        "char": ch["c"],
                        "bbox": pymupdf.Rect(ch["bbox"]),
                        "size": round(span["size"], 2),
                        "font": span["font"],
                        "baseline": baseline,
                    })
    return out


def glyph_pixmap(page, rect, dpi=DEFAULT_DPI, pad=DEFAULT_PAD):
    """Rasterise one glyph/rect at high dpi, grey, no antialias surprises."""
    clip = pymupdf.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
    return page.get_pixmap(dpi=dpi, clip=clip, colorspace=pymupdf.csGRAY)


def ink_rows(pix):
    """Row indices (top-down) that contain ink."""
    w, h, st, buf = pix.width, pix.height, pix.stride, pix.samples
    rows = []
    for r in range(h):
        row = buf[r * st:r * st + w]
        if min(row) < INK_THRESHOLD:
            rows.append(r)
    return rows


def descender_ratio(page, box, dpi=600):
    """Fraction of the glyph's ink height that sits below the baseline.

    ~0.00-0.05  -> no descender  (v w x z a c e m n o r s u ...)
    clearly >0  -> descender     (y g p q j)
    Returns None when the baseline is unknown.
    """
    if box.get("baseline") is None:
        return None
    pix = glyph_pixmap(page, box["bbox"], dpi=dpi, pad=0.0)
    rows = ink_rows(pix)
    if not rows:
        return None
    top, bottom = rows[0], rows[-1]
    # PDF y grows upward, raster y grows downward; the clip starts at bbox.y0
    baseline_px = (box["baseline"] - box["bbox"].y0) * (dpi / 72.0)
    height = bottom - top + 1
    below = max(0.0, bottom - baseline_px)
    return below / height


DESCENDER_LETTERS = set("ygpqj")


def suspect_flag(char, desc):
    """Flag a glyph whose ink shape contradicts the letter the text layer claims.

    This is the cheapest way to catch a re-encoded font: the codepoint says 'y' but
    the drawn glyph has no descender (so it is really a v), or vice versa.
    """
    if desc is None or len(char) != 1 or not char.isalpha() or not char.isascii():
        return ""
    if char in DESCENDER_LETTERS and desc < 0.10:
        return "  !! reported as a descender letter, glyph has NO descender"
    if char not in DESCENDER_LETTERS and desc > 0.15:
        return "  !! glyph HAS a descender, letter is not one of " + "".join(sorted(DESCENDER_LETTERS))
    return ""


def baseline_mask(page, info, size_px=72):
    """Shape mask normalised by font size and anchored on the baseline.

    Anchoring matters: cropping to the ink and stretching to a square (the obvious
    approach) throws away exactly the cue that separates v from y, namely how far
    the ink sits below the baseline. Here the glyph is scaled so that 1 em -> a fixed
    number of pixels and the vertical window is fixed relative to the baseline, so a
    descender stays a descender.
    """
    size = info.get("size")
    baseline = info.get("baseline")
    if not size or baseline is None:
        return None
    bbox = info["bbox"]
    # get_pixmap(dpi=...) needs an int, NOT a float (raises TypeError otherwise)
    dpi = max(1, int(round(size_px * 72.0 / size)))
    clip = pymupdf.Rect(bbox.x0 - 0.3 * size, baseline - 1.05 * size,
                        bbox.x1 + 0.3 * size, baseline + 0.45 * size)
    pix = page.get_pixmap(dpi=dpi, clip=clip, colorspace=pymupdf.csGRAY)
    w, h, st, buf = pix.width, pix.height, pix.stride, pix.samples
    scale = dpi / 72.0
    base_px = (baseline - clip.y0) * scale
    top_px = base_px - 0.85 * size_px      # fixed window: ascender .. descender
    bot_px = base_px + 0.35 * size_px
    # horizontal: crop to the ink columns so letter width does not dominate
    cols = [c for c in range(w)
            if any(buf[r * st + c] < INK_THRESHOLD for r in range(h))]
    if not cols:
        return None
    c0, c1 = cols[0], cols[-1]
    out = [[0] * size_px for _ in range(size_px)]
    for y in range(size_px):
        sy = int(top_px + (y + 0.5) * (bot_px - top_px) / size_px)
        if not (0 <= sy < h):
            continue
        for x in range(size_px):
            sx = int(c0 + (x + 0.5) * (c1 - c0 + 1) / size_px)
            if 0 <= sx < w and buf[sy * st + sx] < INK_THRESHOLD:
                out[y][x] = 1
    return out


def mask_iou(a, b):
    """Intersection over union of two ink masks (0..1)."""
    if a is None or b is None:
        return 0.0
    inter = sum(1 for y in range(len(a)) for x in range(len(a)) if a[y][x] and b[y][x])
    union = sum(1 for y in range(len(a)) for x in range(len(a)) if a[y][x] or b[y][x])
    return inter / union if union else 0.0


# --------------------------------------------------------------------------
# crop specs
# --------------------------------------------------------------------------
def parse_spec(spec):
    """'label:page:kind:arg[:index]' -> (label, page, kind, arg)."""
    parts = spec.split(":")
    if len(parts) < 4:
        raise SystemExit(f"bad crop spec: {spec!r} (need label:page:kind:arg)")
    label, page, kind = parts[0], int(parts[1]), parts[2]
    if kind == "box":
        vals = [float(v) for v in parts[3].split(",")]
        if len(vals) != 4:
            raise SystemExit(f"box spec needs x0,y0,x1,y1: {spec!r}")
        return label, page, kind, pymupdf.Rect(*vals)
    if kind == "char":
        if len(parts) < 5:
            raise SystemExit(f"char spec needs an index: {spec!r}")
        return label, page, kind, (parts[3], int(parts[4]))
    if kind == "search":
        return label, page, kind, ":".join(parts[3:])
    raise SystemExit(f"unknown crop kind {kind!r} in {spec!r}")


def resolve(doc, spec):
    """Crop spec -> (label, rect, extra info dict)."""
    label, pno, kind, arg = parse_spec(spec)
    page = doc[pno]
    if kind == "box":
        info = {"page": pno, "kind": kind}
        # enrich an explicit box with the text layer's view of the char inside it, so
        # `match` gets the font size / baseline it needs for normalisation
        best, best_area = None, 0.0
        for ch in char_boxes(page, arg):
            inter = ch["bbox"] & arg
            area = inter.get_area() if inter else 0.0
            if area > best_area:
                best, best_area = ch, area
        if best is not None:
            info.update(char=best["char"], size=best["size"], font=best["font"],
                        baseline=best["baseline"])
        return label, arg, info
    if kind == "search":
        r = search_rect(page, arg)
        if r is None:
            raise SystemExit(f"{label}: phrase not found on page {pno}: {arg!r}")
        return label, r, {"page": pno, "kind": kind, "phrase": arg}
    phrase, idx = arg
    r = search_rect(page, phrase)
    if r is None:
        raise SystemExit(f"{label}: phrase not found on page {pno}: {phrase!r}")
    chars = char_boxes(page, r)
    if idx >= len(chars):
        raise SystemExit(f"{label}: only {len(chars)} chars in {phrase!r}, asked for #{idx}")
    ch = chars[idx]
    return label, ch["bbox"], {"page": pno, "kind": kind, "char": ch["char"],
                               "size": ch["size"], "font": ch["font"],
                               "baseline": ch["baseline"]}


# --------------------------------------------------------------------------
# modes
# --------------------------------------------------------------------------
def mode_chars(doc, args, emit):
    page = doc[args.page]
    if args.search:
        rect = search_rect(page, args.search)
        if rect is None:
            raise SystemExit(f"phrase not found: {args.search!r}")
    elif args.box:
        rect = pymupdf.Rect(*[float(v) for v in args.box.split(",")])
    else:
        rect = page.rect
    emit(f"page {args.page}, region {rect}")
    emit(f"{'idx':>4} {'char':>6} {'U+':>7} {'size':>6} {'desc':>6}  font / bbox")
    for i, ch in enumerate(char_boxes(page, rect)):
        dr = descender_ratio(page, ch)
        code = "U+%04X" % ord(ch["char"])
        desc = "-" if dr is None else f"{dr:.2f}"
        emit(f"{i:>4} {ch['char']:>6} {code:>7} {ch['size']:>6} {desc:>6}"
             f"  {ch['font']} {tuple(round(v,1) for v in ch['bbox'])}{suspect_flag(ch['char'], dr)}")
    emit("")
    emit("A codepoint here is only what the *text layer* claims. If the font is")
    emit("re-encoded, confirm the shape with `sheet` (look) or `match` (numbers).")
    emit("Flags above mark a glyph whose shape contradicts its codepoint.")


def mode_sheet(doc, args, emit):
    crops = [resolve(doc, s) for s in args.crop]
    out = []
    for label, rect, info in crops:
        pix = glyph_pixmap(page := doc[info["page"]], rect, dpi=args.dpi)
        out.append((label, pix, info))
        emit(f"{label}: page {info['page']} rect {tuple(round(v,1) for v in rect)} "
             f"-> {pix.width}x{pix.height}px")

    # compose one page: one row per crop, label in a fixed left column
    gap = 12
    label_w = 150
    rows = [(label, pix, info) for label, pix, info in out]
    row_h = [p.height * 72.0 / args.dpi for _, p, _ in rows]
    page_w = label_w + max(p.width * 72.0 / args.dpi for _, p, _ in rows) + 2 * gap
    page_h = sum(row_h) + gap * (len(rows) + 1)
    sheet = pymupdf.open()
    pg = sheet.new_page(width=page_w, height=page_h)
    y = gap
    for (label, pix, info), h in zip(rows, row_h):
        w = pix.width * 72.0 / args.dpi
        pg.insert_image(pymupdf.Rect(label_w + gap, y, label_w + gap + w, y + h), pixmap=pix)
        caption = label if "char" not in info else f"{label}\n[{info['char']}]"
        pg.insert_text((gap, y + h / 2), caption, fontsize=8)
        y += h + gap
    if args.out.lower().endswith(".pdf"):
        sheet.save(args.out, deflate=True)
        emit(f"wrote {args.out} ({page_w:.0f}x{page_h:.0f} pt) — look at it")
    else:
        # a Document cannot be saved as a bitmap; rasterise the composed page
        pix = pg.get_pixmap(dpi=args.dpi)
        pix.save(args.out)
        emit(f"wrote {args.out} ({pix.width}x{pix.height}px) — look at it")


def mode_match(doc, args, emit):
    def mask_of(spec):
        label, rect, info = resolve(doc, spec)
        info = dict(info)
        info["bbox"] = rect
        return label, baseline_mask(doc[info["page"]], info), info

    sl, sm, si = mask_of(args.suspect)
    emit(f"suspect: {sl}  ({si.get('char')!r} per text layer, size {si.get('size')})")
    for spec in args.against:
        rl, rm, ri = mask_of(spec)
        iou = mask_iou(sm, rm)
        emit(f"  vs {rl:<22} IoU {iou:.2f}   ({ri.get('char')!r} per text layer)")
    emit("")
    emit("Baseline-anchored, size-normalised shape match. Same glyph, same style ->")
    emit("high (>0.75). Nearest trap: a suspect whose IoU against a genuine specimen of")
    emit("the codepoint the text layer claims is LOW means the encoding is lying.")
    emit("v vs u sit close together (both ~0.3-0.5 apart), so combine with the")
    emit("descender test in `chars`: a claimed y with no descender is not a y.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    def with_common(p, needs_out=True):
        p.add_argument("book", help="path to the PDF")
        if needs_out:
            p.add_argument("--out", help="write text output to this UTF-8 file instead of stdout")
        return p

    c = with_common(sub.add_parser("chars", help="per-character dump with a descender test"))
    c.add_argument("--page", type=int, required=True, help="0-based page index")
    c.add_argument("--search", help="restrict to the first match of this phrase")
    c.add_argument("--box", help="restrict to x0,y0,x1,y1 (PDF points)")

    s = sub.add_parser("sheet", help="labelled side-by-side crops -> PNG")
    s.add_argument("book", help="path to the PDF")
    s.add_argument("--crop", action="append", required=True, help="crop spec (repeatable)")
    s.add_argument("-o", "--output", dest="out", required=True, help="output PNG path")
    s.add_argument("--dpi", type=int, default=DEFAULT_DPI)

    m = with_common(sub.add_parser("match", help="numeric shape comparison (no vision needed)"))
    m.add_argument("--suspect", required=True, help="crop spec")
    m.add_argument("--against", action="append", required=True, help="crop spec (repeatable)")

    args = ap.parse_args(argv)

    # text sinks: --out file, else stdout (GBK consoles make this hard, so be kind)
    fh = open(args.out, "w", encoding="utf-8") if args.out and args.mode != "sheet" else None

    def emit(text=""):
        if fh is not None:
            fh.write(text + "\n")
        else:
            try:
                print(text)
            except UnicodeEncodeError:
                enc = sys.stdout.encoding or "ascii"
                print(text.encode(enc, "replace").decode(enc, "replace"))

    doc = pymupdf.open(args.book)
    if args.mode == "chars":
        mode_chars(doc, args, emit)
    elif args.mode == "sheet":
        mode_sheet(doc, args, emit)
    else:
        mode_match(doc, args, emit)
    if fh is not None:
        fh.close()
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
