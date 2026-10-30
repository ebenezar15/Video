# ClipForge — Roadmap

Each phase ends with a runnable app, passing tests, and a demo note in `CHANGELOG.md`. Ticket IDs: `P<phase>-<n>`. ★ marks a signature feature from `PRODUCT.md`.

## Phase 1 — Foundation
- P1-1 XcodeGen `project.yml`, SPM packages per module, strict concurrency, CI script (`scripts/ci.sh`)
- P1-2 `Core/Timeline`: model types, Codable, `schemas/timeline.v1.json` validation, `EditCommand` + undo/redo
- P1-3 `Core/Media`: import (drag/drop, open panel), SHA-256 hashing, metadata, thumbnails, waveform
- P1-4 Proxy generation (HEVC 720p) as a background job with progress and cancel
- P1-5 App shell: sidebar (Library / Projects / Templates / Models / Settings), Library grid, player with J/K/L scrubbing
- P1-6 `.clipforge` package save/open plus atomic autosave
- P1-7 `scripts/make-fixtures.sh` (FFmpeg test sources) and the first golden-frame test
**Done when:** import → scrub smoothly → save → reopen.

## Phase 2 — Basic editor + export
- P2-1 Timeline canvas (AppKit-backed): tracks, clips, razor (B), trim, ripple, magnetic snapping
- P2-2 `CompositionBuilder` (EDL → AVComposition) and Metal compositor v1 (transform, crop, blur-fill)
- P2-3 Canvas aspects 9:16 / 1:1 / 4:5 / 16:9 with phone-frame preview and safe-zone overlays
- P2-4 Export presets (Shorts, Reels, TikTok, LinkedIn, X, custom) with a VideoToolbox HEVC/H.264 batch queue
**Done when:** manually cut a 9:16 short and export it.

## Phase 3 — Offline analysis
- P3-1 `AnalysisPipeline` actor: stage graph, content-hash cache, pause/resume, progress UI
- P3-2 Transcription: SpeechAnalyzer (macOS 26) / WhisperKit fallback, word timestamps
- P3-3 Diarization (local), punctuation cleanup, filler/silence map
- P3-4 Shot/scene detection, faces and subject tracks (Vision), saliency
- P3-5 Transcript pane synced to playback; **text-based editing** (delete words → `Cut` commands)
**Done when:** the transcript is shown and synced, and text editing cuts the video.

## Phase 4 — Captions & typography
- P4-1 Caption renderer (Core Text → Metal texture atlas) shared by preview and export
- P4-2 20 style presets with safe-zone awareness; karaoke highlight; 1–3 words per line
- P4-3 Kinetic text animations (typeOn, bounce, slide, scalePop, wave), title cards, lower thirds
- P4-4 Bundled OFL fonts and a licence registry
**Done when:** styled animated captions match between preview and export (golden test).

## Phase 5 — Shorts generator + scoring ★
- P5-1 `FactorScorer` (hook, payoff, energy, visual, pacing) with reasons
- P5-2 ★ **Context Guard**: completeness check plus fixes (extend, context card, splice setup)
- P5-3 Auto-reframe: follow-speaker / split-screen / blur-fill, smoothed virtual camera; ★ **Speaker Stage** rules
- P5-4 Silence and filler removal with an aggressiveness slider and jump-cut smoothing
- P5-5 **Moments** screen: ranked list, score breakdown, one click opens a draft in the editor
- P5-6 ★ **Retention Forecast** v1 (heuristic) with dead-zone markers and fixes
- P5-7 ★ **Loop Finder**
**Done when:** one click → 5 ranked, reframed, captioned drafts, each with a score explanation.

## Phase 6 — Provider layer + Claude
- P6-1 `ProviderRouter`, routing modes, Keychain, ★ upload manifest dialog, Airplane mode with a `URLProtocol` guard test
- P6-2 Adapters: Foundation Models, MLX Swift, Ollama/LM Studio, Anthropic (tool use, vision, prompt caching)
- P6-3 Model Manager (download, verify checksum, size/RAM, delete, set default)
- P6-4 Jobs panel showing provider, local/cloud, time, tokens and cost
**Done when:** the same feature runs offline or with Claude, switched by a setting.

