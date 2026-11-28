"""Multi-act loudness-aware BGM, +33ms peak-aligned Storyboard IR SFX & single 2-pass loudnorm."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

import numpy as np
import soundfile as sf
import yaml

from sutradhar.audio.whisper_aligner import probe_duration_sec, require_executable

BROADCAST_SAMPLE_RATE = 48000
BROADCAST_CHANNELS = 2
DEFAULT_TARGET_LUFS = -14.0
DEFAULT_TRUE_PEAK_DBTP = -1.5
DEFAULT_AAC_TRUE_PEAK_HEADROOM_DB = 0.7  # Leaves headroom so AAC-encoded MP4 stays <= -1.5 dBTP
DEFAULT_LRA = 10.0
DEFAULT_BGM_TARGET_LUFS = -34.0
DEFAULT_CUT_CREST_OFFSET_SEC = 0.033  # +1 frame @ 30fps

_LUFS_CACHE: dict[tuple[str, int], float] = {}
_PEAK_OFFSET_CACHE: dict[tuple[str, int], float] = {}

SWEEP_TRANSITION_STEMS = {
    "whoosh-cinematic",
    "whoosh_soft",
    "curtain_whoosh",
    "riser",
    "tension_swell",
    "impact-bass-2",
}


class AudioMixError(RuntimeError):
    """Raised when multi-track mixing, asset validation, or loudness QA fails."""


def load_audio_catalog(root: Path) -> dict[str, Any]:
    """Load `assets/manifest.yaml` v2 catalog when present."""
    manifest_path = root / "assets" / "manifest.yaml"
    if not manifest_path.is_file():
        return {}
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def measure_integrated_lufs(audio_path: Path) -> float:
    """Measure integrated LUFS via FFmpeg `ebur128` (cached by path + mtime_ns)."""
    require_executable("ffmpeg")
    stat = audio_path.stat()
    cache_key = (str(audio_path.resolve()), stat.st_mtime_ns)
    if cache_key in _LUFS_CACHE:
        return _LUFS_CACHE[cache_key]

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(audio_path),
            "-t",
            "45",
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    matches = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", proc.stderr)
    if not matches:
        raise AudioMixError(f"Failed to parse ebur128 integrated loudness for '{audio_path}': {proc.stderr[-300:]}")
    lufs = float(matches[-1])
    _LUFS_CACHE[cache_key] = lufs
    return lufs


def detect_sfx_peak_offset(sfx_path: Path, window_ms: float = 60.0) -> float:
    """Locate the perceptual RMS peak crest inside an SFX clip (in seconds from file start)."""
    stat = sfx_path.stat()
    cache_key = (str(sfx_path.resolve()), stat.st_mtime_ns)
    if cache_key in _PEAK_OFFSET_CACHE:
        return _PEAK_OFFSET_CACHE[cache_key]

    data, sr = sf.read(str(sfx_path), dtype="float32")
    mono = np.mean(np.abs(data), axis=1) if data.ndim > 1 else np.abs(data)
    if mono.size == 0:
        return 0.0
    win = max(1, int(sr * (window_ms / 1000.0)))
    if mono.size >= win:
        kernel = np.ones(win, dtype=np.float32) / float(win)
        env = np.convolve(mono, kernel, mode="same")
        peak_sec = float(np.argmax(env)) / float(sr)
    else:
        peak_sec = float(np.argmax(mono)) / float(sr)
    peak_sec = round(peak_sec, 4)
    _PEAK_OFFSET_CACHE[cache_key] = peak_sec
    return peak_sec


def resolve_bgm_path(
    root: Path,
    track_or_mood: str,
    cfg: Optional[dict[str, Any]] = None,
    catalog: Optional[dict[str, Any]] = None,
    *,
    allow_synth_fallback: bool = False,
) -> tuple[Optional[Path], bool]:
    """Resolve BGM mood/filename against canonical `assets/audio/bgm/` and `manifest.yaml` v2."""
    cat = catalog if catalog is not None else load_audio_catalog(root)
    audio_cat = cat.get("audio", {}) if isinstance(cat, dict) else {}
    bgm_entries = audio_cat.get("bgm", {}) if isinstance(audio_cat, dict) else {}

    token = str(track_or_mood or "").strip()
    token_lower = token.lower()
    stem = Path(token).stem.lower()

    # 1. Exact stem match in manifest.yaml v2
    if stem in bgm_entries:
        rel_file = bgm_entries[stem].get("file")
        if rel_file and (root / rel_file).is_file():
            return (root / rel_file), False

    # 2. Check mood_tags in manifest.yaml v2
    for _, entry in bgm_entries.items():
        tags = [str(t).lower() for t in (entry.get("mood_tags") or [])]
        if token_lower in tags:
            rel_file = entry.get("file")
            if rel_file and (root / rel_file).is_file():
                return (root / rel_file), False

    # 3. Check config.yaml bgm_by_mood mapping
    mood_map = ((cfg or {}).get("assets") or {}).get("bgm_by_mood") or {}
    bgm_dir = root / "assets" / "audio" / "bgm"
    if token_lower in mood_map:
        mapped_name = mood_map[token_lower]
        cand = bgm_dir / mapped_name
        if cand.is_file():
            return cand, False

    # 4. Direct file search in canonical assets/audio/bgm
    if token:
        cand = bgm_dir / token
        if cand.is_file():
            return cand, False
        if not Path(token).suffix:
            for ext in (".mp3", ".wav"):
                cand_ext = bgm_dir / f"{token}{ext}"
                if cand_ext.is_file():
                    return cand_ext, False

    if allow_synth_fallback:
        return None, True
    raise AudioMixError(
        f"BGM track or mood '{track_or_mood}' not found in assets/audio/bgm/ or manifest.yaml "
        "(allow_synth_fallback=False)."
    )


def resolve_sfx_path(
    root: Path,
    sfx_name: str,
    catalog: Optional[dict[str, Any]] = None,
) -> Optional[Path]:
    """Resolve SFX filename/stem against canonical `assets/audio/sfx/` and `manifest.yaml` v2."""
    if not sfx_name:
        return None
    clean = str(sfx_name).strip()
    cat = catalog if catalog is not None else load_audio_catalog(root)
    sfx_cat = ((cat.get("audio") or {}).get("sfx") or {}) if isinstance(cat, dict) else {}
    stem = Path(clean).stem

    for bucket in ("pixabay", "repo"):
        entries = sfx_cat.get(bucket, {})
        if isinstance(entries, dict) and stem in entries:
            rel_file = entries[stem].get("file")
            if rel_file and (root / rel_file).is_file():
                return root / rel_file

    sfx_dir = root / "assets" / "audio" / "sfx"
    direct = sfx_dir / clean
    if direct.is_file():
        return direct
    for ext in (".mp3", ".wav"):
        alt = sfx_dir / f"{stem}{ext}"
        if alt.is_file():
            return alt
    return None


def parse_bgm_schedule(
    root: Path,
    manifest: dict[str, Any],
    cfg: dict[str, Any],
    *,
    allow_synth_fallback: bool = False,
    catalog: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Build ordered multi-act BGM schedule with start/end boundaries and canonical paths."""
    cat = catalog if catalog is not None else load_audio_catalog(root)
    total_dur = float((manifest.get("audio") or {}).get("total_duration_sec", 0.0))
    cues_spec = manifest.get("bgm_cues")
    raw_cues: list[tuple[str, float, Optional[float], float]] = []

    if cues_spec and isinstance(cues_spec, list):
        for item in cues_spec:
            key = str(item.get("track") or item.get("mood") or manifest.get("bgm_track") or "")
            st = float(item.get("start_sec", 0.0))
            et = float(item["end_sec"]) if item.get("end_sec") is not None else None
            gain_off = float(item.get("gain_offset_db", 0.0))
            if key:
                raw_cues.append((key, st, et, gain_off))
    else:
        scenes = manifest.get("scenes", [])
        ir_scenes = (manifest.get("storyboard_ir") or {}).get("scenes") or []
        prev_key: Optional[str] = None
        for idx, sc in enumerate(scenes):
            st = float(sc.get("start_sec", 0.0))
            vs = sc.get("visual_spec") or (ir_scenes[idx] if idx < len(ir_scenes) else {}) or {}
            key = sc.get("bgm_track") or vs.get("bgm_mood") or sc.get("bgm_mood")
            if key and str(key) != prev_key:
                raw_cues.append((str(key), st, None, 0.0))
                prev_key = str(key)

    if not raw_cues:
        default_key = (
            manifest.get("bgm_track")
            or ((cfg.get("assets") or {}).get("bgm_by_pillar") or {}).get(manifest.get("pillar", ""))
            or "dramatic_mythology.mp3"
        )
        raw_cues.append((str(default_key), 0.0, total_dur or None, 0.0))

    raw_cues.sort(key=lambda c: c[1])
    if raw_cues[0][1] > 0.0:
        raw_cues.insert(0, (raw_cues[0][0], 0.0, raw_cues[0][1], raw_cues[0][3]))

    schedule: list[dict[str, Any]] = []
    for idx, (track_key, st, et, gain_off) in enumerate(raw_cues):
        resolved_path, is_fallback = resolve_bgm_path(
            root,
            track_key,
            cfg=cfg,
            catalog=cat,
            allow_synth_fallback=allow_synth_fallback,
        )
        end_sec = et if et is not None else (
            raw_cues[idx + 1][1] if idx + 1 < len(raw_cues) else total_dur
        )
        schedule.append(
            {
                "track": track_key,
                "path": resolved_path,
                "start_sec": round(max(0.0, st), 4),
                "end_sec": round(max(st + 0.25, end_sec), 4),
                "gain_offset_db": gain_off,
                "is_fallback": is_fallback,
            }
        )
    return schedule


