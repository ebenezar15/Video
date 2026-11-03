import asyncio
import json
import subprocess
import threading
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from fixtures.make_fixture import build as build_fixture


@pytest.fixture(scope="session")
def fixture_media(tmp_path_factory):
    return build_fixture(tmp_path_factory.mktemp("media"))


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPFORGE_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture()
def project(home, fixture_media):
    from clipforge.project import Project
    from clipforge.transcript import import_transcript
    video, words = fixture_media
    p = Project.create(video, "demo")
    p.set_words(import_transcript(words))
    return p


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_type",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    return float(info["format"]["duration"]), v["width"], v["height"], any(s["codec_type"] == "audio" for s in info["streams"])


# --- editing logic ------------------------------------------------------------------------
def test_autocut_finds_fillers_and_retakes(project):
    from clipforge import autocut
    r = autocut.plan(project.words)
    text = {project.words[i].text: why for i, why in r.items()}
    assert text["um"] == "filler" and text["uh"] == "filler"
    assert r[2] == "retake" and r[3] == "retake"  # "I was," restarted as "I was going"
    assert 4 not in r and 5 not in r  # the kept take


def test_timeline_cuts_pauses_and_maps_words(project):
    from clipforge import commands as C
    from clipforge.timeline import build
    C.apply(project, {"op": "auto_cut"})
    tl = build(project.words, project.edit, project.meta["duration"])
    assert 7.0 < tl.duration < 8.5  # 11.5s source, ~3.8s removed
    outs = [tl.word_out[i][0] for i in tl.order]
    assert outs == sorted(outs)
    assert all(i not in tl.word_out for i in project.edit["deleted"])


def test_move_hook_plays_hook_first(project):
    from clipforge import commands as C
    from clipforge.timeline import build
    C.apply(project, {"op": "move_hook", "start_id": 10, "end_id": 16})
    tl = build(project.words, project.edit, project.meta["duration"])
    assert tl.order[0] == 10 and tl.word_out[10][0] < 0.1


def test_commands_validate_and_undo(project):
    from clipforge import commands as C
    with pytest.raises(C.CommandError):
        C.apply(project, {"op": "cut_words", "ids": [999]})
    with pytest.raises(C.CommandError):
        C.apply(project, {"op": "set_look", "look": "neon"})
    C.apply(project, {"op": "cut_words", "ids": [0]})
    assert project.edit["deleted"] == [0]
    assert project.undo().startswith("cut_words")
    assert project.edit["deleted"] == []


def test_popups_numbers_and_spacing(project):
    from clipforge import commands as C
    msg = C.apply(project, {"op": "auto_popups", "every": 4})
    texts = [x["text"] for x in project.edit["popups"]]
    assert "40%" in texts and "Dubai" not in texts  # Dubai is within 4s of 40%
    assert "pop-ups found" in msg


def test_popup_number_words():
    from clipforge.popups import detect
    from clipforge.timeline import build
    from clipforge.transcript import Word
    ws = [Word(i, t, i * 0.5, i * 0.5 + 0.4) for i, t in enumerate("We grew forty two percent last year".split())]
    found = detect(ws, build(ws, {"deleted": []}), every=0)
    assert found[0]["text"] == "42%"


def test_captions_ass_animation_emphasis_no_overlap(project):
    from clipforge.captions import build_ass
    from clipforge.looks import resolved
    from clipforge.project import load_brand
    from clipforge.timeline import build
    tl = build(project.words, project.edit, project.meta["duration"])
    edit = {**project.edit, "captions": {**project.edit["captions"], "animation": "bounce"}, "hook": {"title": "Hi", "move": None}}
    ass = build_ass(project.words, tl, edit, resolved("bold", load_brand()), 540, 960)
    assert "PlayResX: 540" in ass and r"\t(0,110" in ass and "Style: Hook" in ass
    accent = "&H003DC2FF"
    assert any("40%" in ln and accent in ln for ln in ass.splitlines() if ln.startswith("Dialogue"))
    events = [ln.split(",", 3)[1:3] for ln in ass.splitlines() if ln.startswith("Dialogue: 0")]
    def secs(t):
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    spans = sorted((secs(a), secs(b)) for a, b in events)
    assert all(b0 <= a1 + 1e-6 for (a0, b0), (a1, b1) in zip(spans, spans[1:]))


