import AVFoundation
import AppKit
import ClipForgeCore
import SwiftUI
import UniformTypeIdentifiers

// MARK: transcript

/// The video as a page of words, one sentence per row.
@MainActor
struct TranscriptView: View {
    @Environment(AppModel.self) private var model
    enum Mode { case cut, pick }
    var mode: Mode

    var body: some View {
        let st = model.state
        let pops = Set((st?.popups ?? []).filter { $0.enabled != false }.map(\.wordId))
        let fx = Set((st?.effects ?? []).compactMap(\.wordId))
        let move = st?.hook.move
        LazyVStack(alignment: .leading, spacing: 6) {
            ForEach(Array(sentences(st?.allWords ?? []).enumerated()), id: \.offset) { _, sent in
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(formatSeconds(sent.first?.start)).font(.caption.monospaced()).foregroundStyle(.secondary).frame(width: 44, alignment: .leading)
                    FlowLayout {
                        ForEach(sent) { w in
                            WordChip(word: w,
                                     picked: mode == .pick && model.pickedWord == w.id,
                                     inHook: move.map { w.id >= $0[0] && w.id <= $0[1] } ?? false,
                                     marker: pops.contains(w.id) ? "◆" : (fx.contains(w.id) ? "✦" : nil)) {
                                tap(w)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    if mode == .cut, let a = sent.first?.id, let b = sent.last?.id {
                        Button("Open with this") { Task { await model.apply(["op": "move_hook", "start_id": .number(Double(a)), "end_id": .number(Double(b))]) } }
                            .controlSize(.small)
                            .help("Cold open: play this line first")
                    }
                }
                Divider().opacity(0.4)
            }
        }
        .font(.system(size: mode == .cut ? 15 : 13))
    }

    func tap(_ w: Word) {
        switch mode {
        case .pick: model.pickedWord = w.id
        case .cut: Task { await model.apply(["op": .string(w.cut ? "restore_words" : "cut_words"), "ids": [.number(Double(w.id))]]) }
        }
    }
}

// MARK: 01 Cut

@MainActor
struct CutView: View {
    @Environment(AppModel.self) private var model
    @State private var pause = 0.4
    @State private var fillers = true
    @State private var soft = false
    @State private var retakes = true
    @State private var hook = ""
    @State private var language = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if model.state?.transcribed != true {
                Panel(title: "First, the words",
                      subtitle: "Transcription runs on this Mac with word timings. Or import a transcript JSON (Whisper or ClipForge).") {
                    HStack {
                        Picker("Language", selection: $language) {
                            Text("Auto-detect").tag("")
                            Text("English").tag("en"); Text("Tamil").tag("ta"); Text("Hindi").tag("hi")
                            Text("Arabic").tag("ar"); Text("Spanish").tag("es"); Text("French").tag("fr")
                        }
                        .frame(width: 220)
                        Button("Transcribe") { Task { await model.transcribe(language: language.isEmpty ? nil : language) } }
                            .buttonStyle(.borderedProminent).disabled(model.busy != nil)
                        Button("Import Transcript…") {
                            if let u = Panels.open(types: [.json]).first { Task { await model.importTranscript(u) } }
                        }
                    }
                }
            } else {
                Panel(title: "Auto cut", subtitle: "Removes pauses, ums and retakes. Keeps your best take and the line that hooks.") {
                    HStack(spacing: 16) {
                        Stepper(value: $pause, in: 0.1...3, step: 0.1) { Text("Cut pauses over \(pause, specifier: "%.1f")s") }
                        Toggle("um · uh · erm", isOn: $fillers)
                        Toggle("like · basically", isOn: $soft)
                        Toggle("retakes", isOn: $retakes)
                        Spacer()
                        Button("Auto Cut") {
                            Task { await model.apply(["op": "auto_cut", "pause_max": .number(pause), "fillers": .bool(fillers),
                                                      "soft_fillers": .bool(soft), "retakes": .bool(retakes)]) }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .toggleStyle(.checkbox)
                }
                Panel(title: "Your video is a page of words",
                      subtitle: "Click a word to cut it, click again to bring it back. “Open with this” makes a line the cold-open hook. Orange strike: filler. Blue: retake.") {
                    HStack {
                        TextField("Hook title for the first 3 seconds", text: $hook)
                        Button("Save Hook") { Task { await model.apply(["op": "set_hook_title", "text": .string(hook)]) } }
                        if model.state?.hook.move != nil {
                            Button("Restore Original Order") { Task { await model.apply(["op": "clear_hook_move"]) } }
                        }
                    }
                    TranscriptView(mode: .cut)
                }
            }
        }
        .onAppear {
            pause = model.state?.pauseMax ?? 0.4
            hook = model.state?.hook.title ?? ""
        }
    }
}

// MARK: 02 Style

@MainActor
struct StyleView: View {
    @Environment(AppModel.self) private var model
    @State private var fxCategory = ""
    @State private var graphicType = "counter"
    @State private var fields: [String: String] = [:]
    @State private var brollMode = "full"
    @State private var pace = "balanced"
    @State private var position = 0.8

    static let fieldHints = ["title": "Title", "subtitle": "Subtitle", "value": "Number, e.g. 40", "prefix": "Prefix, e.g. $",
                             "suffix": "Suffix, e.g. %", "label": "Label", "labels": "Labels, comma separated",
                             "values": "Values, comma separated", "items": "Items, comma separated", "text": "Text",
                             "attribution": "Who said it", "handle": "@handle", "number": "Number"]

    var body: some View {
        let st = model.state
        let meta = model.meta
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Start from a recipe",
                  subtitle: "Sets the look, frame, music, captions, pacing, pop-ups, B-roll and end card for the kind of video you made. Everything stays editable.",
                  trailing: AnyView(Picker("Frame", selection: Binding(get: { st?.aspect ?? "9:16" },
                                                                        set: { a in Task { await model.apply(["op": "set_aspect", "aspect": .string(a)]) } })) {
                      ForEach(meta?.aspects ?? [], id: \.self) { Text($0).tag($0) }
                  }.pickerStyle(.segmented).frame(width: 240))) {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 170), spacing: 8)], spacing: 8) {
                    ForEach(Meta.ordered(meta?.recipes ?? [:], Meta.recipeOrder)) { item in
                        Tile(title: item.value.label, about: item.value.about) { Task { await model.apply(["op": "apply_recipe", "recipe": .string(item.key)]) } }
                    }
                }
            }
            Panel(title: "One video, five looks") {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 8)], spacing: 8) {
                    ForEach(Meta.ordered(meta?.looks ?? [:], Meta.lookOrder)) { item in
                        LookCard(key: item.key, info: item.value, brand: st?.brand, selected: st?.look == item.key) {
                            Task { await model.apply(["op": "set_look", "look": .string(item.key)]) }
                        }
                    }
                }
            }
            Panel(title: "Captions") {
                HStack(spacing: 18) {
                    Stepper("Words per line: \(st?.captions.wordsPerLine ?? 3)", onIncrement: {
                        Task { await model.apply(["op": "set_captions", "words_per_line": .number(Double(min(5, (st?.captions.wordsPerLine ?? 3) + 1)))]) }
                    }, onDecrement: {
                        Task { await model.apply(["op": "set_captions", "words_per_line": .number(Double(max(1, (st?.captions.wordsPerLine ?? 3) - 1)))]) }
                    })
                    Picker("Animation", selection: Binding(get: { st?.captions.animation ?? "pop" },
                                                           set: { v in Task { await model.apply(["op": "set_captions", "animation": .string(v)]) } })) {
                        Text("Pop").tag("pop"); Text("Bounce").tag("bounce"); Text("Rise").tag("rise"); Text("None").tag("none")
                    }
                    .frame(width: 180)
                    Toggle("Karaoke highlight", isOn: Binding(get: { st?.captions.karaoke ?? true },
                                                              set: { v in Task { await model.apply(["op": "set_captions", "karaoke": .bool(v)]) } }))
                    Toggle("Numbers and names in accent", isOn: Binding(get: { (st?.captions.emphasis ?? "auto") == "auto" },
                                                                         set: { v in Task { await model.apply(["op": "set_captions", "emphasis": .string(v ? "auto" : "none")]) } }))
                }
                .toggleStyle(.checkbox)
                HStack {
                    Text("Height")
                    Slider(value: $position, in: 0.4...0.9) { editing in
                        if !editing { Task { await model.apply(["op": "set_captions", "position": .number(position)]) } }
                    }
                    Text("\(Int(position * 100))%").monospacedDigit().frame(width: 40)
                    Picker("Landscape video", selection: Binding(get: { st?.fit ?? "fill" },
                                                                 set: { v in Task { await model.apply(["op": "set_fit", "fit": .string(v)]) } })) {
                        Text("Crop to fill").tag("fill"); Text("Blurred background").tag("blur")
                    }
                    .frame(width: 280)
                }
            }
            Panel(title: "Smart pop-ups",
                  subtitle: "A number becomes a big number; a name or place becomes a card, or your photo if one is named after it. At most one every 4 seconds, away from your face.",
                  trailing: AnyView(HStack {
                      Button("Add Photos…") {
                          let urls = Panels.open(types: [.image], multiple: true)
                          if !urls.isEmpty { Task { _ = await model.upload(kind: "popups", files: urls); model.say("\(urls.count) photos added. Press Find Pop-ups.") } }
                      }
                      Button("Find Pop-ups") { Task { await model.apply(["op": "auto_popups", "every": 4]) } }
                  })) {
                ForEach(st?.popups ?? []) { p in
                    HStack {
                        Toggle(isOn: Binding(get: { p.enabled != false },
                                             set: { v in Task { await model.apply(["op": "toggle_popup", "popup_id": .string(p.id), "enabled": .bool(v)]) } })) {
                            Text(p.text).fontWeight(.semibold)
                        }
                        .toggleStyle(.checkbox)
                        Text("\(p.kind) · on “\(model.wordText(p.wordId))”").foregroundStyle(.secondary)
                        Spacer()
                        Button("Remove") { Task { await model.apply(["op": "remove_popup", "popup_id": .string(p.id)]) } }.controlSize(.small)
                    }
                }
            }
            Panel(title: "Pick a word", subtitle: pickedHint) {
                ScrollView { TranscriptView(mode: .pick) }.frame(maxHeight: 170)
            }
            Panel(title: "Effects, one tap each",
                  trailing: AnyView(Picker("Category", selection: $fxCategory) {
                      Text("All effects").tag("")
                      ForEach(Array(Set((meta?.effects ?? []).map(\.category))).sorted(), id: \.self) { Text($0.capitalized).tag($0) }
                  }.frame(width: 200))) {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 8)], spacing: 8) {
                    ForEach((meta?.effects ?? []).filter { fxCategory.isEmpty || $0.category == fxCategory }) { e in
                        Tile(title: e.label, about: e.about) { addEffect(e.name) }
                    }
                }
                ForEach(st?.effects ?? []) { e in
                    ItemRow(title: meta?.effects.first { $0.name == e.name }?.label ?? e.name,
                            detail: "at “\(model.wordText(e.wordId))”\(e.source == "pace" ? " · pacing" : "")") {
                        Task { await model.apply(["op": "remove_effect", "effect_id": .string(e.id)]) }
                    }
                }
            }
            Panel(title: "Motion graphics", subtitle: "Pick a word above, choose a graphic and fill it in. Only use numbers you actually say.") {
                HStack {
                    Picker("Graphic", selection: $graphicType) {
                        ForEach(meta?.graphics ?? []) { g in Text(g.label).tag(g.type) }
                    }
                    .frame(width: 240)
                    Button("Add at Picked Word") { addGraphic() }.buttonStyle(.borderedProminent)
                }
                FlowLayout(spacing: 8, lineSpacing: 8) {
                    ForEach(meta?.graphics.first { $0.type == graphicType }?.fields ?? [], id: \.self) { f in
                        TextField(Self.fieldHints[f] ?? f, text: Binding(get: { fields[f] ?? "" }, set: { fields[f] = $0 }))
                            .frame(width: 200)
                    }
                }
                ForEach(Array((st?.graphics ?? []).enumerated()), id: \.offset) { _, g in
                    ItemRow(title: meta?.graphics.first { $0.type == g["type"]?.string }?.label ?? (g["type"]?.string ?? ""),
                            detail: graphicDetail(g)) {
                        Task { await model.apply(["op": "remove_graphic", "graphic_id": g["id"] ?? .null]) }
                    }
                }
            }
            HStack(alignment: .top, spacing: 14) {
                Panel(title: "B-roll",
                      subtitle: "Add clips or photos named after what they show (city-skyline.mp4) and press Find B-roll. With a word picked and one file, it goes there.",
                      trailing: AnyView(Button("Find B-roll") { Task { await model.apply(["op": "auto_broll", "every": 6]) } })) {
                    HStack {
                        Button("Add Files…") { addBroll() }
                        Picker("Mode", selection: $brollMode) { Text("Full frame").tag("full"); Text("Picture-in-picture").tag("pip") }
                            .frame(width: 240)
                    }
                    ForEach(st?.cutaways ?? []) { c in
                        ItemRow(title: URL(fileURLWithPath: c.path).lastPathComponent,
                                detail: "\(c.mode) · at “\(model.wordText(c.wordId))” · \(formatSeconds(c.duration))") {
                            Task { await model.apply(["op": "remove_cutaway", "cutaway_id": .string(c.id)]) }
                        }
                    }
                }
                Panel(title: "Pacing", subtitle: "Subtle camera moves wherever a shot holds too long, on the music beat.") {
                    Picker("Pace", selection: $pace) {
                        Text("Calm · every 6s").tag("calm"); Text("Balanced · every 4s").tag("balanced"); Text("Fast · every 2.6s").tag("fast")
                    }
                    Button("Apply Pacing") { Task { await model.apply(["op": "auto_pace", "level": .string(pace)]) } }
                }
                .frame(maxWidth: 320)
            }
        }
        .onAppear {
            position = st?.captions.position ?? 0.8
            pace = st?.pace ?? "balanced"
        }
        .onChange(of: graphicType) { _, _ in prefill() }
    }

    func graphicDetail(_ g: [String: JSONValue]) -> String {
        let what = [g["title"], g["text"], g["value"]].compactMap { $0?.string }.first.map { "\($0) · " } ?? ""
        let place = g["type"]?.string == "end_card" ? "at the end" : "at “\(model.wordText(g["word_id"]?.int))”"
        return what + place
    }

    var pickedHint: String {
        model.pickedWord.map { "Placing at “\(model.wordText($0))”. Now tap an effect or add a graphic." }
            ?? "Click a word to choose where effects, graphics and B-roll start."
    }

    func addEffect(_ name: String) {
        guard let w = model.pickedWord else { return model.say("Pick a word first.") }
        var c: Command = ["op": "add_effect", "name": .string(name), "word_id": .number(Double(w))]
        if name == "sticker" || name == "glass_widget" {
            c["params"] = ["text": .string(model.wordText(w).trimmingCharacters(in: .punctuationCharacters))]
        }
        let cmd = c
        Task { await model.apply(cmd) }
    }

    func prefill() {
        fields = [:]
        let b = model.state?.brand
        if graphicType == "lower_third" { fields["title"] = b?.name ?? ""; fields["subtitle"] = b?.handle ?? "" }
        if graphicType == "end_card" { fields["text"] = b?.cta ?? ""; fields["handle"] = b?.handle ?? "" }
    }

    func addGraphic() {
        guard let st = model.state else { return }
        guard let w = model.pickedWord ?? (graphicType == "end_card" ? st.allWords.last?.id : nil) else {
            return model.say("Pick a word first.")
        }
        var c: Command = ["op": "add_graphic", "type": .string(graphicType), "word_id": .number(Double(w))]
        for (k, v) in fields where !v.trimmingCharacters(in: .whitespaces).isEmpty {
            let parts = v.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }
            switch k {
            case "labels", "items": c[k] = .array(parts.map { .string($0) })
            case "values": c[k] = .array(parts.compactMap { Double($0) }.map { .number($0) })
            case "number": c[k] = Double(v).map { .number($0) } ?? .string(v)
            default: c[k] = .string(v)
            }
        }
        let cmd = c
        Task { await model.apply(cmd) }
    }

    func addBroll() {
        let urls = Panels.open(types: [.movie, .image], multiple: true)
        guard !urls.isEmpty else { return }
        Task {
            let paths = await model.upload(kind: "broll", files: urls)
            if paths.count == 1, let w = model.pickedWord {
                await model.apply(["op": "add_cutaway", "word_id": .number(Double(w)), "path": .string(paths[0]), "mode": .string(brollMode)])
            } else {
                model.say("\(paths.count) files added. Press Find B-roll.")
            }
        }
    }
}