def _match_cue_word_time(scene: dict[str, Any], cue_word: Optional[str]) -> Optional[float]:
    if not cue_word:
        return None
    target = cue_word.strip().lower()
    for w in scene.get("words") or []:
        wt = str(w.get("word") or w.get("text") or "").lower()
        if target in wt:
            return float(w.get("global_start", w.get("start", scene.get("start_sec", 0.0))))
    return None


def collect_sfx_schedule(
    root: Path,
    manifest: dict[str, Any],
    *,
    catalog: Optional[dict[str, Any]] = None,
    cut_crest_offset_sec: float = DEFAULT_CUT_CREST_OFFSET_SEC,
    allow_missing_sfx: bool = False,
) -> list[dict[str, Any]]:
    """Schedule SFX strictly from verified Storyboard IR props and scene transitions."""
    cat = catalog if catalog is not None else load_audio_catalog(root)
    scenes = manifest.get("scenes", [])
    ir_scenes = (manifest.get("storyboard_ir") or {}).get("scenes") or []
    total_dur = float((manifest.get("audio") or {}).get("total_duration_sec", 0.0))

    raw_events: list[tuple[str, float, float, str]] = []  # (sfx_name, target_time, gain_db, kind)

    for idx, sc in enumerate(scenes):
        st = float(sc.get("start_sec", 0.0))
        dur = float(sc.get("end_sec", st)) - st
        vs = sc.get("visual_spec") or (ir_scenes[idx] if idx < len(ir_scenes) else None)

        # 1. Scene transition SFX from verified visual_spec or scene.transition_sfx
        trans_sfx = (vs.get("transition_sfx") if isinstance(vs, dict) else None) or sc.get("transition_sfx") or sc.get("sfx_cue")
        if trans_sfx:
            target_t = st + (cut_crest_offset_sec if idx > 0 else 0.05)
            raw_events.append((str(trans_sfx), target_t, -2.0, "transition"))

        # 2. Verified Storyboard IR prop cues (only props explicitly present in visual_spec!)
        if isinstance(vs, dict):
            for prop in vs.get("props") or []:
                if not isinstance(prop, dict):
                    continue
                prop_sfx = prop.get("sfx") or prop.get("transition_sfx")
                if not prop_sfx:
                    continue
                cue_t = _match_cue_word_time(sc, prop.get("cue_word"))
                if cue_t is None:
                    cue_t = st + min(0.35, max(0.05, dur * 0.20))
                raw_events.append((str(prop_sfx), cue_t, -2.5, f"prop:{prop.get('id', 'prop')}"))

        # 3. Explicit scene sfx_events (verified against disk)
        for evt in sc.get("sfx_events") or []:
            if not isinstance(evt, dict) or not evt.get("sfx"):
                continue
            t_evt = float(evt["timestamp"]) if "timestamp" in evt else (st + float(evt.get("offset", 0.0)))
            raw_events.append((str(evt["sfx"]), t_evt, float(evt.get("gain_db", -2.0)), "explicit"))

    scheduled: list[dict[str, Any]] = []
    last_seen: dict[str, float] = {}

    for sfx_name, target_time, rel_gain_db, source in sorted(raw_events, key=lambda x: x[1]):
        sfx_path = resolve_sfx_path(root, sfx_name, catalog=cat)
        if sfx_path is None:
            if allow_missing_sfx:
                continue
            raise AudioMixError(f"SFX asset '{sfx_name}' referenced by '{source}' not found in assets/audio/sfx/.")

        stem = sfx_path.stem.lower()
        peak_offset = detect_sfx_peak_offset(sfx_path) if (stem in SWEEP_TRANSITION_STEMS or source == "transition") else 0.0
        raw_start = target_time - peak_offset
        trim_front = 0.0
        if raw_start < 0.0:
            trim_front = round(-raw_start, 4)
            raw_start = 0.0

        # Ensure SFX never extends into the final 0.72s quiet tail
        if total_dur > 1.5 and raw_start >= total_dur - 0.75:
            continue

        if sfx_path.name in last_seen and abs(raw_start - last_seen[sfx_path.name]) < 0.25:
            continue
        last_seen[sfx_path.name] = raw_start

        scheduled.append(
            {
                "sfx": sfx_path.name,
                "path": sfx_path,
                "start_sec": round(raw_start, 4),
                "target_time_sec": round(target_time, 4),
                "peak_offset_sec": round(peak_offset, 4),
                "trim_front_sec": trim_front,
                "gain_offset_db": rel_gain_db,
                "source": source,
            }
        )
    return scheduled


