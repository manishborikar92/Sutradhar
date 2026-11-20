#!/usr/bin/env python3
"""Sutradhar Milestone 3 — Offline Kokoro-82M TTS & faster-whisper Word Alignment Engine.

Whitelisted zero-argument CLI invocation:
    python scripts/build_audio.py

Reads:
    - config.yaml
    - pronunciations.yaml
    - build/episode_plan.json
    - episodes.db (read-only active-series continuity check when present)

Writes (atomically):
    - build/audio/scene_{1..N}.wav
    - build/audio/narration_full.wav
    - build/manifest.js  (window.EPISODE_MANIFEST = {...};)
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
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Optional

# Compatibility shim: PyAV 19+ removed metadata_errors parameter from av.open,
# but faster-whisper 1.2.1 still passes metadata_errors="ignore".
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KOKORO_RELEASE_BASE = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)
KOKORO_MODEL_URLS = {
    "kokoro-v1.0.onnx": f"{KOKORO_RELEASE_BASE}/kokoro-v1.0.onnx",
    "voices-v1.0.bin": f"{KOKORO_RELEASE_BASE}/voices-v1.0.bin",
}

KOKORO_EXPECTED_SIZES = {
    "kokoro-v1.0.onnx": 325532387,
    "voices-v1.0.bin": 28214398,
}
KOKORO_MODEL_MIN_SIZES = {
    "kokoro-v1.0.onnx": 250 * 1024 * 1024,
    "voices-v1.0.bin": 10 * 1024 * 1024,
}
KOKORO_KNOWN_SHA256 = {
    "kokoro-v1.0.onnx": "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}

SILENCE_THRESHOLD = 0.003        # ~ -50 dBFS amplitude threshold for edge trim
TRIM_MARGIN_SEC = 0.04           # Keep 40ms onset/release margin so plosives stay clean
INTER_SCENE_PAD_SEC = 0.12       # Natural 120ms breath between scenes
FINAL_SCENE_PAD_SEC = 0.15       # Clean 150ms tail on the final scene
DURATION_TOLERANCE_SEC = 0.08    # Max drift allowed between sum(scenes) and narration_full.wav
MIN_PEAK_AMPLITUDE = 1e-4        # Reject silent / corrupted TTS output
WORD_NORM_RE = re.compile(r"[^a-z0-9']+")


class AudioBuildError(RuntimeError):
    """Raised when audio synthesis, validation, or alignment fails."""


# ---------------------------------------------------------------------------
# System & Model Prerequisites
# ---------------------------------------------------------------------------

def require_executable(name: str) -> str:
    exe = shutil.which(name)
    if not exe:
        raise AudioBuildError(
            f"Required executable '{name}' not found in PATH. Install FFmpeg/FFprobe first."
        )
    return exe


def probe_duration_sec(audio_path: Path) -> float:
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


def _compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _quarantine_corrupt_file(file_path: Path, reason: str) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    quarantine_dir = file_path.parent / "_quarantine" / timestamp
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    target = quarantine_dir / file_path.name
    shutil.move(str(file_path), str(target))
    print(
        f"[WARN] Quarantined invalid model file '{file_path.name}' -> '{target}' (Reason: {reason})",
        file=sys.stderr,
    )
    return target


def _validate_file_structural(file_path: Path) -> None:
    """Check that ONNX models load without protobuf parse errors and voice bins are valid archives."""
    if file_path.name.endswith(".onnx"):
        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.log_severity_level = 3  # Error only
            ort.InferenceSession(str(file_path), sess_options=opts)
        except Exception as exc:
            raise AudioBuildError(
                f"ONNX model '{file_path.name}' failed structural Protobuf parsing: {exc}"
            ) from exc
    elif file_path.name.endswith(".bin"):
        try:
            with zipfile.ZipFile(str(file_path), "r") as z:
                names = z.namelist()
                if not names or not any(n.endswith(".npy") for n in names):
                    raise AudioBuildError(f"Voice archive '{file_path.name}' contains no .npy voice vectors.")
        except Exception as exc:
            raise AudioBuildError(
                f"Voice archive '{file_path.name}' failed structural ZIP validation: {exc}"
            ) from exc


def _download_file_atomic(
    url: str,
    dest: Path,
    expected_size: Optional[int] = None,
    expected_sha: Optional[str] = None,
    min_size: int = 0,
    max_retries: int = 3,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part_path = dest.with_suffix(dest.suffix + ".part")
    print(f"[INFO] Downloading Kokoro asset: {dest.name} from {url} ...", file=sys.stderr)

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            existing_size = part_path.stat().st_size if part_path.is_file() else 0
            req = urllib.request.Request(url, headers={"User-Agent": "Sutradhar/0.1"})
            mode = "wb"
            if existing_size > 0:
                req.add_header("Range", f"bytes={existing_size}-")
                mode = "ab"

            with urllib.request.urlopen(req, timeout=120) as resp:
                status = getattr(resp, "status", 200)
                if status == 200 and existing_size > 0:
                    mode = "wb"
                    existing_size = 0

                with part_path.open(mode) as out_fh:
                    downloaded = existing_size
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        out_fh.write(chunk)
                        downloaded += len(chunk)

            part_size = part_path.stat().st_size
            if part_size == 0:
                raise AudioBuildError(f"Downloaded file '{dest.name}' is empty.")
            if min_size > 0 and part_size < min_size:
                raise AudioBuildError(
                    f"Downloaded file '{dest.name}' size ({part_size:,} bytes) is below minimum {min_size:,} bytes."
                )
            if expected_size is not None and part_size != expected_size:
                raise AudioBuildError(
                    f"Downloaded file '{dest.name}' size mismatch: got {part_size:,} bytes, expected {expected_size:,} bytes."
                )

            if expected_sha:
                actual_sha = _compute_sha256(part_path)
                if actual_sha.lower() != expected_sha.lower():
                    raise AudioBuildError(
                        f"Checksum mismatch for '{dest.name}': got {actual_sha}, expected {expected_sha}."
                    )

            _validate_file_structural(part_path)

            os.replace(part_path, dest)
            print(f"[INFO] Cached and verified {dest.name} ({dest.stat().st_size:,} bytes).", file=sys.stderr)
            return
        except (AudioBuildError, Exception) as exc:
            last_error = exc
            print(f"[WARN] Download attempt {attempt}/{max_retries} failed for '{dest.name}': {exc}", file=sys.stderr)
            if attempt < max_retries:
                time.sleep(2.0 * attempt)

    if part_path.exists():
        try:
            part_path.unlink()
        except OSError:
            pass
    raise AudioBuildError(f"Failed to download and verify '{dest.name}' from {url}: {last_error}")


def ensure_kokoro_models(root: Path, cfg: dict[str, Any]) -> tuple[Path, Path]:
    tts_cfg = cfg["tts"]
    model_dir = (root / tts_cfg["model_dir"]).resolve()
    model_name = tts_cfg["model_file"]
    voices_name = tts_cfg["voices_file"]
    model_path = model_dir / model_name
    voices_path = model_dir / voices_name

    allow_download = os.environ.get("SUTRADHAR_ALLOW_MODEL_DOWNLOAD", "1").strip() != "0"

    for fname, fpath in ((model_name, model_path), (voices_name, voices_path)):
        min_sz = KOKORO_MODEL_MIN_SIZES.get(fname, 0)
        exp_sz = KOKORO_EXPECTED_SIZES.get(fname)
        exp_sha = KOKORO_KNOWN_SHA256.get(fname)

        is_valid = False
        if fpath.is_file():
            actual_sz = fpath.stat().st_size
            if actual_sz >= min_sz and (exp_sz is None or actual_sz == exp_sz):
                try:
                    if exp_sha:
                        actual_sha = _compute_sha256(fpath)
                        if actual_sha.lower() != exp_sha.lower():
                            raise AudioBuildError(f"SHA-256 mismatch: {actual_sha} != {exp_sha}")
                    _validate_file_structural(fpath)
                    is_valid = True
                except Exception as val_exc:
                    if allow_download:
                        _quarantine_corrupt_file(fpath, str(val_exc))
                    else:
                        raise AudioBuildError(
                            f"Model file '{fpath}' is corrupt/invalid ({val_exc}) and "
                            "SUTRADHAR_ALLOW_MODEL_DOWNLOAD=0."
                        ) from val_exc
            else:
                reason = f"File size {actual_sz:,} bytes below min {min_sz:,} bytes"
                if allow_download:
                    _quarantine_corrupt_file(fpath, reason)
                else:
                    raise AudioBuildError(f"Model file '{fpath}' invalid: {reason} and SUTRADHAR_ALLOW_MODEL_DOWNLOAD=0.")

        if not is_valid:
            url = KOKORO_MODEL_URLS.get(fname)
            if not allow_download or not url:
                raise AudioBuildError(
                    f"Missing or invalid Kokoro model file: {fpath}. "
                    f"Download from {url or 'Kokoro-ONNX v1.0 release'} or set "
                    "SUTRADHAR_ALLOW_MODEL_DOWNLOAD=1."
                )
            _download_file_atomic(
                url=url,
                dest=fpath,
                expected_size=exp_sz,
                expected_sha=exp_sha,
                min_size=min_sz,
            )

    try:
        from kokoro_onnx import Kokoro

        test_kokoro = Kokoro(str(model_path), str(voices_path))
        installed_voices = test_kokoro.get_voices()
        if not installed_voices:
            raise AudioBuildError("Kokoro model loaded but get_voices() returned empty list.")
    except Exception as joint_exc:
        raise AudioBuildError(
            f"Joint Kokoro model/voices validation failed for ({model_path.name}, {voices_path.name}): {joint_exc}"
        ) from joint_exc

    return model_path, voices_path


# ---------------------------------------------------------------------------
# Pronunciation Overrides
# ---------------------------------------------------------------------------

def load_pronunciations(root: Path, cfg: dict[str, Any]) -> dict[str, str]:
    pron_rel = cfg["tts"].get("pronunciations_file", "pronunciations.yaml")
    pron_path = (root / pron_rel).resolve()
    if not pron_path.is_file():
        raise AudioBuildError(f"Missing pronunciations file: {pron_path}")
    try:
        with pron_path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise AudioBuildError(f"Malformed YAML in {pron_path}: {exc}") from exc

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise AudioBuildError(f"Expected mapping in {pron_path}")
    replacements = raw.get("replacements", {})
    if not isinstance(replacements, dict):
        raise AudioBuildError(f"'replacements' in {pron_path} must be a mapping")

    cleaned: dict[str, str] = {}
    for key, val in replacements.items():
        if not isinstance(key, str) or not isinstance(val, str):
            raise AudioBuildError(
                f"Invalid pronunciation entry in {pron_path}: {key!r} -> {val!r}"
            )
        k, v = key.strip(), val.strip()
        if k and v:
            cleaned[k] = v
    return cleaned


def apply_pronunciations(text: str, replacements: dict[str, str]) -> str:
    """Apply whole-word case-insensitive phonetic overrides (longest key first)."""
    if not replacements:
        return text
    ordered_keys = sorted(replacements.keys(), key=len, reverse=True)
    lower_map = {k.lower(): v for k, v in replacements.items()}
    pattern = re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(re.escape(k) for k in ordered_keys) + r")(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    return pattern.sub(lambda m: lower_map[m.group(0).lower()], text)


# ---------------------------------------------------------------------------
# Kokoro Voice Resolution & Audio Post-Processing
# ---------------------------------------------------------------------------

def parse_voice_spec(voice_spec: str) -> list[tuple[str, float]]:
    cleaned = voice_spec.strip()
    if "+" not in cleaned:
        return [(cleaned, 1.0)]
    components: list[tuple[str, float]] = []
    for part in cleaned.split("+"):
        vid, raw_weight = part.split(":", 1)
        components.append((vid.strip(), float(raw_weight.strip())))
    return components


def _get_single_voice_vector(kokoro: Any, voice_id: str) -> np.ndarray:
    if hasattr(kokoro, "get_voice_style"):
        return np.asarray(kokoro.get_voice_style(voice_id), dtype=np.float32)
    voices_store = getattr(kokoro, "voices", None)
    if voices_store is not None and voice_id in voices_store:
        return np.asarray(voices_store[voice_id], dtype=np.float32)
    raise AudioBuildError(
        f"Installed kokoro-onnx instance does not expose voice style vectors for '{voice_id}'."
    )


def resolve_kokoro_voice(kokoro: Any, voice_spec: str) -> str | np.ndarray:
    available = set(kokoro.get_voices())
    components = parse_voice_spec(voice_spec)
    missing = [vid for vid, _ in components if vid not in available]
    if missing:
        sample_en = sorted(v for v in available if v.startswith(("am_", "bm_", "af_", "bf_")))
        raise AudioBuildError(
            f"Voice ID(s) {missing} not found in installed Kokoro model. "
            f"Available English voices: {sample_en}"
        )

    if len(components) == 1:
        return components[0][0]

    total_weight = sum(w for _, w in components)
    blended: Optional[np.ndarray] = None
    for vid, weight in components:
        vec = _get_single_voice_vector(kokoro, vid)
        weighted = vec * (weight / total_weight)
        blended = weighted if blended is None else (blended + weighted)
    assert blended is not None
    return blended.astype(np.float32)


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
# Deterministic Word Alignment (faster-whisper -> Canonical Caption Tokens)
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


def align_caption_words(
    caption_text: str,
    whisper_words: list[dict[str, Any]],
    scene_duration: float,
    global_offset: float,
) -> tuple[list[dict[str, Any]], float]:
    """Map faster-whisper word timestamps deterministically onto canonical caption words."""
    canon_tokens = caption_text.split()
    if not canon_tokens:
        raise AudioBuildError("Cannot align empty caption_text.")
    if not whisper_words:
        raise AudioBuildError("faster-whisper detected zero spoken words in synthesized audio.")

    cleaned_whisper: list[tuple[str, float, float]] = []
    for item in whisper_words:
        w_text = str(item.get("word", "")).strip()
        w_norm = _norm_token(w_text)
        if not w_norm:
            continue
        w_start = max(0.0, min(scene_duration, float(item["start"])))
        w_end = max(w_start + 0.01, min(scene_duration, float(item["end"])))
        cleaned_whisper.append((w_norm, w_start, w_end))

    if not cleaned_whisper:
        raise AudioBuildError("faster-whisper produced no usable alphanumeric word timestamps.")

    canon_norms = [_norm_token(t) for t in canon_tokens]
    whisper_norms = [w[0] for w in cleaned_whisper]

    matcher = difflib.SequenceMatcher(None, canon_norms, whisper_norms, autojunk=False)
    opcodes = matcher.get_opcodes()

    aligned_raw: list[Optional[tuple[str, float, float]]] = [None] * len(canon_tokens)
    matched_count = 0

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for c_idx, w_idx in zip(range(i1, i2), range(j1, j2)):
                _, ws, we = cleaned_whisper[w_idx]
                aligned_raw[c_idx] = (canon_tokens[c_idx], ws, we)
                matched_count += 1
        elif tag == "replace":
            span_start = cleaned_whisper[j1][1]
            span_end = cleaned_whisper[j2 - 1][2]
            dist = _distribute_span(canon_tokens[i1:i2], span_start, span_end)
            for c_idx, item in zip(range(i1, i2), dist):
                aligned_raw[c_idx] = item

    # Fill any 'delete' gaps (canonical tokens omitted by Whisper) between adjacent anchors.
    idx = 0
    n = len(canon_tokens)
    while idx < n:
        if aligned_raw[idx] is not None:
            idx += 1
            continue
        gap_start_idx = idx
        while idx < n and aligned_raw[idx] is None:
            idx += 1
        gap_end_idx = idx  # exclusive

        left_time = aligned_raw[gap_start_idx - 1][2] if gap_start_idx > 0 and aligned_raw[gap_start_idx - 1] else 0.0
        right_time = (
            aligned_raw[gap_end_idx][1]
            if gap_end_idx < n and aligned_raw[gap_end_idx]
            else scene_duration
        )
        if right_time <= left_time:
            right_time = min(scene_duration, left_time + 0.08 * (gap_end_idx - gap_start_idx))
        dist = _distribute_span(canon_tokens[gap_start_idx:gap_end_idx], left_time, right_time)
        for c_idx, item in zip(range(gap_start_idx, gap_end_idx), dist):
            aligned_raw[c_idx] = item

    # Enforce strict monotonic clamping within [0.0, scene_duration].
    words_out: list[dict[str, Any]] = []
    prev_end = 0.0
    for item in aligned_raw:
        assert item is not None
        tok, st, en = item
        st = max(prev_end, min(scene_duration, st))
        en = max(st, min(scene_duration, en))
        if en == st and st < scene_duration:
            en = min(scene_duration, st + 0.02)
        prev_end = en
        words_out.append(
            {
                "word": tok,
                "start": round(st, 4),
                "end": round(en, 4),
                "global_start": round(global_offset + st, 4),
                "global_end": round(global_offset + en, 4),
            }
        )

    match_ratio = round(matched_count / max(1, len(canon_tokens)), 4)
    return words_out, match_ratio


def transcribe_scene_words(
    whisper_model: Any,
    wav_path: Path,
    caption_text: str,
    language: str,
) -> list[dict[str, Any]]:
    segments, _ = whisper_model.transcribe(
        str(wav_path),
        language=language,
        word_timestamps=True,
        beam_size=5,
        vad_filter=False,
        condition_on_previous_text=False,
        initial_prompt=caption_text,
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
    return words


# ---------------------------------------------------------------------------
# Read-Only Database Continuity Check
# ---------------------------------------------------------------------------

def verify_active_series_continuity_readonly(
    db_path: Path,
    ep_plan: EpisodePlan,
) -> None:
    """Validate episode_plan against ACTIVE series in episodes.db without mutating DB."""
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
        active = conn.execute("SELECT * FROM series WHERE status = 'ACTIVE'").fetchone()
    finally:
        if conn is not None:
            conn.close()

    if active is None:
        print(
            "[WARN] No ACTIVE series in episodes.db; proceeding with standalone audio build.",
            file=sys.stderr,
        )
        return

    mismatches: list[str] = []
    if int(active["series_id"]) != ep_plan.series_id:
        mismatches.append(f"series_id ({ep_plan.series_id} != {active['series_id']})")
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
# Core Pipeline Execution
# ---------------------------------------------------------------------------

def default_kokoro_factory(model_path: Path, voices_path: Path) -> Any:
    try:
        from kokoro_onnx import Kokoro
    except ImportError as exc:
        raise AudioBuildError(f"kokoro-onnx is not installed: {exc}") from exc
    return Kokoro(str(model_path), str(voices_path))


def default_whisper_factory(cfg: dict[str, Any]) -> Any:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AudioBuildError(f"faster-whisper is not installed: {exc}") from exc
    align_cfg = cfg["alignment"]
    return WhisperModel(
        align_cfg["model_size"],
        device=align_cfg["device"],
        compute_type=align_cfg["compute_type"],
    )


def _posix_rel(path: Path, root: Path) -> str:
    return PurePosixPath(path.relative_to(root).as_posix()).as_posix()


def build_episode_audio(
    root: Path,
    kokoro_factory: Callable[[Path, Path], Any] = default_kokoro_factory,
    whisper_factory: Callable[[dict[str, Any]], Any] = default_whisper_factory,
) -> dict[str, Any]:
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

    replacements = load_pronunciations(root, cfg)
    model_path, voices_path = ensure_kokoro_models(root, cfg)

    kokoro = kokoro_factory(model_path, voices_path)
    resolved_voice = resolve_kokoro_voice(kokoro, ep_plan.tts_voice)
    whisper_model = whisper_factory(cfg)

    tts_lang = cfg["tts"].get("language", "en-us")
    tts_speed = float(cfg["tts"].get("speed", 1.0))
    align_lang = cfg["alignment"].get("language", "en")
    fps = int(cfg["video"]["fps"])
    width = int(cfg["video"]["width"])
    height = int(cfg["video"]["height"])

    # Clean stale scene WAVs from prior episodes before synthesizing new ones
    for stale in audio_dir.glob("scene_*.wav"):
        stale.unlink()

    concat_chunks: list[np.ndarray] = []
    manifest_scenes: list[dict[str, Any]] = []
    expected_sr: Optional[int] = None
    cursor_sec = 0.0
    total_scenes = len(ep_plan.scenes)

    for idx, scene in enumerate(ep_plan.scenes):
        tts_text = apply_pronunciations(scene.narration_text, replacements)
        try:
            samples, sr = kokoro.create(
                tts_text,
                voice=resolved_voice,
                speed=tts_speed,
                lang=tts_lang,
            )
        except Exception as exc:
            raise AudioBuildError(
                f"Kokoro synthesis failed on scene {scene.scene_index}: {exc}"
            ) from exc

        if expected_sr is None:
            expected_sr = int(sr)
        elif int(sr) != expected_sr:
            raise AudioBuildError(
                f"Inconsistent sample rate on scene {scene.scene_index}: {sr} != {expected_sr}"
            )

        pad_sec = FINAL_SCENE_PAD_SEC if idx == total_scenes - 1 else INTER_SCENE_PAD_SEC
        processed = trim_and_pad_audio(samples, expected_sr, pad_tail_sec=pad_sec)

        scene_wav = audio_dir / f"scene_{scene.scene_index}.wav"
        write_wav_atomic(scene_wav, processed, expected_sr)
        scene_dur = probe_duration_sec(scene_wav)

        whisper_words = transcribe_scene_words(
            whisper_model=whisper_model,
            wav_path=scene_wav,
            caption_text=scene.caption_text,
            language=align_lang,
        )
        aligned_words, match_ratio = align_caption_words(
            caption_text=scene.caption_text,
            whisper_words=whisper_words,
            scene_duration=scene_dur,
            global_offset=cursor_sec,
        )
        if match_ratio < 0.5:
            print(
                f"[WARN] Scene {scene.scene_index} low Whisper lexical match ratio "
                f"({match_ratio:.2f}); verify pronunciations.yaml entries.",
                file=sys.stderr,
            )

        start_sec = round(cursor_sec, 4)
        end_sec = round(cursor_sec + scene_dur, 4)
        midpoint_sec = round(start_sec + scene_dur / 2.0, 4)

        scene_entry = scene.model_dump()
        scene_entry.update(
            {
                "tts_text_applied": tts_text,
                "audio_path": _posix_rel(scene_wav, root),
                "duration_sec": scene_dur,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "midpoint_sec": midpoint_sec,
                "start_frame": int(round(start_sec * fps)),
                "end_frame": int(round(end_sec * fps)),
                "alignment_match_ratio": match_ratio,
                "words": aligned_words,
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

    pacing_cfg = cfg["episode_pacing"]
    hard_min = float(pacing_cfg["hard_duration_min_sec"])
    hard_max = float(pacing_cfg["hard_duration_max_sec"])
    target_min = float(pacing_cfg["target_duration_min_sec"])
    target_max = float(pacing_cfg["target_duration_max_sec"])

    if full_duration < hard_min or full_duration > hard_max:
        raise AudioBuildError(
            f"Total narration duration {full_duration:.2f}s violates hard bounds "
            f"[{hard_min:.0f}s, {hard_max:.0f}s]. Adjust script word count in build/episode_plan.json."
        )

    duration_warning: Optional[str] = None
    if full_duration < target_min or full_duration > target_max:
        duration_warning = (
            f"Total narration duration {full_duration:.2f}s is outside target retention "
            f"sweet spot [{target_min:.0f}s, {target_max:.0f}s] (within hard bounds)."
        )
        print(f"[WARN] {duration_warning}", file=sys.stderr)

    manifest_payload = {
        "schema_version": "1.0",
        "series_id": ep_plan.series_id,
        "series_title": ep_plan.series_title,
        "pillar": ep_plan.pillar,
        "episode_number_in_series": ep_plan.episode_number_in_series,
        "total_planned_episodes": ep_plan.total_planned_episodes,
        "global_episode_number": ep_plan.global_episode_number,
        "youtube_title": ep_plan.youtube_title,
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
        },
        "scenes": manifest_scenes,
    }

    manifest_path = build_dir / "manifest.js"
    manifest_js = (
        "// Auto-generated by scripts/build_audio.py — do not edit manually.\n"
        f"window.EPISODE_MANIFEST = {json.dumps(manifest_payload, indent=2, ensure_ascii=False)};\n"
    )
    write_text_atomic(manifest_path, manifest_js)

    return {
        "status": "ok",
        "action": "build_audio",
        "episode_number_in_series": ep_plan.episode_number_in_series,
        "global_episode_number": ep_plan.global_episode_number,
        "tts_voice": ep_plan.tts_voice,
        "sample_rate": expected_sr,
        "scene_count": len(manifest_scenes),
        "total_duration_sec": full_duration,
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
    except Exception as exc:  # pragma: no cover - defensive catch-all
        print(f"[FATAL] Unexpected error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())