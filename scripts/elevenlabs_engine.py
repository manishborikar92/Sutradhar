#!/usr/bin/env python3
"""Sutradhar — ElevenLabs v4 TTS Engine CLI & Facade (delegates to sutradhar.audio)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from sutradhar.audio.elevenlabs_tts import (  # noqa: E402
    AUDIO_TAG_PATTERN,
    DEFAULT_CACHE_DIR,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TIMEOUT_RETRIES,
    DEFAULT_MODEL_ID,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_TAG_TEMPLATES,
    DEFAULT_TIMEOUT_SEC,
    DEFAULT_VOICE_ID,
    DEFAULT_VOICE_SETTINGS,
    ELEVENLABS_API_BASE_URL,
    ElevenLabsAPIError,
    ElevenLabsAuthError,
    ElevenLabsEngine,
    ElevenLabsError,
    ElevenLabsQuotaExceededError,
    ElevenLabsRateLimitError,
    ElevenLabsTimeoutError,
    FakeElevenLabs,
    PreTTSBudgetReport,
    SubscriptionInfo,
    TTSBudgetError,
    VoiceInfo,
    apply_pronunciations_preserving_tags,
    compute_cache_key,
    compute_scene_sha256,
    decode_audio_bytes,
    get_project_root,
    mask_api_key,
    record_audio_ledger,
    strip_audio_tags,
    validate_pre_tts_budget,
)

__all__ = [
    "AUDIO_TAG_PATTERN",
    "DEFAULT_CACHE_DIR",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_TIMEOUT_RETRIES",
    "DEFAULT_MODEL_ID",
    "DEFAULT_OUTPUT_FORMAT",
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_TAG_TEMPLATES",
    "DEFAULT_TIMEOUT_SEC",
    "DEFAULT_VOICE_ID",
    "DEFAULT_VOICE_SETTINGS",
    "ELEVENLABS_API_BASE_URL",
    "ElevenLabsAPIError",
    "ElevenLabsAuthError",
    "ElevenLabsEngine",
    "ElevenLabsError",
    "ElevenLabsQuotaExceededError",
    "ElevenLabsRateLimitError",
    "ElevenLabsTimeoutError",
    "FakeElevenLabs",
    "PreTTSBudgetReport",
    "SubscriptionInfo",
    "TTSBudgetError",
    "VoiceInfo",
    "apply_pronunciations_preserving_tags",
    "compute_cache_key",
    "compute_scene_sha256",
    "decode_audio_bytes",
    "get_project_root",
    "main",
    "mask_api_key",
    "record_audio_ledger",
    "strip_audio_tags",
    "validate_pre_tts_budget",
]


def main() -> None:
    """CLI diagnostics and cache inspection tool for ElevenLabs engine."""
    parser = argparse.ArgumentParser(
        description="Sutradhar ElevenLabs v4 Engine Diagnostic Tool"
    )
    parser.add_argument(
        "--check-subscription",
        action="store_true",
        help="Check current ElevenLabs character credit balance and subscription status.",
    )
    parser.add_argument(
        "--voice-info",
        nargs="?",
        const=DEFAULT_VOICE_ID,
        help="Inspect voice metadata (default: Viraj).",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear local audio disk cache.",
    )
    args = parser.parse_args()

    engine = ElevenLabsEngine(cache_dir=DEFAULT_CACHE_DIR)
    try:
        if args.clear_cache:
            count = 0
            for item in engine.cache_dir.glob("*.mp3"):
                item.unlink()
                count += 1
            print(f"Cleared {count} cached audio files from {engine.cache_dir}.")

        if args.check_subscription:
            sub = engine.get_subscription_info()
            print("ElevenLabs Subscription Information:")
            print(f"  Tier:             {sub.tier}")
            print(f"  Status:           {sub.status}")
            print(f"  Used Characters:  {sub.character_count:,}")
            print(f"  Character Limit:  {sub.character_limit:,}")
            print(f"  Remaining:        {sub.remaining_characters:,}")
            print(f"  Usage:            {sub.percent_used:.1f}%")

        if args.voice_info:
            voice = engine.get_voice_info(args.voice_info)
            print("ElevenLabs Voice Information:")
            print(f"  Voice ID:    {voice.voice_id}")
            print(f"  Name:        {voice.name}")
            print(f"  Category:    {voice.category}")
            if voice.description:
                print(f"  Description: {voice.description}")
    finally:
        engine.close()


if __name__ == "__main__":
    main()
