"""Smart pop-ups: a number becomes a big number, a name or place becomes a card or photo.
At most one every few seconds, and placed away from the speaker's face."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .timeline import Timeline
from .transcript import Word, sentences

NUM_RE = re.compile(r"^[$₹€£]?\d[\d,.]*(k|m|b|x|%)?$", re.I)
UNITS = {"percent": "%", "%": "%", "k": "K", "thousand": "K", "million": "M", "billion": "B", "lakh": " lakh", "crore": " crore",
         "x": "×", "times": "×"}
SMALL = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                     "fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
SKIP = {"I", "I'm", "I've", "I'll", "OK", "Okay", "So", "And", "But", "The", "A"}


def _num_word(norm: str) -> int | None:
    return SMALL.get(norm, TENS.get(norm))


def detect(words: list[Word], tl: Timeline, every: float = 4.0, media_dir: Path | None = None) -> list[dict]:
    cands: list[dict] = []
    starts = {s[0].id for s in sentences(words)}
    i = 0
    while i < len(words):
        w = words[i]
        raw = w.text.strip(".,!?;:\"'()")
        nxt = words[i + 1].norm if i + 1 < len(words) else ""
        if NUM_RE.match(raw) and any(ch.isdigit() for ch in raw):
            text = raw + (UNITS[nxt] if nxt in UNITS else "")
            cands.append({"word_id": w.id, "kind": "number", "text": text})
        elif (n := _num_word(w.norm)) is not None and n >= 2:
            val, j = n, i + 1
            if n >= 20 and j < len(words) and (o := SMALL.get(words[j].norm)) and 0 < o < 10:
                val, j = n + o, j + 1
            unit = words[j].norm if j < len(words) else ""
            if unit in UNITS:
                cands.append({"word_id": w.id, "kind": "number", "text": f"{val}{UNITS[unit]}"})
        elif raw[:1].isupper() and len(raw) > 2 and w.id not in starts and raw not in SKIP:
            phrase, j = [raw], i + 1
            while j < len(words) and words[j].text[:1].isupper() and words[j].id not in starts:
                phrase.append(words[j].text.strip(".,!?;:"))
                j += 1
            text = " ".join(phrase)
            img = find_image(text, media_dir)
            cands.append({"word_id": w.id, "kind": "image" if img else "keyword", "text": text, **({"image": str(img)} if img else {})})
            i = j - 1
        i += 1
    return space_out(cands, tl, every)


def space_out(cands: list[dict], tl: Timeline, every: float) -> list[dict]:
    out, last = [], -1e9
    for c in sorted(cands, key=lambda c: tl.out_time(c["word_id"]) or 1e9):
        t = tl.out_time(c["word_id"])
        if t is None or t - last < every:
            continue
        out.append(c)
        last = t
    return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def find_image(text: str, media_dir: Path | None) -> Path | None:
    if not media_dir or not media_dir.exists():
        return None
    s = slug(text)
    for f in media_dir.iterdir():
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and slug(f.stem) == s:
            return f
    return None


# --- face-aware placement --------------------------------------------------------------
SLOTS = [(0.5, 0.17), (0.27, 0.30), (0.73, 0.30), (0.5, 0.58)]


def faces_at(video: Path, times: list[float], cache: Path) -> dict[str, list[list[float]]]:
    """Face boxes (normalised x, y, w, h in source frame) at the given source times. Cached on disk."""
    known = json.loads(cache.read_text()) if cache.exists() else {}
    todo = [t for t in times if f"{t:.2f}" not in known]
    if todo:
        try:
            import cv2
            det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        except (ImportError, AttributeError):  # extra not installed, or OpenCV 5 (no Haar cascades)
            return known
        cap = cv2.VideoCapture(str(video))
        for t in todo:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            boxes: list[list[float]] = []
            if ok:
                h, w = frame.shape[:2]
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                for (x, y, bw, bh) in det.detectMultiScale(gray, 1.1, 5, minSize=(w // 12, w // 12)):
                    boxes.append([x / w, y / h, bw / w, bh / h])
            known[f"{t:.2f}"] = boxes
        cap.release()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(known))
    return known


def place(face_boxes: list[list[float]], src_w: int, src_h: int, W: int, H: int, card_w: int, card_h: int) -> tuple[int, int]:
    """Pick the first slot whose card rectangle does not cover a face (faces mapped through the cover-crop)."""
    scale = max(W / src_w, H / src_h)
    ox, oy = (src_w * scale - W) / 2, (src_h * scale - H) / 2
    faces = [((x * src_w * scale - ox), (y * src_h * scale - oy), bw * src_w * scale, bh * src_h * scale)
             for x, y, bw, bh in face_boxes]

    def overlap(r1, r2):
        x1, y1, w1, h1 = r1
        x2, y2, w2, h2 = r2
        return max(0, min(x1 + w1, x2 + w2) - max(x1, x2)) * max(0, min(y1 + h1, y2 + h2) - max(y1, y2))

    best, best_ov = SLOTS[0], float("inf")
    for cx, cy in SLOTS:
        rect = (cx * W - card_w / 2, cy * H - card_h / 2, card_w, card_h)
        ov = sum(overlap(rect, f) for f in faces)
        if ov == 0:
            best = (cx, cy)
            break
        if ov < best_ov:
            best, best_ov = (cx, cy), ov
    x = int(min(max(best[0] * W - card_w / 2, 0), W - card_w))
    y = int(min(max(best[1] * H - card_h / 2, 0), H - card_h))
    return x, y
