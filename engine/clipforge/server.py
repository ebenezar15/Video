"""ClipForge Studio: a local web app (http://127.0.0.1:8765) over the same engine Claude uses through MCP."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
import traceback
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__, audio_gen, commands, graphics, planner, recipes, render as render_mod, repurpose
from .effects import catalog
from .looks import LOOKS
from .project import SHOT_TYPES, Project, home
from .transcript import import_transcript, transcribe

STATIC = Path(__file__).parent / "static"
JOBS: dict[str, dict] = {}
UPLOAD_KINDS = {"music", "popups", "broll"}


def run_job(kind: str, fn) -> str:
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "kind": kind, "status": "running", "progress": 0.0}

    def prog(x: float) -> None:
        JOBS[jid]["progress"] = round(x, 3)

    def work():
        try:
            JOBS[jid]["result"] = fn(prog)
            JOBS[jid]["status"] = "done"
            JOBS[jid]["progress"] = 1.0
        except Exception as e:  # surfaced to the UI
            JOBS[jid]["status"] = "error"
            JOBS[jid]["error"] = str(e)
            traceback.print_exc()

    threading.Thread(target=work, daemon=True).start()
    return jid


def claude_available() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    return (Path.home() / ".config" / "anthropic").exists()


class Handler(BaseHTTPRequestHandler):
    server_version = f"ClipForge/{__version__}"

    def log_message(self, fmt, *args):  # quieter console
        if os.environ.get("CLIPFORGE_DEBUG"):
            super().log_message(fmt, *args)

    # helpers -------------------------------------------------------------------------
    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, status=400):
        self._json({"error": msg}, status)

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _jbody(self) -> dict:
        raw = self._body()
        return json.loads(raw) if raw else {}

    def _save_upload(self, dest_dir: Path) -> Path:
        name = Path(unquote(self.headers.get("X-Filename") or "upload.bin")).name
        name = re.sub(r"[^\w.\- ]", "_", name) or "upload.bin"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name
        remaining = int(self.headers.get("Content-Length") or 0)
        with open(dest, "wb") as f:
            while remaining > 0:
                chunk = self.rfile.read(min(1 << 20, remaining))
                if not chunk:
                    break
                f.write(chunk)
                remaining -= len(chunk)
        return dest

    def _file(self, path: Path):
        if not path.is_file():
            return self._err("Not found", 404)
        size = path.stat().st_size
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and (m := re.match(r"bytes=(\d*)-(\d*)", rng)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else end
            else:
                start = size - int(m.group(2))
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    # routing -------------------------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        parts = [unquote(x) for x in u.path.strip("/").split("/") if x]
        try:
            if not parts or parts == ["index.html"]:
                return self._file(STATIC / "studio.html")
            if parts[0] == "static":
                return self._file(STATIC / Path(*parts[1:]).name)
            if parts == ["api", "meta"]:
                return self._json({"version": __version__, "looks": {k: {"label": v["label"], "about": v["about"]} for k, v in LOOKS.items()},
                                   "effects": catalog(), "shot_types": SHOT_TYPES, "ops": commands.DOCS,
                                   "claude": claude_available(), "model": planner.MODEL, "home": str(home()),
                                   "moods": {k: {"label": v["label"], "about": v["about"]} for k, v in audio_gen.MOODS.items()},
                                   "recipes": {k: {"label": v["label"], "about": v["about"]} for k, v in recipes.RECIPES.items()},
                                   "graphics": graphics.catalog(), "aspects": list(recipes.ASPECTS), "sfx": audio_gen.SFX})
            if parts == ["api", "projects"]:
                return self._json(Project.list())
            if len(parts) == 3 and parts[:2] == ["api", "projects"]:
                return self._json(commands.state(Project.load(parts[2])))
            if len(parts) == 3 and parts[:2] == ["api", "jobs"]:
                return self._json(JOBS.get(parts[2]) or {"status": "missing"})
            if len(parts) == 3 and parts[:2] == ["audio", "mood"]:
                if parts[2] not in audio_gen.MOODS:
                    return self._err("Unknown mood", 404)
                return self._file(audio_gen.music(parts[2], 12.0))
            if parts[0] == "files" and len(parts) >= 3:
                p = Project.load(parts[1])
                target = (p.dir / Path(*parts[2:])).resolve()
                if p.dir.resolve() not in target.parents:
                    return self._err("Forbidden", 403)
                return self._file(target)
            return self._err("Not found", 404)
        except FileNotFoundError as e:
            return self._err(str(e), 404)

    def do_POST(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        parts = [unquote(x) for x in u.path.strip("/").split("/") if x]
        try:
            if parts == ["api", "projects"]:
                tmp = self._save_upload(home() / "uploads")
                p = Project.create(tmp, q.get("name") or None, q.get("shot_type", "on_camera"))
                tmp.unlink(missing_ok=True)
                return self._json(commands.state(p))
            if parts == ["api", "projects", "from-path"]:
                b = self._jbody()
                p = Project.create(Path(b["path"]), b.get("name"), b.get("shot_type", "on_camera"), copy_media=b.get("copy", True))
                return self._json(commands.state(p))
            if parts == ["api", "brand"]:
                return self._json({"message": commands.update_brand(self._jbody())})
            if len(parts) < 4 or parts[:2] != ["api", "projects"]:
                return self._err("Not found", 404)
            pid, action = parts[2], parts[3]
            p = Project.load(pid)
            if action == "command":
                msg = commands.apply(p, {k: v for k, v in self._jbody().items() if k != "why"})
                return self._json({"message": msg, "state": commands.state(p)})
            if action == "commands":
                cmds = [{k: v for k, v in c.items() if k != "why"} for c in self._jbody().get("commands", [])]
                msgs = commands.apply_many(p, cmds)
                return self._json({"messages": msgs, "state": commands.state(p)})
            if action == "undo":
                label = p.undo()
                return self._json({"message": f"Undid {label}" if label else "Nothing to undo", "state": commands.state(p)})
            if action == "transcript":
                tmp = self._save_upload(p.dir / "media")
                p.set_words(import_transcript(tmp))
                return self._json({"message": f"{len(p.words)} words imported", "state": commands.state(p)})
            if action == "transcribe":
                b = self._jbody()
                def job(prog):
                    pp = Project.load(pid)
                    pp.set_words(transcribe(pp.source, b.get("language") or None, b.get("model", "small")))
                    return {"words": len(pp.words)}
                return self._json({"job": run_job("transcribe", job)})
            if action == "render":
                quality = self._jbody().get("quality", "preview")
                return self._json({"job": run_job("render", lambda prog: {
                    "video": str(render_mod.render(Project.load(pid), quality, prog).relative_to(p.dir))})})
            if action == "postkit":
                return self._json({"job": run_job("postkit", lambda prog: repurpose.post_kit(Project.load(pid)))})
            if action == "preflight":
                return self._json(recipes.preflight(p, self._jbody().get("platform", "reels")))
            if action == "plan":
                return self._json(planner.plan(p, self._jbody().get("prompt", "")))
            if action == "upload":
                kind = q.get("kind", "")
                if kind not in UPLOAD_KINDS:
                    return self._err(f"kind must be one of {sorted(UPLOAD_KINDS)}")
                dest = self._save_upload(p.dir / "media" / kind)
                return self._json({"path": str(dest)})
            return self._err("Not found", 404)
        except commands.CommandError as e:
            return self._err(str(e), 422)
        except FileNotFoundError as e:
            return self._err(str(e), 404)
        except Exception as e:
            traceback.print_exc()
            return self._err(f"{type(e).__name__}: {e}", 500)


def serve(port: int = 8765, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd


def main(port: int = 8765) -> None:
    httpd = serve(port)
    print(f"ClipForge Studio on http://127.0.0.1:{port}  (projects in {home()})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
