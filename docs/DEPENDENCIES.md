# Dependencies

| Package | Version tested | Licence | Why |
|---|---|---|---|
| ffmpeg (system) | 6.1 (Linux), 8.x (Homebrew) | LGPL/GPL depending on build; invoked as a separate process | All decoding, filtering, encoding. Uses libass captions when the build has them; otherwise (Homebrew) captions are drawn with Pillow. ffmpeg 7+ reads the filter graph via `-/filter_complex` |
| Pillow | 12.3 | MIT-CMU (HPND) | Cards, motion-graphic frames, post kit |
| numpy | 2.5 | BSD-3 | Music and SFX synthesis |
| pydantic | 2.x | MIT | Structured output schema for the Claude planner |
| anthropic | 2.3 | MIT | Ask Claude (Messages API, structured outputs, refusal fallbacks) |
| mcp | 2.3 | MIT | MCP server (`MCPServer`) |
| faster-whisper (optional) | 1.x | MIT | On-device transcription with word timestamps |
| opencv-python-headless (optional) | 4.14 | Apache-2.0 | Face detection for pop-up placement. Pinned below 5: OpenCV 5 removed the Haar cascades |

Fonts: the looks prefer Inter, Caladea, JetBrains Mono (all OFL) and fall back to DejaVu/Liberation. Users can point
the brand at any font file they are licensed to use.

No GPL Python dependencies. Ship ffmpeg as an external binary so its licence stays separate.
