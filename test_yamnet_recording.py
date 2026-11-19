from __future__ import annotations
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from ai.yamnet_detector import analyze_audio_events

BASE = Path(__file__).resolve().parent
RECORDINGS = BASE / "recordings"
REPORTS = BASE / "ai_reports"

def find_ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).resolve())
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    candidates = []
    configured_bin = os.getenv("CLIP_AI_FFMPEG_BIN", "").strip().strip('"')
    if configured_bin:
        candidates.append(Path(configured_bin) / exe_name)
    candidates.extend([
        Path(r"D:\\CLIP_AI\\tools\\ffmpeg\\ffmpeg-9.0.2-essentials_build\\bin") / exe_name,
        BASE.parent.parent / "tools" / "ffmpeg" / "ffmpeg-9.0.2-essentials_build" / "bin" / exe_name,
    ])
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return None

def main():
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ERROR: FFmpeg was not found.")
        print("Checked PATH, CLIP_AI_FFMPEG_BIN and the standard CLIP AI tools folders.")
        input("Press Enter to close...")
        return 1
    print("FFmpeg found:", ffmpeg)

    recordings = sorted(RECORDINGS.glob("*.ts"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not recordings:
        print("ERROR: No .ts recording found in the recordings folder.")
        input("Press Enter to close...")
        return 1

    recording = recordings[0]
    print("CLIP AI - YAMNet local recording test")
    print("Selected recording:", recording.name)
    print("File size: %.2f GB" % (recording.stat().st_size / (1024 ** 3)))
    print("Loading model and analyzing audio. This can take a while on CPU.")
    print("Do not close this window while analysis is running.")
    try:
        result = analyze_audio_events(
            ffmpeg=ffmpeg,
            video_path=recording,
            threshold=0.18,
            max_events=150
        )
    except Exception as exc:
        print("\nANALYSIS ERROR:", str(exc))
        input("Press Enter to close...")
        return 1

    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS / f"yamnet_{recording.stem}_{stamp}.json"
    payload = {
        "recording": recording.name,
        "recording_size_bytes": recording.stat().st_size,
        "created_local": datetime.now().isoformat(timespec="seconds"),
        "analysis": result
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n========== YAMNet RESULT ==========")
    print("Duration:", result.get("duration_seconds"), "seconds")
    print("Detected intervals:", len(result.get("events", [])))
    print("Candidate reactions:", result.get("candidate_reactions"))
    for i, event in enumerate(result.get("events", [])[:30], 1):
        labels = ", ".join(
            f"{d.get('label')} ({d.get('confidence')})"
            for d in event.get("detections", [])
        )
        print(
            f"{i:02d}. {event.get('start')}s - {event.get('end')}s | "
            f"{event.get('duration')}s | {labels} | "
            f"candidate={event.get('is_candidate_reaction')}"
        )
    print("\nFull JSON report:", report_path)
    print("\nNOTE: This is sound-event classification, not proof of emotion or game context.")
    input("\nTest finished. Press Enter to close...")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
