#!/usr/bin/env python3
"""Render regions of a textbook PDF to PNG, for *looking at* the pages.

Two modes, both driven by PDF points (a 8.5x11in page is 612 x 783 pt):

  tiles   split whole pages into a grid of overlapping tiles, so the vision tool
          does not downscale them into illegibility

  box     crop explicit point-boxes, one PNG per problem / figure

The vision tool on this harness keeps images up to ~2.2 Mpx native (e.g. 1654x1287)
and downsamples anything larger -- a full 300 dpi page (2550x3263) loses ~60% of its
linear resolution, which kills superscripts. Hence the tiling default.

Examples
--------
    # whole exercise pages as 2x2 tiles at 300 dpi (the workhorse)
    python crop_rect.py tiles -i book.pdf -o .scratch/tiles -p 148,149,150

    # one problem: name:page:x0,y0,x1,y1
    python crop_rect.py box -i book.pdf -o .scratch/probs \\
        p149_15:149:50,660,335,783  p150_21:150:300,380,612,520

    # figures for the deliverable, at 400 dpi
    python crop_rect.py box -i book.pdf -o fig -d 400 \\
        fig_3_4_15:149:398,60,518,151

Notes
-----
* Console output is ASCII only on purpose (Windows consoles are often GBK); the
  PNGs are the product, the stdout is just a manifest.
* `--grid` must divide the page evenly enough that tiles stay under ~2 Mpx. For a
  612x783 pt page: 2x2 @ 300 dpi -> ~1315x1672 px. 1x1 @ 300 dpi is too big.
* Boxes are clamped to the page and silently reordered if x0>x1 or y0>y1, because
  a transposed pair is a common hand-typed mistake and the crop is still well defined.
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    import pymupdf
except ImportError:  # PyMuPDF < 1.24 only exported `fitz`
    import fitz as pymupdf  # type: ignore

from PIL import Image


def _px_pts(dpi: float):
    return dpi / 72.0


def _save(page, matrix, clip, path, dpi):
    pix = page.get_pixmap(matrix=matrix, clip=clip)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img.save(path, dpi=(dpi, dpi))
    return img.size


def cmd_tiles(args):
    doc = pymupdf.open(args.pdf)
    os.makedirs(args.out, exist_ok=True)
    mat = pymupdf.Matrix(_px_pts(args.dpi), _px_pts(args.dpi))
    cols, rows = (int(v) for v in args.grid.lower().split("x"))
    ov = args.overlap

    for pno in args.pages:
        page = doc[pno]
        r = page.rect
        # one full-page raster, then cut it up in pixel space (cheaper than N clips)
        pix = page.get_pixmap(matrix=mat)
        whole = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        W, H = whole.size
        whole.save(os.path.join(args.out, "p%d.png" % pno), dpi=(args.dpi, args.dpi))
        print("p%d full %dx%d" % (pno, W, H))

        for j in range(rows):
            for i in range(cols):
                x0 = max(0, int(W * i / cols) - (ov if i else 0))
                x1 = min(W, int(W * (i + 1) / cols) + (ov if i + 1 < cols else 0))
                y0 = max(0, int(H * j / rows) - (ov if j else 0))
                y1 = min(H, int(H * (j + 1) / rows) + (ov if j + 1 < rows else 0))
                name = "p%d_q%d.png" % (pno, j * cols + i)
                sub = whole.crop((x0, y0, x1, y1))
                sub.save(os.path.join(args.out, name), dpi=(args.dpi, args.dpi))
                print("  %s %dx%d" % (name, sub.size[0], sub.size[1]))
    doc.close()


def _parse_spec(spec: str):
    name, page, box = spec.split(":", 2)
    x0, y0, x1, y1 = (float(v) for v in box.replace(" ", "").split(","))
    return name, int(page), x0, y0, x1, y1


def cmd_box(args):
    doc = pymupdf.open(args.pdf)
    out = args.out
    if out:
        os.makedirs(out, exist_ok=True)
    mat = pymupdf.Matrix(_px_pts(args.dpi), _px_pts(args.dpi))

    for spec in args.specs:
        name, pno, x0, y0, x1, y1 = _parse_spec(spec)
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        page = doc[pno]
        clip = pymupdf.Rect(x0, y0, x1, y1) & page.rect
        if clip.is_empty:
            print("!! %s: box %s falls outside page %d -- SKIPPED" % (name, clip, pno))
            continue
        if abs(clip.width - (x1 - x0)) > 1 or abs(clip.height - (y1 - y0)) > 1:
            print("   %s: clamped to %s" % (name, clip))
        path = os.path.join(out, name + ".png") if out else name + ".png"
        w, h = _save(page, mat, clip, path, args.dpi)
        print("%s p%d %s %dx%d" % (name, pno, clip, w, h))
    doc.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tiles", help="split whole pages into an overlapping grid")
    t.add_argument("-i", "--pdf", required=True)
    t.add_argument("-o", "--out", default=".")
    t.add_argument("-d", "--dpi", type=int, default=300)
    t.add_argument("-g", "--grid", default="2x2", help="COLSxROWS, default 2x2")
    t.add_argument("-v", "--overlap", type=int, default=40, help="pixels, default 40")
    t.add_argument("-p", "--pages", required=True,
                   help="comma-separated PDF page indices (page index == printed folio "
                        "only if you verified it; use `-` for ranges, e.g. 148-152")
    t.set_defaults(func=cmd_tiles)

    b = sub.add_parser("box", help="crop explicit point-boxes")
    b.add_argument("-i", "--pdf", required=True)
    b.add_argument("-o", "--out", default="")
    b.add_argument("-d", "--dpi", type=int, default=300)
    b.add_argument("specs", nargs="+", metavar="name:page:x0,y0,x1,y1")
    b.set_defaults(func=cmd_box)

    args = ap.parse_args(argv)

    if getattr(args, "pages", None):
        pages = []
        for part in args.pages.split(","):
            part = part.strip()
            if "-" in part:
                a, z = part.split("-", 1)
                pages.extend(range(int(a), int(z) + 1))
            elif part:
                pages.append(int(part))
        args.pages = pages

    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
