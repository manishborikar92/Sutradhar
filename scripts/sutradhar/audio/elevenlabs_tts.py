"""ElevenLabs v4 TTS client, tag-preserving pronunciations, pre-TTS budget gate, and audio_ledger."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import logging
import os
import random
import re
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
import requests
import soundfile as sf
import yaml

from sutradhar.config import get_project_root
from sutradhar.db import connect_db, immediate_transaction
from sutradhar.models import devanagari_token_ratio

try:
    from dotenv import load_dotenv

    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

logger = logging.getLogger("sutradhar.elevenlabs")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

ELEVENLABS_API_BASE_URL = "https://api.elevenlabs.io/v1"

DEFAULT_VOICE_ID = "uuyFQegRan8rpIQCGu9K"  # Viraj (Sole Master Voice)
DEFAULT_MODEL_ID = "eleven_v4"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CACHE_DIR = "build/cache/audio"

DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_TIMEOUT_RETRIES = 2

MAX_BILLED_CHARS = 900
TARGET_BILLED_CHARS_MIN = 760
TARGET_BILLED_CHARS_MAX = 840
SOFT_WARN_BILLED_CHARS = 850
MIN_DEVANAGARI_RATIO = 0.70

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
TAG_SPLIT_RE = re.compile(r"(\[.*?\])")


# ---------------------------------------------------------------------------
# Exceptions & Data Models
# ---------------------------------------------------------------------------

class AudioBuildError(RuntimeError):
    """Raised when audio validation, DSP, budget checks, or alignment fails."""


class ElevenLabsError(RuntimeError):
    """Base exception for all ElevenLabs TTS operations."""


class ElevenLabsAuthError(ElevenLabsError):
    """Raised on 401 Unauthorized (missing, malformed, or invalid API key)."""


class ElevenLabsQuotaExceededError(ElevenLabsError):
    """Raised on 402 Payment Required or exhausted character balance."""


class ElevenLabsRateLimitError(ElevenLabsError):
    """Raised on 429 Rate Limited after retries are exhausted."""


class ElevenLabsTimeoutError(ElevenLabsError):
    """Raised when API connection or read times out repeatedly."""


class ElevenLabsAPIError(ElevenLabsError):
    """Raised on 4xx/5xx API responses or unexpected transport failures."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class TTSBudgetError(ElevenLabsError, AudioBuildError):
    """Raised before any paid TTS call when billed characters or Hindi ratio fail policy."""


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
        return max(0, self.character_limit - self.character_count)

    @property
    def percent_used(self) -> float:
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


@dataclasses.dataclass(frozen=True)
class PreTTSBudgetReport:
    """Summary of pre-TTS billed character and language checks."""

    total_billed_chars: int
    scene_billed_chars: list[int]
    devanagari_ratio: float
    within_target: bool
    warning: Optional[str] = None


# ---------------------------------------------------------------------------
# Text Normalization, Pronunciations & Vocal Tag Steering
# ---------------------------------------------------------------------------

def mask_api_key(api_key: Optional[str]) -> str:
    """Mask an API key for safe logging, displaying only the last 4 chars."""
    if not api_key:
        return "<UNSET>"
    clean = api_key.strip()
    if len(clean) <= 8:
        return "***"
    return f"...{clean[-4:]}"


def strip_audio_tags(text: str) -> str:
    """Remove bracketed vocal steering tags (e.g. `[pause]`, `[slowly]`) for captions/Whisper."""
    cleaned = AUDIO_TAG_PATTERN.sub(" ", text)
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def load_pronunciations(
    root: Path,
    cfg: dict[str, Any],
    lang: str = "hi",
) -> dict[str, str]:
    """Load phonetic pronunciation text replacements from pronunciations_hi.yaml."""
    lang_prof = cfg.get("languages", {}).get(lang, {})
    pron_file = lang_prof.get("pronunciations_file", "pronunciations_hi.yaml")
    pron_path = (root / pron_file).resolve()
    if not pron_path.is_file():
        return {}

    try:
        with pron_path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ElevenLabsError(f"Malformed YAML in {pron_path}: {exc}") from exc

    if not isinstance(raw, dict):
        return {}

    reps_dict = raw.get("text_replacements")
    if not isinstance(reps_dict, dict):
        reps_dict = raw.get("replacements")
    if not isinstance(reps_dict, dict):
        return {}

    return {
        str(k).strip(): str(v).strip()
        for k, v in reps_dict.items()
        if str(k).strip() and str(v).strip() and str(k).strip() != str(v).strip()
    }


