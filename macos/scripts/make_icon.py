"""Draws the ClipForge app icon (a dark squircle with an amber tally light and a 9:16 frame) into an .iconset."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def icon(size: int) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(s * 0.09)
    d.rounded_rectangle((pad, pad, s - pad, s - pad), int(s * 0.2), fill=(22, 25, 30, 255))
    # vertical 9:16 frame
    fw, fh = int(s * 0.34), int(s * 0.6)
    fx, fy = (s - fw) // 2, (s - fh) // 2 + int(s * 0.02)
    d.rounded_rectangle((fx, fy, fx + fw, fy + fh), int(s * 0.05), outline=(236, 233, 227, 255), width=max(2, s // 40))
    # caption bar
    d.rounded_rectangle((fx + fw * 0.18, fy + fh * 0.7, fx + fw * 0.82, fy + fh * 0.78), int(s * 0.015), fill=(255, 178, 62, 255))
    # tally light with glow
    r = int(s * 0.06)
    cx, cy = fx + fw, fy
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - r * 2, cy - r * 2, cx + r * 2, cy + r * 2), fill=(255, 178, 62, 120))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s // 40)))
    ImageDraw.Draw(img).ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 178, 62, 255))
    return img


def main(out: str) -> None:
    d = Path(out)
    d.mkdir(parents=True, exist_ok=True)
    base = icon(1024)
    for pt in (16, 32, 128, 256, 512):
        base.resize((pt, pt), Image.LANCZOS).save(d / f"icon_{pt}x{pt}.png")
        base.resize((pt * 2, pt * 2), Image.LANCZOS).save(d / f"icon_{pt}x{pt}@2x.png")


if __name__ == "__main__":
    main(sys.argv[1])
