#!/usr/bin/env python3
"""Sutradhar Phase 5 Manifest and Audio Verification Script."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

def main() -> int:
    manifest_js_path = Path("build/manifest.js")
    audio_manifest_path = Path("build/audio/audio_manifest.json")

    if not manifest_js_path.is_file():
        print(f"FAIL: Missing {manifest_js_path}", file=sys.stderr)
        return 1
    if not audio_manifest_path.is_file():
        print(f"FAIL: Missing {audio_manifest_path}", file=sys.stderr)
        return 1

    # 1. Parse manifest.js and audio_manifest.json
    manifest_js_text = manifest_js_path.read_text(encoding="utf-8")
    js_match = re.search(r"window\.EPISODE_MANIFEST\s*=\s*(\{.*\});", manifest_js_text, re.DOTALL)
    if not js_match:
        print("FAIL: manifest.js does not contain window.EPISODE_MANIFEST", file=sys.stderr)
        return 1
    manifest_js_obj = json.loads(js_match.group(1))
    audio_manifest_obj = json.loads(audio_manifest_path.read_text(encoding="utf-8"))

    # Check exact equality
    if manifest_js_obj != audio_manifest_obj:
        print("FAIL: manifest.js does not match audio_manifest.json", file=sys.stderr)
        return 1
    print("✓ PASSED: manifest.js matches audio_manifest.json exactly.")

    # Required top-level fields
    required_fields = [
        "schema_version",
        "language",
        "series_id",
        "series_title",
        "pillar",
        "tts_engine",
        "tts_voice",
        "video",
        "audio",
        "scenes",
        "beats",
    ]
    for f in required_fields:
        if f not in audio_manifest_obj:
            print(f"FAIL: Missing required field '{f}'", file=sys.stderr)
            return 1
    print("✓ PASSED: All required top-level fields present.")

    engine = audio_manifest_obj["tts_engine"]
    voice = audio_manifest_obj["tts_voice"]
    lang = audio_manifest_obj["language"]
    sr = audio_manifest_obj["audio"]["sample_rate"]

    assert audio_manifest_obj["schema_version"] == "2.0"
    assert lang == "hi", f"Expected language 'hi', got '{lang}'"
    assert engine in ("elevenlabs", "eleven_v4"), f"Expected engine 'elevenlabs' or 'eleven_v4', got '{engine}'"
    assert voice == "uuyFQegRan8rpIQCGu9K", f"Expected voice 'uuyFQegRan8rpIQCGu9K', got '{voice}'"
    assert sr == 44100, f"Expected sample rate 44100, got {sr}"
    print(f"✓ PASSED: Engine={engine}, Voice={voice}, Lang={lang}, SampleRate={sr} Hz")

    scenes = audio_manifest_obj["scenes"]
    assert len(scenes) == 5, f"Expected 5 scenes, got {len(scenes)}"

    # Check scene boundaries and tag leakage
    tag_re = re.compile(r"\[.*?\]")
    cursor = 0.0
    for idx, s in enumerate(scenes):
        s_idx = s["scene_index"]
        st = float(s["start_sec"])
        mid = float(s["midpoint_sec"])
        et = float(s["end_sec"])
        dur = float(s["duration_sec"])
        clean_narr = s["narration_text"]
        applied_tts = s.get("tts_text_applied", "")
        words = s["words"]

        # Boundary monotonicity
        assert abs(st - cursor) < 1e-4, f"Scene {s_idx} start {st} does not match cursor {cursor}"
        assert st < mid < et, f"Scene {s_idx} timestamps not strictly increasing: {st} < {mid} < {et}"
        assert abs((et - st) - dur) < 1e-3, f"Scene {s_idx} duration mismatch: {dur} != {et - st}"
        cursor = et

        # Tag leakage checks
        assert not tag_re.search(clean_narr), f"Tag leakage in scene {s_idx} narration_text: {clean_narr}"
        for w in words:
            tok = w["word"]
            assert not tag_re.search(tok), f"Tag leakage in scene {s_idx} word token: {tok}"
            assert float(w["start"]) < float(w["end"]), f"Invalid word span {w}"
            assert float(w["global_start"]) < float(w["global_end"]), f"Invalid global word span {w}"
            assert float(w["global_start"]) >= st - 0.05, f"Word global_start {w['global_start']} < scene start {st}"
            assert float(w["global_end"]) <= et + 0.1, f"Word global_end {w['global_end']} > scene end {et}"

        # Applied text should preserve steering tag
        assert tag_re.search(applied_tts), f"Scene {s_idx} tts_text_applied missing steering tag: {applied_tts}"
        print(f"  Scene {s_idx}: [{st:6.2f}s - {et:6.2f}s] ({dur:5.2f}s) | Words: {len(words):2d} | Steering Tag: {applied_tts[:32]:32s} | Clean: {clean_narr[:35]}...")

    print("✓ PASSED: Zero tag leakage across all scenes and words!")
    print("✓ PASSED: Scene boundaries strictly monotonic with zero gaps/overlaps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