@MainActor
struct LookCard: View {
    var key: String
    var info: Info
    var brand: Brand?
    var selected: Bool
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 0) {
                ZStack(alignment: .bottom) {
                    LinearGradient(colors: [Color(white: 0.28), Color(white: 0.09)], startPoint: .top, endPoint: .bottom)
                    sample.padding(.bottom, 12)
                }
                .frame(height: 86)
                VStack(alignment: .leading, spacing: 2) {
                    Text(info.label).font(.subheadline.weight(.semibold))
                    Text(info.about).font(.caption).foregroundStyle(.secondary).lineLimit(3)
                }
                .padding(9)
            }
            .background(Color.primary.opacity(0.04))
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(selected ? Color.tally : Color.primary.opacity(0.1), lineWidth: selected ? 2 : 1))
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder var sample: some View {
        let accent = Color(hex: brand?.palette["accent"] ?? "#FFC23D")
        let primary = Color(hex: brand?.palette["primary"] ?? "#1F1A17")
        let paper = Color(hex: brand?.palette["paper"] ?? "#F3EDE4")
        switch key {
        case "editorial":
            (Text("your ").foregroundColor(.white) + Text("look").foregroundColor(accent)).font(.system(size: 15, design: .serif))
        case "bold":
            (Text("YOUR ").foregroundColor(.white) + Text("LOOK").foregroundColor(accent)).font(.system(size: 16, weight: .black))
        case "soft":
            Text("your look").font(.system(size: 14, weight: .medium)).foregroundStyle(primary)
                .padding(.horizontal, 8).padding(.vertical, 2).background(Capsule().fill(paper))
        case "paper":
            Text("your look").font(.system(size: 13, weight: .bold, design: .monospaced)).foregroundStyle(primary)
                .padding(.horizontal, 6).padding(.vertical, 2).background(Rectangle().fill(paper))
        default:
            (Text("YOUR ").foregroundColor(.white) + Text("LOOK").foregroundColor(accent)).font(.system(size: 16, weight: .heavy))
                .shadow(color: .black, radius: 0, x: 0, y: 2)
        }
    }
}

