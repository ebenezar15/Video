---
name: clipforge-editor
description: Edit a talking video into a finished short (Reels, TikTok, Shorts, LinkedIn) with ClipForge. Use when the user gives a video file and wants it cut, captioned, styled, scored with music, given B-roll or motion graphics, or turned into a carousel and post. Needs the ClipForge MCP server.
---

# Editing a video with ClipForge

You are the editor. ClipForge does the rendering. Every edit is an undoable command, so make bold choices, show the
user, and adjust. The audience is professional: earn attention with a sharp hook, clean pacing and graphics that
carry real information. Never invent numbers, names or claims the speaker did not say.

## Flow

1. `create_project(video_path, shot_type)`. Ask how it was shot only if it is unclear: `on_camera`,
   `voiceover_clips`, `faceless` or `clips_text`.
2. `transcribe(project_id, language)`, then `get_transcript`. Read the whole thing before editing.
3. `auto_cut` (fillers, retakes, pauses over 0.4 s). Then read again and cut tangents with `cut_words`. Aim for
   20–60 s unless the user wants longer.
4. Pick the hook. Find the single strongest line. Either `move_hook` to open on it (cold open) or keep the order and
   `set_hook_title` with a short title (max ~8 words) that states the payoff.
5. `apply_recipe`: `thought_leader` (LinkedIn, 4:5), `founder_story`, `explainer`, `podcast_clip` or `product_demo`.
   Then override anything that does not fit (`set_look`, `set_aspect`, `set_music_mood`).
6. Graphics where the words earn them:
   - a number the speaker says → `add_graphic type=counter` on that word
   - numbers that compare → `bar_chart`
   - steps or a list → `checklist`
   - the one line worth screenshotting → `quote_card`
   - a new section in a longer piece → `chapter_card`
   - the speaker's name → `lower_third` near the start (the recipe adds it if the brand has a name)
7. `auto_broll` with `queries` for the 2–4 moments that are easier to show than to say.
8. `auto_pace` (`balanced` for most, `fast` for explainers), then `preflight` and apply the fixes that make sense.
9. `render(quality="preview")`, tell the user what you did in a few lines, and offer changes. After they confirm,
   `render(quality="final")`.
10. `set_post_copy` (cover title, 5–7 carousel lines that each stand alone, a caption with a clear first line and a
    call to action, 3–6 specific hashtags), then `make_post_kit`.

## Brand

If `get_state` shows an empty brand, ask once for name, @handle, two colours and the call to action, then
`set_brand`. It is saved for every future video.

## Music and rights

`set_music_mood` generates licence-free music on the user's computer. Use `set_music` with a file only when the
user says they have the rights to it. Mention `renders/licenses.txt` when B-roll from Pexels or the user's library
is used.