# --- rendering ----------------------------------------------------------------------------
def test_render_basic(project):
    from clipforge import commands as C, render
    C.apply(project, {"op": "auto_cut"})
    C.apply(project, {"op": "auto_popups"})
    C.apply(project, {"op": "set_hook_title", "text": "How we grew 40%"})
    out = render.render(project, "tiny")
    dur, w, h, audio = probe(out)
    assert (w, h) == (270, 480) and audio
    assert abs(dur - render.timeline_for(project).duration) < 0.15
    assert (project.dir / "renders" / "captions.srt").read_text().startswith("1\n")


def test_every_effect_renders(project):
    from clipforge import commands as C, render
    from clipforge.effects import E
    ids = [w.id for w in project.words]
    for i, name in enumerate(E):
        C.apply(project, {"op": "add_effect", "name": name, "word_id": ids[i % len(ids)], "params": {"text": "save"}})
    assert len(E) >= 30
    dur, w, h, _ = probe(render.render(project, "tiny"))
    assert (w, h) == (270, 480) and dur > 9


def test_every_graphic_renders_and_beats_popups(project, home):
    from clipforge import commands as C, render
    from clipforge.graphics import TYPES
    specs = {"lower_third": {"title": "Sadiq", "subtitle": "Founder"}, "counter": {"value": "40", "suffix": "%", "label": "growth"},
             "bar_chart": {"labels": ["Q1", "Q2"], "values": [2, 7], "title": "Posts"}, "chapter_card": {"title": "Part two", "number": 2},
             "quote_card": {"text": "The trick was simple.", "attribution": "Sadiq"}, "checklist": {"items": ["Post", "Reply"]},
             "end_card": {"text": "Follow", "handle": "@x"}}
    anchors = {"lower_third": 0, "chapter_card": 10, "counter": 14, "bar_chart": 18, "quote_card": 22, "checklist": 26, "end_card": 27}
    assert set(specs) == set(TYPES)
    for k, f in specs.items():
        C.apply(project, {"op": "add_graphic", "type": k, "word_id": anchors[k], **f})
    C.apply(project, {"op": "auto_popups"})
    out = render.render(project, "tiny")
    tl = json.loads((project.dir / "renders" / "timeline.json").read_text())
    assert len(tl["graphics"]) == 7
    assert not any(p["text"] == "40%" for p in tl["popups"])  # the counter owns that moment
    assert probe(out)[1:3] == (270, 480)


@pytest.mark.parametrize("look", ["editorial", "bold", "creator", "soft", "paper"])
def test_each_look_renders(project, look):
    from clipforge import commands as C, render
    C.apply(project, {"op": "set_look", "look": look})
    C.apply(project, {"op": "set_hook_title", "text": "Hook"})
    assert probe(render.render(project, "tiny"))[1:3] == (270, 480)


@pytest.mark.parametrize("aspect,size", [("4:5", (270, 336)), ("1:1", (270, 270)), ("16:9", (480, 270))])
def test_aspects(project, aspect, size):
    from clipforge import commands as C, render
    C.apply(project, {"op": "set_aspect", "aspect": aspect})
    assert probe(render.render(project, "tiny"))[1:3] == size


def test_music_moods_sfx_and_loudness(project):
    from clipforge import audio_gen, commands as C, render
    for mood in audio_gen.MOODS:
        wav = audio_gen.music(mood, 5.0)
        assert 4.9 < probe_audio(wav) < 5.1
    for name in audio_gen.SFX:
        assert audio_gen.sfx(name).exists()
    C.apply(project, {"op": "set_music_mood", "mood": "focus"})
    C.apply(project, {"op": "auto_popups"})
    C.apply(project, {"op": "set_hook_title", "text": "Hook"})
    out = render.render(project, "tiny")
    tl = json.loads((project.dir / "renders" / "timeline.json").read_text())
    assert {"impact", "pop"} <= {n for _, n in tl["sfx"]}
    assert "Generated by ClipForge" in (project.dir / "renders" / "licenses.txt").read_text()
    stats = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
    integrated = float(stats.split("Integrated loudness:")[1].split("I:")[1].split("LUFS")[0])
    assert abs(integrated + 14) < 1.5


