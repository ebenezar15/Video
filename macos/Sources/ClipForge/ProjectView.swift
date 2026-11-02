import AVKit
import ClipForgeCore
import SwiftUI

@MainActor
struct ProjectView: View {
    @Environment(AppModel.self) private var model
    @State private var prompt = ""
    @FocusState private var askFocused: Bool

    var body: some View {
        @Bindable var model = model
        Group {
            if let st = model.state {
                HStack(alignment: .top, spacing: 18) {
                    PlayerPane().frame(width: 300)
                    VStack(alignment: .leading, spacing: 12) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text((model.meta?.shotTypes[st.shotType ?? ""] ?? "").uppercased())
                                .font(.caption.weight(.semibold)).foregroundStyle(.secondary).tracking(0.8)
                            Text(st.name).font(.system(size: 24, weight: .heavy, design: .rounded))
                        }
                        Picker("Step", selection: $model.step) {
                            ForEach(Step.allCases) { s in Text("\(s.number)  \(s.rawValue)").tag(s) }
                        }
                        .pickerStyle(.segmented)
                        .labelsHidden()
                        .frame(maxWidth: 460)
                        ScrollView {
                            Group {
                                switch model.step {
                                case .cut: CutView()
                                case .style: StyleView()
                                case .sound: SoundView()
                                case .finish: FinishView()
                                }
                            }
                            .padding(.bottom, 30)
                        }
                    }
                }
                .padding(20)
            } else {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .navigationTitle(model.state?.name ?? "")
        .toolbar {
            ToolbarItem(placement: .principal) {
                HStack(spacing: 6) {
                    Image(systemName: "sparkles").foregroundStyle(Color.tally)
                    TextField("Ask Claude: “cut it to 40 seconds, LinkedIn-ready, add a stat for the 40%”", text: $prompt)
                        .textFieldStyle(.roundedBorder)
                        .focused($askFocused)
                        .frame(minWidth: 380, idealWidth: 520)
                        .onSubmit { send() }
                    if model.asking { ProgressView().controlSize(.small) }
                }
            }
            ToolbarItemGroup(placement: .primaryAction) {
                Button { send() } label: { Label("Ask Claude", systemImage: "paperplane") }
                    .disabled(prompt.isEmpty || model.asking)
                Button { Task { await model.undo() } } label: { Label("Undo", systemImage: "arrow.uturn.backward") }
                    .help("Undo the last edit (⌥⌘Z)")
            }
        }
        .sheet(isPresented: Binding(get: { model.plan != nil }, set: { if !$0 { model.plan = nil } })) {
            PlanSheet()
        }
        .onReceive(NotificationCenter.default.publisher(for: .focusAsk)) { _ in askFocused = true }
    }

    func send() {
        let p = prompt
        Task {
            await model.ask(p)
            if model.plan != nil { prompt = "" }
        }
    }
}

@MainActor
struct PlayerPane: View {
    @Environment(AppModel.self) private var model
    @State private var player = AVPlayer()

    var body: some View {
        @Bindable var model = model
        VStack(alignment: .leading, spacing: 12) {
            VideoPlayer(player: player)
                .aspectRatio(aspect, contentMode: .fit)
                .background(Color.black)
                .clipShape(RoundedRectangle(cornerRadius: 22))
                .overlay(RoundedRectangle(cornerRadius: 22).strokeBorder(Color.black, lineWidth: 5))
            Picker("Preview", selection: $model.showOriginal) {
                Text("Your edit").tag(false)
                Text("Original").tag(true)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .disabled(model.state?.latestRender == nil)
            HStack {
                Button("Render Preview") { Task { await model.render("preview") } }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.busy != nil)
                Spacer()
            }
            if let busy = model.busy {
                VStack(alignment: .leading, spacing: 4) {
                    Text(busy).font(.caption).foregroundStyle(.secondary)
                    ProgressView(value: model.progress)
                }
            }
            if let s = model.state?.summary {
                HStack(spacing: 22) {
                    Stat(label: "Before", value: formatSeconds(s.before))
                    Stat(label: "After", value: formatSeconds(s.after))
                    Stat(label: "Cuts", value: "\(s.cuts)")
                }
            }
            Spacer()
        }
        .onAppear(perform: load)
        .onChange(of: model.playerURL) { _, _ in load() }
    }

    var aspect: CGFloat {
        let a = (model.showOriginal ? nil : model.state?.aspect) ?? "9:16"
        let p = a.split(separator: ":").compactMap { Double($0) }
        return p.count == 2 && p[1] > 0 ? p[0] / p[1] : 9.0 / 16.0
    }

    func load() {
        guard let url = model.playerURL else { return }
        player.replaceCurrentItem(with: AVPlayerItem(url: url))
    }
}

@MainActor
struct PlanSheet: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Claude suggests", systemImage: "sparkles").font(.title3.bold())
                Spacer()
                Text(model.plan?.model ?? "").font(.caption.monospaced()).foregroundStyle(.secondary)
            }
            Text(model.plan?.summary ?? "")
            ScrollView {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(Array((model.plan?.commands ?? []).enumerated()), id: \.offset) { i, c in
                        Toggle(isOn: Binding(get: { model.planPicked.contains(i) },
                                             set: { on in if on { model.planPicked.insert(i) } else { model.planPicked.remove(i) } })) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(c["why"]?.string ?? c.op)
                                Text(describe(c)).font(.caption.monospaced()).foregroundStyle(Color.tally).lineLimit(2)
                            }
                        }
                        .toggleStyle(.checkbox)
                        .padding(8)
                        .background(RoundedRectangle(cornerRadius: 8).strokeBorder(Color.primary.opacity(0.1)))
                    }
                }
            }
            .frame(minHeight: 160, maxHeight: 380)
            HStack {
                Spacer()
                Button("Cancel") { model.plan = nil }.keyboardShortcut(.cancelAction)
                Button("Apply \(model.planPicked.count) Changes") { Task { await model.applyPlan() } }
                    .keyboardShortcut(.defaultAction)
                    .disabled(model.planPicked.isEmpty)
            }
        }
        .padding(20)
        .frame(width: 620)
    }

    func describe(_ c: Command) -> String {
        let args = c.filter { $0.key != "op" && $0.key != "why" }.sorted { $0.key < $1.key }
            .map { "\($0.key)=\($0.value.string ?? (($0.value.array?.compactMap(\.string))?.joined(separator: ",") ?? "…"))" }
        return ([c.op] + args).joined(separator: " ")
    }
}
