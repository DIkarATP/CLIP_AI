"""
CLIP AI Audio AI v3.
Combines YAMNet sound classes with speech probability and relative acoustic
features. Produces review candidates, not verified emotions.
"""
from __future__ import annotations

import csv
import subprocess
import tempfile
import threading
from pathlib import Path

import numpy as np

_MODEL_URL = "https://tfhub.dev/google/yamnet/1"
_model = None
_labels = None
_lock = threading.Lock()

REACTION_LABELS = {
    "Laughter": "laughter",
    "Baby laughter": "laughter",
    "Giggle": "laughter",
    "Snicker": "laughter",
    "Chuckle, chortle": "laughter",
    "Screaming": "scream",
    "Yell": "yell",
    "Shout": "shout",
    "Bellow": "shout",
    "Whoop": "whoop",
    "Battle cry": "shout",
    "Children shouting": "shout",
}
SPEECH_LABELS = {
    "Speech", "Conversation", "Narration, monologue",
    "Child speech, kid speaking", "Male speech, man speaking",
    "Female speech, woman speaking",
}

def _load_model():
    global _model, _labels
    with _lock:
        if _model is not None:
            return _model, _labels
        try:
            import tensorflow_hub as hub
        except Exception as exc:
            raise RuntimeError(
                "YAMNet не установлен. Запусти install_yamnet.bat. "
                f"Подробности: {exc}"
            ) from exc
        model = hub.load(_MODEL_URL)
        class_map_path = model.class_map_path().numpy().decode("utf-8")
        with open(class_map_path, "r", encoding="utf-8") as f:
            labels = [row["display_name"] for row in csv.DictReader(f)]
        _model, _labels = model, labels
        return _model, _labels

def _extract_wav(ffmpeg: str, video_path: Path) -> np.ndarray:
    with tempfile.TemporaryDirectory(prefix="clipai_audio_v3_") as td:
        wav_path = Path(td) / "audio.wav"
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
               "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000",
               "-f", "wav", str(wav_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not wav_path.exists():
            raise RuntimeError((result.stderr or "FFmpeg не смог извлечь звук")[-700:])
        import soundfile as sf
        audio, sr = sf.read(str(wav_path), dtype="float32")
        if sr != 16000:
            raise RuntimeError(f"Ожидалось 16000 Гц, получено {sr} Гц")
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        return np.asarray(audio, dtype=np.float32)

def _rms(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)) + 1e-12))

