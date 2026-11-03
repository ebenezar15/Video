import ClipForgeCore
import XCTest

final class CoreTests: XCTestCase {
    let stateJSON = #"""
    {"id":"p1","name":"Demo","shot_type":"on_camera","transcribed":true,"look":"bold","aspect":"9:16",
     "hook":{"title":"How we grew","move":[10,16]},
     "captions":{"words_per_line":3,"position":0.8,"karaoke":true,"animation":"pop","emphasis":"auto"},
     "pause_max":0.4,"popups":[{"id":"a1","word_id":14,"kind":"number","text":"40%","enabled":true,"source":"auto"}],
     "effects":[{"id":"e1","name":"zoom_punch","word_id":3,"source":"pace","params":{"amount":0.1}}],
     "cutaways":[{"id":"c1","word_id":16,"path":"/x/dubai.jpg","duration":1.5,"mode":"pip","license":"your library","source":"manual"}],
     "graphics":[{"id":"g1","type":"counter","word_id":14,"value":"40","suffix":"%","source":"manual"}],
     "music":{"mood":"tech","gain_db":-21,"duck":true,"license":"Generated"},
     "sfx":{"enabled":true,"intensity":0.55},"loudness":-14,"fit":"fill","pace":"fast","post":null,
     "renders":{"tiny":"renders/tiny.mp4"},
     "post_kit":{"cover":"post/cover.jpg","carousel":["post/carousel-01.jpg"],"carousel_pdf":"post/carousel.pdf","stories":["post/story-1.jpg"],"caption":"post/caption.txt"},
     "source_rel":"media/source.mp4","history":["auto_cut()"],
     "brand":{"name":"S","handle":"@s","cta":"Follow","palette":{"primary":"#1F1A17","accent":"#FFC23D","ink":"#FFFFFF","paper":"#F3EDE4"},"fonts":{"title":null,"caption":null},"hashtags":["growth"],"hook_position":"top"},
     "summary":{"before":11.5,"after":7.73,"cuts":3,"removed":{"filler":2,"retake":2}},
     "words":[{"id":0,"text":"So","start":0.3,"end":0.5,"cut":false,"reason":null},
              {"id":1,"text":"um","start":0.7,"end":1.0,"cut":true,"reason":"filler"},
              {"id":2,"text":"this.","start":1.1,"end":1.4,"cut":false,"reason":null},
              {"id":3,"text":"Next","start":3.0,"end":3.3,"cut":false,"reason":null},
              {"id":4,"text":"one!","start":3.3,"end":3.6,"cut":false,"reason":null}]}
    """#

    func testDecodesProjectStateAndKeepsSnakeCaseInsideFreeFormFields() throws {
        let st = try JSONDecoder().decode(ProjectState.self, from: Data(stateJSON.utf8))
        XCTAssertEqual(st.shotType, "on_camera")
        XCTAssertEqual(st.captions.wordsPerLine, 3)
        XCTAssertEqual(st.popups.first?.wordId, 14)
        XCTAssertEqual(st.cutaways?.first?.mode, "pip")
        XCTAssertEqual(st.postKit?.carouselPdf, "post/carousel.pdf")
        XCTAssertEqual(st.sourceRel, "media/source.mp4")
        // free-form dictionaries must keep the engine's keys so they can be sent back as commands
        XCTAssertEqual(st.graphics?.first?["word_id"]?.int, 14)
        XCTAssertEqual(st.music?["gain_db"]?.double, -21)
        XCTAssertEqual(st.latestRender, "renders/tiny.mp4")
        XCTAssertEqual(st.word(1)?.reason, "filler")
    }

    func testSentences() throws {
        let st = try JSONDecoder().decode(ProjectState.self, from: Data(stateJSON.utf8))
        let s = sentences(st.allWords)
        XCTAssertEqual(s.map { $0.map(\.id) }, [[0, 1, 2], [3, 4]])
    }

    func testCommandsEncodeAsPlainJSON() throws {
        let cmd: Command = ["op": "add_graphic", "type": "counter", "word_id": 14, "values": [2, 7.5], "enabled": true]
        let data = try JSONEncoder().encode(cmd)
        let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertEqual(obj?["word_id"] as? Double, 14)
        XCTAssertEqual(obj?["op"] as? String, "add_graphic")
        XCTAssertEqual((obj?["values"] as? [Double]) ?? [], [2, 7.5])
        let back = try JSONDecoder().decode(Command.self, from: data)
        XCTAssertEqual(back, cmd)
    }

    func testPlanDecodesWithUntouchedKeys() throws {
        let json = #"{"summary":"s","model":"claude-opus-5-5","commands":[{"op":"move_hook","start_id":10,"end_id":16,"why":"hook"}]}"#
        let plan = try JSONDecoder().decode(Plan.self, from: Data(json.utf8))
        XCTAssertEqual(plan.commands.first?["start_id"]?.int, 10)
    }

    func testOrderedKeepsPreferredOrder() {
        let d = ["soft": 1, "bold": 2, "zeta": 3, "editorial": 4]
        XCTAssertEqual(Meta.ordered(d, Meta.lookOrder).map(\.key), ["editorial", "bold", "soft", "zeta"])
    }

    func testClaudeDesktopMergePreservesOtherServers() throws {
        let existing = Data(#"{"mcpServers":{"other":{"command":"x"}},"theme":"dark"}"#.utf8)
        let out = try ClaudeDesktop.merged(existing: existing, binary: "/usr/local/bin/clipforge", home: "/tmp/cf")
        let obj = try XCTUnwrap(JSONSerialization.jsonObject(with: out) as? [String: Any])
        let servers = try XCTUnwrap(obj["mcpServers"] as? [String: Any])
        XCTAssertNotNil(servers["other"])
        let cf = try XCTUnwrap(servers["clipforge"] as? [String: Any])
        XCTAssertEqual(cf["args"] as? [String], ["mcp"])
        XCTAssertEqual((cf["env"] as? [String: String])?["CLIPFORGE_HOME"], "/tmp/cf")
        XCTAssertEqual(obj["theme"] as? String, "dark")
        XCTAssertThrowsError(try ClaudeDesktop.merged(existing: Data("[1]".utf8), binary: "x", home: nil))
    }

    func testParseEngineURL() {
        XCTAssertEqual(EngineProcess.parseURL("ClipForge Studio on http://127.0.0.1:53122  (projects in /x)")?.port, 53122)
        XCTAssertNil(EngineProcess.parseURL("starting…"))
    }

    func testChildPathAddsToolFolders() {
        let p = EngineProcess.childPath("/usr/bin:/custom")
        XCTAssertTrue(p.hasPrefix("/opt/homebrew/bin"))
        XCTAssertTrue(p.contains("/custom"))
    }

    func testFileURLEncoding() {
        let c = EngineClient(base: URL(string: "http://127.0.0.1:9")!)
        XCTAssertEqual(c.fileURL("p 1", "post/cover image.jpg").absoluteString, "http://127.0.0.1:9/files/p%201/post/cover%20image.jpg")
    }

    func testPythonPreferenceFavoursBestSupportedVersions() {
        XCTAssertNil(EngineProcess.pythonRank(major: 3, minor: 9))   // macOS /usr/bin/python3 is often 3.9
        let order = [10, 11, 12, 13, 14, 15].sorted { EngineProcess.pythonRank(major: 3, minor: $0)! < EngineProcess.pythonRank(major: 3, minor: $1)! }
        XCTAssertEqual(order, [12, 13, 11, 10, 14, 15])
    }

    func testHeavyPackagesAreNeverCompiled() {
        for pkg in ["av", "ctranslate2", "onnxruntime", "tokenizers", "opencv-python-headless"] {
            XCTAssertTrue(EngineProcess.binaryOnly.split(separator: ",").contains(Substring(pkg)), pkg)
        }
    }
}