def probe_audio_stream(audio_path: Path) -> dict[str, Any]:
    """Verify sample_rate, channels, duration, and codec via ffprobe."""
    ffprobe = require_executable("ffprobe")
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,sample_rate,channels,bits_per_raw_sample",
            "-of",
            "json",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AudioMixError(f"ffprobe failed on '{audio_path}': {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    a_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not a_stream:
        raise AudioMixError(f"No audio stream found in '{audio_path}'.")
    return {
        "duration_sec": float(data.get("format", {}).get("duration", 0.0)),
        "sample_rate": int(a_stream.get("sample_rate", 0)),
        "channels": int(a_stream.get("channels", 0)),
        "codec_name": a_stream.get("codec_name"),
    }


def measure_loudness_ebur128(audio_path: Path) -> dict[str, float]:
    """Measure integrated LUFS and true peak dBTP via FFmpeg `ebur128`."""
    require_executable("ffmpeg")
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(audio_path),
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    i_matches = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", proc.stderr)
    tp_matches = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", proc.stderr)
    lra_matches = re.findall(r"LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", proc.stderr)
    if not i_matches or not tp_matches:
        raise AudioMixError(f"Failed to parse ebur128 stats for '{audio_path}'.")
    return {
        "integrated_lufs": float(i_matches[-1]),
        "true_peak_dbtp": float(tp_matches[-1]),
        "lra_lu": float(lra_matches[-1]) if lra_matches else 0.0,
    }


def detect_silences(
    audio_path: Path,
    noise_db: float = -45.0,
    min_duration: float = 0.50,
) -> list[dict[str, float]]:
    """Run FFmpeg `silencedetect` and return detected silence intervals."""
    require_executable("ffmpeg")
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(audio_path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_duration}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    silences: list[dict[str, float]] = []
    cur_start: Optional[float] = None
    for line in proc.stderr.splitlines():
        m_start = re.search(r"silence_start:\s*([0-9.]+)", line)
        if m_start:
            cur_start = float(m_start.group(1))
        m_end = re.search(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", line)
        if m_end:
            end_val = float(m_end.group(1))
            dur_val = float(m_end.group(2))
            silences.append(
                {
                    "start": cur_start if cur_start is not None else max(0.0, end_val - dur_val),
                    "end": end_val,
                    "duration": dur_val,
                }
            )
            cur_start = None
    if cur_start is not None:
        dur = probe_duration_sec(audio_path)
        silences.append({"start": cur_start, "end": dur, "duration": max(0.0, dur - cur_start)})
    return silences


def mix_episode_audio(
    root: Path,
    manifest: dict[str, Any],
    cfg: dict[str, Any],
    *,
    narration_path: Optional[Path] = None,
    output_wav_path: Path,
    allow_synth_fallback: bool = False,
    bgm_target_lufs: float = DEFAULT_BGM_TARGET_LUFS,
    sfx_gain_db: Optional[float] = None,
) -> dict[str, Any]:
    """Mix broadcast voice EQ/comp + loudness-matched BGM + peak-aligned SFX with ONE 2-pass loudnorm."""
    require_executable("ffmpeg")
    require_executable("ffprobe")

    resolved_narr = narration_path or (root / manifest["audio"]["narration_full_path"])
    if not resolved_narr.is_file():
        raise AudioMixError(f"Narration audio file missing: '{resolved_narr}'")

    total_dur = float((manifest.get("audio") or {}).get("total_duration_sec") or probe_duration_sec(resolved_narr))
    master_cfg = cfg.get("audio_mastering", {})
    target_lufs = float(master_cfg.get("target_lufs", DEFAULT_TARGET_LUFS))
    max_tp = float(master_cfg.get("true_peak_max_dbtp", DEFAULT_TRUE_PEAK_DBTP))
    aac_headroom_db = float(master_cfg.get("aac_true_peak_headroom_db", DEFAULT_AAC_TRUE_PEAK_HEADROOM_DB))
    target_tp = round(min(max_tp - max(0.0, aac_headroom_db), max_tp), 2)
    base_sfx_gain = float(sfx_gain_db if sfx_gain_db is not None else master_cfg.get("sfx_gain_db", -10.0))

    duck_cfg = master_cfg.get("sidechain_ducking", {})
    duck_thresh = float(duck_cfg.get("threshold", 0.03))
    duck_ratio = float(duck_cfg.get("ratio", 6.5))
    duck_attack = float(duck_cfg.get("attack_ms", 20))
    duck_release = float(duck_cfg.get("release_ms", 500))

    catalog = load_audio_catalog(root)
    bgm_schedule = parse_bgm_schedule(
        root, manifest, cfg, allow_synth_fallback=allow_synth_fallback, catalog=catalog
    )
    sfx_schedule = collect_sfx_schedule(root, manifest, catalog=catalog)

    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(resolved_narr)]
    in_idx = 1

    bgm_inputs: list[tuple[int, dict[str, Any], float]] = []
    for act_idx, cue in enumerate(bgm_schedule):
        if cue["is_fallback"]:
            cmd.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "aevalsrc=exprs='0.03*sin(2*PI*110*t)+0.02*sin(2*PI*165*t)':s=48000:c=stereo",
                ]
            )
            measured_lufs = -30.0
        else:
            cmd.extend(["-stream_loop", "-1", "-i", str(cue["path"])])
            measured_lufs = measure_integrated_lufs(cue["path"])
        gain_db = round(max(-36.0, min(18.0, (bgm_target_lufs - measured_lufs) + cue["gain_offset_db"])), 2)
        bgm_inputs.append((in_idx, cue, gain_db))
        in_idx += 1

    sfx_inputs: list[tuple[int, dict[str, Any]]] = []
    for sfx_evt in sfx_schedule:
        cmd.extend(["-i", str(sfx_evt["path"])])
        sfx_inputs.append((in_idx, sfx_evt))
        in_idx += 1

    filters: list[str] = [
        "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
        "highpass=f=75,equalizer=f=180:t=q:w=1.0:g=1.6,"
        "equalizer=f=4600:t=q:w=1.4:g=-1.5,equalizer=f=9800:t=q:w=1.0:g=1.4,"
        "acompressor=threshold=-18dB:ratio=2.3:attack=15:release=120,asplit=2[voice_main][voice_sc]"
    ]

    tail_quiet_sec = float(master_cfg.get("trailing_silence_min_sec", 0.7))
    bgm_stop_sec = max(1.0, total_dur - max(0.75, tail_quiet_sec + 0.05))

    bgm_labels: list[str] = []
    for k, (i_num, cue, gain_db) in enumerate(bgm_inputs):
        is_last = k == len(bgm_inputs) - 1
        t0 = cue["start_sec"]
        t1 = min(bgm_stop_sec, cue["end_sec"]) if is_last else min(bgm_stop_sec, cue["end_sec"] + 0.8)
        seg_dur = max(0.4, t1 - t0)
        delay_ms = int(round(t0 * 1000.0))
        fade_in = min(1.0, seg_dur * 0.25)
        fade_out = min(1.4, seg_dur * 0.35)
        fade_out_st = max(0.0, seg_dur - fade_out)
        lbl = f"[bgm_{k}]"
        delay_part = f",adelay={delay_ms}|{delay_ms}" if delay_ms > 0 else ""
        filters.append(
            f"[{i_num}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"atrim=0:{seg_dur:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade_in:.3f},"
            f"afade=t=out:st={fade_out_st:.4f}:d={fade_out:.3f},"
            f"volume={gain_db}dB{delay_part}{lbl}"
        )
        bgm_labels.append(lbl)

    filters.append(
        f"{''.join(bgm_labels)}amix=inputs={len(bgm_labels)}:normalize=0:duration=longest:dropout_transition=0,"
        f"atrim=0:{bgm_stop_sec:.4f},apad=whole_dur={total_dur:.4f}[bgm_raw]"
    )
    filters.append(
        f"[bgm_raw][voice_sc]sidechaincompress=threshold={duck_thresh}:ratio={duck_ratio}:"
        f"attack={duck_attack}:release={duck_release}:makeup=1[bgm_ducked]"
    )

    mix_labels = ["[voice_main]", "[bgm_ducked]"]
    for k, (i_num, sfx_evt) in enumerate(sfx_inputs):
        delay_ms = int(round(sfx_evt["start_sec"] * 1000.0))
        gain_db = round(base_sfx_gain + sfx_evt["gain_offset_db"], 2)
        trim_front = sfx_evt["trim_front_sec"]
        trim_part = f"atrim=start={trim_front:.4f},asetpts=PTS-STARTPTS," if trim_front > 0 else ""
        max_sfx_dur = max(0.15, (total_dur - 0.72) - sfx_evt["start_sec"])
        delay_part = f",adelay={delay_ms}|{delay_ms}" if delay_ms > 0 else ""
        lbl = f"[sfx_{k}]"
        filters.append(
            f"[{i_num}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"{trim_part}atrim=0:{max_sfx_dur:.4f},asetpts=PTS-STARTPTS,"
            f"volume={gain_db}dB{delay_part}{lbl}"
        )
        mix_labels.append(lbl)

    filters.append(
        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:normalize=0:duration=first:dropout_transition=2[raw_mix]"
    )

    # Pass 1: measure raw mix EBU R128 stats
    pass1_cmd = cmd + [
        "-filter_complex",
        ";".join(filters + [f"[raw_mix]loudnorm=I={target_lufs}:TP={target_tp}:LRA={DEFAULT_LRA}:print_format=json[m]"]),
        "-map",
        "[m]",
        "-f",
        "null",
        "-",
    ]
    p1 = subprocess.run(pass1_cmd, capture_output=True, text=True, check=False)
    if p1.returncode != 0:
        raise AudioMixError(f"loudnorm pass 1 failed: {p1.stderr}")
    s_idx = p1.stderr.rfind("{")
    e_idx = p1.stderr.rfind("}")
    if s_idx == -1 or e_idx == -1:
        raise AudioMixError("loudnorm pass 1 did not emit JSON measurement stats.")
    stats = json.loads(p1.stderr[s_idx : e_idx + 1])

    # Pass 2: linear EBU R128 render to 48 kHz 24-bit stereo WAV (single loudnorm pass!)
    norm_filter = (
        f"[raw_mix]loudnorm=I={target_lufs}:TP={target_tp}:LRA={DEFAULT_LRA}:"
        f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
        f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
        f"offset={stats['target_offset']}:linear=true,"
        "aformat=sample_rates=48000:channel_layouts=stereo[final_audio]"
    )
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = output_wav_path.with_suffix(".tmp.wav")
    pass2_cmd = cmd + [
        "-filter_complex",
        ";".join(filters + [norm_filter]),
        "-map",
        "[final_audio]",
        "-ar",
        str(BROADCAST_SAMPLE_RATE),
        "-ac",
        str(BROADCAST_CHANNELS),
        "-c:a",
        "pcm_s24le",
        str(tmp_out),
    ]
    p2 = subprocess.run(pass2_cmd, capture_output=True, text=True, check=False)
    if p2.returncode != 0 or not tmp_out.is_file():
        if tmp_out.exists():
            tmp_out.unlink()
        raise AudioMixError(f"FFmpeg master audio mix failed: {p2.stderr}")
    tmp_out.replace(output_wav_path)

    stream_info = probe_audio_stream(output_wav_path)
    loudness = measure_loudness_ebur128(output_wav_path)
    silences = detect_silences(output_wav_path, noise_db=-42.0, min_duration=0.45)

    return {
        "output_wav": str(output_wav_path),
        "sample_rate": stream_info["sample_rate"],
        "channels": stream_info["channels"],
        "duration_sec": round(stream_info["duration_sec"], 4),
        "integrated_lufs": loudness["integrated_lufs"],
        "true_peak_dbtp": loudness["true_peak_dbtp"],
        "lra_lu": loudness["lra_lu"],
        "bgm_acts": len(bgm_inputs),
        "sfx_cues": len(sfx_inputs),
        "silences": silences,
    }
