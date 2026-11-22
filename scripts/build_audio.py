#!/usr/bin/env python3
"""Sutradhar — Dual-Language Expressive Audio Engine.

Whitelisted zero-argument CLI invocation:
    python scripts/build_audio.py

Reads:
    - config.yaml
    - pronunciations_en.yaml / pronunciations_hi.yaml (with pronunciations.yaml fallback)
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
import tempfile
import time
import urllib.error
import urllib.request
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

# ---------------------------------------------------------------------------
# Constants & Model Pins
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
    if file_path.name.endswith(".onnx"):
        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            ort.InferenceSession(str(file_path), sess_options=opts)
        except Exception as exc:
            raise AudioBuildError(
                f"Protobuf parsing failed for ONNX model '{file_path.name}': {exc}"
            ) from exc
    elif file_path.name.endswith(".bin"):
        try:
            with zipfile.ZipFile(str(file_path), "r") as zf:
                bad = zf.testzip()
                if bad is not None:
                    raise AudioBuildError(f"Corrupt entry in ZIP archive '{file_path.name}': {bad}")
        except Exception as exc:
            raise AudioBuildError(
                f"ZIP validation failed for voice archive '{file_path.name}': {exc}"
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
            req = urllib.request.Request(url, headers={"User-Agent": "Sutradhar/0.2"})
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

def load_pronunciations(root: Path, cfg: dict[str, Any], lang: str = "en") -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Load language-specific pronunciation text and IPA replacement rules."""
    lang_prof = cfg.get("languages", {}).get(lang, {})
    pron_file = lang_prof.get("pronunciations_file")
    if not pron_file:
        pron_file = f"pronunciations_{lang}.yaml" if (root / f"pronunciations_{lang}.yaml").is_file() else "pronunciations.yaml"

    pron_path = (root / pron_file).resolve()
    if not pron_path.is_file():
        # Fall back to root pronunciations.yaml
        fallback = (root / "pronunciations.yaml").resolve()
        if fallback.is_file():
            pron_path = fallback
        else:
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

    ipa_rules: list[tuple[str, str]] = []
    if "ipa_replacements" in raw and isinstance(raw["ipa_replacements"], list):
        for item in raw["ipa_replacements"]:
            if isinstance(item, dict) and "pattern" in item and "replacement" in item:
                ipa_rules.append((item["pattern"], item["replacement"]))

    return text_reps, ipa_rules


def apply_pronunciations(text: str, replacements: dict[str, str]) -> str:
    """Apply whole-word case-insensitive phonetic text overrides."""
    if not replacements:
        return text
    ordered_keys = sorted(replacements.keys(), key=len, reverse=True)
    lower_map = {k.lower(): v for k, v in replacements.items()}
    # Support word boundary matching for both ASCII and Devanagari
    pattern = re.compile(
        r"(?<![A-Za-z0-9\u0900-\u097F])(" + "|".join(re.escape(k) for k in ordered_keys) + r")(?![A-Za-z0-9\u0900-\u097F])",
        re.IGNORECASE,
    )
    return pattern.sub(lambda m: lower_map.get(m.group(0).lower(), lower_map.get(m.group(0), m.group(0))), text)


# ---------------------------------------------------------------------------
# Kokoro Voice Resolution & Audio Post-Processing
# ---------------------------------------------------------------------------

def parse_voice_spec(voice_spec: Any) -> list[tuple[str, float]]:
    if isinstance(voice_spec, dict):
        return [(str(k).strip(), float(v)) for k, v in voice_spec.items()]
    cleaned = str(voice_spec).strip()
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


def resolve_kokoro_voice(kokoro: Any, voice_spec: Any) -> str | np.ndarray:
    available = set(kokoro.get_voices())
    components = parse_voice_spec(voice_spec)
    missing = [vid for vid, _ in components if vid not in available]
    if missing:
        sample_voices = sorted(available)
        raise AudioBuildError(
            f"Voice ID(s) {missing} not found in installed Kokoro model. "
            f"Available voices: {sample_voices}"
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


# ---------------------------------------------------------------------------
# Acoustic Metrics & DSP Chains
# ---------------------------------------------------------------------------

def measure_spectral_centroid(x: np.ndarray, fs: int, max_freq: int = 4000) -> float:
    """Computes speech-band spectral centroid (Hz) as proxy for vocal pitch/resonance."""
    magnitudes = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1.0 / fs)
    mask = (freqs >= 50) & (freqs <= max_freq) if max_freq else (freqs >= 50)
    return float(np.sum(magnitudes[mask] * freqs[mask]) / (np.sum(magnitudes[mask]) + 1e-12))


