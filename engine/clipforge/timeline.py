"""Turn a transcript plus edit decisions into source segments and an output-time map."""
from __future__ import annotations

from dataclasses import dataclass, field

from .transcript import Word

PAD = 0.06
GRID = 30  # output frame rate; cut points are snapped to it


@dataclass
class Segment:
    src_start: float
    src_end: float
    out_start: float

    @property
    def dur(self) -> float:
        return self.src_end - self.src_start


@dataclass
class Timeline:
    segments: list[Segment] = field(default_factory=list)
    word_out: dict[int, tuple[float, float]] = field(default_factory=dict)
    order: list[int] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return sum(s.dur for s in self.segments)

    def out_time(self, word_id: int) -> float | None:
        t = self.word_out.get(word_id)
        return t[0] if t else None


def kept_order(words: list[Word], edit: dict) -> list[Word]:
    deleted = set(edit.get("deleted", []))
    kept = [w for w in words if w.id not in deleted]
    move = (edit.get("hook") or {}).get("move")
    if move:
        a, b = move
        front = [w for w in kept if a <= w.id <= b]
        rest = [w for w in kept if not (a <= w.id <= b)]
        kept = front + rest
    return kept


def build(words: list[Word], edit: dict, media_duration: float | None = None) -> Timeline:
    """Consecutive kept words share a segment; long pauses and removed words become cuts."""
    pause_max = float(edit.get("pause_max", 0.4))
    kept = kept_order(words, edit)
    tl = Timeline(order=[w.id for w in kept])
    if not kept:
        return tl
    runs: list[list[Word]] = [[kept[0]]]
    for prev, w in zip(kept, kept[1:]):
        contiguous = w.id == prev.id + 1 and (w.start - prev.end) <= pause_max
        if contiguous:
            runs[-1].append(w)
        else:
            runs.append([w])
    out = 0.0
    for i, run in enumerate(runs):
        first, last = run[0], run[-1]
        before = words[first.id - 1].end if first.id > 0 else 0.0
        after = words[last.id + 1].start if last.id + 1 < len(words) else (media_duration or last.end + PAD)
        # pad each cut, but never past halfway into the neighbouring word or gap
        s = max(first.start - min(PAD, max(0.0, first.start - before) / 2), 0.0)
        e = min(last.end + min(PAD, max(0.0, after - last.end) / 2), media_duration or 1e9)
        # cut on the 30 fps frame grid so audio and video drop exactly the same spans (no drift over many cuts)
        s, e = round(s * GRID) / GRID, round(e * GRID) / GRID
        if e - s < 1 / GRID:  # words past the end of the media (mismatched or overlong transcript)
            continue
        seg = Segment(round(s, 3), round(e, 3), round(out, 3))
        tl.segments.append(seg)
        for w in run:
            if w.start < e:
                tl.word_out[w.id] = (round(out + w.start - s, 3), round(out + min(w.end, e) - s, 3))
        out += seg.dur
    tl.order = [i for i in tl.order if i in tl.word_out]
    return tl


def summary(words: list[Word], edit: dict, media_duration: float) -> dict:
    tl = build(words, edit, media_duration)
    reasons = edit.get("cut_reasons", {})
    counts: dict[str, int] = {}
    for wid in edit.get("deleted", []):
        r = reasons.get(str(wid), "manual")
        counts[r] = counts.get(r, 0) + 1
    return {"before": round(media_duration, 2), "after": round(tl.duration, 2), "cuts": len(tl.segments) - 1 if tl.segments else 0,
            "removed": counts}