## Phase 7 — Director Chat (prompt-to-edit) ★
- P7-1 ⌘K command bar plus voice dictation
- P7-2 Agent tool loop over `EditCommand`s and query tools; schema validation and repair loop
- P7-3 Visual diff (before/after timeline + preview) with per-change accept/reject
- P7-4 Recipe library (save prompts)
**Done when:** "Add zoom cuts on punchlines and yellow captions" works end-to-end.

## Phase 8 — Effects, transitions, color
- P8-1 Data-driven Metal effect presets (zoom punch, shake, glitch, VHS, grain, blur, vignette, chromatic aberration, speed ramp, freeze, background removal)
- P8-2 Transitions (dissolve, whip, zoom, slide, spin, luma, glitch) and match-cut suggestions
- P8-3 Color panel, wheels, curves, HSL, `.cube` LUTs, auto-correct, auto-match, scopes, HDR→SDR
- P8-4 Keyframe editor with easing curves
**Done when:** golden-frame tests pass for every preset.

## Phase 9 — Audio
- P9-1 Mixer, auto-ducking, per-platform LUFS normalisation, noise reduction, voice enhance
- P9-2 Music library with licence metadata; local or cloud music generation adapter
- P9-3 SFX library with auto-placement and an intensity slider
- P9-4 Beat detection; snap cuts and effects to beats
**Done when:** exported audio hits the target LUFS and cuts land on beats.

## Phase 10 — B-roll
- P10-1 B-roll slot detection from transcript nouns and topics
- P10-2 Source priority chain: library → local folder → Pexels/Pixabay → generative
- P10-3 Local image generation plus Ken Burns/parallax; cloud video-gen adapter
**Done when:** the agent inserts relevant B-roll with licence metadata.

## Phase 11 — Templates, brand & Style DNA ★
- P11-1 Templates (partial EDL + StyleProfile + slots), `.cftemplate` import/export
- P11-2 Layouts: full, split, PiP, podcast two-up, screen + face-cam, quote card, listicle
- P11-3 Brand kit plus ★ **Brand Memory** defaults
- P11-4 ★ **Style DNA** from a reference video with a match-strength slider
- P11-5 ★ **Hook Lab**: variant generation and synchronized side-by-side scroll test
**Done when:** applying a reference's style visibly matches its pacing, captions and color.

## Phase 12 — Carousels & Moment Board ★
- P12-1 Key-idea extraction, frame selection (sharpness + face + saliency), slide copy
- P12-2 Layout engine (minimal, bold, quote, step-by-step, stat); PNG/PDF export plus caption and hashtags
- P12-3 ★ **Moment Board** canvas: cross-library moments, clustering, lasso → supercut / series / carousel
**Done when:** a video produces an editable 8–10 slide carousel, and a supercut can be built from 3 videos.

## Phase 13 — Integrations & automation ★
- P13-1 MCP server (`list_projects`, `import_video`, `analyze`, `generate_shorts`, `apply_prompt_edit`, `export`, `get_timeline`)
- P13-2 `clipforge` CLI (analyze / shorts / export)
- P13-3 Watch folders, recipes, and ★ **Triage Inbox**
- P13-4 ★ **Pre-flight Linter** with fixers
- P13-5 ★ **Taste Loop**: analytics CSV import, then the per-channel weight fit and an "audience rewards" report
- P13-6 Optional publishing/scheduling adapters (YouTube Data API, TikTok Content Posting API, Instagram Graph API), behind a setting
**Done when:** Claude Code generates and exports shorts via MCP, and Triage decisions change the ranking.

## Phase 14 — Polish & ship
- Onboarding (AI mode, model downloads, keys), accessibility pass (VoiceOver, reduced motion), localisation
- Performance pass (1 h 1080p in under 15 min offline), notarisation script, Sparkle (optional), `docs/USER_GUIDE.md`

---

## Open decisions (need your call; defaults in **bold**)
1. **Minimum OS:** **macOS 15+ with macOS 26 extras behind `#available`**, or macOS 26-only (simpler, and SpeechAnalyzer + Foundation Models are always there).
2. **Persistence:** **GRDB/SQLite** (explicit, fast, testable), or SwiftData.
3. **Publishing (P13-6):** **keep it optional and late**, or move direct posting earlier. It requires platform app review per network.
4. **Distribution:** **direct download (notarised, Sparkle)**, or Mac App Store (sandbox limits FFmpeg subprocess and folder watching).
5. **Local LLM default:** **Apple Foundation Models when available, else an MLX 7–8B instruct model (~5 GB)**, or Ollama-first.
