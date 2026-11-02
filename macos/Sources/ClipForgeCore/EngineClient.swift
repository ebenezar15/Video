import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public enum EngineError: LocalizedError, Equatable {
    case server(String)
    case jobFailed(String)
    case notRunning
    case setup(String)

    public var errorDescription: String? {
        switch self {
        case .server(let m), .jobFailed(let m), .setup(let m): return m
        case .notRunning: return "The ClipForge engine is not running."
        }
    }
}

/// Talks to the local engine (the same API the Studio web app uses).
public struct EngineClient: Sendable {
    public let base: URL
    let session: URLSession

    public init(base: URL, session: URLSession = .shared) {
        self.base = base
        self.session = session
    }

    static let decoder = JSONDecoder()

    // MARK: transport

    func request(_ path: String, method: String = "GET", body: Data? = nil, headers: [String: String] = [:]) async throws -> Data {
        var req = URLRequest(url: URL(string: path, relativeTo: base)!)
        req.httpMethod = method
        req.httpBody = body
        req.timeoutInterval = 600
        for (k, v) in headers { req.setValue(v, forHTTPHeaderField: k) }
        let (data, resp) = try await session.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else {
            let msg = (try? JSONDecoder().decode([String: String].self, from: data))?["error"] ?? "HTTP \(code)"
            throw EngineError.server(msg)
        }
        return data
    }

    func get<T: Decodable>(_ path: String, as: T.Type = T.self) async throws -> T {
        try Self.decoder.decode(T.self, from: try await request(path))
    }

    func post<T: Decodable>(_ path: String, json: JSONValue = [:], as: T.Type = T.self) async throws -> T {
        let body = try JSONEncoder().encode(json)
        return try Self.decoder.decode(T.self, from: try await request(path, method: "POST", body: body,
                                                                         headers: ["Content-Type": "application/json"]))
    }

    func upload<T: Decodable>(_ path: String, file: URL, as: T.Type = T.self) async throws -> T {
        let data = try Data(contentsOf: file)
        let name = file.lastPathComponent.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? "upload"
        return try Self.decoder.decode(T.self, from: try await request(path, method: "POST", body: data,
                                                                         headers: ["X-Filename": name]))
    }

    static func q(_ s: String) -> String { s.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? s }

    // MARK: API

    public func meta() async throws -> Meta { try await get("/api/meta") }
    public func projects() async throws -> [ProjectSummary] { try await get("/api/projects") }
    public func project(_ id: String) async throws -> ProjectState { try await get("/api/projects/\(Self.q(id))") }

    public func createProject(video: URL, shotType: String, name: String? = nil, copyMedia: Bool = true) async throws -> ProjectState {
        var body: [String: JSONValue] = ["path": .string(video.path), "shot_type": .string(shotType), "copy": .bool(copyMedia)]
        if let name { body["name"] = .string(name) }
        return try await post("/api/projects/from-path", json: .object(body))
    }

    public func apply(_ id: String, _ cmd: Command) async throws -> CommandResponse {
        try await post("/api/projects/\(Self.q(id))/command", json: .object(cmd))
    }

    public func applyMany(_ id: String, _ cmds: [Command]) async throws -> CommandsResponse {
        try await post("/api/projects/\(Self.q(id))/commands", json: ["commands": .array(cmds.map { .object($0) })])
    }

    public func undo(_ id: String) async throws -> CommandResponse { try await post("/api/projects/\(Self.q(id))/undo") }

    public func importTranscript(_ id: String, file: URL) async throws -> CommandResponse {
        try await upload("/api/projects/\(Self.q(id))/transcript", file: file)
    }

    public func uploadMedia(_ id: String, kind: String, file: URL) async throws -> String {
        let r: UploadResult = try await upload("/api/projects/\(Self.q(id))/upload?kind=\(kind)", file: file)
        return r.path
    }

    public func transcribe(_ id: String, language: String?) async throws -> String {
        let r: JobRef = try await post("/api/projects/\(Self.q(id))/transcribe", json: ["language": .string(language ?? "")])
        return r.job
    }

    public func render(_ id: String, quality: String) async throws -> String {
        let r: JobRef = try await post("/api/projects/\(Self.q(id))/render", json: ["quality": .string(quality)])
        return r.job
    }

    public func postKit(_ id: String) async throws -> String {
        let r: JobRef = try await post("/api/projects/\(Self.q(id))/postkit")
        return r.job
    }

    public func job(_ jobId: String) async throws -> JobStatus { try await get("/api/jobs/\(jobId)") }

    /// Polls a background job until it finishes.
    public func wait(job jobId: String, progress: (@Sendable (Double) -> Void)? = nil) async throws -> JSONValue? {
        while true {
            let j = try await job(jobId)
            progress?(j.progress ?? 0)
            switch j.status {
            case "done": return j.result
            case "error", "missing": throw EngineError.jobFailed(j.error ?? "The job stopped.")
            default: try await Task.sleep(nanoseconds: 400_000_000)
            }
        }
    }

    public func plan(_ id: String, prompt: String) async throws -> Plan {
        try await post("/api/projects/\(Self.q(id))/plan", json: ["prompt": .string(prompt)])
    }

    public func preflight(_ id: String, platform: String) async throws -> [PreflightIssue] {
        try await post("/api/projects/\(Self.q(id))/preflight", json: ["platform": .string(platform)])
    }

    public func brand() async throws -> Brand { try await get("/api/brand") }

    public func setBrand(_ fields: [String: JSONValue]) async throws -> String {
        let r: [String: String] = try await post("/api/brand", json: .object(fields))
        return r["message"] ?? "Brand saved"
    }

    public func fileURL(_ projectId: String, _ rel: String) -> URL {
        URL(string: "/files/\(Self.q(projectId))/\(rel.split(separator: "/").map { Self.q(String($0)) }.joined(separator: "/"))", relativeTo: base)!
    }

    public func moodPreviewURL(_ mood: String) -> URL { URL(string: "/audio/mood/\(mood)", relativeTo: base)! }
}
