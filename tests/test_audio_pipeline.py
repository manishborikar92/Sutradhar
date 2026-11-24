"""Unit and integration tests for Phase 3 Broadcast 48kHz Stereo Audio Pipeline.

Verifies:
1. Narration 48,000Hz stereo up-mixing before split.
2. BGM and SFX 48,000Hz stereo channel formatting.
3. amix filter `normalize=0` volume protection.
4. Sidechain compressor parameters (ratio=8, threshold=0.03, attack=20ms, release=500ms).
5. EBU R128 integrated loudness normalization (I=-14, TP=-1.5, LRA=11).
6. FFmpeg output options (-ar 48000 -ac 2 -b:a 192k).
7. End-to-end synthetic audio mixing with ffprobe verification.
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

from scripts.engine.config import (
    BROADCAST_BIT_DEPTH,
    BROADCAST_CHANNELS,
    BROADCAST_SAMPLE_RATE_HZ,
    LOUDNORM_TARGET_I,
    LOUDNORM_TARGET_LRA,
    LOUDNORM_TARGET_TP,
    SIDECHAIN_ATTACK_MS,
    SIDECHAIN_MAKEUP,
    SIDECHAIN_RATIO,
    SIDECHAIN_RELEASE_MS,
    SIDECHAIN_THRESHOLD,
)
from scripts.render_and_qa import build_audio_mix, probe_media


class TestBroadcastAudioPipelineSpecs:
    """Verifies architectural audio pipeline specifications."""

    def test_broadcast_constants(self):
        assert BROADCAST_SAMPLE_RATE_HZ == 48000
        assert BROADCAST_CHANNELS == 2
        assert BROADCAST_BIT_DEPTH == 24
        assert LOUDNORM_TARGET_I == -14.0
        assert LOUDNORM_TARGET_TP == -1.5
        assert LOUDNORM_TARGET_LRA == 11.0
        assert SIDECHAIN_RATIO == 8.0
        assert SIDECHAIN_RELEASE_MS == 500
        assert SIDECHAIN_ATTACK_MS == 20
        assert SIDECHAIN_THRESHOLD == 0.03
        assert SIDECHAIN_MAKEUP == 1.0

    def test_filter_complex_generation_strings(self):
        """Inspects build_audio_mix filter graph construction."""
        # Mock subprocess to capture ffmpeg command arguments
        mock_manifest = {
            "audio": {
                "narration_full_path": "build/audio/narration_full.wav",
                "total_duration_sec": 10.0,
            },
            "bgm_track": "theatrical_narrative.mp3",
            "scenes": [
                {
                    "scene_index": 1,
                    "start_sec": 0.0,
                    "end_sec": 10.0,
                    "duration_sec": 10.0,
                }
            ],
            "props": [
                {
                    "id": "prop_kundali_1",
                    "prop_id": "vedic_kundali",
                    "start_sec": 1.0,
                    "duration_sec": 4.0,
                }
            ],
        }
        mock_cfg = {
            "audio_mastering": {
                "sample_rate_hz": 48000,
                "channels": 2,
                "bgm_base_gain_db": -22.0,
                "sfx_gain_db": -10.0,
                "sidechain_ducking": {
                    "threshold": 0.03,
                    "ratio": 8,
                    "attack_ms": 20,
                    "release_ms": 500,
                },
                "ebu_r128": {
                    "integrated_lufs": -14.0,
                    "true_peak_dbtp": -1.5,
                    "lra": 11,
                },
            }
        }

        captured_cmds = []

        def fake_run(cmd, *args, **kwargs):
            captured_cmds.append(cmd)
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = ""
            mock_res.stderr = ""
            return mock_res

        with patch("subprocess.run", side_effect=fake_run):
            with tempfile.TemporaryDirectory() as td:
                t_root = Path(td)
                (t_root / "build" / "audio").mkdir(parents=True)
                (t_root / "assets" / "bgm").mkdir(parents=True)
                (t_root / "assets" / "sfx").mkdir(parents=True)

                (t_root / "build" / "audio" / "narration_full.wav").write_bytes(b"dummy")
                (t_root / "assets" / "bgm" / "theatrical_narrative.mp3").write_bytes(b"dummy")
                (t_root / "assets" / "sfx" / "crystal_shatter.wav").write_bytes(b"dummy")

                raw_video = t_root / "build" / "raw_video.mp4"
                out_video = t_root / "build" / "final_short.mp4"
                raw_video.write_bytes(b"dummy")

                build_audio_mix(t_root, mock_manifest, mock_cfg, raw_video, out_video)

        assert len(captured_cmds) == 1
        ffmpeg_cmd = captured_cmds[0]

        # 1. Check Output Encoding Options: 48,000Hz stereo
        assert "-ar" in ffmpeg_cmd
        ar_idx = ffmpeg_cmd.index("-ar")
        assert ffmpeg_cmd[ar_idx + 1] == "48000"

        assert "-ac" in ffmpeg_cmd
        ac_idx = ffmpeg_cmd.index("-ac")
        assert ffmpeg_cmd[ac_idx + 1] == "2"

        assert "-b:a" in ffmpeg_cmd
        ba_idx = ffmpeg_cmd.index("-b:a")
        assert ffmpeg_cmd[ba_idx + 1] == "192k"

        # 2. Check Filter Complex contents
        fc_idx = ffmpeg_cmd.index("-filter_complex")
        filter_str = ffmpeg_cmd[fc_idx + 1]

        # Narration stereo upmix & mastering
        assert "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo" in filter_str

        # BGM 48kHz stereo format
        assert "sample_rates=48000:channel_layouts=stereo" in filter_str

        # Sidechain compressor settings
        assert "sidechaincompress=threshold=0.03:ratio=8:attack=20:release=500:makeup=1" in filter_str

        # amix normalize=0
        assert "amix=inputs=" in filter_str
        assert "normalize=0" in filter_str

        # EBU R128 integrated loudness normalization
        assert "loudnorm=I=-14:TP=-1.5:LRA=11" in filter_str


class TestLiveAudioMasteringExecution:
    """Tests live FFmpeg audio processing with synthetic signals to verify output properties."""

    @pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not found on PATH")
    def test_ffmpeg_48k_stereo_output(self, tmp_path):
        """Renders synthetic test signals through the exact broadcast mastering filter graph."""
        # 1. Generate 3.0s synthetic narration (1kHz tone, mono 44.1kHz)
        narr_file = tmp_path / "narration.wav"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=3.0",
                "-ar", "44100", "-ac", "1",
                str(narr_file),
            ],
            capture_output=True,
            check=True,
        )

        # 2. Generate 4.0s synthetic BGM (220Hz drone, stereo 44.1kHz)
        bgm_file = tmp_path / "bgm.wav"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=4.0",
                "-ar", "44100", "-ac", "2",
                str(bgm_file),
            ],
            capture_output=True,
            check=True,
        )

        # 3. Generate 1.0s synthetic SFX (500Hz burst)
        sfx_file = tmp_path / "sfx.wav"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "sine=frequency=500:duration=1.0",
                "-ar", "44100", "-ac", "1",
                str(sfx_file),
            ],
            capture_output=True,
            check=True,
        )

        out_mix = tmp_path / "mastered_output.wav"

        # Apply the exact Phase 3 Broadcast Mastering Filtergraph
        filter_complex = (
            "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            "highpass=f=80,acompressor=threshold=-18dB:ratio=2.5:attack=15:release=120,asplit=2[narration_mastered][narration_sidechain];"
            "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,atrim=0:3.5,asetpts=PTS-STARTPTS,volume=-20dB[bgm_base];"
            "[bgm_base][narration_sidechain]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=500:makeup=1[bgm_ducked];"
            "[2:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,adelay=1000|1000,volume=-10dB[sfx_0];"
            "[narration_mastered][bgm_ducked][sfx_0]amix=inputs=3:duration=first:normalize=0[mixed_raw];"
            "[mixed_raw]loudnorm=I=-14:TP=-1.5:LRA=11[a_out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(narr_file),
            "-i", str(bgm_file),
            "-i", str(sfx_file),
            "-filter_complex", filter_complex,
            "-map", "[a_out]",
            "-ar", "48000",
            "-ac", "2",
            str(out_mix),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"FFmpeg mixing failed: {res.stderr}"

        # 4. Probe output audio file using ffprobe
        info = probe_media(out_mix)
        streams = info.get("streams", [])
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        assert a_stream is not None

        # Verify 48,000Hz sampling rate and 2-channel stereo
        assert int(a_stream.get("sample_rate", 0)) == 48000
        assert int(a_stream.get("channels", 0)) == 2
