import ClipForgeCore
import SwiftUI
import UniformTypeIdentifiers

struct RootView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Group {
            switch model.phase {
            case .ready: MainSplit()
            case .starting: ProgressView("Starting the editing engine…").frame(maxWidth: .infinity, maxHeight: .infinity)
            case .needsEngine(let why): SetupView(reason: why)
            case .installing: InstallView()
            case .failed(let msg): FailedView(message: msg)
            }
        }
        .overlay(alignment: .bottom) {
            if let t = model.toast {
                Text(t)
                    .padding(.horizontal, 14).padding(.vertical, 9)
                    .background(Capsule().fill(.regularMaterial))
                    .overlay(Capsule().strokeBorder(Color.primary.opacity(0.1)))
                    .padding(.bottom, 18)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.snappy, value: model.toast)
    }
}

struct MainSplit: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        NavigationSplitView {
            List(selection: $model.selection) {
                Section {
                    Label("New video", systemImage: "plus.rectangle.on.rectangle").tag(Sidebar.home)
                    Label("Brand", systemImage: "paintpalette").tag(Sidebar.brand)
                }
                Section("Videos") {
                    ForEach(model.projects) { p in
                        VStack(alignment: .leading, spacing: 1) {
                            Text(p.name).lineLimit(1)
                            Text("\(formatSeconds(p.duration))\(p.transcribed == true ? " · transcribed" : "")")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                        .tag(Sidebar.project(p.id))
                    }
                }
            }
            .navigationSplitViewColumnWidth(min: 200, ideal: 230)
            .safeAreaInset(edge: .bottom) {
                HStack(spacing: 8) {
                    Circle().fill(Color.tally).frame(width: 9, height: 9)
                        .shadow(color: .tally.opacity(0.6), radius: 4)
                    Text("ClipForge \(model.meta?.version ?? "")").font(.caption).foregroundStyle(.secondary)
                    Spacer()
                }
                .padding(12)
            }
        } detail: {
            switch model.selection {
            case .project: ProjectView()
            case .brand: BrandView()
            default: HomeView()
            }
        }
        .onChange(of: model.selection) { _, new in
            if case .project(let id) = new, model.state?.id != id { Task { await model.open(id) } }
        }
    }
}

struct HomeView: View {
    @Environment(AppModel.self) private var model
    @State private var shot = "on_camera"
    @State private var targeted = false

    static let shotHints = ["on_camera": "Talking to camera", "voiceover_clips": "Your voice over B-roll clips",
                            "faceless": "Animated text, no face", "clips_text": "Clips with big text"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Drop in a video. Get back a finished reel in your look.")
                        .font(.system(size: 30, weight: .heavy, design: .rounded))
                    Text("Pick how it was shot, then drop the file. ClipForge transcribes it on this Mac, and Claude cuts, captions, styles, scores and packages it.")
                        .foregroundStyle(.secondary)
                    HStack(spacing: 10) {
                        ForEach(Meta.ordered(model.meta?.shotTypes ?? [:], Meta.shotOrder)) { item in
                            Tile(title: item.value, about: Self.shotHints[item.key] ?? "", selected: shot == item.key) { shot = item.key }
                        }
                    }
                    VStack(spacing: 12) {
                        Image(systemName: "film.stack").font(.system(size: 40)).foregroundStyle(Color.tally)
                        Text("Drag a video here").font(.title3.weight(.semibold))
                        Button("Choose a Video…") {
                            if let url = Panels.open(types: [.movie, .video, .mpeg4Movie, .quickTimeMovie]).first {
                                Task { await model.create(video: url, shotType: shot) }
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        Text("MP4, MOV, MKV, ProRes, HEVC").font(.caption).foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, minHeight: 220)
                    .background(RoundedRectangle(cornerRadius: 16).fill(targeted ? Color.tally.opacity(0.12) : Color.primary.opacity(0.03)))
                    .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(targeted ? Color.tally : Color.primary.opacity(0.15),
                                                                            style: StrokeStyle(lineWidth: 1.5, dash: [6, 5])))
                    .dropDestination(for: URL.self) { urls, _ in
                        guard let u = urls.first else { return false }
                        Task { await model.create(video: u, shotType: shot) }
                        return true
                    } isTargeted: { targeted = $0 }
                }
                if !model.projects.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Your videos").font(.headline)
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 10)], spacing: 10) {
                            ForEach(model.projects) { p in
                                Tile(title: p.name, about: "\(model.meta?.shotTypes[p.shotType ?? ""] ?? "") · \(formatSeconds(p.duration))") {
                                    model.selection = .project(p.id)
                                }
                            }
                        }
                    }
                }
            }
            .padding(28)
            .frame(maxWidth: 980, alignment: .leading)
        }
        .navigationTitle("New video")
    }
}

