import AppKit
import ClipForgeCore
import SwiftUI

@MainActor
struct SettingsView: View {
    @Environment(AppModel.self) private var model
    @State private var binary = ""
    @State private var home = ""
    @State private var anthropicKey = ""
    @State private var pexelsKey = ""
    @State private var status = ""

    var body: some View {
        TabView {
            Form {
                Section("Engine") {
                    LabeledContent("Status", value: model.phase == .ready ? "Running at \(model.client?.base.absoluteString ?? "")" : "\(model.phase)")
                    LabeledContent("ffmpeg", value: EngineProcess.ffmpeg?.path ?? "Not found. Run: brew install ffmpeg")
                    LabeledContent("Engine", value: EngineProcess.engineBinary(explicit: binary)?.path ?? "Not installed")
                    TextField("Custom engine path (optional)", text: $binary, prompt: Text("/path/to/clipforge"))
                    TextField("Projects folder (optional)", text: $home, prompt: Text("~/ClipForge"))
                    HStack {
                        Button("Save and Restart Engine") {
                            model.engineBinarySetting = binary
                            model.homeSetting = home
                            Task { await model.restartEngine() }
                        }
                        if AppModel.bundledEngine != nil {
                            Button("Reinstall Engine") { Task { await model.installEngine() } }
                        }
                        Button("Engine Log") { status = String(model.engine.log.suffix(3000)) }
                    }
                }
                if !status.isEmpty {
                    Section("Log") { Text(status).font(.caption.monospaced()).textSelection(.enabled) }
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("Engine", systemImage: "gearshape.2") }

            Form {
                Section("Ask Claude in this app") {
                    SecureField("Anthropic API key", text: $anthropicKey)
                    Text("Stored in your Keychain and passed only to the local engine. Model: \(model.meta?.model ?? "claude-opus-5-5").")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Section("Use your Claude subscription instead") {
                    Text("Claude Desktop and Claude Code can drive ClipForge directly through MCP. No API key needed.")
                        .font(.callout)
                    HStack {
                        Button("Add ClipForge to Claude Desktop") { installClaudeDesktop() }
                        Button("Copy Claude Code Command") { copy("claude mcp add clipforge -- \(enginePath) mcp") }
                    }
                    Text("Then ask Claude: “Edit ~/Movies/talk.mov into a LinkedIn clip in my brand.”")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Section("Stock B-roll") {
                    SecureField("Pexels API key (optional)", text: $pexelsKey)
                }
                HStack {
                    Spacer()
                    Button("Save Keys and Restart Engine") {
                        Keychain.set("anthropic", anthropicKey)
                        Keychain.set("pexels", pexelsKey)
                        Task { await model.restartEngine() }
                    }
                    .buttonStyle(.borderedProminent)
                }
                if !status.isEmpty { Text(status).font(.caption) }
            }
            .formStyle(.grouped)
            .tabItem { Label("Claude", systemImage: "sparkles") }
        }
        .frame(width: 620, height: 460)
        .onAppear {
            binary = model.engineBinarySetting
            home = model.homeSetting
            anthropicKey = Keychain.get("anthropic") ?? ""
            pexelsKey = Keychain.get("pexels") ?? ""
        }
    }

    var enginePath: String { EngineProcess.engineBinary(explicit: binary)?.path ?? "clipforge" }

    func copy(_ s: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(s, forType: .string)
        status = "Copied: \(s)"
    }

    func installClaudeDesktop() {
        do {
            let url = try ClaudeDesktop.install(binary: enginePath, home: home.isEmpty ? nil : home,
                                                extraEnv: ["PEXELS_API_KEY": Keychain.get("pexels") ?? ""])
            status = "Added to \(url.path). Restart Claude Desktop."
        } catch {
            status = error.localizedDescription
        }
    }
}
