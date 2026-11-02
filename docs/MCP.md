# Connect ClipForge to Claude

ClipForge ships an MCP server, so Claude Desktop, Claude Code, or any MCP client can edit your videos. It runs on your
computer and uses your Claude subscription; no API key is needed for this path.

## Claude Desktop

Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "clipforge": {
      "command": "clipforge",
      "args": ["mcp"],
      "env": { "CLIPFORGE_HOME": "/Users/you/ClipForge", "PEXELS_API_KEY": "optional" }
    }
  }
}
```

Restart Claude Desktop. If `clipforge` is not on the app's PATH, use the full path from `which clipforge`.

## Claude Code

```bash
claude mcp add clipforge -- clipforge mcp
```

To give Claude Code the editing playbook, copy the skill folder into your Claude Code skills directory:

```bash
cp -r engine/skill/clipforge-editor ~/.claude/skills/
```

## Try it

> Edit ~/Movies/talk.mov into a 40-second LinkedIn clip. Cut the ums, open on the strongest line,
> add a counter when I say the number, calm music, and make the carousel.

## Tools

| Tool | What it does |
|---|---|
| `create_project`, `list_projects` | Start from a video file; list projects |
| `transcribe`, `import_transcript_file`, `get_transcript` | On-device transcription; transcript as `id:word` lines |
| `auto_cut`, `cut_words`, `restore_words` | Remove fillers, retakes, pauses; edit by words |
| `set_hook_title`, `move_hook` | Hook title; cold open |
| `apply_recipe`, `list_recipes` | Professional presets |
| `set_look`, `list_looks`, `set_aspect`, `set_captions`, `set_brand` | Look, frame, captions, brand |
| `auto_popups`, `add_popup`, `remove_popup` | Smart pop-ups |
| `add_graphic`, `remove_graphic`, `list_graphics` | Motion graphics |
| `add_effect`, `remove_effect`, `list_effects` | 30 effects |
| `auto_broll`, `add_cutaway` | B-roll cutaways |
| `set_music_mood`, `list_music_moods`, `set_music`, `set_sfx` | Music and sound effects |
| `auto_pace`, `preflight` | Pattern interrupts; checks before export |
| `render`, `set_post_copy`, `make_post_kit`, `get_state`, `undo` | Output and housekeeping |
