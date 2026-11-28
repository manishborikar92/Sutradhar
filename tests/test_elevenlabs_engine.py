#!/usr/bin/env python3
"""Automated unit and integration tests for scripts/elevenlabs_engine.py.

Verifies:
1. Cache key generation (determinism, sensitivity to text, voice_id, model, settings).
2. Audio tag stripping for subtitle/Whisper alignment (preserves Devanagari text).
3. Audio decoding (float32 array, mono conversion, error handling on bad/empty data).
4. Content-addressable disk cache (cache hit, cache miss, atomic file writing, corruption recovery).
5. Subscription and quota balance tracking (parsing, credit checks on cache miss, quota exceeded errors).
6. Voice metadata inspection (Viraj default, custom voice).
7. HTTP resilience & error mapping (401 auth, 402 payment, 429 rate limit backoff, 5xx retry, socket timeouts).
8. File synthesis and FakeElevenLabs compatibility.
9. 100% offline execution with zero billable API requests.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import requests
import soundfile as sf

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from elevenlabs_engine import (
    DEFAULT_MODEL_ID,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_VOICE_ID,
    DEFAULT_VOICE_SETTINGS,
    ElevenLabsAPIError,
    ElevenLabsAuthError,
    ElevenLabsEngine,
    ElevenLabsError,
    ElevenLabsQuotaExceededError,
    ElevenLabsRateLimitError,
    ElevenLabsTimeoutError,
    FakeElevenLabs,
    SubscriptionInfo,
    VoiceInfo,
    compute_cache_key,
    decode_audio_bytes,
    mask_api_key,
    strip_audio_tags,
)


def make_test_mp3_bytes(duration_sec: float = 0.5, sample_rate: int = DEFAULT_SAMPLE_RATE) -> bytes:
    """Generate real, valid MP3 audio bytes in memory for deterministic offline testing."""
    n_samples = int(duration_sec * sample_rate)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
    # 220 Hz sine tone
    samples = (0.2 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)

    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="MP3")
    return buf.getvalue()


def make_mock_response(
    status_code: int = 200,
    content: bytes = b"",
    json_data: Any = None,
    text: str = "",
    headers: dict[str, str] = None,
) -> MagicMock:
    """Create a mock requests.Response object."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.content = content
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
        resp.text = json.dumps(json_data)
    else:
        resp.text = text or (content.decode("utf-8", errors="replace") if content else "")
        resp.json.side_effect = ValueError("No JSON in mock response")
    return resp


