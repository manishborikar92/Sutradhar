#!/usr/bin/env python3
"""Sutradhar Focused Voice & Vocal Tag Audition Utility (ElevenLabs v4).

Auditions Viraj (uuyFQegRan8rpIQCGu9K) across configured vocal steering tags
and character archetypes (narrator, divine, antagonist, grief, devotional, climax, outro).
Evaluates duration, WPM, RMS dBFS (acoustic energy), and faster-whisper lexical alignment accuracy.
Saves candidate WAVs and audition_report.json under build/audition/.

Strictly read-only with respect to config.yaml and episodes.db.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_audio import (  # noqa: E402
    align_narration_words,
    apply_pronunciations,
    default_elevenlabs_factory,
    default_whisper_factory,
    load_pronunciations,
    probe_duration_sec,
    transcribe_scene_words,
    trim_and_pad_audio,
    write_text_atomic,
    write_wav_atomic,
)
from db_manager import get_project_root, load_config  # noqa: E402
from elevenlabs_engine import (  # noqa: E402
    DEFAULT_TAG_TEMPLATES,
    DEFAULT_VOICE_ID,
    DEFAULT_VOICE_SETTINGS,
    ElevenLabsEngine,
    FakeElevenLabs,
    strip_audio_tags,
)

# Canonical Hindi audition passage featuring mythological terms and natural rhetorical pauses
AUDITION_PASSAGE_HI = (
    "क्या हो यदि पृथ्वी का सबसे पावन पर्वत शिखर... कोई प्राकृतिक पर्वत ही न हो? "
    "प्राचीन संस्कृत ग्रंथ कैलाश को चारों दिशाओं में पूर्णतः संरेखित बताते हैं। "
    "रामायण में रावण ने इस दिव्य पर्वत की जड़ों को हिला दिया था। "
    "सूतजी के मुख से सुनिए... वह गूढ़ रहस्य जो अनादि काल से छिपा है।"
)

# Canonical English passage preserved for historical benchmark continuity
AUDITION_PASSAGE = (
    "What if the most sacred peak on Earth... is not a natural mountain at all? "
    "Ancient Sanskrit scrolls describe Mount Kailash as four faces aligned precisely to true cardinal directions. "
    "In the Ramayana, Ravana shook the very roots of the peak—testing forces modern geologists still cannot explain. "
    "At Nalanda and Pataliputra, astronomers calculated celestial cycles centuries before the West. "
    "Welcome to Sutradhar... where ancient mystery meets cosmic reality."
)

# Character acting evaluation lines from Empirical Acoustic Validation (Section 3.2 of development plan)
CHARACTER_ACTING_LINES = {
    "narrator": {
        "tag": "[slowly, solemn, deep]",
        "text": AUDITION_PASSAGE_HI,
        "persona": "Sutradhar (Cosmic Narrator)",
    },
    "antagonist": {
        "tag": "[arrogant, booming, furious, shouts]",
        "text": "त्रिलोक में ऐसा कोई नहीं जो रावण के मार्ग में आ सके! देव, दानव और ग्रह सब मेरे चरणों में झुकेंगे!",
        "persona": "Ravana (Wrath)",
    },
    "grief": {
        "tag": "[softly, sorrowful, trembling, sighs]",
        "text": "हे नाथ, रुक जाइए! काल की विकराल छाया आपके मस्तक पर मंडरा रही है... इस हठ का परिणाम सर्वनाश होगा!",
        "persona": "Mandodari (Grief)",
    },
    "divine": {
        "tag": "[calm, serene, deep, slowly]",
        "text": "नियति अपना मार्ग स्वयं खोज लेती है, रावण। अहंकार का अंत ही शाश्वत धर्म की स्थापना है।",
        "persona": "Mahadev (Serenity)",
    },
    "devotional": {
        "tag": "[calm, gentle, devotional]",
        "text": "हे प्रभु नारायण, आपकी लीला अपरंपार है। इस अज्ञानी भक्त को अपने चरणों में शरण दीजिए।",
        "persona": "Narada / Devotee",
    },
    "climax": {
        "tag": "[building energy, intense]",
        "text": "और फिर... शनिदेव की वक्र दृष्टि लंका की स्वर्णिम नींव पर पड़ी! एक ही क्षण में तीनों लोकों का संतुलन डोल गया!",
        "persona": "Cosmic Climax (Turning Point)",
    },
    "outro": {
        "tag": "[gentle, calm, peaceful]",
        "text": "इतिहास गवाह है... कोई भी साम्राज्य धर्म के नियम से ऊपर नहीं हो सका। जुड़े रहिए सूत्रधार के साथ।",
        "persona": "Philosophical Outro",
    },
}

# Legacy constants retained for backward compatibility
FOCUSED_VOICES = ["Viraj", "uuyFQegRan8rpIQCGu9K"]
CANDIDATE_BLENDS = ["Viraj:1.0"]
SPEEDS = [0.90, 0.94]


def _slugify_voice(voice_spec: str) -> str:
    """Slugify voice spec for filenames and identifiers."""
    return voice_spec.replace(":", "_").replace("+", "__").replace(".", "p")


def _slugify_tag(tag_str: str) -> str:
    """Slugify bracketed vocal steering tag into clean safe filename."""
    cleaned = re.sub(r"[\[\]]", "", tag_str).strip()
    return re.sub(r"[^a-zA-Z0-9]+", "_", cleaned).strip("_").lower()


def _rms_dbfs(samples: np.ndarray) -> float:
    """Calculate RMS power in dBFS."""
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    if rms <= 1e-12:
        return -120.0
    return round(20.0 * float(np.log10(rms)), 2)


def run_audition(
    root: Path,
    cfg: Optional[dict[str, Any]] = None,
    tts_factory: Optional[Callable[..., Any]] = None,
    whisper_factory: Optional[Callable[..., Any]] = None,
    tag_filter: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Execute focused vocal tag audition on Viraj with ElevenLabs v4."""
    if cfg is None:
        cfg = load_config(root)

    tts_cfg = cfg.get("tts", {})
    voice_id = tts_cfg.get("voice_id", DEFAULT_VOICE_ID)
    model_id = tts_cfg.get("model_id", "eleven_v4")
    voice_settings = {**DEFAULT_VOICE_SETTINGS, **tts_cfg.get("voice_settings", {})}

    lang = cfg.get("channel", {}).get("primary_language", "hi")
    text_reps, _ = load_pronunciations(root, cfg, lang=lang)

    # Initialize TTS Engine
    if tts_factory is not None:
        tts_engine = tts_factory(cfg, root)
    else:
        tts_engine = default_elevenlabs_factory(cfg, root)

    # Initialize Whisper Model
    whisper_builder = whisper_factory or default_whisper_factory
    try:
        whisper_model = whisper_builder(cfg)
    except Exception as exc:
        print(f"[WARN] faster-whisper not available; alignment scoring will be skipped: {exc}", file=sys.stderr)
        whisper_model = None

    audition_dir = root / cfg.get("paths", {}).get("build_dir", "build") / "audition"
    audition_dir.mkdir(parents=True, exist_ok=True)

    candidates = (
        {k: v for k, v in CHARACTER_ACTING_LINES.items() if k in tag_filter}
        if tag_filter
        else CHARACTER_ACTING_LINES
    )

    results: list[dict[str, Any]] = []
    print(
        f"[INFO] Auditioning Viraj ({voice_id}) on {model_id} across {len(candidates)} vocal tags...",
        file=sys.stderr,
    )

    for role_name, item in candidates.items():
        tag = item["tag"]
        raw_text = item["text"]
        persona = item["persona"]

        # 1. Clean canonical text for lexical alignment
        clean_text = strip_audio_tags(raw_text)

        # 2. Phonetic pronunciation overrides
        phonetic_text = apply_pronunciations(clean_text, text_reps)

        # 3. Directed text with vocal steering tag
        directed_text = f"{tag} {phonetic_text.strip()}"

        tag_slug = f"{role_name}_{_slugify_tag(tag)}"
        wav_path = audition_dir / f"{tag_slug}.wav"

        try:
            if hasattr(tts_engine, "synthesize_scene"):
                samples, sr = tts_engine.synthesize_scene(
                    directed_text,
                    voice_id=voice_id,
                    model_id=model_id,
                    voice_settings=voice_settings,
                )
            elif hasattr(tts_engine, "synthesize"):
                samples, sr = tts_engine.synthesize(
                    directed_text,
                    voice_settings=voice_settings,
                )
            else:
                raise RuntimeError(f"Unsupported TTS engine: {type(tts_engine)}")
        except Exception as exc:
            print(f"[WARN] Failed to synthesize vocal tag '{role_name}': {exc}", file=sys.stderr)
            continue

        processed = trim_and_pad_audio(samples, sr, pad_tail_sec=0.50)
        write_wav_atomic(wav_path, processed, sr)
        dur = probe_duration_sec(wav_path)
        word_count = len(clean_text.split())
        wpm = round((word_count / max(dur, 0.1)) * 60.0, 1)
        rms = _rms_dbfs(processed)

        match_ratio = 1.0
        if whisper_model is not None:
            try:
                whisper_words = transcribe_scene_words(
                    whisper_model=whisper_model,
                    wav_path=wav_path,
                    narration_text=clean_text,
                    language="hi" if lang == "hi" else "en",
                )
                _, match_ratio = align_narration_words(
                    narration_text=clean_text,
                    whisper_words=whisper_words,
                    scene_duration=dur,
                    global_offset=0.0,
                )
            except Exception as w_exc:
                print(f"[WARN] Whisper alignment skipped for {tag_slug}: {w_exc}", file=sys.stderr)
                match_ratio = 0.0

        entry = {
            "role": role_name,
            "persona": persona,
            "tag": tag,
            "slug": tag_slug,
            "voice": "Viraj",
            "voice_id": voice_id,
            "model_id": model_id,
            "wav_file": str(wav_path.relative_to(root)).replace("\\", "/"),
            "duration_sec": dur,
            "word_count": word_count,
            "wpm": wpm,
            "rms_dbfs": rms,
            "lexical_match_ratio": match_ratio,
        }
        results.append(entry)
        print(
            f"[AUDITION] {role_name:<12} ({persona:<28}) | {dur:.2f}s | {wpm:5.1f} WPM | "
            f"RMS={rms:6.1f} dBFS | Match={match_ratio:.4f}",
            file=sys.stderr,
        )

    results.sort(key=lambda r: r["rms_dbfs"], reverse=True)

    report_payload = {
        "status": "ok",
        "action": "audition_voices",
        "engine": "elevenlabs",
        "voice": "Viraj",
        "voice_id": voice_id,
        "model_id": model_id,
        "sample_rate": 44100,
        "tags_evaluated": len(results),
        "results": results,
    }

    report_path = audition_dir / "audition_report.json"
    write_text_atomic(report_path, json.dumps(report_payload, indent=2, ensure_ascii=False))
    return report_payload


def main() -> int:
    root = get_project_root()
    cfg = load_config(root)
    payload = run_audition(root, cfg)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
