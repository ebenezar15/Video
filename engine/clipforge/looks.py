"""The five looks, font resolution, and brand merging."""
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

# Each look: caption typography, hook title, colour grade, pacing, card style for pop-ups and posts.
LOOKS: dict[str, dict] = {
    "editorial": {
        "label": "Editorial", "about": "Serif titles, quiet captions, film-like grade, thin letterbox.",
        "title_font": ["Caladea:bold", "Liberation Serif:bold", "Georgia:bold", "DejaVu Serif:bold"],
        "caption_font": ["Caladea", "Liberation Serif", "Georgia", "DejaVu Serif"],
        "caption": {"size": 0.040, "case": "sentence", "outline": 0, "shadow": 3, "box": False, "pop": False},
        "grade": "eq=contrast=1.05:saturation=0.82:gamma=1.03,colorbalance=rs=0.04:bs=-0.04",
        "letterbox": 0.05, "auto_zoom": False, "card": {"bg": "paper", "fg": "primary", "radius": 6},
    },
    "bold": {
        "label": "Bold", "about": "Heavy uppercase captions, punchy contrast, auto zoom on key lines.",
        "title_font": ["Inter Display:black", "Inter:extrabold", "Liberation Sans:bold", "Arial Black", "DejaVu Sans:bold"],
        "caption_font": ["Inter Display:black", "Inter:extrabold", "Liberation Sans:bold", "Arial Black", "DejaVu Sans:bold"],
        "caption": {"size": 0.062, "case": "upper", "outline": 7, "shadow": 0, "box": False, "pop": True},
        "grade": "eq=contrast=1.14:saturation=1.25",
        "letterbox": 0, "auto_zoom": True, "card": {"bg": "accent", "fg": "primary", "radius": 18},
    },
    "creator": {
        "label": "Creator", "about": "Word-by-word karaoke captions with a highlight pop, bright and clean.",
        "title_font": ["Inter:extrabold", "Liberation Sans:bold", "Helvetica:bold", "DejaVu Sans:bold"],
        "caption_font": ["Inter:bold", "Liberation Sans:bold", "Helvetica:bold", "DejaVu Sans:bold"],
        "caption": {"size": 0.052, "case": "upper", "outline": 5, "shadow": 2, "box": False, "pop": True},
        "grade": "eq=contrast=1.06:saturation=1.12",
        "letterbox": 0, "auto_zoom": True, "card": {"bg": "ink", "fg": "primary", "radius": 28},
    },
    "soft": {
        "label": "Soft", "about": "Lowercase captions on rounded paper boxes, pastel low-contrast grade.",
        "title_font": ["Inter:semibold", "Carlito:bold", "Liberation Sans:bold", "DejaVu Sans:bold"],
        "caption_font": ["Inter:medium", "Carlito", "Liberation Sans", "DejaVu Sans"],
        "caption": {"size": 0.042, "case": "lower", "outline": 0, "shadow": 0, "box": True, "pop": False},
        "grade": "eq=contrast=0.92:saturation=0.86:brightness=0.03,colorbalance=rh=0.03:bh=0.04",
        "letterbox": 0, "auto_zoom": False, "card": {"bg": "paper", "fg": "primary", "radius": 36},
    },
    "paper": {
        "label": "Paper", "about": "Typewriter captions on paper strips, warm grain, scrapbook cards.",
        "title_font": ["JetBrains Mono:bold", "Courier 10 Pitch:bold", "DejaVu Sans Mono:bold", "Courier New:bold"],
        "caption_font": ["JetBrains Mono:bold", "Courier 10 Pitch:bold", "DejaVu Sans Mono:bold", "Courier New:bold"],
        "caption": {"size": 0.040, "case": "sentence", "outline": 0, "shadow": 0, "box": True, "pop": False},
        "grade": "eq=saturation=0.72:contrast=1.02,colorbalance=rs=0.06:gs=0.02:bs=-0.06,noise=alls=10:allf=t",
        "letterbox": 0, "auto_zoom": False, "card": {"bg": "paper", "fg": "primary", "radius": 0},
    },
}

FONT_DIRS = ["/System/Library/Fonts", "/Library/Fonts", "~/Library/Fonts", "/usr/share/fonts", "~/.fonts",
             "~/.local/share/fonts", "C:/Windows/Fonts"]


@lru_cache(maxsize=128)
def resolve_font(spec: str) -> Path | None:
    """'Family:weight' -> font file. Uses fontconfig when present, else scans common font folders."""
    if os.path.isfile(os.path.expanduser(spec)):
        return Path(os.path.expanduser(spec))
    family, _, weight = spec.partition(":")
    if shutil.which("fc-match"):
        r = subprocess.run(["fc-match", "-f", "%{family}|%{file}", spec], capture_output=True, text=True)
        fam, _, file = r.stdout.partition("|")
        if file and family.lower() in fam.lower():
            return Path(file)
        return None
    want = (family + weight).replace(" ", "").lower()
    for d in FONT_DIRS:
        root = Path(os.path.expanduser(d))
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if f.suffix.lower() in (".ttf", ".otf", ".ttc") and want in f.stem.replace("-", "").replace(" ", "").lower():
                return f
    return None


def first_font(specs: list[str]) -> Path:
    for s in specs:
        if s and (p := resolve_font(s)):
            return p
    fallback = resolve_font("DejaVu Sans:bold") or resolve_font("Arial:bold")
    if not fallback:
        raise RuntimeError("No usable font found. Set brand fonts to a .ttf/.otf file path.")
    return fallback


def font_full_name(path: Path) -> str:
    from PIL import ImageFont
    fam, style = ImageFont.truetype(str(path), 20).getname()
    return fam if style in ("Regular", "Book", "Roman") else f"{fam} {style}"


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def resolved(look_name: str, brand: dict) -> dict:
    """A look with brand colours and fonts applied, fonts resolved to files."""
    if look_name not in LOOKS:
        raise ValueError(f"Unknown look '{look_name}'. Choose from {list(LOOKS)}")
    look = {**LOOKS[look_name], "name": look_name}
    pal = brand.get("palette", {})
    look["colors"] = {k: pal.get(k, v) for k, v in
                      {"primary": "#1F1A17", "accent": "#FFC23D", "ink": "#FFFFFF", "paper": "#F3EDE4"}.items()}
    fonts = brand.get("fonts") or {}
    look["title_font_file"] = first_font([fonts.get("title")] + look["title_font"])
    look["caption_font_file"] = first_font([fonts.get("caption")] + look["caption_font"])
    return look