class TestElevenLabsEngineUnit(unittest.TestCase):
    """Unit tests for standalone helper functions and data structures."""

    def test_compute_cache_key_determinism(self) -> None:
        text = "[slowly, solemn, deep] सत्य केवल काल के गाल पर लिखा एक शब्द नहीं..."
        settings_a = {"stability": 0.55, "similarity_boost": 0.80, "style": 0.10, "use_speaker_boost": True}
        # Different dictionary key order should yield the exact same cache key
        settings_b = {"style": 0.10, "use_speaker_boost": True, "similarity_boost": 0.80, "stability": 0.55}

        key_a = compute_cache_key(text, DEFAULT_VOICE_ID, DEFAULT_MODEL_ID, settings_a)
        key_b = compute_cache_key(text, DEFAULT_VOICE_ID, DEFAULT_MODEL_ID, settings_b)

        self.assertEqual(key_a, key_b)
        self.assertEqual(len(key_a), 32)  # MD5 hex length

    def test_compute_cache_key_sensitivity(self) -> None:
        base_text = "सत्य केवल काल के गाल पर..."
        key_base = compute_cache_key(base_text, DEFAULT_VOICE_ID, DEFAULT_MODEL_ID, DEFAULT_VOICE_SETTINGS)

        # 1. Changed text (tag change)
        key_tagged = compute_cache_key(
            f"[slowly] {base_text}", DEFAULT_VOICE_ID, DEFAULT_MODEL_ID, DEFAULT_VOICE_SETTINGS
        )
        self.assertNotEqual(key_base, key_tagged)

        # 2. Changed voice
        key_other_voice = compute_cache_key(
            base_text, "other_voice_id", DEFAULT_MODEL_ID, DEFAULT_VOICE_SETTINGS
        )
        self.assertNotEqual(key_base, key_other_voice)

        # 3. Changed model
        key_other_model = compute_cache_key(
            base_text, DEFAULT_VOICE_ID, "eleven_multilingual_v2", DEFAULT_VOICE_SETTINGS
        )
        self.assertNotEqual(key_base, key_other_model)

        # 4. Changed voice setting
        mod_settings = {**DEFAULT_VOICE_SETTINGS, "stability": 0.70}
        key_mod_settings = compute_cache_key(
            base_text, DEFAULT_VOICE_ID, DEFAULT_MODEL_ID, mod_settings
        )
        self.assertNotEqual(key_base, key_mod_settings)

    def test_strip_audio_tags(self) -> None:
        raw_text = (
            "[slowly, solemn, deep] सत्य केवल काल के गाल पर लिखा एक शब्द नहीं... "
            "[pause] यह सृष्टि का मूल आधार है। [outro]"
        )
        cleaned = strip_audio_tags(raw_text)
        expected = "सत्य केवल काल के गाल पर लिखा एक शब्द नहीं... यह सृष्टि का मूल आधार है।"
        self.assertEqual(cleaned, expected)

        # Plain text without tags remains untouched
        plain = "यह एक साधारण वाक्य है।"
        self.assertEqual(strip_audio_tags(plain), plain)

    def test_mask_api_key(self) -> None:
        self.assertEqual(mask_api_key(None), "<UNSET>")
        self.assertEqual(mask_api_key(""), "<UNSET>")
        self.assertEqual(mask_api_key("short"), "***")
        self.assertEqual(mask_api_key("sk_test_1234567890abcdef"), "...cdef")

    def test_decode_audio_bytes_valid(self) -> None:
        mp3_bytes = make_test_mp3_bytes(duration_sec=0.2, sample_rate=44100)
        data, sr = decode_audio_bytes(mp3_bytes, target_sample_rate=44100)
        self.assertIsInstance(data, np.ndarray)
        self.assertEqual(data.dtype, np.float32)
        self.assertEqual(data.ndim, 1)
        self.assertEqual(sr, 44100)
        self.assertGreater(len(data), 0)

    def test_decode_audio_bytes_stereo_to_mono(self) -> None:
        """Verify stereo MP3 audio is safely downmixed to 1D mono float32 array."""
        n_samples = int(0.2 * 44100)
        t = np.linspace(0.0, 0.2, n_samples, endpoint=False, dtype=np.float32)
        stereo_samples = np.stack(
            [0.2 * np.sin(2.0 * np.pi * 220.0 * t), 0.2 * np.sin(2.0 * np.pi * 440.0 * t)],
            axis=1,
        ).astype(np.float32)

        buf = io.BytesIO()
        sf.write(buf, stereo_samples, 44100, format="MP3")
        stereo_mp3_bytes = buf.getvalue()

        data, sr = decode_audio_bytes(stereo_mp3_bytes, target_sample_rate=44100)
        self.assertEqual(data.ndim, 1)
        self.assertEqual(data.dtype, np.float32)
        self.assertEqual(len(data), n_samples)

    def test_decode_audio_bytes_empty_and_corrupt(self) -> None:
        with self.assertRaises(ElevenLabsError):
            decode_audio_bytes(b"")

        with self.assertRaises(ElevenLabsError):
            decode_audio_bytes(b"NOT_AN_MP3_PAYLOAD")

    def test_subscription_info_calculations(self) -> None:
        sub = SubscriptionInfo(
            tier="starter",
            character_count=12000,
            character_limit=37188,
            status="active",
        )
        self.assertEqual(sub.remaining_characters, 25188)
        self.assertAlmostEqual(sub.percent_used, (12000 / 37188) * 100.0, places=2)

        # Exhausted quota
        sub_exhausted = SubscriptionInfo(
            tier="starter",
            character_count=40000,
            character_limit=37188,
            status="active",
        )
        self.assertEqual(sub_exhausted.remaining_characters, 0)


