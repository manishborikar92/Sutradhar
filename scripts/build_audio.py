#!/usr/bin/env python3
"""Sutradhar — Production Expressive Hindi Audio Engine (ElevenLabs v4).

Whitelisted zero-argument CLI invocation:
    python scripts/build_audio.py

Reads:
    - config.yaml
    - pronunciations_hi.yaml (with pronunciations.yaml fallback)
    - build/episode_plan.json
    - episodes.db (read-only active-series continuity check when present)

Writes (atomically):
    - build/audio/scene_{1..N}.wav (44.1 kHz 16-bit PCM)
    - build/audio/narration_full.wav (44.1 kHz broadcast mastered EBU R128)
    - build/audio/audio_manifest.json
    - build/manifest.js (window.EPISODE_MANIFEST = {...};)
"""

from __future__ import annotations

import datetime
import difflib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Optional

# Compatibility shim: PyAV 19+ removed metadata_errors parameter from av.open
try:
    import av

    _orig_av_open = av.open

    def _safe_av_open(*args: Any, **kwargs: Any) -> Any:
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except Exception:
    pass

import numpy as np
import soundfile as sf
import yaml
from pydantic import ValidationError

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from db_manager import (  # noqa: E402
    EpisodePlan,
    StateError,
    connect_db,
    emit_pacing_warnings,
    get_project_root,
    load_config,
    load_json_file,
    resolve_paths,
)
from elevenlabs_engine import (  # noqa: E402
    DEFAULT_SAMPLE_RATE,
    DEFAULT_TAG_TEMPLATES,
    DEFAULT_VOICE_ID,
    DEFAULT_VOICE_SETTINGS,
    ElevenLabsEngine,
    FakeElevenLabs,
    strip_audio_tags,
)

# ---------------------------------------------------------------------------
# Constants & Timing Standards
# ---------------------------------------------------------------------------

SILENCE_THRESHOLD = 0.003
TRIM_MARGIN_SEC = 0.10
INTER_SCENE_PAD_SEC = 0.20
FINAL_SCENE_PAD_SEC = 0.85
DURATION_TOLERANCE_SEC = 0.15
MIN_PEAK_AMPLITUDE = 1e-4
WORD_NORM_RE = re.compile(r"[^a-z0-9'\u0900-\u097F]+", re.IGNORECASE)


class AudioBuildError(RuntimeError):
    """Raised when audio synthesis, validation, DSP, or alignment fails."""


# ---------------------------------------------------------------------------
# System Prerequisites & Duration Probing
# ---------------------------------------------------------------------------

def require_executable(name: str) -> str:
    exe = shutil.which(name)
    if not exe:
        raise AudioBuildError(
            f"Required executable '{name}' not found in PATH. Install FFmpeg/FFprobe first."
        )
    return exe


def probe_duration_sec(audio_path: Path) -> float:
    try:
        return float(sf.info(str(audio_path)).duration)
    except Exception:
        pass
    ffprobe = require_executable("ffprobe")
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise AudioBuildError(
            f"ffprobe failed on '{audio_path}': {proc.stderr.strip() or proc.stdout.strip()}"
        )
    raw = proc.stdout.strip()
    try:
        duration = float(raw)
    except ValueError as exc:
        raise AudioBuildError(f"Invalid ffprobe duration '{raw}' for '{audio_path}'") from exc
    if duration <= 0.0:
        raise AudioBuildError(f"Non-positive audio duration ({duration}s) for '{audio_path}'")
    return round(duration, 4)


# ---------------------------------------------------------------------------
# Pronunciation Overrides
# ---------------------------------------------------------------------------