def apply_pronunciations(text: str, replacements: dict[str, str]) -> str:
    """Apply whole-word case-insensitive phonetic overrides (longest match first)."""
    if not replacements:
        return text
    ordered_keys = sorted(replacements.keys(), key=len, reverse=True)
    lower_map = {k.lower(): v for k, v in replacements.items()}
    pattern = re.compile(
        r"(?<![A-Za-z0-9\u0900-\u097F])("
        + "|".join(re.escape(k) for k in ordered_keys)
        + r")(?![A-Za-z0-9\u0900-\u097F])",
        re.IGNORECASE,
    )
    return pattern.sub(
        lambda m: lower_map.get(m.group(0).lower(), lower_map.get(m.group(0), m.group(0))),
        text,
    )


def apply_pronunciations_preserving_tags(text: str, replacements: dict[str, str]) -> str:
    """Apply phonetic overrides ONLY outside `[...]` tags so `[pause]` and steering tags survive."""
    parts = TAG_SPLIT_RE.split(text)
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            out.append(part)
        else:
            out.append(apply_pronunciations(part, replacements))
    return re.sub(r"[ \t]{2,}", " ", "".join(out)).strip()


def resolve_scene_tag(
    scene: Any,
    scene_idx: int,
    total_scenes: int,
    tag_templates: dict[str, str],
    is_climax_scene: bool,
) -> str:
    """Resolve inline vocal steering tag for scene persona and emotional context."""
    text = str(getattr(scene, "narration_text", "") or "").strip()
    if text.startswith("["):
        match = re.match(r"^(\[.*?\])", text)
        if match:
            return match.group(1)

    explicit_tag = str(getattr(scene, "vocal_tag", "") or "").strip()
    if explicit_tag.startswith("[") and explicit_tag.endswith("]"):
        return explicit_tag

    speaker_role = getattr(scene, "speaker_role", "narrator") or "narrator"
    emotion = str(getattr(scene, "emotion", "") or "").lower()
    shot_type = str(getattr(scene, "shot_type", "") or "").lower()
    char_name = str(getattr(scene, "primary_character", "") or "").lower()

    if speaker_role == "character_dialogue":
        if emotion in ("wrath", "rage", "arrogant", "angry") or any(
            ant in char_name for ant in ("ravana", "asura", "danava", "demon")
        ):
            return tag_templates.get("antagonist", "[arrogant, booming, furious, shouts]")
        if emotion in ("sad", "sorrow", "grief", "crying", "trembling", "fear"):
            return tag_templates.get("grief", "[softly, sorrowful, trembling, sighs]")
        if emotion in ("calm", "serene", "meditating", "divine") or any(
            div in char_name for div in ("shiva", "mahadev", "vishnu", "brahma", "devi", "shani")
        ):
            return tag_templates.get("divine", "[calm, serene, deep, slowly]")
        if emotion in ("devotional", "reverent", "gentle") or any(
            sag in char_name for sag in ("narad", "rishi", "sage", "sutradhar")
        ):
            return tag_templates.get("devotional", "[calm, gentle, devotional]")
        return tag_templates.get("narrator", "[slowly, solemn, deep]")

    if is_climax_scene or shot_type in ("dramatic_climax", "climax", "revelation"):
        return tag_templates.get("climax", "[building energy, intense]")
    if scene_idx == total_scenes - 1 or shot_type in ("philosophical_outro", "outro"):
        return tag_templates.get("outro", "[gentle, calm, peaceful]")
    return tag_templates.get("narrator", "[slowly, solemn, deep]")


def prepare_scene_tts_text(
    scene: Any,
    scene_idx: int,
    total_scenes: int,
    replacements: dict[str, str],
    tag_templates: dict[str, str],
    is_climax_scene: bool,
) -> tuple[str, str]:
    """Return `(clean_caption_text, tagged_phonetic_tts_text)` while keeping inline `[pause]` tags."""
    raw_text = str(getattr(scene, "narration_text", "") or "").strip()
    clean_text = strip_audio_tags(raw_text)
    phonetic_tagged = apply_pronunciations_preserving_tags(raw_text, replacements)
    if phonetic_tagged.lstrip().startswith("["):
        tagged_text = phonetic_tagged
    else:
        tag = resolve_scene_tag(
            scene=scene,
            scene_idx=scene_idx,
            total_scenes=total_scenes,
            tag_templates=tag_templates,
            is_climax_scene=is_climax_scene,
        )
        tagged_text = f"{tag} {phonetic_tagged}".strip()
    return clean_text, tagged_text


