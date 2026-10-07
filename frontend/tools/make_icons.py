"""Draws the app icons in static/icons/: one split flap showing an S, in the
page's colours.

Run from frontend/ (needs Pillow and the DejaVu fonts):
    python tools/make_icons.py static/icons
"""
import sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
BG, FLAP, FLAP_TOP, TEXT, SPLIT = '#121212', '#1d1d1d', '#262626', '#f2f2f2', '#000000'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def icon(size, inset):
    """`inset` is the share of the icon left as background round the flap
    (bigger for a maskable icon, whose edges the phone may crop)."""
    scale = 4   # draw big, then shrink, for smooth edges
    s = size * scale
    img = Image.new('RGB', (s, s), BG)
    d = ImageDraw.Draw(img)
    pad = round(s * inset)
    box = [pad, pad, s - pad, s - pad]
    radius = round((s - 2 * pad) * 0.12)
    mid = s // 2
    d.rounded_rectangle(box, radius, fill=FLAP)
    d.rounded_rectangle([box[0], box[1], box[2], mid], radius, fill=FLAP_TOP, corners=(True, True, False, False))
    font = ImageFont.truetype(FONT, round((s - 2 * pad) * 0.72))
    d.text((mid, mid + round(s * 0.01)), 'S', font=font, fill=TEXT, anchor='mm')
    # The split between the two halves, with the hinge pins either side.
    gap = max(scale, round(s * 0.014))
    d.rectangle([box[0], mid - gap // 2, box[2], mid + gap // 2], fill=SPLIT)
    pin_w, pin_h = round(s * 0.035), round(s * 0.09)
    for x in (box[0] - pin_w // 2, box[2] - pin_w // 2):
        d.rounded_rectangle([x, mid - pin_h // 2, x + pin_w, mid + pin_h // 2], pin_w // 2, fill='#3a3a3a')
    return img.resize((size, size), Image.LANCZOS)


for name, size, inset in [('icon-192.png', 192, 0.08), ('icon-512.png', 512, 0.08),
                          ('icon-maskable-512.png', 512, 0.2), ('apple-touch-icon.png', 180, 0.1),
                          ('favicon-32.png', 32, 0.04)]:
    icon(size, inset).save(f'{OUT}/{name}', optimize=True)
