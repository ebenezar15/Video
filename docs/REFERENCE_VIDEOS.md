# Reference videos and what ClipForge took from them

Analysed 2026-11-02. Captions and on-screen text were extracted with Apify (instagram-scraper and an Instagram
transcript/OCR actor). Direct fetches of instagram.com were blocked by this environment's network policy.

## 1. @sadiyagram: "My Claude editing engine" (carousel of ten 7-second clips)

Caption: an AI-powered editing system with 36 effects, 5 looks and word-by-word editing, built with Claude.

| Slide | What it shows | ClipForge |
|---|---|---|
| 01 What it is | Drop in a video, get a finished reel in my look; 4-hour edits → 4 min | `clipforge auto`, Studio home |
| 02 Drop it in | New video; pick how it was shot: me on camera, voice-over clips, faceless (animated), clips + text; start with a hook | 4 shot types, hook title |
| 03 Auto cut | Pauses over 0.4 s, um/uh/erm, retakes gone; keeps the best take and the line that hooks (3:43 → 0:46) | `auto_cut` (0.4 s default, keeps last take) |
| 04 Edit by reading | Video as a page of words; click a word to cut, click again to restore; move the hook | Cut step, `move_hook` |
| 05 Your brand | Colours, fonts, captions and title style saved once | `brand.json`, `set_brand` |
| 06 Smart pop-ups | A place → a photo, a number → big number, a product → its picture; max 1 every 4 s; never on the face | `auto_popups` with face-aware placement |
| 07 Effects | 36 one-tap effects: orbiting pictures, glass widgets, Pinterest stickers, paper tear, curtain, scene changes | 30 effects including orbit, glass widget, sticker, paper tear, curtain |
| 08 5 looks | Editorial, bold, creator, soft, paper; captions stay at the bottom; your colours | Same five looks; captions drawn last so zooms never move them |
| 09 Every post | One reel → cover, carousel, story frames, post caption | `make_post_kit` |
| 10 CTA | Comment "EDIT" | n/a |

## 2. @ctrl_plus_u: "Left side raw, right side edited" (58-second ad, Tamil/English)

Claims Claude edits raw footage end to end (cuts, captions, zoom, B-roll, music) in the creator's style, sold as a
₹199 kit with the Claude subscription paid separately.

| Idea | ClipForge |
|---|---|
| Claude does the whole edit, no editor | MCP server + skill: Claude drives every step through commands |
| Uses your existing Claude subscription | MCP path needs no API key |
| Cuts, captions, zoom, B-roll, music | auto-cut, karaoke captions, camera effects and pacing, B-roll cutaways, mood music |
| "In your style" | Brand kit + looks + recipes |
| Tamil speech | Whisper handles Tamil and other languages; set a Tamil-capable caption font in the brand |

## Where ClipForge goes further

- Motion graphics that carry information (counting stats, bar charts, checklists, quote cards, lower thirds).
- Licence-free music generated to the exact length, plus sound effects placed on every visual beat.
- A pacing engine that guarantees a visual change every few seconds.
- Professional recipes and a pre-flight check (hook, length, safe zones, loudness, licences, end card).
- Every edit is undoable and reviewable: Claude proposes, you accept per change.
