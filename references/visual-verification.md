# Seeing the pages: getting a vision tool, and using it

The single largest source of error in this skill's history was **not having a vision tool and
not realising the tool was one config line away**. A whole session was spent building
ASCII-art substitutes for looking at a page, and it still produced two silent factual errors
(reversed signs in one problem, a wrong "page not found" verdict for another). Two minutes of
checking the modality declaration would have avoided all of it.

**Read this before you accept a text-only workflow.**

---

## 0. Confirm you can actually see the pages (do this first)

```
read_image -> cannot read "<path>" as an image: model "<model>" does not declare image input
```

If you see this, the model route has no `image` input modality declared. **Do not** conclude
"this session has no vision" and fall back to ASCII-art / glyph-IoU substitutes. Fix the
declaration, then retry — see the next section.

Sanity checks worth doing **once** per environment, before committing to a workflow:

| check | how | what it tells you |
|---|---|---|
| does the main agent have `read_image`? | list your tools | gate is present |
| does the *subagent* tool set include `read_image`? | spawn a one-line probe subagent: "list your exact tool names; if you have `read_image`, call it on `<path>` and describe the image" | subagents often inherit the same tool set — **verify, don't assume** |
| is the model route declared image-capable? | see below | fixes the gate |
| does the provider *really* accept images? | send a control image with a known answer straight to the endpoint (see "Control probe") | a config claim is not a runtime probe |

**Lesson:** a capability declaration in config is a *claim*. A tool that appears in your tool
list is also a claim. Both can be wrong, and both can be right while you assume wrong. Probe.

## 1. Declaring image input (dsh + `dsh-llm-pi-ai`)

The gate lives in the fs tool: it reads `active.inputModalities` and refuses if `image` is
absent. The provider adapter defaults to `DEFAULT_INPUT = ["text"]`, so a model entry that
never mentions `input` is text-only **even if the underlying model is multimodal**.

Fix in `~/.dsh/settings.yaml`, per model:

```yaml
llm-pi-ai:
  providers:
    <provider-name>:
      # optional provider-wide default
      # defaultInput: [text, image]
      # defaultContextWindow: 1024000
      models:
        - name: <model-id>
          input: [text, image]        # ← the line that turns read_image on
          contextWindow: 1024000
          maxTokens: 384000
```

Notes:

- **Takes effect immediately in the running session** — no restart, no new session required.
  On dsh the profile is `patchReload: "live"` and the image gate calls
  `resolveModelInfo(provider, model, signal)` on *every* invocation, so the next `read_image`
  call already sees the new declaration. (An earlier note in this skill's history claimed a
  restart was needed. That was wrong.)
- Back up the settings file before editing, and diff afterwards
  (`diff = N added / 0 removed` is the shape you want — a *pure addition*).
- Confirm the file is the one actually being read: there is normally only
  `~/.dsh/settings.yaml`; an additional project-level or profile-level settings file would
  compete with it. Check before trusting the edit.
- Validate the YAML through the plugin's own schema rather than by eye. For cordis plugins the
  `Config` export is a *Schema constructor*, not a schema object — `Config.safeParse` does not
  exist. Use:

  ```js
  const res = await Config['~standard'].validate(raw)   // Standard Schema
  ```

- **Only declare `image` for models you have actually seen accept an image.** The adapter's own
  source warns that over-claiming fails mid-turn and leaves the session repeating a request that
  cannot succeed. A text-only model declared as image-capable is worse than an honest refusal.

### Control probe (is the *provider* really multimodal?)

Ask the endpoint directly with an image whose content you know, then check the answer:

1. Generate a small PNG with a known payload — e.g. a shape, a colour, and a 5-digit number.
2. POST it in the chat/responses payload the provider expects.
3. The model must read back all three. A reply of `NO_IMAGE`, a refusal, or a wrong number means
   the route is text-only **regardless of what the catalogue says**.
4. Also send the same prompt *without* the image: if the answer is the same, you are being
   hallucinated at, not read.

Record the result per model. Catalogue pages (vendor docs, aggregator mirrors, model cards) are
useful for `contextWindow` / `maxTokens` but they are not evidence about this key and this
endpoint — plans differ, and a key can be authorised for one API shape and 401 on another.

## 2. Render so the model can actually read it

The image reader **downsamples** large images. Measured on this harness:

| source | result |
|---|---|
| 1654 × 1287 (2.1 Mpx) | kept native |
| 1150 × 1209 | kept native |
| 2550 × 3263 (8.3 Mpx, a 300 dpi letter page) | downsampled to 1315 × 1672 |

So a whole page at 300 dpi loses ~60 % of its linear resolution. Body text survives; a
`size≈6.1` superscript does not.

