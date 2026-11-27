"""FFmpeg 16 kHz PCM resampling, local faster-whisper alignment, and RMS burst snapping."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import numpy as np
import soundfile as sf

from sutradhar.audio.elevenlabs_tts import DEFAULT_SAMPLE_RATE, strip_audio_tags

DEFAULT_WHISPER_MODEL = "small"
FALLBACK_WHISPER_MODEL = "base"
WHISPER_SAMPLE_RATE = 16000

SILENCE_THRESHOLD = 0.003
TRIM_MARGIN_SEC = 0.10
INTER_SCENE_PAD_SEC = 0.20
FINAL_SCENE_PAD_SEC = 0.85
DURATION_TOLERANCE_SEC = 0.15
MIN_PEAK_AMPLITUDE = 1e-4

WORD_NORM_RE = re.compile(r"[^a-z0-9'\u0900-\u097F\u0600-\u06FF]+", re.IGNORECASE)
MAX_SINGLE_WORD_SPAN_SEC = 1.50


class AudioBuildError(RuntimeError):
    """Raised when audio validation, DSP, or Whisper word alignment fails."""


# ---------------------------------------------------------------------------
# System Executables, Probing & Atomic Audio DSP Helpers
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


def measure_trailing_rms(wav_path: str | Path, tail_sec: float = 0.50) -> float:
    data, fs = sf.read(str(wav_path))
    if data.ndim > 1:
        data = data[:, 0]
    n_tail = int(tail_sec * fs)
    tail = data[-n_tail:] if len(data) >= n_tail else data
    rms = np.sqrt(np.mean(tail ** 2) + 1e-15)
    return float(20 * np.log10(rms))


def two_pass_loudnorm(
    in_wav: Path,
    out_wav: Path,
    target_lufs: float = -14.0,
    target_tp: float = -1.5,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    """Run two-pass EBU R128 loudness normalization with linear gain."""
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

    stats = json.loads(stderr[idx_start : idx_end + 1])
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
# HuggingFace Local Whisper Cache & 16 kHz Resampling
# ---------------------------------------------------------------------------

def is_whisper_model_cached(model_size: str, cache_dir: Optional[Path] = None) -> bool:
    """Verify `models--Systran--faster-whisper-<size>` has a complete local `model.bin`."""
    hub_root = cache_dir or (Path.home() / ".cache" / "huggingface" / "hub")
    model_dir = hub_root / f"models--Systran--faster-whisper-{model_size}" / "snapshots"
    if not model_dir.is_dir():
        return False
    for snap in model_dir.iterdir():
        model_bin = snap / "model.bin"
        if model_bin.is_file() and model_bin.stat().st_size > 10_000_000:
            return True
    return False


def resolve_local_whisper_model(
    preferred: str = DEFAULT_WHISPER_MODEL,
    fallback: str = FALLBACK_WHISPER_MODEL,
) -> str:
    """Return `preferred` when complete in local HF cache; otherwise fall back cleanly."""
    if is_whisper_model_cached(preferred):
        return preferred
    if fallback and fallback != preferred and is_whisper_model_cached(fallback):
        print(
            f"[WARN] faster-whisper '{preferred}' model.bin is missing or incomplete in local HF cache; "
            f"using locally cached '{fallback}'.",
            file=sys.stderr,
        )
        return fallback
    return preferred


class LazyWhisperProxy:
    """Lazy loader for local faster-whisper without PyAV monkeypatching."""

    def __init__(self, cfg: Optional[dict[str, Any]] = None) -> None:
        self.cfg = cfg or {}
        self._instance: Any = None
        self.loaded_model_size: Optional[str] = None

    def _ensure_loaded(self) -> Any:
        if self._instance is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise AudioBuildError(f"faster-whisper is not installed: {exc}") from exc
            align_cfg = self.cfg.get("alignment", {})
            preferred = str(align_cfg.get("model_size", DEFAULT_WHISPER_MODEL))
            local_only = bool(align_cfg.get("local_files_only", True))
            selected = resolve_local_whisper_model(preferred, FALLBACK_WHISPER_MODEL) if local_only else preferred
            self.loaded_model_size = selected
            self._instance = WhisperModel(
                selected,
                device=align_cfg.get("device", "cpu"),
                compute_type=align_cfg.get("compute_type", "int8"),
                local_files_only=local_only,
            )
        return self._instance

    def transcribe(self, *args: Any, **kwargs: Any) -> Any:
        model = self._ensure_loaded()
        return model.transcribe(*args, **kwargs)


_LazyWhisperProxy = LazyWhisperProxy


def default_whisper_factory(cfg: Optional[dict[str, Any]] = None) -> LazyWhisperProxy:
    return LazyWhisperProxy(cfg or {})


def resample_to_16k_mono(src_wav: Path, dst_wav: Path) -> Path:
    """Resample any WAV/audio asset via ffmpeg to clean 16,000 Hz mono PCM_S16LE."""
    require_executable("ffmpeg")
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src_wav),
            "-ac",
            "1",
            "-ar",
            str(WHISPER_SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(dst_wav),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not dst_wav.is_file():
        raise AudioBuildError(
            f"ffmpeg 16 kHz resample failed for '{src_wav}': {proc.stderr.strip()}"
        )
    return dst_wav


def load_16k_mono_array(wav_path: Path) -> np.ndarray:
    """Load 16 kHz mono float32 waveform via ffmpeg + soundfile (bypasses PyAV completely)."""
    try:
        info = sf.info(str(wav_path))
        if info.samplerate == WHISPER_SAMPLE_RATE and info.channels == 1 and info.subtype == "PCM_16":
            data, _ = sf.read(str(wav_path), dtype="float32")
            return np.ascontiguousarray(data, dtype=np.float32)
    except Exception:
        pass

    with tempfile.TemporaryDirectory(prefix="sutradhar_16k_") as td:
        tmp_16k = Path(td) / "audio_16k.wav"
        resample_to_16k_mono(wav_path, tmp_16k)
        data, _ = sf.read(str(tmp_16k), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1, dtype=np.float32)
        return np.ascontiguousarray(data, dtype=np.float32)


# ---------------------------------------------------------------------------
# Devanagari & Cross-Script Indic Phonetic Normalization
# ---------------------------------------------------------------------------

def norm_indic_token(token: str) -> str:
    """Normalize Devanagari equivalence (`ं/ङ्/ञ्/ण्/न्/म्`, chandrabindu, nukta) and strip punctuation."""
    s = WORD_NORM_RE.sub("", token.lower())
    s = s.replace("\u0901", "\u0902")  # chandrabindu -> anusvara
    s = s.replace("\u093c", "")        # strip nukta
    for nasal in ("ङ्", "ञ्", "ण्", "न्", "म्"):
        s = s.replace(nasal, "ं")
    return s


_DEVA_CONSONANT_SKELETON = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "f", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
    "ं": "n", "ः": "h", "ँ": "n",
}

_URDU_CONSONANT_SKELETON = {
    "ب": "b", "پ": "p", "ت": "t", "ٹ": "t", "ث": "s",
    "ج": "j", "چ": "ch", "ح": "h", "خ": "kh",
    "د": "d", "ڈ": "d", "ذ": "z", "ر": "r", "ڑ": "r",
    "ز": "z", "ژ": "z", "س": "s", "ش": "sh", "ص": "s",
    "ض": "z", "ط": "t", "ظ": "z", "ع": "", "غ": "gh",
    "ف": "f", "ق": "k", "ک": "k", "گ": "g", "ل": "l",
    "م": "m", "ن": "n", "ں": "n", "و": "v", "ہ": "h",
    "ھ": "h", "ی": "y", "ے": "y", "ئ": "y", "ء": "",
}


def indic_phonetic_skeleton(token: str) -> str:
    """Map Devanagari, Perso-Arabic (Urdu), and Latin tokens into a shared phonetic skeleton."""
    norm = norm_indic_token(token)
    if not norm:
        return ""
    if re.fullmatch(r"[a-z0-9']+", norm):
        return norm

    out: list[str] = []
    for ch in norm:
        if ch in _DEVA_CONSONANT_SKELETON:
            out.append(_DEVA_CONSONANT_SKELETON[ch])
        elif ch in _URDU_CONSONANT_SKELETON:
            out.append(_URDU_CONSONANT_SKELETON[ch])
        elif "a" <= ch <= "z" or "0" <= ch <= "9":
            out.append(ch)
    skel = "".join(out)
    # Collapse aspiration / voiced-labial ambiguities (`bh/b`, `sh/s`, `v/b`, `chh/ch`) gently
    skel = skel.replace("sh", "s").replace("v", "b").replace("ph", "f")
    return skel


def _tokens_match(canon_tok: str, whisper_tok: str) -> tuple[bool, float]:
    c_norm = norm_indic_token(canon_tok)
    w_norm = norm_indic_token(whisper_tok)
    if not c_norm or not w_norm:
        return False, 0.0
    if c_norm == w_norm:
        return True, 1.0
    ratio = difflib.SequenceMatcher(None, c_norm, w_norm).ratio()
    if ratio >= 0.62:
        return True, ratio

    c_skel = indic_phonetic_skeleton(canon_tok)
    w_skel = indic_phonetic_skeleton(whisper_tok)
    if c_skel and w_skel:
        if c_skel == w_skel:
            return True, 0.95
        s_ratio = difflib.SequenceMatcher(None, c_skel, w_skel).ratio()
        if s_ratio >= 0.65:
            return True, s_ratio
    return False, max(ratio, 0.0)


# ---------------------------------------------------------------------------
# RMS Speech-Envelope Detection & Clause Burst Mapping
# ---------------------------------------------------------------------------

def detect_speech_bursts(
    wav_path: Path,
    frame_ms: float = 20.0,
    thresh_ratio: float = 0.08,
) -> list[tuple[float, float]]:
    """Detect active speech intervals `(start_sec, end_sec)` via short-time RMS energy."""
    data, sr = sf.read(str(wav_path), dtype="float32")
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    hop = max(1, int(sr * (frame_ms / 1000.0)))
    n_frames = len(data) // hop
    if n_frames <= 0:
        return []
    frames = data[: n_frames * hop].reshape(n_frames, hop)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    peak_rms = float(np.percentile(rms, 95))
    thresh = max(0.004, peak_rms * thresh_ratio)
    active = rms >= thresh

    intervals: list[tuple[float, float]] = []
    in_seg = False
    s_idx = 0
    for i, flag in enumerate(active):
        if flag and not in_seg:
            in_seg = True
            s_idx = i
        elif not flag and in_seg:
            in_seg = False
            intervals.append((s_idx * hop / sr, i * hop / sr))
    if in_seg:
        intervals.append((s_idx * hop / sr, n_frames * hop / sr))

    merged: list[tuple[float, float]] = []
    for s, e in intervals:
        if merged and s - merged[-1][1] < 0.14:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return [seg for seg in merged if seg[1] - seg[0] >= 0.08]


def _distribute_span(
    tokens: list[str],
    span_start: float,
    span_end: float,
) -> list[tuple[str, float, float]]:
    if not tokens:
        return []
    safe_start = max(0.0, span_start)
    safe_end = max(safe_start + 0.02 * len(tokens), span_end)
    weights = [max(1, len(norm_indic_token(t)) or len(t)) for t in tokens]
    total_w = float(sum(weights))
    cursor = safe_start
    total_dur = safe_end - safe_start
    result: list[tuple[str, float, float]] = []
    for idx, (tok, w) in enumerate(zip(tokens, weights)):
        nxt = safe_end if idx == len(tokens) - 1 else cursor + total_dur * (w / total_w)
        result.append((tok, cursor, max(cursor + 0.01, nxt)))
        cursor = nxt
    return result


def _distribute_across_intervals(
    tokens: list[str],
    intervals: list[tuple[float, float]],
    fallback_start: float,
    fallback_end: float,
) -> list[tuple[float, float]]:
    if not tokens:
        return []
    weights = [max(1, len(norm_indic_token(t)) or len(t)) for t in tokens]
    clipped: list[tuple[float, float]] = []
    for s, e in intervals:
        cs = max(fallback_start, s)
        ce = min(fallback_end, e)
        if ce - cs >= 0.05:
            clipped.append((cs, ce))
    if not clipped:
        return [(s, e) for _, s, e in _distribute_span(tokens, fallback_start, fallback_end)]

    total_speech = sum(e - s for s, e in clipped)
    total_w = float(sum(weights))
    cum_w = 0.0
    spans: list[tuple[float, float]] = []

    def map_u(u: float) -> float:
        target = max(0.0, min(1.0, u)) * total_speech
        acc = 0.0
        for s, e in clipped:
            dur = e - s
            if acc + dur >= target - 1e-9:
                return s + (target - acc)
            acc += dur
        return clipped[-1][1]

    for w in weights:
        t0 = map_u(cum_w / total_w)
        cum_w += w
        t1 = map_u(cum_w / total_w)
        spans.append((t0, max(t0 + 0.03, t1)))
    return spans


def _split_clauses(tokens: list[str]) -> list[list[str]]:
    """Split canonical tokens into spoken clauses on sentence/comma boundaries."""
    clauses: list[list[str]] = []
    cur: list[str] = []
    for tok in tokens:
        cur.append(tok)
        if tok.endswith(("।", "!", "?")):
            clauses.append(cur)
            cur = []
    if cur:
        clauses.append(cur)

    # If a single sentence has >= 12 tokens and contains a comma clause split, refine on comma
    if len(clauses) == 1 and len(tokens) >= 12:
        comma_clauses: list[list[str]] = []
        cur = []
        for tok in tokens:
            cur.append(tok)
            if tok.endswith((",", "—")) and len(cur) >= 4:
                comma_clauses.append(cur)
                cur = []
        if cur:
            if len(cur) < 3 and comma_clauses:
                comma_clauses[-1].extend(cur)
            else:
                comma_clauses.append(cur)
        if len(comma_clauses) > 1:
            return comma_clauses
    return clauses


def _split_bursts_into_clauses(
    bursts: list[tuple[float, float]],
    n_clauses: int,
    scene_dur: float,
) -> list[list[tuple[float, float]]]:
    if not bursts:
        step = max(0.3, (scene_dur - 0.2) / max(1, n_clauses))
        return [[(i * step, (i + 1) * step)] for i in range(n_clauses)]
    if n_clauses <= 1 or len(bursts) <= 1:
        return [bursts]

    gaps = [(bursts[i + 1][0] - bursts[i][1], i) for i in range(len(bursts) - 1)]
    top_cuts = sorted(
        idx for _, idx in sorted(gaps, key=lambda x: x[0], reverse=True)[: n_clauses - 1]
    )
    groups: list[list[tuple[float, float]]] = []
    prev = 0
    for cut in top_cuts:
        groups.append(bursts[prev : cut + 1])
        prev = cut + 1
    groups.append(bursts[prev:])
    while len(groups) < n_clauses:
        groups.append([groups[-1][-1]])
    return groups


# ---------------------------------------------------------------------------
# Whisper Transcription & Adaptive Alignment
# ---------------------------------------------------------------------------

def _is_real_whisper(whisper_model: Any) -> bool:
    if isinstance(whisper_model, LazyWhisperProxy):
        return True
    mod = type(whisper_model).__module__
    return mod.startswith("faster_whisper")


def _extract_segment_words(segments: Any) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for seg in segments:
        for w in getattr(seg, "words", None) or []:
            words.append(
                {
                    "word": getattr(w, "word", ""),
                    "start": float(getattr(w, "start", 0.0)),
                    "end": float(getattr(w, "end", 0.0)),
                }
            )
    return words


def _words_cache_path(wav_path: Path, clean_prompt: str, language: str) -> Optional[Path]:
    if not wav_path.is_file():
        return None
    cache_dir = wav_path.parent.parent / "cache" / "audio"
    content_hash = hashlib.md5(
        wav_path.read_bytes() + clean_prompt.encode("utf-8") + language.encode("utf-8")
    ).hexdigest()
    return cache_dir / f"{content_hash}.words.json"


def transcribe_scene_words(
    whisper_model: Any,
    wav_path: Path,
    narration_text: str,
    language: str = "hi",
    *,
    use_cache: bool = True,
    vad_filter: bool = True,
) -> list[dict[str, Any]]:
    """Transcribe a scene WAV using 16 kHz mono PCM arrays (zero PyAV metadata errors)."""
    if not hasattr(whisper_model, "transcribe"):
        return []
    clean_prompt = strip_audio_tags(narration_text)

    cache_file: Optional[Path] = None
    if use_cache:
        try:
            cache_file = _words_cache_path(wav_path, clean_prompt, language)
            if cache_file is not None and cache_file.is_file() and cache_file.stat().st_size > 0:
                return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    try:
        audio_input: Any = (
            load_16k_mono_array(wav_path)
            if (_is_real_whisper(whisper_model) and wav_path.is_file())
            else str(wav_path)
        )
        segments, _ = whisper_model.transcribe(
            audio_input,
            language=language,
            word_timestamps=True,
            beam_size=5,
            vad_filter=vad_filter,
            condition_on_previous_text=False,
            initial_prompt=clean_prompt,
        )
        words = _extract_segment_words(segments)
        if use_cache and cache_file is not None and words:
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                write_text_atomic(cache_file, json.dumps(words, ensure_ascii=False))
            except Exception:
                pass
        return words
    except Exception as exc:
        print(f"[WARN] faster-whisper transcription skipped: {exc}", file=sys.stderr)
        return []


def transcribe_scene_adaptive(
    whisper_model: Any,
    wav_path: Path,
    narration_text: str,
    language: str = "hi",
    *,
    scene_duration: Optional[float] = None,
    use_cache: bool = True,
) -> tuple[list[dict[str, Any]], float]:
    """Transcribe with primary prompt, retrying prompt-free or clause-sliced if match < 0.70."""
    clean_text = strip_audio_tags(narration_text)
    dur = scene_duration or (probe_duration_sec(wav_path) if wav_path.is_file() else 0.0)
    cache_file = _words_cache_path(wav_path, clean_text, language) if use_cache else None
    was_cached = bool(cache_file is not None and cache_file.is_file() and cache_file.stat().st_size > 0)

    words = transcribe_scene_words(
        whisper_model=whisper_model,
        wav_path=wav_path,
        narration_text=clean_text,
        language=language,
        use_cache=use_cache,
        vad_filter=True,
    )
    if not words or was_cached or not _is_real_whisper(whisper_model) or not wav_path.is_file():
        if not words:
            return words, 0.0
        _, ratio = align_narration_words(
            narration_text=clean_text,
            whisper_words=words,
            scene_duration=dur,
            wav_path=wav_path if wav_path.is_file() else None,
        )
        return words, ratio

    _, best_ratio = align_narration_words(
        narration_text=clean_text,
        whisper_words=words,
        scene_duration=dur,
        wav_path=wav_path,
    )
    if best_ratio >= 0.70:
        return words, best_ratio

    arr_16k = load_16k_mono_array(wav_path)
    best_words = words

    # Recovery A: Prompt-free decode (prevents prompt-induced repetition loops)
    try:
        segs_np, _ = whisper_model.transcribe(
            arr_16k,
            language=language,
            word_timestamps=True,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=None,
        )
        w_np = _extract_segment_words(segs_np)
        if w_np:
            _, r_np = align_narration_words(
                narration_text=clean_text,
                whisper_words=w_np,
                scene_duration=dur,
                wav_path=wav_path,
            )
            if r_np > best_ratio:
                best_ratio, best_words = r_np, w_np
    except Exception:
        pass

    # Recovery B: Clause-by-clause RMS burst decode when clauses remain weak (< 0.70)
    if best_ratio < 0.70:
        clauses = _split_clauses(clean_text.split())
        bursts = detect_speech_bursts(wav_path)
        if len(clauses) > 1 and len(bursts) >= len(clauses):
            clause_bursts = _split_bursts_into_clauses(bursts, len(clauses), dur)
            merged_clause_words: list[dict[str, Any]] = []
            for c_toks, c_b in zip(clauses, clause_bursts):
                s_pad = max(0.0, c_b[0][0] - 0.05)
                e_pad = min(dur, c_b[-1][1] + 0.08)
                i0 = int(round(s_pad * WHISPER_SAMPLE_RATE))
                i1 = int(round(e_pad * WHISPER_SAMPLE_RATE))
                if i1 - i0 < WHISPER_SAMPLE_RATE // 4:
                    continue
                try:
                    segs_c, _ = whisper_model.transcribe(
                        arr_16k[i0:i1],
                        language=language,
                        word_timestamps=True,
                        beam_size=5,
                        vad_filter=False,
                        condition_on_previous_text=False,
                        initial_prompt=" ".join(c_toks),
                    )
                    for item in _extract_segment_words(segs_c):
                        merged_clause_words.append(
                            {
                                "word": item["word"],
                                "start": item["start"] + s_pad,
                                "end": item["end"] + s_pad,
                            }
                        )
                except Exception:
                    continue
            if merged_clause_words:
                _, r_cl = align_narration_words(
                    narration_text=clean_text,
                    whisper_words=merged_clause_words,
                    scene_duration=dur,
                    wav_path=wav_path,
                )
                if r_cl > best_ratio:
                    best_ratio, best_words = r_cl, merged_clause_words

    return best_words, best_ratio


def _match_whisper_anchors(
    canon_tokens: list[str],
    cleaned_whisper: list[tuple[str, float, float]],
) -> tuple[list[Optional[tuple[float, float]]], float]:
    """Match canonical tokens against Whisper words via Devanagari + cross-script skeleton + splits."""
    canon_skels = [indic_phonetic_skeleton(t) or norm_indic_token(t) for t in canon_tokens]
    w_skels = [indic_phonetic_skeleton(w[0]) or norm_indic_token(w[0]) for w in cleaned_whisper]

    sm = difflib.SequenceMatcher(None, canon_skels, w_skels)
    word_spans: list[Optional[tuple[float, float]]] = [None] * len(canon_tokens)
    matched = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                if canon_skels[i1 + k]:
                    _, ws, we = cleaned_whisper[j1 + k]
                    word_spans[i1 + k] = (ws, max(ws + 0.03, we))
                    matched += 1
        elif tag == "replace":
            c_len = i2 - i1
            w_len = j2 - j1
            if c_len == w_len:
                for k in range(c_len):
                    ok, _ = _tokens_match(canon_tokens[i1 + k], cleaned_whisper[j1 + k][0])
                    if ok:
                        _, ws, we = cleaned_whisper[j1 + k]
                        word_spans[i1 + k] = (ws, max(ws + 0.03, we))
                        matched += 1
            else:
                # Try 2-canon-to-1-whisper and 1-canon-to-2-whisper splits inside replacement blocks
                ci, wi = i1, j1
                while ci < i2 and wi < j2:
                    ok_1, _ = _tokens_match(canon_tokens[ci], cleaned_whisper[wi][0])
                    if ok_1:
                        _, ws, we = cleaned_whisper[wi]
                        word_spans[ci] = (ws, max(ws + 0.03, we))
                        matched += 1
                        ci += 1
                        wi += 1
                        continue
                    if ci + 1 < i2:
                        merged_c = canon_tokens[ci] + canon_tokens[ci + 1]
                        ok_21, _ = _tokens_match(merged_c, cleaned_whisper[wi][0])
                        if ok_21:
                            _, ws, we = cleaned_whisper[wi]
                            parts = _distribute_span([canon_tokens[ci], canon_tokens[ci + 1]], ws, max(ws + 0.06, we))
                            word_spans[ci] = (parts[0][1], parts[0][2])
                            word_spans[ci + 1] = (parts[1][1], parts[1][2])
                            matched += 2
                            ci += 2
                            wi += 1
                            continue
                    if wi + 1 < j2:
                        merged_w = cleaned_whisper[wi][0] + cleaned_whisper[wi + 1][0]
                        ok_12, _ = _tokens_match(canon_tokens[ci], merged_w)
                        if ok_12:
                            ws = cleaned_whisper[wi][1]
                            we = max(ws + 0.04, cleaned_whisper[wi + 1][2])
                            word_spans[ci] = (ws, we)
                            matched += 1
                            ci += 1
                            wi += 2
                            continue
                    ci += 1
                    wi += 1

    ratio = round(float(matched) / max(1, len(canon_tokens)), 4)
    return word_spans, ratio


def _apply_rms_burst_snapping(
    canon_tokens: list[str],
    word_spans: list[Optional[tuple[float, float]]],
    wav_path: Path,
    scene_duration: float,
) -> list[Optional[tuple[float, float]]]:
    """Constrain clause spans & large unanchored gaps to active RMS speech bursts."""
    bursts = detect_speech_bursts(wav_path)
    if not bursts:
        return word_spans

    clauses = _split_clauses(canon_tokens)
    clause_bursts = _split_bursts_into_clauses(bursts, len(clauses), scene_duration)
    tok_offset = 0

    for c_idx, c_tokens in enumerate(clauses):
        c_end_idx = tok_offset + len(c_tokens)
        c_b = clause_bursts[c_idx]
        c_lo = c_b[0][0]
        c_hi = c_b[-1][1]

        c_matched = sum(1 for k in range(tok_offset, c_end_idx) if word_spans[k] is not None)
        if c_matched < max(1, len(c_tokens) * 0.5):
            fills = _distribute_across_intervals(c_tokens, c_b, c_lo, c_hi)
            for off, sp in enumerate(fills):
                word_spans[tok_offset + off] = sp
        else:
            i = tok_offset
            while i < c_end_idx:
                if word_spans[i] is None:
                    g0 = i
                    while i < c_end_idx and word_spans[i] is None:
                        i += 1
                    g1 = i
                    t0 = max(c_lo, word_spans[g0 - 1][1]) if g0 > tok_offset else c_lo
                    t1 = min(c_hi, word_spans[g1][0]) if g1 < c_end_idx else c_hi
                    t1 = max(t0 + 0.04 * (g1 - g0), t1)
                    fills = _distribute_across_intervals(canon_tokens[g0:g1], c_b, t0, t1)
                    for off, sp in enumerate(fills):
                        word_spans[g0 + off] = sp
                else:
                    s, e = word_spans[i]  # type: ignore[misc]
                    # Prevent a single matched word from stretching abnormally across a silence pause
                    if e - s > MAX_SINGLE_WORD_SPAN_SEC:
                        matched_bursts = [b for b in c_b if b[1] > s and b[0] < e]
                        if matched_bursts:
                            s = max(s, matched_bursts[-1][0])
                            e = min(e, s + 0.90)
                        else:
                            e = s + 0.90
                    word_spans[i] = (max(0.0, s), min(c_hi + 0.12, max(s + 0.04, e)))
                    i += 1
        tok_offset = c_end_idx

    return word_spans


def align_narration_words(
    narration_text: str = "",
    whisper_words: list[dict[str, Any]] | None = None,
    scene_duration: float = 0.0,
    global_offset: float = 0.0,
    caption_text: str | None = None,
    wav_path: Optional[Path] = None,
) -> tuple[list[dict[str, Any]], float]:
    """Align Whisper timestamps onto canonical tag-free narration words with RMS safety."""
    text_source = caption_text if (caption_text is not None and not narration_text) else narration_text
    clean_text = strip_audio_tags(text_source)
    canon_tokens = clean_text.split()
    if not canon_tokens:
        raise AudioBuildError("Cannot align empty narration_text.")

    if not whisper_words:
        raise AudioBuildError("faster-whisper detected zero spoken words in synthesized audio.")

    cleaned_whisper: list[tuple[str, float, float]] = []
    for item in whisper_words:
        w_text = str(item.get("word", "")).strip()
        if norm_indic_token(w_text):
            cleaned_whisper.append(
                (w_text, float(item.get("start", 0.0)), float(item.get("end", 0.0)))
            )

    word_spans, match_ratio = _match_whisper_anchors(canon_tokens, cleaned_whisper)

    has_oversized_span = any(
        sp is not None and (sp[1] - sp[0]) > MAX_SINGLE_WORD_SPAN_SEC for sp in word_spans
    )
    if wav_path is not None and wav_path.is_file() and (match_ratio < 0.75 or has_oversized_span or any(sp is None for sp in word_spans)):
        word_spans = _apply_rms_burst_snapping(canon_tokens, word_spans, wav_path, scene_duration)
    else:
        # Pure timestamp interpolation when no WAV path is passed (e.g. unit test fixtures)
        first_anchor = next(((i, sp[0]) for i, sp in enumerate(word_spans) if sp is not None), None)
        if first_anchor is None:
            distributed = _distribute_span(canon_tokens, 0.05, max(0.2, scene_duration - 0.1))
            return [
                {
                    "word": tok,
                    "start": round(s, 4),
                    "end": round(e, 4),
                    "global_start": round(global_offset + s, 4),
                    "global_end": round(global_offset + e, 4),
                }
                for tok, s, e in distributed
            ], match_ratio

        if first_anchor[0] > 0:
            lead_span = _distribute_span(
                canon_tokens[: first_anchor[0]], 0.02, max(0.04, first_anchor[1])
            )
            for idx, (_, s, e) in enumerate(lead_span):
                word_spans[idx] = (s, e)

        last_anchor = next(
            ((i, word_spans[i][1]) for i in range(len(canon_tokens) - 1, -1, -1) if word_spans[i] is not None),
            None,
        )
        if last_anchor is not None and last_anchor[0] < len(canon_tokens) - 1:
            tail_start = last_anchor[0] + 1
            tail_tokens = canon_tokens[tail_start:]
            tail_end = max(last_anchor[1] + 0.05 * len(tail_tokens), scene_duration - 0.05)
            for idx, (_, s, e) in enumerate(_distribute_span(tail_tokens, last_anchor[1], tail_end)):
                word_spans[tail_start + idx] = (s, e)

        idx = 0
        while idx < len(canon_tokens):
            if word_spans[idx] is None:
                g0 = idx
                while idx < len(canon_tokens) and word_spans[idx] is None:
                    idx += 1
                g1 = idx
                prev_end = word_spans[g0 - 1][1] if g0 > 0 else 0.02
                next_start = word_spans[g1][0] if g1 < len(canon_tokens) else scene_duration - 0.02
                for off, (_, s, e) in enumerate(
                    _distribute_span(canon_tokens[g0:g1], prev_end, max(prev_end + 0.04, next_start))
                ):
                    word_spans[g0 + off] = (s, e)
            else:
                idx += 1

    # Strict monotonicity enforcement
    aligned_words: list[dict[str, Any]] = []
    current_time = 0.0
    max_end = max(0.05, scene_duration - 0.01) if scene_duration > 0 else 1e6
    for tok, sp in zip(canon_tokens, word_spans):
        assert sp is not None
        s, e = sp
        s = max(current_time, min(max_end - 0.02, s))
        e = max(s + 0.01, min(max_end, e))
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