def probe_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def test_broll_library_auto_and_pip(project, home):
    from clipforge import commands as C, render
    (home / "broll").mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:d=2", "-pix_fmt", "yuv420p",
                    str(home / "broll" / "simple-trick.mp4")], check=True)
    Image.new("RGB", (400, 300), (30, 120, 200)).save(home / "broll" / "dubai-skyline.jpg")
    msg = C.apply(project, {"op": "auto_broll", "every": 1})
    assert "dubai-skyline" in msg and "simple-trick" in msg  # "Dubai." and "trick"
    C.apply(project, {"op": "add_cutaway", "word_id": 16, "path": str(home / "broll" / "dubai-skyline.jpg"), "mode": "pip", "duration": 1.5})
    assert probe(render.render(project, "tiny"))[1:3] == (270, 480)
    assert "dubai-skyline.jpg" in (project.dir / "renders" / "licenses.txt").read_text()


def test_recipe_pace_and_preflight(project):
    from clipforge import commands as C, recipes
    C.update_brand({"name": "Sadiq", "handle": "@s", "cta": "Follow"})
    C.apply(project, {"op": "auto_cut"})
    issues = recipes.preflight(project)
    assert any("hook" in i["message"].lower() and i.get("fix") for i in issues)
    msg = C.apply(project, {"op": "apply_recipe", "recipe": "thought_leader"})
    assert "Thought leader" in msg and project.edit["aspect"] == "4:5" and project.edit["music"]["mood"] == "focus"
    assert {g["type"] for g in project.edit["graphics"]} >= {"lower_third", "end_card"}
    for i in recipes.preflight(project):
        if i.get("fix"):
            C.apply(project, i["fix"])
    assert recipes.preflight(project)[0]["level"] in ("good", "info")
    assert len(project.history_labels()) >= 3


def test_faceless_and_voiceover_shots(home, fixture_media, tmp_path):
    from clipforge import commands as C, render
    from clipforge.project import Project
    from clipforge.transcript import import_transcript
    video, words = fixture_media
    p = Project.create(video, "faceless", "faceless")
    p.set_words(import_transcript(words))
    assert probe(render.render(p, "tiny"))[1:3] == (270, 480)
    clip = tmp_path / "b.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:d=1.5", "-pix_fmt", "yuv420p", str(clip)], check=True)
    v = Project.create(video, "vo", "voiceover_clips")
    v.set_words(import_transcript(words))
    C.apply(v, {"op": "set_broll", "paths": [str(clip)]})
    dur, *_ = probe(render.render(v, "tiny"))
    assert abs(dur - render.timeline_for(v).duration) < 0.2


def test_post_kit(project):
    from clipforge import commands as C, render, repurpose
    C.apply(project, {"op": "auto_cut"})
    render.render(project, "tiny")
    C.apply(project, {"op": "set_post_copy", "title": "How we grew 40%", "slides": ["Post every day", "Hook first", "Reply fast"],
                      "caption": "We grew 40%.", "hashtags": ["growth", "founders"]})
    kit = repurpose.post_kit(project)["files"]
    assert Image.open(project.dir / kit["cover"]).size == (1080, 1920)
    assert len(kit["carousel"]) == 5 and Image.open(project.dir / kit["carousel"][0]).size == (1080, 1350)
    assert len(kit["stories"]) == 3
    assert "#growth" in (project.dir / kit["caption"]).read_text()
    assert (project.dir / kit["carousel_pdf"]).stat().st_size > 1000


