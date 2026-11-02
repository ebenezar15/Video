"""One-tap effects. Each builds ffmpeg filter pieces for a window [a, a+d] in output time.

Pieces a builder may return:
  zoom / dx / dy  expression terms added to the virtual camera (scale + crop, evaluated per frame)
  vf              filters on the picture (colour, blur, glitch) with timeline enable
  overlay         a Pillow image plus x/y expressions, overlaid during the window
  draw            static drawbox filters above the picture (flashes, bars). drawbox geometry is fixed at setup,
                  so anything that moves is an overlay instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import cards
from .looks import hex_rgb


def _solid(w: int, h: int, color: str):
    from PIL import Image
    return Image.new("RGBA", (w, h), (*hex_rgb(color), 255))


def win(a: float, d: float) -> str:
    return f"between(t,{a:.3f},{a + d:.3f})"


def _hex(c: str, alpha: float = 1.0) -> str:
    r, g, b = hex_rgb(c)
    return f"0x{r:02X}{g:02X}{b:02X}@{alpha}"


@dataclass
class Effect:
    name: str
    label: str
    category: str
    duration: float
    about: str
    build: Callable[..., dict]


E: dict[str, Effect] = {}


def effect(name, label, category, duration, about):
    def deco(fn):
        E[name] = Effect(name, label, category, duration, about, fn)
        return fn
    return deco


# --- camera --------------------------------------------------------------------------
@effect("zoom_punch", "Zoom punch", "camera", 1.2, "Instant 15% punch-in on the line")
def _(a, d, W, H, look, p):
    return {"zoom": f"{p.get('amount', 0.15)}*{win(a, d)}"}


@effect("zoom_in_slow", "Slow push-in", "camera", 3.0, "Gradual 20% push-in")
def _(a, d, W, H, look, p):
    return {"zoom": f"{p.get('amount', 0.2)}*{win(a, d)}*(t-{a:.3f})/{d:.3f}"}


@effect("zoom_out_slow", "Slow pull-out", "camera", 3.0, "Starts tight, eases out")
def _(a, d, W, H, look, p):
    return {"zoom": f"{p.get('amount', 0.2)}*{win(a, d)}*(1-(t-{a:.3f})/{d:.3f})"}


@effect("whip_zoom", "Whip zoom", "camera", 0.5, "Fast zoom pulse with motion blur")
def _(a, d, W, H, look, p):
    return {"zoom": f"0.35*{win(a, d)}*sin(PI*(t-{a:.3f})/{d:.3f})",
            "vf": [f"gblur=sigma=14:enable='{win(a, d)}'"]}


@effect("shake", "Camera shake", "camera", 0.6, "Handheld impact shake")
def _(a, d, W, H, look, p):
    amp = p.get("amount", 0.012) * W
    return {"zoom": f"0.06*{win(a, d)}", "dx": f"{amp:.1f}*sin(t*53)*{win(a, d)}", "dy": f"{amp:.1f}*cos(t*47)*{win(a, d)}"}


@effect("ken_burns", "Ken Burns drift", "camera", 4.0, "Slow zoom with a sideways drift")
def _(a, d, W, H, look, p):
    return {"zoom": f"0.1*{win(a, d)}*(t-{a:.3f})/{d:.3f}", "dx": f"{0.04 * W:.1f}*{win(a, d)}*(t-{a:.3f})/{d:.3f}"}


# --- colour & texture -----------------------------------------------------------------
def _vf(name, label, duration, about, filt):
    @effect(name, label, "color", duration, about)
    def _(a, d, W, H, look, p):
        return {"vf": [f"{f}{':' if '=' in f else '='}enable='{win(a, d)}'" for f in filt]}


_vf("black_white", "Black & white", 2.0, "Drop the colour for a beat", ["hue=s=0"])
_vf("sepia", "Sepia", 2.0, "Old-photo tone", ["colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"])
_vf("glitch", "RGB glitch", 0.4, "Channel-split digital glitch", ["rgbashift=rh=-14:bh=14:gv=6", "noise=alls=40:allf=t"])
_vf("vhs", "VHS", 2.0, "Tape noise and colour bleed", ["noise=alls=28:allf=t+u", "rgbashift=rh=6:bv=4", "eq=saturation=1.35:contrast=0.95"])
_vf("film_grain", "Film grain", 3.0, "Moving grain", ["noise=alls=22:allf=t+u"])
_vf("blur_focus", "Blur focus", 1.0, "Soft blur, good under a title card", ["gblur=sigma=18"])
_vf("vignette", "Vignette", 2.0, "Dark edges, centre focus", ["vignette=angle=PI/3.2"])
_vf("negative_flash", "Negative flash", 0.15, "One-frame invert hit", ["negate"])
_vf("warm_glow", "Warm glow", 2.0, "Golden-hour warmth", ["eq=brightness=0.05:saturation=1.25", "colorbalance=rs=0.08:gs=0.03:bs=-0.08"])
_vf("cool_tone", "Cool tone", 2.0, "Blue, calm, night feel", ["colorbalance=rs=-0.07:bs=0.12"])
_vf("saturate_pop", "Colour pop", 1.5, "Punchy saturation boost", ["eq=saturation=1.7:contrast=1.08"])
_vf("spotlight", "Spotlight", 2.0, "Heavy vignette spotlight", ["vignette=angle=PI/2.2"])


# --- flashes --------------------------------------------------------------------------
@effect("flash_white", "White flash", "flash", 0.14, "Bright cut flash")
def _(a, d, W, H, look, p):
    return {"draw": [f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.85:t=fill:enable='{win(a, d)}'"]}


@effect("flash_black", "Dip to black", "flash", 0.2, "Quick blackout beat")
def _(a, d, W, H, look, p):
    return {"draw": [f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.95:t=fill:enable='{win(a, d)}'"]}


# --- overlays -------------------------------------------------------------------------
@effect("sticker", "Sticker", "overlay", 2.0, "Die-cut sticker with your text")
def _(a, d, W, H, look, p):
    img = cards.sticker(p.get("text", "save this ✦"), look, W)
    return {"overlay": {"img": img, "x": f"W*0.55-w/2", "y": f"H*0.62-h/2"}}


@effect("glass_widget", "Glass widget", "overlay", 2.5, "Frosted stat widget")
def _(a, d, W, H, look, p):
    img = cards.glass_widget(p.get("title", "today"), p.get("text", "4 min edit"), look, W)
    return {"overlay": {"img": img, "x": "W*0.06", "y": f"H*0.14+20*sin((t-{a:.3f})*3)"}}


@effect("orbit", "Orbiting pictures", "overlay", 3.0, "Pictures orbit around the subject")
def _(a, d, W, H, look, p):
    photos = p.get("images") or [None, None, None]
    out = []
    for i, ph in enumerate(photos[:4]):
        ph_ = ph and __import__("pathlib").Path(ph)
        img = cards.orbit_dot(look, W, ph_ if ph_ and ph_.exists() else None)
        phase = 2 * 3.14159 * i / len(photos[:4])
        out.append({"img": img, "x": f"W/2+W*0.34*cos((t-{a:.3f})*1.8+{phase:.3f})-w/2",
                    "y": f"H*0.42+H*0.10*sin((t-{a:.3f})*1.8+{phase:.3f})-h/2"})
    return {"overlay": out}


@effect("light_leak", "Light leak", "overlay", 1.5, "Warm film light leak")
def _(a, d, W, H, look, p):
    return {"overlay": {"img": cards.light_leak(W, H), "x": "0", "y": "0"}}


@effect("progress_bar", "Progress bar", "overlay", 0, "Thin bar along the top for the whole video")
def _(a, d, W, H, look, p):
    total = max(p.get("total", 1), 0.1)
    return {"overlay": {"img": _solid(W, max(4, H // 220), look["colors"]["accent"]), "x": f"-W+W*t/{total:.3f}", "y": "0"}}


@effect("highlight_box", "Highlight box", "overlay", 1.5, "Outline box to point at something")
def _(a, d, W, H, look, p):
    x, y, w, h = p.get("box", [0.2, 0.3, 0.6, 0.25])
    return {"draw": [f"drawbox=x={x * W:.0f}:y={y * H:.0f}:w={w * W:.0f}:h={h * H:.0f}:color={_hex(look['colors']['accent'])}:t={max(4, W // 140)}:enable='{win(a, d)}'"]}


# --- transitions ----------------------------------------------------------------------
@effect("curtain", "Curtain", "transition", 0.7, "Two panels close and open")
def _(a, d, W, H, look, p):
    k = f"sin(PI*(t-{a:.3f})/{d:.3f})"
    panel = _solid(W // 2 + 2, H, look["colors"]["primary"])
    return {"overlay": [{"img": panel, "x": f"-w+w*{k}", "y": "0"}, {"img": panel, "x": f"W-w*{k}", "y": "0"}]}


@effect("wipe", "Colour wipe", "transition", 0.6, "Brand-colour panel sweeps across")
def _(a, d, W, H, look, p):
    return {"overlay": {"img": _solid(W, H, look["colors"]["accent"]), "x": f"-W+2*W*(t-{a:.3f})/{d:.3f}", "y": "0"}}


@effect("paper_tear", "Paper tear", "transition", 0.8, "Torn paper strip slides across")
def _(a, d, W, H, look, p):
    img = cards.paper_tear(W, H, look)
    return {"overlay": {"img": img, "x": f"-w+(W+w)*(t-{a:.3f})/{d:.3f}", "y": "0"}}


# --- framing --------------------------------------------------------------------------
@effect("letterbox", "Letterbox", "framing", 3.0, "Cinematic bars top and bottom")
def _(a, d, W, H, look, p):
    bar = int(H * p.get("amount", 0.09))
    return {"draw": [f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill:enable='{win(a, d)}'",
                     f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill:enable='{win(a, d)}'"]}


def catalog() -> list[dict]:
    return [{"name": e.name, "label": e.label, "category": e.category, "duration": e.duration, "about": e.about}
            for e in E.values()]
