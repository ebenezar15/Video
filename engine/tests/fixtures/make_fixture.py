"""Build a synthetic talking clip: test pattern video + one tone per word, plus its transcript."""
import json, subprocess, sys
from pathlib import Path

SCRIPT = [  # (text, start, end) - fillers, a retake, a long pause and a number on purpose
    ("So", 0.30, 0.50), ("um", 0.70, 1.00), ("I", 1.10, 1.20), ("was,", 1.20, 1.45), ("I", 1.60, 1.70), ("was", 1.70, 1.90),
    ("going", 1.90, 2.20), ("to", 2.20, 2.30), ("say", 2.30, 2.60), ("this.", 2.60, 2.95),
    ("We", 4.40, 4.55), ("grew", 4.55, 4.85), ("sales", 4.85, 5.20), ("by", 5.20, 5.35), ("40%", 5.35, 5.90), ("in", 5.90, 6.00),
    ("Dubai.", 6.00, 6.50), ("uh", 6.80, 7.05), ("The", 7.20, 7.35), ("trick", 7.35, 7.70), ("was", 7.70, 7.85),
    ("simple.", 7.85, 8.40), ("Post", 8.60, 8.85), ("every", 8.85, 9.10), ("single", 9.10, 9.45), ("day.", 9.45, 9.90),
    ("That's", 10.20, 10.50), ("it.", 10.50, 10.80),
]
DUR = 11.5

def build(out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    video, words = out_dir / "talk.mp4", out_dir / "talk.words.json"
    tones = "+".join(f"between(t,{s},{e})*sin(2*PI*{220 + 20 * i}*t)" for i, (_, s, e) in enumerate(SCRIPT))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=30:d={DUR}",
                    "-f", "lavfi", "-i", f"aevalsrc='0.4*({tones})':s=48000:d={DUR}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)], check=True)
    words.write_text(json.dumps({"words": [{"text": t, "start": s, "end": e} for t, s, e in SCRIPT]}))
    return video, words

if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "fixture-out")))
