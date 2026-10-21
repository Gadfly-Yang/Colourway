# CLI reference

Everything below is `python scripts/lookgrade.py <command> ...`.
Run without arguments to get the short usage list.

```
python scripts/lookgrade.py probe   CLIP
python scripts/lookgrade.py metrics CLIP [--frames N]
python scripts/lookgrade.py sig     CLIP [--frames N]
python scripts/lookgrade.py defaults [--out P.json]
python scripts/lookgrade.py match   STILL CLIP [--out P.json] [--base P.json] [--width 960] [--samples 3]
python scripts/lookgrade.py preview CLIP T [T ...] [--params P.json] [--width 1280]
python scripts/lookgrade.py variant CLIP T OVERRIDES TAG [--params P.json] [--width 1280]
python scripts/lookgrade.py render  CLIP OUT [--params P.json] [--size 1920x1080] [--crf 18] [--limit N]
python scripts/lookgrade.py lut     P.json OUT.cube [--size 45] [--title NAME]
```

CLIP / STILL accept any file ffmpeg can decode: mp4, mov, mkv, png, jpg.
All previews and logs land in `_grade/` (`_grade/look/` for stills) so a run never
litters the folder holding your footage.

---

## probe

```bash
python scripts/lookgrade.py probe CLIP.mp4
```

```json
{ "width": 1920, "height": 1080, "fps": 30.0, "frames": 149,
  "duration": 4.967, "codec": "hevc", "pix_fmt": "yuv420p",
  "audio": true }
```

Use it first: the frame count and duration tell you whether ffmpeg is reading the
file correctly (a variable-frame-rate mp4 can report an unexpected `fps`, which
matters for `render --fps`).

---

## metrics

```bash
python scripts/lookgrade.py metrics CLIP.mp4 --frames 40
```

Samples `N` evenly spaced frames at 480×270 (cheap, content-weighted) and prints:

| field | meaning |
|---|---|
| `luma`, `luma_std` | mean / spread of Rec.709 luma |
| `p5 p50 p95 p99` | luma percentiles — the tone shape |
| `sat` | mean HSV saturation |
| `shadow_rb` | mean `R − B` over pixels with luma < 0.25 → cool/warm of the darks |
| `high_rb` | mean `R − B` over pixels with luma > 0.70 → cool/warm of the highlights |
| `clip` | share of pixels with any channel ≥ 0.995 **or** ≤ 0.005 |

Two notes that save time:

- `high_rb` is `0.000` when nothing in the frame is above 0.70 — normal for night
  footage. Compare `shadow_rb` and the percentiles instead.
- `clip` counts **bottom** clipping too. Teal pushes the red channel of dark pixels
  toward zero, so a blue night grade legitimately reports 1–3 %; that is not white
  clipping. Check a 100 % crop before "fixing" it.

---

## sig

```bash
python scripts/lookgrade.py sig REF.mp4 --frames 24
```

The reference side of the workflow. Same metrics plus a horizontal band split:

```json
{ "luma": 0.224, "p50": 0.080, "p99": 0.935, "sat": 0.643,
  "shadow_rb": 0.087, "high_rb": 0.278, "clip": 0.233,
  "thirds": { "top": {"luma": 0.179, "rb": 0.173},
              "mid": {"luma": 0.337, "rb": 0.217},
              "bot": {"luma": 0.156, "rb": 0.043} } }
```

`thirds` is the giveaway for gradients: top dark + blue while bottom is warm means
the reference has a cool sky and a warm ground bounce (`grad_cool` / `grad_dark`).

Works on a still image too — `sig REF.png` returns one frame's numbers.

---

## defaults

```bash
python scripts/lookgrade.py defaults --out _grade/params_clip.json
```

Writes the neutral starting parameter set (all 25 keys, see the table in
`SKILL.md`). Editing that JSON is the whole tuning interface: every other command
takes `--params`.

---

## match

```bash
python scripts/lookgrade.py match REF.png CLIP.mp4 --out _grade/params_match.json
```

For a **still reference whose content differs from the clip**. It measures both
images in three luma bands (dark / mid / bright) as *hue + chroma* — not `R − B`,
because a reference's dark band is usually a black silhouette where `R − B` means
nothing — then runs a bounded coordinate search from `--base` (default: the
neutral params) over 11 knobs:

