"""Ask Claude: a plain-language request becomes a list of ClipForge commands you can accept or reject."""
from __future__ import annotations

import json
import os
from typing import Literal

from pydantic import BaseModel, Field

from .commands import DOCS, state, transcript_text
from .effects import catalog
from .audio_gen import MOODS
from .looks import LOOKS
from .recipes import RECIPES
from .project import Project

MODEL = os.environ.get("CLIPFORGE_MODEL", "claude-opus-5-5")

Op = Literal["cut_words", "restore_words", "auto_cut", "set_pause_max", "set_hook_title", "move_hook", "clear_hook_move",
             "set_look", "set_captions", "auto_popups", "add_popup", "remove_popup", "add_effect", "remove_effect",
             "set_loudness", "set_fit", "set_post_copy", "set_music_mood", "set_sfx", "set_aspect", "auto_broll",
             "add_graphic", "remove_graphic", "auto_pace", "apply_recipe"]


class PlanCommand(BaseModel):
    op: Op
    why: str = Field(description="One short sentence the user will read before accepting this change")
    ids: list[int] | None = None
    start_id: int | None = None
    end_id: int | None = None
    word_id: int | None = None
    text: str | None = None
    look: Literal["editorial", "bold", "creator", "soft", "paper"] | None = None
    name: str | None = Field(default=None, description="effect name for add_effect")
    kind: Literal["number", "keyword", "image"] | None = None
    duration: float | None = None
    seconds: float | None = None
    words_per_line: int | None = None
    position: float | None = None
    popup_id: str | None = None
    effect_id: str | None = None
    lufs: float | None = None
    fit: Literal["fill", "blur"] | None = None
    title: str | None = None
    slides: list[str] | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    mood: Literal["uplifting", "focus", "cinematic", "tech", "warm"] | None = None
    intensity: float | None = None
    enabled: bool | None = None
    aspect: Literal["9:16", "4:5", "1:1", "16:9"] | None = None
    type: Literal["lower_third", "counter", "bar_chart", "chapter_card", "quote_card", "checklist", "end_card"] | None = None
    subtitle: str | None = None
    value: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    label: str | None = None
    labels: list[str] | None = None
    values: list[float] | None = None
    items: list[str] | None = None
    attribution: str | None = None
    handle: str | None = None
    number: int | None = None
    graphic_id: str | None = None
    recipe: Literal["thought_leader", "founder_story", "explainer", "podcast_clip", "product_demo"] | None = None
    level: Literal["calm", "balanced", "fast"] | None = None
    animation: Literal["pop", "bounce", "rise", "none"] | None = None
    emphasis: Literal["auto", "none"] | None = None


class Plan(BaseModel):
    summary: str
    commands: list[PlanCommand]


SYSTEM = """You are the editor inside ClipForge, a short-form video editing engine. The user talks; you edit by
emitting ClipForge commands. You never write code. You only choose commands from the list below, with word ids
taken from the transcript. Keep the speaker's meaning intact: never cut a word that would change what they said.
Cutting a word removes it from the video. The audience is professional: aim for content that earns attention
without gimmicks. A good short opens on its strongest line (a hook title or a cold open), keeps one idea per
sentence, changes the picture every few seconds (auto_pace), and lands visual beats on the words that matter:
counters for real numbers the speaker says, a bar chart only for numbers that compare, a lower third for the
speaker's name, a checklist for steps, a quote card for the one line worth screenshotting, an end card with the
call to action. At most one pop-up every 4 seconds. Never invent numbers or claims the speaker did not make.

Commands:
{ops}

Effects: {effects}
Looks: {looks}
Recipes: {recipes}
Music moods: {moods}"""


def context(p: Project) -> str:
    st = state(p, with_words=False)
    keep = {k: st[k] for k in ("shot_type", "look", "aspect", "hook", "captions", "pause_max", "popups", "effects",
                               "cutaways", "graphics", "music", "sfx", "summary")}
    return f"Current edit:\n{json.dumps(keep, ensure_ascii=False)}\n\nTranscript (id:word, ~~removed~~):\n{transcript_text(p)}"


def to_command(c: PlanCommand) -> dict:
    d = {k: v for k, v in c.model_dump().items() if v is not None and k != "why"}
    if c.op == "set_hook_title" and "text" not in d:
        d["text"] = c.title or ""
    return d


def plan(p: Project, request: str, client=None) -> dict:
    """Returns {summary, commands:[{...command, why}]} without applying anything."""
    if not p.words:
        raise ValueError("Transcribe the video first so Claude can read it.")
    import anthropic

    client = client or anthropic.Anthropic()
    system = SYSTEM.format(
        ops="\n".join(f"- {k}: {v}" for k, v in DOCS.items() if k in PlanCommand.model_fields["op"].annotation.__args__),
        effects=", ".join(f"{e['name']} ({e['about']})" for e in catalog()),
        looks=", ".join(f"{k} ({v['about']})" for k, v in LOOKS.items()),
        recipes=", ".join(f"{k} ({v['about']})" for k, v in RECIPES.items()),
        moods=", ".join(f"{k} ({v['about']})" for k, v in MOODS.items()))
    resp = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"{context(p)}\n\nRequest: {request}"}],
        output_format=Plan,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request.")
    parsed: Plan | None = resp.parsed_output
    if parsed is None:
        raise RuntimeError(f"Claude returned no plan (stop_reason={resp.stop_reason}).")
    return {"summary": parsed.summary, "model": resp.model,
            "commands": [{**to_command(c), "why": c.why} for c in parsed.commands]}
