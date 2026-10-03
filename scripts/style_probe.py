#!/usr/bin/env python3
"""Profile a textbook PDF's typography so the output can be made to *look like the book*.

The point of this skill is not to produce a generic LaTeX handout -- it is to produce a
problem set that reads like it was torn out of the same book. That means matching the
source's body serif, its sans-serif accent colour, its section banner, its section-number
colour and its running head. This script measures those and prints a ready-to-paste
LaTeX STYLE BLOCK for `assets/hw-template.tex` / `assets/hw-template-zh.tex`.

    python style_probe.py -i book.pdf -p 163,164,165
    python style_probe.py -i book.pdf -p 148-152 --latex -o .scratch/style.tex

It prints, in order:

    1. FACE CENSUS        every (font, size, colour) carrying real text, by volume
    2. COLOUR CENSUS      the same, collapsed to colour, tagged with a guess at its role
    3. HEAD BAND          what the running head is made of
    4. RULE CENSUS        page-wide hairlines (banner rule, running-head rule)
    5. SHAPE CENSUS       filled rectangles big enough to be a banner
    6. BANNER BAND        the text inside the banner box, and the number beside it
    7. PROPOSED STYLE     the complete STYLE BLOCK + LaTeX font-package suggestions

The proposal covers the whole STYLE BLOCK of the template, so it can be pasted in one
piece. It adapts to books with no banner (`\\StyleBannerfalse`) and to books whose running
head carries no hairline (`\\StyleHeadRulefalse`) -- both decided from measurements, not
assumed.

Everything is *evidence plus a proposal* -- never silently a verdict. If a value looks
wrong, override it by hand; the census above it is what you argue from.
"""

from __future__ import annotations

import argparse
import collections
import os
import sys

try:
    import pymupdf
except ImportError:  # PyMuPDF < 1.24 only exported `fitz`
    import fitz as pymupdf  # type: ignore


# ----------------------------------------------------------------------------- colour

def rgb(c):
    """pymupdf stores span colours as 0xRRGGBB ints and shape fills as 0..1 tuples."""
    if c is None:
        return None
    if isinstance(c, (tuple, list)):
        return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v * 255)))) for v in c[:3])
    return "#%06X" % (int(c) & 0xFFFFFF)


def unpack(h):
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


def lit(h):
    """Perceived lightness 0..1 -- tells a light tint from a solid colour."""
    r, g, b = unpack(h)
    return 0.299 * r + 0.587 * g + 0.114 * b


def is_white(h, tol=0.94):
    return all(v >= tol for v in unpack(h))


def is_ink(h, tol=0.32):
    return all(v <= tol for v in unpack(h))


def is_warm(h):
    """Reddish/crimson: what these books use for a section number or a head rule."""
    r, g, b = unpack(h)
    return r > 0.35 and r - g > 0.15 and r - b > 0.12


def saturation(h):
    r, g, b = unpack(h)
    mx, mn = max(r, g, b), min(r, g, b)
    return 0.0 if mx == 0 else (mx - mn) / mx


SANS_HINTS = ("helvetica", "arial", "heros", "gothic", "sans", "neue", "tahoma",
              "verdana", "frutiger", "univers", "myriad", "din", "calibri",
              "gotham", "open sans", "roboto", "source han sans", "yahei",
              "simhei", "黑体", "heiti")
SERIF_HINTS = ("times", "termes", "serif", "roman", "garamond", "palatino", "bookman",
               "century", "georgia", "minion", "charter", "caslon", "baskerville",
               "cambria", "song", "sung", "ming", "宋体", "明朝", "mincho")
CJK_HINTS = ("cjk", "song", "sung", "ming", "kai", "mincho", "yahei", "simhei",
             "黑体", "宋体", "明朝")


def looks_sans(font):
    f = font.lower()
    return any(h in f for h in SANS_HINTS)


def looks_serif(font):
    f = font.lower()
    return any(h in f for h in SERIF_HINTS)


