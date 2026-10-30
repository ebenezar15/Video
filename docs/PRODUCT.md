# ClipForge — Product Design

> **One line:** a local-first Mac studio that turns long videos into shorts and carousels that actually make sense, explains *why* each clip should work, and gets smarter from your real results.

## 1. Personas

| Persona | Job to be done | What they hate today |
|---|---|---|
| **Podcaster** (2–3 hosts, weekly 90 min) | 8–12 clips per episode, speaker-aware layouts | Clips that cut off the setup; manual split-screen |
| **Educator / course creator** | Turn lessons into hooks and carousels | Generic captions; losing the explanation |
| **Agency editor** (many clients) | Batch drafts in each client's brand, private footage | Cloud uploads of client media, per-seat credits |
| **Solo creator** | Daily posting from one long video a week | Time spent; guessing what will perform |

## 2. Core loop

```
 Import ─▶ Understand ─▶ Moments ─▶ Triage ─▶ Polish ─▶ Pre-flight ─▶ Export/Publish ─▶ Learn
   ▲                                                                                   │
   └──────────────────────── Taste Loop (analytics re-weight scoring) ◀─────────────────┘
```

## 3. Feature map

Baseline features (parity with the market) come from the build prompt §4. The **signature features** below are what make ClipForge more creative and more useful than the existing tools (see `RESEARCH.md` §3).

### 3.1 Signature features

1. **Context Guard.** Each candidate clip gets a *completeness* check from transcript + LLM: does it contain the setup a cold viewer needs? Fixes are offered: extend in-point, add a one-line context card ("Context: we're talking about pricing"), or splice the setup sentence from earlier with a jump cut.
2. **Explainable Score + Retention Forecast.** Score 0–100 split into factors (Hook, Payoff, Energy, Faces/visuals, Pacing, Context). A predicted retention curve highlights dead zones ("12–17 s: no visual change, slow speech"), each with a one-click fix such as zoom punch, B-roll, or trim.
3. **Hook Lab.** 3–5 opening variants per clip:
   - *Cold open*: move the strongest line to frame 0, then rewind.
   - *Text hook*: an LLM-written on-screen headline.
   - *Question hook*: reframe the topic as a concrete question.
   - *Pattern interrupt*: SFX + zoom + flash on frame 0.
   Variants are previewed side by side in a phone-frame "scroll test", and all of them can be exported for A/B tests.
4. **Triage Inbox.** Drafts from watch folders or channel monitoring arrive as cards. Keys: `→` keep, `←` drop, `↑` open in editor, `1-5` pick a hook variant. Every decision feeds the Taste Loop.
5. **Taste Loop.** Import analytics (YouTube/TikTok/Instagram CSV exports, or APIs when connected). ClipForge fits per-channel weights on its score factors, so ranking adapts to *your* audience. Shows a "What your audience rewards" report.
6. **Moment Board.** An infinite canvas of every scored moment across the whole library. Filter by topic, speaker, emotion, or quote. Lasso moments into a **supercut**, a **series** (Part 1/2/3 with auto "follow for part 2" CTA), or a **carousel**.
7. **Loop Finder.** Detects endings that can cut seamlessly back to the hook (matching words, matching shot) for rewatchable shorts.
8. **Pre-flight Linter.** Per-platform checks before export: safe-zone collisions, caption contrast (WCAG AA), loudness target, max duration, aspect, missing music/B-roll license, profanity flag for brand accounts. Every issue has a **Fix** button.
9. **Style DNA.** Drop a reference video and get a StyleProfile: pace, cut length, caption look, zoom habits, color, music energy. Apply it as a template, with a "match strength" slider (0–100 %).
10. **Director Chat (⌘K).** Natural-language editing that produces *typed EDL commands*, shown as a visual diff you accept per change. Voice dictation is supported too.
11. **Speaker Stage.** Podcast-aware layouts: auto split-screen when two speakers trade quickly, follow-speaker otherwise, and reaction-shot inserts on laughs.
12. **Brand Memory.** Brand kit plus remembered preferences: favourite caption style, banned words, CTA wording, emoji policy, applied by default.

### 3.2 Trust & business principles (from user complaints)
- No credits or watermarks for local processing. Cloud uses the user's own keys with a cost preview before every job.
- An **upload manifest** shows exactly which frames, audio, or text leave the Mac. Airplane mode is a hard switch.
- Licenses are tracked per asset and shown at export.

## 4. Key screens

| Screen | Purpose |
|---|---|
| **Home / Library** | Video grid with analysis status rings, transcript search, watch-folder status |
| **Moments** | Ranked clips for a video: score breakdown, retention forecast, Context Guard status |
| **Triage** | Full-screen card queue in a phone frame, driven from the keyboard |
| **Editor** | Preview (phone frame + safe zones), multi-track timeline, transcript pane, inspector tabs |
| **Hook Lab** | Variant grid with synchronized playback |
| **Moment Board** | Canvas of all moments with clustering by topic |
| **Carousel Studio** | Slide strip, layout picker, copy editor, brand kit |
| **Export & Pre-flight** | Platform presets, lint results, batch queue, sidecars |
| **Models & Providers** | Local model manager, API keys, routing mode, usage/cost |

The clickable prototype in `prototype/index.html` shows Library, Moments, Triage, Editor (with ⌘K), Hook Lab and Pre-flight.

## 5. Success metrics
- 1-hour 1080p video → ranked drafts in under 15 min fully offline on an M-series Mac.
- At least 70 % of top-5 drafts are kept in Triage after 2 weeks of Taste Loop learning.
- Draft to export takes under 2 minutes for a kept clip.
- Zero network calls while Airplane mode is on (verified by a test).
