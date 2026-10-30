# ClipForge — notes for Claude Code

Native macOS (Swift 6 / SwiftUI) AI video repurposing studio. **Status: design phase.** Docs, schema and a clickable HTML prototype exist. Phase 1 code starts after the open decisions in `docs/ROADMAP.md` are approved.

## Read first
- `docs/PRODUCT.md`: personas, signature features, screens
- `docs/ARCHITECTURE.md`: modules, data flow, EDL, provider protocols
- `docs/ROADMAP.md`: phases, tickets, open decisions
- `docs/RESEARCH.md`: market research and sources
- `schemas/timeline.v1.json`: the EDL contract (everything reads and writes it)

## Commands
- Prototype: open `prototype/index.html` in a browser (no build step).
- Build/test (from Phase 1, macOS only): `xcodegen && xcodebuild -scheme ClipForge test`

## Conventions
- All timeline mutations go through `EditCommand` (undoable). AI emits commands, never code.
- Heavy work stays off the main actor; expose `AsyncStream` progress and support cancellation.
- Each AI decision stores `reasons` and a provider stamp.
- No network in tests; Airplane mode must hold.
- Before adding a dependency, record its version and licence in `docs/DEPENDENCIES.md`. Flag GPL, non-commercial or research-only licences.
- Update `docs/CHANGELOG.md` at the end of each phase.
