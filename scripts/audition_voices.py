#!/usr/bin/env python3
"""Sutradhar Kokoro-82M Voice Audition Utility (Milestone 3 Calibration).

Inspects the installed Kokoro ONNX voice archive, synthesizes a consistent
English + Sanskrit/Indian history documentary passage across suitable voices
and blends, runs faster-whisper lexical verification, and saves WAVs + JSON
report under build/audition/.

Does NOT modify config.yaml or episodes.db.
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
    align_caption_words,
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

# Consistent 2-part documentary passage with repeated Sanskrit & historical nouns
AUDITION_PASSAGE = (
    "Welcome to Sutradhar. Long before telescopes mapped the Schwarzschild radius, "
    "ancient scholars at Nalanda and Pataliputra debated time itself. "
    "From Ravana beneath Mount Kailash to Ashwatthama on the plains of Kurukshetra, "
    "the Mahabharata asks a chilling question. "
    "Listen closely as Chanakya, Ravana, and the lost halls of Nalanda return—"
    "because Sutradhar reveals the hidden pattern connecting myth and cosmos."
)

# Candidate blends to audition only if both component voices exist in voices-v1.0.bin
CANDIDATE_BLENDS = [
    "am_fenrir:0.65+bm_george:0.35",
    "am_michael:0.60+bm_george:0.40",
    "am_onyx:0.55+bm_george:0.45",
]


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
    all_voices = sorted(kokoro.get_voices())
    english_voices = [v for v in all_voices if v.startswith(("am_", "bm_", "af_", "bf_"))]
    # Documentary narrator shortlist: all available male US/UK voices + top female US/UK voices
    shortlist = [v for v in english_voices if v.startswith(("am_", "bm_"))]
    for female_pick in ("af_heart", "af_bella", "bf_emma", "bf_isabella"):
        if female_pick in english_voices and female_pick not in shortlist:
            shortlist.append(female_pick)

    # Add blends only when every component exists in the installed model
    available_set = set(all_voices)
    for blend in CANDIDATE_BLENDS:
        parts = [p.split(":", 1)[0] for p in blend.split("+")]
        if all(p in available_set for p in parts):
            shortlist.append(blend)

    whisper_model = default_whisper_factory(cfg)
    tts_text = apply_pronunciations(AUDITION_PASSAGE, replacements)
    tts_lang = cfg["tts"].get("language", "en-us")
    tts_speed = float(cfg["tts"].get("speed", 1.0))

    audition_dir = root / cfg["paths"]["build_dir"] / "audition"
    audition_dir.mkdir(parents=True, exist_ok=True)

    word_count = len(AUDITION_PASSAGE.split())
    results: list[dict[str, Any]] = []

    print(f"[INFO] Installed voices total: {len(all_voices)} (English: {len(english_voices)})", file=sys.stderr)
    print(f"[INFO] Auditioning {len(shortlist)} voice candidates -> {audition_dir}", file=sys.stderr)

    for voice_spec in shortlist:
        resolved = resolve_kokoro_voice(kokoro, voice_spec)
        # Use British G2P for pure British voices, US G2P otherwise
        lang_code = "en-gb" if (isinstance(resolved, str) and resolved.startswith(("bm_", "bf_"))) else tts_lang
        samples, sr = kokoro.create(tts_text, voice=resolved, speed=tts_speed, lang=lang_code)
        processed = trim_and_pad_audio(samples, int(sr), pad_tail_sec=0.2)

        wav_name = f"audition_{_slugify_voice(voice_spec)}.wav"
        wav_path = audition_dir / wav_name
        write_wav_atomic(wav_path, processed, int(sr))
        dur = probe_duration_sec(wav_path)

        whisper_words = transcribe_scene_words(
            whisper_model=whisper_model,
            wav_path=wav_path,
            caption_text=AUDITION_PASSAGE,
            language="en",
        )
        _, match_ratio = align_caption_words(
            caption_text=AUDITION_PASSAGE,
            whisper_words=whisper_words,
            scene_duration=dur,
            global_offset=0.0,
        )
        wpm = round((word_count / dur) * 60.0, 1)
        transcript_preview = " ".join(w["word"].strip() for w in whisper_words)

        entry = {
            "voice_spec": voice_spec,
            "lang_code": lang_code,
            "wav_path": f"build/audition/{wav_name}",
            "duration_sec": dur,
            "wpm": wpm,
            "rms_dbfs": _rms_dbfs(processed),
            "whisper_match_ratio": match_ratio,
            "whisper_transcript": transcript_preview,
        }
        results.append(entry)
        print(
            f"  - {voice_spec:<32} | {dur:5.2f}s | {wpm:5.1f} WPM | match={match_ratio:.2f} | {wav_name}",
            file=sys.stderr,
        )

    report = {
        "config_default_voice": cfg["tts"]["default_voice"],
        "config_voice_provisional": cfg["tts"]["voice_provisional"],
        "installed_english_voices": english_voices,
        "audition_passage_canonical": AUDITION_PASSAGE,
        "audition_passage_tts_phonetic": tts_text,
        "samples_generated": len(results),
        "results": sorted(results, key=lambda r: (-r["whisper_match_ratio"], abs(r["wpm"] - 155.0))),
    }
    report_path = audition_dir / "audition_report.json"
    write_text_atomic(report_path, json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())