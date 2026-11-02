"""Licence-free sound made on this computer: mood music beds with a known beat grid, and subtle SFX.
Also picks from your own licensed library (CLIPFORGE_HOME/music + library.json) when a track matches the mood."""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

from .project import home

SR = 44100
MOODS: dict[str, dict] = {
    "uplifting": {"label": "Uplifting", "about": "Bright major progression, steady four-on-the-floor. Wins, launches, results.",
                  "bpm": 112, "root": 57, "prog": [(0, "maj"), (7, "maj"), (9, "min"), (5, "maj")], "drums": "four", "arp": True},
    "focus": {"label": "Focus", "about": "Calm pads and soft pulse. Explainers, advice, thought leadership.",
              "bpm": 86, "root": 55, "prog": [(0, "maj7"), (9, "min7"), (5, "maj7"), (7, "sus")], "drums": "soft", "arp": True},
    "cinematic": {"label": "Cinematic", "about": "Minor, slow, low booms. Founder stories, turning points.",
                  "bpm": 72, "root": 50, "prog": [(0, "min"), (8, "maj"), (3, "maj"), (10, "maj")], "drums": "boom", "arp": False},
    "tech": {"label": "Tech", "about": "Driving minor arpeggios. Product demos, AI, data.",
             "bpm": 120, "root": 52, "prog": [(0, "min"), (0, "min"), (8, "maj"), (10, "maj")], "drums": "four", "arp": True},
    "warm": {"label": "Warm", "about": "Gentle major with a light groove. Personal stories, behind the scenes.",
             "bpm": 94, "root": 53, "prog": [(0, "maj"), (9, "min"), (5, "maj"), (7, "maj")], "drums": "soft", "arp": False},
}
CHORDS = {"maj": [0, 4, 7], "min": [0, 3, 7], "maj7": [0, 4, 7, 11], "min7": [0, 3, 7, 10], "sus": [0, 5, 7]}


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _env(n: int, attack: float, release: float) -> np.ndarray:
    a, r = max(1, int(attack * SR)), max(1, int(release * SR))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, min(a, n))[: min(a, n)]
    if r < n:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def _tone(freq: float, n: int, harmonics: int = 3, detune: float = 0.0) -> np.ndarray:
    t = np.arange(n) / SR
    out = np.zeros(n)
    for h in range(1, harmonics + 1):
        out += np.sin(2 * np.pi * freq * h * (1 + detune) * t) / (h ** 1.6)
    return out


def _write(path: Path, stereo: np.ndarray) -> Path:
    peak = float(np.max(np.abs(stereo))) or 1.0
    data = (stereo / peak * 0.89 * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path


def beats(mood: str, duration: float) -> list[float]:
    spb = 60.0 / MOODS[mood]["bpm"]
    return [round(i * spb, 3) for i in range(int(duration / spb) + 1)]


def music(mood: str, duration: float, seed: int = 3) -> Path:
    """Render a mood bed exactly as long as the video (cached)."""
    if mood not in MOODS:
        raise ValueError(f"mood must be one of {list(MOODS)}")
    duration = round(max(duration, 2.0), 1)
    out = home() / "cache" / "music" / f"{mood}-{duration}.wav"
    if out.exists():
        return out
    m = MOODS[mood]
    rng = np.random.default_rng(seed)
    spb = 60.0 / m["bpm"]
    bar = 4 * spb
    n = int((duration + 1.0) * SR)
    L = np.zeros(n)
    R = np.zeros(n)
    bars = int(np.ceil(duration / bar)) + 1
    for b in range(bars):
        deg, kind = m["prog"][b % len(m["prog"])]
        s0 = int(b * bar * SR)
        if s0 >= n:
            break
        ln = min(int(bar * SR), n - s0)
        notes = [m["root"] + deg + iv for iv in CHORDS[kind]]
        pad = sum(_tone(_hz(x + 12), ln, 3, d) for x, d in zip(notes, (0.0, 0.002, -0.002, 0.001)))
        pad *= _env(ln, 0.35 * bar, 0.25 * bar) * 0.10
        L[s0:s0 + ln] += pad
        R[s0:s0 + ln] += np.roll(pad, 220)
        for q in range(4):  # bass on each beat
            qs = s0 + int(q * spb * SR)
            ql = min(int(spb * 0.9 * SR), n - qs)
            if ql <= 0:
                continue
            bass = _tone(_hz(m["root"] + deg - 12), ql, 2) * _env(ql, 0.01, 0.4 * spb) * 0.16
            L[qs:qs + ql] += bass
            R[qs:qs + ql] += bass
        if m["arp"]:  # eighth-note arpeggio, plucked
            for e in range(8):
                es = s0 + int(e * spb / 2 * SR)
                el = min(int(spb / 2 * SR), n - es)
                if el <= 0:
                    continue
                note = notes[(e * 2 + b) % len(notes)] + 24
                pl = _tone(_hz(note), el, 2) * np.exp(-np.arange(el) / SR * 9) * 0.05
                pan = 0.3 + 0.4 * ((e % 2) == 0)
                L[es:es + el] += pl * pan
                R[es:es + el] += pl * (1 - pan)
    # drums
    nb = int(duration / spb) + 2
    for i in range(nb):
        s = int(i * spb * SR)
        if s >= n:
            break
        kick_on = m["drums"] == "four" or (m["drums"] == "soft" and i % 2 == 0) or (m["drums"] == "boom" and i % 4 == 0)
        if kick_on:
            kl = min(int(0.35 * SR), n - s)
            t = np.arange(kl) / SR
            f = 50 + 70 * np.exp(-t * 30)
            kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (6 if m["drums"] == "boom" else 12))
            amp = 0.5 if m["drums"] == "four" else 0.32
            L[s:s + kl] += kick * amp
            R[s:s + kl] += kick * amp
        if m["drums"] in ("four", "soft"):
            hs = s + int(spb / 2 * SR)
            hl = min(int(0.05 * SR), n - hs)
            if hl > 0:
                hat = rng.standard_normal(hl) * np.exp(-np.arange(hl) / SR * 90)
                hat = np.diff(hat, prepend=0) * (0.05 if m["drums"] == "four" else 0.03)
                L[hs:hs + hl] += hat * 0.8
                R[hs:hs + hl] += hat
    total = int(duration * SR)
    fade = int(min(1.5, duration / 4) * SR)
    env = np.ones(total)
    env[:int(0.4 * SR)] = np.linspace(0, 1, int(0.4 * SR))
    env[-fade:] = np.linspace(1, 0, fade)
    return _write(out, np.stack([L[:total] * env, R[:total] * env], axis=1))


