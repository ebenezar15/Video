"""Projects live in folders under CLIPFORGE_HOME (default ~/ClipForge)."""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .transcript import Word, load_words, save_words

SHOT_TYPES = {
    "on_camera": "Me on camera",
    "voiceover_clips": "Voice-over on clips",
    "faceless": "Faceless (animated text)",
    "clips_text": "Clips + big text",
}

DEFAULT_EDIT: dict = {
    "deleted": [],
    "cut_reasons": {},
    "pause_max": 0.4,
    "hook": {"title": "", "move": None},
    "look": "creator",
    "captions": {"words_per_line": 3, "position": 0.80, "karaoke": True, "animation": "pop", "emphasis": "auto"},
    "popups": [],
    "effects": [],
    "cutaways": [],
    "graphics": [],
    "music": None,
    "sfx": {"enabled": True, "intensity": 0.4},
    "loudness": -14.0,
    "fit": "fill",
    "aspect": "9:16",
    "broll": [],
    "post": None,
}

DEFAULT_BRAND: dict = {
    "name": "",
    "handle": "",
    "palette": {"primary": "#1F1A17", "accent": "#FFC23D", "ink": "#FFFFFF", "paper": "#F3EDE4"},
    "fonts": {"title": None, "caption": None},
    "cta": "Follow for more",
    "hashtags": [],
    "hook_position": "top",
}


def home() -> Path:
    p = Path(os.environ.get("CLIPFORGE_HOME", Path.home() / "ClipForge")).expanduser()
    (p / "projects").mkdir(parents=True, exist_ok=True)
    return p


def load_brand() -> dict:
    f = home() / "brand.json"
    brand = copy.deepcopy(DEFAULT_BRAND)
    if f.exists():
        saved = json.loads(f.read_text())
        for k, v in saved.items():
            if isinstance(v, dict) and isinstance(brand.get(k), dict):
                brand[k].update(v)
            else:
                brand[k] = v
    return brand


def save_brand(brand: dict) -> None:
    (home() / "brand.json").write_text(json.dumps(brand, indent=2, ensure_ascii=False))


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height,r_frame_rate,color_transfer:stream_side_data=rotation:stream_tags=rotate",
         "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    num, _, den = (v.get("r_frame_rate") or "30/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    # phones store portrait video as landscape pixels plus a rotation flag; report what the viewer sees
    rotation = next((int(float(sd["rotation"])) for sd in v.get("side_data_list", []) if "rotation" in sd),
                    int(float((v.get("tags") or {}).get("rotate", 0) or 0)))
    w, h = v.get("width"), v.get("height")
    if rotation % 180 and w and h:
        w, h = h, w
    transfer = v.get("color_transfer") or ""
    return {"duration": float(info["format"].get("duration", 0)), "width": w, "height": h, "fps": round(fps, 3),
            "has_audio": has_audio, "rotation": rotation, "hdr": transfer in ("arib-std-b67", "smpte2084"),
            "transfer": transfer}


@dataclass
class Project:
    dir: Path
    meta: dict = field(default_factory=dict)
    edit: dict = field(default_factory=dict)
    words: list[Word] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.meta["id"]

    @property
    def source(self) -> Path:
        return self.dir / self.meta["source"]

    def path(self, *parts: str) -> Path:
        p = self.dir.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # persistence -------------------------------------------------------
    @classmethod
    def create(cls, video: Path, name: str | None = None, shot_type: str = "on_camera", copy_media: bool = True) -> "Project":
        if shot_type not in SHOT_TYPES:
            raise ValueError(f"shot_type must be one of {list(SHOT_TYPES)}")
        video = Path(video).expanduser().resolve()
        if not video.exists():
            raise FileNotFoundError(video)
        pid = time.strftime("%Y%m%d-") + uuid.uuid4().hex[:6]
        d = home() / "projects" / pid
        (d / "media").mkdir(parents=True)
        dest = d / "media" / ("source" + video.suffix.lower())
        if copy_media:
            shutil.copyfile(video, dest)
        else:
            dest.symlink_to(video)
        meta = {"id": pid, "name": name or video.stem, "source": str(dest.relative_to(d)), "shot_type": shot_type,
                "created": time.time(), **probe(dest)}
        p = cls(d, meta, copy.deepcopy(DEFAULT_EDIT), [])
        p.save()
        return p

    @classmethod
    def load(cls, pid: str) -> "Project":
        d = home() / "projects" / pid
        if not (d / "project.json").exists():
            raise FileNotFoundError(f"No project {pid}")
        meta = json.loads((d / "project.json").read_text())
        edit = copy.deepcopy(DEFAULT_EDIT)
        if (d / "edit.json").exists():
            edit.update(json.loads((d / "edit.json").read_text()))
        return cls(d, meta, edit, load_words(d / "words.json"))

    @staticmethod
    def list() -> list[dict]:
        out = []
        for f in sorted((home() / "projects").glob("*/project.json"), reverse=True):
            out.append(json.loads(f.read_text()))
        return out

    def save(self) -> None:
        (self.dir / "project.json").write_text(json.dumps(self.meta, indent=2, ensure_ascii=False))
        (self.dir / "edit.json").write_text(json.dumps(self.edit, indent=2, ensure_ascii=False))

    def set_words(self, words: list[Word]) -> None:
        self.words = words
        save_words(words, self.dir / "words.json")
        self.meta["transcribed"] = True
        self.save()

    # undo history --------------------------------------------------------
    def push_history(self, label: str) -> None:
        hist = self._history()
        hist.append({"label": label, "edit": copy.deepcopy(self.edit), "at": time.time()})
        (self.dir / "history.json").write_text(json.dumps(hist[-100:], ensure_ascii=False))

    def undo(self) -> str | None:
        hist = self._history()
        if not hist:
            return None
        last = hist.pop()
        self.edit = last["edit"]
        (self.dir / "history.json").write_text(json.dumps(hist, ensure_ascii=False))
        self.save()
        return last["label"]

    def history_labels(self) -> list[str]:
        return [h["label"] for h in self._history()]

    def _history(self) -> list[dict]:
        f = self.dir / "history.json"
        return json.loads(f.read_text()) if f.exists() else []
