#!/usr/bin/env python3
"""contact_sheet.py - stack stills into a labelled before/after/reference sheet.

  python contact_sheet.py OUT.png "原片=before.png" "调色后=after.png" "风格参考=ref.png"
  python contact_sheet.py OUT.png --row --width 640 "A=a.png" "B=b.png" "C=c.png"   # side by side
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
    pos, flags = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                flags[key] = argv[i + 1]
                i += 2
            else:
                flags[key] = "1"
                i += 1
        else:
            pos.append(a)
            i += 1
    if not pos:
        raise SystemExit(__doc__)
    out, panels = pos[0], pos[1:]
    if not panels:
        raise SystemExit(__doc__)

    row = "row" in flags
    width = int(flags.get("width", 640 if row else 960))
    font = load_font(int(flags.get("font_size", 26)))
    items = []
    for spec in panels:
        label, _, path = spec.partition("=")
        img = Image.open(path).convert("RGB")
        h = round(width * img.height / img.width)
        items.append((label, img.resize((width, h), Image.LANCZOS), h))

    if row:
        h = items[0][2]
        sheet = Image.new("RGB", (width * len(items) + GAP * (len(items) - 1), h + BAR),
                          (18, 18, 18))
        draw = ImageDraw.Draw(sheet)
        x = 0
        for label, img, ih in items:
            draw.text((x + 18, 8), label, font=font, fill=(238, 238, 238))
            sheet.paste(img.resize((width, h), Image.LANCZOS), (x, BAR))
            x += width + GAP
    else:
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
