"""Every edit is a command. The Studio UI, the CLI, the MCP server and the Claude planner all go through apply()."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

from . import audio_gen, autocut, broll, graphics, popups, recipes
from .effects import E
from .looks import LOOKS
from .project import SHOT_TYPES, Project, load_brand, save_brand
from .timeline import build, summary
from .transcript import sentences


class CommandError(ValueError):
    pass


OPS: dict[str, Callable[[Project, dict], str]] = {}
DOCS: dict[str, str] = {}


def op(name: str, doc: str):
    def deco(fn):
        OPS[name] = fn
        DOCS[name] = doc
        return fn
    return deco


def _ids(p: Project, ids) -> list[int]:
    valid = {w.id for w in p.words}
    out = [int(i) for i in ids or []]
    bad = [i for i in out if i not in valid]
    if bad:
        raise CommandError(f"Unknown word ids: {bad[:10]}")
    return out


def _word_id(p: Project, wid) -> int:
    return _ids(p, [wid])[0]


@op("cut_words", "Remove words from the video. args: ids (word ids)")
def _(p, c):
    ids = _ids(p, c.get("ids"))
    dele = set(p.edit["deleted"]) | set(ids)
    p.edit["deleted"] = sorted(dele)
    for i in ids:
        p.edit["cut_reasons"].setdefault(str(i), "manual")
    return f"Cut {len(ids)} words"


@op("restore_words", "Bring removed words back. args: ids")
def _(p, c):
    ids = set(_ids(p, c.get("ids")))
    p.edit["deleted"] = [i for i in p.edit["deleted"] if i not in ids]
    for i in ids:
        p.edit["cut_reasons"].pop(str(i), None)
    return f"Restored {len(ids)} words"


@op("auto_cut", "Remove fillers, retakes and long pauses. args: pause_max (s, default 0.4), fillers (bool), soft_fillers (bool: like/basically/you know), retakes (bool)")
def _(p, c):
    if not p.words:
        raise CommandError("Transcribe the video first.")
    if c.get("pause_max") is not None:
        p.edit["pause_max"] = max(0.1, float(c["pause_max"]))
    reasons = autocut.plan(p.words, c.get("fillers", True), c.get("soft_fillers", False), c.get("retakes", True),
                           set(p.edit["deleted"]))
    p.edit["deleted"] = sorted(set(p.edit["deleted"]) | set(reasons))
    for i, r in reasons.items():
        p.edit["cut_reasons"][str(i)] = r
    s = summary(p.words, p.edit, p.meta["duration"])
    return f"Auto cut: {s['before']}s → {s['after']}s ({', '.join(f'{v} {k}' for k, v in s['removed'].items()) or 'nothing to remove'})"


@op("set_pause_max", "Longest pause to keep between words, in seconds. args: seconds")
def _(p, c):
    p.edit["pause_max"] = max(0.1, float(c["seconds"]))
    return f"Pauses over {p.edit['pause_max']}s are cut"


@op("set_hook_title", "Big title shown for the first 3 seconds. args: text ('' to remove)")
def _(p, c):
    p.edit["hook"]["title"] = str(c.get("text", "")).strip()[:90]
    return f"Hook title: {p.edit['hook']['title'] or '(none)'}"


@op("move_hook", "Cold open: play words start_id..end_id first, then the rest. args: start_id, end_id")
def _(p, c):
    a, b = sorted((_word_id(p, c["start_id"]), _word_id(p, c["end_id"])))
    if b - a > 80:
        raise CommandError("Hook is too long. Pick one or two sentences.")
    p.edit["hook"]["move"] = [a, b]
    return f"Hook moved to the front: words {a}-{b}"


@op("clear_hook_move", "Undo a cold open; play in original order")
def _(p, c):
    p.edit["hook"]["move"] = None
    return "Original order restored"


@op("set_look", f"Apply a look. args: look ({', '.join(LOOKS)})")
def _(p, c):
    if c.get("look") not in LOOKS:
        raise CommandError(f"look must be one of {list(LOOKS)}")
    p.edit["look"] = c["look"]
    return f"Look: {LOOKS[c['look']]['label']}"


@op("set_captions", "Caption options. args: words_per_line (1-5), position (0-1, fraction of height), karaoke (bool), "
    "animation (pop|bounce|rise|none), emphasis (auto = numbers and names in your accent colour | none)")
def _(p, c):
    cap = p.edit["captions"]
    if c.get("animation") is not None:
        if c["animation"] not in ("pop", "bounce", "rise", "none"):
            raise CommandError("animation must be pop, bounce, rise or none")
        cap["animation"] = c["animation"]
    if c.get("emphasis") is not None:
        cap["emphasis"] = "auto" if c["emphasis"] == "auto" else "none"
    if c.get("words_per_line") is not None:
        cap["words_per_line"] = max(1, min(5, int(c["words_per_line"])))
    if c.get("position") is not None:
        cap["position"] = max(0.3, min(0.92, float(c["position"])))
    if c.get("karaoke") is not None:
        cap["karaoke"] = bool(c["karaoke"])
    return f"Captions: {cap['words_per_line']} words/line at {round(cap['position'] * 100)}% height"


@op("auto_popups", "Detect numbers, names and places and add pop-ups (max one every N seconds). args: every (s, default 4)")
def _(p, c):
    tl = build(p.words, p.edit, p.meta["duration"])
    manual = [x for x in p.edit["popups"] if x.get("source") == "manual"]
    found = popups.detect(p.words, tl, float(c.get("every", 4.0)), p.dir / "media" / "popups")
    every = float(c.get("every", 4.0))
    mt = [tl.out_time(x["word_id"]) for x in manual]
    auto = [{**x, "id": uuid.uuid4().hex[:6], "enabled": True, "source": "auto"} for x in found
            if all(t is None or abs(tl.out_time(x["word_id"]) - t) >= every for t in mt)]
    p.edit["popups"] = manual + auto
    return f"{len(auto)} pop-ups found: " + ", ".join(x["text"] for x in auto)


@op("add_popup", "Add a pop-up on a word. args: word_id, kind (number|keyword|image), text, image (path, optional), sub (small line, optional)")
def _(p, c):
    wid = _word_id(p, c["word_id"])
    kind = c.get("kind", "keyword")
    if kind not in ("number", "keyword", "image"):
        raise CommandError("kind must be number, keyword or image")
    if kind == "image" and not (c.get("image") and Path(c["image"]).expanduser().exists()):
        raise CommandError("image pop-ups need an existing image path")
    x = {"id": uuid.uuid4().hex[:6], "word_id": wid, "kind": kind, "text": str(c.get("text", ""))[:40], "enabled": True,
         "source": "manual", **({"image": str(Path(c["image"]).expanduser())} if c.get("image") else {}),
         **({"sub": str(c["sub"])[:40]} if c.get("sub") else {})}
    p.edit["popups"] = [y for y in p.edit["popups"] if y["word_id"] != wid] + [x]
    return f"Pop-up '{x['text']}' on word {wid}"


@op("remove_popup", "Remove a pop-up. args: popup_id")
def _(p, c):
    before = len(p.edit["popups"])
    p.edit["popups"] = [x for x in p.edit["popups"] if x["id"] != c.get("popup_id")]
    if len(p.edit["popups"]) == before:
        raise CommandError("No such pop-up")
    return "Pop-up removed"


@op("toggle_popup", "Turn a pop-up on or off. args: popup_id, enabled (bool)")
def _(p, c):
    for x in p.edit["popups"]:
        if x["id"] == c.get("popup_id"):
            x["enabled"] = bool(c.get("enabled", not x.get("enabled", True)))
            return f"Pop-up {'on' if x['enabled'] else 'off'}"
    raise CommandError("No such pop-up")


@op("add_effect", "Add an effect starting at a word. args: name (see list_effects), word_id, duration (s, optional), params (optional)")
def _(p, c):
    if c.get("name") not in E:
        raise CommandError(f"Unknown effect. Choose from {list(E)}")
    wid = _word_id(p, c["word_id"])
    fx = {"id": uuid.uuid4().hex[:6], "name": c["name"], "word_id": wid}
    if c.get("duration"):
        fx["duration"] = max(0.05, min(30.0, float(c["duration"])))
    if c.get("params"):
        fx["params"] = dict(c["params"])
    p.edit["effects"].append(fx)
    return f"{E[c['name']].label} at word {wid}"


@op("remove_effect", "Remove an effect. args: effect_id")
def _(p, c):
    before = len(p.edit["effects"])
    p.edit["effects"] = [x for x in p.edit["effects"] if x["id"] != c.get("effect_id")]
    if len(p.edit["effects"]) == before:
        raise CommandError("No such effect")
    return "Effect removed"


@op("set_music", "Background music. args: path (audio file, or empty to remove), gain_db (default -16), duck (bool, default true)")
def _(p, c):
    if not c.get("path"):
        p.edit["music"] = None
        return "Music removed"
    path = Path(c["path"]).expanduser()
    if not path.exists():
        raise CommandError(f"Music file not found: {path}")
    p.edit["music"] = {"path": str(path.resolve()), "gain_db": float(c.get("gain_db", -16)), "duck": bool(c.get("duck", True)),
                       **({"license": str(c["license"])} if c.get("license") else {})}
    return f"Music: {path.name} at {p.edit['music']['gain_db']} dB" + (", ducked under speech" if p.edit["music"]["duck"] else "")


@op("set_loudness", "Target loudness in LUFS (platforms use about -14). args: lufs")
def _(p, c):
    p.edit["loudness"] = max(-24.0, min(-9.0, float(c["lufs"])))
    return f"Loudness target {p.edit['loudness']} LUFS"


@op("set_fit", "How a landscape video fills the vertical frame. args: fit (fill = crop to fill, blur = fit with blurred background)")
def _(p, c):
    if c.get("fit") not in ("fill", "blur"):
        raise CommandError("fit must be fill or blur")
    p.edit["fit"] = c["fit"]
    return f"Fit: {c['fit']}"


@op("set_shot_type", f"How the video was shot. args: shot_type ({', '.join(SHOT_TYPES)})")
def _(p, c):
    if c.get("shot_type") not in SHOT_TYPES:
        raise CommandError(f"shot_type must be one of {list(SHOT_TYPES)}")
    p.meta["shot_type"] = c["shot_type"]
    return f"Shot type: {SHOT_TYPES[c['shot_type']]}"


@op("set_broll", "Clips to show over the voice (voiceover_clips and clips_text). args: paths (list of video files)")
def _(p, c):
    paths = [str(Path(x).expanduser().resolve()) for x in c.get("paths", [])]
    missing = [x for x in paths if not Path(x).exists()]
    if missing:
        raise CommandError(f"Not found: {missing}")
    p.edit["broll"] = paths
    return f"{len(paths)} clips set"


@op("set_brand", "Save your brand once; every video uses it. args: any of name, handle, cta, hashtags (list), palette {primary, accent, ink, paper} (hex), fonts {title, caption} (family name or font file)")
def _(p, c):
    return update_brand(c)


def update_brand(c: dict) -> str:
    """Brand is global, not per project."""
    brand = load_brand()
    for k in ("name", "handle", "cta", "hashtags", "hook_position"):
        if k in c:
            brand[k] = c[k]
    for k in ("palette", "fonts"):
        if isinstance(c.get(k), dict):
            brand[k].update({a: b for a, b in c[k].items() if b is not None})
    for k, v in brand["palette"].items():
        if not (isinstance(v, str) and v.startswith("#") and len(v) in (4, 7)):
            raise CommandError(f"palette.{k} must be a hex colour like #FFC23D")
    save_brand(brand)
    return "Brand saved"


@op("set_post_copy", "Copy for the post kit. args: title (cover), slides (list of short lines for the carousel), caption (post text), hashtags (list)")
def _(p, c):
    post = p.edit.get("post") or {}
    for k in ("title", "slides", "caption", "hashtags"):
        if k in c:
            post[k] = c[k]
    if "slides" in post and not (isinstance(post["slides"], list) and all(isinstance(s, str) for s in post["slides"])):
        raise CommandError("slides must be a list of strings")
    p.edit["post"] = post
    return "Post copy saved"


@op("set_music_mood", f"Background music that fits the mood, made on this computer (licence-free) or picked from your library. args: mood ({', '.join(audio_gen.MOODS)}), gain_db (default -20), duck (bool)")
def _(p, c):
    mood = c.get("mood")
    if mood not in audio_gen.MOODS:
        raise CommandError(f"mood must be one of {list(audio_gen.MOODS)}")
    lib = audio_gen.library_track(mood)
    p.edit["music"] = {"mood": mood, "gain_db": float(c.get("gain_db", -20)), "duck": bool(c.get("duck", True)),
                       **({"path": lib["path"], "license": lib["license"]} if lib else {"license": "Generated by ClipForge (no licence needed)"})}
    return f"Music: {audio_gen.MOODS[mood]['label']} ({'your library' if lib else 'generated'})"


@op("set_sfx", "Sound effects on transitions, pop-ups and graphics. args: enabled (bool), intensity (0-1; 0.3 is subtle)")
def _(p, c):
    s = p.edit.setdefault("sfx", {"enabled": True, "intensity": 0.4})
    if c.get("enabled") is not None:
        s["enabled"] = bool(c["enabled"])
    if c.get("intensity") is not None:
        s["intensity"] = max(0.0, min(1.0, float(c["intensity"])))
    return f"Sound effects {'on' if s['enabled'] else 'off'} at {round(s['intensity'] * 100)}%"


@op("set_aspect", f"Frame shape for the platform. args: aspect ({', '.join(recipes.ASPECTS)}); 9:16 Reels/TikTok/Shorts, 4:5 LinkedIn/Instagram feed, 1:1, 16:9 YouTube")
def _(p, c):
    if c.get("aspect") not in recipes.ASPECTS:
        raise CommandError(f"aspect must be one of {list(recipes.ASPECTS)}")
    p.edit["aspect"] = c["aspect"]
    return f"Aspect {c['aspect']}"


@op("add_cutaway", "B-roll cutaway at a word. args: word_id, path (video or image), duration (s, default 2), mode (full|pip)")
def _(p, c):
    wid = _word_id(p, c["word_id"])
    path = Path(str(c.get("path", ""))).expanduser()
    if not path.exists():
        raise CommandError(f"B-roll file not found: {path}")
    mode = c.get("mode", "full")
    if mode not in ("full", "pip"):
        raise CommandError("mode must be full or pip")
    x = {"id": uuid.uuid4().hex[:6], "word_id": wid, "path": str(path.resolve()), "duration": max(0.5, min(8.0, float(c.get("duration", 2.0)))),
         "mode": mode, "license": broll.license_of(path), "source": c.get("source", "manual")}
    p.edit["cutaways"] = [y for y in p.edit.get("cutaways", []) if y["word_id"] != wid] + [x]
    return f"B-roll {path.name} at word {wid}"


@op("auto_broll", "Find B-roll for what is said, from your library (and Pexels if PEXELS_API_KEY is set). args: every (s, default 6), queries (optional list of {word_id, query})")
def _(p, c):
    tl = build(p.words, p.edit, p.meta["duration"])
    files = broll.library(p.dir)
    added = []
    for q in c.get("queries") or []:
        f = broll.match(q["query"], files) or broll.pexels(q["query"], "portrait" if p.edit.get("aspect", "9:16") in ("9:16", "4:5") else "landscape")
        if f:
            added.append({"word_id": int(q["word_id"]), "path": str(f), "duration": float(q.get("duration", 2.0)), "mode": "full", "query": q["query"]})
    if not c.get("queries"):
        added = broll.auto(p.words, tl, files, float(c.get("every", 6.0)))
    keep = [x for x in p.edit.get("cutaways", []) if x.get("source") != "auto"]
    for a in added:
        keep.append({**a, "id": uuid.uuid4().hex[:6], "license": broll.license_of(Path(a["path"])), "source": "auto"})
    p.edit["cutaways"] = keep
    if not added:
        return "No matching B-roll. Add clips to your B-roll folder (named after what they show) or set PEXELS_API_KEY."
    return f"{len(added)} B-roll cutaways: " + ", ".join(Path(a["path"]).stem for a in added)


@op("remove_cutaway", "Remove a B-roll cutaway. args: cutaway_id")
def _(p, c):
    before = len(p.edit.get("cutaways", []))
    p.edit["cutaways"] = [x for x in p.edit.get("cutaways", []) if x["id"] != c.get("cutaway_id")]
    if len(p.edit["cutaways"]) == before:
        raise CommandError("No such cutaway")
    return "Cutaway removed"


@op("add_graphic", f"Motion graphic at a word. args: type ({', '.join(graphics.TYPES)}), word_id, duration (optional), and its fields: "
    + "; ".join(f"{k}: {', '.join(v['fields'])}" for k, v in graphics.TYPES.items()))
def _(p, c):
    kind = c.get("type")
    if kind not in graphics.TYPES:
        raise CommandError(f"type must be one of {list(graphics.TYPES)}")
    wid = _word_id(p, c["word_id"]) if kind != "end_card" or c.get("word_id") is not None else (p.words[-1].id if p.words else 0)
    g = {"id": uuid.uuid4().hex[:6], "type": kind, "word_id": wid, "source": c.get("source", "manual")}
    for k in graphics.TYPES[kind]["fields"]:
        if c.get(k) not in (None, ""):
            g[k] = c[k]
    if kind == "bar_chart" and len(g.get("values") or []) != len(g.get("labels") or []):
        raise CommandError("bar_chart needs the same number of labels and values")
    if c.get("duration"):
        g["duration"] = max(0.8, min(12.0, float(c["duration"])))
    p.edit.setdefault("graphics", [])
    if kind == "end_card":
        p.edit["graphics"] = [x for x in p.edit["graphics"] if x["type"] != "end_card"]
    p.edit["graphics"].append(g)
    return f"{graphics.TYPES[kind]['label']} added"


@op("remove_graphic", "Remove a motion graphic. args: graphic_id")
def _(p, c):
    before = len(p.edit.get("graphics", []))
    p.edit["graphics"] = [x for x in p.edit.get("graphics", []) if x["id"] != c.get("graphic_id")]
    if len(p.edit["graphics"]) == before:
        raise CommandError("No such graphic")
    return "Graphic removed"


@op("auto_pace", "Add subtle camera moves wherever a shot holds too long, snapped to the music beat. args: level (calm|balanced|fast)")
def _(p, c):
    level = c.get("level", "balanced")
    p.edit["effects"] = [x for x in p.edit["effects"] if x.get("source") != "pace"]
    added = recipes.pace(p, level)
    for x in added:
        p.edit["effects"].append({"id": uuid.uuid4().hex[:6], **x})
    p.edit["pace"] = level
    return f"Pacing {level}: {len(added)} pattern interrupts added"


@op("apply_recipe", f"Professional preset: look, music, captions, pacing, graphics. args: recipe ({', '.join(recipes.RECIPES)})")
def _(p, c):
    name = c.get("recipe")
    if name not in recipes.RECIPES:
        raise CommandError(f"recipe must be one of {list(recipes.RECIPES)}")
    r = recipes.RECIPES[name]
    brand = load_brand()
    msgs = []
    p.edit["look"] = r["look"]
    p.edit["aspect"] = r["aspect"]
    p.edit["captions"].update(r["captions"])
    if r.get("fit"):
        p.edit["fit"] = r["fit"]
    p.edit.setdefault("sfx", {})
    p.edit["sfx"].update({"enabled": r["sfx"] > 0, "intensity": r["sfx"]})
    if r["mood"]:
        msgs.append(OPS["set_music_mood"](p, {"mood": r["mood"], "gain_db": r["music_db"]}))
    else:
        p.edit["music"] = None
    if p.words:
        if r["popups"]:
            msgs.append(OPS["auto_popups"](p, {}))
        if r["broll"]:
            msgs.append(OPS["auto_broll"](p, {}))
        p.edit["graphics"] = [g for g in p.edit.get("graphics", []) if g.get("source") != "recipe"]
        if r["lower_third"] and brand.get("name"):
            first = next((w.id for w in p.words if w.id not in set(p.edit["deleted"])), p.words[0].id)
            p.edit["graphics"].append({"id": uuid.uuid4().hex[:6], "type": "lower_third", "word_id": first, "source": "recipe",
                                       "title": brand["name"], "subtitle": brand.get("handle", "")})
        if r["end_card"]:
            p.edit["graphics"] = [g for g in p.edit["graphics"] if g["type"] != "end_card"]
            p.edit["graphics"].append({"id": uuid.uuid4().hex[:6], "type": "end_card", "word_id": p.words[-1].id, "source": "recipe",
                                       "text": brand.get("cta") or "Follow for more", "handle": brand.get("handle", "")})
        msgs.append(OPS["auto_pace"](p, {"level": r["pace"]}))
    return f"Recipe {r['label']} applied. " + " ".join(m for m in msgs if m)


BRAND_OPS = {"set_brand"}
NO_HISTORY = BRAND_OPS


def apply(p: Project, cmd: dict) -> str:
    name = cmd.get("op")
    if name not in OPS:
        raise CommandError(f"Unknown op '{name}'. Ops: {sorted(OPS)}")
    if name not in NO_HISTORY:
        p.push_history(_label(cmd))
    try:
        msg = OPS[name](p, cmd)
    except (KeyError, TypeError, ValueError) as e:
        if name not in NO_HISTORY:
            p.undo()
        raise CommandError(f"{name}: {e}") from e
    p.save()
    return msg


def apply_many(p: Project, cmds: list[dict]) -> list[str]:
    return [apply(p, c) for c in cmds]


def _label(cmd: dict) -> str:
    args = ", ".join(f"{k}={v}" for k, v in cmd.items() if k != "op")
    return f"{cmd['op']}({args[:80]})"


def state(p: Project, with_words: bool = True) -> dict:
    """Compact view for UIs and for Claude."""
    out = {"id": p.id, "name": p.meta["name"], "shot_type": p.meta.get("shot_type"), "transcribed": bool(p.words),
           "look": p.edit["look"], "hook": p.edit["hook"], "captions": p.edit["captions"], "pause_max": p.edit["pause_max"],
           "popups": p.edit["popups"], "effects": p.edit["effects"], "music": p.edit["music"], "fit": p.edit["fit"],
           "cutaways": p.edit.get("cutaways", []), "graphics": p.edit.get("graphics", []), "sfx": p.edit.get("sfx"),
           "aspect": p.edit.get("aspect", "9:16"), "loudness": p.edit.get("loudness", -14), "pace": p.edit.get("pace"),
           "post": p.edit.get("post"), "renders": p.meta.get("renders", {}), "post_kit": p.meta.get("post_kit"),
           "source_rel": p.meta["source"], "history": p.history_labels()[-15:], "brand": load_brand()}
    if p.words:
        out["summary"] = summary(p.words, p.edit, p.meta["duration"])
    else:
        out["summary"] = {"before": p.meta.get("duration"), "after": p.meta.get("duration"), "cuts": 0, "removed": {}}
    if with_words:
        dele = set(p.edit["deleted"])
        out["words"] = [{"id": w.id, "text": w.text, "start": w.start, "end": w.end, "cut": w.id in dele,
                         "reason": p.edit["cut_reasons"].get(str(w.id))} for w in p.words]
    return out


def transcript_text(p: Project) -> str:
    """One sentence per line, each word as id:text; removed words in ~~strikethrough~~."""
    dele = set(p.edit["deleted"])
    lines = []
    for s in sentences(p.words):
        toks = [f"~~{w.id}:{w.text}~~" if w.id in dele else f"{w.id}:{w.text}" for w in s]
        lines.append(f"[{s[0].start:6.2f}s] " + " ".join(toks))
    return "\n".join(lines)
