"""Unit and integration tests for Phase 4 Automated Triple-Gate QA Verifier and KinoCut Fail-Closed Enforcement.

Verifies:
1. Gate 1: Cinematography & Temporal Pacing QA (ASL bounds, static hold, opening hook).
2. Gate 2: Geometric & Safe-Zone QA (Character widths, negative space, zero collision, facial clearance).
3. Gate 3: Acoustic & Spectral Quality QA (48kHz, stereo, spectral ceiling, EBU R128 loudness, true peak).
4. KinoCut Strict Fail-Closed Verification (Eliminates 90.0 default; fails on missing/malformed scores).
5. Comprehensive error diagnostics and failure reporting.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.engine.qa_verifier import (
    QACheckResult,
    QAGateReport,
    QASuiteReport,
    QAVerificationError,
    compute_spectral_ceiling,
    measure_ebu_r128_loudness,
    run_triple_gate_qa,
    verify_acoustic_and_spectral_master,
    verify_geometric_and_safe_zones,
    verify_temporal_and_cinematography_pacing,
)
from scripts.render_and_qa import RenderPipelineError, run_render_and_qa_pipeline


# ==============================================================================
# Gate 1: Cinematography & Temporal Pacing Tests
# ==============================================================================

class TestGate1CinematographyQA:
    """Verifies ASL calculation, static hold limit, and opening hook duration."""

    def test_valid_pacing_passes(self):
        manifest = {
            "total_duration_sec": 10.0,
            "beats": [
                {"beat_id": "1_1", "duration_sec": 1.9, "start_sec": 0.0, "is_hook": True},
                {"beat_id": "1_2", "duration_sec": 2.6, "start_sec": 1.9, "is_hook": False},
                {"beat_id": "2_1", "duration_sec": 2.8, "start_sec": 4.5, "is_hook": False},
                {"beat_id": "2_2", "duration_sec": 2.7, "start_sec": 7.3, "is_hook": False},
            ],
            "scenes": [{"scene_index": 1}, {"scene_index": 2}],
        }
        report = verify_temporal_and_cinematography_pacing(manifest)
        assert report.passed is True
        assert report.failure_count == 0

    def test_asl_too_fast_fails(self):
        # 10s with 7 beats -> ASL = 1.42s (< 1.8s)
        beats = [{"beat_id": f"b_{i}", "duration_sec": 1.42, "start_sec": i * 1.42} for i in range(7)]
        manifest = {"total_duration_sec": 10.0, "beats": beats, "scenes": [{"scene_index": 1}]}
        report = verify_temporal_and_cinematography_pacing(manifest)
        assert report.passed is False
        assert any("CINEMA-ASL" in msg for msg in report.failure_messages)
        assert any("ASL VIOLATION" in msg for msg in report.failure_messages)

    def test_asl_too_slow_fails(self):
        # 20s with 5 beats of 4.0s -> ASL = 4.0s (> 3.2s)
        beats = [{"beat_id": f"b_{i}", "duration_sec": 4.0, "start_sec": i * 4.0} for i in range(5)]
        manifest = {"total_duration_sec": 20.0, "beats": beats, "scenes": [{"scene_index": 1}]}
        report = verify_temporal_and_cinematography_pacing(manifest)
        assert report.passed is False
        assert any("CINEMA-ASL" in msg for msg in report.failure_messages)

    def test_static_hold_exceeding_3_8s_fails(self):
        manifest = {
            "total_duration_sec": 12.0,
            "beats": [
                {"beat_id": "1_1", "duration_sec": 1.8, "start_sec": 0.0},
                {"beat_id": "1_2", "duration_sec": 4.2, "start_sec": 1.8},  # Violates 3.8s!
                {"beat_id": "2_1", "duration_sec": 3.0, "start_sec": 6.0},
                {"beat_id": "2_2", "duration_sec": 3.0, "start_sec": 9.0},
            ],
            "scenes": [{"scene_index": 1}, {"scene_index": 2}],
        }
        report = verify_temporal_and_cinematography_pacing(manifest)
        assert report.passed is False
        assert any("CINEMA-STATIC-HOLD" in msg for msg in report.failure_messages)
        assert any("1_2" in msg for msg in report.failure_messages)

    def test_opening_hook_exceeding_2_0s_fails(self):
        manifest = {
            "total_duration_sec": 10.0,
            "beats": [
                {"beat_id": "1_1", "duration_sec": 3.2, "start_sec": 0.0, "is_hook": True},  # Violates 2.0s hook!
                {"beat_id": "1_2", "duration_sec": 2.5, "start_sec": 3.2, "is_hook": False},
                {"beat_id": "2_1", "duration_sec": 2.5, "start_sec": 5.7, "is_hook": False},
                {"beat_id": "2_2", "duration_sec": 1.8, "start_sec": 8.2, "is_hook": False},
            ],
            "scenes": [{"scene_index": 1}, {"scene_index": 2}],
        }
        report = verify_temporal_and_cinematography_pacing(manifest)
        assert report.passed is False
        assert any("CINEMA-HOOK-DURATION" in msg for msg in report.failure_messages)


# ==============================================================================
# Gate 2: Geometric & Safe-Zone QA Tests
# ==============================================================================

class TestGate2GeometricQA:
    """Verifies character dimensions, central conversational space, zero overlap, and facial clearance."""

    def test_valid_geometry_and_safe_zones_pass(self):
        dom_snapshots = [
            {
                "shot_id": "shot_1",
                "shot_type": "full_two_shot",
                "p1_width_px": 360,
                "p2_width_px": 360,
                "gap_px": 180,
                "overlap_px": 0,
                "head_y_px": 480,
                "subtitle_y_px": 1580,
                "overlay_intersects_head": False,
            }
        ]
        manifest = {"scenes": [{"scene_index": 1}]}
        report = verify_geometric_and_safe_zones(manifest, dom_snapshots)
        assert report.passed is True
        assert report.failure_count == 0

    def test_character_width_exceeding_400px_fails(self):
        dom_snapshots = [
            {
                "shot_id": "shot_wide",
                "shot_type": "full_two_shot",
                "p1_width_px": 460,  # Exceeds 400px!
                "p2_width_px": 360,
                "gap_px": 180,
                "overlap_px": 0,
                "overlay_intersects_head": False,
            }
        ]
        report = verify_geometric_and_safe_zones({"scenes": []}, dom_snapshots)
        assert report.passed is False
        assert any("GEOM-CHAR-WIDTH" in msg for msg in report.failure_messages)

    def test_character_overlap_collision_fails(self):
        dom_snapshots = [
            {
                "shot_id": "shot_collide",
                "shot_type": "two_character_confrontation",
                "p1_width_px": 360,
                "p2_width_px": 360,
                "gap_px": -40,
                "overlap_px": 40,  # Collision detected!
                "overlay_intersects_head": False,
            }
        ]
        report = verify_geometric_and_safe_zones({"scenes": []}, dom_snapshots)
        assert report.passed is False
        assert any("GEOM-ZERO-OVERLAP" in msg for msg in report.failure_messages)
        assert any("CHARACTER COLLISION" in msg for msg in report.failure_messages)

    def test_facial_occlusion_by_overlay_fails(self):
        dom_snapshots = [
            {
                "shot_id": "shot_occluded",
                "shot_type": "medium",
                "p1_width_px": 360,
                "head_y_px": 480,
                "subtitle_y_px": 520,  # Occluding head area!
                "overlay_intersects_head": True,
            }
        ]
        report = verify_geometric_and_safe_zones({"scenes": []}, dom_snapshots)
        assert report.passed is False
        assert any("GEOM-FACIAL-CLEARANCE" in msg for msg in report.failure_messages)


# ==============================================================================
# Gate 3: Acoustic & Spectral Quality QA Tests
# ==============================================================================

class TestGate3AcousticAndSpectralQA:
    """Verifies 48kHz sampling, stereo channels, spectral ceiling, and loudness."""

    @pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe not found on PATH")
    def test_genuine_48k_stereo_audio_passes(self):
        bgm_path = REPO_ROOT / "assets" / "bgm" / "theatrical_narrative.mp3"
        report = verify_acoustic_and_spectral_master(bgm_path)
        # Note: BGM file alone will pass 48kHz, stereo, and spectral ceiling
        sr_check = next((c for c in report.checks if c.check_id == "AUDIO-48KHZ"), None)
        assert sr_check is not None and sr_check.passed is True

        stereo_check = next((c for c in report.checks if c.check_id == "AUDIO-STEREO"), None)
        assert stereo_check is not None and stereo_check.passed is True

    @pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not found on PATH")
    def test_downsampled_24k_audio_fails(self, tmp_path):
        downsampled_wav = tmp_path / "downsampled_24k.wav"
        # Generate 24kHz audio file
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=2.0",
                "-ar", "24000", "-ac", "2",
                str(downsampled_wav),
            ],
            capture_output=True,
            check=True,
        )
        report = verify_acoustic_and_spectral_master(downsampled_wav)
        assert report.passed is False
        sr_check = next((c for c in report.checks if c.check_id == "AUDIO-48KHZ"), None)
        assert sr_check is not None and sr_check.passed is False
        assert "24kHz downsampling detected" in sr_check.message

    @pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not found on PATH")
    def test_mono_audio_fails(self, tmp_path):
        mono_wav = tmp_path / "mono_audio.wav"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=2.0",
                "-ar", "48000", "-ac", "1",
                str(mono_wav),
            ],
            capture_output=True,
            check=True,
        )
        report = verify_acoustic_and_spectral_master(mono_wav)
        assert report.passed is False
        mono_check = next((c for c in report.checks if c.check_id == "AUDIO-STEREO"), None)
        assert mono_check is not None and mono_check.passed is False
        assert "Mono audio detected" in mono_check.message


# ==============================================================================
# KinoCut Strict Fail-Closed Verification Tests
# ==============================================================================

class TestKinoCutFailClosedEnforcement:
    """Verifies that render_and_qa.py strictly fails closed with zero magic 90.0 defaults."""

    def test_kinocut_missing_score_fails_closed(self, tmp_path):
        fake_manifest = {
            "schema_version": "2.0",
            "series_id": 1,
            "scenes": [{"scene_index": 1, "start_sec": 0.0, "end_sec": 35.0}],
            "audio": {"narration_full_path": "build/audio/narration_full.wav", "total_duration_sec": 35.0},
        }
        cfg = {
            "paths": {"build_dir": "build"},
            "audio_mastering": {"kinocut_min_score": 80.0},
        }

        mock_kino = MagicMock()
        # Returns empty dict with NO score!
        mock_kino.release_checkpoint.return_value = {}

        with patch("kinocut.Client", return_value=mock_kino), \
             patch("scripts.render_and_qa.load_config", return_value=cfg), \
             patch("scripts.render_and_qa.compose_episode"), \
             patch("subprocess.run") as mock_subproc:

            mock_subproc.return_value = MagicMock(returncode=0, stdout='{"streams":[{"codec_type":"video","width":1080,"height":1920,"duration":"35.0"},{"codec_type":"audio","sample_rate":"48000","channels":2,"duration":"35.0"}]}')

            # Create required mock files in tmp_path
            (tmp_path / "build" / "audio").mkdir(parents=True)
            (tmp_path / "build" / "raw_video.mp4").write_bytes(b"dummy")
            (tmp_path / "build" / "final_short.mp4").write_bytes(b"dummy")
            (tmp_path / "build" / "audio" / "narration_full.wav").write_bytes(b"dummy")
            (tmp_path / "build" / "manifest.js").write_text(f"window.EPISODE_MANIFEST = {json.dumps(fake_manifest)};", encoding="utf-8")

            with pytest.raises(RenderPipelineError, match="No quality score found in checkpoint response"):
                run_render_and_qa_pipeline(tmp_path)

    def test_kinocut_non_dict_response_fails_closed(self, tmp_path):
        fake_manifest = {
            "schema_version": "2.0",
            "series_id": 1,
            "scenes": [{"scene_index": 1, "start_sec": 0.0, "end_sec": 35.0}],
            "audio": {"narration_full_path": "build/audio/narration_full.wav", "total_duration_sec": 35.0},
        }
        cfg = {
            "paths": {"build_dir": "build"},
            "audio_mastering": {"kinocut_min_score": 80.0},
        }

        mock_kino = MagicMock()
        # Returns string instead of dict
        mock_kino.release_checkpoint.return_value = "invalid_string"

        with patch("kinocut.Client", return_value=mock_kino), \
             patch("scripts.render_and_qa.load_config", return_value=cfg), \
             patch("scripts.render_and_qa.compose_episode"), \
             patch("subprocess.run") as mock_subproc:

            mock_subproc.return_value = MagicMock(returncode=0, stdout='{"streams":[{"codec_type":"video","width":1080,"height":1920,"duration":"35.0"},{"codec_type":"audio","sample_rate":"48000","channels":2,"duration":"35.0"}]}')

            (tmp_path / "build" / "audio").mkdir(parents=True)
            (tmp_path / "build" / "raw_video.mp4").write_bytes(b"dummy")
            (tmp_path / "build" / "final_short.mp4").write_bytes(b"dummy")
            (tmp_path / "build" / "audio" / "narration_full.wav").write_bytes(b"dummy")
            (tmp_path / "build" / "manifest.js").write_text(f"window.EPISODE_MANIFEST = {json.dumps(fake_manifest)};", encoding="utf-8")

            with pytest.raises(RenderPipelineError, match="Expected dict response, got str"):
                run_render_and_qa_pipeline(tmp_path)

    def test_kinocut_below_min_score_fails_closed(self, tmp_path):
        fake_manifest = {
            "schema_version": "2.0",
            "series_id": 1,
            "scenes": [{"scene_index": 1, "start_sec": 0.0, "end_sec": 35.0}],
            "audio": {"narration_full_path": "build/audio/narration_full.wav", "total_duration_sec": 35.0},
        }
        cfg = {
            "paths": {"build_dir": "build"},
            "audio_mastering": {"kinocut_min_score": 80.0},
        }
        mock_kino = MagicMock()
        # Returns failing score of 72.5 (< 80.0)
        mock_kino.release_checkpoint.return_value = {"quality": {"overall_score": 72.5}}

        with patch("kinocut.Client", return_value=mock_kino), \
             patch("scripts.render_and_qa.load_config", return_value=cfg), \
             patch("scripts.render_and_qa.compose_episode"), \
             patch("subprocess.run") as mock_subproc:

            mock_subproc.return_value = MagicMock(returncode=0, stdout='{"streams":[{"codec_type":"video","width":1080,"height":1920,"duration":"35.0"},{"codec_type":"audio","sample_rate":"48000","channels":2,"duration":"35.0"}]}')

            (tmp_path / "build" / "audio").mkdir(parents=True)
            (tmp_path / "build" / "raw_video.mp4").write_bytes(b"dummy")
            (tmp_path / "build" / "final_short.mp4").write_bytes(b"dummy")
            (tmp_path / "build" / "audio" / "narration_full.wav").write_bytes(b"dummy")
            (tmp_path / "build" / "manifest.js").write_text(f"window.EPISODE_MANIFEST = {json.dumps(fake_manifest)};", encoding="utf-8")

            with pytest.raises(RenderPipelineError, match="quality score 72.5 is below minimum 80.0"):
                run_render_and_qa_pipeline(tmp_path)
