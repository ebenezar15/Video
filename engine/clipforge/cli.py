"""clipforge command line: studio, mcp, and headless editing."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import commands, recipes, render, repurpose
from .project import Project


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="clipforge", description="Claude-driven short-form video editing engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("studio", help="Open the local Studio web app")
    s.add_argument("--port", type=int, default=8765)
    sub.add_parser("mcp", help="Run the MCP server on stdio (for Claude Desktop / Claude Code)")
    n = sub.add_parser("new", help="Create a project from a video")
    n.add_argument("video")
    n.add_argument("--shot", default="on_camera")
    n.add_argument("--name")
    t = sub.add_parser("transcribe", help="Transcribe on this computer, or import a transcript JSON")
    t.add_argument("project")
    t.add_argument("--language")
    t.add_argument("--import", dest="import_path")
    e = sub.add_parser("edit", help="Apply commands, e.g. '{\"op\":\"auto_cut\"}' (repeatable)")
    e.add_argument("project")
    e.add_argument("commands", nargs="+")
    q = sub.add_parser("auto", help="One-shot: auto cut + recipe + preflight fixes + render + post kit")
    q.add_argument("video")
    q.add_argument("--recipe", default="founder_story", choices=list(recipes.RECIPES))
    q.add_argument("--hook", default="")
    q.add_argument("--transcript", help="transcript JSON to import instead of transcribing")
    q.add_argument("--quality", default="final")
    r = sub.add_parser("render", help="Render a project")
    r.add_argument("project")
    r.add_argument("--quality", default="preview", choices=list(render.QUALITY))
    k = sub.add_parser("post", help="Make the post kit (cover, carousel, stories, caption)")
    k.add_argument("project")
    pf = sub.add_parser("preflight", help="Checks before export")
    pf.add_argument("project")
    pf.add_argument("--platform", default="reels")
    sub.add_parser("list", help="List projects")
    a = ap.parse_args(argv)

    if a.cmd == "studio":
        from .server import main as studio
        studio(a.port)
    elif a.cmd == "mcp":
        from .mcp_server import main as mcp_main
        mcp_main()
    elif a.cmd == "new":
        p = Project.create(Path(a.video), a.name, a.shot)
        print(p.id)
    elif a.cmd == "transcribe":
        from .transcript import import_transcript, transcribe
        p = Project.load(a.project)
        p.set_words(import_transcript(Path(a.import_path)) if a.import_path else transcribe(p.source, a.language))
        print(f"{len(p.words)} words")
    elif a.cmd == "edit":
        p = Project.load(a.project)
        for c in a.commands:
            print(commands.apply(p, json.loads(c)))
    elif a.cmd == "auto":
        from .transcript import import_transcript, transcribe
        p = Project.create(Path(a.video))
        p.set_words(import_transcript(Path(a.transcript)) if a.transcript else transcribe(p.source))
        print(commands.apply(p, {"op": "auto_cut"}))
        if a.hook:
            print(commands.apply(p, {"op": "set_hook_title", "text": a.hook}))
        print(commands.apply(p, {"op": "apply_recipe", "recipe": a.recipe}))
        for issue in recipes.preflight(p):
            if issue.get("fix") and issue["level"] in ("bad", "warn"):
                print("fix:", commands.apply(p, issue["fix"]))
        out = render.render(p, a.quality, lambda x: print(f"\rrendering {x:5.0%}", end="", file=sys.stderr))
        print(f"\n{out}")
        print(json.dumps(repurpose.post_kit(p)["files"], indent=1))
    elif a.cmd == "render":
        out = render.render(Project.load(a.project), a.quality, lambda x: print(f"\rrendering {x:5.0%}", end="", file=sys.stderr))
        print(f"\n{out}")
    elif a.cmd == "post":
        print(json.dumps(repurpose.post_kit(Project.load(a.project))["files"], indent=1))
    elif a.cmd == "preflight":
        for i in recipes.preflight(Project.load(a.project), a.platform):
            print(f"[{i['level']}] {i['message']}" + (f"  fix: {json.dumps(i['fix'])}" if i.get("fix") else ""))
    elif a.cmd == "list":
        for m in Project.list():
            print(f"{m['id']}  {m['name']}  {m.get('shot_type')}  {m.get('duration', 0):.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
