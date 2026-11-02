import Foundation

// Mirrors of the engine's JSON. Snake_case keys are mapped with CodingKeys: the decoder's convertFromSnakeCase
// would also rewrite dictionary keys (e.g. word_id inside commands), which must round-trip unchanged.

public struct Info: Codable, Hashable, Sendable {
    public var label: String
    public var about: String
}

public struct EffectInfo: Codable, Hashable, Identifiable, Sendable {
    public var name: String
    public var label: String
    public var category: String
    public var duration: Double
    public var about: String
    public var id: String { name }
}

public struct GraphicType: Codable, Hashable, Identifiable, Sendable {
    public var type: String
    public var label: String
    public var duration: Double
    public var about: String
    public var fields: [String]
    public var id: String { type }
}

public struct Meta: Codable, Sendable {
    public var version: String
    public var looks: [String: Info]
    public var effects: [EffectInfo]
    public var shotTypes: [String: String]
    public var claude: Bool
    public var model: String
    public var home: String
    public var moods: [String: Info]
    public var recipes: [String: Info]
    public var graphics: [GraphicType]
    public var aspects: [String]
    public var sfx: [String: String]

    enum CodingKeys: String, CodingKey {
        case version, looks, effects, claude, model, home, moods, recipes, graphics, aspects, sfx
        case shotTypes = "shot_types"
    }

    public static let lookOrder = ["editorial", "bold", "creator", "soft", "paper"]
    public static let shotOrder = ["on_camera", "voiceover_clips", "faceless", "clips_text"]
    public static let moodOrder = ["uplifting", "focus", "cinematic", "tech", "warm"]
    public static let recipeOrder = ["thought_leader", "founder_story", "explainer", "podcast_clip", "product_demo"]

    /// Entries of a dictionary in a preferred order, unknown keys last.
    public static func ordered<V>(_ dict: [String: V], _ order: [String]) -> [Keyed<V>] {
        let known = order.compactMap { k in dict[k].map { Keyed(key: k, value: $0) } }
        let rest = dict.filter { !order.contains($0.key) }.sorted { $0.key < $1.key }.map { Keyed(key: $0.key, value: $0.value) }
        return known + rest
    }
}

public struct Keyed<V>: Identifiable {
    public let key: String
    public let value: V
    public var id: String { key }
}

public struct ProjectSummary: Codable, Hashable, Identifiable, Sendable {
    public var id: String
    public var name: String
    public var shotType: String?
    public var duration: Double?
    public var transcribed: Bool?

    enum CodingKeys: String, CodingKey {
        case id, name, duration, transcribed
        case shotType = "shot_type"
    }
}

public struct Word: Codable, Hashable, Identifiable, Sendable {
    public var id: Int
    public var text: String
    public var start: Double
    public var end: Double
    public var cut: Bool
    public var reason: String?
}

public struct EditSummary: Codable, Hashable, Sendable {
    public var before: Double?
    public var after: Double?
    public var cuts: Int
    public var removed: [String: Int]
}

public struct Hook: Codable, Hashable, Sendable {
    public var title: String
    public var move: [Int]?
}

public struct Captions: Codable, Hashable, Sendable {
    public var wordsPerLine: Int
    public var position: Double
    public var karaoke: Bool?
    public var animation: String?
    public var emphasis: String?

    enum CodingKeys: String, CodingKey {
        case position, karaoke, animation, emphasis
        case wordsPerLine = "words_per_line"
    }
}

public struct Popup: Codable, Hashable, Identifiable, Sendable {
    public var id: String
    public var wordId: Int
    public var kind: String
    public var text: String
    public var enabled: Bool?

    enum CodingKeys: String, CodingKey {
        case id, kind, text, enabled
        case wordId = "word_id"
    }
}

public struct EffectItem: Codable, Hashable, Identifiable, Sendable {
    public var id: String
    public var name: String
    public var wordId: Int?
    public var duration: Double?
    public var source: String?

    enum CodingKeys: String, CodingKey {
        case id, name, duration, source
        case wordId = "word_id"
    }
}

