"""One reel becomes a whole post: cover, carousel, story frames and the caption, all in the same look."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .looks import hex_rgb, resolved
from .project import Project, load_brand
from .render import timeline_for
from .transcript import sentences


def _frame(video: Path, t: float, out: Path) -> Image.Image:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(t, 0):.2f}", "-i", str(video), "-frames:v", "1", str(out)],
                   check=True)
    return Image.open(out).convert("RGB")


def _font(path: Path, size: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), max(10, int(size)))


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def _text_block(img: Image.Image, text: str, font_path: Path, color, box: tuple[int, int, int, int], start: float,
                align: str = "left", min_size: float = 28) -> None:
    d = ImageDraw.Draw(img)
    x, y, w, h = box
    size = start
    while True:
        f = _font(font_path, size)
        lines = _wrap(d, text, f, w)
        lh = int(size * 1.15)
        if lh * len(lines) <= h or size <= min_size:
            break
        size *= 0.92
    ty = y + (h - lh * len(lines)) // 2
    for ln in lines:
        lx = x + (w - d.textlength(ln, font=f)) // 2 if align == "center" else x
        d.text((lx, ty), ln, font=f, fill=color)
        ty += lh


def default_copy(p: Project) -> dict:
    """Without Claude: cover = hook title or first line; slides = the strongest kept sentences."""
    tl = timeline_for(p)
    kept = [w for w in p.words if w.id in tl.word_out]
    sents = [" ".join(w.text for w in s) for s in sentences(kept)]
    sents = [x for x in sents if len(x.split()) >= 4] or sents  # no one-word fragments on slides
    def score(s: str) -> float:  # prefer complete thoughts of slide length, and lines with numbers
        n = len(s.split())
        return (10 if 5 <= n <= 22 else 0) + (5 if re.search(r"\d", s) else 0) + n / 10

    best = sorted(range(len(sents)), key=lambda i: -score(sents[i]))[:6]
    picks = [sents[i] for i in sorted(best)]
    title = (p.edit.get("hook") or {}).get("title") or (sents[0] if sents else p.meta["name"])
    brand = load_brand()
    tags = brand.get("hashtags") or []
    body = "\n".join(f"→ {s}" for s in picks[:3])
    caption = f"{title}\n\n{body}\n\n{brand.get('cta') or ''}".strip()
    return {"title": title, "slides": picks, "caption": caption, "hashtags": tags}


def post_kit(p: Project, slides_max: int = 8) -> dict:
    brand = load_brand()
    look = resolved(p.edit.get("look", "creator"), brand)
    c = {k: hex_rgb(v) for k, v in look["colors"].items()}
    copy = {**default_copy(p), **{k: v for k, v in (p.edit.get("post") or {}).items() if v}}
    out_dir = p.dir / "post"
    out_dir.mkdir(exist_ok=True)
    for f in out_dir.glob("*"):
        f.unlink()
    # clean frames (no burned-in captions) from the source, at the moments the edit actually uses
    video = p.source
    tl = timeline_for(p)
    dur = tl.duration
    has_video = bool(p.meta.get("width"))

    def src_time(out_t: float) -> float:
        for sg in tl.segments:
            if sg.out_start <= out_t < sg.out_start + sg.dur:
                return sg.src_start + out_t - sg.out_start
        return tl.segments[-1].src_end - 0.1 if tl.segments else 0.0
    tf, cf = look["title_font_file"], look["caption_font_file"]
    handle = brand.get("handle") or ""
    files: dict[str, list[str] | str] = {}

    def bg_frame(t: float, size: tuple[int, int], dark: float = 0.45) -> Image.Image:
        fr = _frame(video, src_time(t), out_dir / "_f.png") if has_video else Image.new("RGB", size, c["primary"])
        fr = ImageOps.fit(fr, size)
        return ImageEnhance.Brightness(fr).enhance(1 - dark)

    # cover 1080x1920
    cover = bg_frame(min(0.6, dur / 3), (1080, 1920), 0.35)
    shade = Image.new("L", (1, 256))
    for i in range(256):
        shade.putpixel((0, i), int(i * 0.8))
    cover.paste(Image.new("RGB", cover.size, (0, 0, 0)), (0, 0), shade.resize(cover.size))
    _text_block(cover, copy["title"], tf, c["ink"], (90, 1080, 900, 560), 130)
    if handle:
        ImageDraw.Draw(cover).text((90, 1760), handle, font=_font(cf, 44), fill=c["accent"])
    cover.save(out_dir / "cover.jpg", quality=92)
    files["cover"] = "post/cover.jpg"

    # carousel 1080x1350: hook slide, one idea per slide, CTA slide
    slides = copy["slides"][: max(1, slides_max - 2)]
    car = []
    s1 = bg_frame(min(1.0, dur / 4), (1080, 1350), 0.5)
    _text_block(s1, copy["title"], tf, c["ink"], (80, 520, 920, 520), 120)
    ImageDraw.Draw(s1).text((80, 1230), "swipe →", font=_font(cf, 40), fill=c["accent"])
    car.append(s1)
    n = len(slides)
    for i, line in enumerate(slides):
        sl = Image.new("RGB", (1080, 1350), c["paper"])
        thumb = ImageOps.fit(_frame(video, src_time(dur * (i + 1) / (n + 1)), out_dir / "_f.png") if has_video
                             else Image.new("RGB", (10, 10), c["accent"]), (920, 520))
        sl.paste(thumb, (80, 80))
        d = ImageDraw.Draw(sl)
        d.text((80, 650), f"{i + 1:02d}", font=_font(tf, 64), fill=c["accent"])
        _text_block(sl, line, cf, c["primary"], (80, 740, 920, 480), 66)
        d.text((80, 1260), handle, font=_font(cf, 34), fill=c["primary"])
        d.text((1000, 1260), f"{i + 2}/{n + 2}", font=_font(cf, 34), fill=c["primary"], anchor="ra")
        car.append(sl)
    cta = Image.new("RGB", (1080, 1350), c["accent"])
    _text_block(cta, brand.get("cta") or "Follow for more", tf, c["primary"], (80, 400, 920, 420), 110, "center")
    if handle:
        ImageDraw.Draw(cta).text((540, 900), handle, font=_font(cf, 56), fill=c["primary"], anchor="ma")
    car.append(cta)
    files["carousel"] = []
    for i, im in enumerate(car, 1):
        im.save(out_dir / f"carousel-{i:02d}.jpg", quality=92)
        files["carousel"].append(f"post/carousel-{i:02d}.jpg")
    car[0].save(out_dir / "carousel.pdf", save_all=True, append_images=car[1:])
    files["carousel_pdf"] = "post/carousel.pdf"

    # three story frames 1080x1920
    files["stories"] = []
    for i, line in enumerate((slides or [copy["title"]])[:3]):
        st = bg_frame(dur * (i + 1) / 4, (1080, 1920), 0.2).filter(ImageFilter.GaussianBlur(2))
        card_ = Image.new("RGB", (900, 600), c["paper"])
        _text_block(card_, line, cf, c["primary"], (60, 60, 780, 480), 72)
        st.paste(card_, (90, 1120))
        st.save(out_dir / f"story-{i + 1}.jpg", quality=90)
        files["stories"].append(f"post/story-{i + 1}.jpg")

    caption = copy["caption"] + ("\n\n" + " ".join("#" + h.lstrip("#") for h in copy["hashtags"]) if copy["hashtags"] else "")
    (out_dir / "caption.txt").write_text(caption, encoding="utf-8")
    files["caption"] = "post/caption.txt"
    (out_dir / "_f.png").unlink(missing_ok=True)
    p.meta["post_kit"] = files
    p.save()
    return {"files": files, "copy": copy}
