"""MCP server: lets Claude (Desktop, Code, or any MCP client) run ClipForge on the user's own subscription."""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from . import audio_gen, commands, graphics, recipes, render as render_mod, repurpose
from .effects import catalog
from .looks import LOOKS
from .project import SHOT_TYPES, Project
from .transcript import import_transcript, transcribe as transcribe_audio

INSTRUCTIONS = """ClipForge edits short-form videos for professional audiences. Typical flow: create_project -> transcribe ->
get_transcript -> auto_cut -> apply_recipe (or set_look, set_aspect, set_music_mood yourself) -> pick the hook
(set_hook_title, optionally move_hook) -> add_graphic on the lines that carry numbers, names, steps or the quotable line ->
auto_broll -> auto_pace -> preflight and apply its fixes -> render(quality='preview') -> review with the user ->
render(quality='final') -> set_post_copy -> make_post_kit. Never invent numbers or claims the speaker did not make.
Word ids come from get_transcript. Every edit is undoable with undo. Brand settings are saved once with set_brand."""

mcp = MCPServer("clipforge", instructions=INSTRUCTIONS)


def _run(pid: str, cmd: dict) -> str:
    p = Project.load(pid)
    msg = commands.apply(p, cmd)
    s = commands.state(p, with_words=False)["summary"]
    return f"{msg}. Length {s['before']}s → {s['after']}s."


@mcp.tool()
def list_projects() -> str:
    """List projects, newest first."""
    return json.dumps([{k: m.get(k) for k in ("id", "name", "shot_type", "duration", "transcribed")} for m in Project.list()])


@mcp.tool()
def create_project(video_path: str, shot_type: str = "on_camera", name: str = "") -> str:
    """Start a project from a video file. shot_type: on_camera, voiceover_clips, faceless, clips_text."""
    if shot_type not in SHOT_TYPES:
        return f"shot_type must be one of {list(SHOT_TYPES)}"
    p = Project.create(Path(video_path), name or None, shot_type)
    return json.dumps({"project_id": p.id, "duration": p.meta["duration"], "size": [p.meta["width"], p.meta["height"]]})


@mcp.tool()
def transcribe(project_id: str, language: str = "", model: str = "small") -> str:
    """Transcribe on this computer with word timings (faster-whisper). language: e.g. 'en', 'ta', 'ar'; empty = auto."""
    p = Project.load(project_id)
    p.set_words(transcribe_audio(p.source, language or None, model))
    return f"{len(p.words)} words transcribed. Call get_transcript to read them."


@mcp.tool()
def import_transcript_file(project_id: str, path: str) -> str:
    """Use an existing transcript JSON (ClipForge, Whisper, or a word list with text/start/end)."""
    p = Project.load(project_id)
    p.set_words(import_transcript(Path(path)))
    return f"{len(p.words)} words imported."


@mcp.tool()
def get_transcript(project_id: str) -> str:
    """The transcript as one sentence per line, each word as id:text. Removed words appear as ~~id:text~~."""
    p = Project.load(project_id)
    if not p.words:
        return "Not transcribed yet. Call transcribe first."
    return commands.transcript_text(p)


@mcp.tool()
def get_state(project_id: str) -> str:
    """Current edit: look, hook, captions, pop-ups, effects, music, lengths, recent history and brand."""
    return json.dumps(commands.state(Project.load(project_id), with_words=False), ensure_ascii=False)


@mcp.tool()
def auto_cut(project_id: str, pause_max: float = 0.4, fillers: bool = True, soft_fillers: bool = False, retakes: bool = True) -> str:
    """Remove ums/uhs, restarted phrases (keeps the last take) and pauses longer than pause_max seconds."""
    return _run(project_id, {"op": "auto_cut", "pause_max": pause_max, "fillers": fillers, "soft_fillers": soft_fillers, "retakes": retakes})


@mcp.tool()
def cut_words(project_id: str, ids: list[int]) -> str:
    """Remove words from the video by id."""
    return _run(project_id, {"op": "cut_words", "ids": ids})


@mcp.tool()
def restore_words(project_id: str, ids: list[int]) -> str:
    """Bring removed words back."""
    return _run(project_id, {"op": "restore_words", "ids": ids})


@mcp.tool()
def set_hook_title(project_id: str, text: str) -> str:
    """Big title over the first 3 seconds. Empty text removes it."""
    return _run(project_id, {"op": "set_hook_title", "text": text})


@mcp.tool()
def move_hook(project_id: str, start_id: int, end_id: int) -> str:
    """Cold open: play words start_id..end_id first, then the rest of the video."""
    return _run(project_id, {"op": "move_hook", "start_id": start_id, "end_id": end_id})


@mcp.tool()
def list_looks() -> str:
    """The five looks."""
    return json.dumps({k: v["about"] for k, v in LOOKS.items()})