def measure_f0(x: np.ndarray, fs: int) -> float:
    """Estimates fundamental vocal frequency F0 (Hz) via short-time autocorrelation."""
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
    """Measures RMS of the trailing silence (dBFS). Pure digital silence is < -65 dBFS."""
    data, fs = sf.read(str(wav_path))
    if data.ndim > 1:
        data = data[:, 0]
    n_tail = int(tail_sec * fs)
    tail = data[-n_tail:] if len(data) >= n_tail else data
    rms = np.sqrt(np.mean(tail ** 2) + 1e-15)
    return float(20 * np.log10(rms))


def apply_dialogue_dsp(
    raw_wav: Path,
    out_wav: Path,
    pitch_ratio: float = 0.917,
) -> None:
    """Applies dynamic-sample-rate pitch drop and chest warmth to character dialogue."""
    info = sf.info(str(raw_wav))
    sr_in = info.samplerate
    target_rate = int(sr_in * pitch_ratio)
    atempo = 1.0 / pitch_ratio

    af = (
        f"asetrate={target_rate},aresample={sr_in},atempo={atempo:.4f},"
        "equalizer=f=115:width_type=o:w=1.0:g=3.5,"
        "equalizer=f=3500:width_type=o:w=1.2:g=-1.5,"
        "acompressor=threshold=-16dB:ratio=2.8:attack=10:release=150,"
        "aecho=0.8:0.88:20:0.06"
    )

    cmd = ["ffmpeg", "-y", "-i", str(raw_wav), "-ar", str(sr_in), "-af", af, str(out_wav)]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def apply_narrator_dsp(raw_wav: Path, out_wav: Path) -> None:
    """Applies gentle theatrical EQ, HPF, and dynamic control to narrator voice."""
    info = sf.info(str(raw_wav))
    sr_in = info.samplerate
    af = (
        "highpass=f=75,"
        "equalizer=f=160:width_type=o:w=1.0:g=2.0,"
        "equalizer=f=4500:width_type=o:w=1.2:g=-2.5,"
        "equalizer=f=10000:width_type=o:w=1.5:g=1.5,"
        "acompressor=threshold=-18dB:ratio=2.2:attack=15:release=120,"
        "aecho=0.8:0.88:15:0.03"
    )
    cmd = ["ffmpeg", "-y", "-i", str(raw_wav), "-ar", str(sr_in), "-af", af, str(out_wav)]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def two_pass_loudnorm(
    in_wav: Path,
    out_wav: Path,
    target_lufs: float = -14.0,
    target_tp: float = -1.5,
) -> None:
    """Runs professional two-pass EBU R128 loudness normalization with linear gain."""
    pass1_res = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(in_wav),
            "-af", f"loudnorm=I={target_lufs}:TP={target_tp}:LRA=9:print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    stderr = pass1_res.stderr
    idx_start = stderr.rfind("{")
    idx_end = stderr.rfind("}")
    if idx_start == -1 or idx_end == -1:
        # Fallback to single-pass if JSON parse fails
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(in_wav), "-af", f"loudnorm=I={target_lufs}:TP={target_tp}:LRA=9", "-ar", "48000", str(out_wav)],
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
        ["ffmpeg", "-y", "-i", str(in_wav), "-af", norm_filter, "-ar", "48000", str(out_wav)],
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
        # Clean digital silence (zero hiss)
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
# Deterministic Word Alignment
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
    if caption_text is not None and not narration_text:
        narration_text = caption_text
    canon_tokens = narration_text.split()
    if not canon_tokens:
        raise AudioBuildError("Cannot align empty narration_text.")

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

    # If no usable whisper tokens, distribute deterministically across duration
    if not cleaned_whisper:
        dist = _distribute_span(canon_tokens, 0.0, scene_duration)
        words_out = [
            {
                "word": tok,
                "start": round(st, 4),
                "end": round(en, 4),
                "global_start": round(global_offset + st, 4),
                "global_end": round(global_offset + en, 4),
            }
            for tok, st, en in dist
        ]
        return words_out, 1.0

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

    idx = 0
    n = len(canon_tokens)
    while idx < n:
        if aligned_raw[idx] is not None:
            idx += 1
            continue
        gap_start_idx = idx
        while idx < n and aligned_raw[idx] is None:
            idx += 1
        gap_end_idx = idx

        left_time = aligned_raw[gap_start_idx - 1][2] if gap_start_idx > 0 and aligned_raw[gap_start_idx - 1] else 0.0
        right_time = aligned_raw[gap_end_idx][1] if gap_end_idx < n and aligned_raw[gap_end_idx] else scene_duration
        if right_time <= left_time:
            right_time = min(scene_duration, left_time + 0.08 * (gap_end_idx - gap_start_idx))
        dist = _distribute_span(canon_tokens[gap_start_idx:gap_end_idx], left_time, right_time)
        for c_idx, item in zip(range(gap_start_idx, gap_end_idx), dist):
            aligned_raw[c_idx] = item

    words_out = []
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