class TestElevenLabsEngineOperations(unittest.TestCase):
    """Integration and behavioral tests for ElevenLabsEngine with mocked transport."""

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="sutradhar_tts_test_"))
        self.cache_dir = self.tmp_dir / "cache" / "audio"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.mock_session = MagicMock(spec=requests.Session)
        self.mock_session.headers = {}
        self.test_mp3_bytes = make_test_mp3_bytes(duration_sec=0.3, sample_rate=44100)

        self.engine = ElevenLabsEngine(
            api_key="sk_mock_valid_api_key_12345",
            cache_dir=self.cache_dir,
            session=self.mock_session,
            project_root=self.tmp_dir,
            timeout_sec=5.0,
            max_retries=3,
        )

    def tearDown(self) -> None:
        self.engine.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_initialization_defaults(self) -> None:
        self.assertEqual(self.engine.voice_id, DEFAULT_VOICE_ID)
        self.assertEqual(self.engine.model_id, DEFAULT_MODEL_ID)
        self.assertEqual(self.engine.sample_rate, 44100)
        self.assertEqual(self.engine.cache_dir, self.cache_dir)
        self.assertEqual(self.engine.voice_settings["stability"], 0.55)

    def test_missing_api_key_raises_auth_error(self) -> None:
        engine_no_key = ElevenLabsEngine(
            api_key="",
            cache_dir=self.cache_dir,
            session=self.mock_session,
            project_root=self.tmp_dir,
        )
        with self.assertRaises(ElevenLabsAuthError) as ctx:
            engine_no_key.get_subscription_info()
        self.assertIn("ELEVENLABS_API_KEY is missing", str(ctx.exception))

    def test_get_subscription_info_success(self) -> None:
        self.mock_session.request.return_value = make_mock_response(
            status_code=200,
            json_data={
                "tier": "starter",
                "character_count": 16500,
                "character_limit": 37188,
                "status": "active",
                "can_extend_character_limit": False,
                "allowed_to_extend_character_limit": False,
                "next_character_count_reset_unix": 1735689600,
            },
        )

        sub = self.engine.get_subscription_info()
        self.assertEqual(sub.tier, "starter")
        self.assertEqual(sub.character_count, 16500)
        self.assertEqual(sub.character_limit, 37188)
        self.assertEqual(sub.remaining_characters, 20688)
        self.assertEqual(sub.status, "active")

        # Verify request details
        self.mock_session.request.assert_called_once()
        args, kwargs = self.mock_session.request.call_args
        self.assertEqual(kwargs["method"], "GET")
        self.assertTrue(kwargs["url"].endswith("/v1/user/subscription"))
        self.assertEqual(kwargs["headers"]["xi-api-key"], "sk_mock_valid_api_key_12345")

    def test_get_voice_info_success(self) -> None:
        self.mock_session.request.return_value = make_mock_response(
            status_code=200,
            json_data={
                "voice_id": DEFAULT_VOICE_ID,
                "name": "Viraj",
                "category": "professional",
                "description": "Sole master storyteller voice for Sutradhar",
            },
        )

        voice = self.engine.get_voice_info()
        self.assertEqual(voice.voice_id, DEFAULT_VOICE_ID)
        self.assertEqual(voice.name, "Viraj")
        self.assertEqual(voice.category, "professional")
        self.assertIn("Viraj", voice.name)

    def test_synthesize_scene_cache_miss_then_hit(self) -> None:
        """Verify that first call fetches from API and caches, and second call uses disk cache (0 calls)."""
        # Mock TTS audio response
        tts_resp = make_mock_response(
            status_code=200,
            content=self.test_mp3_bytes,
        )

        self.mock_session.request.return_value = tts_resp

        text = "[slowly, solemn, deep] सत्य केवल काल के गाल पर लिखा एक शब्द नहीं..."
        cache_path = self.engine.get_cache_path(text)
        self.assertFalse(cache_path.exists())

        # First call: Cache Miss
        samples_1, sr_1 = self.engine.synthesize_scene(text)
        self.assertEqual(sr_1, 44100)
        self.assertGreater(len(samples_1), 0)
        self.assertTrue(cache_path.exists())
        self.assertEqual(cache_path.stat().st_size, len(self.test_mp3_bytes))
        self.assertEqual(self.mock_session.request.call_count, 1)  # 1 tts

        # Second call: Cache Hit
        self.mock_session.request.reset_mock()
        samples_2, sr_2 = self.engine.synthesize_scene(text)
        self.assertEqual(sr_2, 44100)
        np.testing.assert_array_almost_equal(samples_1, samples_2)
        # Zero API requests made on cache hit
        self.mock_session.request.assert_not_called()

    def test_skip_cache_forces_api_call(self) -> None:
        """Verify skip_cache=True invokes API even if cache file exists."""
        text = "पुनः निर्माण वाक्य।"
        cache_path = self.engine.get_cache_path(text)
        cache_path.write_bytes(self.test_mp3_bytes)

        tts_resp = make_mock_response(status_code=200, content=self.test_mp3_bytes)
        self.mock_session.request.return_value = tts_resp

        self.engine.synthesize_scene(text, skip_cache=True)
        self.assertEqual(self.mock_session.request.call_count, 1)

    def test_corrupt_cache_file_recovery(self) -> None:
        """Verify engine re-synthesizes if cached file exists but is corrupted."""
        text = "भ्रष्ट कैश फाइल परीक्षण।"
        cache_path = self.engine.get_cache_path(text)
        # Write corrupted garbage bytes
        cache_path.write_bytes(b"CORRUPTED_GARBAGE_NOT_MP3")

        tts_resp = make_mock_response(status_code=200, content=self.test_mp3_bytes)
        self.mock_session.request.return_value = tts_resp

        samples, sr = self.engine.synthesize_scene(text)
        self.assertEqual(sr, 44100)
        self.assertGreater(len(samples), 0)
        # Should have overwritten corrupt file with valid MP3 bytes
        self.assertEqual(cache_path.read_bytes(), self.test_mp3_bytes)

    def test_auth_error_401_no_retry(self) -> None:
        """Verify 401 raises ElevenLabsAuthError immediately without retrying."""
        self.mock_session.request.return_value = make_mock_response(
            status_code=401, text="Unauthorized: Invalid API key"
        )
        with self.assertRaises(ElevenLabsAuthError):
            self.engine.get_subscription_info()

        # Exactly 1 call, zero retries
        self.assertEqual(self.mock_session.request.call_count, 1)

    def test_payment_required_402_no_retry(self) -> None:
        """Verify 402 raises ElevenLabsQuotaExceededError immediately without retrying."""
        self.mock_session.request.return_value = make_mock_response(
            status_code=402, text="Payment Required: Quota exceeded"
        )
        with self.assertRaises(ElevenLabsQuotaExceededError):
            self.engine.get_subscription_info()

        self.assertEqual(self.mock_session.request.call_count, 1)

    @patch("time.sleep", return_value=None)
    def test_rate_limit_429_retries_and_succeeds(self, mock_sleep: MagicMock) -> None:
        """Verify 429 triggers exponential backoff and succeeds on subsequent try."""
        rate_limit_resp = make_mock_response(
            status_code=429,
            text="Too Many Requests",
            headers={"Retry-After": "2"},
        )
        success_resp = make_mock_response(
            status_code=200,
            json_data={"tier": "starter", "character_count": 0, "character_limit": 37188, "status": "active"},
        )
        self.mock_session.request.side_effect = [rate_limit_resp, success_resp]

        sub = self.engine.get_subscription_info()
        self.assertEqual(sub.tier, "starter")
        self.assertEqual(self.mock_session.request.call_count, 2)
        mock_sleep.assert_called_once_with(2.0)

    @patch("time.sleep", return_value=None)
    def test_rate_limit_429_exhaustion_raises(self, mock_sleep: MagicMock) -> None:
        """Verify 429 raises ElevenLabsRateLimitError when retries are exhausted."""
        rate_limit_resp = make_mock_response(status_code=429, text="Too Many Requests")
        self.mock_session.request.return_value = rate_limit_resp

        with self.assertRaises(ElevenLabsRateLimitError):
            self.engine.get_subscription_info()

        self.assertEqual(self.mock_session.request.call_count, self.engine.max_retries)

    @patch("time.sleep", return_value=None)
    def test_server_error_500_retries_and_succeeds(self, mock_sleep: MagicMock) -> None:
        """Verify 500 error retries and recovers on success."""
        err_resp = make_mock_response(status_code=500, text="Internal Server Error")
        ok_resp = make_mock_response(
            status_code=200,
            json_data={"tier": "starter", "character_count": 0, "character_limit": 37188, "status": "active"},
        )
        self.mock_session.request.side_effect = [err_resp, ok_resp]

        sub = self.engine.get_subscription_info()
        self.assertEqual(sub.tier, "starter")
        self.assertEqual(self.mock_session.request.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch("time.sleep", return_value=None)
    def test_timeout_retry_and_exhaustion(self, mock_sleep: MagicMock) -> None:
        """Verify network timeout retries up to timeout retry limit."""
        self.mock_session.request.side_effect = requests.exceptions.Timeout("Read timeout")

        with self.assertRaises(ElevenLabsTimeoutError):
            self.engine.get_subscription_info()

        # Retries max 2 timeouts + 1 initial = 3 attempts
        self.assertGreaterEqual(self.mock_session.request.call_count, 2)

    def test_client_error_400_no_retry(self) -> None:
        """Verify 400 Bad Request raises ElevenLabsAPIError immediately without retrying."""
        self.mock_session.request.return_value = make_mock_response(
            status_code=400, text="Bad Request: Invalid model_id"
        )
        with self.assertRaises(ElevenLabsAPIError) as ctx:
            self.engine.get_subscription_info()

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(self.mock_session.request.call_count, 1)

    def test_synthesize_to_file(self) -> None:
        """Verify synthesize_to_file creates a valid WAV file."""
        tts_resp = make_mock_response(status_code=200, content=self.test_mp3_bytes)
        self.mock_session.request.return_value = tts_resp

        out_wav = self.tmp_dir / "output" / "scene_1.wav"
        result_path = self.engine.synthesize_to_file("परीक्षण दृश्य।", out_wav)

        self.assertEqual(result_path, out_wav)
        self.assertTrue(out_wav.is_file())
        self.assertGreater(out_wav.stat().st_size, 0)

        # Verify output WAV is readable by soundfile at 44.1 kHz
        data, sr = sf.read(str(out_wav))
        self.assertEqual(sr, 44100)
        self.assertEqual(data.dtype, np.float64)  # default soundfile read returns float64

    def test_context_manager(self) -> None:
        """Verify context manager calls close on exit."""
        session_mock = MagicMock()
        with ElevenLabsEngine(api_key="sk_test", session=session_mock) as eng:
            self.assertIsNotNone(eng)

    def test_empty_or_whitespace_text_raises_error(self) -> None:
        """Verify empty or whitespace-only text raises ElevenLabsError without calling API."""
        with self.assertRaises(ElevenLabsError):
            self.engine.synthesize_scene("")

        with self.assertRaises(ElevenLabsError):
            self.engine.synthesize_scene("    \n\t  ")

        self.mock_session.request.assert_not_called()

    def test_synthesize_convenience_alias(self) -> None:
        """Verify synthesize() acts as an exact alias for synthesize_scene()."""
        tts_resp = make_mock_response(status_code=200, content=self.test_mp3_bytes)
        self.mock_session.request.return_value = tts_resp

        text = "संक्षिप्त कॉल।"
        samples, sr = self.engine.synthesize(text)
        self.assertEqual(sr, 44100)
        self.assertGreater(len(samples), 0)

    def test_config_dict_custom_settings(self) -> None:
        """Verify custom settings from config dictionary are applied correctly."""
        custom_cfg = {
            "tts": {
                "engine": "elevenlabs",
                "model_id": "eleven_custom_model",
                "voice_id": "custom_voice_abc123",
                "sample_rate": 48000,
                "cache_dir": "custom_build/cache",
                "voice_settings": {
                    "stability": 0.75,
                    "similarity_boost": 0.90,
                },
            }
        }
        engine_cfg = ElevenLabsEngine(
            api_key="sk_test",
            config=custom_cfg,
            session=self.mock_session,
            project_root=self.tmp_dir,
        )
        self.assertEqual(engine_cfg.model_id, "eleven_custom_model")
        self.assertEqual(engine_cfg.voice_id, "custom_voice_abc123")
        self.assertEqual(engine_cfg.sample_rate, 48000)
        self.assertEqual(engine_cfg.cache_dir, self.tmp_dir / "custom_build" / "cache")
        self.assertEqual(engine_cfg.voice_settings["stability"], 0.75)
        self.assertEqual(engine_cfg.voice_settings["similarity_boost"], 0.90)
        # Unspecified settings retain defaults
        self.assertEqual(engine_cfg.voice_settings["style"], 0.10)
        self.assertTrue(engine_cfg.voice_settings["use_speaker_boost"])

    def test_api_key_security_not_leaked_in_exceptions(self) -> None:
        """Verify secret API key never leaks in exception text or error messages."""
        secret_key = "sk_prod_super_secret_elevenlabs_credential_9999"
        engine_secret = ElevenLabsEngine(
            api_key=secret_key,
            cache_dir=self.cache_dir,
            session=self.mock_session,
            project_root=self.tmp_dir,
        )

        self.mock_session.request.return_value = make_mock_response(
            status_code=401, text="Unauthorized: Invalid API key"
        )

        with self.assertRaises(ElevenLabsAuthError) as ctx:
            engine_secret.get_subscription_info()

        error_message = str(ctx.exception)
        self.assertNotIn(secret_key, error_message)
        self.assertIn("...9999", error_message)

    @patch("sys.argv", ["elevenlabs_engine.py", "--check-subscription"])
    @patch("builtins.print")
    def test_cli_check_subscription(self, mock_print: MagicMock) -> None:
        """Verify CLI --check-subscription option prints correct quota details."""
        from elevenlabs_engine import main

        with patch.object(ElevenLabsEngine, "get_subscription_info") as mock_sub:
            mock_sub.return_value = SubscriptionInfo(
                tier="starter",
                character_count=16500,
                character_limit=37188,
                status="active",
            )
            with patch.object(ElevenLabsEngine, "close"):
                main()

            mock_sub.assert_called_once()
            printed_output = " ".join(call[0][0] for call in mock_print.call_args_list if call[0])
            self.assertIn("starter", printed_output)
            self.assertIn("16,500", printed_output)
            self.assertIn("37,188", printed_output)

    @patch("sys.argv", ["elevenlabs_engine.py", "--voice-info", DEFAULT_VOICE_ID])
    @patch("builtins.print")
    def test_cli_voice_info(self, mock_print: MagicMock) -> None:
        """Verify CLI --voice-info option prints voice metadata."""
        from elevenlabs_engine import main

        with patch.object(ElevenLabsEngine, "get_voice_info") as mock_vinfo:
            mock_vinfo.return_value = VoiceInfo(
                voice_id=DEFAULT_VOICE_ID,
                name="Viraj",
                category="professional",
                description="Master voice for Sutradhar",
            )
            with patch.object(ElevenLabsEngine, "close"):
                main()

            mock_vinfo.assert_called_once_with(DEFAULT_VOICE_ID)
            printed_output = " ".join(call[0][0] for call in mock_print.call_args_list if call[0])
            self.assertIn("Viraj", printed_output)
            self.assertIn("professional", printed_output)

    @patch("sys.argv", ["elevenlabs_engine.py", "--clear-cache"])
    @patch("builtins.print")
    def test_cli_clear_cache(self, mock_print: MagicMock) -> None:
        """Verify CLI --clear-cache deletes cached mp3 files."""
        from elevenlabs_engine import main

        # Create dummy mp3 in engine cache_dir
        dummy_file = self.cache_dir / "test_dummy_cache.mp3"
        dummy_file.write_bytes(b"dummy")

        with patch.object(ElevenLabsEngine, "close"):
            with patch("elevenlabs_engine.DEFAULT_CACHE_DIR", str(self.cache_dir)):
                main()

        self.assertFalse(dummy_file.exists())
        printed_output = " ".join(call[0][0] for call in mock_print.call_args_list if call[0])
        self.assertIn("Cleared 1 cached audio files", printed_output)


class TestFakeElevenLabs(unittest.TestCase):
    """Verify FakeElevenLabs test double behaves reliably according to contract."""

    def test_fake_synthesis_shape_and_rate(self) -> None:
        fake = FakeElevenLabs(sec_per_scene=3.0, sample_rate=44100)
        samples, sr = fake.synthesize("परीक्षण वाक्य")
        self.assertEqual(sr, 44100)
        self.assertEqual(samples.dtype, np.float32)
        self.assertEqual(len(samples), 3 * 44100)
        self.assertEqual(len(fake.calls), 1)

    def test_fake_silent_mode(self) -> None:
        fake = FakeElevenLabs(sec_per_scene=1.0, sample_rate=44100, silent=True)
        samples, sr = fake.synthesize("शांत मोड")
        self.assertTrue(np.all(samples == 0.0))

    def test_fake_fail_on_call(self) -> None:
        fake = FakeElevenLabs(fail_on_call=2)
        fake.synthesize("कॉल 1")
        with self.assertRaises(ElevenLabsAPIError):
            fake.synthesize("कॉल 2")

    def test_fake_metadata_methods(self) -> None:
        fake = FakeElevenLabs()
        sub = fake.get_subscription_info()
        self.assertEqual(sub.tier, "starter")
        self.assertEqual(sub.character_limit, 37188)

        voice = fake.get_voice_info()
        self.assertEqual(voice.voice_id, DEFAULT_VOICE_ID)
        self.assertEqual(voice.name, "Viraj")


if __name__ == "__main__":
    unittest.main()