@mcp.tool()
def set_look(project_id: str, look: str) -> str:
    """Apply a look: editorial, bold, creator, soft or paper."""
    return _run(project_id, {"op": "set_look", "look": look})


@mcp.tool()
def set_captions(project_id: str, words_per_line: int = 3, position: float = 0.8, karaoke: bool = True) -> str:
    """Caption layout. position is the fraction of the frame height (0.8 = lower fifth)."""
    return _run(project_id, {"op": "set_captions", "words_per_line": words_per_line, "position": position, "karaoke": karaoke})


@mcp.tool()
def auto_popups(project_id: str, every: float = 4.0) -> str:
    """Detect numbers, names and places; add pop-ups at most once every `every` seconds, away from the face."""
    return _run(project_id, {"op": "auto_popups", "every": every})


@mcp.tool()
def add_popup(project_id: str, word_id: int, text: str, kind: str = "keyword", image: str = "", sub: str = "") -> str:
    """Pop-up on a word. kind: number (big number card), keyword (name or idea), image (a photo file)."""
    return _run(project_id, {"op": "add_popup", "word_id": word_id, "text": text, "kind": kind, "image": image or None, "sub": sub or None})


@mcp.tool()
def remove_popup(project_id: str, popup_id: str) -> str:
    """Remove a pop-up by id (see get_state)."""
    return _run(project_id, {"op": "remove_popup", "popup_id": popup_id})


@mcp.tool()
def list_effects() -> str:
    """All one-tap effects with category and default duration."""
    return json.dumps(catalog())


@mcp.tool()
def add_effect(project_id: str, name: str, word_id: int, duration: float = 0, text: str = "") -> str:
    """Add an effect starting at a word. text is used by sticker and glass_widget."""
    cmd = {"op": "add_effect", "name": name, "word_id": word_id}
    if duration:
        cmd["duration"] = duration
    if text:
        cmd["params"] = {"text": text}
    return _run(project_id, cmd)


@mcp.tool()
def remove_effect(project_id: str, effect_id: str) -> str:
    """Remove an effect by id (see get_state)."""
    return _run(project_id, {"op": "remove_effect", "effect_id": effect_id})


@mcp.tool()
def set_music(project_id: str, path: str = "", gain_db: float = -16, duck: bool = True) -> str:
    """Background music from an audio file you have the rights to use; ducked under speech. Empty path removes it."""
    return _run(project_id, {"op": "set_music", "path": path, "gain_db": gain_db, "duck": duck})


@mcp.tool()
def set_brand(name: str = "", handle: str = "", cta: str = "", primary: str = "", accent: str = "", ink: str = "",
              paper: str = "", title_font: str = "", caption_font: str = "", hashtags: list[str] | None = None) -> str:
    """Save the brand once (colours as hex, fonts as family name or font file). Every video and post uses it."""
    cmd: dict = {}
    for k, v in (("name", name), ("handle", handle), ("cta", cta)):
        if v:
            cmd[k] = v
    if hashtags is not None:
        cmd["hashtags"] = hashtags
    pal = {k: v for k, v in (("primary", primary), ("accent", accent), ("ink", ink), ("paper", paper)) if v}
    fonts = {k: v for k, v in (("title", title_font), ("caption", caption_font)) if v}
    if pal:
        cmd["palette"] = pal
    if fonts:
        cmd["fonts"] = fonts
    return commands.update_brand(cmd)


@mcp.tool()
def set_post_copy(project_id: str, title: str = "", slides: list[str] | None = None, caption: str = "",
                  hashtags: list[str] | None = None) -> str:
    """Write the post kit copy: cover title, carousel slide lines, post caption, hashtags."""
    cmd: dict = {"op": "set_post_copy"}
    if title:
        cmd["title"] = title
    if slides is not None:
        cmd["slides"] = slides
    if caption:
        cmd["caption"] = caption
    if hashtags is not None:
        cmd["hashtags"] = hashtags
    return _run(project_id, cmd)


@mcp.tool()
def list_recipes() -> str:
    """Professional presets (look, aspect, music, captions, pacing, graphics) for different content types."""
    return json.dumps({k: v["about"] for k, v in recipes.RECIPES.items()})


@mcp.tool()
def apply_recipe(project_id: str, recipe: str) -> str:
    """Apply a recipe: thought_leader, founder_story, explainer, podcast_clip, product_demo. Run after auto_cut."""
    return _run(project_id, {"op": "apply_recipe", "recipe": recipe})


@mcp.tool()
def list_music_moods() -> str:
    """Moods for generated, licence-free background music (or tracks tagged in your library)."""
    return json.dumps({k: v["about"] for k, v in audio_gen.MOODS.items()})


