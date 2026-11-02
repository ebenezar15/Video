import AppKit
import ClipForgeCore
import SwiftUI

@main
enum Main {
    static func main() {
        let args = CommandLine.arguments
        if let i = args.firstIndex(of: "--selftest") {
            let shots = args.firstIndex(of: "--screenshots").flatMap { args.indices.contains($0 + 1) ? args[$0 + 1] : nil }
            _ = i
            SelfTest.launch(screenshots: shots)
        } else {
            ClipForgeApp.main()
        }
    }
}

struct ClipForgeApp: App {
    @State private var model = AppModel()
    @NSApplicationDelegateAdaptor private var delegate: AppDelegate

    var body: some Scene {
        WindowGroup("ClipForge") {
            RootView()
                .environment(model)
                .frame(minWidth: 1080, minHeight: 720)
                .tint(.tally)
                .task { if model.phase == .starting { await model.boot() } }
                .onAppear { delegate.model = model }
        }
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New Video…") { model.selection = .home }.keyboardShortcut("n")
            }
            CommandGroup(after: .undoRedo) {
                Button("Undo Video Edit") { Task { await model.undo() } }
                    .keyboardShortcut("z", modifiers: [.command, .option])
                    .disabled(model.state == nil)
            }
            CommandMenu("Video") {
                Button("Ask Claude…") { NotificationCenter.default.post(name: .focusAsk, object: nil) }
                    .keyboardShortcut("k")
                Button("Render Preview") { Task { await model.render("preview") } }
                    .keyboardShortcut("r")
                    .disabled(model.state == nil || model.busy != nil)
                Button("Render Final") { Task { await model.render("final") } }
                    .keyboardShortcut("r", modifiers: [.command, .shift])
                    .disabled(model.state == nil || model.busy != nil)
                Divider()
                ForEach(Step.allCases) { s in
                    Button(s.rawValue) { model.step = s }
                        .keyboardShortcut(KeyEquivalent(Character(String((Step.allCases.firstIndex(of: s) ?? 0) + 1))))
                        .disabled(model.state == nil)
                }
            }
        }

        Settings {
            SettingsView().environment(model).tint(.tally)
        }
    }
}

extension Notification.Name {
    static let focusAsk = Notification.Name("ClipForgeFocusAsk")
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    weak var model: AppModel?

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { model?.engine.stop() }
    }
}
