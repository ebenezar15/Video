# ClipForge engine

Drop in a talking video and get back a finished short in your look, edited by Claude. Everything renders on your
computer with ffmpeg. Claude is the editor: through MCP (Claude Desktop or Claude Code, on your own subscription) or
the **Ask Claude** box in the Studio (Anthropic API key).

## What it does

| Area | Features |
|---|---|
| **Cut** | Transcribe on-device with word timings · auto-cut ums, retakes (keeps the last take) and pauses over 0.4 s · edit by clicking words · cold-open hook · hook title |
| **Look** | 5 looks (editorial, bold, creator, soft, paper) · brand kit saved once (colours, fonts, handle, CTA) · 4 frame shapes (9:16, 4:5, 1:1, 16:9) |
| **Captions** | Word-by-word karaoke · pop / bounce / rise animation · numbers and names in your accent colour · SRT sidecar |
| **Smart pop-ups** | Numbers become big-number cards, names and places become cards or your photos · max one per 4 s · placed away from your face (OpenCV) |
| **Motion graphics** | Lower third · counting stat · bar chart · chapter card · quote card · checklist · end card (eased animation, any font or script) |
| **Effects** | 30 one-tap effects: zoom punch, push-in, whip zoom, shake, Ken Burns, glitch, VHS, grain, light leak, orbiting pictures, glass widget, sticker, curtain, paper tear, colour wipe, letterbox and more |
| **B-roll** | Cutaways matched to what you say from your library (files named after what they show) · Pexels search with `PEXELS_API_KEY` · full frame or picture-in-picture · Ken Burns on photos |
| **Music & sound** | Mood music generated on your computer to the exact length (uplifting, focus, cinematic, tech, warm), no licence needed · or your own tagged library · ducked under speech · SFX (whoosh, pop, ding, riser, impact) auto-placed on transitions, pop-ups and graphics · −14 LUFS loudness |
| **Retention** | Pacing engine adds subtle camera moves wherever a shot holds too long, on the beat · 5 professional recipes (thought leader, founder story, explainer, podcast clip, product demo) · pre-flight check with one-click fixes |
| **Every post** | Cover, 4:5 carousel (JPGs + PDF), 3 story frames and the caption, all in the same look · licence report |
| **Shot types** | Me on camera · voice-over on clips · faceless (animated background, big text) · clips + text |

## Install

Needs Python 3.10+ and ffmpeg (with libass, which most builds have).

```bash
brew install ffmpeg            # macOS; or apt install ffmpeg
```

```bash
pip install -e "./engine[all]"  # faster-whisper for transcription, OpenCV for face-aware pop-ups
```

## Use it

**Studio** (local web app):

```bash
clipforge studio
```

Then open http://127.0.0.1:8765. Set `ANTHROPIC_API_KEY` to use the Ask Claude box.

**With Claude Desktop or Claude Code** (your subscription, no API key): see [`docs/MCP.md`](../docs/MCP.md), then say
*"Edit ~/Movies/talk.mov into a LinkedIn clip in my brand."* The skill in `skill/clipforge-editor/` tells Claude Code
the editing playbook.

**Headless, one command:**

```bash
clipforge auto talk.mov --recipe thought_leader --hook "How we grew 40% in 90 days"
```

Other commands: `clipforge new | transcribe | edit | render | post | preflight | list | mcp`.

## Where things live

`~/ClipForge` (or `CLIPFORGE_HOME`):

```
brand.json                 your brand, used by every project
broll/                     your B-roll library (name files after what they show: city-skyline.mp4)
music/ + library.json      your licensed tracks tagged by mood (optional)
projects/<id>/             media/, words.json, edit.json (every edit), history.json (undo),
                           renders/ (mp4, captions.srt, licenses.txt, timeline.json), post/ (kit)
```

## How it fits together

```
Claude (MCP / Ask Claude) ─┐
Studio UI ─────────────────┼─► commands.apply()  ── undoable edits in edit.json
CLI ───────────────────────┘          │
                                       ▼
transcript + edit + look + brand ─► render.py ─► one ffmpeg pass:
  trims → reframe → camera (zoom/shake) → B-roll → grade → effects → pop-ups → motion graphics
  → captions (libass) ; voice + ducked music + SFX → loudnorm
```

Claude never writes code. It reads the transcript (`id:word` per line) and emits commands such as
`{"op": "add_graphic", "type": "counter", "word_id": 14, "value": "40", "suffix": "%"}`, which you accept or
reject one by one.

## Tests

```bash
cd engine && python -m pytest
```

27 tests build a synthetic clip, then render every effect, graphic, look, aspect and shot type, and check the
Claude planner, MCP server and Studio API with no network.

## Limits, honestly

- Transcription runs `faster-whisper`; the first run downloads the model (~500 MB for `small`).
- The generated music is simple and clean (pads, bass, arpeggio, light drums). For a signature sound, tag your own
  licensed tracks in `music/library.json`.
- Pop-ups and B-roll matching use simple rules. Claude makes the editorial calls when you ask it.
