"""Compile a project (transcript + edit + look + brand) into one ffmpeg run."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from . import audio_gen, cards, graphics, popups
from . import captions as cap_mod
from .effects import E
from .looks import hex_rgb, resolved
from .project import Project, load_brand
from .recipes import ASPECTS
from .timeline import Segment, Timeline, build
from .transcript import sentences

QUALITY = {
    "tiny": (270, 480, "ultrafast", 30),
    "preview": (540, 960, "veryfast", 25),
    "final": (1080, 1920, "medium", 19),
}
FPS = 30
POPUP_SECONDS = 1.8


class RenderError(RuntimeError):
    pass


def timeline_for(p: Project) -> Timeline:
    if p.words:
        return build(p.words, p.edit, p.meta.get("duration"))
    d = float(p.meta.get("duration") or 0)
    return Timeline(segments=[Segment(0.0, d, 0.0)])


def effect_instances(p: Project, tl: Timeline, look: dict) -> list[dict]:
    """User effects anchored to words, plus the look's automatic zooms."""
    out = []
    for fx in p.edit.get("effects", []):
        a = fx.get("at")
        if a is None:
            a = tl.out_time(fx.get("word_id", -1))
        if a is None or fx["name"] not in E:
            continue
        d = fx.get("duration") or E[fx["name"]].duration or tl.duration
        out.append({"name": fx["name"], "a": float(a), "d": float(d), "params": fx.get("params") or {}})
    if look.get("auto_zoom") and p.words:
        user_zoom = {round(x["a"], 1) for x in out if E[x["name"]].category == "camera"}
        kept = [w for w in p.words if w.id in tl.word_out]
        for i, s in enumerate(sentences(kept)):
            if i % 2 == 1:
                a, end = tl.word_out[s[0].id][0], tl.word_out[s[-1].id][1]
                if round(a, 1) not in user_zoom:
                    out.append({"name": "zoom_punch", "a": a, "d": min(2.5, max(0.6, end - a)), "params": {"amount": 0.1}})
    for x in out:
        if x["name"] == "progress_bar":
            x["params"]["total"] = tl.duration
    return out


