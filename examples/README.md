# Reproducing the before/after image

The picture in `docs/images/look-transfer-before-after.png` was made from a free
stock clip, so you can rebuild it byte-for-byte and then swap in your own footage.

## 1. Get the source clip

The shot is **"Drone View Of Big Waves"** by *Coverr* on Pexels:
<https://www.pexels.com/video/drone-view-of-big-waves-3571264/>

Pexels clips are free to use, including commercially, without attribution
(<https://www.pexels.com/license/>). Download the 4K file and keep it outside this
repo — video files are git-ignored on purpose.

## 2. Make a flat 5-second 1080p cut

The original is 4K / 29.97 fps / 33 s. Trimming first keeps the render fast:

```bash
ffmpeg -y -i demo_src.mp4 -t 5 -vf "scale=1920:1080:flags=lanczos" \
       -r 30000/1001 -c:v libx264 -crf 18 -preset slow -an demo_flat.mp4
```

Result: 1920×1080, 150 frames, ~5.005 s.

## 3. Grade it

```bash
python scripts/lookgrade.py render demo_flat.mp4 demo_graded.mp4 \
       --params examples/params_ocean.json --crf 20
```

`examples/params_ocean.json` is the exact parameter set used for the published
image: desaturated cool shadows, mild warm highlights, two-radius halation around
the sun glints, a touch of top darkening, luminance-only grain (chroma grain is off
because heavy blue in 8-bit 4:2:0 turns it into blotches).

## 4. Build the two-panel sheet

```bash
ffmpeg -y -v error -ss 1.5 -i demo_flat.mp4   -frames:v 1 -vf scale=960:540 flat.png
ffmpeg -y -v error -ss 1.5 -i demo_graded.mp4 -frames:v 1 -vf scale=960:540 graded.png
python scripts/contact_sheet.py before-after.png "Before=flat.png" "After=graded.png"
```

## 5. Check the numbers

```bash
python scripts/lookgrade.py metrics demo_flat.mp4
python scripts/lookgrade.py metrics demo_graded.mp4
```

The demo moves saturation up ~1.4× and pulls the highlights down (p99 well below
the source), which is what this particular look asks for. Your own footage will
want a different direction — that is what `sig` on a reference clip is for.

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
