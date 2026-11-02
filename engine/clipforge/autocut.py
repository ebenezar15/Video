"""Find fillers and retakes to remove. Long pauses are trimmed by the timeline (pause_max)."""
from __future__ import annotations

from .transcript import Word, sentences

FILLERS = {"um", "umm", "uh", "uhh", "erm", "er", "uhm", "hmm", "mm", "mhm", "ah", "eh"}
SOFT_FILLERS = {"like", "basically", "actually", "literally"}


def fillers(words: list[Word], soft: bool = False) -> list[int]:
    bag = FILLERS | (SOFT_FILLERS if soft else set())
    out = [w.id for w in words if w.norm in bag]
    if soft:  # "you know" as a pair
        for a, b in zip(words, words[1:]):
            if a.norm == "you" and b.norm == "know" and b.text.endswith(","):
                out += [a.id, b.id]
    return sorted(set(out))


def retakes(words: list[Word], deleted: set[int] | None = None) -> list[int]:
    """Keep the last take. Catches restarted phrases ("I was, I was going") and repeated sentence openings."""
    deleted = deleted or set()
    live = [w for w in words if w.id not in deleted]
    out: set[int] = set()
    # phrase restarts: words[i:i+k] repeated within the next few words
    for i in range(len(live)):
        for k in (4, 3, 2):
            a = [w.norm for w in live[i:i + k]]
            if len(a) < k or not all(a):
                continue
            for j in range(i + k, min(i + k + 3, len(live) - k + 1)):
                if [w.norm for w in live[j:j + k]] == a:
                    out.update(w.id for w in live[i:j])
                    break
            else:
                continue
            break
    # sentence restarts: a sentence whose first 3 words open the next sentence too
    sents = sentences(live)
    for s1, s2 in zip(sents, sents[1:]):
        if len(s1) >= 3 and len(s2) >= 3 and [w.norm for w in s1[:3]] == [w.norm for w in s2[:3]]:
            out.update(w.id for w in s1)
    return sorted(out)


def plan(words: list[Word], remove_fillers: bool = True, soft_fillers: bool = False, remove_retakes: bool = True,
         already: set[int] | None = None) -> dict[int, str]:
    reasons: dict[int, str] = {}
    already = set(already or ())
    if remove_fillers:
        for wid in fillers(words, soft_fillers):
            reasons[wid] = "filler"
    if remove_retakes:
        for wid in retakes(words, already | set(reasons)):
            reasons.setdefault(wid, "retake")
    return reasons
