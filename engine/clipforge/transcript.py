"""Word-level transcripts: load, save, import from common formats, or transcribe locally."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

SENTENCE_END = re.compile(r"[.!?…।]['\")\]]*$")


@dataclass
class Word:
    id: int
    text: str
    start: float
    end: float
    speaker: str | None = None

    @property
    def norm(self) -> str:
        return re.sub(r"[^\w%$₹€£']", "", self.text.lower())


def save_words(words: list[Word], path: Path) -> None:
    path.write_text(json.dumps({"words": [asdict(w) for w in words]}, ensure_ascii=False, indent=1))


def load_words(path: Path) -> list[Word]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [Word(**w) for w in data.get("words", [])]


def import_transcript(path: Path) -> list[Word]:
    """Accepts ClipForge JSON, faster-whisper/OpenAI-whisper JSON, or a plain word list."""
    data = json.loads(Path(path).read_text())
    raw: list[dict] = []
    if isinstance(data, list):
        raw = data
    elif "words" in data:
        raw = data["words"]
    elif "segments" in data:
        for seg in data["segments"]:
            raw.extend(seg.get("words", []))
    out = []
    for i, w in enumerate(raw):
        text = (w.get("text") or w.get("word") or "").strip()
        if not text:
            continue
        out.append(Word(len(out), text, float(w["start"]), float(w["end"]), w.get("speaker")))
    if not out:
        raise ValueError(f"No words with timings found in {path}")
    return out


def transcribe(media: Path, language: str | None = None, model: str = "small") -> list[Word]:
    """Local, on-device transcription with word timestamps (faster-whisper)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "On-device transcription is not installed. Install it with ready-made builds only: "
            "pip install --prefer-binary --only-binary av,ctranslate2,onnxruntime,tokenizers 'clipforge[whisper]' "
            "(Python 3.12 has the widest support). Or import a transcript JSON with words and timings."
        ) from e
    wm = WhisperModel(model, device="auto", compute_type="auto")
    segments, _info = wm.transcribe(str(media), language=language, word_timestamps=True, vad_filter=True)
    out: list[Word] = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                out.append(Word(len(out), text, round(w.start, 3), round(w.end, 3)))
    return out


def sentences(words: list[Word], gap: float = 0.9) -> list[list[Word]]:
    """Split into sentences on end punctuation or long silences."""
    out: list[list[Word]] = []
    cur: list[Word] = []
    for i, w in enumerate(words):
        if cur and w.start - cur[-1].end > gap:
            out.append(cur)
            cur = []
        cur.append(w)
        if SENTENCE_END.search(w.text):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out