public struct Cutaway: Codable, Hashable, Identifiable, Sendable {
    public var id: String
    public var wordId: Int
    public var path: String
    public var duration: Double
    public var mode: String

    enum CodingKeys: String, CodingKey {
        case id, path, duration, mode
        case wordId = "word_id"
    }
}

public struct SfxSettings: Codable, Hashable, Sendable {
    public var enabled: Bool
    public var intensity: Double
}

public struct Brand: Codable, Hashable, Sendable {
    public var name: String?
    public var handle: String?
    public var cta: String?
    public var palette: [String: String]
    public var fonts: [String: JSONValue]?
    public var hashtags: [String]?
}

public struct PostKit: Codable, Hashable, Sendable {
    public var cover: String
    public var carousel: [String]
    public var carouselPdf: String
    public var stories: [String]
    public var caption: String

    enum CodingKeys: String, CodingKey {
        case cover, carousel, stories, caption
        case carouselPdf = "carousel_pdf"
    }
}

public struct ProjectState: Codable, Sendable {
    public var id: String
    public var name: String
    public var shotType: String?
    public var transcribed: Bool
    public var look: String
    public var aspect: String?
    public var hook: Hook
    public var captions: Captions
    public var pauseMax: Double
    public var popups: [Popup]
    public var effects: [EffectItem]
    public var cutaways: [Cutaway]?
    public var graphics: [[String: JSONValue]]?
    public var music: [String: JSONValue]?
    public var sfx: SfxSettings?
    public var loudness: Double?
    public var fit: String?
    public var pace: String?
    public var renders: [String: String]
    public var postKit: PostKit?
    public var sourceRel: String
    public var history: [String]
    public var brand: Brand
    public var summary: EditSummary
    public var words: [Word]?

    enum CodingKeys: String, CodingKey {
        case id, name, transcribed, look, aspect, hook, captions, popups, effects, cutaways, graphics, music, sfx
        case loudness, fit, pace, renders, history, brand, summary, words
        case shotType = "shot_type", pauseMax = "pause_max", postKit = "post_kit", sourceRel = "source_rel"
    }

    public var allWords: [Word] { words ?? [] }
    public func word(_ id: Int?) -> Word? { allWords.first { $0.id == id } }
    public var latestRender: String? { renders["final"] ?? renders["preview"] ?? renders["tiny"] }
}

public struct CommandResponse: Codable, Sendable {
    public var message: String
    public var state: ProjectState
}

public struct CommandsResponse: Codable, Sendable {
    public var messages: [String]
    public var state: ProjectState
}

public struct JobRef: Codable, Sendable { public var job: String }

public struct JobStatus: Codable, Sendable {
    public var status: String
    public var progress: Double?
    public var error: String?
    public var result: JSONValue?
}

public struct Plan: Codable, Sendable {
    public var summary: String
    public var model: String?
    public var commands: [Command]
}

public struct PreflightIssue: Codable, Hashable, Identifiable, Sendable {
    public var level: String
    public var message: String
    public var fix: Command?
    public var id: String { level + message }
}

public struct UploadResult: Codable, Sendable { public var path: String }

/// Group words into sentences the same way the engine and Studio do.
public func sentences(_ words: [Word], gap: Double = 0.9) -> [[Word]] {
    var out: [[Word]] = []
    var cur: [Word] = []
    for w in words {
        if let last = cur.last, w.start - last.end > gap {
            out.append(cur)
            cur = []
        }
        cur.append(w)
        if w.text.range(of: #"[.!?…।]["')\]]*$"#, options: .regularExpression) != nil {
            out.append(cur)
            cur = []
        }
    }
    if !cur.isEmpty { out.append(cur) }
    return out
}

public func formatSeconds(_ s: Double?) -> String {
    guard let s else { return "–" }
    if s >= 60 { return String(format: "%d:%02d", Int(s) / 60, Int(s.rounded()) % 60) }
    return String(format: "%.1fs", s)
}