def render(p: Project, quality: str = "preview", progress: Callable[[float], None] | None = None,
           size: tuple[int, int] | None = None) -> Path:
    if quality not in QUALITY:
        raise ValueError(f"quality must be one of {list(QUALITY)}")
    _, _, preset, crf = QUALITY[quality]
    aw, ah = ASPECTS.get(p.edit.get("aspect", "9:16"), ASPECTS["9:16"])
    k = {"tiny": 0.25, "preview": 0.5, "final": 1.0}[quality]
    W, H = size or (int(aw * k) // 2 * 2, int(ah * k) // 2 * 2)
    brand = load_brand()
    look = resolved(p.edit.get("look", "creator"), brand)
    tl = timeline_for(p)
    if not tl.segments or tl.duration <= 0.05:
        raise RenderError("Nothing left to render: every word is cut.")
    total = round(tl.duration, 3)
    shot = p.meta.get("shot_type", "on_camera")
    work = p.dir / "renders" / f"work-{quality}"
    if work.exists():
        shutil.rmtree(work)
    (work / "fonts").mkdir(parents=True)
    for f in {look["title_font_file"], look["caption_font_file"]}:
        shutil.copyfile(f, work / "fonts" / Path(f).name)  # contents only: copy2 fails on protected macOS system fonts

    args: list[str] = []
    fc: list[str] = []
    n_in = 0

    def add_input(*a: str) -> int:
        nonlocal n_in
        args.extend(a)
        n_in += 1
        return n_in - 1

    src = add_input("-i", str(p.source))
    segs = tl.segments
    N = len(segs)

    # audio: trims of the source, in edit order
    if p.meta.get("has_audio", True):
        fc.append(f"[{src}:a]asplit={N}" + "".join(f"[as{i}]" for i in range(N)) if N > 1 else f"[{src}:a]anull[as0]")
        for i, s in enumerate(segs):
            fade = min(0.015, s.dur / 4)
            fc.append(f"[as{i}]atrim=start={s.src_start}:end={s.src_end},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d={fade:.3f},afade=t=out:st={max(s.dur - fade, 0):.3f}:d={fade:.3f}[at{i}]")
        fc.append("".join(f"[at{i}]" for i in range(N)) + f"concat=n={N}:v=0:a=1[acat]")
    else:
        sil = add_input("-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=48000:cl=stereo")
        fc.append(f"[{sil}:a]anull[acat]")

    # picture: depends on how it was shot
    broll = [b for b in p.edit.get("broll", []) if Path(b).exists()]
    if shot == "faceless" or (shot in ("voiceover_clips", "clips_text") and not broll and not p.meta.get("width")):
        c0, c1 = look["colors"]["primary"], look["colors"]["accent"]
        g = add_input("-f", "lavfi", "-t", str(total), "-i",
                      f"gradients=s={W}x{H}:c0=0x{c0.lstrip('#')}:c1=0x{c0.lstrip('#')}:c2=0x{c1.lstrip('#')}:n=3:speed=0.008:r={FPS}")
        fc.append(f"[{g}:v]setsar=1,format=yuv420p[vbase]")
    elif shot in ("voiceover_clips", "clips_text") and broll:
        kept = [w for w in p.words if w.id in tl.word_out]
        spans = [(tl.word_out[s[0].id][0], tl.word_out[s[-1].id][1]) for s in sentences(kept)] or [(0.0, total)]
        cuts = [0.0] + [b for _, b in spans[:-1]] + [total]
        for k in range(len(cuts) - 1):
            d = cuts[k + 1] - cuts[k]
            bi = add_input("-stream_loop", "-1", "-i", broll[k % len(broll)])
            fc.append(f"[{bi}:v]trim=duration={d:.3f},setpts=PTS-STARTPTS,fps={FPS},"
                      f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[b{k}]")
        fc.append("".join(f"[b{k}]" for k in range(len(cuts) - 1)) + f"concat=n={len(cuts) - 1}:v=1:a=0,format=yuv420p[vbase]")
    else:
        fc.append(f"[{src}:v]split={N}" + "".join(f"[vs{i}]" for i in range(N)) if N > 1 else f"[{src}:v]null[vs0]")
        for i, s in enumerate(segs):
            fc.append(f"[vs{i}]trim=start={s.src_start}:end={s.src_end},setpts=PTS-STARTPTS,fps={FPS}[vt{i}]")
        fc.append("".join(f"[vt{i}]" for i in range(N)) + f"concat=n={N}:v=1:a=0[vcat]")
        if p.edit.get("fit") == "blur":
            fc.append(f"[vcat]split[bgs][fgs];[bgs]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=40[bg];"
                      f"[fgs]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[vbase]")
        else:
            fc.append(f"[vcat]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p[vbase]")

    # effects -> pieces
    fx = effect_instances(p, tl, look)
    zoom, dx, dy, vf, draws, overlays = [], [], [], [], [], []
    for x in fx:
        piece = E[x["name"]].build(x["a"], x["d"], W, H, look, x["params"])
        zoom += [piece["zoom"]] if "zoom" in piece else []
        dx += [piece["dx"]] if "dx" in piece else []
        dy += [piece["dy"]] if "dy" in piece else []
        vf += piece.get("vf", [])
        draws += piece.get("draw", [])
        ov = piece.get("overlay")
        for o in ([ov] if isinstance(ov, dict) else ov or []):
            overlays.append({**o, "a": x["a"], "d": x["d"]})

    if zoom or dx or dy:
        Z = "1+" + "+".join(zoom) if zoom else "1"
        X = "+".join(dx) or "0"
        Y = "+".join(dy) or "0"
        fc.append(f"[vbase]scale=w='trunc({W}*({Z})/2)*2':h='trunc({H}*({Z})/2)*2':eval=frame,"
                  f"crop={W}:{H}:x='clip((iw-{W})/2+({X}),0,iw-{W})':y='clip((ih-{H})/2+({Y}),0,ih-{H})'[vcam]")
    else:
        fc.append("[vbase]null[vcam]")
    cur = "vcam"

    # B-roll cutaways (before the grade, so they take the same look)
    cutaways = []
    for i, cw in enumerate(p.edit.get("cutaways", [])):
        a = tl.out_time(cw["word_id"])
        f = Path(cw["path"])
        if a is None or not f.exists():
            continue
        d = min(float(cw.get("duration", 2.0)), max(0.3, total - a))
        is_img = f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        bi = add_input("-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", str(f)) if is_img else \
            add_input("-stream_loop", "-1", "-t", f"{d:.3f}", "-i", str(f))
        pip = cw.get("mode") == "pip"
        bw, bh = (int(W * 0.46) // 2 * 2, int(H * 0.3) // 2 * 2) if pip else (W, H)
        zk = f"(1+0.08*clip(if(isnan(t),0,(t-{a:.3f})/{d:.3f}),0,1))"  # t is NaN while the filter configures
        kb = f",scale=w='trunc({bw}*{zk}/2)*2+2':h='trunc({bh}*{zk}/2)*2+2':eval=frame,crop={bw}:{bh}" if is_img else ""
        fc.append(f"[{bi}:v]trim=duration={d:.3f},setpts=PTS-STARTPTS+{a:.3f}/TB,fps={FPS},"
                  f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh}{kb},setsar=1,format=yuva420p[cw{i}]")
        x, y = (f"{W - bw - int(W * 0.05)}", f"{int(H * 0.12)}") if pip else ("0", "0")
        fc.append(f"[{cur}][cw{i}]overlay=x={x}:y={y}:eof_action=pass:enable='between(t,{a:.3f},{a + d:.3f})'[cwo{i}]")
        cur = f"cwo{i}"
        cutaways.append({**cw, "a": a, "d": d})

    chain = [look["grade"], *vf]
    if look.get("letterbox"):
        bar = int(H * look["letterbox"])
        chain.append(f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill")
    fc.append(f"[{cur}]" + ",".join(chain) + "[vfx]")
    cur = "vfx"

    # smart pop-ups, placed away from faces
    # graphics that occupy the upper frame take priority over pop-ups at the same moment
    busy = []
    for g in p.edit.get("graphics", []):
        if g["type"] in ("counter", "bar_chart", "quote_card", "checklist", "chapter_card") and tl.out_time(g["word_id"]) is not None:
            ga = tl.out_time(g["word_id"])
            busy.append((ga - POPUP_SECONDS, ga + float(g.get("duration") or graphics.TYPES[g["type"]]["duration"])))
    pop_list = [x for x in p.edit.get("popups", []) if x.get("enabled", True) and tl.out_time(x["word_id"]) is not None
                and not any(b0 < tl.out_time(x["word_id"]) < b1 for b0, b1 in busy)]
    face_cache = {}
    if pop_list and shot == "on_camera" and p.meta.get("width"):
        src_t = {}
        for x in pop_list:
            w = next(w for w in p.words if w.id == x["word_id"])
            src_t[x["id"]] = round(w.start, 2)
        face_cache = popups.faces_at(p.source, sorted(set(src_t.values())), p.dir / "analysis" / "faces.json")
    for x in pop_list:
        a = tl.out_time(x["word_id"])
        if x["kind"] == "image" and x.get("image") and Path(x["image"]).exists():
            img = cards.image_card(Path(x["image"]), look, W, x.get("text", ""))
        else:
            img = cards.card(x["text"], look, W, "number" if x["kind"] == "number" else "keyword", x.get("sub", ""))
        boxes = []
        if face_cache:
            w = next(w for w in p.words if w.id == x["word_id"])
            boxes = face_cache.get(f"{round(w.start, 2):.2f}", [])
        px, py = popups.place(boxes, p.meta["width"], p.meta["height"], W, H, img.width, img.height) if face_cache else \
            popups.place([], W, H, W, H, img.width, img.height)
        overlays.append({"img": img, "x": str(px), "y": f"{py}+{H * 0.02:.0f}*(1-min(1,(t-{a:.3f})/0.15))",
                         "a": a, "d": POPUP_SECONDS})

    for k, o in enumerate(overlays):
        png = cards.save(o["img"], work / f"ov{k}.png")
        oi = add_input("-loop", "1", "-framerate", str(FPS), "-t", str(total), "-i", png.name)
        fc.append(f"[{cur}][{oi}:v]overlay=x='{o['x']}':y='{o['y']}':eval=frame:"
                  f"enable='between(t,{o['a']:.3f},{o['a'] + o['d']:.3f})'[ov{k}]")
        cur = f"ov{k}"

    # captions + hook title on top of everything, so zooms never move them
    edit = dict(p.edit)
    if shot in ("faceless", "clips_text"):
        edit["captions"] = {**edit.get("captions", {}), "position": 0.55, "words_per_line": 2}
    ass = work / "captions.ass"
    if p.words:
        ass.write_text(cap_mod.build_ass(p.words, tl, edit, look, W, H), encoding="utf-8")
    elif edit.get("hook", {}).get("title"):
        ass.write_text(cap_mod.build_ass([], tl, edit, look, W, H), encoding="utf-8")
    placed_graphics = []
    for k, g in enumerate(p.edit.get("graphics", [])):
        d = float(g.get("duration") or graphics.TYPES[g["type"]]["duration"])
        a = max(0.0, total - d) if g["type"] == "end_card" else tl.out_time(g["word_id"])
        if a is None:
            continue
        d = min(d, max(0.3, total - a))
        gx, gy = graphics.render_sequence(g["type"], g, look, W, H, d, work / f"g{k}")
        gi = add_input("-framerate", str(graphics.FPS), "-i", f"g{k}/%04d.png")
        fc.append(f"[{gi}:v]format=rgba,setpts=PTS-STARTPTS+{a:.3f}/TB[gs{k}]")
        fc.append(f"[{cur}][gs{k}]overlay=x={gx}:y={gy}:eof_action=pass:enable='between(t,{a:.3f},{a + d:.3f})'[go{k}]")
        cur = f"go{k}"
        placed_graphics.append({**g, "a": a, "d": d})
    post = draws[:]
    if ass.exists():
        post.append("subtitles=filename=captions.ass:fontsdir=fonts")
    fc.append(f"[{cur}]" + (",".join(post) if post else "null") + "[vout]")

    # sound: duck the music under speech, then normalise loudness
    music = p.edit.get("music")
    music_path = None
    if music:
        if music.get("path") and Path(music["path"]).exists():
            music_path = Path(music["path"]).resolve()
        elif music.get("mood"):
            music_path = audio_gen.music(music["mood"], total)
    if music_path:
        mi = add_input("-stream_loop", "-1", "-i", str(music_path))
        fc.append(f"[{mi}:a]atrim=duration={total},volume={music.get('gain_db', -16)}dB,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[mus]")
        fc.append("[acat]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asplit=2[voice][sc]")
        if music.get("duck", True):
            fc.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=350[duck]")
        else:
            fc.append("[sc]anullsink;[mus]anull[duck]")
        fc.append("[voice][duck]amix=inputs=2:duration=first:normalize=0[mix]")
        alast = "mix"
    else:
        alast = "acat"

    # sound effects on the visual beats
    sfx_cfg = p.edit.get("sfx") or {}
    hits: list[tuple[float, str]] = []
    if sfx_cfg.get("enabled", True) and sfx_cfg.get("intensity", 0.4) > 0:
        hits += [(tl.out_time(x["word_id"]), "pop") for x in pop_list]
        hits += [(x["a"], "whoosh") for x in fx if x["name"] in ("curtain", "wipe", "paper_tear", "whip_zoom")]
        hits += [(max(0.0, c["a"] - 0.2), "whoosh") for c in cutaways]
        for g in placed_graphics:
            if g["type"] == "counter":
                hits.append((g["a"] + min(1.4, g["d"] * 0.6), "ding"))
            elif g["type"] == "chapter_card":
                hits.append((max(0.0, g["a"] - 0.9), "riser"))
            else:
                hits.append((g["a"], "pop"))
        if (p.edit.get("hook") or {}).get("title"):
            hits.append((0.05, "impact"))
    hits = sorted((t, n) for t, n in hits if t is not None and t < total - 0.1)
    if hits:
        gain = -32 + 22 * float(sfx_cfg.get("intensity", 0.4))
        for j, (t, name) in enumerate(hits):
            si = add_input("-i", str(audio_gen.sfx(name)))
            ms = int(t * 1000)
            fc.append(f"[{si}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,adelay={ms}|{ms},volume={gain:.1f}dB[sx{j}]")
        fc.append(f"[{alast}]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[abed]")
        fc.append("[abed]" + "".join(f"[sx{j}]" for j in range(len(hits))) + f"amix=inputs={len(hits) + 1}:duration=first:normalize=0[asfx]")
        alast = "asfx"
    fc.append(f"[{alast}]loudnorm=I={p.edit.get('loudness', -14)}:TP=-1.5:LRA=11,aresample=48000[aout]")

    (work / "graph.txt").write_text(";\n".join(fc))
    out = p.path("renders", f"{quality}.mp4")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats", *args,
           "-filter_complex_script", "graph.txt", "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", str(total), str(out.resolve())]
    proc = subprocess.Popen(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.stdout
    for line in proc.stdout:
        if line.startswith("out_time_us=") and progress:
            try:
                progress(min(1.0, int(line.split("=")[1]) / 1e6 / total))
            except ValueError:
                pass
    err = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0:
        raise RenderError(f"ffmpeg failed: {err.strip()[-1500:]}")

    # sidecars
    if p.words:
        p.path("renders", "captions.srt").write_text(cap_mod.srt(p.words, tl, int(edit.get("captions", {}).get("words_per_line", 3))))
    p.path("renders", "timeline.json").write_text(json.dumps(
        {"duration": total, "segments": [s.__dict__ for s in tl.segments], "effects": fx, "popups": pop_list,
         "cutaways": cutaways, "graphics": placed_graphics, "sfx": hits, "look": look["name"], "shot_type": shot,
         "canvas": [W, H]}, indent=1, default=str))
    lic = []
    if music:
        lic.append(f"Music: {Path(music_path).name if music_path else '-'} — {music.get('license', 'unknown: confirm you have the rights')}")
    lic += [f"B-roll: {Path(c['path']).name} — {c.get('license', 'your library')}" for c in cutaways]
    if hits:
        lic.append("Sound effects: generated by ClipForge (no licence needed)")
    p.path("renders", "licenses.txt").write_text("\n".join(lic) + "\n" if lic else "No third-party media.\n")
    p.meta.setdefault("renders", {})[quality] = str(out.relative_to(p.dir))
    p.save()
    if progress:
        progress(1.0)
    return out


def hex_color(c: str) -> tuple[int, int, int]:
    return hex_rgb(c)