def analyze_audio_events(ffmpeg: str, video_path: str | Path,
                         threshold: float = 0.12,
                         max_events: int = 150) -> dict:
    model, labels = _load_model()
    audio = _extract_wav(ffmpeg, Path(video_path))
    if audio.size < 16000:
        raise RuntimeError("В записи слишком мало звука для анализа")

    # 28.8 s is exactly 60 YAMNet hops (0.48 s), avoiding block-boundary drift.
    chunk_samples = int(28.8 * 16000)
    score_parts = []
    for offset in range(0, len(audio), chunk_samples):
        chunk = audio[offset:offset + chunk_samples]
        if chunk.size < 16000:
            continue
        chunk_scores, _, _ = model(chunk)
        score_parts.append(chunk_scores.numpy())
    if not score_parts:
        raise RuntimeError("Не удалось получить аудиоблоки для YAMNet")
    score_array = np.concatenate(score_parts, axis=0)
    if score_array.ndim != 2:
        raise RuntimeError("Неожиданный формат результата YAMNet")

    label_to_index = {label: i for i, label in enumerate(labels)}
    reaction_indices = {
        i: (label, category) for label, category in REACTION_LABELS.items()
        if (i := label_to_index.get(label)) is not None
    }
    speech_indices = [label_to_index[x] for x in SPEECH_LABELS if x in label_to_index]

    requested_threshold = max(0.0, min(float(threshold), 0.95))
    reaction_floors = {
        "laughter": max(requested_threshold, 0.22),
        "scream": max(requested_threshold, 0.27),
        "yell": max(requested_threshold, 0.27),
        "shout": max(requested_threshold, 0.27),
        "whoop": max(requested_threshold, 0.26),
    }

    frame_step = 0.48
    frame_size = 0.96
    total_duration = len(audio) / 16000.0
    raw = []
    frame_count = min(score_array.shape[0], int(np.ceil(total_duration / frame_step)))
    for frame_idx in range(frame_count):
        start = frame_idx * frame_step
        end = min(total_duration, start + frame_size)
        a = max(0, int(start * 16000))
        b = min(len(audio), int(end * 16000))
        level = _rms(audio[a:b])
        reaction_hits = []
        for class_idx, (label, category) in reaction_indices.items():
            confidence = float(score_array[frame_idx, class_idx])
            if confidence >= reaction_floors[category]:
                reaction_hits.append({
                    "label": label, "category": category,
                    "confidence": round(confidence, 3)
                })
        speech_score = max(
            (float(score_array[frame_idx, idx]) for idx in speech_indices),
            default=0.0
        )
        raw.append({
            "frame": frame_idx, "start": start, "end": end,
            "rms": level, "reaction_hits": reaction_hits,
            "speech_score": speech_score
        })

    # Robust baseline from the recording's audio level. Loudness is only a
    # supporting signal and can never create an event without speech evidence.
    levels = np.asarray([x["rms"] for x in raw if x["rms"] > 1e-5], dtype=np.float32)
    baseline = float(np.percentile(levels, 60)) if levels.size else 0.0
    for i, item in enumerate(raw):
        prev_level = raw[i-1]["rms"] if i else item["rms"]
        item["relative_loud"] = bool(
            baseline > 1e-5 and item["rms"] >= baseline * 1.55
        )
        item["energy_surge"] = bool(
            prev_level > 1e-5 and item["rms"] >= prev_level * 1.25
        )

    # Build two kinds of evidence:
    # A) explicit YAMNet reaction classes;
    # B) speech + elevated level + a local energy surge (review-only candidate).
    for item in raw:
        explicit = bool(item["reaction_hits"])
        voice_reaction = (
            item["speech_score"] >= 0.12
            and item["relative_loud"]
            and item["energy_surge"]
        )
        item["kind"] = (
            "explicit" if explicit else
            "voice" if voice_reaction else None
        )

    windows = []
    for item in raw:
        if item["kind"] is None:
            continue
        if windows and item["start"] <= windows[-1]["end"] + 0.48:
            w = windows[-1]
            w["end"] = max(w["end"], item["end"])
            w["items"].append(item)
        else:
            windows.append({"start": item["start"], "end": item["end"], "items": [item]})

    events = []
    for w in windows:
        items = w["items"]
        explicit_items = [x for x in items if x["kind"] == "explicit"]
        voice_items = [x for x in items if x["kind"] == "voice"]
        # Do not merge isolated one-frame detections into clips.
        explicit_frames = len({x["frame"] for x in explicit_items})
        voice_frames = len({x["frame"] for x in voice_items})
        duration = round(w["end"] - w["start"], 2)

        if explicit_frames >= 2 and duration >= 0.80:
            kind = "sound_class_reaction"
            detections = {}
            for item in explicit_items:
                for d in item["reaction_hits"]:
                    key = (d["label"], d["category"])
                    if key not in detections or d["confidence"] > detections[key]["confidence"]:
                        detections[key] = d
            found = sorted(detections.values(), key=lambda d: d["confidence"], reverse=True)
            display = " / ".join(d["label"] for d in found[:3])
            confidence = max((d["confidence"] for d in found), default=0.0)
        elif voice_frames >= 3 and duration >= 1.44:
            kind = "speech_energy_candidate"
            found = []
            display = "Громкая эмоциональная речь — проверить"
            confidence = round(min(0.99, np.mean([x["speech_score"] for x in voice_items])), 3)
        else:
            continue

        events.append({
            "start": round(w["start"], 2), "end": round(w["end"], 2),
            "duration": duration, "detections": found,
            "categories": sorted({d["category"] for d in found}) if found else ["speech_energy_candidate"],
            "display_label": display,
            "is_sustained": duration >= 1.5,
            "is_candidate_reaction": True,
            "candidate_type": kind,
            "evidence_frames": explicit_frames if kind == "sound_class_reaction" else voice_frames,
            "peak_confidence": confidence
        })

    events.sort(key=lambda e: (-e["peak_confidence"], -e["duration"], e["start"]))
    events = events[:max(1, min(int(max_events), 60))]
    events.sort(key=lambda e: e["start"])

    return {
        "engine": "CLIP AI Audio AI v3",
        "model": "YAMNet sound classes + speech/energy evidence",
        "duration_seconds": round(total_duration, 2),
        "threshold": requested_threshold,
        "events": events,
        "candidate_reactions": len(events),
        "note": (
            "Audio AI v3 использует два пути: явные звуковые классы смеха/криков "
            "YAMNet и отдельные кандидаты громкой речи, где одновременно есть "
            "вероятность речи, повышенный уровень и локальный всплеск энергии. "
            "Второй тип помечен «проверить» и не считается доказанной эмоцией. "
            "Громкие игровые эффекты без признака речи не должны попадать в этот "
            "тип. Видео и веб-камера пока не анализируются."
        )
    }
