import AppKit
import ClipForgeCore
import Foundation
import Observation

enum Sidebar: Hashable {
    case home
    case brand
    case project(String)
}

enum Step: String, CaseIterable, Identifiable {
    case cut = "Cut", style = "Style", sound = "Sound", finish = "Finish"
    var id: String { rawValue }
    var number: String { String(format: "%02d", (Step.allCases.firstIndex(of: self) ?? 0) + 1) }
}

/// App state. Every edit goes to the engine as a command and the returned project state replaces ours.
@MainActor @Observable
final class AppModel {
    enum Phase: Equatable {
        case starting
        case needsEngine(String)
        case installing
        case ready
        case failed(String)
    }

    var phase: Phase = .starting
    var installLog = ""
    var client: EngineClient?
    var meta: Meta?
    var projects: [ProjectSummary] = []
    var selection: Sidebar? = .home
    var state: ProjectState?
    var step: Step = .cut
    var busy: String?
    var progress: Double = 0
    var toast: String?
    var plan: Plan?
    var planPicked: Set<Int> = []
    var asking = false
    var preflight: [PreflightIssue] = []
    var pickedWord: Int?
    var showOriginal = false
    var renderNonce = 0

    let engine = EngineProcess()
    private var toastTask: Task<Void, Never>?

    // MARK: settings (UserDefaults + Keychain)

    static let defaults = UserDefaults.standard
    var engineBinarySetting: String {
        get { Self.defaults.string(forKey: "engineBinary") ?? "" }
        set { Self.defaults.set(newValue, forKey: "engineBinary") }
    }
    var homeSetting: String {
        get { Self.defaults.string(forKey: "clipforgeHome") ?? "" }
        set { Self.defaults.set(newValue, forKey: "clipforgeHome") }
    }

    var engineEnv: [String: String] {
        var env = [
            "ANTHROPIC_API_KEY": Keychain.get("anthropic") ?? "",
            "PEXELS_API_KEY": Keychain.get("pexels") ?? "",
        ]
        if !homeSetting.isEmpty { env["CLIPFORGE_HOME"] = homeSetting }
        return env
    }

    static var bundledEngine: URL? {
        guard let r = Bundle.main.resourceURL?.appendingPathComponent("engine"),
              FileManager.default.fileExists(atPath: r.appendingPathComponent("pyproject.toml").path) else { return nil }
        return r
    }

    // MARK: engine lifecycle