def looks_cjk(font):
    f = font.lower()
    return any(h in f for h in CJK_HINTS)


# ------------------------------------------------------------------ font suggestions

# source font family -> (LaTeX package, note).  Order matters: first hit wins.
FONT_MAP = [
    (("times", "termes", "nimbus roman", "liberation serif"), "mathptmx",
     "Times-like text AND maths (psnfss, ships with scheme-small)"),
    (("garamond", "ebgaramond"), "ebgaramond",
     "Garamond-like; add newtxmath for Times-y maths"),
    (("palatino", "pagella", "book antiqua"), "mathpazo", "Palatino-like text AND maths"),
    (("bookman",), "bookman", "Bookman-like"),
    (("century", "schoolbook", "new century"), "newcent", "New Century Schoolbook-like"),
    (("charter", "charis", "xcharter"), "xcharter", "Charter-like"),
    (("cmu", "computer modern", "latin modern", "lmroman"), "", "already the LaTeX default"),
    (("helvetica", "arial", "heros", "gothic", "neue", "swiss"), "tgheros",
     "Helvetica-like sans"),
    (("frutiger", "avant", "adventor"), "tgadventor", "Avant-Garde-like sans"),
    (("univers", "humanist"), "", "no TeX clone; try tgheros and check"),
    (("song", "sung", "ming", "mincho", "serif cjk"), "", "CJK serif: leave it to ctex"),
    (("yahei", "hei", "gothic", "sans cjk"), "", "CJK sans: leave it to ctex"),
]


def suggest_font(fontname):
    f = (fontname or "").lower()
    for keys, pkg, note in FONT_MAP:
        if any(k in f for k in keys):
            return pkg, note
    return "", "no automatic mapping -- pick by eye"


# --------------------------------------------------------------------------- censuses

def spans(doc, pages):
    """Yield (page number, span dict) for every span carrying non-blank text."""
    for pno in pages:
        for b in doc[pno].get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for line in b["lines"]:
                for s in line["spans"]:
                    if s["text"].strip():
                        yield pno, s


def face_census(doc, pages, min_chars=1, head_band=62):
    faces = collections.Counter()
    colours = collections.Counter()
    sans = collections.Counter()
    head = collections.Counter()
    cjk = 0
    italic = collections.Counter()
    head_bottom = 0.0
    for _pno, s in spans(doc, pages):
        t = s["text"].strip()
        if len(t) < min_chars:
            continue
        c = rgb(s["color"])
        faces[(s["font"], round(s["size"], 1), c)] += len(t)
        colours[c] += len(t)
        if looks_sans(s["font"]):
            sans[c] += len(t)
        if s["bbox"][3] < head_band:              # the running-head band, above the text
            head[c] += len(t)
            head_bottom = max(head_bottom, s["bbox"][3])
        if "italic" in s["font"].lower() or "oblique" in s["font"].lower():
            italic[round(s["size"], 1)] += len(t)
        if any("\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" or
               "\uac00" <= ch <= "\ud7af" for ch in t):
            cjk += len(t)
    return faces, colours, sans, head, cjk, italic, head_bottom


def rect_census(doc, pages, min_w=40.0, min_h=10.0, max_h=40.0):
    """Filled rectangles that could be a banner, keyed with the page they sit on."""
    found = collections.Counter()
    for pno in pages:
        for d in doc[pno].get_drawings():
            r = d["rect"]
            fill = rgb(d.get("fill"))
            if fill is None or not (min_w <= r.width and min_h <= r.height <= max_h):
                continue
            if is_white(fill):
                continue
            found[(fill, pno, round(r.x0, 1), round(r.y0, 1),
                   round(r.width, 1), round(r.height, 1))] += 1
    return found


def rule_census(doc, pages, min_h=2.5, width_frac=0.40):
    """Page-wide hairlines, drawn either as a thin fill or as a stroked line."""
    width = width_frac * min(doc[p].rect.width for p in pages)
    found = collections.Counter()
    for pno in pages:
        for d in doc[pno].get_drawings():
            r = d["rect"]
            if not (r.width >= width and r.height <= min_h):
                continue
            col = rgb(d.get("fill")) or rgb(d.get("color"))
            if col is None or is_white(col):
                continue
            found[(col, pno, round(r.y0, 1), round(r.width, 0))] += 1
    return found


