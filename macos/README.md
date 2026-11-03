# ClipForge for Mac

A native SwiftUI app over the ClipForge engine. It looks and behaves like a Mac app (sidebar library, drag and drop,
AVKit preview, menus and shortcuts, Keychain, Settings window) and uses the same engine that Claude drives over MCP,
so every feature works the same in the app, in the Studio web page, and in Claude.

## Install

Requirements: macOS 14 or later, ffmpeg and Python 3.10+ (`brew install ffmpeg python`).

1. Download **[ClipForge.zip](https://github.com/ebenezar15/Video/releases/download/mac-latest/ClipForge.zip)**
   (always the latest build that passed CI), or build it yourself (below).
2. Unzip and move **ClipForge.app** to Applications. The build is ad-hoc signed, not notarised, so macOS blocks the
   first launch. Run once in Terminal:

   ```bash
   xattr -dr com.apple.quarantine /Applications/ClipForge.app
   ```

   or open it, then go to System Settings → Privacy & Security → **Open Anyway**.
3. On first launch, press **Install Engine**. ClipForge creates a private Python environment in
   `~/Library/Application Support/ClipForge` and installs the engine bundled inside the app. This takes a few
   minutes once.

If you already installed the engine with `pip install --prefer-binary --only-binary av,ctranslate2,onnxruntime,tokenizers,opencv-python-headless -e engine[all]`, the app finds `clipforge` on your PATH and
skips the install. You can also set a custom engine path in **Settings → Engine**.

## Use

| | |
|---|---|
| **New video** (⌘N) | Pick how it was shot, then drop a video or choose one. |
| **01 Cut** | Transcribe on this Mac, Auto Cut, click words to cut or restore, “Open with this” for a cold-open hook. |
| **02 Style** | Recipes, frame shape, five looks, captions, smart pop-ups, 30 effects, motion graphics, B-roll, pacing. |
| **03 Sound** | Mood music (preview, use), your own track, sound effects, loudness. |
| **04 Finish** | Pre-flight with Fix buttons, render preview/final, post kit (cover, carousel, stories, caption). |
| **Ask Claude** (⌘K) | Describe the edit; review Claude's changes one by one; apply. Needs an Anthropic API key in Settings. |
| **Brand** | Name, handle, call to action, hashtags, colours, fonts. Saved once for every video. |
| Shortcuts | ⌘R render preview · ⇧⌘R render final · ⌥⌘Z undo last edit · ⌘1–⌘4 steps |

**Use your Claude subscription instead of an API key:** Settings → Claude → **Add ClipForge to Claude Desktop**
(merges into `claude_desktop_config.json` and keeps a `.bak`), or copy the Claude Code command.

## Build

```bash
cd macos
swift test                     # ClipForgeCore unit tests
./scripts/build-app.sh         # build/ClipForge.app and build/ClipForge.zip
```

Set `SIGN_ID="Developer ID Application: …"` to sign for distribution; notarise with `xcrun notarytool`.

Self-test against the real engine (what CI runs):

```bash
python ../engine/tests/fixtures/make_fixture.py /tmp/fx
CLIPFORGE_SELFTEST_VIDEO=/tmp/fx/talk.mp4 CLIPFORGE_SELFTEST_WORDS=/tmp/fx/talk.words.json \
  ./build/ClipForge.app/Contents/MacOS/ClipForge --selftest --screenshots build/screenshots
```

## Layout

```
Sources/ClipForgeCore/   Foundation only: Models, JSONValue, EngineClient, EngineProcess, ClaudeDesktop
Sources/ClipForge/       SwiftUI: Main (app + menus), AppModel, RootView (sidebar, home, setup, brand),
                         ProjectView (player, Ask Claude, plan sheet), Steps (Cut/Style/Sound/Finish),
                         SettingsView, Support (Keychain, FlowLayout, components), SelfTest
Tests/                   ClipForgeCore tests
scripts/                 build-app.sh, make_icon.py
```

The app starts the engine with `clipforge studio --port 0`, reads the port from its first line, and talks to it over
`127.0.0.1`. Every edit is an engine command, so undo, Claude and the Studio web page all see the same history.
