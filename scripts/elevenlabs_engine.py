#!/usr/bin/env python3
"""Sutradhar — ElevenLabs v4 Neural Synthesis & Caching Engine.

This module provides the production speech synthesis client for Sutradhar:
    - Model: ElevenLabs v4 (`eleven_v4`)
    - Sole Master Voice: Viraj (`uuyFQegRan8rpIQCGu9K`)
    - Vocal Acting Steering: Native Inline Audio Tags (`[...]`)
    - Caching: Content-addressable zero-waste disk cache (`build/cache/audio/`)
    - Resilience: Exponential backoff retries (429, 5xx), timeouts, balance checks
    - Audio Standard: 44.1 kHz float32 broadcast quality

Usage:
    from elevenlabs_engine import ElevenLabsEngine

    engine = ElevenLabsEngine()
    samples, sample_rate = engine.synthesize_scene(
        "[slowly, solemn, deep] सत्य केवल काल के गाल पर लिखा एक शब्द नहीं..."
    )
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import logging
import os
import random
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
import requests
import soundfile as sf

# Load environment variables (.env.local / .env)
try:
    from dotenv import load_dotenv

    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False


# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger("sutradhar.elevenlabs")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Constants & Defaults
# ---------------------------------------------------------------------------

ELEVENLABS_API_BASE_URL = "https://api.elevenlabs.io/v1"

DEFAULT_VOICE_ID = "uuyFQegRan8rpIQCGu9K"  # Viraj (Sole Voice for Sutradhar)
DEFAULT_MODEL_ID = "eleven_v4"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CACHE_DIR = "build/cache/audio"

DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_TIMEOUT_RETRIES = 2

DEFAULT_VOICE_SETTINGS: dict[str, Any] = {
    "stability": 0.55,
    "similarity_boost": 0.80,
    "style": 0.10,
    "use_speaker_boost": True,
}

DEFAULT_TAG_TEMPLATES: dict[str, str] = {
    "narrator": "[slowly, solemn, deep]",
    "divine": "[calm, serene, deep, slowly]",
    "antagonist": "[arrogant, booming, furious, shouts]",
    "grief": "[softly, sorrowful, trembling, sighs]",
    "devotional": "[calm, gentle, devotional]",
    "climax": "[building energy, intense]",
    "outro": "[gentle, calm, peaceful]",
}

AUDIO_TAG_PATTERN = re.compile(r"\[.*?\]")


# ---------------------------------------------------------------------------
# Exception Hierarchy
# ---------------------------------------------------------------------------

class ElevenLabsError(RuntimeError):
    """Base exception for all ElevenLabs engine operations."""


class ElevenLabsAuthError(ElevenLabsError):
    """Raised on 401 Unauthorized (missing, malformed, or invalid API key)."""


class ElevenLabsQuotaExceededError(ElevenLabsError):
    """Raised on 402 Payment Required or when character quota is exhausted."""


class ElevenLabsRateLimitError(ElevenLabsError):
    """Raised on 429 Rate Limited when retry attempts are exhausted."""


class ElevenLabsTimeoutError(ElevenLabsError):
    """Raised when API connection or read times out repeatedly."""


class ElevenLabsAPIError(ElevenLabsError):
    """Raised on 4xx/5xx API responses or unexpected server communication errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class SubscriptionInfo:
    """Subscription quota and status details from ElevenLabs API."""

    tier: str
    character_count: int
    character_limit: int
    status: str
    can_extend_character_limit: bool = False
    allowed_to_extend_character_limit: bool = False
    next_character_count_reset_unix: Optional[int] = None
    raw: dict[str, Any] = dataclasses.field(default_factory=dict, repr=False)

    @property
    def remaining_characters(self) -> int:
        """Remaining usable character credits in the billing cycle."""
        return max(0, self.character_limit - self.character_count)

    @property
    def percent_used(self) -> float:
        """Percentage of quota consumed."""
        if self.character_limit <= 0:
            return 0.0
        return (self.character_count / self.character_limit) * 100.0