# --- Claude integrations (no network) --------------------------------------------------------
def test_planner_parses_and_applies(project):
    from clipforge import commands as C, planner
    calls = {}

    class FakeMessages:
        def parse(self, **kw):
            calls.update(kw)
            plan = planner.Plan(summary="Tighter, with a stat.", commands=[
                planner.PlanCommand(op="auto_cut", why="Remove ums"),
                planner.PlanCommand(op="add_graphic", why="Show the growth", type="counter", word_id=14, value="40", suffix="%"),
                planner.PlanCommand(op="apply_recipe", why="LinkedIn", recipe="thought_leader"),
            ])
            return SimpleNamespace(parsed_output=plan, stop_reason="end_turn", model="claude-opus-5-5")

    client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))
    out = planner.plan(project, "make it LinkedIn ready with a stat", client=client)
    assert calls["model"] == planner.MODEL and calls["fallbacks"] == "default"
    assert "14:40%" in calls["messages"][0]["content"]
    cmds = [{k: v for k, v in c.items() if k != "why"} for c in out["commands"]]
    C.apply_many(project, cmds)
    assert project.edit["aspect"] == "4:5" and any(g["type"] == "counter" for g in project.edit["graphics"])


def test_planner_refusal(project):
    from clipforge import planner
    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(
        parse=lambda **kw: SimpleNamespace(parsed_output=None, stop_reason="refusal", model="x"))))
    with pytest.raises(RuntimeError, match="declined"):
        planner.plan(project, "x", client=fake)


def test_mcp_tools(project):
    from clipforge.mcp_server import mcp
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"create_project", "transcribe", "get_transcript", "auto_cut", "apply_recipe", "add_graphic", "set_music_mood",
            "auto_broll", "auto_pace", "preflight", "render", "make_post_kit"} <= names
    r = asyncio.run(mcp.call_tool("get_transcript", {"project_id": project.id}))
    assert "14:40%" in r.content[0].text
    r = asyncio.run(mcp.call_tool("auto_cut", {"project_id": project.id}))
    assert "Auto cut" in r.content[0].text


def test_studio_api(project):
    from clipforge.server import serve
    httpd = serve(0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        meta = json.load(urllib.request.urlopen(base + "/api/meta"))
        assert len(meta["effects"]) >= 30 and "thought_leader" in meta["recipes"] and "focus" in meta["moods"]
        assert b"ClipForge Studio" in urllib.request.urlopen(base + "/").read()
        req = urllib.request.Request(f"{base}/api/projects/{project.id}/command", data=json.dumps({"op": "auto_cut"}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        st = json.load(urllib.request.urlopen(req))["state"]
        assert st["summary"]["after"] < st["summary"]["before"]
        req = urllib.request.Request(f"{base}/api/projects/{project.id}/preflight", data=b"{}", method="POST")
        assert isinstance(json.load(urllib.request.urlopen(req)), list)
        rng = urllib.request.Request(f"{base}/files/{project.id}/{st['source_rel']}", headers={"Range": "bytes=0-99"})
        r = urllib.request.urlopen(rng)
        assert r.status == 206 and len(r.read()) == 100
        bad = urllib.request.Request(f"{base}/files/{project.id}/../../brand.json")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(bad)
    finally:
        httpd.shutdown()


def test_pillow_captions_without_libass(project, monkeypatch):
    """Homebrew's ffmpeg has no libass; captions must still render."""
    from clipforge import commands as C, render
    from clipforge.captions import caption_states
    from clipforge.looks import resolved
    from clipforge.project import load_brand
    monkeypatch.setenv("CLIPFORGE_CAPTIONS", "pillow")
    C.apply(project, {"op": "auto_cut"})
    C.apply(project, {"op": "set_hook_title", "text": "How we grew 40%"})
    tl = render.timeline_for(project)
    states = caption_states(project.words, tl, project.edit, resolved("creator", load_brand()))
    assert abs(states[-1][1] - tl.duration) < 1e-6 and states[0][2]["hook"] == "How we grew 40%"
    assert all(b > a for a, b, _ in states)
    out = render.render(project, "tiny")
    work = project.dir / "renders" / "work-tiny"
    assert (work / "captions.ffconcat").exists() and not (work / "captions.ass").exists()
    dur, w, h, _ = probe(out)
    assert (w, h) == (270, 480) and abs(dur - tl.duration) < 0.15
    # a frame with a caption has bright caption pixels in the lower band
    frame = work / "f.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "4.4", "-i", str(out), "-frames:v", "1", str(frame)], check=True)
    assert Image.open(frame).convert("L").crop((20, 300, 250, 400)).getextrema()[1] > 200


def test_transcript_longer_than_media_is_clipped():
    """An imported transcript that runs past the end of the video must not produce negative segments."""
    from clipforge.timeline import build
    from clipforge.transcript import Word
    ws = [Word(i, "word.", i * 1.0, i * 1.0 + 0.4) for i in range(20)]  # words to 19.4 s
    tl = build(ws, {"deleted": [], "pause_max": 0.4}, media_duration=10.0)
    assert all(s.dur > 0 for s in tl.segments)
    assert 0 < tl.duration <= 10.0
    assert max(tl.word_out) <= 9 and all(i in tl.word_out for i in tl.order)


@pytest.mark.parametrize("hook", [False, True])
def test_single_pass_render_for_many_cuts(project, monkeypatch, hook):
    """Long recordings use one select pass per in-order run; audio and video must stay in sync."""
    from clipforge import commands as C, render
    monkeypatch.setattr(render, "SELECT_THRESHOLD", 0)
    C.apply(project, {"op": "auto_cut"})
    if hook:
        C.apply(project, {"op": "move_hook", "start_id": 10, "end_id": 16})
    tl = render.timeline_for(project)
    assert len(render.select_groups(tl.segments)) == (2 if hook else 1)
    out = render.render(project, "tiny")
    streams = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json",
                                         str(out)], capture_output=True, text=True, check=True).stdout)["streams"]
    d = {s["codec_type"]: float(s["duration"]) for s in streams}
    assert abs(d["video"] - tl.duration) < 0.07 and abs(d["audio"] - tl.duration) < 0.07


