#!/usr/bin/env python3
"""Generate a PNG icon for CutIsEndless."""
from PIL import Image, ImageDraw
import math

size = 256
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background rounded rect (dark)
draw.rounded_rectangle([4, 4, 252, 252], radius=44, fill=(22, 22, 44, 255))

# Inner glow border
draw.rounded_rectangle([10, 10, 246, 246], radius=40, outline=(0, 180, 230, 100), width=2)

cx, cy = 128, 120

# Scissor blade 1 (left)
for i in range(5):
    r = 30 - i
    draw.ellipse([cx - 60 - r, cy - 20 - r, cx - 60 + r, cy - 20 + r],
                 outline=(0, 210, 255, 200 + i*10), width=2)

# Scissor blade 2 (right)
for i in range(5):
    r = 30 - i
    draw.ellipse([cx + 60 - r, cy - 20 - r, cx + 60 + r, cy - 20 + r],
                 outline=(0, 210, 255, 200 + i*10), width=2)

# Left handle
draw.rounded_rectangle([cx - 75, cy + 30, cx - 35, cy + 95], radius=12,
                       outline=(0, 210, 255), width=5)
# Right handle
draw.rounded_rectangle([cx + 35, cy + 30, cx + 75, cy + 95], radius=12,
                       outline=(0, 210, 255), width=5)

# Cross point
draw.line([(cx - 20, cy - 10), (cx + 20, cy + 10)], fill=(255, 80, 80), width=4)
draw.line([(cx + 20, cy - 10), (cx - 20, cy + 10)], fill=(255, 80, 80), width=4)

# Cut line (dashed horizontal)
for x in range(40, 220, 12):
    draw.line([(x, cy + 105), (x + 6, cy + 105)], fill=(255, 80, 80, 180), width=3)

# Text area bar at bottom
draw.rounded_rectangle([30, 195, 226, 235], radius=8, fill=(0, 180, 230, 40))

img.save("/home/bytechester/icon.png")
print("Icon saved to /home/bytechester/icon.png")
