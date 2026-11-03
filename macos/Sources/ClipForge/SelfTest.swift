import AppKit
import ClipForgeCore
import SwiftUI

/// `ClipForge --selftest [--screenshots DIR]`
/// Starts the real engine, runs a full edit through the same client the UI uses, then (optionally) renders each
/// screen of the app to PNG. CI runs this on macOS. Needs CLIPFORGE_SELFTEST_VIDEO and CLIPFORGE_SELFTEST_WORDS.
enum SelfTest {
    static func launch(screenshots: String?) {
        setvbuf(stdout, nil, _IOLBF, 0)  // keep every line if the process dies while capturing screens
        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)
        Task { @MainActor in
            let code = await run(screenshots: screenshots)
            exit(code)
        }
        app.run()
    }

    /// `ClipForge --install-engine`: the first-run install exactly as a user gets it, then start that engine.
    static func launchInstall() {
        setvbuf(stdout, nil, _IOLBF, 0)
        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)
        Task { @MainActor in
            let code = await install()
            exit(code)
        }
        app.run()
    }

    @MainActor
    static func install() async -> Int32 {
        guard let src = AppModel.bundledEngine else {
            print("FAIL  no engine source inside the app bundle")
            return 1
        }
        guard let py = EngineProcess.findPython() else {
            print("FAIL  no Python 3.10+ found")
            return 1
        }
        print("Installing from \(src.path) with \(py.path)")
        do {
            let report = try await EngineProcess.install(engineSource: src, python: py) { line in print(line, terminator: line.hasSuffix("\n") ? "" : "\n") }
            let complete = report.missing.isEmpty && EngineProcess.lastReport()?.python == report.python
            print(complete ? "PASS  transcription and face detection installed (Python \(report.python))"
                           : "FAIL  missing optional parts: \(report.missing)")
            let engine = EngineProcess()
            defer { engine.stop() }
            let url = try await engine.start(binary: EngineProcess.venvBinary, timeout: 90)
            let meta = try await EngineClient(base: url).meta()
            let untouched = !FileManager.default.fileExists(atPath: src.appendingPathComponent("build").path)
                && ((try? FileManager.default.contentsOfDirectory(atPath: src.path)) ?? []).allSatisfy { !$0.hasSuffix(".egg-info") }
            print(untouched ? "PASS  app bundle left untouched" : "FAIL  install wrote into the app bundle")
            print("PASS  installed engine \(meta.version) runs (\(meta.effects.count) effects)")
            let current = !EngineProcess.needsUpdate(bundled: src) && report.build != nil
            print(current ? "PASS  install recorded engine build \(report.build ?? "")" : "FAIL  engine build not recorded")
            let ok = untouched && complete && current
            print(ok ? "INSTALL OK" : "INSTALL FAILED")
            return ok ? 0 : 1
        } catch {
            print("FAIL  \(error.localizedDescription)")
            print("INSTALL FAILED")
            return 1
        }
    }

    @MainActor
    static func run(screenshots: String?) async -> Int32 {
        var failures = 0
        func check(_ name: String, _ ok: Bool, _ detail: String = "") {
            print("\(ok ? "PASS" : "FAIL")  \(name)\(detail.isEmpty ? "" : "  (\(detail))")")
            if !ok { failures += 1 }
        }
        let env = ProcessInfo.processInfo.environment
        guard let video = env["CLIPFORGE_SELFTEST_VIDEO"], let words = env["CLIPFORGE_SELFTEST_WORDS"] else {
            print("FAIL  set CLIPFORGE_SELFTEST_VIDEO and CLIPFORGE_SELFTEST_WORDS")
            return 2
        }
        guard let bin = EngineProcess.engineBinary() else {
            print("FAIL  engine binary not found (set CLIPFORGE_BIN or install clipforge)")
            return 2
        }
        let home = FileManager.default.temporaryDirectory.appendingPathComponent("clipforge-selftest-\(UUID().uuidString.prefix(6))")
        let engine = EngineProcess()
        defer { engine.stop() }
        do {
            let url = try await engine.start(binary: bin, env: ["CLIPFORGE_HOME": home.path])
            check("engine starts on a free port", url.port != nil && url.port != 0, url.absoluteString)
            let c = EngineClient(base: url)
            let meta = try await c.meta()
            check("meta lists effects, looks, recipes, moods", meta.effects.count >= 30 && meta.looks.count == 5 && meta.recipes.count == 5 && meta.moods.count == 5,
                  "\(meta.effects.count) effects")
            check("shot type keys stay snake_case", meta.shotTypes["on_camera"] != nil)

            var st = try await c.createProject(video: URL(fileURLWithPath: video), shotType: "on_camera", name: "Self test")
            check("create project from path", !st.id.isEmpty)
            st = try await c.importTranscript(st.id, file: URL(fileURLWithPath: words)).state
            check("import transcript", st.transcribed && st.allWords.count > 10, "\(st.allWords.count) words")

            st = try await c.apply(st.id, ["op": "auto_cut"]).state
            check("auto cut shortens the video", (st.summary.after ?? 99) < (st.summary.before ?? 0),
                  "\(formatSeconds(st.summary.before)) → \(formatSeconds(st.summary.after))")
            check("sentences group the transcript", sentences(st.allWords).count >= 3)

            _ = try await c.setBrand(["name": "Self Test", "handle": "@selftest", "cta": "Follow for more"])
            let brand = try await c.brand()
            check("brand round-trips", brand.handle == "@selftest")

            st = try await c.apply(st.id, ["op": "apply_recipe", "recipe": "explainer"]).state
            check("recipe applies look, music and graphics", st.look == "bold" && st.music?["mood"]?.string == "tech"
                  && (st.graphics ?? []).contains { $0["type"]?.string == "end_card" })
            let wid = st.allWords.first { $0.text.contains("40") }?.id ?? st.allWords[0].id
            st = try await c.apply(st.id, ["op": "add_graphic", "type": "counter", "word_id": .number(Double(wid)),
                                           "value": "40", "suffix": "%", "label": "growth"]).state
            check("counter graphic keeps word_id", (st.graphics ?? []).contains { $0["type"]?.string == "counter" && $0["word_id"]?.int == wid })

            let issues = try await c.preflight(st.id, platform: "reels")
            check("preflight returns checks", !issues.isEmpty, issues.map(\.level).joined(separator: ","))

            let bad = try? await c.apply(st.id, ["op": "set_look", "look": "neon"])
            check("invalid command is rejected", bad == nil)

            let job = try await c.render(st.id, quality: "tiny")
            _ = try await c.wait(job: job)
            st = try await c.project(st.id)
            check("render finishes", st.renders["tiny"] != nil)
            if let r = st.renders["tiny"] {
                let (data, resp) = try await URLSession.shared.data(from: c.fileURL(st.id, r))
                check("rendered video is served", (resp as? HTTPURLResponse)?.statusCode == 200 && data.count > 10_000, "\(data.count) bytes")
            }

            let kit = try await c.postKit(st.id)
            _ = try await c.wait(job: kit)
            st = try await c.project(st.id)
            check("post kit", (st.postKit?.carousel.count ?? 0) >= 3)

            let before = st.history.count
            st = try await c.undo(st.id).state
            check("undo", st.history.count == before - 1)

            if let speech = env["CLIPFORGE_SELFTEST_SPEECH"] {
                // real on-device transcription (faster-whisper) of real speech, through the app's client
                let sp = try await c.createProject(video: URL(fileURLWithPath: speech), shotType: "on_camera", name: "Speech")
                _ = try await c.wait(job: try await c.transcribe(sp.id, language: "en", model: "tiny"))
                let heard = try await c.project(sp.id).allWords
                let text = heard.map(\.text).joined(separator: " ").lowercased()
                let ordered = zip(heard, heard.dropFirst()).allSatisfy { $0.start <= $1.start && $0.end <= $1.end + 0.01 }
                check("transcribes real speech with word timings", heard.count >= 8 && text.contains("story") && ordered,
                      "\(heard.count) words: \(text.prefix(80))")
            }

            let cfg = try ClaudeDesktop.merged(existing: Data(#"{"mcpServers":{"other":{"command":"x"}}}"#.utf8), binary: bin.path, home: home.path)
            let obj = try JSONSerialization.jsonObject(with: cfg) as? [String: Any]
            let servers = obj?["mcpServers"] as? [String: Any]
            check("Claude Desktop config keeps other servers", servers?["other"] != nil && servers?["clipforge"] != nil)

            // the functional verdict is final here; screenshots below are best-effort extras
            print(failures == 0 ? "SELFTEST OK" : "SELFTEST FAILED (\(failures))")
            if let dir = screenshots {
                await capture(client: c, meta: meta, state: st, to: URL(fileURLWithPath: dir))
                print("SCREENSHOTS DONE")
            }
        } catch {
            check("self test ran without errors", false, error.localizedDescription + "\n" + String(engine.log.suffix(2000)))
            print("SELFTEST FAILED (\(failures))")
        }
        return failures == 0 ? 0 : 1
    }

    /// Renders the real app views offscreen and saves one PNG per screen.
    @MainActor
    static func capture(client: EngineClient, meta: Meta, state: ProjectState, to dir: URL) async {
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let model = AppModel()
        model.client = client
        model.meta = meta
        model.projects = (try? await client.projects()) ?? []
        model.state = state
        model.phase = .ready
        model.pickedWord = state.allWords.dropFirst(10).first?.id

        let size = NSSize(width: 1440, height: 900)
        let host = NSHostingView(rootView: RootView().environment(model).tint(.tally).frame(width: size.width, height: size.height))
        let window = NSWindow(contentRect: NSRect(origin: .zero, size: size), styleMask: [.titled, .closable],
                              backing: .buffered, defer: false)
        window.contentView = host
        window.appearance = NSAppearance(named: .darkAqua)
        window.orderFrontRegardless()

        func shot(_ name: String) async {
            print("SHOT  rendering \(name)")
            try? await Task.sleep(nanoseconds: 1_800_000_000)
            host.layoutSubtreeIfNeeded()
            guard let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { return }
            host.cacheDisplay(in: host.bounds, to: rep)
            if let png = rep.representation(using: .png, properties: [:]) {
                try? png.write(to: dir.appendingPathComponent("\(name).png"))
                print("SHOT  \(name).png")
            }
        }

        model.selection = .home
        await shot("0-home")
        model.selection = .project(state.id)
        for s in Step.allCases {
            model.step = s
            await shot("\(Step.allCases.firstIndex(of: s)! + 1)-\(s.rawValue.lowercased())")
        }
        model.selection = .brand
        await shot("5-brand")
        window.close()
    }
}