// MARK: 03 Sound

@MainActor
struct SoundView: View {
    @Environment(AppModel.self) private var model
    @State private var preview: AVPlayer?
    @State private var playing: String?
    @State private var gain = -20.0
    @State private var intensity = 0.4

    var body: some View {
        let st = model.state
        let mood = st?.music?["mood"]?.string
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Music that fits",
                  subtitle: "Made on this Mac to the exact length of your video, so there is nothing to license. Your own tracks tagged in music/library.json are used first.") {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 180), spacing: 8)], spacing: 8) {
                    ForEach(Meta.ordered(model.meta?.moods ?? [:], Meta.moodOrder)) { item in
                        let key = item.key, info = item.value
                        VStack(alignment: .leading, spacing: 6) {
                            Text(info.label).font(.subheadline.weight(.semibold))
                            Text(info.about).font(.caption).foregroundStyle(.secondary).lineLimit(3)
                            HStack {
                                Button(playing == key ? "Stop" : "Preview") { toggle(key) }.controlSize(.small)
                                Button(mood == key ? "In Use" : "Use") {
                                    Task { await model.apply(["op": "set_music_mood", "mood": .string(key), "gain_db": .number(gain), "duck": true]) }
                                }
                                .controlSize(.small)
                                .buttonStyle(.borderedProminent)
                                .tint(mood == key ? Color.tally : Color.gray)
                            }
                        }
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 9).strokeBorder(mood == key ? Color.tally : Color.primary.opacity(0.1)))
                    }
                }
            }
            Panel(title: "Your own track", subtitle: "Use music you have the rights to. It ducks under your voice.") {
                HStack {
                    Button("Choose Audio…") {
                        guard let u = Panels.open(types: [.audio]).first else { return }
                        Task {
                            if let path = await model.upload(kind: "music", files: [u]).first {
                                await model.apply(["op": "set_music", "path": .string(path), "gain_db": .number(gain), "duck": true])
                            }
                        }
                    }
                    Text(musicLabel).foregroundStyle(.secondary)
                    Spacer()
                    if st?.music != nil { Button("Remove Music") { Task { await model.apply(["op": "set_music", "path": ""]) } } }
                }
                HStack {
                    Text("Music level")
                    Slider(value: $gain, in: -30...(-4), step: 1) { editing in if !editing { reapplyMusic() } }
                    Text("\(Int(gain)) dB").monospacedDigit().frame(width: 52)
                }
            }
            Panel(title: "Sound effects",
                  subtitle: "Whoosh on transitions and B-roll, pop on pop-ups and graphics, ding when a number lands, riser into chapters, impact under the hook.") {
                Toggle("On", isOn: Binding(get: { st?.sfx?.enabled ?? true },
                                           set: { v in Task { await model.apply(["op": "set_sfx", "enabled": .bool(v)]) } }))
                    .toggleStyle(.checkbox)
                HStack {
                    Text("Intensity")
                    Slider(value: $intensity, in: 0.05...1) { editing in
                        if !editing { Task { await model.apply(["op": "set_sfx", "intensity": .number(intensity)]) } }
                    }
                    Text("\(Int(intensity * 100))%").monospacedDigit().frame(width: 44)
                }
            }
            Panel(title: "Loudness", subtitle: "Reels, TikTok and Shorts play around −14 LUFS.") {
                Stepper(value: Binding(get: { st?.loudness ?? -14 },
                                       set: { v in Task { await model.apply(["op": "set_loudness", "lufs": .number(v)]) } }),
                        in: -24 ... -9, step: 0.5) {
                    Text("Target \(st?.loudness ?? -14, specifier: "%.1f") LUFS")
                }
            }
        }
        .onAppear {
            gain = st?.music?["gain_db"]?.double ?? -20
            intensity = st?.sfx?.intensity ?? 0.4
        }
        .onDisappear { preview?.pause() }
    }

    var musicLabel: String {
        guard let m = model.state?.music else { return "No music" }
        if let p = m["path"]?.string { return URL(fileURLWithPath: p).lastPathComponent }
        return "\(model.meta?.moods[m["mood"]?.string ?? ""]?.label ?? "") (generated)"
    }

    func toggle(_ mood: String) {
        if playing == mood {
            preview?.pause()
            playing = nil
            return
        }
        guard let url = model.client?.moodPreviewURL(mood) else { return }
        preview = AVPlayer(url: url)
        preview?.play()
        playing = mood
    }

    func reapplyMusic() {
        guard let m = model.state?.music else { return }
        if let p = m["path"]?.string, m["mood"] == nil {
            Task { await model.apply(["op": "set_music", "path": .string(p), "gain_db": .number(gain), "duck": m["duck"] ?? true]) }
        } else if let mood = m["mood"]?.string {
            Task { await model.apply(["op": "set_music_mood", "mood": .string(mood), "gain_db": .number(gain), "duck": m["duck"] ?? true]) }
        }
    }
}