align_caption_words = align_narration_words


def transcribe_scene_words(
    whisper_model: Any,
    wav_path: Path,
    narration_text: str,
    language: str,
) -> list[dict[str, Any]]:
    if not hasattr(whisper_model, "transcribe"):
        return []
    try:
        segments, _ = whisper_model.transcribe(
            str(wav_path),
            language=language,
            word_timestamps=True,
            beam_size=5,
            vad_filter=False,
            condition_on_previous_text=False,
            initial_prompt=narration_text,
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
    except Exception as exc:
        print(f"[WARN] faster-whisper transcription skipped: {exc}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Read-Only Database Continuity Check
# ---------------------------------------------------------------------------

def verify_active_series_continuity_readonly(
    db_path: Path,
    ep_plan: EpisodePlan,
) -> None:
    if getattr(ep_plan, "content_format", "serial") == "standalone" or ep_plan.series_id is None:
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
    align_cfg = cfg.get("alignment", {})
    return WhisperModel(
        align_cfg.get("model_size", "base"),
        device=align_cfg.get("device", "cpu"),
        compute_type=align_cfg.get("compute_type", "int8"),
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

    active_lang = getattr(ep_plan, "language", cfg["channel"].get("primary_language", "en"))
    lang_prof = cfg.get("languages", {}).get(active_lang, {})

    text_reps, ipa_rules = load_pronunciations(root, cfg, lang=active_lang)
    model_path, voices_path = ensure_kokoro_models(root, cfg)

    kokoro = kokoro_factory(model_path, voices_path)
    whisper_model = whisper_factory(cfg)

    # Resolve default narrator and dialogue voices
    available_voices = set(kokoro.get_voices())
    if ep_plan.tts_voice and all(v.split(":")[0] in available_voices for v in str(ep_plan.tts_voice).split("+")):
        narrator_voice_spec = ep_plan.tts_voice
    elif "narrator_voice" in lang_prof:
        narrator_voice_spec = lang_prof["narrator_voice"]
    else:
        narrator_voice_spec = ep_plan.tts_voice or "am_fenrir"

    dialogue_voice_spec = lang_prof.get("character_dialogue_voice", "am_onyx" if active_lang == "en" else "hm_omega")
    if not all(v.split(":")[0] in available_voices for v in str(dialogue_voice_spec).split("+")):
        dialogue_voice_spec = narrator_voice_spec

    resolved_narrator_voice = resolve_kokoro_voice(kokoro, narrator_voice_spec)
    resolved_dialogue_voice = resolve_kokoro_voice(kokoro, dialogue_voice_spec)

    tts_lang = lang_prof.get("kokoro_lang", "en-us" if active_lang == "en" else "hi")
    default_narr_speed = float(lang_prof.get("narrator_speed", cfg["tts"].get("speed", 0.92)))
    default_diag_speed = float(lang_prof.get("character_dialogue_speed", 0.88 if active_lang == "en" else 0.90))

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
    expected_sr: Optional[int] = None
    cursor_sec = 0.0
    total_scenes = len(ep_plan.scenes)

    narrator_f0: Optional[float] = None
    narrator_centroid: Optional[float] = None

    for idx, scene in enumerate(ep_plan.scenes):
        # Apply text pronunciation substitutions
        tts_text = apply_pronunciations(scene.narration_text, text_reps)

        # Speaker role & voice selection
        is_dialogue = getattr(scene, "speaker_role", "narrator") == "character_dialogue"
        if getattr(scene, "speed", None) is not None:
            speed = float(scene.speed)
        else:
            base_speed = default_diag_speed if is_dialogue else default_narr_speed
            # Dynamic emotion- and dramatic-role aware pacing adjustment
            emotion = getattr(scene, "emotion", "calm")
            shot_type = getattr(scene, "shot_type", None) or ""
            is_climax_scene = (
                getattr(ep_plan, "story_arc", None) is not None
                and ep_plan.story_arc.climax_scene_index == scene.scene_index
            )

            multiplier = 1.0
            if emotion in ("wrath", "shock") or shot_type in ("dramatic_climax", "confrontation", "climax") or is_climax_scene:
                multiplier = 1.04
            elif emotion in ("calm", "meditating") or shot_type in ("curtain_establishing", "philosophical_outro"):
                multiplier = 0.96
            elif emotion == "smirk":
                multiplier = 1.01

            speed = round(min(1.15, max(0.80, base_speed * multiplier)), 3)

        if is_dialogue:
            voice_spec = getattr(scene, "voice_override", None) or dialogue_voice_spec
            current_voice = resolve_kokoro_voice(kokoro, voice_spec)
        else:
            current_voice = resolved_narrator_voice

        # Check for phonemization with native IPA substitutions if Kokoro exposes tokenizer
        ph_text = tts_text
        use_phonemes = False
        if hasattr(kokoro, "tokenizer") and hasattr(kokoro.tokenizer, "phonemize") and ipa_rules:
            try:
                raw_ph = kokoro.tokenizer.phonemize(tts_text, lang=tts_lang)
                injected_ph = raw_ph
                for pat, rep in ipa_rules:
                    injected_ph = re.sub(pat, rep, injected_ph)
                ph_text = injected_ph
                use_phonemes = True
            except Exception:
                ph_text = tts_text
                use_phonemes = False

        try:
            if use_phonemes:
                samples, sr = kokoro.create(
                    ph_text,
                    voice=current_voice,
                    speed=speed,
                    lang=tts_lang,
                    is_phonemes=True,
                )
            else:
                samples, sr = kokoro.create(
                    tts_text,
                    voice=current_voice,
                    speed=speed,
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

        # Pause duration calculation
        if idx == total_scenes - 1:
            pad_sec = FINAL_SCENE_PAD_SEC
        else:
            custom_ms = getattr(scene, "pause_after_ms", None)
            if custom_ms and custom_ms > 0:
                pad_sec = custom_ms / 1000.0
            else:
                # Dynamic narrative-aware pause calculation
                is_climax = (
                    getattr(ep_plan, "story_arc", None) is not None
                    and ep_plan.story_arc.climax_scene_index == scene.scene_index
                )
                shot_type = getattr(scene, "shot_type", None) or ""
                next_is_dialogue = (
                    idx + 1 < total_scenes
                    and getattr(ep_plan.scenes[idx + 1], "speaker_role", "narrator") == "character_dialogue"
                )

                if is_climax or shot_type in ("dramatic_climax", "revelation"):
                    pad_sec = 0.40  # 400ms pause after dramatic climax/revelation for emotional resonance
                elif next_is_dialogue or is_dialogue:
                    pad_sec = 0.18  # 180ms crisp conversational pause
                else:
                    pad_sec = INTER_SCENE_PAD_SEC  # default 0.20s (200ms)

        pre_dsp_samples = trim_and_pad_audio(samples, expected_sr, pad_tail_sec=0.0)

        # Measure pre-DSP metrics for validation
        pre_dur = float(len(pre_dsp_samples)) / float(expected_sr)
        pre_f0 = measure_f0(pre_dsp_samples, expected_sr)
        pre_centroid = measure_spectral_centroid(pre_dsp_samples, expected_sr)

        if not is_dialogue and narrator_f0 is None:
            narrator_f0 = pre_f0
            narrator_centroid = pre_centroid

        scene_wav = audio_dir / f"scene_{scene.scene_index}.wav"

        # Apply Character Dialogue DSP if dialogue beat
        if is_dialogue:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf_raw:
                raw_path = Path(tf_raw.name)
            tf_raw.close()
            write_wav_atomic(raw_path, pre_dsp_samples, expected_sr)

            try:
                apply_dialogue_dsp(raw_path, scene_wav, pitch_ratio=0.917)
                post_aud, post_sr = sf.read(str(scene_wav))
                if post_aud.ndim > 1:
                    post_aud = post_aud[:, 0]
                post_dur = float(len(post_aud)) / float(post_sr)
                post_f0 = measure_f0(post_aud, post_sr)
                post_centroid = measure_spectral_centroid(post_aud, post_sr)

                # Automated guardrails
                dur_diff = abs(post_dur - pre_dur) / max(1e-6, pre_dur)
                if dur_diff > 0.05:
                    raise AudioBuildError(
                        f"Scene {scene.scene_index} Ravana dialogue duration shifted by {dur_diff*100:.2f}% (exceeds 5% limit)"
                    )
                if post_centroid >= pre_centroid:
                    print(
                        f"[WARN] Scene {scene.scene_index} dialogue spectral centroid ({post_centroid:.1f}Hz) >= pre-DSP ({pre_centroid:.1f}Hz)",
                        file=sys.stderr,
                    )
                if narrator_f0 and post_f0 > narrator_f0:
                    print(
                        f"[WARN] Scene {scene.scene_index} dialogue F0 ({post_f0:.1f}Hz) > narrator ({narrator_f0:.1f}Hz)",
                        file=sys.stderr,
                    )

                # Append tail padding
                tail_samples = int(round(pad_sec * post_sr))
                if tail_samples > 0:
                    post_aud = np.concatenate([post_aud, np.zeros(tail_samples, dtype=np.float32)])
                write_wav_atomic(scene_wav, post_aud, post_sr)
                processed = post_aud
                expected_sr = post_sr
            finally:
                if raw_path.exists():
                    try:
                        raw_path.unlink()
                    except OSError:
                        pass
        else:
            # Standard narrator scene
            processed = trim_and_pad_audio(samples, expected_sr, pad_tail_sec=pad_sec)
            write_wav_atomic(scene_wav, processed, expected_sr)

        scene_dur = probe_duration_sec(scene_wav)

        whisper_words = transcribe_scene_words(
            whisper_model=whisper_model,
            wav_path=scene_wav,
            narration_text=scene.narration_text,
            language="en" if active_lang == "en" else "hi",
        )
        aligned_words, match_ratio = align_narration_words(
            narration_text=scene.narration_text,
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

    active_format = getattr(ep_plan, "content_format", None) or cfg.get("content_format", "serial")
    format_pacing = cfg.get("format_pacing", {}).get(active_format, {})
    default_pacing = cfg.get("episode_pacing", {})

    hard_min = float(format_pacing.get("hard_duration_min_sec", default_pacing.get("hard_duration_min_sec", 30.0)))
    hard_max = float(format_pacing.get("hard_duration_max_sec", default_pacing.get("hard_duration_max_sec", 180.0)))
    target_min = float(format_pacing.get("target_duration_min_sec", default_pacing.get("target_duration_min_sec", 40.0)))
    target_max = float(format_pacing.get("target_duration_max_sec", default_pacing.get("target_duration_max_sec", 120.0)))

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

    # Master full narration with two-pass EBU R128 loudness normalization
    norm_wav = audio_dir / "narration_norm.wav"
    try:
        two_pass_loudnorm(full_wav, norm_wav, target_lufs=-14.0, target_tp=-1.5)
        if norm_wav.is_file() and norm_wav.stat().st_size > 0:
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
        raise AudioBuildError(f"Hiss detected in trailing silence: {trailing_rms:.1f} dBFS (must be < -65 dBFS)")

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
        "story_arc": ep_plan.story_arc.model_dump() if getattr(ep_plan, "story_arc", None) else None,
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