    func boot() async {
        phase = .starting
        guard EngineProcess.ffmpeg != nil else {
            phase = .needsEngine("ClipForge renders with ffmpeg, which is not installed. In Terminal run:\n\nbrew install ffmpeg\n\nthen press Try again.")
            return
        }
        guard let bin = EngineProcess.engineBinary(explicit: engineBinarySetting) else {
            phase = .needsEngine(Self.bundledEngine == nil
                ? "The ClipForge engine was not found. Install it with pip install -e engine[all], or set its path in Settings."
                : "First run: ClipForge installs its editing engine into ~/Library/Application Support/ClipForge. This takes a few minutes and needs Python 3.10 or newer.")
            return
        }
        do {
            let url = try await engine.start(binary: bin, env: engineEnv)
            let c = EngineClient(base: url)
            client = c
            meta = try await c.meta()
            projects = try await c.projects()
            phase = .ready
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    func installEngine() async {
        guard let src = Self.bundledEngine else {
            phase = .failed("This build does not include the engine source.")
            return
        }
        guard let py = EngineProcess.findPython() else {
            phase = .needsEngine("Python 3.10 or newer is needed. In Terminal run:\n\nbrew install python\n\nthen press Try again.")
            return
        }
        phase = .installing
        installLog = ""
        do {
            let report = try await EngineProcess.install(engineSource: src, python: py) { line in
                Task { @MainActor in self.installLog += line.hasSuffix("\n") ? line : line + "\n" }
            }
            await boot()
            if !report.missing.isEmpty {
                say("Installed. Not available on this Mac yet: \(report.missing.values.sorted().joined(separator: ", ")). See Settings → Engine.")
            }
        } catch {
            phase = .failed(error.localizedDescription + "\n\n" + String(installLog.suffix(2000)))
        }
    }

    func restartEngine() async {
        engine.stop()
        let current = selection
        await boot()
        if case .project(let id) = current { await open(id) }
    }

    // MARK: helpers

    func say(_ msg: String) {
        toast = msg
        toastTask?.cancel()
        toastTask = Task {
            try? await Task.sleep(nanoseconds: 3_500_000_000)
            if !Task.isCancelled { toast = nil }
        }
    }

    func fail(_ error: Error) { say(error.localizedDescription) }

    var projectDir: URL? {
        guard let meta, let state else { return nil }
        return URL(fileURLWithPath: meta.home).appendingPathComponent("projects").appendingPathComponent(state.id)
    }

    func fileURL(_ rel: String) -> URL? {
        guard let client, let state else { return nil }
        return client.fileURL(state.id, rel)
    }

    var playerURL: URL? {
        guard let state else { return nil }
        if !showOriginal, let r = state.latestRender {
            return fileURL(r).flatMap { URL(string: "\($0.absoluteString)?v=\(renderNonce)") }
        }
        return fileURL(state.sourceRel)
    }

    func wordText(_ id: Int?) -> String { state?.word(id)?.text ?? "?" }

    // MARK: projects

    func refreshProjects() async {
        guard let client else { return }
        projects = (try? await client.projects()) ?? projects
    }

    func open(_ id: String) async {
        guard let client else { return }
        do {
            state = try await client.project(id)
            pickedWord = nil
            preflight = []
            showOriginal = state?.latestRender == nil
            step = (state?.transcribed ?? false) ? step : .cut
        } catch { fail(error) }
    }

    func create(video: URL, shotType: String) async {
        guard let client else { return }
        do {
            let st = try await client.createProject(video: video, shotType: shotType, name: video.deletingPathExtension().lastPathComponent)
            await refreshProjects()
            state = st
            step = .cut
            selection = .project(st.id)
            say("Imported \(video.lastPathComponent)")
        } catch { fail(error) }
    }

    // MARK: edits

    func apply(_ cmd: Command) async {
        guard let client, let state else { return }
        do {
            let r = try await client.apply(state.id, cmd)
            self.state = r.state
            say(r.message)
        } catch { fail(error) }
    }

    func undo() async {
        guard let client, let state else { return }
        do {
            let r = try await client.undo(state.id)
            self.state = r.state
            say(r.message)
        } catch { fail(error) }
    }

    func upload(kind: String, files: [URL]) async -> [String] {
        guard let client, let state else { return [] }
        var paths: [String] = []
        for f in files {
            do { paths.append(try await client.uploadMedia(state.id, kind: kind, file: f)) } catch { fail(error) }
        }
        return paths
    }

    // MARK: jobs

    @discardableResult
    func runJob(_ label: String, _ start: (EngineClient, String) async throws -> String) async -> JSONValue? {
        guard let client, let state else { return nil }
        busy = label
        progress = 0
        defer { busy = nil }
        do {
            let job = try await start(client, state.id)
            let result = try await client.wait(job: job) { p in Task { @MainActor in self.progress = p } }
            self.state = try await client.project(state.id)
            return result
        } catch {
            fail(error)
            return nil
        }
    }

    func transcribe(language: String?) async {
        await runJob("Transcribing on this Mac…") { c, id in try await c.transcribe(id, language: language) }
        if state?.transcribed == true { say("Transcribed \(state?.allWords.count ?? 0) words") }
    }

    func importTranscript(_ url: URL) async {
        guard let client, let state else { return }
        do {
            let r = try await client.importTranscript(state.id, file: url)
            self.state = r.state
            say(r.message)
        } catch { fail(error) }
    }

    func render(_ quality: String) async {
        if await runJob(quality == "final" ? "Rendering 1080p…" : "Rendering preview…", { c, id in try await c.render(id, quality: quality) }) != nil {
            showOriginal = false
            renderNonce += 1
            say("Rendered \(quality)")
        }
    }

    func makePostKit() async {
        if await runJob("Making the post kit…", { c, id in try await c.postKit(id) }) != nil { say("Post kit ready") }
    }

    func runPreflight(platform: String) async {
        guard let client, let state else { return }
        do { preflight = try await client.preflight(state.id, platform: platform) } catch { fail(error) }
    }

    // MARK: Claude

    func ask(_ prompt: String) async {
        guard let client, let state, !prompt.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        guard meta?.claude == true else {
            say("Add your Anthropic API key in Settings to ask Claude here, or connect Claude Desktop in Settings → Claude.")
            return
        }
        guard state.transcribed else {
            say("Transcribe first so Claude can read the video.")
            return
        }
        asking = true
        defer { asking = false }
        do {
            let p = try await client.plan(state.id, prompt: prompt)
            plan = p
            planPicked = Set(p.commands.indices)
        } catch { fail(error) }
    }

    func applyPlan() async {
        guard let client, let state, let plan else { return }
        let picks = plan.commands.enumerated().filter { planPicked.contains($0.offset) }
            .map { $0.element.filter { $0.key != "why" } }
        self.plan = nil
        guard !picks.isEmpty else { return }
        do {
            let r = try await client.applyMany(state.id, picks)
            self.state = r.state
            say("Applied \(picks.count) change\(picks.count == 1 ? "" : "s"). Undo is ⌥⌘Z.")
        } catch {
            fail(error)
            self.state = try? await client.project(state.id)
        }
    }

    func saveBrand(_ fields: [String: JSONValue]) async {
        guard let client else { return }
        do {
            say(try await client.setBrand(fields))
            meta = try await client.meta()
            if let id = state?.id { state = try await client.project(id) }
        } catch { fail(error) }
    }
}
