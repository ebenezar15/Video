import Foundation

/// Finds, installs and runs the Python engine that does the rendering.
///
/// Order of preference for the engine binary:
/// 1. an explicit path (Settings, or CLIPFORGE_BIN)
/// 2. the app's private install in ~/Library/Application Support/ClipForge/engine-venv
/// 3. `clipforge` on PATH
public final class EngineProcess: @unchecked Sendable {
    public static let searchDirs = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin",
                                    NSHomeDirectory() + "/.local/bin"]

    public private(set) var process: Process?
    public private(set) var baseURL: URL?
    private var output = ""
    private let lock = NSLock()

    public init() {}

    // MARK: discovery

    public static var appSupport: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory() + "/Library/Application Support")
        return base.appendingPathComponent("ClipForge", isDirectory: true)
    }

    public static var venv: URL { appSupport.appendingPathComponent("engine-venv", isDirectory: true) }
    public static var venvBinary: URL { venv.appendingPathComponent("bin/clipforge") }

    /// PATH for child processes. Apps launched from Finder get a minimal PATH, so add the usual tool folders.
    public static func childPath(_ current: String? = ProcessInfo.processInfo.environment["PATH"]) -> String {
        var parts = searchDirs
        for p in (current ?? "").split(separator: ":").map(String.init) where !parts.contains(p) { parts.append(p) }
        return parts.joined(separator: ":")
    }

    public static func which(_ name: String) -> URL? {
        for dir in childPath().split(separator: ":") {
            let u = URL(fileURLWithPath: String(dir)).appendingPathComponent(name)
            if FileManager.default.isExecutableFile(atPath: u.path) { return u }
        }
        return nil
    }

    public static func engineBinary(explicit: String? = nil) -> URL? {
        let candidates = [explicit, ProcessInfo.processInfo.environment["CLIPFORGE_BIN"]].compactMap { $0 }.filter { !$0.isEmpty }
        for c in candidates where FileManager.default.isExecutableFile(atPath: c) { return URL(fileURLWithPath: c) }
        if FileManager.default.isExecutableFile(atPath: venvBinary.path) { return venvBinary }
        return which("clipforge")
    }

    /// Preference among Python versions: the ones every dependency ships ready-made builds for come first.
    /// Lower is better; nil means unsupported (3.9 and older, which is what /usr/bin/python3 often is).
    public static func pythonRank(major: Int, minor: Int) -> Int? {
        guard major == 3, minor >= 10 else { return nil }
        return [12: 0, 13: 1, 11: 2, 10: 3][minor] ?? 10 + minor
    }

    /// The best Python 3.10+ on this Mac (Homebrew, python.org or PATH).
    public static func findPython() -> URL? {
        var dirs = childPath().split(separator: ":").map(String.init)
        let framework = "/Library/Frameworks/Python.framework/Versions"
        if let versions = try? FileManager.default.contentsOfDirectory(atPath: framework) {
            dirs += versions.map { "\(framework)/\($0)/bin" }
        }
        let names = ["python3.12", "python3.13", "python3.11", "python3.10", "python3.14", "python3.15", "python3"]
        var best: (rank: Int, url: URL)?
        var seen = Set<String>()
        for dir in dirs {
            for n in names {
                let u = URL(fileURLWithPath: dir).appendingPathComponent(n)
                guard FileManager.default.isExecutableFile(atPath: u.path) else { continue }
                let real = u.resolvingSymlinksInPath().path
                guard seen.insert(real).inserted,
                      let v = try? run(u, ["-c", "import sys;print('%d.%d' % sys.version_info[:2])"]) else { continue }
                let parts = v.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: ".").compactMap { Int($0) }
                guard parts.count == 2, let rank = pythonRank(major: parts[0], minor: parts[1]) else { continue }
                if best == nil || rank < best!.rank { best = (rank, u) }
            }
        }
        return best?.url
    }

    public static var ffmpeg: URL? { which("ffmpeg") }

    /// Run a command to completion and return stdout.
    @discardableResult
    public static func run(_ exe: URL, _ args: [String], env: [String: String] = [:]) throws -> String {
        let p = Process()
        p.executableURL = exe
        p.arguments = args
        var e = ProcessInfo.processInfo.environment
        e["PATH"] = childPath()
        e.merge(env) { _, b in b }
        p.environment = e
        let out = Pipe()
        p.standardOutput = out
        p.standardError = Pipe()
        try p.run()
        let data = out.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        guard p.terminationStatus == 0 else {
            throw EngineError.setup("\(exe.lastPathComponent) exited with \(p.terminationStatus)")
        }
        return String(decoding: data, as: UTF8.self)
    }

    // MARK: install

    /// Packages that must never be compiled on the user's Mac (they need a full C/C++ toolchain and ffmpeg headers).
    /// With these binary-only, pip picks the newest version that has a ready-made build for this Mac and Python.
    public static let binaryOnly = "av,ctranslate2,onnxruntime,tokenizers,opencv-python-headless,numpy,pillow,pydantic-core"

    /// What an install managed to set up. The core engine is required; the extras are optional.
    public struct InstallReport: Codable, Sendable {
        public var python: String
        public var missing: [String: String] = [:]   // extra -> what it is for
        public var transcription: Bool { missing["whisper"] == nil }
    }

    public static var reportURL: URL { appSupport.appendingPathComponent("install-report.json") }

    public static func lastReport() -> InstallReport? {
        guard let d = try? Data(contentsOf: reportURL) else { return nil }
        return try? JSONDecoder().decode(InstallReport.self, from: d)
    }

    /// Creates a private virtual environment and installs the engine shipped inside the app.
    /// Core first (required), then each optional extra on its own, so one missing build never blocks the app.
    @discardableResult
    public static func install(engineSource: URL, python: URL, log: @escaping @Sendable (String) -> Void) async throws -> InstallReport {
        let fm = FileManager.default
        try fm.createDirectory(at: appSupport, withIntermediateDirectories: true)
        // build from a copy: setuptools writes into the source folder, which must not be the signed app bundle
        let src = appSupport.appendingPathComponent("engine-src", isDirectory: true)
        if fm.fileExists(atPath: src.path) { try fm.removeItem(at: src) }
        try fm.copyItem(at: engineSource, to: src)
        log("Copied engine source to \(src.path)")
        try await stream(python, ["-m", "venv", "--clear", venv.path], log: log)
        let py = venv.appendingPathComponent("bin/python3")
        let version = (try? run(py, ["-c", "import sys;print(sys.version.split()[0])"]))?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "?"
        var report = InstallReport(python: version)
        try await stream(py, ["-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], log: log)
        let pipArgs = ["-m", "pip", "install", "--prefer-binary", "--only-binary", binaryOnly]
        try await stream(py, pipArgs + [src.path], log: log)
        guard fm.isExecutableFile(atPath: venvBinary.path) else {
            throw EngineError.setup("Install finished but \(venvBinary.path) is missing.")
        }
        for (extra, purpose) in [("faces", "face-aware pop-up placement"), ("whisper", "on-device transcription")] {
            do {
                try await stream(py, pipArgs + ["\(src.path)[\(extra)]"], log: log)
            } catch {
                report.missing[extra] = purpose
                log("NOTE: \(purpose) could not be installed for Python \(version) on this Mac. ClipForge works without it."
                    + (extra == "whisper" ? " Import a transcript instead, or install Python 3.12 (brew install python@3.12) and choose Reinstall Engine." : ""))
            }
        }
        if let d = try? JSONEncoder().encode(report) { try? d.write(to: reportURL) }
        return report
    }

    static func stream(_ exe: URL, _ args: [String], log: @escaping @Sendable (String) -> Void) async throws {
        log("$ \(exe.lastPathComponent) \(args.joined(separator: " "))")
        let p = Process()
        p.executableURL = exe
        p.arguments = args
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = childPath()
        p.environment = env
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { h in
            let s = String(decoding: h.availableData, as: UTF8.self)
            if !s.isEmpty { log(s) }
        }
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            p.terminationHandler = { proc in
                pipe.fileHandleForReading.readabilityHandler = nil
                if proc.terminationStatus == 0 { c.resume() }
                else { c.resume(throwing: EngineError.setup("\(exe.lastPathComponent) failed (exit \(proc.terminationStatus)). See the log.")) }
            }
            do { try p.run() } catch { c.resume(throwing: error) }
        }
    }

    // MARK: run

    /// Starts `clipforge studio --port 0` and waits until the API answers.
    public func start(binary: URL, env extra: [String: String] = [:], timeout: TimeInterval = 40) async throws -> URL {
        stop()
        let p = Process()
        p.executableURL = binary
        p.arguments = ["studio", "--port", "0"]
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = Self.childPath()
        env["PYTHONUNBUFFERED"] = "1"
        env.merge(extra.filter { !$0.value.isEmpty }) { _, b in b }
        p.environment = env
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        output = ""
        pipe.fileHandleForReading.readabilityHandler = { [weak self] h in
            let s = String(decoding: h.availableData, as: UTF8.self)
            guard let self, !s.isEmpty else { return }
            self.lock.lock()
            self.output += s
            if self.output.count > 200_000 { self.output = String(self.output.suffix(100_000)) }
            self.lock.unlock()
        }
        try p.run()
        process = p

        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if !p.isRunning { throw EngineError.setup("The engine stopped while starting:\n\(log.suffix(1500))") }
            if let url = Self.parseURL(log) {
                let client = EngineClient(base: url)
                if (try? await client.meta()) != nil {
                    baseURL = url
                    return url
                }
            }
            try await Task.sleep(nanoseconds: 250_000_000)
        }
        stop()
        throw EngineError.setup("The engine did not start within \(Int(timeout))s.\n\(log.suffix(1500))")
    }

    public var log: String {
        lock.lock(); defer { lock.unlock() }
        return output
    }

    public static func parseURL(_ text: String) -> URL? {
        guard let r = text.range(of: #"http://127\.0\.0\.1:\d+"#, options: .regularExpression) else { return nil }
        return URL(string: String(text[r]))
    }

    public func stop() {
        if let p = process, p.isRunning { p.terminate() }
        process = nil
        baseURL = nil
    }

    deinit { stop() }
}