struct SetupView: View {
    @Environment(AppModel.self) private var model
    var reason: String

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "wand.and.stars").font(.system(size: 44)).foregroundStyle(Color.tally)
            Text("Set up ClipForge").font(.title.bold())
            Text(reason).multilineTextAlignment(.center).textSelection(.enabled).frame(maxWidth: 520)
            HStack {
                if AppModel.bundledEngine != nil && EngineProcess.ffmpeg != nil {
                    Button("Install Engine") { Task { await model.installEngine() } }.buttonStyle(.borderedProminent)
                }
                Button("Try Again") { Task { await model.boot() } }
                SettingsLink { Text("Settings…") }
            }
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct InstallView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack { ProgressView().controlSize(.small); Text("Installing the editing engine…").font(.headline) }
            ScrollView {
                Text(model.installLog.suffix(8000)).font(.system(.caption, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled)
            }
            .defaultScrollAnchor(.bottom)
            .padding(10)
            .background(RoundedRectangle(cornerRadius: 8).fill(Color.primary.opacity(0.05)))
        }
        .padding(30)
    }
}

struct FailedView: View {
    @Environment(AppModel.self) private var model
    var message: String

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "exclamationmark.triangle").font(.system(size: 36)).foregroundStyle(.orange)
            Text("The engine could not start").font(.title2.bold())
            ScrollView { Text(message).font(.system(.caption, design: .monospaced)).textSelection(.enabled) }
                .frame(maxWidth: 680, maxHeight: 260)
            HStack {
                Button("Try Again") { Task { await model.boot() } }.buttonStyle(.borderedProminent)
                if AppModel.bundledEngine != nil { Button("Reinstall Engine") { Task { await model.installEngine() } } }
                SettingsLink { Text("Settings…") }
            }
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct BrandView: View {
    @Environment(AppModel.self) private var model
    @State private var name = ""
    @State private var handle = ""
    @State private var cta = ""
    @State private var hashtags = ""
    @State private var titleFont = ""
    @State private var captionFont = ""
    @State private var colors: [String: Color] = [:]
    @State private var loaded = false

    static let keys = ["primary", "accent", "ink", "paper"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Your look, set once").font(.system(size: 26, weight: .heavy, design: .rounded))
                Text("Colours, fonts and the call to action used by every reel, graphic and post.").foregroundStyle(.secondary)
                Panel(title: "Who you are") {
                    Form {
                        TextField("Name (for lower thirds)", text: $name)
                        TextField("@handle", text: $handle)
                        TextField("Call to action", text: $cta)
                        TextField("Hashtags, comma separated", text: $hashtags)
                    }
                }
                Panel(title: "Colours") {
                    HStack(spacing: 18) {
                        ForEach(Self.keys, id: \.self) { k in
                            ColorPicker(k.capitalized, selection: Binding(get: { colors[k] ?? .gray }, set: { colors[k] = $0 }))
                        }
                    }
                }
                Panel(title: "Fonts", subtitle: "A font name installed on this Mac, or the path to a .ttf/.otf file. Leave empty to use each look's fonts.") {
                    Form {
                        TextField("Title font", text: $titleFont)
                        TextField("Caption font", text: $captionFont)
                    }
                }
                Button("Save Brand") {
                    let tags: [JSONValue] = hashtags.split(separator: ",")
                        .map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }.map { JSONValue.string($0) }
                    var palette: [String: JSONValue] = [:]
                    for k in Self.keys { if let c = colors[k] { palette[k] = JSONValue.string(c.hex) } }
                    let fonts: [String: JSONValue] = ["title": titleFont.isEmpty ? JSONValue.null : JSONValue.string(titleFont),
                                                      "caption": captionFont.isEmpty ? JSONValue.null : JSONValue.string(captionFont)]
                    let f: [String: JSONValue] = ["name": .string(name), "handle": .string(handle), "cta": .string(cta),
                                                  "hashtags": .array(tags), "palette": .object(palette), "fonts": .object(fonts)]
                    Task { await model.saveBrand(f) }
                }
                .buttonStyle(.borderedProminent)
            }
            .padding(28)
            .frame(maxWidth: 760, alignment: .leading)
        }
        .navigationTitle("Brand")
        .task { await load() }
    }

    func load() async {
        guard !loaded, let client = model.client else { return }
        let brand = try? await client.brand()
        name = brand?.name ?? ""
        hashtags = (brand?.hashtags ?? []).joined(separator: ", ")
        handle = brand?.handle ?? ""
        cta = brand?.cta ?? ""
        titleFont = brand?.fonts?["title"]?.string ?? ""
        captionFont = brand?.fonts?["caption"]?.string ?? ""
        let pal = brand?.palette ?? ["primary": "#1F1A17", "accent": "#FFC23D", "ink": "#FFFFFF", "paper": "#F3EDE4"]
        colors = pal.mapValues { Color(hex: $0) }
        loaded = true
    }
}