def validate_pre_tts_budget(
    tagged_texts: list[str],
    clean_texts: list[str],
    *,
    max_billed_chars: int = MAX_BILLED_CHARS,
    warn_billed_chars: int = SOFT_WARN_BILLED_CHARS,
    target_min: int = TARGET_BILLED_CHARS_MIN,
    target_max: int = TARGET_BILLED_CHARS_MAX,
    language: str = "hi",
    min_devanagari_ratio: float = MIN_DEVANAGARI_RATIO,
    enforce_devanagari: bool = True,
) -> PreTTSBudgetReport:
    """Validate pre-TTS billed character cap and Devanagari ratio BEFORE any API call."""
    scene_chars = [len(t.strip()) for t in tagged_texts]
    total_chars = sum(scene_chars)
    combined_clean = " ".join(t.strip() for t in clean_texts if t and t.strip())
    hi_ratio = devanagari_token_ratio(combined_clean)

    if enforce_devanagari and language == "hi" and hi_ratio < min_devanagari_ratio:
        raise TTSBudgetError(
            f"Pre-TTS Hindi validation failed: Devanagari token ratio {hi_ratio:.2%} < "
            f"{min_devanagari_ratio:.0%} required for language='hi'."
        )

    if total_chars > max_billed_chars:
        raise TTSBudgetError(
            f"Pre-TTS budget aborted: {total_chars} total billed characters (incl. tags) "
            f"exceeds hard limit {max_billed_chars} (target {target_min}-{target_max})."
        )

    warning: Optional[str] = None
    if total_chars > warn_billed_chars:
        warning = (
            f"Pre-TTS billed character count {total_chars} exceeds soft target "
            f"{warn_billed_chars} (hard limit {max_billed_chars})."
        )
        logger.warning("%s", warning)

    return PreTTSBudgetReport(
        total_billed_chars=total_chars,
        scene_billed_chars=scene_chars,
        devanagari_ratio=round(hi_ratio, 4),
        within_target=(target_min <= total_chars <= target_max),
        warning=warning,
    )


# ---------------------------------------------------------------------------
# Content-Addressable Cache Keys & Audio Decoding
# ---------------------------------------------------------------------------

def _serialized_voice_settings(voice_settings: Mapping[str, Any]) -> str:
    return json.dumps(voice_settings, sort_keys=True, separators=(",", ":"))


def compute_cache_key(
    text: str,
    voice_id: str,
    model_id: str,
    voice_settings: Mapping[str, Any],
) -> str:
    """Compute legacy MD5 content-addressable cache key (32-char hex)."""
    raw_key = f"{text}:{voice_id}:{model_id}:{_serialized_voice_settings(voice_settings)}"
    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()


def compute_scene_sha256(
    text: str,
    voice_id: str,
    model_id: str,
    voice_settings: Mapping[str, Any],
) -> str:
    """Compute canonical SHA-256 scene cache & audio_ledger key (64-char hex)."""
    raw_key = f"{text}:{voice_id}:{model_id}:{_serialized_voice_settings(voice_settings)}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def decode_audio_bytes(
    audio_bytes: bytes,
    target_sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> tuple[np.ndarray, int]:
    """Decode MP3/WAV audio bytes into a contiguous 1D float32 NumPy waveform."""
    if not audio_bytes:
        raise ElevenLabsError("Cannot decode empty audio payload.")
    try:
        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    except Exception as exc:
        raise ElevenLabsError(f"Failed to decode audio payload via soundfile: {exc}") from exc

    if data.ndim > 1:
        data = np.mean(data, axis=1, dtype=np.float32)
    data = np.ascontiguousarray(data, dtype=np.float32)

    if sr != target_sample_rate:
        logger.debug(
            "Decoded audio sample rate (%d Hz) differs from target (%d Hz)",
            sr,
            target_sample_rate,
        )
    return data, int(sr)


# ---------------------------------------------------------------------------
# SQLite audio_ledger Helpers
# ---------------------------------------------------------------------------

