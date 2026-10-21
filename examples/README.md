# Reproducing the three-panel image

The picture in `docs/images/look-transfer-three-panel.png` is built from two free stock
assets, so you can rebuild it and then swap in your own footage:

1. **the flat footage** — a grey, foggy aerial: almost no colour (saturation 0.084)
2. **the reference still** — a warm sunset over the sea, used only as a look source
3. **the result** — the same aerial graded with `examples/params_foggy_sunset.json`

## 1. Get the assets

| Panel | Asset | Link |
|---|---|---|
| 1 & 3 | **"Foggy"** — 4K aerial, 41 s | <https://www.pexels.com/video/36411791/> |
| 2 | **"Cloud Over Sea At Sunset"** — still | <https://www.pexels.com/photo/cloud-over-sea-at-sunset-20141165/> |

Pexels assets are free to use, including commercially, without attribution
(<https://www.pexels.com/license/>). Keep the downloads outside this repo — video and
image files are git-ignored on purpose.

```bash
curl -L -o demo_src.mp4  "https://www.pexels.com/download/video/36411791/"
curl -L -o ref_style.jpg "https://images.pexels.com/photos/20141165/pexels-photo-20141165.jpeg?cs=srgb&fm=jpg&w=1920"
```

## 2. Make a flat 5-second 1080p cut

```bash
ffmpeg -y -v error -ss 1 -t 5 -i demo_src.mp4 \
       -vf "scale=1920:1080:flags=lanczos,fps=30" \
       -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -an demo_flat.mp4
ffmpeg -y -v error -i ref_style.jpg -vf "scale=1920:1080:flags=lanczos" ref_1080.png
```

Result: 1920×1080, 150 frames, 5.0 s, no audio.

## 3. Read the reference, then grade

`sig` on the still gives the direction (warm darks *and* warm highlights would mean an
amber wash; here the still separates warm sky from cool water, which is what we copy):

```bash
python scripts/lookgrade.py sig ref_1080.png
python scripts/lookgrade.py render demo_flat.mp4 demo_graded.mp4 \
       --params examples/params_foggy_sunset.json --crf 18
```

The parameter set: highlights compressed into a warm hazy band (`orange` 0.45,
`white` 0.80), a cool cast pushed into the darks (`teal` 0.20, `teal_mid` 0.10), the top
of the frame darkened (`grad_dark` 0.28) so the horizon reads as the brightest line, and
luminance-only grain (chroma grain is off — heavy blue in 8-bit 4:2:0 turns it into
blotches).

## 4. Build the three-panel sheet

```bash
ffmpeg -y -v error -ss 2 -i demo_flat.mp4   -frames:v 1 -vf scale=960:540 src.png
ffmpeg -y -v error -i ref_1080.png          -vf scale=960:540 ref.png
ffmpeg -y -v error -ss 2 -i demo_graded.mp4 -frames:v 1 -vf scale=960:540 graded.png
python scripts/contact_sheet.py three-panel.png \
       "Original (flat, ungraded)=src.png" \
       "Reference still (look source)=ref.png" \
       "Graded (after transfer)=graded.png"
```

## 5. Check the numbers

```bash
python scripts/lookgrade.py metrics demo_flat.mp4
python scripts/lookgrade.py metrics demo_graded.mp4
```

Expected movement: saturation 0.08 → ~0.52, luma 0.57 → ~0.38, p99 0.87 → ~0.59,
`shadow_rb` +0.02 → −0.30, `high_rb` −0.06 → +0.25.

## Using your own footage

```bash
python scripts/lookgrade.py probe   myclip.mp4
python scripts/lookgrade.py metrics myclip.mp4
python scripts/lookgrade.py sig     reference.mp4        # or reference.png
python scripts/lookgrade.py defaults --out _grade/params_myclip.json
python scripts/lookgrade.py variant myclip.mp4 3.5 _grade/_ov.json v1 --params _grade/params_myclip.json
python scripts/lookgrade.py render  myclip.mp4 myclip_graded.mp4 --params _grade/params_myclip.json
```

Change two or three keys per iteration, and look at two different timestamps before
committing to a full render.