def load_pronunciations(
    root: Path,
    cfg: dict[str, Any],
    lang: str = "hi",
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Load language-specific pronunciation text overrides from pronunciations_hi.yaml."""
    lang_prof = cfg.get("languages", {}).get(lang, {})
    pron_file = lang_prof.get("pronunciations_file", "pronunciations_hi.yaml")

    pron_path = (root / pron_file).resolve()
    if not pron_path.is_file():
        return {}, []

    try:
        with pron_path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise AudioBuildError(f"Malformed YAML in {pron_path}: {exc}") from exc

    if not isinstance(raw, dict):
        return {}, []

    text_reps: dict[str, str] = {}
    if "text_replacements" in raw and isinstance(raw["text_replacements"], dict):
        text_reps.update({str(k).strip(): str(v).strip() for k, v in raw["text_replacements"].items()})
    elif "replacements" in raw and isinstance(raw["replacements"], dict):
        text_reps.update({str(k).strip(): str(v).strip() for k, v in raw["replacements"].items()})

    return text_reps, []


def apply_pronunciations(text: str, replacements: dict[str, str]) -> str:
    """Apply whole-word case-insensitive phonetic text overrides."""
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


# ---------------------------------------------------------------------------
# Vocal Tag Steering Determination
# ---------------------------------------------------------------------------

def resolve_scene_tag(
    scene: Any,
    scene_idx: int,
    total_scenes: int,
    tag_templates: dict[str, str],
    is_climax_scene: bool,
) -> str:
    """Resolve inline vocal steering tag for scene persona and emotional context."""
    text = getattr(scene, "narration_text", "").strip()
    if text.startswith("["):
        match = re.match(r"^(\[.*?\])", text)
        if match:
            return match.group(1)

    speaker_role = getattr(scene, "speaker_role", "narrator") or "narrator"
    emotion = str(getattr(scene, "emotion", "") or "").lower()
    shot_type = str(getattr(scene, "shot_type", "") or "").lower()
    char_name = str(getattr(scene, "primary_character", "") or "").lower()

    if speaker_role == "character_dialogue":
        if emotion in ("wrath", "arrogant", "angry") or any(
            ant in char_name for ant in ("ravana", "asura", "danava", "demon")
        ):
            return tag_templates.get("antagonist", "[arrogant, booming, furious, shouts]")
        elif emotion in ("sad", "sorrow", "grief", "crying", "trembling"):
            return tag_templates.get("grief", "[softly, sorrowful, trembling, sighs]")
        elif emotion in ("calm", "serene", "meditating", "divine") or any(
            div in char_name for div in ("shiva", "mahadev", "vishnu", "brahma", "devi")
        ):
            return tag_templates.get("divine", "[calm, serene, deep, slowly]")
        elif emotion in ("devotional", "reverent", "gentle") or any(
            sag in char_name for sag in ("narad", "rishi", "sage")
        ):
            return tag_templates.get("devotional", "[calm, gentle, devotional]")
        else:
            return tag_templates.get("antagonist", "[arrogant, booming, furious, shouts]")
    else:
        # Narrator
        if is_climax_scene or shot_type in ("dramatic_climax", "climax", "revelation"):
            return tag_templates.get("climax", "[building energy, intense]")
        elif scene_idx == total_scenes - 1 or shot_type in ("philosophical_outro", "outro"):
            return tag_templates.get("outro", "[gentle, calm, peaceful]")
        else:
            return tag_templates.get("narrator", "[slowly, solemn, deep]")


# ---------------------------------------------------------------------------
# Acoustic Metrics & Mastering
# ---------------------------------------------------------------------------

def measure_spectral_centroid(x: np.ndarray, fs: int, max_freq: int = 4000) -> float:
    magnitudes = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1.0 / fs)
    mask = (freqs >= 50) & (freqs <= max_freq) if max_freq else (freqs >= 50)
    return float(np.sum(magnitudes[mask] * freqs[mask]) / (np.sum(magnitudes[mask]) + 1e-12))


def measure_f0(x: np.ndarray, fs: int) -> float:
    frame_len = int(0.04 * fs)
    hop = int(0.02 * fs)
    f0s = []
    min_lag = int(fs / 350)
    max_lag = int(fs / 60)
    for start in range(0, len(x) - frame_len, hop):
        frame = x[start : start + frame_len]
        if np.std(frame) < 0.01:
            continue
        corr = np.correlate(frame, frame, mode="full")
        corr = corr[len(corr) // 2 :]
        if len(corr) > max_lag:
            peak_lag = min_lag + np.argmax(corr[min_lag:max_lag])
            f0s.append(fs / peak_lag)
    return float(np.median(f0s)) if f0s else 0.0


def measure_trailing_rms(wav_path: str | Path, tail_sec: float = 0.50) -> float:
    data, fs = sf.read(str(wav_path))
    if data.ndim > 1:
        data = data[:, 0]
    n_tail = int(tail_sec * fs)
    tail = data[-n_tail:] if len(data) >= n_tail else data
    rms = np.sqrt(np.mean(tail**2) + 1e-15)
    return float(20 * np.log10(rms))


def two_pass_loudnorm(
    in_wav: Path,
    out_wav: Path,
    target_lufs: float = -14.0,
    target_tp: float = -1.5,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    """Runs professional two-pass EBU R128 loudness normalization with linear gain."""
    pass1_res = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(in_wav),
            "-af",
            f"loudnorm=I={target_lufs}:TP={target_tp}:LRA=9:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    stderr = pass1_res.stderr
    idx_start = stderr.rfind("{")
    idx_end = stderr.rfind("}")
    if idx_start == -1 or idx_end == -1:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(in_wav),
                "-af",
                f"loudnorm=I={target_lufs}:TP={target_tp}:LRA=9",
                "-ar",
                str(sample_rate),
                str(out_wav),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return

    json_text = stderr[idx_start : idx_end + 1]
    stats = json.loads(json_text)

    norm_filter = (
        f"loudnorm=I={target_lufs}:TP={target_tp}:LRA=9:"
        f"measured_I={stats['input_i']}:"
        f"measured_TP={stats['input_tp']}:"
        f"measured_LRA={stats['input_lra']}:"
        f"measured_thresh={stats['input_thresh']}:"
        f"offset={stats['target_offset']}:linear=true"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(in_wav),
            "-af",
            norm_filter,
            "-ar",
            str(sample_rate),
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def trim_and_pad_audio(
    samples: np.ndarray,
    sample_rate: int,
    pad_tail_sec: float,
) -> np.ndarray:
    arr = np.asarray(samples, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1, dtype=np.float32)
    if arr.size == 0:
        raise AudioBuildError("TTS synthesis returned empty audio buffer.")

    peak = float(np.max(np.abs(arr)))
    if not np.isfinite(peak) or peak < MIN_PEAK_AMPLITUDE:
        raise AudioBuildError(
            f"TTS synthesis returned silent or non-finite audio (peak={peak})."
        )

    active_indices = np.flatnonzero(np.abs(arr) >= SILENCE_THRESHOLD)
    if active_indices.size > 0:
        margin = int(round(TRIM_MARGIN_SEC * sample_rate))
        start_idx = max(0, int(active_indices[0]) - margin)
        end_idx = min(arr.size, int(active_indices[-1]) + 1 + margin)
        arr = arr[start_idx:end_idx]

    # Smooth 20ms cosine fade ramp to avoid DC pops
    fade_len = int(0.020 * sample_rate)
    if arr.size > 2 * fade_len:
        ramp_in = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_len, dtype=np.float32)))
        ramp_out = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, fade_len, dtype=np.float32)))
        arr[:fade_len] *= ramp_in
        arr[-fade_len:] *= ramp_out

    arr = np.clip(arr, -1.0, 1.0)
    tail_samples = int(round(pad_tail_sec * sample_rate))
    if tail_samples > 0:
        arr = np.concatenate([arr, np.zeros(tail_samples, dtype=np.float32)])
    return arr


def write_wav_atomic(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp.wav")
    try:
        sf.write(str(tmp_path), samples, sample_rate, subtype="PCM_16")
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# Lexical Alignment & Subtitle Timestamps
# ---------------------------------------------------------------------------

def _norm_token(token: str) -> str:
    return WORD_NORM_RE.sub("", token.lower())


def _distribute_span(
    tokens: list[str],
    span_start: float,
    span_end: float,
) -> list[tuple[str, float, float]]:
    if not tokens:
        return []
    safe_start = max(0.0, span_start)
    safe_end = max(safe_start + 0.02 * len(tokens), span_end)
    weights = [max(1, len(_norm_token(t)) or len(t)) for t in tokens]
    total_w = float(sum(weights))
    cursor = safe_start
    total_dur = safe_end - safe_start
    result: list[tuple[str, float, float]] = []
    for idx, (tok, w) in enumerate(zip(tokens, weights)):
        nxt = safe_end if idx == len(tokens) - 1 else cursor + total_dur * (w / total_w)
        result.append((tok, cursor, max(cursor + 0.01, nxt)))
        cursor = nxt
    return result


def align_narration_words(
    narration_text: str = "",
    whisper_words: list[dict[str, Any]] | None = None,
    scene_duration: float = 0.0,
    global_offset: float = 0.0,
    caption_text: str | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """Map word timestamps deterministically onto canonical narration words."""
    text_source = caption_text if (caption_text is not None and not narration_text) else narration_text
    # Ensure text is cleanly stripped of any audio steering tags
    clean_text = strip_audio_tags(text_source)
    canon_tokens = clean_text.split()
    if not canon_tokens:
        raise AudioBuildError("Cannot align empty narration_text.")

    if not whisper_words:
        raise AudioBuildError("faster-whisper detected zero spoken words in synthesized audio.")
    cleaned_whisper: list[tuple[str, float, float]] = []
    for item in whisper_words:
        w_text = str(item.get("word", "")).strip()
        norm = _norm_token(w_text)
        if norm:
            cleaned_whisper.append((w_text, float(item.get("start", 0.0)), float(item.get("end", 0.0))))

    canon_norms = [_norm_token(t) for t in canon_tokens]
    whisper_norms = [_norm_token(w[0]) for w in cleaned_whisper]

    sm = difflib.SequenceMatcher(None, canon_norms, whisper_norms)
    blocks = [b for b in sm.get_matching_blocks() if b.size > 0]
    total_matches = sum(b.size for b in blocks)
    match_ratio = round(float(total_matches) / max(1, len(canon_tokens)), 4)

    word_spans: list[Optional[tuple[float, float]]] = [None] * len(canon_tokens)
    for b in blocks:
        for offset in range(b.size):
            c_idx = b.a + offset
            w_idx = b.b + offset
            _, w_start, w_end = cleaned_whisper[w_idx]
            word_spans[c_idx] = (w_start, max(w_start + 0.01, w_end))

    # Boundary interpolation for missing word anchors
    first_anchor = None
    for idx, span in enumerate(word_spans):
        if span is not None:
            first_anchor = (idx, span[0])
            break

    if first_anchor is None:
        distributed = _distribute_span(canon_tokens, 0.05, max(0.2, scene_duration - 0.1))
        aligned_words = []
        for tok, s, e in distributed:
            aligned_words.append(
                {
                    "word": tok,
                    "start": round(s, 4),
                    "end": round(e, 4),
                    "global_start": round(global_offset + s, 4),
                    "global_end": round(global_offset + e, 4),
                }
            )
        return aligned_words, match_ratio

    if first_anchor[0] > 0:
        lead_tokens = canon_tokens[: first_anchor[0]]
        lead_span = _distribute_span(lead_tokens, 0.02, max(0.04, first_anchor[1]))
        for idx, (_, s, e) in enumerate(lead_span):
            word_spans[idx] = (s, e)

    last_anchor = None
    for idx in range(len(canon_tokens) - 1, -1, -1):
        if word_spans[idx] is not None:
            last_anchor = (idx, word_spans[idx][1])
            break

    if last_anchor is not None and last_anchor[0] < len(canon_tokens) - 1:
        tail_start_idx = last_anchor[0] + 1
        tail_tokens = canon_tokens[tail_start_idx:]
        tail_end = max(last_anchor[1] + 0.05 * len(tail_tokens), scene_duration - 0.05)
        tail_span = _distribute_span(tail_tokens, last_anchor[1], tail_end)
        for idx, (_, s, e) in enumerate(tail_span):
            word_spans[tail_start_idx + idx] = (s, e)

    # Fill internal gaps
    idx = 0
    while idx < len(canon_tokens):
        if word_spans[idx] is None:
            gap_start = idx
            while idx < len(canon_tokens) and word_spans[idx] is None:
                idx += 1
            gap_end = idx
            prev_end = word_spans[gap_start - 1][1] if gap_start > 0 else 0.02
            next_start = (
                word_spans[gap_end][0] if gap_end < len(canon_tokens) else scene_duration - 0.02
            )
            gap_tokens = canon_tokens[gap_start:gap_end]
            gap_span = _distribute_span(gap_tokens, prev_end, max(prev_end + 0.04, next_start))
            for g_offset, (_, s, e) in enumerate(gap_span):
                word_spans[gap_start + g_offset] = (s, e)
        else:
            idx += 1

    # Monotonicity enforcement
    aligned_words: list[dict[str, Any]] = []
    current_time = 0.0
    for tok, span in zip(canon_tokens, word_spans):
        assert span is not None
        s, e = span
        s = max(current_time, s)
        e = max(s + 0.01, e)
        current_time = e
        aligned_words.append(
            {
                "word": tok,
                "start": round(s, 4),
                "end": round(e, 4),
                "global_start": round(global_offset + s, 4),
                "global_end": round(global_offset + e, 4),
            }
        )

    return aligned_words, match_ratio


align_caption_words = align_narration_words


def transcribe_scene_words(
    whisper_model: Any,
    wav_path: Path,
    narration_text: str,
    language: str,
) -> list[dict[str, Any]]:
    if not hasattr(whisper_model, "transcribe"):
        return []
    # Stripping tags guarantees zero tag leakage into Whisper's initial_prompt
    clean_prompt = strip_audio_tags(narration_text)

    # Content-addressable transcription caching for sub-2-second zero-waste rebuilds
    cache_dir = wav_path.parent.parent / "cache" / "audio"
    cache_file: Optional[Path] = None
    if wav_path.is_file():
        try:
            content_hash = hashlib.md5(
                wav_path.read_bytes() + clean_prompt.encode("utf-8") + language.encode("utf-8")
            ).hexdigest()
            cache_file = cache_dir / f"{content_hash}.words.json"
            if cache_file.is_file() and cache_file.stat().st_size > 0:
                return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    try:
        segments, _ = whisper_model.transcribe(
            str(wav_path),
            language=language,
            word_timestamps=True,
            beam_size=5,
            vad_filter=False,
            condition_on_previous_text=False,
            initial_prompt=clean_prompt,
        )
        words: list[dict[str, Any]] = []
        for seg in segments:
            seg_words = getattr(seg, "words", None) or []
            for w in seg_words:
                words.append(
                    {
                        "word": getattr(w, "word", ""),
                        "start": float(getattr(w, "start", 0.0)),
                        "end": float(getattr(w, "end", 0.0)),
                    }
                )
        if cache_file is not None and words:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                write_text_atomic(cache_file, json.dumps(words, ensure_ascii=False))
            except Exception:
                pass
        return words
    except Exception as exc:
        print(f"[WARN] faster-whisper transcription skipped: {exc}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Continuity Check
# ---------------------------------------------------------------------------

def verify_active_series_continuity_readonly(
    db_path: Path,
    ep_plan: EpisodePlan,
) -> None:
    if (
        getattr(ep_plan, "content_format", "episodic_series") == "standalone"
        or ep_plan.series_id is None
    ):
        return

    if not db_path.is_file():
        print(
            f"[WARN] Database not found at {db_path}; skipping active-series continuity check.",
            file=sys.stderr,
        )
        return

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = connect_db(db_path)
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='series'"
        ).fetchone()
        if not table_exists:
            return
        active = conn.execute(
            "SELECT * FROM series WHERE series_id = ? AND status = 'ACTIVE'",
            (ep_plan.series_id,),
        ).fetchone()
    finally:
        if conn is not None:
            conn.close()

    if active is None:
        print(
            f"[WARN] No ACTIVE series #{ep_plan.series_id} in episodes.db; proceeding with standalone audio build.",
            file=sys.stderr,
        )
        return

    mismatches: list[str] = []
    if active["series_title"] != ep_plan.series_title:
        mismatches.append(f"series_title ('{ep_plan.series_title}' != '{active['series_title']}')")
    if active["pillar"] != ep_plan.pillar:
        mismatches.append(f"pillar ('{ep_plan.pillar}' != '{active['pillar']}')")
    if active["tts_voice"] != ep_plan.tts_voice:
        mismatches.append(f"tts_voice ('{ep_plan.tts_voice}' != '{active['tts_voice']}')")
    if active["bgm_track"] != ep_plan.bgm_track:
        mismatches.append(f"bgm_track ('{ep_plan.bgm_track}' != '{active['bgm_track']}')")
    expected_ep = int(active["completed_episodes"]) + 1
    if ep_plan.episode_number_in_series != expected_ep:
        mismatches.append(
            f"episode_number_in_series ({ep_plan.episode_number_in_series} != {expected_ep})"
        )
    if mismatches:
        raise AudioBuildError(
            "episode_plan.json does not match ACTIVE series in episodes.db: "
            + "; ".join(mismatches)
        )


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def default_elevenlabs_factory(cfg: dict[str, Any], root: Path) -> Any:
    """Create centralized ElevenLabsEngine from configuration."""
    return ElevenLabsEngine(config=cfg, project_root=root)


class _LazyWhisperProxy:
    """Lazy loader for faster-whisper to allow sub-2-second rebuilds on cache hits."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self._instance: Any = None

    def transcribe(self, *args: Any, **kwargs: Any) -> Any:
        if self._instance is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise AudioBuildError(f"faster-whisper is not installed: {exc}") from exc
            align_cfg = self.cfg.get("alignment", {})
            self._instance = WhisperModel(
                align_cfg.get("model_size", "base"),
                device=align_cfg.get("device", "cpu"),
                compute_type=align_cfg.get("compute_type", "int8"),
            )
        return self._instance.transcribe(*args, **kwargs)


def default_whisper_factory(cfg: dict[str, Any]) -> Any:
    return _LazyWhisperProxy(cfg)


def _posix_rel(path: Path, root: Path) -> str:
    return PurePosixPath(path.relative_to(root).as_posix()).as_posix()


# ---------------------------------------------------------------------------
# Audio Pipeline Execution
# ---------------------------------------------------------------------------

def build_episode_audio(
    root: Path,
    tts_factory: Optional[Callable[..., Any]] = None,
    whisper_factory: Callable[[dict[str, Any]], Any] = default_whisper_factory,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute end-to-end speech synthesis, word alignment, and audio mastering."""
    require_executable("ffprobe")

    cfg = load_config(root)
    paths = resolve_paths(root, cfg)
    build_dir = paths["build_dir"]
    audio_dir = build_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    ep_path = build_dir / "episode_plan.json"
    raw_ep = load_json_file(ep_path, "episode_plan.json")
    try:
        ep_plan = EpisodePlan.model_validate(raw_ep, context={"config": cfg})
    except ValidationError as exc:
        raise AudioBuildError(f"episode_plan.json validation failed:\n{exc}") from exc

    emit_pacing_warnings(ep_plan, cfg)
    verify_active_series_continuity_readonly(paths["db_file"], ep_plan)

    active_lang = getattr(ep_plan, "language", cfg["channel"].get("primary_language", "hi"))
    text_reps, _ = load_pronunciations(root, cfg, lang=active_lang)

    # Initialize TTS Engine (accepts tts_factory or elevenlabs_factory)
    raw_factory = (
        tts_factory
        or kwargs.get("elevenlabs_factory")
        or default_elevenlabs_factory
    )
    if callable(raw_factory):
        try:
            tts_engine = raw_factory(cfg, root)
        except TypeError:
            try:
                tts_engine = raw_factory(root, cfg)
            except TypeError:
                try:
                    tts_engine = raw_factory()
                except TypeError:
                    try:
                        tts_engine = raw_factory(None, None)
                    except TypeError:
                        tts_engine = raw_factory
    else:
        tts_engine = raw_factory

    whisper_model = whisper_factory(cfg)

    tts_cfg = cfg.get("tts", {})
    expected_sr = int(tts_cfg.get("sample_rate", DEFAULT_SAMPLE_RATE))
    tag_templates = {**DEFAULT_TAG_TEMPLATES, **tts_cfg.get("tag_templates", {})}
    voice_settings = {**DEFAULT_VOICE_SETTINGS, **tts_cfg.get("voice_settings", {})}

    fps = int(cfg["video"]["fps"])
    width = int(cfg["video"]["width"])
    height = int(cfg["video"]["height"])

    # Clean stale scene WAVs from prior episodes
    for stale in audio_dir.glob("scene_*.wav"):
        try:
            stale.unlink()
        except OSError:
            pass

    concat_chunks: list[np.ndarray] = []
    manifest_scenes: list[dict[str, Any]] = []
    cursor_sec = 0.0
    total_scenes = len(ep_plan.scenes)

    for idx, scene in enumerate(ep_plan.scenes):
        # 1. Clean canonical text (tag-free) for Whisper and closed captions
        clean_text = strip_audio_tags(scene.narration_text)

        # 2. Apply pronunciation overrides to narration text for TTS synthesis
        phonetic_text = apply_pronunciations(clean_text, text_reps)

        # 3. Determine tagged text for vocal steering
        is_climax_scene = (
            getattr(ep_plan, "story_arc", None) is not None
            and getattr(ep_plan.story_arc, "climax_scene_index", None) == scene.scene_index
        )
        is_dialogue = getattr(scene, "speaker_role", "narrator") == "character_dialogue"

        if phonetic_text.lstrip().startswith("["):
            tagged_text = phonetic_text.strip()
        else:
            tag = resolve_scene_tag(
                scene=scene,
                scene_idx=idx,
                total_scenes=total_scenes,
                tag_templates=tag_templates,
                is_climax_scene=is_climax_scene,
            )
            tagged_text = f"{tag} {phonetic_text.strip()}"

        # 4. Dynamic pacing speed calculation
        lang_prof = cfg.get("languages", {}).get(active_lang, {})
        default_narr_speed = float(lang_prof.get("narrator_speed", cfg.get("tts", {}).get("speed", 0.92)))
        default_diag_speed = float(lang_prof.get("character_dialogue_speed", 0.90))

        if getattr(scene, "speed", None) is not None:
            speed = float(scene.speed)
        else:
            base_speed = default_diag_speed if is_dialogue else default_narr_speed
            emotion = getattr(scene, "emotion", "calm")
            shot_type = getattr(scene, "shot_type", None) or ""
            multiplier = 1.0
            if (
                emotion in ("wrath", "shock")
                or shot_type in ("dramatic_climax", "confrontation", "climax")
                or is_climax_scene
            ):
                multiplier = 1.04
            elif emotion in ("calm", "meditating") or shot_type in (
                "curtain_establishing",
                "philosophical_outro",
            ):
                multiplier = 0.96
            elif emotion == "smirk":
                multiplier = 1.01

            speed = round(min(1.15, max(0.80, base_speed * multiplier)), 3)

        # 5. Synthesize scene with ElevenLabs (passing calculated pacing speed)
        scene_voice_settings = {**voice_settings, "speed": speed}
        try:
            if hasattr(tts_engine, "synthesize_scene"):
                samples, sr = tts_engine.synthesize_scene(
                    tagged_text,
                    voice_settings=scene_voice_settings,
                )
            elif hasattr(tts_engine, "synthesize"):
                samples, sr = tts_engine.synthesize(
                    tagged_text,
                    voice_settings=scene_voice_settings,
                )
            elif hasattr(tts_engine, "create"):
                samples, sr = tts_engine.create(
                    tagged_text,
                    voice=None,
                    speed=speed,
                    lang=active_lang,
                )
            else:
                raise AudioBuildError(
                    f"TTS engine {type(tts_engine)} does not expose a supported synthesis method."
                )
        except Exception as exc:
            raise AudioBuildError(
                f"Speech synthesis failed on scene {scene.scene_index}: {exc}"
            ) from exc

        sr = int(sr)
        if expected_sr != sr:
            expected_sr = sr

        # 5. Pause duration calculation
        if idx == total_scenes - 1:
            pad_sec = FINAL_SCENE_PAD_SEC
        else:
            custom_ms = getattr(scene, "pause_after_ms", None)
            if custom_ms and custom_ms > 0:
                pad_sec = custom_ms / 1000.0
            else:
                shot_type = getattr(scene, "shot_type", None) or ""
                next_is_dialogue = (
                    idx + 1 < total_scenes
                    and getattr(ep_plan.scenes[idx + 1], "speaker_role", "narrator") == "character_dialogue"
                )
                if is_climax_scene or shot_type in ("dramatic_climax", "revelation"):
                    pad_sec = 0.40  # 400ms pause after dramatic climax/revelation
                elif next_is_dialogue or is_dialogue:
                    pad_sec = 0.18  # 180ms crisp conversational pause
                else:
                    pad_sec = INTER_SCENE_PAD_SEC  # default 0.20s (200ms)

        scene_wav = audio_dir / f"scene_{scene.scene_index}.wav"
        processed = trim_and_pad_audio(samples, expected_sr, pad_tail_sec=pad_sec)
        write_wav_atomic(scene_wav, processed, expected_sr)
        scene_dur = probe_duration_sec(scene_wav)

        # 6. Faster-whisper transcription & lexical alignment using clean text (zero tag contamination)
        whisper_words = transcribe_scene_words(
            whisper_model=whisper_model,
            wav_path=scene_wav,
            narration_text=clean_text,
            language="hi" if active_lang == "hi" else "en",
        )
        aligned_words, match_ratio = align_narration_words(
            narration_text=clean_text,
            whisper_words=whisper_words,
            scene_duration=scene_dur,
            global_offset=cursor_sec,
        )

        start_sec = round(cursor_sec, 4)
        end_sec = round(cursor_sec + scene_dur, 4)
        midpoint_sec = round(start_sec + scene_dur / 2.0, 4)

        scene_entry = scene.model_dump()
        scene_entry.update(
            {
                "speaker_role": "character_dialogue" if is_dialogue else "narrator",
                "narration_text": clean_text,
                "tts_text_applied": tagged_text,
                "audio_path": _posix_rel(scene_wav, root),
                "duration_sec": scene_dur,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "midpoint_sec": midpoint_sec,
                "start_frame": int(round(start_sec * fps)),
                "end_frame": int(round(end_sec * fps)),
                "alignment_match_ratio": match_ratio,
                "words": aligned_words,
                "applied_speed": speed,
                "applied_pause_sec": pad_sec,
            }
        )
        manifest_scenes.append(scene_entry)
        concat_chunks.append(processed)
        cursor_sec = end_sec

    assert expected_sr is not None and concat_chunks
    full_audio = np.concatenate(concat_chunks)
    full_wav = audio_dir / "narration_full.wav"
    write_wav_atomic(full_wav, full_audio, expected_sr)
    full_duration = probe_duration_sec(full_wav)

    sum_duration = round(sum(s["duration_sec"] for s in manifest_scenes), 4)
    if abs(full_duration - sum_duration) > DURATION_TOLERANCE_SEC:
        raise AudioBuildError(
            f"Duration mismatch: narration_full.wav={full_duration}s vs "
            f"sum(scenes)={sum_duration}s (tolerance={DURATION_TOLERANCE_SEC}s)."
        )

    active_format = (
        getattr(ep_plan, "content_format", None)
        or cfg.get("content_format", "episodic_series")
    )
    format_pacing = cfg.get("format_pacing", {}).get(active_format, {})
    default_pacing = cfg.get("episode_pacing", {})

    hard_min = float(
        format_pacing.get(
            "hard_duration_min_sec",
            default_pacing.get("hard_duration_min_sec", 30.0),
        )
    )
    hard_max = float(
        format_pacing.get(
            "hard_duration_max_sec",
            default_pacing.get("hard_duration_max_sec", 180.0),
        )
    )
    target_min = float(
        format_pacing.get(
            "target_duration_min_sec",
            default_pacing.get("target_duration_min_sec", 40.0),
        )
    )
    target_max = float(
        format_pacing.get(
            "target_duration_max_sec",
            default_pacing.get("target_duration_max_sec", 120.0),
        )
    )

    if getattr(ep_plan, "target_duration_range", None):
        plan_range = ep_plan.target_duration_range
        if isinstance(plan_range, dict):
            p_min = plan_range.get("min_seconds")
            p_max = plan_range.get("max_seconds")
            if p_min is not None and p_max is not None:
                target_min = float(p_min)
                target_max = float(p_max)
                hard_min = max(30.0, target_min * 0.85)
                hard_max = min(180.0, target_max * 1.15)

    hard_min = max(30.0, hard_min)
    hard_max = min(180.0, hard_max)

    if full_duration < hard_min or full_duration > hard_max:
        raise AudioBuildError(
            f"Total narration duration {full_duration:.2f}s violates hard bounds "
            f"[{hard_min:.0f}s, {hard_max:.0f}s] for format '{active_format}'. Adjust script word count in build/episode_plan.json."
        )

    # Master full narration with two-pass EBU R128 loudness normalization (content-cached)
    norm_wav = audio_dir / "narration_norm.wav"
    cache_dir = audio_dir.parent / "cache" / "audio"
    try:
        raw_bytes = full_wav.read_bytes()
        loudnorm_key = hashlib.md5(
            raw_bytes + f"loudnorm_-14.0_-1.5_{expected_sr}".encode("utf-8")
        ).hexdigest()
        cached_master = cache_dir / f"{loudnorm_key}.wav"
        if cached_master.is_file() and cached_master.stat().st_size > 0:
            shutil.copyfile(cached_master, full_wav)
            full_duration = probe_duration_sec(full_wav)
        else:
            two_pass_loudnorm(
                full_wav,
                norm_wav,
                target_lufs=-14.0,
                target_tp=-1.5,
                sample_rate=expected_sr,
            )
            if norm_wav.is_file() and norm_wav.stat().st_size > 0:
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(norm_wav, cached_master)
                except Exception:
                    pass
                os.replace(norm_wav, full_wav)
                full_duration = probe_duration_sec(full_wav)
    except Exception as exc:
        print(f"[WARN] Loudnorm normalization bypassed: {exc}", file=sys.stderr)
        if norm_wav.exists():
            try:
                norm_wav.unlink()
            except OSError:
                pass

    # Verify trailing silence floor (< -65 dBFS)
    trailing_rms = measure_trailing_rms(full_wav, tail_sec=0.50)
    if trailing_rms >= -65.0:
        raise AudioBuildError(
            f"Hiss detected in trailing silence: {trailing_rms:.1f} dBFS (must be < -65 dBFS)"
        )

    duration_warning: Optional[str] = None
    if full_duration < target_min or full_duration > target_max:
        duration_warning = (
            f"Total narration duration {full_duration:.2f}s is outside target retention "
            f"sweet spot [{target_min:.0f}s, {target_max:.0f}s] (within hard bounds)."
        )
        print(f"[WARN] {duration_warning}", file=sys.stderr)

    manifest_payload = {
        "schema_version": "2.0",
        "language": active_lang,
        "content_format": active_format,
        "series_id": ep_plan.series_id,
        "series_title": ep_plan.series_title,
        "pillar": ep_plan.pillar,
        "episode_number_in_series": ep_plan.episode_number_in_series,
        "total_planned_episodes": ep_plan.total_planned_episodes,
        "global_episode_number": ep_plan.global_episode_number,
        "youtube_title": ep_plan.youtube_title,
        "duration_target_seconds": getattr(ep_plan, "target_duration_sec", None),
        "target_duration_range": getattr(ep_plan, "target_duration_range", None),
        "story_arc": ep_plan.story_arc.model_dump()
        if getattr(ep_plan, "story_arc", None)
        else None,
        "narrative_structure": getattr(ep_plan, "narrative_structure", None),
        "tts_engine": cfg["tts"]["engine"],
        "tts_voice": ep_plan.tts_voice,
        "bgm_track": ep_plan.bgm_track,
        "bespoke_asset_path": ep_plan.bespoke_asset_path,
        "video": {
            "width": width,
            "height": height,
            "fps": fps,
            "safe_zones": cfg["video"]["safe_zones"],
        },
        "audio": {
            "sample_rate": expected_sr,
            "narration_full_path": _posix_rel(full_wav, root),
            "total_duration_sec": full_duration,
            "total_frames": int(round(full_duration * fps)),
            "trailing_silence_rms_dbfs": trailing_rms,
        },
        "scenes": manifest_scenes,
        "beats": manifest_scenes,
    }

    manifest_path = build_dir / "manifest.js"
    manifest_js = (
        "// Auto-generated by scripts/build_audio.py — do not edit manually.\n"
        f"window.EPISODE_MANIFEST = {json.dumps(manifest_payload, indent=2, ensure_ascii=False)};\n"
    )
    write_text_atomic(manifest_path, manifest_js)

    audio_manifest_path = audio_dir / "audio_manifest.json"
    write_text_atomic(
        audio_manifest_path,
        json.dumps(manifest_payload, indent=2, ensure_ascii=False),
    )

    return {
        "status": "ok",
        "action": "build_audio",
        "language": active_lang,
        "episode_number_in_series": ep_plan.episode_number_in_series,
        "global_episode_number": ep_plan.global_episode_number,
        "tts_voice": ep_plan.tts_voice,
        "sample_rate": expected_sr,
        "scene_count": len(manifest_scenes),
        "total_duration_sec": full_duration,
        "trailing_silence_rms_dbfs": trailing_rms,
        "narration_full_wav": _posix_rel(full_wav, root),
        "manifest_js": _posix_rel(manifest_path, root),
        "avg_alignment_match_ratio": round(
            sum(s["alignment_match_ratio"] for s in manifest_scenes) / len(manifest_scenes), 4
        ),
        "duration_warning": duration_warning,
    }


def main() -> int:
    if len(sys.argv) > 1:
        print(
            "[ERROR] scripts/build_audio.py takes zero CLI arguments "
            "(strict Antigravity whitelist compliance).",
            file=sys.stderr,
        )
        return 1
    try:
        root = get_project_root()
        result = build_episode_audio(root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        print("[ERROR] Audio build interrupted by user.", file=sys.stderr)
        return 130
    except (AudioBuildError, StateError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[FATAL] Unexpected error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
