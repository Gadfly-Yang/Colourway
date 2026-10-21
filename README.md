<h1 align="center">🎬 Colourway</h1>

<p align="center">
  <b>A colourway is a colour scheme. This one you copy from a reference.</b><br/>
  Give your footage the colour of a reference photo or video — you get back the graded clip, plus a short JSON of colour settings you can read, edit and re-render. No LUT involved.
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> ｜ <a href="README_ZH.md">简体中文</a> ｜ <a href="docs/CLI.md">CLI reference</a> ｜ <a href="SKILL.md">Agent skill</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-3DA639.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-3776AB.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/runtime-ffmpeg-007808.svg" alt="ffmpeg">
  <a href="https://github.com/Gadfly-Yang/Colourway/stargazers"><img src="https://img.shields.io/github/stars/Gadfly-Yang/Colourway.svg" alt="Stars"></a>
  <a href="https://github.com/Gadfly-Yang/Colourway/issues"><img src="https://img.shields.io/github/issues/Gadfly-Yang/Colourway.svg" alt="Issues"></a>
</p>

<p align="center">
  <img src="docs/images/look-transfer-three-panel.png" alt="Flat original, reference still, graded result" width="100%">
</p>

<p align="center">
  <i>Left → right: the flat, ungraded footage · the sunset still used as the look source · the same footage after the transfer.<br/>
  One parameter set. No baked LUT. Sources: “Calm Sea Under Overcast Sky” and “Cloud Over Sea At Sunset” on Pexels.</i>
</p>

---

## 🌟 Overview

You have a video that looks flat and a picture (or another clip) whose colour you envy.
Colourway reads the reference as a **look signature** — tone percentiles,
cool/warm separation, saturation, halation, vertical structure — and then grades your
footage with a **parameterised** pipeline that reproduces those relationships.

The output is not just a video: it is a video **plus** a JSON file with the 26 numbers
that produced it. Change one number, re-render, compare. Nothing is lost in a black box.

Key features:

- 🎯 **Reference → numbers.** `sig` turns any clip or still into a comparable signature.
- 🧮 **Parametric, not a LUT.** Halation, grain and vertical gradients survive — a LUT cannot hold them.
- 🎛️ **26 readable knobs.** Tone curve (`black … white`), split toning, hue-selective pushes, halation radii, grain, vignette.
- 🖼️ **Stills welcome.** Grade a video against a photo, or grade a photo itself.
- 🎞️ **Audio kept.** `render` copies the original audio stream untouched.
- 🧩 **Agent-ready.** Ships as a Claude-style skill (`SKILL.md`) with the translation table from numbers to parameters.
- 🐍 **Tiny dependency surface.** numpy + ffmpeg. No OpenCV, no scipy, no compiled extensions.

## 🤔 Why not just bake a LUT?

Because a graded clip is not a colour function. The look you are copying contains
**halation** (light bleeding around bright edges), local glow, a vertical gradient and
grain — all spatial effects. Bake them into a 45³ LUT and you get a transform that
reproduces average colours but destroys the bloom that made the reference look expensive.

Measured on a real pair (a clip and its graded version, 128 frames):

| Approach | Held-out frame error |
|---|---|
| 45³ 3D LUT learned from frame pairs | **14.7 dB PSNR** — unusable |
| Parameters (tone + split tone + halation), 16 knobs | **mean abs error 0.0196** |

So the grade stays as numbers you can read, diff, re-render and explain.

## 🚀 Quick start

**Requirements**

```bash
pip install numpy imageio pillow   # Pillow only for contact_sheet.py
ffmpeg -version                    # ffmpeg + ffprobe must be on PATH
```

Python 3.9+. No GPU. Rendering is CPU numpy plus pipes to ffmpeg.

**Grade a clip against a reference**

```bash
# 1. what am I working with?
python scripts/lookgrade.py probe   myclip.mp4
python scripts/lookgrade.py metrics myclip.mp4

# 2. what does the reference look like? (video or still)
python scripts/lookgrade.py sig     reference.mp4

# 3. neutral starting point — this JSON *is* the tuning interface
python scripts/lookgrade.py defaults --out _grade/params_myclip.json

# 4. iterate: change 2–3 keys, look at two timestamps, repeat
python scripts/lookgrade.py variant myclip.mp4 3.5 _grade/_ov.json v3 --params _grade/params_myclip.json
python scripts/lookgrade.py preview myclip.mp4 1.0 4.5 --params _grade/params_myclip.json

# 5. full render + proof
python scripts/lookgrade.py render  myclip.mp4 myclip_graded.mp4 --params _grade/params_myclip.json
python scripts/lookgrade.py metrics myclip_graded.mp4

# 6. optional: a .cube for Premiere / Resolve (colour only — no halation, no grain)
python scripts/lookgrade.py lut _grade/params_myclip.json LUTs/look.cube
```