**Tiling recipe** — `scripts/crop_rect.py` implements it; use it rather than re-deriving:

```bash
python scripts/crop_rect.py tiles -i book.pdf -o .scratch/tiles -p 148-152 -g 2x2 -d 300
python scripts/crop_rect.py box   -i book.pdf -o .scratch/probs -d 300 \
    p149_15:149:50,660,335,783  p150_21:150:300,380,612,520
```

The equivalent by hand, if you need to fold it into a larger script:

```python
import pymupdf
from PIL import Image

DPI, OV = 300, 40                      # 300 dpi, 40 px overlap between quadrants
mat = pymupdf.Matrix(DPI / 72, DPI / 72)
for pno in pages:
    pix = doc[pno].get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    W, H = img.size
    hw, hh = W // 2, H // 2
    for tag, box in {
        "q0": (0, 0, hw + OV, hh + OV),   "q1": (hw - OV, 0, W, hh + OV),
        "q2": (0, hh - OV, hw + OV, H),   "q3": (hw - OV, hh - OV, W, H),
    }.items():
        img.crop(box).save(OUT / f"p{pno}_{tag}.png")
```

A quadrant of a 300 dpi letter page is ≈1315 × 1672 px — right at the limit, still native, and
the text is crisp. **Never read a whole 300 dpi page.**

**Targeted crops by PDF-point box** — better when you want one problem:

```python
pix = doc[pno].get_pixmap(matrix=pymupdf.Matrix(DPI / 72, DPI / 72),
                          clip=pymupdf.Rect(x0, y0, x1, y1))   # points, page is 612x783
```

Because the exercise area is two columns *each split into two sub-columns*, a column-shaped
crop about 280 pt wide × 200 pt tall gives a perfectly legible single problem.

Build the crop list once and keep it as a file — it is the index of the whole job, and the
reviewer subagents can re-run the same specs. A transposed `x0>x1` pair is a common hand-typing
slip; `crop_rect.py` reorders rather than emitting a blank image, and prints the clamped rect so
you notice.

**DPI by purpose**

| purpose | dpi |
|---|---|
| reading body text, problem statements | 300 (tiled) |
| settling one symbol / one line / a fraction bar | 600, tiny clip |
| figures destined for the final PDF | 400, written straight into `fig/` |

**Test the tool once on a small file before building a pipeline on it.** Reading one known
image and confirming you can describe it takes seconds and de-risks everything after.

## 3. Transcript → LaTeX → verify

1. Transcribe from the **images**, not from the text layer.
2. Build the `.tex` (group instructions included — see `SKILL.md`).
3. Compile, then **render the output and look at every page** (200 dpi, split top/bottom).
   Check: every problem present, numbering continuous, formulas render, no `??`, no heading
   stranded at a page bottom, figures clear and correctly placed.
4. **Cross-check with subagents, one per section.** Since subagents have the same vision tool,
   a fresh reviewer with no stake in your transcription is cheap and effective.

### Subagent cross-check recipe

Give each reviewer:

- the transcript path (and its own section, named explicitly),
- the tile paths for its pages, plus `scripts/crop_rect.py` and the PDF path so it can make its
  own tighter crops,
- the glyph-trap table (so it knows the text layer lies, and which way),
- an explicit output contract: one line per problem,
  `- #3 ✅ match` / `- #3 ❌ transcript says X, source says Y, evidence: <page/coords>`, and an
  explicit `⚠️ cannot determine` when it cannot settle something,
- the instruction to **report the method it used** (visual vs text layer), and
- the instruction not to edit any existing file.

In the MAT1001 HW3 build this ran as four subagents in parallel (one per section). All four
returned **zero transcription errors** on 39 problems — but between them they found **two
structural omissions** the main agent had made:

- a whole exercise-group instruction paragraph was missing in one section (it governed the
  problems at the end of that section, which is exactly where attention thins out), and
- a blue sub-heading was missing.

Neither was a maths error, and neither would have been caught by re-reading your own transcript.
That is the value of the pass: it checks *completeness of structure*, not just symbol identity.

## 4. If you genuinely have no vision tool

Only after the checks in §0 have failed. Report the limitation to the user and offer the fix
(§1) before starting — do not silently substitute an ASCII renderer.

`scripts/glyphcheck.py` (descender test + baseline-anchored shape IoU) and an ASCII half-block
renderer are legitimate tools for settling a *single glyph* when the text layer lies. They are
**not** a substitute for reading the page: this skill's own history has a build where a
text-layer-only pass reversed the signs of a polynomial and mis-filed a problem's page, and
neither error was detectable by any amount of text-layer cross-checking.

If the user cannot enable vision, say so plainly, deliver the transcription as a **draft**, and
state which problems are low-confidence.