def record_audio_ledger(
    db_or_conn: Path | sqlite3.Connection,
    *,
    scene_index: int,
    sha256_key: str,
    billed_chars: int,
    model_id: str = DEFAULT_MODEL_ID,
    voice_id: str = DEFAULT_VOICE_ID,
    cache_hit: bool = False,
    episode_id: Optional[int] = None,
) -> int:
    """Insert a per-scene synthesis or cache-hit event into Schema v4 `audio_ledger`."""
    owns_conn = not isinstance(db_or_conn, sqlite3.Connection)
    conn = connect_db(Path(db_or_conn)) if owns_conn else db_or_conn
    try:
        with immediate_transaction(conn) as cur:
            cur.execute(
                """
                INSERT INTO audio_ledger (
                    episode_id, scene_index, sha256_key, billed_chars,
                    model_id, voice_id, cache_hit
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    int(scene_index),
                    sha256_key,
                    int(billed_chars),
                    model_id,
                    voice_id,
                    1 if cache_hit else 0,
                ),
            )
            return int(cur.lastrowid)
    finally:
        if owns_conn:
            conn.close()


def get_monthly_tts_usage(
    db_or_conn: Path | sqlite3.Connection,
    *,
    monthly_limit: int = 30000,
    month_yyyy_mm: Optional[str] = None,
) -> dict[str, Any]:
    """Summarize billed ElevenLabs characters (excluding cache hits) for a calendar month."""
    owns_conn = not isinstance(db_or_conn, sqlite3.Connection)
    conn = connect_db(Path(db_or_conn)) if owns_conn else db_or_conn
    try:
        if month_yyyy_mm:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN cache_hit = 0 THEN billed_chars ELSE 0 END), 0) AS spent_chars,
                    COALESCE(SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END), 0) AS cache_hits,
                    COUNT(*) AS total_entries
                FROM audio_ledger
                WHERE strftime('%Y-%m', created_at) = ?
                """,
                (month_yyyy_mm,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN cache_hit = 0 THEN billed_chars ELSE 0 END), 0) AS spent_chars,
                    COALESCE(SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END), 0) AS cache_hits,
                    COUNT(*) AS total_entries
                FROM audio_ledger
                WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
                """
            ).fetchone()
        spent = int(row["spent_chars"]) if row else 0
        hits = int(row["cache_hits"]) if row else 0
        total_entries = int(row["total_entries"]) if row else 0
        return {
            "monthly_limit": int(monthly_limit),
            "spent_chars": spent,
            "remaining_credits": max(0, int(monthly_limit) - spent),
            "cache_hits": hits,
            "total_entries": total_entries,
        }
    finally:
        if owns_conn:
            conn.close()


# ---------------------------------------------------------------------------
# ElevenLabs v4 Client & Offline Test Double
# ---------------------------------------------------------------------------

class ElevenLabsEngine:
    """Production ElevenLabs v4 TTS Client with SHA-256/MD5 disk cache, quota checks & retries."""

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
        cache_algo: str = "md5",
    ) -> None:
        self.project_root = project_root or get_project_root()
        self._load_environment()

        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = float(timeout_sec)
        self.max_retries = int(max_retries)
        self.cache_algo = cache_algo if cache_algo in ("md5", "sha256") else "md5"

        tts_cfg = (config or {}).get("tts", {}) if isinstance(config, dict) else {}
        self.voice_id = voice_id or tts_cfg.get("voice_id") or DEFAULT_VOICE_ID
        self.model_id = model_id or tts_cfg.get("model_id") or DEFAULT_MODEL_ID
        self.output_format = output_format or tts_cfg.get("output_format") or DEFAULT_OUTPUT_FORMAT
        self.sample_rate = int(sample_rate or tts_cfg.get("sample_rate") or DEFAULT_SAMPLE_RATE)

        settings_override = voice_settings or tts_cfg.get("voice_settings") or {}
        self.voice_settings = {**DEFAULT_VOICE_SETTINGS, **settings_override}

        templates_override = tag_templates or tts_cfg.get("tag_templates") or {}
        self.tag_templates = {**DEFAULT_TAG_TEMPLATES, **templates_override}

        configured_cache = cache_dir or tts_cfg.get("cache_dir") or DEFAULT_CACHE_DIR
        self.cache_dir = (
            Path(configured_cache)
            if Path(configured_cache).is_absolute()
            else (self.project_root / configured_cache)
        )
        self._ensure_cache_dir()

        self._owns_session = session is None
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Sutradhar-ElevenLabsEngine/2.0.0",
                "Accept": "audio/mpeg",
            }
        )

    def _load_environment(self) -> None:
        if not _DOTENV_AVAILABLE:
            return
        for fname in (".env.local", ".env"):
            fpath = self.project_root / fname
            if fpath.is_file():
                load_dotenv(fpath, override=False)

    def _ensure_cache_dir(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create cache directory %s: %s", self.cache_dir, exc)

    def _get_auth_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ElevenLabsAuthError(
                "ELEVENLABS_API_KEY is missing or empty. Please set it in .env.local "
                "or your execution environment."
            )
        return {"xi-api-key": self.api_key}

    def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
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
                    raise ElevenLabsQuotaExceededError(
                        f"ElevenLabs character quota exhausted or payment required (HTTP 402): {resp.text.strip()}"
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

    def get_subscription_info(self) -> SubscriptionInfo:
        """Fetch subscription details, character limits, and remaining credits."""
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
            allowed_to_extend_character_limit=bool(data.get("allowed_to_extend_character_limit", False)),
            next_character_count_reset_unix=data.get("next_character_count_reset_unix"),
            raw=data,
        )

    def get_voice_info(self, voice_id: Optional[str] = None) -> VoiceInfo:
        """Fetch voice metadata from ElevenLabs API."""
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

    def get_cache_path(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[Mapping[str, Any]] = None,
        *,
        algo: Optional[str] = None,
    ) -> Path:
        """Compute cache file path using configured hash algorithm (`md5` or `sha256`)."""
        vid = voice_id or self.voice_id
        mid = model_id or self.model_id
        settings = voice_settings if voice_settings is not None else self.voice_settings
        selected = algo or self.cache_algo
        if selected == "sha256":
            key = compute_scene_sha256(text, vid, mid, settings)
        else:
            key = compute_cache_key(text, vid, mid, settings)
        return self.cache_dir / f"{key}.mp3"

    def is_scene_cached(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        """Return True if a non-empty valid cache file exists (SHA-256 or legacy MD5)."""
        for algo in ("sha256", "md5"):
            p = self.get_cache_path(text, voice_id, model_id, voice_settings, algo=algo)
            if p.is_file() and p.stat().st_size > 0:
                return True
        return False

    def _write_cache_atomic(self, cache_path: Path, audio_bytes: bytes) -> None:
        self._ensure_cache_dir()
        temp_file: Optional[Path] = None
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
        """Synthesize scene text into float32 audio samples using cache first."""
        if not text or not text.strip():
            raise ElevenLabsError("Cannot synthesize empty text.")

        vid = voice_id or self.voice_id
        mid = model_id or self.model_id
        fmt = output_format or self.output_format
        settings = {**self.voice_settings, **(voice_settings or {})}

        primary_cache = self.get_cache_path(text, vid, mid, settings)
        alt_algo = "md5" if self.cache_algo == "sha256" else "sha256"
        secondary_cache = self.get_cache_path(text, vid, mid, settings, algo=alt_algo)

        if not skip_cache:
            for candidate in (primary_cache, secondary_cache):
                if candidate.is_file() and candidate.stat().st_size > 0:
                    try:
                        return decode_audio_bytes(candidate.read_bytes(), self.sample_rate)
                    except Exception as exc:
                        logger.warning(
                            "Cached audio file %s is corrupted (%s); continuing.",
                            candidate.name,
                            exc,
                        )

        char_count = len(text)
        if check_quota:
            sub_info = self.get_subscription_info()
            if sub_info.remaining_characters < char_count:
                raise ElevenLabsQuotaExceededError(
                    f"Insufficient ElevenLabs credits: text requires {char_count} characters, "
                    f"but only {sub_info.remaining_characters} remain in {sub_info.tier} tier "
                    f"({sub_info.character_count}/{sub_info.character_limit} used)."
                )

        url = f"{self.base_url}/text-to-speech/{vid}"
        resp = self._request_with_retry(
            method="POST",
            url=url,
            params={"output_format": fmt},
            json_data={"text": text, "model_id": mid, "voice_settings": settings},
            headers={"Content-Type": "application/json", "Accept": "audio/mpeg"},
        )
        audio_bytes = resp.content
        if not audio_bytes:
            raise ElevenLabsAPIError("ElevenLabs returned an empty audio response.")

        self._write_cache_atomic(primary_cache, audio_bytes)
        return decode_audio_bytes(audio_bytes, self.sample_rate)

    def synthesize(
        self,
        text: str,
        voice_settings: Optional[dict[str, Any]] = None,
    ) -> tuple[np.ndarray, int]:
        """Convenience alias matching FakeElevenLabs signature."""
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
        """Synthesize audio and write directly to a destination WAV path."""
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

    def close(self) -> None:
        if self._owns_session and self.session:
            self.session.close()

    def __enter__(self) -> ElevenLabsEngine:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class FakeElevenLabs:
    """Deterministic zero-network test double emitting clean 44.1 kHz synthetic sine audio."""

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
