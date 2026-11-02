"""Professional recipes, the pacing engine (pattern interrupts) and the pre-flight check."""
from __future__ import annotations

from .audio_gen import MOODS, beats
from .project import Project, load_brand
from .timeline import Timeline, build
from .transcript import sentences

RECIPES: dict[str, dict] = {
    "thought_leader": {
        "label": "Thought leader", "about": "LinkedIn-ready 4:5. Editorial look, calm focus music, name lower third, measured pacing.",
        "aspect": "4:5", "look": "editorial", "mood": "focus", "music_db": -22, "pace": "balanced", "sfx": 0.25,
        "captions": {"words_per_line": 4, "animation": "rise"}, "lower_third": True, "end_card": True, "popups": True, "broll": False,
    },
    "founder_story": {
        "label": "Founder story", "about": "Cinematic music, warm creator captions, cold-open hook, end card.",
        "aspect": "9:16", "look": "creator", "mood": "cinematic", "music_db": -20, "pace": "balanced", "sfx": 0.4,
        "captions": {"words_per_line": 3, "animation": "pop"}, "lower_third": True, "end_card": True, "popups": True, "broll": True,
    },
    "explainer": {
        "label": "Explainer", "about": "Bold captions, counting stats, fast pattern interrupts, tech music.",
        "aspect": "9:16", "look": "bold", "mood": "tech", "music_db": -21, "pace": "fast", "sfx": 0.55,
        "captions": {"words_per_line": 2, "animation": "bounce"}, "lower_third": False, "end_card": True, "popups": True, "broll": True,
    },
    "podcast_clip": {
        "label": "Podcast clip", "about": "Soft captions, blurred-background fit, no music, gentle pacing.",
        "aspect": "9:16", "look": "soft", "mood": None, "music_db": None, "pace": "calm", "sfx": 0.0, "fit": "blur",
        "captions": {"words_per_line": 4, "animation": "rise"}, "lower_third": True, "end_card": False, "popups": True, "broll": False,
    },
    "product_demo": {
        "label": "Product demo", "about": "Uplifting music, B-roll cutaways, stickers and stats, quick cuts.",
        "aspect": "9:16", "look": "creator", "mood": "uplifting", "music_db": -19, "pace": "fast", "sfx": 0.5,
        "captions": {"words_per_line": 3, "animation": "pop"}, "lower_third": False, "end_card": True, "popups": True, "broll": True,
    },
}

PACE = {"calm": 6.0, "balanced": 4.0, "fast": 2.6}
ASPECTS = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}


def visual_changes(p: Project, tl: Timeline) -> list[float]:
    """Times where the picture already changes: cuts, effects, pop-ups, cutaways, graphics."""
    times = [s.out_start for s in tl.segments]
    for coll in ("effects", "popups", "cutaways", "graphics"):
        for x in p.edit.get(coll, []):
            if x.get("source") == "pace":
                continue
            t = tl.out_time(x.get("word_id", -1))
            if t is not None:
                times.append(t)
    return sorted(set(round(t, 2) for t in times))


def pace(p: Project, level: str) -> list[dict]:
    """Add a subtle camera move wherever the picture holds longer than the level allows."""
    if level not in PACE:
        raise ValueError(f"level must be one of {list(PACE)}")
    max_hold = PACE[level]
    tl = build(p.words, p.edit, p.meta["duration"])
    music = p.edit.get("music") or {}
    grid = beats(music["mood"], tl.duration) if music.get("mood") in MOODS else []
    changes = visual_changes(p, tl) + [tl.duration]
    kept = [w for w in p.words if w.id in tl.word_out]
    starts = [(tl.word_out[w.id][0], w.id) for w in kept]
    added, last, flip = [], 0.0, 0
    for nxt in changes:
        while nxt - last > max_hold:
            target = last + max_hold * 0.85
            if grid:
                target = min(grid, key=lambda b: abs(b - target))
            t, wid = min(starts, key=lambda s: abs(s[0] - target))
            if t <= last + 0.5 or t >= nxt - 0.5:
                break
            name = ("zoom_in_slow", "zoom_punch")[flip % 2]
            added.append({"name": name, "word_id": wid, "duration": min(2.5, nxt - t), "source": "pace",
                          "params": {"amount": 0.08 if name == "zoom_punch" else 0.12}})
            flip += 1
            last = t
        last = max(last, nxt)
    return added


def preflight(p: Project, platform: str = "reels") -> list[dict]:
    """Checks before export. Each issue may carry a fix command."""
    issues: list[dict] = []
    tl = build(p.words, p.edit, p.meta["duration"]) if p.words else None
    dur = tl.duration if tl else float(p.meta.get("duration") or 0)
    add = lambda level, msg, fix=None: issues.append({"level": level, "message": msg, **({"fix": fix} if fix else {})})  # noqa: E731
    if not p.words:
        add("bad", "No transcript: captions, auto-cut and pop-ups need one.")
        return issues
    hook = p.edit.get("hook") or {}
    if not hook.get("title") and not hook.get("move"):
        first = sentences([w for w in p.words if w.id in tl.word_out])[:1]
        line = " ".join(w.text for w in first[0]) if first else ""
        add("warn", "No hook on screen in the first 3 seconds. Viewers scrolling with sound off see only the speaker.",
            {"op": "set_hook_title", "text": line[:60]})
    limits = {"reels": 90, "tiktok": 180, "shorts": 60, "linkedin": 120}
    if dur > limits.get(platform, 90):
        add("warn", f"{dur:.0f}s is long for {platform}. Most high-retention clips run 20–60s. Try auto-cut or ask Claude to tighten it.")
    words_per_s = len(tl.word_out) / max(dur, 0.1)
    if words_per_s > 3.6:
        add("warn", f"Speech is fast ({words_per_s:.1f} words/s). Use 2 words per line so captions stay readable.",
            {"op": "set_captions", "words_per_line": 2})
    pos = float(p.edit["captions"].get("position", 0.8))
    if p.edit.get("aspect", "9:16") == "9:16" and pos > 0.84:
        add("bad", "Captions sit under the platform's caption and button area.", {"op": "set_captions", "position": 0.78})
    if abs(float(p.edit.get("loudness", -14)) + 14) > 1.5:
        add("warn", f"Loudness target {p.edit['loudness']} LUFS; platforms play around −14.", {"op": "set_loudness", "lufs": -14})
    holds = [b - a for a, b in zip(visual_changes(p, tl), visual_changes(p, tl)[1:] + [dur]) if b - a > 6]
    if holds:
        add("warn", f"{len(holds)} shots hold longer than 6s without a visual change.", {"op": "auto_pace", "level": "balanced"})
    m = p.edit.get("music")
    if m and m.get("path") and not m.get("license"):
        add("warn", "Music licence unknown. Only publish music you have the rights to.")
    if not any(g["type"] == "end_card" for g in p.edit.get("graphics", [])):
        brand = load_brand()
        add("info", "No end card. A clear next step lifts follows.",
            {"op": "add_graphic", "type": "end_card", "word_id": max(tl.word_out), "text": brand.get("cta") or "Follow for more",
             "handle": brand.get("handle", "")})
    if not issues:
        add("good", "Ready to export.")
    return issues