> 💡 **Tip**: every still, preview and log lands in `_grade/`, so a run never scatters
> files next to your footage. Point `variant` at two or three timestamps before you
> commit to a full render — one frame flatters, three tell the truth.

## 🧠 What "reading the style" means

`sig` turns a reference into numbers — tone percentiles, cool/warm separation in the
darks and highlights, saturation, and a three-band vertical split:

```json
{ "luma": 0.224, "p50": 0.080, "p99": 0.935, "sat": 0.643,
  "shadow_rb": 0.087, "high_rb": 0.278, "clip": 0.233,
  "thirds": { "top": {"luma": 0.179, "rb": 0.173},
              "mid": {"luma": 0.337, "rb": 0.217},
              "bot": {"luma": 0.156, "rb": 0.043} } }
```

Those numbers are a **direction, not a target**: content differs, so absolute values are
not comparable between two clips. `shadow_rb` well below zero means the darks are
teal-shaped; `high_rb` above +0.2 means warm highlights; a dark top band with a warm
bottom means you need a vertical gradient.

| Signature reading | What it means | Knobs to reach for |
|---|---|---|
| `shadow_rb` ≪ 0 | darks lean teal | `teal`, `teal_mid` |
| `high_rb` > +0.2 | highlights lean warm | `orange`, `rose` |
| `p99` close to 1.0 | blown highlights in the reference | `white`, `knee` |
| `thirds.top` dark + `thirds.bot` warm | vertical colour ramp | `grad_dark`, `grad_cool` |
| `sat` far above your clip | reference is heavily saturated | `sat`, `warm_sat` |

The full translation table lives in [SKILL.md](SKILL.md).

## 🛠 Commands

| Command | What it does |
|---|---|
| `probe CLIP` | resolution / fps / frames / duration / audio |
| `metrics CLIP` | tone percentiles, saturation, cool–warm split, clipping |
| `sig REF` | the same, plus a three-band vertical split — the reference side |
| `defaults --out P.json` | neutral parameter set (all 26 keys) |
| `match STILL CLIP` | still reference + different content: bounded search for a starting point |
| `preview CLIP T…` | grade the frames at those timestamps, 1280-wide PNGs |
| `variant CLIP T OV TAG` | one timestamp + an override dict — the iteration loop |
| `render CLIP OUT` | full clip, H.264 crf 18, audio copied, progress in `_grade/render.log` |
| `lut P.json OUT.cube` | bake the colour part into a `.cube` |

Full flags, exit codes and environment variables: [docs/CLI.md](docs/CLI.md).

## 🎛 The parameters

All in display space, 0–1. Six tone control points (`black, c1 … c4, white`), then:

| Group | Keys |
|---|---|
| Split toning | `teal` (darks), `teal_mid` (midtones), `teal_g` (teal ↔ blue), `orange` (highlights), `rose` (magenta highlights) |
| Hue-selective | `cool_amt`, `warm_amt` — push only the pixels that are already blue / already red |
| Chroma | `sat`, `warm_sat` (warm pixels only) |
| Halation | `glow_thr`, `glow_amt`, `glow_r1`, `glow_r2` (two radii, ~3 % and ~15 % of the frame) |
| Spatial | `grad_cool`, `grad_dark` (vertical), `vignette` |
| Texture | `grain`, `grain_chroma` |
| Safety | `knee`, `knee_gain` — per-channel soft highlight knee |

Suggested ranges for every key are in [SKILL.md](SKILL.md).

## 📊 Verification, not vibes

The demo deltas are what *this* look asks for, not a universal target:

| | source | graded |
|---|---|---|
| saturation | 0.187 | **0.487** |
| luma | 0.678 | **0.412** |
| p50 (midtones) | 0.745 | **0.416** |
| p99 (highlights) | 0.904 | **0.623** |
| `shadow_rb` (darks) | −0.175 | **−0.356** |