`sat, teal, teal_mid, orange, rose, c2, c3, c4, white, grad_cool, grad_dark`

A `+0.35 × distance-from-base` penalty keeps the result near the base, so the output
is a usable starting point rather than boundary-hugging nonsense. Flags: `--base`
start from your own params, `--width` analysis width (960), `--samples` clip frames
to average (3). Takes 2–6 minutes.

It prints a table so you can see what it could and could not match:

```
feature       still     clip   graded
hue_mid       0.860    0.531    0.570
chr_bright    0.390    0.267    0.389
sat           0.463    0.393    0.466
contrast      0.825    0.321    0.300
```

Read it honestly: saturation and chroma transfer well; hue only moves if the same
*object* occupies the same band in both images. In the run above the clip's mid band
is water and the still's mid band is sky, so `hue_mid` barely moved. Take the result
to `variant` and finish by eye.

---

## preview

```bash
python scripts/lookgrade.py preview CLIP.mp4 1.0 4.5 --params _grade/params_clip.json
```

Grades the frames at the given timestamps and writes 1280-wide PNGs named
`_grade/look/prev_<clip>_<t>.png`, printing metrics for each. Use at least two
timestamps with different framing — one frame that looks right is often wrong at
the other end of the shot.

`--width` sets the preview width (default 1280, height stays 16:9).

---

## variant

```bash
python scripts/lookgrade.py variant CLIP.mp4 3.5 '{"teal":0.14,"orange":0.22}' v3 --params _grade/params_clip.json
```

Same as `preview` for one timestamp, but applies an **override dict** on top of
`--params` and tags the output `_grade/look/v_<tag>.png`. This is the iteration
loop: change 2–3 keys, look, keep or revert.

`OVERRIDES` may be a JSON string or a path to a JSON file. **On Windows prefer the
file** — inline JSON through PowerShell repeatedly mangles quotes and yields
`json.decoder.JSONDecodeError`. Write `_grade/_ov.json` with `Set-Content` and pass
that path.

---

## render

```bash
python scripts/lookgrade.py render CLIP.mp4 CLIP_graded.mp4 --params _grade/params_clip.json
python scripts/lookgrade.py render CLIP.mp4 _grade/test.mp4 --params _grade/params_clip.json --limit 20
```

| flag | default | notes |
|---|---|---|
| `--params` | neutral | parameter JSON |
| `--size` | `1920x1080` | output size; changing it rescales the whole grade |
| `--crf` | `18` | x264 quality, higher = smaller/softer |
| `--limit` | all frames | render only the first N frames to sanity-check |
| `--fps` | source fps | override for odd containers |
| `--preset` | `slow` | x264 preset |
| `--audio` | `copy` | falls back to AAC when the source has no audio stream |

Writes `_grade/render.log` and prints `frames=<n> size=<MB>`. Expect roughly
1.5–2.5 s per 1080p frame on a modern laptop — a 5 s clip is a few minutes, a
30 s clip is a coffee break.

---

## lut

```bash
python scripts/lookgrade.py lut _grade/params_clip.json LUTs/look.cube --size 45
```

Bakes **colour only** into a `.cube` for Premiere / Resolve / Final Cut:
tone curve, split toning, saturation and the highlight knee. Halation, grain,
vignettes and the vertical gradients are spatial and *cannot* live in a LUT — if
those matter, render the clip instead of using the LUT.

`--size` is the cube edge (45³ is the usual sweet spot; 33³ for speed, 65³ for
gradient-heavy looks). `--title` sets the `TITLE` line inside the file.

---

## Environment

| variable | effect |
|---|---|
| `LOOKGRADE_DIR` | work directory for previews/logs (default `_grade`) |
| `FFMPEG` / `FFPROBE` | explicit binary paths when they are not on `PATH` |
| `SHEET_FONT` | font used by `contact_sheet.py` (default `C:\Windows\Fonts\msyhbd.ttc`, then DejaVu) |

Dependencies: Python 3.9+, `numpy`, `imageio` (PNG writing), `Pillow`
(only `contact_sheet.py`), and `ffmpeg`/`ffprobe` on `PATH`.

## Exit codes

`0` success · `1` any failure (bad path, missing ffmpeg, unreadable params).
Errors are printed to stderr with the offending value, so `2>&1 | tail -3` is
usually enough to see what happened.
