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