The source is a flat overcast seascape: saturation ×2.6, the whole upper range pulled down
(p99 0.904 → 0.623, so no pixel above 0.70 survives and `high_rb` stops reporting), darks
pushed further into teal, and a top-down gradient that darkens the sky so the horizon band
is the brightest thing in frame.

> ⚠️ `clip` reports 0.089 — mostly **bottom** clipping, i.e. teal pushing the red channel
> of deep-shade pixels to zero. `metrics` counts both ends on purpose; check a 100 % crop
> before treating it as a problem.

## 🧪 Rules learned the hard way

1. **Do not chase the reference's absolute numbers.** Different content means incomparable
   `sat` / `p99`. Match the *direction*: darks go teal, highlights go warm and come down,
   saturation goes up.
2. **Brightness-keyed toning fails on mixed lighting.** In a night shot the sodium-lit wall
   sits in the *dark* band, so "push the darks teal" paints it grey. Use `cool_amt` /
   `warm_amt`: they separate by hue, so orange walls stay orange.
3. **Soft-knee the highlights.** Hard clipping saturates one channel before the others and
   the hue jumps. `knee 0.94 / knee_gain 0.45` cut channel clipping from 19.7 % to ~5 % on
   a test clip.
4. **Turn chroma grain off for dark footage.** 8-bit 4:2:0 turns chroma noise into blotches;
   luminance-only grain also dithers smooth sky gradients and prevents banding.
5. **Two timestamps minimum.** A grade that flatters one frame routinely crushes the next.
6. **Statistics can point, not decide.** On one reference, four hand grades landed at
   warm–cool splits from 0.15 to 0.68 (reference 0.396). A metric built on those numbers
   scored the hand-graded version *worse* than doing nothing (4.05 vs 3.26) — which is why
   there is no "auto-solve to the reference" button.

## ❓ FAQ

<details>
<summary><b>Do I need a GPU?</b></summary>

No. It is numpy on the CPU, roughly 1.5–2.5 s per 1080p frame — fine for a few minutes of
footage, not for a feature. `--limit N` renders a short proof before you commit.
</details>

<details>
<summary><b>Does the reference have to be the same content as my clip?</b></summary>

No, and it usually is not. The signature gives *direction*; you close the gap by hand.
Same-content pairs are easier (you can compare frame against frame), but any graded still
is enough to start.
</details>

<details>
<summary><b>Can I use the result in Premiere / Resolve?</b></summary>

Two ways: drop the rendered clip in (audio intact), or export a `.cube` with `lut` and apply
it in Lumetri / Resolve. The LUT carries colour only — halation, grain and the vertical
gradients are spatial and stay in the render.
</details>

<details>
<summary><b>Why are there nine commands instead of one `auto` button?</b></summary>

Because the interesting decisions are editorial: how dark, how warm, how much bloom. The
tool measures, previews and renders quickly so those decisions are cheap to make — it does
not pretend to make them.
</details>

## 🧩 Using it from an AI agent

`SKILL.md` is a self-contained skill: the workflow, the parameter table with suggested
ranges, the translation rules above, and known failure modes. Drop the folder into your
agent's skills directory and ask it to "grade this clip like that reference" — it has
everything it needs, including `scripts/contact_sheet.py` for the three-panel proof image.

## 🙏 Credits

- Demo footage — [Calm Sea Under Overcast Sky](https://www.pexels.com/video/34727351/) via Pexels (free, no attribution required, [licence](https://www.pexels.com/license/)).
- Reference still — [Cloud Over Sea At Sunset](https://www.pexels.com/photo/cloud-over-sea-at-sunset-20141165/) via Pexels, same licence.
- Extra ocean demo — [Drone View Of Big Waves](https://www.pexels.com/video/drone-view-of-big-waves-3571264/) by Coverr (`examples/params_ocean.json`).
- The engine calls `ffmpeg` as an external program; it does not bundle it.

## 📄 License

MIT — see [LICENSE](LICENSE). Do whatever you want, no warranty.

## ⭐ Star history

[![Star History Chart](https://api.star-history.com/svg?repos=Gadfly-Yang/Colourway&type=Date)](https://star-history.com/#Gadfly-Yang/Colourway&Date)

---

<p align="center">If this saved you an evening of colour wheels, consider a ⭐ — it helps other editors find it.</p>
