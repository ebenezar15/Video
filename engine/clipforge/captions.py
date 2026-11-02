"""Burned-in captions and hook titles as ASS subtitles (rendered by libass inside ffmpeg)."""
from __future__ import annotations

import re

from .looks import font_full_name, hex_rgb
from .timeline import Timeline
from .transcript import Word, sentences


def ass_color(hex_color: str, alpha: int = 0) -> str:
    r, g, b = hex_rgb(hex_color)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def ass_time(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _case(text: str, mode: str) -> str:
    return text.upper() if mode == "upper" else text.lower() if mode == "lower" else text


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def groups(words: list[Word], tl: Timeline, per_line: int) -> list[list[tuple[Word, float, float]]]:
    by_id = {w.id: w for w in words}
    items = sorted(((by_id[i], *tl.word_out[i]) for i in tl.order if i in tl.word_out), key=lambda x: x[1])
    out: list[list] = []
    cur: list = []
    for w, s, e in items:
        if cur and (len(cur) >= per_line or s - cur[-1][2] > 0.5):
            out.append(cur)
            cur = []
        cur.append((w, s, e))
        if re.search(r"[.!?,;:…]$", w.text):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def build_ass(words: list[Word], tl: Timeline, edit: dict, look: dict, W: int, H: int) -> str:
    cap = {**look["caption"], **{k: v for k, v in edit.get("captions", {}).items() if v is not None}}
    col = look["colors"]
    size = round(H * cap["size"] * (0.85 if cap.get("words_per_line", 3) > 3 else 1))
    margin_v = round(H * (1 - float(cap.get("position", 0.80))))
    cap_font = font_full_name(look["caption_font_file"])
    title_font = font_full_name(look["title_font_file"])
    boxed = cap.get("box")
    text_col = col["primary"] if boxed else col["ink"]
    outline = round(cap["outline"] * H / 1920) if not boxed else round(H * 0.008)
    border_style = 3 if boxed else 1
    back = ass_color(col["paper"], 0x10) if boxed else ass_color("#000000", 0x60)
    out_col = ass_color(col["paper"]) if boxed else ass_color("#000000")
    hook_size = round(H * 0.052)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{cap_font},{size},{ass_color(text_col)},{ass_color(col['accent'])},{out_col},{back},0,0,0,0,100,100,0,0,"
        f"{border_style},{outline},{round(cap['shadow'] * H / 1920)},2,{round(W * 0.08)},{round(W * 0.08)},{margin_v},1",
        f"Style: Hook,{title_font},{hook_size},{ass_color(col['primary'])},{ass_color(col['accent'])},{ass_color(col['ink'])},"
        f"{ass_color(col['accent'], 0)},0,0,0,0,100,100,0,0,3,{round(H * 0.012)},0,8,{round(W * 0.08)},{round(W * 0.08)},{round(H * 0.11)},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    hi = ass_color(col["primary"] if boxed and look["name"] == "paper" else col["accent"])
    anim = cap.get("animation") or ("pop" if cap.get("pop") else "none")
    active_tag = {"pop": r"\fscx112\fscy112", "bounce": r"\fscx108\fscy124\t(0,110,\fscx100\fscy100)", "rise": "", "none": ""}[anim]
    sent_starts = {s[0].id for s in sentences(words)} if words else set()

    def emphasised(w: Word) -> bool:
        raw = w.text.strip(".,!?;:\"'()")
        return cap.get("emphasis", "auto") == "auto" and (any(ch.isdigit() for ch in raw) or
                                                          (raw[:1].isupper() and len(raw) > 2 and w.id not in sent_starts and raw != "I'm"))

    all_groups = groups(words, tl, int(cap.get("words_per_line", 3)))
    for gi, g in enumerate(all_groups):
        texts = [_esc(_case(w.text, cap["case"])) for w, _, _ in g]
        next_start = all_groups[gi + 1][0][1] if gi + 1 < len(all_groups) else float("inf")
        for i, (w, s, e) in enumerate(g):
            end = g[i + 1][1] if i + 1 < len(g) else min(e + 0.12, next_start)
            start = g[0][1] if i == 0 else s
            parts = []
            for j, t in enumerate(texts):
                if j == i and cap.get("karaoke", True):
                    parts.append(f"{{\\c{hi}{active_tag}}}{t}{{\\r}}")
                elif emphasised(g[j][0]):
                    parts.append(f"{{\\c{hi}}}{t}{{\\r}}")
                else:
                    parts.append(t)
            intro = r"{\fad(90,0)\fscy70\t(0,140,\fscy100)}" if anim == "rise" and i == 0 else ""
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{intro}{' '.join(parts)}")
    title = (edit.get("hook") or {}).get("title")
    if title:
        lines.append(f"Dialogue: 1,{ass_time(0)},{ass_time(min(3.0, tl.duration))},Hook,,0,0,0,,"
                     f"{{\\fad(120,200)}}{_esc(title)}")
    return "\n".join(lines) + "\n"


def srt(words: list[Word], tl: Timeline, per_line: int = 3) -> str:
    def ts(t: float) -> str:
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    out = []
    for i, g in enumerate(groups(words, tl, per_line), 1):
        out.append(f"{i}\n{ts(g[0][1])} --> {ts(g[-1][2])}\n{' '.join(w.text for w, _, _ in g)}\n")
    return "\n".join(out)


# --- Pillow caption track (for ffmpeg builds without libass, e.g. Homebrew's) ------------------------------
def caption_states(words: list[Word], tl: Timeline, edit: dict, look: dict) -> list[tuple[float, float, dict]]:
    """Every change in what the caption layer shows: (start, end, state)."""
    cap = {**look["caption"], **{k: v for k, v in edit.get("captions", {}).items() if v is not None}}
    sent_starts = {s[0].id for s in sentences(words)} if words else set()

    def emphasised(w: Word) -> bool:
        raw = w.text.strip(".,!?;:\"'()")
        return cap.get("emphasis", "auto") == "auto" and (any(ch.isdigit() for ch in raw) or
                                                          (raw[:1].isupper() and len(raw) > 2 and w.id not in sent_starts and raw != "I'm"))

    events: list[tuple[float, float, dict]] = []
    all_groups = groups(words, tl, int(cap.get("words_per_line", 3)))
    for gi, g in enumerate(all_groups):
        next_start = all_groups[gi + 1][0][1] if gi + 1 < len(all_groups) else float("inf")
        toks = [(_case(w.text, cap["case"]), emphasised(w)) for w, _, _ in g]
        for i, (w, s, e) in enumerate(g):
            end = g[i + 1][1] if i + 1 < len(g) else min(e + 0.12, next_start)
            start = g[0][1] if i == 0 else s
            events.append((start, end, {"words": toks, "active": i if cap.get("karaoke", True) else -1}))
    title = (edit.get("hook") or {}).get("title")
    hook_end = min(3.0, tl.duration) if title else 0.0
    cuts = sorted({0.0, tl.duration, hook_end, *[min(t, tl.duration) for a, b, _ in events for t in (a, b)]})
    out = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 1e-3:
            continue
        mid = (a + b) / 2
        cur = next((st for s, e, st in events if s <= mid < e), None)
        state = {"caption": cur, "hook": title if mid < hook_end else None}
        out.append((a, b, state))
    return out


def draw_state(state: dict, look: dict, edit: dict, W: int, H: int):
    from PIL import Image, ImageDraw, ImageFont

    from .looks import hex_rgb
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cap = {**look["caption"], **{k: v for k, v in edit.get("captions", {}).items() if v is not None}}
    col = {k: hex_rgb(v) for k, v in look["colors"].items()}
    d = ImageDraw.Draw(img)
    if state.get("hook"):
        f = ImageFont.truetype(str(look["title_font_file"]), max(10, round(H * 0.052)))
        text = state["hook"]
        tw = d.textlength(text, font=f)
        pad = H * 0.014
        y = H * 0.11
        x = (W - tw) / 2
        asc, desc = f.getmetrics()
        d.rounded_rectangle((x - pad * 1.4, y - pad, x + tw + pad * 1.4, y + asc + desc + pad), radius=pad, fill=(*col["ink"], 255))
        d.text((x, y), text, font=f, fill=(*col["primary"], 255))
    c = state.get("caption")
    if c:
        boxed = cap.get("box")
        size = round(H * cap["size"] * (0.85 if cap.get("words_per_line", 3) > 3 else 1))
        base = ImageFont.truetype(str(look["caption_font_file"]), max(10, size))
        big = ImageFont.truetype(str(look["caption_font_file"]), max(10, round(size * 1.12)))
        anim = cap.get("animation") or ("pop" if cap.get("pop") else "none")
        hi = col["primary"] if boxed and look["name"] == "paper" else col["accent"]
        text_col = col["primary"] if boxed else col["ink"]
        stroke = 0 if boxed else max(2, round(cap["outline"] * H / 1920)) if cap["outline"] else 0
        space = d.textlength(" ", font=base)
        items = []
        for i, (t, emph) in enumerate(c["words"]):
            active = i == c["active"]
            f = big if active and anim in ("pop", "bounce") else base
            fill = hi if active or emph else text_col
            items.append((t, f, fill, d.textlength(t, font=f)))
        # wrap into lines within 84% of the width
        lines, cur, cur_w = [], [], 0.0
        for it in items:
            add = it[3] + (space if cur else 0)
            if cur and cur_w + add > W * 0.84:
                lines.append((cur, cur_w))
                cur, cur_w = [], 0.0
                add = it[3]
            cur.append(it)
            cur_w += add
        if cur:
            lines.append((cur, cur_w))
        asc, desc = big.getmetrics()
        line_h = (asc + desc) * 1.05
        bottom = H * float(cap.get("position", 0.80))
        y = bottom - line_h * len(lines)
        for line, lw in lines:
            x = (W - lw) / 2
            if boxed:
                pad = H * 0.008
                d.rounded_rectangle((x - pad * 2, y - pad, x + lw + pad * 2, y + line_h), radius=pad * 2, fill=(*col["paper"], 240))
            for t, f, fill, tw in line:
                yy = y + (asc - f.getmetrics()[0])
                if cap.get("shadow") and not boxed:
                    off = max(1, round(cap["shadow"] * H / 1920))
                    d.text((x + off, yy + off), t, font=f, fill=(0, 0, 0, 150))
                d.text((x, yy), t, font=f, fill=(*fill, 255), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
                x += tw + space
            y += line_h
    return img


def write_caption_track(words: list[Word], tl: Timeline, edit: dict, look: dict, W: int, H: int, out_dir) -> str | None:
    """Renders caption states to PNGs and an ffconcat list. Returns the list's file name, or None if empty."""
    from pathlib import Path
    out_dir = Path(out_dir)
    states = caption_states(words, tl, edit, look)
    if not states:
        return None
    files: dict[str, str] = {}
    lines = ["ffconcat version 1.0"]
    for a, b, st in states:
        key = repr(st)
        if key not in files:
            name = f"cap{len(files):04d}.png"
            draw_state(st, look, edit, W, H).save(out_dir / name, compress_level=1)
            files[key] = name
        lines += [f"file '{files[key]}'", f"duration {b - a:.3f}"]
    lines.append(f"file '{files[repr(states[-1][2])]}'")  # the concat demuxer needs the last entry repeated
    (out_dir / "captions.ffconcat").write_text("\n".join(lines) + "\n")
    return "captions.ffconcat"
