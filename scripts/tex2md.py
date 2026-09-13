# -*- coding: utf-8 -*-
"""Convert a problem-set .tex (built with assets/hw-template.tex) into Markdown.

The .tex uses custom macros (\prob, \instr, \fig) that pandoc's LaTeX reader drops,
so we translate the (deliberately small) macro set directly and keep every formula
verbatim. The resulting Markdown can then be fed to pandoc for docx/html/pdf.

    python tex2md.py hw1.tex -o hw1.md          # figures referenced as fig/*.png
    python tex2md.py hw1.tex -o hw1.md --figprefix figs
"""
import argparse
import re
import sys

ALPHA = "abcdefghijklmnopqrstuvwxyz"


def strip_preamble(lines):
    out, in_doc = [], False
    for ln in lines:
        if ln.startswith(r"\begin{document}"):
            in_doc = True
            continue
        if in_doc:
            if ln.startswith(r"\end{document}"):
                break
            out.append(ln)
    return out


def convert(text, figprefix="fig"):
    lines = strip_preamble(text.splitlines())
    out = []
    i = 0
    depth = 0          # enumerate nesting
    counters = [0]

    while i < len(lines):
        ln = lines[i].rstrip()
        s = ln.strip()

        # --- title block (first \begin{center} ... \end{center}) ----------
        if s.startswith(r"\begin{center}"):
            buf, j = [], i + 1
            while j < len(lines) and not lines[j].strip().startswith(r"\end{center}"):
                buf.append(lines[j].strip())
                j += 1
            body = [clean_title(b) for b in buf]
            body = [b for b in body if b]
            if body:
                out.append("")
                out.append(f"# {body[0]}")
                for b in body[1:]:
                    out.append("")
                    out.append(b)
                out.append("")
            i = j + 1
            continue
        if s.startswith(r"\end{center}"):
            i += 1
            continue

        # --- display math \[ ... \] -------------------------------------
        if s == r"\[":
            buf = []
            i += 1
            while i < len(lines) and lines[i].strip() != r"\]":
                buf.append(lines[i].rstrip())
                i += 1
            i += 1
            out.append("")
            out.append("$$")
            out.extend(f"  {b.strip()}" for b in buf)
            out.append("$$")
            out.append("")
            continue

        # --- figures -----------------------------------------------------
        m = re.match(r"\\fig(?:\[[^\]]*\])?\{([^}]*)\}", s)
        if m:
            out.append("")
            out.append(f"![figure]({figprefix}/{m.group(1)}.png)")
            out.append("")
            i += 1
            continue

        # --- sectioning ---------------------------------------------------
        m = re.match(r"\\section\*\{(.*)\}", s)
        if m:
            out.append("")
            out.append(f"# {clean(m.group(1))}")
            out.append("")
            i += 1
            continue
        m = re.match(r"\\subsection\*\{(.*)\}", s)
        if m:
            out.append("")
            out.append(f"## {clean(m.group(1))}")
            out.append("")
            i += 1
            continue

        # --- instruction paragraph (MUST be preserved) --------------------
        if s.startswith(r"\instr{"):
            # may span several lines
            buf, j = [s[len(r"\instr{"):]], i + 1
            while j < len(lines) and "}" not in " ".join(buf):
                buf.append(lines[j].strip())
                j += 1
            body = " ".join(buf)
            body = body[:body.rfind("}")]
            out.append("")
            out.append(f"> _{clean(body)}_")
            out.append("")
            i = j
            continue

        # --- problem number ----------------------------------------------
        m = re.match(r"\\prob\{([^}]*)\}", s)
        if m:
            rest = s[m.end():]
            out.append("")
            out.append(f"**{m.group(1)}** {clean(rest)}".rstrip())
            i += 1
            continue

        # --- enumerate ----------------------------------------------------
        if s.startswith(r"\begin{enumerate}"):
            depth += 1
            if len(counters) < depth:
                counters.append(0)
            counters[depth - 1] = 0
            out.append("")
            i += 1
            continue
        if s.startswith(r"\end{enumerate}"):
            counters[depth - 1] = 0
            depth -= 1
            out.append("")
            i += 1
            continue
        if s.startswith(r"\item"):
            body = s[len(r"\item"):].strip()
            counters[depth - 1] += 1
            n = counters[depth - 1]
            lab = f"{ALPHA[n-1]}." if n <= 26 else f"{n}."
            out.append(f"{lab} {clean(body)}")
            out.append("")       # keep every sub-item as its own paragraph
            i += 1
            continue

        # --- things to drop ------------------------------------------------
        if (s.startswith(r"\needspace") or s.startswith(r"\clearpage")
                or s.startswith(r"\vspace") or s.startswith(r"\hrule")
                or s.startswith(r"\begin{center}") or s.startswith(r"\end{center}")
                or s.startswith(r"\linespread") or s.startswith("%")
                or s == ""):
            i += 1
            continue

        # --- plain text ----------------------------------------------------
        out.append(clean(s))
        i += 1

    md = "\n".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def clean_title(s):
    """Strip font/size/colour wrappers from the title block."""
    s = re.sub(r"\\\[\d+pt\]", " ", s)
    s = s.replace(r"\textperiodcentered", "\u00b7")
    s = re.sub(r"\\(?:LARGE|Large|large|small|footnotesize|bfseries|itshape|rmfamily)\b", " ", s)
    s = re.sub(r"\\color\{[^}]*\}", " ", s)
    s = re.sub(r"\\[A-Za-z]+", " ", s)          # any leftover macro
    s = s.replace("{", " ").replace("}", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def clean(s):
    s = s.replace(r"\quad", " ").replace(r"\qquad", "  ")
    s = s.replace(r"\dots", "...").replace(r"\ldots", "...")
    s = s.replace(r"\,", " ").replace(r"\;", " ").replace(r"\!", "")
    s = re.sub(r"\\textbf\{([^}]*)\}", r"**\1**", s)
    s = re.sub(r"\\emph\{([^}]*)\}", r"*\1*", s)
    s = re.sub(r"\\text(?:periodcentered|it|bf|sc)\{([^}]*)\}", r"\1", s)
    s = s.replace(r"\%", "%").replace(r"\&", "&").replace(r"\_", "_")
    s = s.replace("---", "—").replace("--", "–")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tex")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--figprefix", default="fig")
    a = ap.parse_args()
    with open(a.tex, encoding="utf-8") as f:
        md = convert(f.read(), a.figprefix)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {a.out} ({len(md)} chars)")


if __name__ == "__main__":
    main()