@dataclasses.dataclass(frozen=True)
class VoiceInfo:
    """Voice metadata retrieved from ElevenLabs API."""

    voice_id: str
    name: str
    category: str
    description: Optional[str] = None
    raw: dict[str, Any] = dataclasses.field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def get_project_root() -> Path:
    """Resolve repository root directory, respecting SUTRADHAR_ROOT override."""
    env_root = os.environ.get("SUTRADHAR_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parent.parent


def mask_api_key(api_key: Optional[str]) -> str:
    """Mask an API key for safe logging, displaying only suffix."""
    if not api_key:
        return "<UNSET>"
    clean = api_key.strip()
    if len(clean) <= 8:
        return "***"
    return f"...{clean[-4:]}"


def strip_audio_tags(text: str) -> str:
    """Strip bracketed vocal steering tags (e.g. `[slowly, solemn]`) for Whisper alignment.

    Example:
        `[slowly, solemn, deep] सत्य केवल काल के गाल... [pause]`
        -> `सत्य केवल काल के गाल...`
    """
    cleaned = AUDIO_TAG_PATTERN.sub(" ", text)
    # Collapse multiple spaces while preserving newlines
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    return cleaned


def compute_cache_key(
    text: str,
    voice_id: str,
    model_id: str,
    voice_settings: Mapping[str, Any],
) -> str:
    """Compute content-addressable cache key according to Sutradhar specification.

    Formula:
        MD5(text_with_tags + ":" + voice_id + ":" + model_id + ":" + json(voice_settings))
    """
    settings_json = json.dumps(voice_settings, sort_keys=True, separators=(",", ":"))
    raw_key = f"{text}:{voice_id}:{model_id}:{settings_json}"
    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()


def decode_audio_bytes(
    audio_bytes: bytes,
    target_sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> tuple[np.ndarray, int]:
    """Decode MP3 audio bytes directly into a float32 1D NumPy array.

    Args:
        audio_bytes: Raw MP3 stream bytes.
        target_sample_rate: Expected sample rate (typically 44100 Hz).

    Returns:
        tuple[np.ndarray, int]: 1D float32 audio samples and detected sample rate.

    Raises:
        ElevenLabsError: If audio decoding fails or payload is empty.
    """
    if not audio_bytes:
        raise ElevenLabsError("Cannot decode empty audio payload.")

    try:
        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    except Exception as exc:
        raise ElevenLabsError(f"Failed to decode audio payload via soundfile: {exc}") from exc

    # If audio is multi-channel, convert to mono for narration alignment
    if data.ndim > 1:
        data = np.mean(data, axis=1, dtype=np.float32)

    data = np.ascontiguousarray(data, dtype=np.float32)

    if sr != target_sample_rate:
        logger.debug(
            "Decoded audio sample rate (%d Hz) differs from target (%d Hz)",
            sr,
            target_sample_rate,
        )

    return data, sr


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class ElevenLabsEngine:
    """Production ElevenLabs v4 TTS Client with Caching, Quota & Resilience."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        cache_dir: Optional[Path | str] = None,
        session: Optional[requests.Session] = None,
        project_root: Optional[Path] = None,
        base_url: str = ELEVENLABS_API_BASE_URL,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        output_format: Optional[str] = None,
        sample_rate: Optional[int] = None,
        voice_settings: Optional[dict[str, Any]] = None,
        tag_templates: Optional[dict[str, str]] = None,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Initialize the ElevenLabs TTS Engine.

        Loads environment variables and configuration files automatically if not passed.
        """
        self.project_root = project_root or get_project_root()
        self._load_environment()

        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = float(timeout_sec)
        self.max_retries = int(max_retries)

        # Merge config settings
        tts_cfg = (config or {}).get("tts", {}) if isinstance(config, dict) else {}

        self.voice_id = voice_id or tts_cfg.get("voice_id") or DEFAULT_VOICE_ID
        self.model_id = model_id or tts_cfg.get("model_id") or DEFAULT_MODEL_ID
        self.output_format = (
            output_format or tts_cfg.get("output_format") or DEFAULT_OUTPUT_FORMAT
        )
        self.sample_rate = int(
            sample_rate or tts_cfg.get("sample_rate") or DEFAULT_SAMPLE_RATE
        )

        settings_override = voice_settings or tts_cfg.get("voice_settings") or {}
        self.voice_settings = {**DEFAULT_VOICE_SETTINGS, **settings_override}

        templates_override = tag_templates or tts_cfg.get("tag_templates") or {}
        self.tag_templates = {**DEFAULT_TAG_TEMPLATES, **templates_override}

        # Resolve cache directory
        configured_cache = cache_dir or tts_cfg.get("cache_dir") or DEFAULT_CACHE_DIR
        self.cache_dir = (
            Path(configured_cache)
            if Path(configured_cache).is_absolute()
            else (self.project_root / configured_cache)
        )
        self._ensure_cache_dir()

        # Session management
        self._owns_session = session is None
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Sutradhar-ElevenLabsEngine/1.0.0",
                "Accept": "audio/mpeg",
            }
        )

    def _load_environment(self) -> None:
        """Load .env.local and .env files from the project root if available."""
        if not _DOTENV_AVAILABLE:
            return
        env_local = self.project_root / ".env.local"
        if env_local.is_file():
            load_dotenv(env_local, override=False)
        env_std = self.project_root / ".env"
        if env_std.is_file():
            load_dotenv(env_std, override=False)

    def _ensure_cache_dir(self) -> None:
        """Ensure disk cache directory exists."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create cache directory %s: %s", self.cache_dir, exc)

    def _get_auth_headers(self) -> dict[str, str]:
        """Validate and return headers with ElevenLabs API authentication."""
        if not self.api_key:
            raise ElevenLabsAuthError(
                "ELEVENLABS_API_KEY is missing or empty. Please set it in .env.local "
                "or your execution environment."
            )
        return {
            "xi-api-key": self.api_key,
        }

    # -----------------------------------------------------------------------
    # API Communication & Resilience
    # -----------------------------------------------------------------------

    def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
        """Execute HTTP request with exponential backoff and comprehensive error mapping."""
        req_headers = {**self._get_auth_headers(), **(headers or {})}
        timeout_attempts = 0

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.request(
                    method=method,
                    url=url,
                    headers=req_headers,
                    params=params,
                    json=json_data,
                    timeout=self.timeout_sec,
                    stream=stream,
                )

                if resp.status_code == 200:
                    return resp

                if resp.status_code == 401:
                    masked = mask_api_key(self.api_key)
                    raise ElevenLabsAuthError(
                        f"Authentication failed (HTTP 401 Unauthorized) with key {masked}. "
                        "Verify ELEVENLABS_API_KEY in .env.local."
                    )

                if resp.status_code == 402:
                    error_text = resp.text.strip()
                    raise ElevenLabsQuotaExceededError(
                        f"ElevenLabs character quota exhausted or payment required (HTTP 402): {error_text}"
                    )

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        sleep_sec = min(float(retry_after), 60.0)
                    else:
                        sleep_sec = (2.0 ** attempt) + random.uniform(0.1, 0.5)

                    logger.warning(
                        "ElevenLabs rate limit encountered (HTTP 429). Attempt %d/%d. Retrying in %.2fs...",
                        attempt,
                        self.max_retries,
                        sleep_sec,
                    )
                    if attempt == self.max_retries:
                        raise ElevenLabsRateLimitError(
                            f"ElevenLabs rate limit exceeded after {self.max_retries} attempts: {resp.text.strip()}"
                        )
                    time.sleep(sleep_sec)
                    continue

                if resp.status_code >= 500:
                    sleep_sec = (2.0 ** attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "ElevenLabs server error (HTTP %d). Attempt %d/%d. Retrying in %.2fs...",
                        resp.status_code,
                        attempt,
                        self.max_retries,
                        sleep_sec,
                    )
                    if attempt == self.max_retries:
                        raise ElevenLabsAPIError(
                            f"ElevenLabs backend server error (HTTP {resp.status_code}) after "
                            f"{self.max_retries} retries: {resp.text.strip()}",
                            status_code=resp.status_code,
                            response_body=resp.text,
                        )
                    time.sleep(sleep_sec)
                    continue

                # Non-retryable 4xx client errors (400, 404, etc.)
                raise ElevenLabsAPIError(
                    f"ElevenLabs API request failed with HTTP {resp.status_code}: {resp.text.strip()}",
                    status_code=resp.status_code,
                    response_body=resp.text,
                )

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                timeout_attempts += 1
                logger.warning(
                    "ElevenLabs network/timeout error on attempt %d: %s",
                    timeout_attempts,
                    exc,
                )
                if timeout_attempts > DEFAULT_MAX_TIMEOUT_RETRIES:
                    raise ElevenLabsTimeoutError(
                        f"ElevenLabs request timed out after {DEFAULT_MAX_TIMEOUT_RETRIES} attempts."
                    ) from exc
                time.sleep(1.0 + random.uniform(0.1, 0.3))

        raise ElevenLabsAPIError("ElevenLabs request failed unexpectedly after retries.")

    # -----------------------------------------------------------------------
    # Metadata & Quota Verification
    # -----------------------------------------------------------------------

    def get_subscription_info(self) -> SubscriptionInfo:
        """Fetch subscription details, character limits, and remaining credits.

        Returns:
            SubscriptionInfo: Detailed quota tracking data.
        """
        url = f"{self.base_url}/user/subscription"
        resp = self._request_with_retry("GET", url, headers={"Accept": "application/json"})
        try:
            data = resp.json()
        except ValueError as exc:
            raise ElevenLabsAPIError(
                f"Invalid JSON received from subscription endpoint: {resp.text}"
            ) from exc

        return SubscriptionInfo(
            tier=str(data.get("tier", "unknown")),
            character_count=int(data.get("character_count", 0)),
            character_limit=int(data.get("character_limit", 0)),
            status=str(data.get("status", "unknown")),
            can_extend_character_limit=bool(data.get("can_extend_character_limit", False)),
            allowed_to_extend_character_limit=bool(
                data.get("allowed_to_extend_character_limit", False)
            ),
            next_character_count_reset_unix=data.get("next_character_count_reset_unix"),
            raw=data,
        )

    def get_voice_info(self, voice_id: Optional[str] = None) -> VoiceInfo:
        """Fetch voice details and verify voice existence.

        Args:
            voice_id: Target voice ID. Defaults to Viraj (`uuyFQegRan8rpIQCGu9K`).

        Returns:
            VoiceInfo: Name, category, and metadata for the voice.
        """
        vid = voice_id or self.voice_id
        url = f"{self.base_url}/voices/{vid}"
        resp = self._request_with_retry("GET", url, headers={"Accept": "application/json"})
        try:
            data = resp.json()
        except ValueError as exc:
            raise ElevenLabsAPIError(
                f"Invalid JSON received from voice endpoint: {resp.text}"
            ) from exc

        return VoiceInfo(
            voice_id=str(data.get("voice_id", vid)),
            name=str(data.get("name", "Unknown")),
            category=str(data.get("category", "unknown")),
            description=data.get("description"),
            raw=data,
        )

    # -----------------------------------------------------------------------
    # Cache Management
    # -----------------------------------------------------------------------

    def get_cache_path(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        """Compute the cache file path for given synthesis parameters."""
        vid = voice_id or self.voice_id
        mid = model_id or self.model_id
        settings = voice_settings if voice_settings is not None else self.voice_settings
        cache_key = compute_cache_key(text, vid, mid, settings)
        return self.cache_dir / f"{cache_key}.mp3"

    def get_cached_audio_path(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Path]:
        """Check if an audio asset is already cached on disk with non-zero size."""
        cache_path = self.get_cache_path(text, voice_id, model_id, voice_settings)
        if cache_path.is_file() and cache_path.stat().st_size > 0:
            return cache_path
        return None

    def _write_cache_atomic(self, cache_path: Path, audio_bytes: bytes) -> None:
        """Atomically write audio bytes to cache file to prevent partial reads."""
        self._ensure_cache_dir()
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.cache_dir,
                prefix="cache_tmp_",
                suffix=".mp3",
                delete=False,
            ) as tf:
                temp_file = Path(tf.name)
                tf.write(audio_bytes)
                tf.flush()
                os.fsync(tf.fileno())

            temp_file.replace(cache_path)
            temp_file = None
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

    # -----------------------------------------------------------------------
    # Speech Synthesis
    # -----------------------------------------------------------------------

    def synthesize_scene(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[dict[str, Any]] = None,
        output_format: Optional[str] = None,
        check_quota: bool = True,
        skip_cache: bool = False,
    ) -> tuple[np.ndarray, int]:
        """Synthesize scene text into float32 audio samples.

        Checks disk cache first. If a cache miss occurs, verifies character balance
        and invokes the ElevenLabs v4 API, saving output to cache.

        Args:
            text: Narration or dialogue text, optionally including inline audio tags `[...]`.
            voice_id: Target voice ID (defaults to Viraj).
            model_id: Target model ID (defaults to `eleven_v4`).
            voice_settings: Custom stability/similarity/style settings.
            output_format: ElevenLabs output format (defaults to `mp3_44100_128`).
            check_quota: Whether to verify subscription credit balance on cache miss.
            skip_cache: If True, bypasses disk cache read and forces fresh API synthesis.

        Returns:
            tuple[np.ndarray, int]: Float32 1D audio waveform and sample rate (44100 Hz).
        """
        if not text or not text.strip():
            raise ElevenLabsError("Cannot synthesize empty text.")

        vid = voice_id or self.voice_id
        mid = model_id or self.model_id
        fmt = output_format or self.output_format
        settings = {**self.voice_settings, **(voice_settings or {})}

        cache_path = self.get_cache_path(text, vid, mid, settings)

        # 1. Check disk cache
        if not skip_cache and cache_path.is_file() and cache_path.stat().st_size > 0:
            logger.info("Cache hit for scene audio: %s", cache_path.name)
            try:
                audio_bytes = cache_path.read_bytes()
                return decode_audio_bytes(audio_bytes, self.sample_rate)
            except Exception as exc:
                logger.warning(
                    "Cached audio file %s is corrupted (%s). Re-synthesizing...",
                    cache_path.name,
                    exc,
                )

        # 2. Check subscription balance on cache miss
        char_count = len(text)
        if check_quota:
            sub_info = self.get_subscription_info()
            if sub_info.remaining_characters < char_count:
                raise ElevenLabsQuotaExceededError(
                    f"Insufficient ElevenLabs credits: text requires {char_count} characters, "
                    f"but only {sub_info.remaining_characters} remain in {sub_info.tier} tier "
                    f"({sub_info.character_count}/{sub_info.character_limit} used)."
                )

        # 3. Call ElevenLabs TTS API
        url = f"{self.base_url}/text-to-speech/{vid}"
        params = {"output_format": fmt}
        payload = {
            "text": text,
            "model_id": mid,
            "voice_settings": settings,
        }

        logger.info(
            "Synthesizing %d characters via ElevenLabs API (model=%s, voice=%s)...",
            char_count,
            mid,
            vid,
        )
        resp = self._request_with_retry(
            method="POST",
            url=url,
            params=params,
            json_data=payload,
            headers={"Content-Type": "application/json", "Accept": "audio/mpeg"},
        )

        audio_bytes = resp.content
        if not audio_bytes:
            raise ElevenLabsAPIError("ElevenLabs returned an empty audio response.")

        # 4. Save to content-addressable cache
        self._write_cache_atomic(cache_path, audio_bytes)
        logger.info("Saved synthesized audio to cache: %s (%d bytes)", cache_path.name, len(audio_bytes))

        # 5. Decode to float32 NumPy array
        return decode_audio_bytes(audio_bytes, self.sample_rate)

    def synthesize(
        self,
        text: str,
        voice_settings: Optional[dict[str, Any]] = None,
    ) -> tuple[np.ndarray, int]:
        """Convenience method conforming to FakeElevenLabs test double signature."""
        return self.synthesize_scene(text, voice_settings=voice_settings)

    def synthesize_to_file(
        self,
        text: str,
        output_path: Path | str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[dict[str, Any]] = None,
        output_format: Optional[str] = None,
        check_quota: bool = True,
        skip_cache: bool = False,
    ) -> Path:
        """Synthesize audio and write directly to the specified destination path."""
        target_path = Path(output_path)
        samples, sr = self.synthesize_scene(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            voice_settings=voice_settings,
            output_format=output_format,
            check_quota=check_quota,
            skip_cache=skip_cache,
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(target_path), samples, sr, subtype="PCM_16")
        return target_path

    # -----------------------------------------------------------------------
    # Lifecycle & Context Management
    # -----------------------------------------------------------------------

    def close(self) -> None:
        """Release underlying HTTP session resources."""
        if self._owns_session and self.session:
            self.session.close()

    def __enter__(self) -> ElevenLabsEngine:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Test Double: FakeElevenLabs
# ---------------------------------------------------------------------------

class FakeElevenLabs:
    """Deterministic, zero-network test double for ElevenLabs synthesis.

    Implements the test double contract specified in Section 8.1 of the development plan.
    Generates clean synthetic audio waveforms at 44.1 kHz broadcast standard.
    """

    def __init__(
        self,
        sec_per_scene: float = 6.0,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        fail_on_call: int = -1,
        silent: bool = False,
    ) -> None:
        self.sec_per_scene = float(sec_per_scene)
        self.sample_rate = int(sample_rate)
        self.fail_on_call = int(fail_on_call)
        self.silent = bool(silent)
        self.calls: list[dict[str, Any]] = []

    def synthesize(
        self,
        text: str,
        voice_settings: Optional[dict[str, Any]] = None,
    ) -> tuple[np.ndarray, int]:
        call_idx = len(self.calls) + 1
        self.calls.append({"text": text, "voice_settings": voice_settings})
        if call_idx == self.fail_on_call:
            raise ElevenLabsAPIError("Simulated FakeElevenLabs synthesis failure.")

        total_samples = int(round(self.sec_per_scene * self.sample_rate))
        if self.silent:
            return np.zeros(total_samples, dtype=np.float32), self.sample_rate

        t = np.linspace(0.0, self.sec_per_scene, total_samples, endpoint=False, dtype=np.float32)
        samples = (0.3 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
        return samples, self.sample_rate

    def synthesize_scene(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> tuple[np.ndarray, int]:
        return self.synthesize(text, voice_settings=voice_settings)

    def get_subscription_info(self) -> SubscriptionInfo:
        return SubscriptionInfo(
            tier="starter",
            character_count=12000,
            character_limit=37188,
            status="active",
        )

    def get_voice_info(self, voice_id: Optional[str] = None) -> VoiceInfo:
        return VoiceInfo(
            voice_id=voice_id or DEFAULT_VOICE_ID,
            name="Viraj",
            category="professional",
            description="Fake Viraj voice for offline testing",
        )


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

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

    engine = ElevenLabsEngine()

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
            vid = args.voice_info
            voice = engine.get_voice_info(vid)
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
