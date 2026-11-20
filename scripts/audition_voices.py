#!/usr/bin/env python3
"""Sutradhar Focused Documentary Voice Audition Utility.

Synthesizes an authentic English + Sanskrit historical passage across top
warm, authoritative documentary voices and blends at 0.90x and 0.94x speeds.
Evaluates WPM, RMS dBFS, and Whisper lexical alignment accuracy.
Saves candidate WAVs and audition_report.json under build/audition/.

Strictly read-only with respect to config.yaml and episodes.db.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_audio import (  # noqa: E402
    align_narration_words,
    apply_pronunciations,
    default_kokoro_factory,
    default_whisper_factory,
    ensure_kokoro_models,
    load_pronunciations,
    probe_duration_sec,
    resolve_kokoro_voice,
    transcribe_scene_words,
    trim_and_pad_audio,
    write_text_atomic,
    write_wav_atomic,
)
from db_manager import get_project_root, load_config  # noqa: E402

# Punchy documentary passage featuring Sanskrit terms and natural rhetorical pauses
AUDITION_PASSAGE = (
    "What if the most sacred peak on Earth... is not a natural mountain at all? "
    "Ancient Sanskrit scrolls describe Mount Kailash as four faces aligned precisely to true cardinal directions. "
    "In the Ramayana, Ravana shook the very roots of the peak—testing forces modern geologists still cannot explain. "
    "At Nalanda and Pataliputra, astronomers calculated celestial cycles centuries before the West. "
    "Welcome to Sutradhar... where ancient mystery meets cosmic reality."
)

FOCUSED_VOICES = [
    "bm_daniel",
    "bm_george",
    "am_fenrir",
    "am_onyx",
    "am_michael",
]

CANDIDATE_BLENDS = [
    "am_fenrir:0.60+am_onyx:0.40",
    "bm_george:0.60+am_fenrir:0.40",
    "am_michael:0.55+bm_george:0.45",
]

SPEEDS = [0.90, 0.94]


def _slugify_voice(voice_spec: str) -> str:
    return voice_spec.replace(":", "_").replace("+", "__").replace(".", "p")


def _rms_dbfs(samples: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    if rms <= 1e-12:
        return -120.0
    return round(20.0 * float(np.log10(rms)), 2)


def main() -> int:
    root = get_project_root()
    cfg = load_config(root)
    replacements = load_pronunciations(root, cfg)
    model_path, voices_path = ensure_kokoro_models(root, cfg)

    kokoro = default_kokoro_factory(model_path, voices_path)
    all_voices = set(kokoro.get_voices())

    candidates: list[str] = [v for v in FOCUSED_VOICES if v in all_voices]
    for blend in CANDIDATE_BLENDS:
        parts = [p.split(":", 1)[0] for p in blend.split("+")]
        if all(p in all_voices for p in parts):
            candidates.append(blend)

    whisper_model = default_whisper_factory(cfg)
    tts_text = apply_pronunciations(AUDITION_PASSAGE, replacements)
    tts_lang = cfg["tts"].get("language", "en-us")

    audition_dir = root / cfg["paths"]["build_dir"] / "audition"
    audition_dir.mkdir(parents=True, exist_ok=True)

    word_count = len(AUDITION_PASSAGE.split())
    results: list[dict[str, Any]] = []

    print(
        f"[INFO] Auditioning {len(candidates)} candidates across {len(SPEEDS)} speeds "
        f"({len(candidates) * len(SPEEDS)} total evaluations)...",
        file=sys.stderr,
    )

    for speed in SPEEDS:
        for voice_spec in candidates:
            voice_slug = f"{_slugify_voice(voice_spec)}_spd{int(round(speed * 100))}"
            wav_path = audition_dir / f"{voice_slug}.wav"

            try:
                voice_data = resolve_kokoro_voice(kokoro, voice_spec)
                samples, sr = kokoro.create(
                    tts_text,
                    voice=voice_data,
                    speed=speed,
                    lang=tts_lang,
                )
            except Exception as exc:
                print(f"[WARN] Failed to synthesize '{voice_spec}' @ {speed}x: {exc}", file=sys.stderr)
                continue

            processed = trim_and_pad_audio(samples, sr, pad_tail_sec=0.50)
            write_wav_atomic(wav_path, processed, sr)
            dur = probe_duration_sec(wav_path)
            wpm = round((word_count / max(dur, 0.1)) * 60.0, 1)
            rms = _rms_dbfs(processed)

            try:
                whisper_words = transcribe_scene_words(
                    whisper_model=whisper_model,
                    wav_path=wav_path,
                    narration_text=AUDITION_PASSAGE,
                    language="en",
                )
                _, match_ratio = align_narration_words(
                    narration_text=AUDITION_PASSAGE,
                    whisper_words=whisper_words,
                    scene_duration=dur,
                    global_offset=0.0,
                )
            except Exception as w_exc:
                print(f"[WARN] Whisper alignment failed for {voice_slug}: {w_exc}", file=sys.stderr)
                match_ratio = 0.0

            entry = {
                "voice_spec": voice_spec,
                "speed": speed,
                "slug": voice_slug,
                "wav_file": str(wav_path.relative_to(root)).replace("\\", "/"),
                "duration_sec": dur,
                "wpm": wpm,
                "rms_dbfs": rms,
                "lexical_match_ratio": match_ratio,
            }
            results.append(entry)
            print(
                f"[AUDITION] {voice_spec:<28} spd={speed:.2f}x | {dur:.2f}s | {wpm:5.1f} WPM | "
                f"RMS={rms:6.1f} dBFS | Match={match_ratio:.4f}",
                file=sys.stderr,
            )

    results.sort(key=lambda r: (r["lexical_match_ratio"], -abs(r["wpm"] - 148.0)), reverse=True)

    report_payload = {
        "status": "ok",
        "action": "audition_voices",
        "speed_evaluated": SPEEDS,
        "audition_passage": AUDITION_PASSAGE,
        "tts_text_applied": tts_text,
        "results": results,
    }

    report_path = audition_dir / "audition_report.json"
    write_text_atomic(report_path, json.dumps(report_payload, indent=2, ensure_ascii=False))
    print(json.dumps(report_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