def pick_banner(shapes):
    """The most common saturated rectangle: the book's EXERCISES-style banner."""
    for key, _n in shapes.most_common(20):
        fill = key[0]
        if is_ink(fill) or lit(fill) > 0.85 or saturation(fill) <= 0.15:
            continue
        return {"fill": fill, "page": key[1],
                "rect": pymupdf.Rect(key[2], key[3], key[2] + key[4], key[3] + key[5])}
    return None


def banner_band(doc, banner):
    """The banner's own label (inside the box) and the number beside it, same page only."""
    rect = banner["rect"]
    label, number = collections.Counter(), collections.Counter()
    inside, beside = [], []
    for _pno, s in spans(doc, [banner["page"]]):
        x0, y0, x1, y1 = s["bbox"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if rect.x0 - 1 <= cx <= rect.x1 + 1 and rect.y0 - 1 <= cy <= rect.y1 + 1:
            inside.append(s)
        elif (rect.x1 - 2 <= x0 <= rect.x1 + 90
              and y1 >= rect.y0 - 4 and y0 <= rect.y1 + 4):
            beside.append(s)

    baseline = None
    if inside:
        big = max(inside, key=lambda s: len(s["text"]))
        baseline = big["origin"][1]
        for s in inside:
            label[(s["text"].strip(), rgb(s["color"]), round(s["size"], 1))] += len(s["text"])

    number_size = 0.0
    if beside:
        number_size = max(round(s["size"], 1) for s in beside)
        for s in beside:                        # the number is the largest text beside
            if round(s["size"], 1) >= number_size - 0.3:   # the banner
                number[rgb(s["color"])] += len(s["text"])
    return label, number, number_size, baseline


# --------------------------------------------------------------------- the proposal

DEFAULTS = {
    "ink": "#231F20",
    "accent": "#0089CF",
    "banner": "#00608A",
    "banner_text": "#FFFFFF",
    "number": "#790018",
    "banner_rule": "#939598",
    "head_text": "#231F20",
    "head_rule": "#ED1846",
}


def propose(faces, colours, sans, head, italic, shapes, rules, banner, band, pdf_name,
            head_bottom=0.0):
    out, notes = [], []
    hits = collections.Counter()

    # -- body face: the serif face carrying the most text --------------------------
    body_font, body_size = None, None
    cands = [(k, v) for k, v in faces.items() if looks_serif(k[0])] or list(faces.items())
    if cands:
        (body_font, body_size, _c), _n = max(cands, key=lambda kv: kv[1])
    if body_font and looks_cjk(body_font):
        notes.append("body face is a CJK font -- use xelatex + ctexart "
                     "(see SKILL.md 'Language support')")

    # -- sans face: the headings ---------------------------------------------------
    sans_faces = [(k, v) for k, v in faces.items() if looks_sans(k[0])]
    sans_font = max(sans_faces, key=lambda kv: kv[1])[0][0] if sans_faces else "Helvetica"

    # -- ink: the most common text colour -------------------------------------------
    ink = colours.most_common(1)[0][0] if colours else DEFAULTS["ink"]
    if colours:
        hits["ink"] = 1

    # -- accent: the loudest non-ink, non-white SANS colour -------------------------
    accent = DEFAULTS["accent"]
    loud = [(c, n) for c, n in sans.items() if not is_ink(c) and not is_white(c)]
    if loud:
        accent = max(loud, key=lambda kv: kv[1])[0]
        hits["accent"] = 1
    else:
        notes.append("no coloured sans text found -- this book may have no group "
                     "headings; StyleAccent kept as a template default")

    # -- banner, its label and the section number beside it ------------------------
    banner_on = banner is not None
    banner_fill = banner["fill"] if banner_on else DEFAULTS["banner"]
    label_text, banner_text, label_size = "Exercises", DEFAULTS["banner_text"], 0.0
    number, number_size, baseline = DEFAULTS["number"], 0.0, None
    if banner_on:
        hits["banner"] = 1
        label, num, number_size, baseline = band
        if label:
            (label_text, banner_text, label_size), _n = max(label.items(),
                                                            key=lambda kv: kv[1])
            hits["banner_text"] = 1
        else:
            notes.append("no text found inside the banner box -- \\StyleBannerLabel and "
                         "\\StyleBannerText kept as template defaults")
        if num:
            number = max(num.items(), key=lambda kv: kv[1])[0]
            hits["number"] = 1
        else:
            notes.append("no section number found beside the banner -- \\StyleNumber kept "
                         "as a template default; it may be drawn as shapes")
    else:
        notes.append("no filled banner rectangle found -- \\StyleBannerfalse is proposed; "
                     "if the book does have one, re-run on a page that shows it")

    # -- rules: the banner hairline and the running-head hairline -------------------
    banner_rule, raise_pt = DEFAULTS["banner_rule"], None
    head_rule, head_rule_on = DEFAULTS["head_rule"], False
    if banner_on:
        near = [(k, n) for k, n in rules.items()
                if k[1] == banner["page"] and abs(k[2] - banner["rect"].y0) <= 8]
        if near:
            banner_rule = max(near, key=lambda kv: kv[1])[0][0]
            hits["banner_rule"] = 1
            if baseline is not None:
                raise_pt = round(baseline - min(k[2] for k, _n in near), 1)
        else:
            notes.append("no hairline at the banner's top edge -- this banner may not hang "
                         "from a rule; \\StyleBannerRule kept as a template default")
    # A running-head rule has to sit with the running head -- just above it or just under it.
    # Anything further down is content (a table or section rule inside the text block), and
    # accepting those would turn \StyleHeadRuletrue on for books that simply own a table.
    limit = (head_bottom + 14) if head_bottom else 62.0
    top_rules = [(k, n) for k, n in rules.items() if k[2] <= limit]
    if top_rules:
        head_rule = max(top_rules, key=lambda kv: kv[1])[0][0]
        head_rule_on = True
        hits["head_rule"] = 1
    else:
        notes.append("no running-head hairline found -- \\StyleHeadRulefalse is proposed; "
                     "the head is text only")
        if rules:
            near = [k for k in rules if k[2] < 200]
            if near:
                notes.append("rules exist in the top half of the page but none sits with the "
                             "running head (nearest is %s at y=%s) -- treated as content, "
                             "not a head rule" % (near[0][0], near[0][2]))

    # -- running-head text colour ---------------------------------------------------
    head_text = DEFAULTS["head_text"]
    loud_head = [(c, n) for c, n in head.items() if not is_ink(c) and n >= 6]
    if loud_head:
        head_text = max(loud_head, key=lambda kv: kv[1])[0]
        hits["head_text"] = 1
    else:
        notes.append("running head is plain ink -- StyleHeadText kept as the ink colour")

    # -- instruction shape: how much of the body-size text is italic -----------------
    body_chars = sum(n for (f, sz, c), n in faces.items()
                     if sz and body_size and abs(sz - body_size) < 0.6)
    share = (italic.get(body_size, 0) / body_chars) if body_chars else 0.0
    if share >= 0.12:
        instr, instr_note = "\\itshape", f"{share:.0%} of body-size text is italic"
    else:
        instr, instr_note = "\\relax", f"only {share:.0%} of body-size text is italic"

    # -- note colours that are almost certainly links, not styling ------------------
    for c, n in colours.most_common(8):
        small_serif = sum(v for (f, sz, cc), v in faces.items()
                          if cc == c and sz and body_size and sz < body_size
                          and looks_serif(f))
        if small_serif >= 40 and c not in (ink, accent) and not is_warm(c):
            notes.append(f"colour {c} appears only in small serif text ({small_serif} chars) "
                         "-- probably the hyperlink/reference colour, ignored for styling")

    # -- emit ------------------------------------------------------------------------
    serif_pkg, serif_note = suggest_font(body_font or "")
    sans_pkg, sans_note = suggest_font(sans_font)
    w = out.append
    w("%% ---- STYLE BLOCK: paste into the STYLE BLOCK of assets/hw-template.tex ----")
    w("%% measured from %s @ pages %s" % (os.path.basename(pdf_name),
                                          getattr(propose, "_pages", "?")))
    w("%% body face  : %s @ %spt -- %s" % (body_font, body_size, serif_note))
    w("%% sans face  : %s -- %s" % (sans_font, sans_note))
    if banner_on:
        w("%% banner     : yes -- label %r (%spt, %s on %s), box %sx%spt"
          % (label_text, label_size or number_size, banner_text, banner_fill,
             round(banner["rect"].width, 1), round(banner["rect"].height, 1)))
    else:
        w("%% banner     : none found")
    w("%% head rule  : %s" % (head_rule if head_rule_on else "none found"))
    w("%% instructions: %s (%s)" % (instr, instr_note))
    if raise_pt:
        w("%% banner rule: %s, measured %spt above the label baseline (the box top edge)"
          % (banner_rule, raise_pt))
    w("%% NOTE: \\StyleBannerRaise below is the template's own box geometry (0.75 x its 14pt")
    w("%%       label + 3pt \\fboxsep), not the book's number -- nudge it if the rule cuts")
    w("%%       the box. Everything else is a direct measurement.")
    w("%% ---------------------------------------------------------------- 1. faces")
    w("\\usepackage{%s}          %% body serif + maths" % (serif_pkg or "mathptmx"))
    w("\\usepackage{%s}           %% sans: headings, banner, folio"
      % (sans_pkg or "tgheros"))
    w("\\newcommand{\\StyleBodyFont}{\\rmfamily}")
    w("\\newcommand{\\StyleSansFont}{\\sffamily}")
    w("%% -------------------------------------------------------------- 2. palette")
    w("\\definecolor{StyleInk}{HTML}{%s}        %% body text" % ink.lstrip("#"))
    w("\\definecolor{StyleAccent}{HTML}{%s}     %% group headings" % accent.lstrip("#"))
    w("\\definecolor{StyleBanner}{HTML}{%s}     %% banner fill" % banner_fill.lstrip("#"))
    w("\\definecolor{StyleBannerText}{HTML}{%s} %% banner label"
      % banner_text.lstrip("#"))
    w("\\definecolor{StyleNumber}{HTML}{%s}     %% section number beside the banner"
      % number.lstrip("#"))
    w("\\definecolor{StyleBannerRule}{HTML}{%s} %% hairline the banner hangs from"
      % banner_rule.lstrip("#"))
    w("\\definecolor{StyleHeadText}{HTML}{%s}   %% running-head text" % head_text.lstrip("#"))
    w("\\definecolor{StyleHeadRule}{HTML}{%s}   %% running-head hairline (when enabled)"
      % head_rule.lstrip("#"))
    w("%% --------------------------------------------------------------- 3. banner")
    w("\\newif\\ifStyleBanner")
    w("\\StyleBanner%s" % ("true" if banner_on else "false"))
    w("\\newcommand{\\StyleBannerRaise}{13.5pt}")
    w("\\newcommand{\\StyleBannerLabel}{%s}" % label_text)
    w("%% --------------------------------------------------------- 4. instructions")
    w("\\newcommand{\\StyleInstrShape}{%s}" % instr)
    w("%% -------------------------------------------------------- 5. running head")
    w("\\newif\\ifStyleHeadRule")
    w("\\StyleHeadRule%s" % ("true" if head_rule_on else "false"))
    w("%% -------------------------------------------------------------------")
    block = "\n".join(out)

    notes.append(f"{len(hits)}/9 style values measured; the rest are template defaults -- "
                 "override by hand wherever the census disagrees")
    return block, notes


# ------------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--pdf", required=True)
    ap.add_argument("-p", "--pages", required=True,
                    help="comma-separated page indices, ranges with '-', e.g. 163,164 or 148-152")
    ap.add_argument("-o", "--out", default="", help="also write the proposal to this file")
    ap.add_argument("--latex", action="store_true", help="print only the STYLE BLOCK")
    ap.add_argument("-n", "--top", type=int, default=20)
    args = ap.parse_args(argv)

    pages = []
    for part in args.pages.split(","):
        part = part.strip()
        if "-" in part:
            a, z = part.split("-", 1)
            pages.extend(range(int(a), int(z) + 1))
        elif part:
            pages.append(int(part))

    doc = pymupdf.open(args.pdf)
    faces, colours, sans, head, cjk, italic, head_bottom = face_census(doc, pages)
    shapes = rect_census(doc, pages)
    rules = rule_census(doc, pages)
    banner = pick_banner(shapes)
    band = banner_band(doc, banner) if banner else ({}, {}, 0.0, None)
    propose._pages = args.pages
    block, notes = propose(faces, colours, sans, head, italic, shapes, rules,
                           banner, band, args.pdf, head_bottom)

    lines = []
    if not args.latex:
        lines.append("FACE CENSUS  (pages %s)" % args.pages)
        for (f, sz, c), n in faces.most_common(args.top):
            lines.append("  %-30s size=%-6s %s  chars=%d" % (f, sz, c, n))
        lines.append("")
        lines.append("COLOUR CENSUS  (text only -- rules and fills are censused separately)")
        for c, n in colours.most_common(args.top):
            role = []
            if any(cc == c for cc, _ in sans.items()):
                role.append("sans")
            if any(cc == c for cc, _ in head.items()):
                role.append("head")
            lines.append("  %s  chars=%-6d %s" % (c, n, " ".join(role)))
        lines.append("")
        lines.append("HEAD BAND  (spans above y=62: running head and folio; bottom y=%s)"
                     % round(head_bottom, 1))
        for c, n in head.most_common(6):
            lines.append("  %s  chars=%d" % (c, n))
        if not head:
            lines.append("  (nothing found)")
        lines.append("")
        lines.append("RULE CENSUS  (page-wide hairlines)")
        for (c, pno, y, wd), n in rules.most_common(12):
            lines.append("  %s  page %-5s y=%-7s width=%-6s n=%d" % (c, pno, y, wd, n))
        if not rules:
            lines.append("  (none)")
        lines.append("")
        lines.append("SHAPE CENSUS  (filled rects: banner candidates)")
        for (fill, pno, x0, y0, wd, h), n in shapes.most_common(12):
            lines.append("  %s  page %-5s x0=%-7s y0=%-7s w=%-6s h=%-5s n=%d"
                         % (fill, pno, x0, y0, wd, h, n))
        if not shapes:
            lines.append("  (none)")
        lines.append("")
        if banner:
            lab, num, nsize, baseline = band
            r = banner["rect"]
            lines.append("BANNER BAND  (page %s, box %s x0=%s y0=%s w=%s h=%s)"
                         % (banner["page"], banner["fill"], round(r.x0, 1),
                            round(r.y0, 1), round(r.width, 1), round(r.height, 1)))
            for (t, c, sz), n in lab.most_common(6):
                lines.append("  inside : %-26s %s size=%-5s chars=%d" % (repr(t), c, sz, n))
            for c, n in num.most_common(6):
                lines.append("  beside : %s chars=%-5d (largest size %s)" % (c, n, nsize))
            if baseline is not None:
                lines.append("  label baseline y=%s" % baseline)
            lines.append("")
        if cjk > 400:
            lines.append("!! %d CJK characters found -- use xelatex + ctexart, "
                         "not pdflatex (see SKILL.md 'Language support')." % cjk)
            lines.append("")
    lines.append(block)
    for n in notes:
        lines.append("% " + n)

    text = "\n".join(lines)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