SFX = {
    "whoosh": "Air swish for transitions and B-roll",
    "pop": "Soft pop for pop-ups and stickers",
    "ding": "Clean bell for numbers and results",
    "riser": "Short build into a chapter or reveal",
    "impact": "Low hit under a hook title",
}


def sfx(name: str) -> Path:
    out = home() / "cache" / "sfx" / f"{name}.wav"
    if out.exists():
        return out
    rng = np.random.default_rng(11)
    if name == "whoosh":
        d = 0.55
        n = int(d * SR)
        t = np.arange(n) / SR
        noise = rng.standard_normal(n)
        k = np.clip((np.sin(np.pi * t / d)) ** 2, 0, 1)
        smooth = np.convolve(noise, np.ones(24) / 24, mode="same")
        x = smooth * k * 0.9
        st = np.stack([x * (1 - t / d), x * (t / d)], axis=1)
    elif name == "pop":
        n = int(0.12 * SR)
        t = np.arange(n) / SR
        x = np.sin(2 * np.pi * np.cumsum(700 - 2500 * t) / SR) * np.exp(-t * 45)
        st = np.stack([x, x], axis=1)
    elif name == "ding":
        n = int(1.0 * SR)
        t = np.arange(n) / SR
        x = (np.sin(2 * np.pi * 1318.5 * t) + 0.4 * np.sin(2 * np.pi * 2637 * t)) * np.exp(-t * 5)
        st = np.stack([x, x], axis=1)
    elif name == "riser":
        d = 1.2
        n = int(d * SR)
        t = np.arange(n) / SR
        f = 180 + 900 * (t / d) ** 2
        x = (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5 + np.convolve(rng.standard_normal(n), np.ones(8) / 8, "same") * 0.4) * (t / d) ** 1.5
        st = np.stack([x, x], axis=1)
    elif name == "impact":
        n = int(0.9 * SR)
        t = np.arange(n) / SR
        x = np.sin(2 * np.pi * (45 + 40 * np.exp(-t * 20)) * t) * np.exp(-t * 4) + rng.standard_normal(n) * np.exp(-t * 40) * 0.3
        st = np.stack([x, x], axis=1)
    else:
        raise ValueError(f"sfx must be one of {list(SFX)}")
    return _write(out, st)


def library_track(mood: str) -> dict | None:
    """A track from your own licensed library tagged with this mood: CLIPFORGE_HOME/music/library.json
    {"file.mp3": {"mood": "focus", "bpm": 90, "license": "Artlist, licence #123"}}"""
    lib_dir = home() / "music"
    index = lib_dir / "library.json"
    if not index.exists():
        return None
    for fname, meta in json.loads(index.read_text()).items():
        f = lib_dir / fname
        if meta.get("mood") == mood and f.exists():
            return {"path": str(f), "bpm": meta.get("bpm"), "license": meta.get("license", "your library")}
    return None
