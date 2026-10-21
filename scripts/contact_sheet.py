#!/usr/bin/env python3
"""contact_sheet.py - stack stills into a labelled before/after/reference sheet.

  python contact_sheet.py OUT.png "原片=before.png" "调色后=after.png" "风格参考=ref.png"
  python contact_sheet.py OUT.png LABEL=PATH ... --width 960 --font "C:/Windows/Fonts/msyhbd.ttc"

Panels are letterboxed to a 16:9 box; each gets a label bar. Height is derived from
the panel aspect so a 2.39:1 clip does not get squashed.
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

GAP = 10
BAR = 46


def load_font(size=26):
    for cand in (os.environ.get("SHEET_FONT"),
                 r"C:\Windows\Fonts\msyhbd.ttc",
                 r"C:\Windows\Fonts\msyh.ttc",
                 "/System/Library/Fonts/PingFang.ttc",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if cand and os.path.exists(cand):
            try:
                return ImageFont.truetype(cand, size)
            except OSError:
                continue
    return ImageFont.load_default()


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {}
    for i, a in enumerate(argv):
        if a.startswith("--") and i + 1 < len(argv):
            flags[a[2:]] = argv[i + 1]
    out, panels = args[0], args[1:]
    if not panels:
        raise SystemExit(__doc__)

    width = int(flags.get("width", 960))
    font = load_font(int(flags.get("font_size", 26)))
    items = []
    for spec in panels:
        label, _, path = spec.partition("=")
        img = Image.open(path).convert("RGB")
        h = round(width * img.height / img.width)
        items.append((label, img.resize((width, h), Image.LANCZOS), h))
    body = sum(h for _, _, h in items) + GAP * (len(items) - 1)
    sheet = Image.new("RGB", (width, body + BAR * len(items)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    y = 0
    for label, img, h in items:
        draw.text((18, y + 8), label, font=font, fill=(238, 238, 238))
        sheet.paste(img, (0, y + BAR))
        y += BAR + h + GAP
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    sheet.save(out, optimize=True)
    print(f"wrote {out} {sheet.size}")


if __name__ == "__main__":
    main(sys.argv[1:])
