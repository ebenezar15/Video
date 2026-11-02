# ClipForge — notes for Claude Code

Claude-driven short-form video studio. **Status: v0.2.** The working engine is in `engine/` (Python + ffmpeg: Studio web
app, MCP server, CLI, Claude Code skill). A native macOS shell is planned on top of it.

## Engine map (`engine/clipforge/`)
- `commands.py`: every edit op (validated, undoable). Add new features as ops here first.
- `render.py`: the single ffmpeg graph. `effects.py`, `graphics.py`, `cards.py`, `captions.py` build its pieces.
- `mcp_server.py`, `planner.py`, `server.py` + `static/studio.html`, `cli.py`: the four front doors.
- ffmpeg 6 gotchas: `drawbox` geometry is fixed at setup (animate with overlays); expressions see `t` as NaN while a
  filter configures; filters without options take `name=enable=...`.

## Read first
- `docs/PRODUCT.md`: personas, signature features, screens
- `docs/ARCHITECTURE.md`: modules, data flow, EDL, provider protocols
- `docs/ROADMAP.md`: phases, tickets, open decisions
- `docs/RESEARCH.md`: market research and sources
- `schemas/timeline.v1.json`: the EDL contract (everything reads and writes it)

## Commands
- Install: `pip install -e "./engine[all,dev]"` (needs ffmpeg with libass)
- Test: `cd engine && python -m pytest` (renders real video; ~1 min)
- Studio: `clipforge studio` → http://127.0.0.1:8765
- MCP: `clipforge mcp` (see `docs/MCP.md`)
- Design prototype: open `prototype/index.html`

## Conventions
- All timeline mutations go through `EditCommand` (undoable). AI emits commands, never code.
- Heavy work stays off the main actor; expose `AsyncStream` progress and support cancellation.
- Each AI decision stores `reasons` and a provider stamp.
- No network in tests; Airplane mode must hold.
- Before adding a dependency, record its version and licence in `docs/DEPENDENCIES.md`. Flag GPL, non-commercial or research-only licences.
- Update `docs/CHANGELOG.md` at the end of each phase.
