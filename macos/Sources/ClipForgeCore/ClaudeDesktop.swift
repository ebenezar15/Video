import Foundation

/// Adds ClipForge to Claude Desktop's MCP servers without touching anything else in the file.
public enum ClaudeDesktop {
    public static var configURL: URL {
        URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent("Library/Application Support/Claude/claude_desktop_config.json")
    }

    public static func merged(existing: Data?, binary: String, home: String?, extraEnv: [String: String] = [:]) throws -> Data {
        var root: [String: Any] = [:]
        if let existing, !existing.isEmpty {
            guard let obj = try JSONSerialization.jsonObject(with: existing) as? [String: Any] else {
                throw EngineError.setup("Claude Desktop's config is not a JSON object; not changing it.")
            }
            root = obj
        }
        var servers = root["mcpServers"] as? [String: Any] ?? [:]
        var env: [String: String] = extraEnv.filter { !$0.value.isEmpty }
        if let home, !home.isEmpty { env["CLIPFORGE_HOME"] = home }
        env["PATH"] = EngineProcess.childPath()
        servers["clipforge"] = ["command": binary, "args": ["mcp"], "env": env] as [String: Any]
        root["mcpServers"] = servers
        return try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys])
    }

    /// Writes the config, keeping a backup of the previous file.
    public static func install(binary: String, home: String?, extraEnv: [String: String] = [:]) throws -> URL {
        let url = configURL
        let fm = FileManager.default
        try fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let old = try? Data(contentsOf: url)
        if let old { try old.write(to: url.appendingPathExtension("bak")) }
        try merged(existing: old, binary: binary, home: home, extraEnv: extraEnv).write(to: url, options: .atomic)
        return url
    }

    public static func snippet(binary: String, home: String?) -> String {
        let data = (try? merged(existing: nil, binary: binary, home: home)) ?? Data()
        return String(decoding: data, as: UTF8.self)
    }
}
