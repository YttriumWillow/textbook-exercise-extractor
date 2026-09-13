# -*- coding: utf-8 -*-
"""Helpers for textbook-exercise-extractor.

Typical use:
    doc = pymupdf.open(TEXTBOOK)
    print(section_pages(doc))                  # which pages hold each EXERCISES n.m set
    render_page(doc, 71, "out/p72.png")        # LOOK at it to learn the column layout
    print(profile(doc, 71, 44, 314, 100, 760)) # exact ink bands -> pick y0/y1
    rect = crop_rect(doc, 71, 44, 314, 110.0, 254.0)
    dump_crops(doc, JOBS, "check.jpg")         # contact sheet for visual verification
"""
import math
import re

import pymupdf

DPI = 200
S = DPI / 72.0
THRESH = 205          # pixel value below this counts as ink
GAP_FRAC = 0.012      # a row is "blank" if ink pixels <= GAP_FRAC * strip width


def section_pages(doc):
    """section label -> list of 1-based PDF page numbers containing 'EXERCISES n.m'."""
    out = {}
    pat = re.compile(r"EXERCISES\s+(\d+\.\d+)")
    for i in range(doc.page_count):
        for m in pat.finditer(doc[i].get_text()):
            out.setdefault(m.group(1), []).append(i + 1)
    return out


def render_page(doc, page_index, path, dpi=130, clip=None):
    doc[page_index].get_pixmap(dpi=dpi, clip=clip).save(path)


def _strip(doc, page_index, sx0, sx1):
    clip = pymupdf.Rect(sx0, 0, sx1, doc[page_index].rect.height)
    pix = doc[page_index].get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY, clip=clip)
    w, h, st, buf = pix.width, pix.height, pix.stride, pix.samples
    counts = [sum(1 for v in buf[r * st:r * st + w] if v < THRESH) for r in range(h)]
    return buf, w, h, st, counts


def profile(doc, page_index, sx0, sx1, y0, y1):
    """Return [(kind, y_start, y_end, max_ink)] runs over [y0, y1]."""
    _, w, h, _, counts = _strip(doc, page_index, sx0, sx1)
    th = max(2, int(GAP_FRAC * w))
    rows, cur = [], None
    for i in range(max(0, int(y0 * S)), min(h, int(y1 * S))):
        lab = "GAP" if counts[i] <= th else "ink"
        if cur is None or cur[0] != lab:
            if cur:
                rows.append(tuple(cur))
            cur = [lab, i, counts[i]]
        cur[2] = max(cur[2], counts[i])
    if cur:
        rows.append(tuple(cur))
    return [(k, a / S, b / S, m) for k, a, b, m in rows]


def crop_rect(doc, page_index, sx0, sx1, y0, y1, pad=4.0):
    """Tight x extent of the ink inside the band, clipped to the strip."""
    buf, w, h, st, _ = _strip(doc, page_index, sx0, sx1)
    xs0 = xs1 = None
    for r in range(max(0, int(y0 * S)), min(h, int(y1 * S))):
        row = buf[r * st:r * st + w]
        for c in range(w):
            if row[c] < THRESH:
                if xs0 is None or c < xs0:
                    xs0 = c
                break
        for c in range(w - 1, -1, -1):
            if row[c] < THRESH:
                if xs1 is None or c > xs1:
                    xs1 = c
                break
    if xs0 is None:
        xs0, xs1 = 0, w - 1
    r = pymupdf.Rect(sx0 + xs0 / S - pad, y0, sx0 + xs1 / S + pad, y1)
    return r & pymupdf.Rect(sx0, 0, sx1, doc[page_index].rect.height)


def merge_crops(doc, jobs, out_path, title="Textbook Problems"):
    """jobs: [(page_index, x0, y0, x1, y1, section, label)]. Writes the merged PDF."""
    PW, PH, M, CAPH, GAP, BOTTOM = 612.0, 792.0, 34.0, 21.0, 15.0, 26.0
    out = pymupdf.open()
    st = {"cur": None, "y": 0.0}

    def newpage():
        pg = out.new_page(width=PW, height=PH)
        pg.insert_text((M, M - 13), title, fontname="helv", fontsize=8,
                       color=(0.42, 0.45, 0.52))
        pg.draw_line(pymupdf.Point(M, M - 8), pymupdf.Point(PW - M, M - 8),
                     color=(0.80, 0.82, 0.86), width=0.6)
        st["cur"], st["y"] = pg, M + 6

    newpage()
    for pi, x0, y0, x1, y1, sec, label in jobs:
        rect = crop_rect(doc, pi, x0, x1, y0, y1)
        cur, y = st["cur"], st["y"]
        avail = PH - M - BOTTOM - (y + CAPH)
        if avail < 90:
            newpage()
            cur, y = st["cur"], st["y"]
            avail = PH - M - BOTTOM - (y + CAPH)
        sc = min((PW - 2 * M) / rect.width, avail / rect.height, 1.9)
        tw, th = rect.width * sc, rect.height * sc
        cur.insert_text((M, y + 10), f"Section {sec}   \u00b7   {label}",
                        fontname="hebo", fontsize=10.5, color=(0.09, 0.36, 0.72))
        y += CAPH - 5
        tgt = pymupdf.Rect(M, y, M + tw, y + th)
        cur.show_pdf_page(tgt, doc, pi, clip=rect)
        cur.draw_rect(tgt, color=(0.84, 0.86, 0.90), width=0.5)
        st["y"] = y + th + GAP
    out.set_metadata({"title": title})
    out.save(out_path, garbage=4, deflate=True)
    return out.page_count


def contact_sheet(doc, jobs, jpg_path, cols=3, colw=300, dpi=72):
    """Render a grid of every crop so you can eyeball wrong/clipped crops."""
    rects = [crop_rect(doc, *j[:5]) for j in jobs]
    rows = math.ceil(len(rects) / cols)
    heights = []
    for r in range(rows):
        h = 40
        for c in range(cols):
            i = r * cols + c
            if i < len(rects):
                h = max(h, int(rects[i].height * min(colw / rects[i].width, 2.0)))
        heights.append(h)
    W = cols * (colw + 8) + 8
    H = sum(h + 18 + 8 for h in heights) + 8
    tmp = pymupdf.open()
    pg = tmp.new_page(width=W, height=H)
    y = 8
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            if i >= len(jobs):
                continue
            pi, x0, y0, x1, y1, sec, label = jobs[i]
            rect = rects[i]
            sc = min(colw / rect.width, 2.0)
            pix = doc[pi].get_pixmap(dpi=int(dpi * sc), clip=rect)
            x = 8 + c * (colw + 8)
            pg.insert_text((x, y + 13), f"{sec} {label}", fontname="hebo", fontsize=12)
            pg.insert_image(pymupdf.Rect(x, y + 18, x + pix.width, y + 18 + pix.height),
                            pixmap=pix)
        y += heights[r] + 26
    out = pg.get_pixmap(dpi=int(1150.0 / W * 72.0))
    open(jpg_path, "wb").write(out.tobytes("jpeg", jpg_quality=72))
    tmp.close()
