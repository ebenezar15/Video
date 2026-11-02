"""B-roll: find cutaways for what is being said. Your library first (CLIPFORGE_HOME/broll and the project's
media/broll), then Pexels when PEXELS_API_KEY is set. Files are matched by the words in their names."""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from .project import home
from .timeline import Timeline
from .transcript import Word

VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
STOP = set("""a an the and or but so to of in on at for with from by about as is are was were be been being it its this that these
those i you he she we they me him her us them my your our their there here what which who whom when where why how not no yes do does
did done have has had just really very more most much many some any all every each other than then too also only own same such can
will would should could might must shall may going get got like know think thing things want need make made say said one two""".split())


def tags(path: Path) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", path.stem.lower()) if len(t) > 2 and not t.isdigit()}


def library(project_dir: Path | None = None) -> list[Path]:
    roots = [home() / "broll"] + ([project_dir / "media" / "broll"] if project_dir else [])
    out = []
    for r in roots:
        if r.exists():
            out += [f for f in r.rglob("*") if f.suffix.lower() in VIDEO | IMAGE]
    return out


def match(query: str, files: list[Path]) -> Path | None:
    q = {t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) > 2}
    best, score = None, 0
    for f in files:
        s = len(q & tags(f))
        if s > score:
            best, score = f, s
    return best


def keywords(words: list[Word]) -> list[tuple[Word, str]]:
    """Content words worth illustrating: names, numbers and longer nouns-ish words."""
    out = []
    for w in words:
        n = w.norm
        if len(n) >= 5 and n not in STOP:
            out.append((w, n))
    return out


def auto(words: list[Word], tl: Timeline, files: list[Path], every: float = 6.0, skip_first: float = 2.5,
         duration: float = 2.0) -> list[dict]:
    picks, last = [], -1e9
    for w, n in keywords(words):
        t = tl.out_time(w.id)
        if t is None or t < skip_first or t - last < every or t + duration > tl.duration:
            continue
        f = match(n, files)
        if f:
            picks.append({"word_id": w.id, "path": str(f), "duration": duration, "mode": "full", "query": n})
            last = t
    return picks


def pexels(query: str, orientation: str = "portrait") -> Path | None:
    """Download the first matching Pexels clip (Pexels licence: free to use, attribution appreciated)."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    dest_dir = home() / "broll" / "pexels"
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": orientation, "per_page": 3, "size": "medium"})
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "ClipForge"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    for v in data.get("videos", []):
        files = sorted((f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 720),
                       key=lambda f: f.get("height") or 0)
        if not files:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        dest = dest_dir / f"{slug}-pexels-{v['id']}.mp4"
        if not dest.exists():
            urllib.request.urlretrieve(files[0]["link"], dest)
        (dest.with_suffix(".json")).write_text(json.dumps({"license": "Pexels License", "url": v.get("url"),
                                                            "author": (v.get("user") or {}).get("name")}))
        return dest
    return None


def license_of(path: Path) -> str:
    meta = Path(path).with_suffix(".json")
    if meta.exists():
        m = json.loads(meta.read_text())
        return f"{m.get('license')} — {m.get('author', '')} {m.get('url', '')}".strip()
    return "your library"