@pytest.fixture(scope="session")
def phone_media(tmp_path_factory):
    """A portrait phone clip (landscape pixels + rotation flag) and an HDR HLG clip, like iPhone footage."""
    d = tmp_path_factory.mktemp("phone")
    land = d / "land.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=3", "-f", "lavfi", "-i", "sine=d=3",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(land)], check=True)
    portrait = d / "portrait.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-display_rotation:v:0", "90", "-i", str(land), "-c", "copy", str(portrait)], check=True)
    hdr = d / "hdr.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=3", "-f", "lavfi", "-i", "sine=d=3",
                    "-c:v", "libx265", "-preset", "ultrafast", "-x265-params", "log-level=none", "-pix_fmt", "yuv420p10le",
                    "-color_primaries", "bt2020", "-color_trc", "arib-std-b67", "-colorspace", "bt2020nc", "-c:a", "aac",
                    "-shortest", str(hdr)], check=True)
    return portrait, hdr


def test_phone_portrait_and_hdr(home, phone_media):
    from clipforge import render
    from clipforge.project import Project
    portrait, hdr = phone_media
    p = Project.create(portrait)
    assert (p.meta["width"], p.meta["height"], p.meta["rotation"] % 180) == (360, 640, 90)
    h = Project.create(hdr)
    assert h.meta["hdr"] and h.meta["transfer"] == "arib-std-b67"
    out = render.render(h, "tiny")
    assert "vsdr" in (h.dir / "renders" / "work-tiny" / "graph.txt").read_text()
    assert probe(out)[1:3] == (270, 480)
    f = Project.create(hdr, shot_type="faceless")  # no source picture used: the tone-map must not dangle
    assert probe(render.render(f, "tiny"))[1:3] == (270, 480)


def test_engine_rejects_other_sites(home):
    """Web pages open in the browser must not be able to drive the local engine."""
    from clipforge.server import serve
    httpd = serve(0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"

    def status(path, method="GET", headers=None, body=None):
        r = urllib.request.Request(base + path, data=body, method=method, headers=headers or {})
        try:
            return urllib.request.urlopen(r).status
        except urllib.error.HTTPError as e:
            return e.code
    try:
        assert status("/api/brand", "POST", {"Origin": "https://evil.example"}, b'{"handle": "@x"}') == 403
        assert status("/api/meta", headers={"Host": f"evil.example:{port}"}) == 403
        assert status("/api/meta") == 200
        assert status("/api/meta", headers={"Host": f"localhost:{port}"}) == 200
        assert status("/api/brand", "POST", {"Origin": f"http://127.0.0.1:{port}"}, b'{"handle": "@ok"}') == 200
    finally:
        httpd.shutdown()