// MARK: 04 Finish

@MainActor
struct FinishView: View {
    @Environment(AppModel.self) private var model
    @State private var platform = "reels"
    @State private var caption = ""

    var body: some View {
        let st = model.state
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Pre-flight",
                  trailing: AnyView(HStack {
                      Picker("Platform", selection: $platform) {
                          Text("Instagram Reels").tag("reels"); Text("TikTok").tag("tiktok"); Text("YouTube Shorts").tag("shorts"); Text("LinkedIn").tag("linkedin")
                      }
                      .frame(width: 220)
                      Button("Check") { Task { await model.runPreflight(platform: platform) } }
                  })) {
                ForEach(model.preflight) { issue in
                    HStack {
                        RoundedRectangle(cornerRadius: 2).fill(color(issue.level)).frame(width: 4)
                        Text(issue.message).fixedSize(horizontal: false, vertical: true)
                        Spacer()
                        if let fix = issue.fix {
                            Button("Fix") { Task { await model.apply(fix); await model.runPreflight(platform: platform) } }.controlSize(.small)
                        }
                    }
                    .padding(8)
                    .background(RoundedRectangle(cornerRadius: 8).strokeBorder(Color.primary.opacity(0.1)))
                }
            }
            Panel(title: "Render") {
                HStack {
                    Button("Preview 540×960") { Task { await model.render("preview") } }
                    Button("Final 1080×1920") { Task { await model.render("final") } }.buttonStyle(.borderedProminent)
                    Spacer()
                    if let dir = model.projectDir, st?.latestRender != nil {
                        Button("Show in Finder") { Panels.reveal(dir.appendingPathComponent(st!.latestRender!)) }
                    }
                }
                .disabled(model.busy != nil)
                if let renders = st?.renders, !renders.isEmpty, let dir = model.projectDir {
                    HStack {
                        ForEach(renders.keys.sorted(), id: \.self) { q in
                            Button("\(q).mp4") { NSWorkspace.shared.open(dir.appendingPathComponent(renders[q]!)) }.controlSize(.small)
                        }
                        Button("captions.srt") { Panels.reveal(dir.appendingPathComponent("renders/captions.srt")) }.controlSize(.small)
                        Button("licenses.txt") { NSWorkspace.shared.open(dir.appendingPathComponent("renders/licenses.txt")) }.controlSize(.small)
                    }
                }
            }
            Panel(title: "One reel becomes a whole post",
                  subtitle: "Cover, 4:5 carousel (images and PDF), three story frames and the caption, in the same look. Ask Claude to write the copy first for sharper slides.",
                  trailing: AnyView(Button("Make Post Kit") { Task { await model.makePostKit(); await loadCaption() } }
                    .buttonStyle(.borderedProminent).disabled(model.busy != nil))) {
                if let kit = st?.postKit {
                    ScrollView(.horizontal) {
                        HStack(spacing: 8) {
                            ForEach([kit.cover] + kit.carousel + kit.stories, id: \.self) { f in
                                AsyncImage(url: model.fileURL(f).flatMap { URL(string: "\($0.absoluteString)?v=\(model.renderNonce)") }) { img in
                                    img.resizable().scaledToFit()
                                } placeholder: { Color.primary.opacity(0.06) }
                                .frame(height: 170)
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                                .onTapGesture { if let d = model.projectDir { NSWorkspace.shared.open(d.appendingPathComponent(f)) } }
                            }
                        }
                    }
                    HStack {
                        Button("Copy Caption") {
                            NSPasteboard.general.clearContents()
                            NSPasteboard.general.setString(caption, forType: .string)
                            model.say("Caption copied")
                        }
                        if let d = model.projectDir {
                            Button("Open Carousel PDF") { NSWorkspace.shared.open(d.appendingPathComponent(kit.carouselPdf)) }
                            Button("Show Folder") { Panels.reveal(d.appendingPathComponent(kit.cover)) }
                        }
                    }
                    Text(caption).font(.callout).textSelection(.enabled)
                        .padding(10).frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 8).fill(Color.primary.opacity(0.05)))
                }
            }
        }
        .task {
            await model.runPreflight(platform: platform)
            await loadCaption()
        }
    }

    func color(_ level: String) -> Color {
        switch level {
        case "bad": return .red
        case "warn": return .orange
        case "good": return .green
        default: return .blue
        }
    }

    func loadCaption() async {
        guard let kit = model.state?.postKit, let url = model.fileURL(kit.caption),
              let (data, _) = try? await URLSession.shared.data(from: url) else { return }
        caption = String(decoding: data, as: UTF8.self)
    }
}
