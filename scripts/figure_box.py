# -*- coding: utf-8 -*-
"""Extract figures from a textbook PDF, auto-growing the crop box until no ink
touches any border (so nothing is ever clipped).

Usage:
    doc = pymupdf.open(TEXTBOOK)
    box = figure_box(doc, page_index=71, init=(128,196,250,250), limit=(118,190,258,254))
    save_fig(doc, page_index=71, box=box, path="fig/f22_1.png")
"""
import pymupdf

DPI = 200
S = DPI / 72.0
THRESH = 205
EDGE = 1.6          # pt of border probed for stray ink


def _dirty_sides(page, box, min_ink=2):
    x0, y0, x1, y1 = box
    pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY,
                          clip=pymupdf.Rect(x0, y0, x1, y1))
    w, h, st, buf = pix.width, pix.height, pix.stride, pix.samples
    e = max(1, int(EDGE * S))

    def dark(rows, cols):
        n = 0
        for r in rows:
            row = buf[r * st:r * st + w]
            for c in cols:
                if row[c] < THRESH:
                    n += 1
                    if n >= min_ink:
                        return True
        return False

    sides = []
    if dark(range(0, min(e, h)), range(w)):
        sides.append("top")
    if dark(range(max(0, h - e), h), range(w)):
        sides.append("bottom")
    if dark(range(h), range(0, min(e, w))):
        sides.append("left")
    if dark(range(h), range(max(0, w - e), w)):
        sides.append("right")
    return sides


def figure_box(doc, page_index, init, limit, step=1, max_iter=60):
    """init / limit are (x0, y0, x1, y1) tuples in PDF points.

    `limit` is the *allowed* region; the box never grows beyond it, which is how
    you stop it from swallowing a neighbouring problem or the text beside the figure.
    """
    page = doc[page_index]
    lx0, ly0, lx1, ly1 = limit
    r = list(init)
    for _ in range(max_iter):
        s = _dirty_sides(page, r)
        if not s:
            break
        if "top" in s and r[1] > ly0:
            r[1] -= step
        if "bottom" in s and r[3] < ly1:
            r[3] += step
        if "left" in s and r[0] > lx0:
            r[0] -= step
        if "right" in s and r[2] < lx1:
            r[2] += step
    return tuple(round(v, 1) for v in r)


def save_fig(doc, page_index, box, path, dpi=400, pad=1.5):
    x0, y0, x1, y1 = box
    clip = pymupdf.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    doc[page_index].get_pixmap(dpi=dpi, clip=clip).save(path)
    return path
