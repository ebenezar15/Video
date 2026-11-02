"""PNG graphics drawn with Pillow: pop-up cards, stickers, glass widgets, paper tears, light leaks."""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .looks import hex_rgb


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), max(8, int(size)))


def _fit(draw: ImageDraw.ImageDraw, text: str, font_path: Path, max_w: int, start: int) -> ImageFont.FreeTypeFont:
    size = start
    while size > 10:
        f = _font(font_path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size = int(size * 0.9)
    return _font(font_path, size)


def _shadow(img: Image.Image, radius: int, offset: int = 6, alpha: int = 110) -> Image.Image:
    pad = radius * 3
    base = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, alpha))
    sh.putalpha(img.getchannel("A").point(lambda a: min(a, alpha)))
    base.paste(sh, (pad + offset, pad + offset), sh)
    base = base.filter(ImageFilter.GaussianBlur(radius))
    base.alpha_composite(img, (pad, pad))
    return base


def card(text: str, look: dict, W: int, kind: str = "keyword", sub: str = "") -> Image.Image:
    """Number cards are big and loud; keyword cards are a pill with the word."""
    c = look["colors"]
    style = look["card"]
    bg, fg = hex_rgb(c[style["bg"]]), hex_rgb(c[style["fg"]])
    font_path = look["title_font_file"]
    w = int(W * (0.62 if kind == "number" else 0.56))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    f = _fit(probe, text, font_path, int(w * 0.84), int(W * (0.2 if kind == "number" else 0.085)))
    tb = probe.textbbox((0, 0), text, font=f)
    th = tb[3] - tb[1]
    sf = _font(font_path, W * 0.034)
    h = int(th + W * 0.09 + (W * 0.05 if sub else 0))
    r = int(min(style["radius"] * W / 1080, h / 2))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=(*bg, 245))
    d.text((w / 2, W * 0.045 - tb[1] + th / 2), text, font=f, fill=(*fg, 255), anchor="mm")
    if sub:
        d.text((w / 2, h - W * 0.045), sub, font=sf, fill=(*fg, 200), anchor="mm")
    return _shadow(img, int(W * 0.012))


def image_card(photo: Path, look: dict, W: int, label: str = "") -> Image.Image:
    w = int(W * 0.5)
    pic = ImageOps.fit(Image.open(photo).convert("RGB"), (w, int(w * 0.75)))
    border = int(W * 0.012)
    lab_h = int(W * 0.06) if label else 0
    img = Image.new("RGBA", (w + border * 2, pic.height + border * 2 + lab_h), (255, 255, 255, 255))
    img.paste(pic, (border, border))
    if label:
        d = ImageDraw.Draw(img)
        d.text((img.width / 2, pic.height + border + lab_h / 2 + border / 2), label,
               font=_font(look["title_font_file"], W * 0.034), fill=hex_rgb(look["colors"]["primary"]), anchor="mm")
    return _shadow(img.rotate(-2.5, expand=True, resample=Image.BICUBIC), int(W * 0.012))


def sticker(text: str, look: dict, W: int) -> Image.Image:
    """Pinterest-style die-cut sticker: white outline, slight tilt."""
    c = look["colors"]
    f = _font(look["title_font_file"], W * 0.07)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tb = probe.textbbox((0, 0), text, font=f)
    pad = int(W * 0.03)
    w, h = tb[2] - tb[0] + pad * 2, tb[3] - tb[1] + pad * 2
    img = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, w + 16, h + 16), h // 2, fill=(255, 255, 255, 255))
    d.rounded_rectangle((10, 10, w + 10, h + 10), h // 2, fill=(*hex_rgb(c["accent"]), 255))
    d.text((w / 2 + 10, h / 2 + 10), text, font=f, fill=hex_rgb(c["primary"]), anchor="mm")
    return _shadow(img.rotate(6, expand=True, resample=Image.BICUBIC), int(W * 0.01))


def glass_widget(title: str, value: str, look: dict, W: int) -> Image.Image:
    """Frosted iOS-style widget card."""
    w, h = int(W * 0.5), int(W * 0.24)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), int(W * 0.04), fill=(255, 255, 255, 70), outline=(255, 255, 255, 150), width=2)
    d.text((W * 0.035, W * 0.03), title.upper(), font=_font(look["caption_font_file"], W * 0.028), fill=(255, 255, 255, 230))
    d.text((W * 0.035, h - W * 0.03), value, font=_fit(d, value, look["title_font_file"], int(w * 0.85), int(W * 0.1)),
           fill=(255, 255, 255, 255), anchor="ls")
    return img


def orbit_dot(look: dict, W: int, photo: Path | None = None) -> Image.Image:
    s = int(W * 0.14)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, s - 1, s - 1), fill=255)
    if photo:
        pic = ImageOps.fit(Image.open(photo).convert("RGBA"), (s, s))
        img.paste(pic, (0, 0), mask)
    else:
        ImageDraw.Draw(img).ellipse((0, 0, s - 1, s - 1), fill=(*hex_rgb(look["colors"]["accent"]), 255))
    ImageDraw.Draw(img).ellipse((1, 1, s - 2, s - 2), outline=(255, 255, 255, 255), width=max(2, s // 20))
    return img


def paper_tear(W: int, H: int, look: dict, seed: int = 7) -> Image.Image:
    """A full-height paper strip with torn edges, slid across the frame as a transition."""
    rnd = random.Random(seed)
    w = int(W * 1.25)
    img = Image.new("RGBA", (w, H), (0, 0, 0, 0))
    pts_l = [(int(W * 0.08 + rnd.uniform(-W * 0.03, W * 0.03)), y) for y in range(0, H + 40, 40)]
    pts_r = [(int(w - W * 0.08 + rnd.uniform(-W * 0.03, W * 0.03)), y) for y in range(H + 40, -40, -40)]
    ImageDraw.Draw(img).polygon(pts_l + pts_r, fill=(*hex_rgb(look["colors"]["paper"]), 255))
    noise = Image.effect_noise((w, H), 18).convert("L").point(lambda v: 255 - v // 6)
    tex = Image.merge("RGBA", (noise, noise, noise, img.getchannel("A")))
    return Image.blend(img, tex, 0.15)


def light_leak(W: int, H: int) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(12, 0, -1):
        r = int(W * 0.09 * i)
        a = int(16 + 8 * (12 - i))
        d.ellipse((W - r, -r // 2, W + r, r * 3 // 2), fill=(255, 150 + i * 6, 60, min(a, 120)))
    return img.filter(ImageFilter.GaussianBlur(W // 30))


def save(img: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def angle_points(n: int) -> list[float]:
    return [2 * math.pi * i / n for i in range(n)]
