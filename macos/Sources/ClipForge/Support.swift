import AppKit
import ClipForgeCore
import Security
import SwiftUI
import UniformTypeIdentifiers

// MARK: theme

extension Color {
    static let tally = Color(red: 1.0, green: 0.70, blue: 0.24)

    init(hex: String) {
        let h = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        let v = UInt64(h, radix: 16) ?? 0
        self.init(red: Double((v >> 16) & 0xFF) / 255, green: Double((v >> 8) & 0xFF) / 255, blue: Double(v & 0xFF) / 255)
    }

    var hex: String {
        let c = NSColor(self).usingColorSpace(.sRGB) ?? .black
        return String(format: "#%02X%02X%02X", Int(c.redComponent * 255), Int(c.greenComponent * 255), Int(c.blueComponent * 255))
    }
}

// MARK: Keychain

enum Keychain {
    static let service = "app.clipforge.mac"

    static func get(_ account: String) -> String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                kSecAttrAccount as String: account, kSecReturnData as String: true]
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }

    static func set(_ account: String, _ value: String) {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                kSecAttrAccount as String: account]
        SecItemDelete(q as CFDictionary)
        guard !value.isEmpty else { return }
        var add = q
        add[kSecValueData as String] = Data(value.utf8)
        SecItemAdd(add as CFDictionary, nil)
    }
}

// MARK: panels

enum Panels {
    static func open(types: [UTType], multiple: Bool = false) -> [URL] {
        let p = NSOpenPanel()
        p.allowedContentTypes = types
        p.allowsMultipleSelection = multiple
        p.canChooseDirectories = false
        return p.runModal() == .OK ? p.urls : []
    }

    static func reveal(_ url: URL) { NSWorkspace.shared.activateFileViewerSelecting([url]) }
}

// MARK: layout

/// Wraps children onto new lines, like text. Used for the transcript.
struct FlowLayout: Layout {
    var spacing: CGFloat = 3
    var lineSpacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxW = proposal.width ?? 640
        var x: CGFloat = 0, y: CGFloat = 0, line: CGFloat = 0, widest: CGFloat = 0
        for s in subviews {
            let sz = s.sizeThatFits(.unspecified)
            if x > 0 && x + sz.width > maxW {
                y += line + lineSpacing
                x = 0
                line = 0
            }
            x += sz.width + spacing
            line = max(line, sz.height)
            widest = max(widest, x)
        }
        return CGSize(width: min(widest, maxW), height: y + line)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, line: CGFloat = 0
        for s in subviews {
            let sz = s.sizeThatFits(.unspecified)
            if x > bounds.minX && x + sz.width > bounds.maxX {
                y += line + lineSpacing
                x = bounds.minX
                line = 0
            }
            s.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(sz))
            x += sz.width + spacing
            line = max(line, sz.height)
        }
    }
}

// MARK: building blocks

struct Panel<Content: View>: View {
    var title: String
    var subtitle: String? = nil
    var trailing: AnyView? = nil
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(title).font(.headline)
                Spacer()
                trailing
            }
            if let subtitle { Text(subtitle).font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
            content
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color(nsColor: .controlBackgroundColor)))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.primary.opacity(0.08)))
    }
}

struct Tile: View {
    var title: String
    var about: String
    var selected = false
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.subheadline.weight(.semibold))
                Text(about).font(.caption).foregroundStyle(.secondary).lineLimit(3).multilineTextAlignment(.leading)
            }
            .padding(10)
            .frame(maxWidth: .infinity, minHeight: 74, alignment: .topLeading)
            .background(RoundedRectangle(cornerRadius: 9).fill(selected ? Color.tally.opacity(0.16) : Color.primary.opacity(0.04)))
            .overlay(RoundedRectangle(cornerRadius: 9).strokeBorder(selected ? Color.tally : Color.primary.opacity(0.1)))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

struct ItemRow: View {
    var title: String
    var detail: String
    var onRemove: () -> Void

    var body: some View {
        HStack {
            Text(title).fontWeight(.semibold)
            Text(detail).foregroundStyle(.secondary).lineLimit(1)
            Spacer()
            Button("Remove", action: onRemove).controlSize(.small)
        }
        .padding(.vertical, 6).padding(.horizontal, 10)
        .background(RoundedRectangle(cornerRadius: 8).strokeBorder(Color.primary.opacity(0.1)))
    }
}

struct Stat: View {
    var label: String
    var value: String
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(label.uppercased()).font(.caption2.weight(.semibold)).foregroundStyle(.secondary).tracking(0.8)
            Text(value).font(.system(.title2, design: .rounded).weight(.bold)).monospacedDigit()
        }
    }
}

/// One word of the transcript, clickable.
struct WordChip: View {
    let word: Word
    var picked = false
    var inHook = false
    var marker: String? = nil
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 1) {
                Text(word.text)
                    .strikethrough(word.cut, color: strikeColor)
                    .foregroundStyle(word.cut ? Color.secondary.opacity(0.6) : (picked ? Color.black : Color.primary))
                if let marker { Text(marker).font(.system(size: 8)).foregroundStyle(Color.tally).baselineOffset(6) }
            }
            .padding(.horizontal, 3).padding(.vertical, 1)
            .background(RoundedRectangle(cornerRadius: 4).fill(picked ? Color.tally : Color.clear))
            .overlay(alignment: .bottom) { if inHook { Rectangle().fill(Color.tally).frame(height: 2) } }
        }
        .buttonStyle(.plain)
        .help(word.cut ? "Cut: \(word.reason ?? "manual"). Click to restore." : formatSeconds(word.start))
    }

    var strikeColor: Color {
        switch word.reason {
        case "filler": return .orange
        case "retake": return .blue
        default: return .secondary
        }
    }
}