@mcp.tool()
def set_music_mood(project_id: str, mood: str, gain_db: float = -20, duck: bool = True) -> str:
    """Background music that fits the content: uplifting, focus, cinematic, tech, warm. Ducked under speech."""
    return _run(project_id, {"op": "set_music_mood", "mood": mood, "gain_db": gain_db, "duck": duck})


@mcp.tool()
def set_sfx(project_id: str, enabled: bool = True, intensity: float = 0.4) -> str:
    """Sound effects (whoosh, pop, ding, riser, impact) placed on transitions, pop-ups and graphics. 0.3 is subtle."""
    return _run(project_id, {"op": "set_sfx", "enabled": enabled, "intensity": intensity})


@mcp.tool()
def set_aspect(project_id: str, aspect: str) -> str:
    """9:16 (Reels, TikTok, Shorts), 4:5 (LinkedIn, Instagram feed), 1:1, or 16:9 (YouTube)."""
    return _run(project_id, {"op": "set_aspect", "aspect": aspect})


@mcp.tool()
def auto_broll(project_id: str, queries: list[dict] | None = None, every: float = 6.0) -> str:
    """B-roll cutaways. Without queries: matches spoken words to files in the B-roll library.
    With queries, e.g. [{"word_id": 14, "query": "city skyline"}]: library first, then Pexels if PEXELS_API_KEY is set."""
    cmd: dict = {"op": "auto_broll", "every": every}
    if queries:
        cmd["queries"] = queries
    return _run(project_id, cmd)


@mcp.tool()
def add_cutaway(project_id: str, word_id: int, path: str, duration: float = 2.0, mode: str = "full") -> str:
    """Put a specific B-roll video or image over the speaker at a word. mode: full or pip (picture-in-picture)."""
    return _run(project_id, {"op": "add_cutaway", "word_id": word_id, "path": path, "duration": duration, "mode": mode})


@mcp.tool()
def list_graphics() -> str:
    """Motion graphic types and their fields."""
    return json.dumps(graphics.catalog())


@mcp.tool()
def add_graphic(project_id: str, type: str, word_id: int, duration: float = 0, title: str = "", subtitle: str = "",
                value: str = "", prefix: str = "", suffix: str = "", label: str = "", labels: list[str] | None = None,
                values: list[float] | None = None, items: list[str] | None = None, text: str = "", attribution: str = "",
                handle: str = "", number: int | None = None) -> str:
    """Motion graphic at a word: lower_third (title, subtitle), counter (value, prefix, suffix, label),
    bar_chart (title, labels, values), chapter_card (title, number), quote_card (text, attribution),
    checklist (title, items), end_card (text, handle; always placed at the end). Only use numbers the speaker said."""
    cmd = {"op": "add_graphic", "type": type, "word_id": word_id, "title": title, "subtitle": subtitle, "value": value,
           "prefix": prefix, "suffix": suffix, "label": label, "labels": labels, "values": values, "items": items,
           "text": text, "attribution": attribution, "handle": handle, "number": number}
    if duration:
        cmd["duration"] = duration
    return _run(project_id, {k: v for k, v in cmd.items() if v not in (None, "")})


@mcp.tool()
def remove_graphic(project_id: str, graphic_id: str) -> str:
    """Remove a motion graphic by id (see get_state)."""
    return _run(project_id, {"op": "remove_graphic", "graphic_id": graphic_id})


@mcp.tool()
def auto_pace(project_id: str, level: str = "balanced") -> str:
    """Pattern interrupts: subtle camera moves wherever a shot holds too long. calm (6s), balanced (4s), fast (2.6s)."""
    return _run(project_id, {"op": "auto_pace", "level": level})


@mcp.tool()
def preflight(project_id: str, platform: str = "reels") -> str:
    """Checks before export (hook, length, caption safe zone, loudness, long holds, licences, end card), with fixes."""
    return json.dumps(recipes.preflight(Project.load(project_id), platform), ensure_ascii=False)


@mcp.tool()
def undo(project_id: str) -> str:
    """Undo the last edit."""
    label = Project.load(project_id).undo()
    return f"Undid {label}" if label else "Nothing to undo"


@mcp.tool()
def render(project_id: str, quality: str = "preview") -> str:
    """Render the vertical video. quality: preview (540x960, fast) or final (1080x1920)."""
    p = Project.load(project_id)
    out = render_mod.render(p, quality)
    return json.dumps({"video": str(out), "captions_srt": str(p.dir / "renders" / "captions.srt"),
                       "duration": commands.state(p, with_words=False)["summary"]["after"]})


@mcp.tool()
def make_post_kit(project_id: str) -> str:
    """Cover, 4:5 carousel (JPGs + PDF), 3 story frames and the caption, in the same look. Render first for best frames."""
    p = Project.load(project_id)
    kit = repurpose.post_kit(p)
    return json.dumps({"folder": str(p.dir / "post"), **kit}, ensure_ascii=False)


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
