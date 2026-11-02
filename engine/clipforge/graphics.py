"""Motion graphics for professional content: lower thirds, counting stats, bar charts, chapter and quote cards,
checklists and end cards. Each is drawn with Pillow as a short RGBA frame sequence (eased motion, count-ups,
any font or script) and overlaid by ffmpeg at its word."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .looks import hex_rgb

FPS = 30
TYPES = {
    "lower_third": {"label": "Lower third", "duration": 3.5, "about": "Name and role slide in above the captions",
                    "fields": ["title", "subtitle"]},
    "counter": {"label": "Counting stat", "duration": 2.4, "about": "A number counts up with a label",
                "fields": ["value", "prefix", "suffix", "label"]},
    "bar_chart": {"label": "Bar chart", "duration": 3.5, "about": "Up to 5 bars grow in, values count up",
                  "fields": ["title", "labels", "values"]},
    "chapter_card": {"label": "Chapter card", "duration": 1.6, "about": "Full-frame wipe with a section title",
                     "fields": ["title", "number"]},
    "quote_card": {"label": "Quote card", "duration": 3.0, "about": "Pull-quote on a paper card",
                   "fields": ["text", "attribution"]},
    "checklist": {"label": "Checklist", "duration": 3.5, "about": "Items tick in one by one",
                  "fields": ["title", "items"]},
    "end_card": {"label": "End card", "duration": 2.5, "about": "Call to action and handle over the last seconds",
                 "fields": ["text", "handle"]},
}


def ease_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def envelope(t: float, d: float, k: float = 0.3) -> float:
    """0 -> 1 in k seconds, hold, 1 -> 0 in the last k seconds."""
    return min(ease_out(t / k), ease_out((d - t) / k))


def _num(v) -> float:
    return float("".join(ch for ch in str(v) if ch.isdigit() or ch == ".") or 0)


class Painter:
    def __init__(self, look: dict, W: int, H: int):
        self.look, self.W, self.H = look, W, H
        self.c = {k: hex_rgb(v) for k, v in look["colors"].items()}
        self._fonts: dict = {}

    def font(self, size: float, title: bool = True) -> ImageFont.FreeTypeFont:
        key = (int(size), title)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(str(self.look["title_font_file" if title else "caption_font_file"]), max(8, int(size)))
        return self._fonts[key]

    def wrap(self, text: str, size: float, max_w: float, title: bool = True) -> list[str]:
        f = self.font(size, title)
        lines, cur = [], ""
        for w in str(text).split():
            trial = f"{cur} {w}".strip()
            if f.getlength(trial) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        return lines + ([cur] if cur else [])

    def rgba(self, key: str, a: float = 1.0) -> tuple[int, int, int, int]:
        return (*self.c[key], int(255 * max(0.0, min(1.0, a))))


def layout(kind: str, f: dict, P: Painter) -> tuple[int, int, int, int]:
    """Box (x, y, w, h) in frame pixels for a graphic."""
    W, H = P.W, P.H
    if kind == "lower_third":
        return int(W * 0.05), int(H * 0.6), int(W * 0.82), int(H * 0.09)
    if kind == "counter":
        return int(W * 0.12), int(H * 0.14), int(W * 0.76), int(H * 0.2)
    if kind == "bar_chart":
        return int(W * 0.08), int(H * 0.12), int(W * 0.84), int(H * 0.4)
    if kind == "chapter_card":
        return 0, 0, W, H
    if kind == "quote_card":
        lines = P.wrap(f"“{f.get('text', '')}”", H * 0.032, W * 0.7)
        return int(W * 0.08), int(H * 0.13), int(W * 0.84), int(H * 0.09 + len(lines) * H * 0.032 * 1.25)
    if kind == "checklist":
        n = len(list(f.get("items") or [])[:5])
        return int(W * 0.08), int(H * 0.13), int(W * 0.84), int(H * 0.08 + n * H * 0.027 * 1.8)
    if kind == "end_card":
        return int(W * 0.06), int(H * 0.36), int(W * 0.88), int(H * 0.22)
    raise ValueError(f"Unknown graphic '{kind}'")


def draw(kind: str, f: dict, P: Painter, t: float, d: float, box: tuple[int, int, int, int]) -> Image.Image:
    _, _, bw, bh = box
    W, H = P.W, P.H
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    g = ImageDraw.Draw(img)
    env = envelope(t, d)
    if kind == "lower_third":
        off = int(-bw * (1 - env))
        g.rectangle((off, 0, off + int(W * 0.012), bh), fill=P.rgba("accent"))
        g.rectangle((off + int(W * 0.012), 0, off + bw, bh), fill=P.rgba("primary", 0.86))
        g.text((off + W * 0.045, bh * 0.12), str(f.get("title", "")), font=P.font(H * 0.03), fill=P.rgba("ink"))
        if f.get("subtitle"):
            g.text((off + W * 0.045, bh * 0.58), str(f["subtitle"]), font=P.font(H * 0.019, False), fill=P.rgba("accent"))
    elif kind == "counter":
        g.rounded_rectangle((0, 0, bw - 1, bh - 1), int(H * 0.015), fill=P.rgba("primary", 0.82 * env))
        val = _num(f.get("value", 0)) * ease_out(t / min(1.4, d * 0.6))
        txt = f"{f.get('prefix', '')}{int(round(val)):,}{f.get('suffix', '')}"
        g.text((bw / 2, bh * 0.42), txt, font=P.font(H * 0.085), fill=P.rgba("accent", env), anchor="mm")
        if f.get("label"):
            g.text((bw / 2, bh * 0.82), str(f["label"]), font=P.font(H * 0.022, False), fill=P.rgba("ink", env), anchor="mm")
    elif kind == "bar_chart":
        labels = list(f.get("labels") or [])[:5]
        values = [float(v) for v in (f.get("values") or [])][:len(labels)]
        g.rounded_rectangle((0, 0, bw - 1, bh - 1), int(H * 0.012), fill=P.rgba("paper", 0.94 * env))
        if f.get("title"):
            g.text((bw * 0.05, bh * 0.05), str(f["title"]), font=P.font(H * 0.024), fill=P.rgba("primary", env))
        if values:
            top = max(values) or 1
            n = len(values)
            gap = bw * 0.06
            w = (bw - gap * (n + 1)) / n
            base, maxh = bh * 0.84, bh * 0.58
            for i, (lab, v) in enumerate(zip(labels, values)):
                grow = ease_out((t - 0.15 * i) / 0.8)
                x = gap + i * (w + gap)
                h = maxh * v / top * grow
                g.rectangle((x, base - h, x + w, base), fill=P.rgba("accent" if v == top else "primary", env))
                g.text((x + w / 2, base - h - H * 0.004), f"{v * grow:,.0f}", font=P.font(H * 0.02), fill=P.rgba("primary", env), anchor="ms")
                g.text((x + w / 2, base + H * 0.008), str(lab)[:12], font=P.font(H * 0.016, False), fill=P.rgba("primary", env), anchor="ma")
    elif kind == "chapter_card":
        wipe = min(ease_out(t / 0.3), ease_out((d - t) / 0.3))
        g.rectangle((0, 0, int(bw * wipe), bh), fill=P.rgba("primary"))
        a = envelope(t - 0.15, d - 0.15, 0.2)
        if f.get("number") not in (None, ""):
            g.text((bw / 2, bh * 0.4), f"{int(_num(f['number'])):02d}", font=P.font(H * 0.05), fill=P.rgba("accent", a), anchor="mm")
        y = bh * 0.46
        for line in P.wrap(f.get("title", ""), H * 0.05, W * 0.8):
            g.text((bw / 2, y), line, font=P.font(H * 0.05), fill=P.rgba("ink", a), anchor="ma")
            y += H * 0.06
    elif kind == "quote_card":
        rise = int(H * 0.02 * (1 - ease_out(t / 0.35)))
        g.rectangle((0, rise, bw, bh), fill=P.rgba("paper", 0.95 * env))
        g.rectangle((0, rise, int(W * 0.012), bh), fill=P.rgba("accent", env))
        y = rise + H * 0.035
        size = H * 0.032
        lines = P.wrap(f"“{f.get('text', '')}”", size, W * 0.7)
        for line in lines:
            g.text((W * 0.06, y), line, font=P.font(size), fill=P.rgba("primary", env))
            y += size * 1.25
        if f.get("attribution"):
            g.text((W * 0.06, y + H * 0.004), f"— {f['attribution']}", font=P.font(H * 0.018, False), fill=P.rgba("primary", 0.75 * env))
    elif kind == "checklist":
        items = list(f.get("items") or [])[:5]
        g.rounded_rectangle((0, 0, bw - 1, bh - 1), int(H * 0.012), fill=P.rgba("primary", 0.86 * env))
        if f.get("title"):
            g.text((W * 0.05, H * 0.018), str(f["title"]), font=P.font(H * 0.024), fill=P.rgba("accent", env))
        step = max(0.35, (d - 1.0) / max(1, len(items)))
        size = H * 0.027
        for i, it in enumerate(items):
            a = ease_out((t - 0.3 - i * step) / 0.2) * env
            y = H * 0.06 + i * size * 1.8
            r = size * 0.42
            cx, cy = W * 0.065, y + size * 0.55
            g.ellipse((cx - r, cy - r, cx + r, cy + r), fill=P.rgba("accent", a))
            g.line((cx - r * 0.45, cy, cx - r * 0.1, cy + r * 0.38, cx + r * 0.5, cy - r * 0.4), fill=P.rgba("primary", a), width=max(2, int(r * 0.28)))
            g.text((W * 0.11, y), str(it)[:42], font=P.font(size, False), fill=P.rgba("ink", a))
    elif kind == "end_card":
        rise = int(bh * 0.4 * (1 - ease_out(t / 0.4)))
        g.rounded_rectangle((0, rise, bw - 1, bh - 1), int(H * 0.02), fill=P.rgba("accent", env))
        y = rise + bh * 0.16
        for line in P.wrap(f.get("text", "Follow for more"), H * 0.04, bw * 0.86):
            g.text((bw / 2, y), line, font=P.font(H * 0.04), fill=P.rgba("primary", env), anchor="ma")
            y += H * 0.048
        if f.get("handle"):
            g.text((bw / 2, bh * 0.8 + rise), str(f["handle"]), font=P.font(H * 0.024, False), fill=P.rgba("primary", env), anchor="mm")
    return img


def render_sequence(kind: str, f: dict, look: dict, W: int, H: int, d: float, out_dir: Path) -> tuple[int, int]:
    """Writes out_dir/0000.png... and returns the (x, y) where the sequence sits in the frame."""
    P = Painter(look, W, H)
    box = layout(kind, f, P)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = max(1, int(round(d * FPS)))
    for i in range(n):
        draw(kind, f, P, i / FPS, d, box).save(out_dir / f"{i:04d}.png", compress_level=1)
    return box[0], box[1]


def catalog() -> list[dict]:
    return [{"type": k, **v} for k, v in TYPES.items()]
