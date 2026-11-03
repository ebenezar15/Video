# Changelog

## 0.3.3 — Real-world fixes (2026-11-03)
- Long recordings: many cuts render in one select pass per in-order run (work grows linearly, not frames × cuts);
  cut points snap to the 30 fps grid so audio and video stay in sync across hundreds of cuts.
- Transcripts that run past the end of the video no longer produce negative segments or empty renders.
- iPhone footage: portrait videos (rotation flag) are measured as shown; HDR (HLG/PQ) is tone-mapped to SDR.
- Security: the local engine rejects requests from other websites (Origin) and DNS rebinding (Host).
- Transcription reports progress; CI transcribes real speech (macOS `say`) with Whisper through the Mac app.

## 0.3.2 — Install fix (2026-11-03)
- Fix "Failed to build 'av'": installs use ready-made builds only (`--prefer-binary --only-binary av,ctranslate2,…`),
  so pip picks a compatible PyAV instead of compiling the newest one (e.g. PyAV 15.1 on macOS 13).
- Mac app installs in stages: core engine first, then transcription and face detection as optional parts; a missing
  part no longer blocks the app, and Settings/Cut say what is missing and how to add it. Prefers Python 3.12.

## 0.3.1 — Mac app ships (2026-11-02)
- Downloadable build: https://github.com/ebenezar15/Video/releases/download/mac-latest/ClipForge.zip (CI on macOS 14
  builds, unit-tests, self-tests against the real engine, renders every screen, then publishes).
- Fixes found on macOS: SwiftUI views made main-actor; AVPlayerView replaces SwiftUI VideoPlayer (crashed in SwiftPM
  builds); ffmpeg 7+ `-/filter_complex`; Pillow captions when ffmpeg lacks libass (Homebrew); copy fonts by contents
  (protected system fonts).

## 0.3.0 — Native Mac app (2026-11-02)
- `macos/`: SwiftUI app over the engine. Sidebar library, drag-and-drop import, Cut/Style/Sound/Finish, Ask Claude
  with per-change review, AVKit preview, brand editor, Settings (Keychain keys, one-click Claude Desktop MCP setup).
- First-run engine install into a private venv from the source bundled in the app; engine runs on a free port.
- `--selftest` runs a full edit against the real engine and renders every screen to PNG; CI on macOS builds the app.

## 0.2.0 — Claude-driven engine (2026-11-02)
- Redesign from two reference videos (`docs/REFERENCE_VIDEOS.md`): Claude edits, the engine renders.
- `engine/`: Python + ffmpeg engine with Studio web app, MCP server, CLI and Claude Code skill.
- Auto-cut (fillers, retakes, pauses), edit by words, cold-open hooks, hook titles.
- 5 looks, brand kit, 4 frame shapes, animated karaoke captions with emphasis.
- Smart pop-ups with face-aware placement; 30 effects; 7 motion graphics.
- Generated mood music (licence-free) and SFX, ducking, −14 LUFS; B-roll from library or Pexels.
- Pacing engine, 5 professional recipes, pre-flight with fixes, post kit (cover, carousel + PDF, stories, caption).
- 27 tests render every effect, graphic, look, aspect and shot type.

## 0.0.1 — Design package (2026-10-30)
- Market research with sources (`docs/RESEARCH.md`)
- Product design with 12 signature features (`docs/PRODUCT.md`)
- Architecture, TimelineDocument v1, provider protocols (`docs/ARCHITECTURE.md`, `schemas/timeline.v1.json`)
- Phased roadmap with tickets and 5 open decisions (`docs/ROADMAP.md`)
- Clickable UI prototype (`prototype/index.html`): Library, Moments, Triage, Editor + ⌘K Director Chat, Hook Lab, Pre-flight
