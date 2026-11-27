"""Comprehensive unit and offline integration tests for Phase 3 (`sutradhar.audio`)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_audio  # noqa: E402
from sutradhar.audio.caption_builder import (  # noqa: E402
    build_caption_cues,
    extract_subtokens,
    is_keyword_token,
    write_captions_data_js,
)
from sutradhar.audio.elevenlabs_tts import (  # noqa: E402
    DEFAULT_TAG_TEMPLATES,
    FakeElevenLabs,
    TTSBudgetError,
    apply_pronunciations_preserving_tags,
    compute_scene_sha256,
    get_monthly_tts_usage,
    load_pronunciations,
    record_audio_ledger,
    resolve_scene_tag,
    strip_audio_tags,
    validate_pre_tts_budget,
)
from sutradhar.audio.sound_mixer import (  # noqa: E402
    AudioMixError,
    collect_sfx_schedule,
    detect_sfx_peak_offset,
    measure_integrated_lufs,
    mix_episode_audio,
    parse_bgm_schedule,
    resolve_bgm_path,
)
from sutradhar.audio.whisper_aligner import (  # noqa: E402
    _tokens_match,
    align_narration_words,
    detect_speech_bursts,
    indic_phonetic_skeleton,
    load_16k_mono_array,
    norm_indic_token,
    resample_to_16k_mono,
)
from sutradhar.config import load_config  # noqa: E402
from sutradhar.db import cmd_context, cmd_init  # noqa: E402


class _FakeWord:
    def __init__(self, word: str, start: float, end: float) -> None:
        self.word = word
        self.start = start
        self.end = end


class _FakeSegment:
    def __init__(self, words: list[_FakeWord]) -> None:
        self.words = words


class _FakeWhisper:
    def transcribe(
        self,
        audio_input: Any,
        language: str = "hi",
        word_timestamps: bool = True,
        initial_prompt: str = "",
        **kwargs: Any,
    ) -> tuple[list[_FakeSegment], dict[str, Any]]:
        tokens = (initial_prompt or "").split()
        step = 7.0 / max(1, len(tokens))
        words = [_FakeWord(tok, i * step, (i + 0.85) * step) for i, tok in enumerate(tokens)]
        return [_FakeSegment(words)], {"language": language}


def _make_hindi_plan(scene_texts: list[str]) -> dict[str, Any]:
    scenes = []
    for idx, txt in enumerate(scene_texts, 1):
        scenes.append(
            {
                "scene_index": idx,
                "narration_text": txt,
                "visual_mode": "character_drama",
                "backdrop_rig": "kailash_horizon",
                "primary_character": "shiva",
                "mood_palette": "kailash_himalayan",
                "particle_theme": "himalayan_snow",
                "camera_motion": "slow_push",
                "speaker_role": "narrator",
                "emotion": "calm",
                "visual_spec": {
                    "atmosphere_mode": "dawn_epic",
                    "environment_preset": "kailash_horizon",
                    "horizon_y": 1142,
                    "camera_move": "push_slow",
                    "transition_in": "fade",
                    "bgm_mood": "dramatic",
                    "props": (
                        [{"id": "samudra_manthan_halahala", "kind": "halahala_orb", "mount": "terrain", "x": 540.0}]
                        if idx == 1
                        else []
                    ),
                    "characters": [{"id": "shiva", "role": "protagonist", "x": 540.0}],
                },
            }
        )
    return {
        "content_format": "standalone",
        "series_id": None,
        "series_title": None,
        "episode_number_in_series": None,
        "total_planned_episodes": None,
        "global_episode_number": 99,
        "pillar": "Ancient Epics & Lore",
        "tts_voice": "uuyFQegRan8rpIQCGu9K",
        "bgm_track": "dramatic_mythology.mp3",
        "bespoke_asset_path": "canvas_prop:samudra_manthan_halahala",
        "youtube_title": "Why Shiva Held Cosmic Poison #Shorts",
        "youtube_description": "Pure English description for Samudra Manthan episode. #Shorts",
        "summary": "Standalone English summary without cliffhangers.",
        "language": "hi",
        "audio_language": "hi",
        "caption_language": "hi",
        "metadata_language": "en",
        "thumbnail_language": "en",
        "scenes": scenes,
    }


def _write_two_burst_wav(path: Path, sr: int = 44100) -> None:
    """Create a 6.0s WAV with two active speech bursts separated by a 2.0s silence gap."""
    t1 = np.linspace(0.0, 1.5, int(1.5 * sr), endpoint=False, dtype=np.float32)
    b1 = (0.3 * np.sin(2.0 * np.pi * 220.0 * t1)).astype(np.float32)
    gap = np.zeros(int(2.0 * sr), dtype=np.float32)
    t2 = np.linspace(0.0, 1.65, int(1.65 * sr), endpoint=False, dtype=np.float32)
    b2 = (0.3 * np.sin(2.0 * np.pi * 260.0 * t2)).astype(np.float32)
    tail = np.zeros(int(0.85 * sr), dtype=np.float32)
    audio = np.concatenate([np.zeros(int(0.05 * sr), dtype=np.float32), b1, gap, b2, tail])
    sf.write(str(path), audio, sr, subtype="PCM_16")


class TestPhase3AudioPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = load_config(REPO_ROOT)

    def test_01_budget_abort_gt_900_and_devanagari_guard_zero_tts_calls(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copy2(REPO_ROOT / "config.yaml", root / "config.yaml")
            shutil.copy2(REPO_ROOT / "pronunciations_hi.yaml", root / "pronunciations_hi.yaml")
            (root / "build").mkdir(parents=True, exist_ok=True)

            # Build Hindi plan exceeding 900 billed chars (~1050 chars)
            long_line = "[slowly, solemn, deep] अमृत के लिए देव और असुरों ने सागर मथा और भयानक हलाहल निकला। [pause] ब्रह्मांड जलने लगा था और सभी भयभीत थे।"
            plan = _make_hindi_plan([long_line for _ in range(8)])
            (root / "build" / "episode_plan.json").write_text(
                json.dumps(plan, ensure_ascii=False), encoding="utf-8"
            )

            fake_tts = FakeElevenLabs(sec_per_scene=9.0)
            with self.assertRaises(build_audio.AudioBuildError) as ctx:
                build_audio.build_episode_audio(
                    root,
                    tts_factory=lambda c, r: fake_tts,
                    whisper_factory=lambda c: _FakeWhisper(),
                    strict_budget=True,
                )
            self.assertIn("900", str(ctx.exception))
            self.assertEqual(len(fake_tts.calls), 0, "FakeElevenLabs must NOT be called on >900 char abort")

            # Also verify <70% Devanagari guard aborts BEFORE any TTS call
            with self.assertRaises(TTSBudgetError):
                validate_pre_tts_budget(
                    ["[slowly] This is mostly English text with one देव word."],
                    ["This is mostly English text with one देव word."],
                    language="hi",
                )

    def test_02_pause_tag_preservation_pronunciations_and_neutral_fallback(self) -> None:
        reps = load_pronunciations(REPO_ROOT, self.cfg, lang="hi")
        src = "[slowly, solemn, deep] ब्रह्मांड और अहंकार का अंत स्वयं शिव करते हैं। [pause] सृष्टि शांत हुई।"
        phonetic = apply_pronunciations_preserving_tags(src, reps)

        self.assertIn("[slowly, solemn, deep]", phonetic)
        self.assertIn("[pause]", phonetic)
        self.assertIn("ब्रह्माण्ड", phonetic)
        self.assertIn("अहङ्कार", phonetic)
        self.assertIn("स्वयम्", phonetic)

        clean = strip_audio_tags(phonetic)
        self.assertNotIn("[", clean)
        self.assertNotIn("]", clean)
        self.assertIn("सृष्टि शांत हुई।", clean)

        # Verify neutral fallback replaced old antagonist fallback in resolve_scene_tag
        class _GenericDialogue:
            narration_text = "कहानी आगे बढ़ती है।"
            speaker_role = "character_dialogue"
            emotion = "neutral"
            primary_character = "citizen"
            shot_type = "medium"

        tag = resolve_scene_tag(_GenericDialogue(), 2, 5, DEFAULT_TAG_TEMPLATES, False)
        self.assertEqual(tag, DEFAULT_TAG_TEMPLATES["narrator"])
        self.assertNotEqual(tag, DEFAULT_TAG_TEMPLATES["antagonist"])

        # End-to-end build preserves [pause] in TTS input and removes it from captions/manifest
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copy2(REPO_ROOT / "config.yaml", root / "config.yaml")
            shutil.copy2(REPO_ROOT / "pronunciations_hi.yaml", root / "pronunciations_hi.yaml")
            (root / "build").mkdir(parents=True, exist_ok=True)
            lines = [
                "[slowly, solemn, deep] अमृत के लिए सागर मथा। [pause] पर पहले विष निकला!",
                "[calm, serene] देवता भयभीत हो भागे। [pause] कोई रक्षक न बचा।",
                "[solemn] तब आशा बची—कैलाश के महादेव। [pause] देव शरण में गए।",
                "[calm] शिव ने कहा मैं विष पिऊँगा। [pause] करुणा से हृदय भरा।",
                "[gentle, peaceful] शिव कहलाए—नीलकंठ! [pause] जगत की पीड़ा थाम ली।",
            ]
            (root / "build" / "episode_plan.json").write_text(
                json.dumps(_make_hindi_plan(lines), ensure_ascii=False), encoding="utf-8"
            )
            fake_tts = FakeElevenLabs(sec_per_scene=9.0)
            res = build_audio.build_episode_audio(
                root,
                tts_factory=lambda c, r: fake_tts,
                whisper_factory=lambda c: _FakeWhisper(),
                strict_budget=True,
            )
            self.assertEqual(res["status"], "ok")
            self.assertIn("[pause]", fake_tts.calls[0]["text"])
            man = json.loads((root / "build" / "audio" / "audio_manifest.json").read_text(encoding="utf-8"))
            for sc in man["scenes"]:
                self.assertNotIn("[pause]", sc["narration_text"])
                self.assertIn("[pause]", sc["tts_text_applied"])

    def test_03_temp_db_audio_ledger_and_cache_hit_accounting(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copy2(REPO_ROOT / "config.yaml", root / "config.yaml")
            (root / "assets").mkdir()
            cmd_init(root, self.cfg)
            db_path = root / "episodes.db"

            k1 = compute_scene_sha256("[slowly] दृश्य एक", "uuyFQegRan8rpIQCGu9K", "eleven_v4", {"speed": 0.9})
            k2 = compute_scene_sha256("[calm] दृश्य दो", "uuyFQegRan8rpIQCGu9K", "eleven_v4", {"speed": 0.9})
            self.assertEqual(len(k1), 64)

            record_audio_ledger(db_path, scene_index=1, sha256_key=k1, billed_chars=120, cache_hit=False)
            record_audio_ledger(db_path, scene_index=2, sha256_key=k2, billed_chars=110, cache_hit=False)
            # Re-run / single-scene revision: scene 1 hits cache (0 credits spent), scene 2 regenerated
            record_audio_ledger(db_path, scene_index=1, sha256_key=k1, billed_chars=120, cache_hit=True)
            record_audio_ledger(db_path, scene_index=2, sha256_key=k2 + "_rev", billed_chars=105, cache_hit=False)

            usage = get_monthly_tts_usage(db_path, monthly_limit=30000)
            self.assertEqual(usage["spent_chars"], 335)  # 120 + 110 + 105 (cache_hit=True excluded!)
            self.assertEqual(usage["cache_hits"], 1)
            self.assertEqual(usage["remaining_credits"], 29665)

            ctx = cmd_context(root, self.cfg)
            self.assertEqual(ctx["monthly_tts_budget"]["spent_this_month_billed_chars"], 335)
            self.assertEqual(ctx["monthly_tts_budget"]["cache_hits_this_month"], 1)

    def test_04_em_dash_tokenization_dynamic_keywords_and_non_overlap(self) -> None:
        self.assertEqual(extract_subtokens("बची—कैलाश"), ["बची", "कैलाश"])
        self.assertEqual(extract_subtokens("कहलाए—नीलकंठ!"), ["कहलाए", "नीलकंठ"])
        self.assertEqual(extract_subtokens("सूर्य/चंद्र-गति"), ["सूर्य", "चंद्र", "गति"])

        # Parameterized keywords without Episode 1 Ravana bias
        self.assertTrue(is_keyword_token("बची—कैलाश", keywords={"कैलाश"}))
        self.assertTrue(is_keyword_token("कहलाए—नीलकंठ!", keywords={"नीलकंठ"}))
        self.assertTrue(is_keyword_token("महाविष", keyword_patterns=[r"विष"]))
        self.assertFalse(is_keyword_token("रावण", keywords={"कैलाश", "नीलकंठ"}))

        scenes = [
            {
                "scene_index": 1,
                "emphasis_word": "कैलाश",
                "words": [
                    {"word": "तब", "global_start": 0.1, "global_end": 0.4},
                    {"word": "आशा", "global_start": 0.4, "global_end": 0.8},
                    {"word": "बची—कैलाश", "global_start": 0.8, "global_end": 1.6},
                    {"word": "के", "global_start": 1.6, "global_end": 1.8},
                    {"word": "महादेव।", "global_start": 1.8, "global_end": 2.4},
                ],
            },
            {
                "scene_index": 2,
                "emphasis_word": "नीलकंठ",
                "words": [
                    {"word": "और", "global_start": 2.8, "global_end": 3.1},
                    {"word": "शिव", "global_start": 3.1, "global_end": 3.6},
                    {"word": "कहलाए—नीलकंठ!", "global_start": 3.6, "global_end": 4.9},
                ],
            },
        ]
        cues = build_caption_cues(scenes, total_duration=5.8)
        self.assertGreaterEqual(len(cues), 2)
        for i, cue in enumerate(cues):
            self.assertTrue(1 <= len(cue["words"]) <= 4)
            self.assertIn("id", cue)
            self.assertIn("scene", cue)
            self.assertLess(cue["start"], cue["end"])
            if i + 1 < len(cues):
                self.assertLessEqual(cue["end"], round(cues[i + 1]["start"] - 0.03, 3) + 1e-6)
            for wo in cue["words"]:
                self.assertIn("text", wo)
                self.assertIn("global_start", wo)
                self.assertIn("global_end", wo)
                self.assertIn("kw", wo)

        kw_map = {wo["text"]: wo["kw"] for cue in cues for wo in cue["words"]}
        self.assertTrue(kw_map["बची—कैलाश"])
        self.assertTrue(kw_map["कहलाए—नीलकंठ!"])

        with tempfile.TemporaryDirectory() as td:
            js_path = Path(td) / "captions_data.js"
            write_captions_data_js(cues, js_path)
            self.assertIn("window.CAPTIONS_DATA =", js_path.read_text(encoding="utf-8"))

    def test_05_whisper_16k_resample_cross_script_and_rms_pause_snap(self) -> None:
        self.assertEqual(norm_indic_token("अहंकार"), norm_indic_token("अहङ्कार"))
        self.assertEqual(indic_phonetic_skeleton("शंकर"), indic_phonetic_skeleton("شنکر"))
        matched_mh, score_mh = _tokens_match("महादेव", "محادیو")
        self.assertTrue(matched_mh)
        self.assertGreaterEqual(score_mh, 0.85)
        matched, score = _tokens_match("ब्रह्मांड", "برماند")
        self.assertTrue(matched)
        self.assertGreaterEqual(score, 0.85)

        with tempfile.TemporaryDirectory() as td:
            src_wav = Path(td) / "two_bursts.wav"
            dst_16k = Path(td) / "two_bursts_16k.wav"
            _write_two_burst_wav(src_wav, sr=44100)
            resample_to_16k_mono(src_wav, dst_16k)

            info = sf.info(str(dst_16k))
            self.assertEqual(info.samplerate, 16000)
            self.assertEqual(info.channels, 1)
            self.assertEqual(info.subtype, "PCM_16")

            arr = load_16k_mono_array(src_wav)
            self.assertEqual(arr.dtype, np.float32)
            self.assertEqual(arr.ndim, 1)

            bursts = detect_speech_bursts(src_wav)
            self.assertEqual(len(bursts), 2)

            # Simulate Whisper missing middle words across the 2.0s pause: RMS snapping must prevent >1.5s stretch
            text = "पृथ्वी पर राजा लौटे। देवी रेवती का विवाह हुआ।"
            sparse_whisper = [
                {"word": "पृथ्वी", "start": 0.08, "end": 0.45},
                {"word": "रेवती", "start": 3.85, "end": 4.30},
                {"word": "हुआ।", "start": 4.80, "end": 5.15},
            ]
            aligned, _ = align_narration_words(
                narration_text=text,
                whisper_words=sparse_whisper,
                scene_duration=6.0,
                global_offset=0.0,
                wav_path=src_wav,
            )
            max_word_dur = max(w["end"] - w["start"] for w in aligned)
            self.assertLessEqual(max_word_dur, 1.5, f"Word stretched across pause: {max_word_dur:.2f}s")

    def test_06_sound_mixer_no_synth_fallback_peak_preroll_and_ebur128(self) -> None:
        # 1. Missing BGM track must fail cleanly when allow_synth_fallback=False
        with self.assertRaises(AudioMixError):
            resolve_bgm_path(REPO_ROOT, "does_not_exist.mp3", self.cfg, allow_synth_fallback=False)

        # 2. Check peak offset & negative pre-roll on whoosh-cinematic.mp3 and zero orphan cues
        sfx_manifest = {
            "audio": {"total_duration_sec": 12.0},
            "scenes": [
                {
                    "scene_index": 1,
                    "start_sec": 0.0,
                    "end_sec": 5.0,
                    "visual_spec": {
                        "transition_sfx": None,
                        "props": [{"id": "kalash", "kind": "kalash"}],  # no sfx -> zero orphan pops
                    },
                },
                {
                    "scene_index": 2,
                    "start_sec": 5.0,
                    "end_sec": 12.0,
                    "visual_spec": {"transition_sfx": "whoosh-cinematic.mp3", "props": []},
                    "sfx_events": [],
                },
            ],
        }
        cues = collect_sfx_schedule(REPO_ROOT, sfx_manifest)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0]["sfx"], "whoosh-cinematic.mp3")
        peak_off = detect_sfx_peak_offset(REPO_ROOT / "assets" / "audio" / "sfx" / "whoosh-cinematic.mp3")
        self.assertGreater(peak_off, 1.5)
        self.assertAlmostEqual(cues[0]["start_sec"], 5.0 + 0.033 - peak_off, places=2)

        # 3. Loudness-matched multi-act mix (-17 LUFS Wikimedia + -44 LUFS repo bed) -> single 2-pass loudnorm
        lufs_veena = measure_integrated_lufs(REPO_ROOT / "assets" / "audio" / "bgm" / "veena_devotional_serene.mp3")
        lufs_myth = measure_integrated_lufs(REPO_ROOT / "assets" / "audio" / "bgm" / "dramatic_mythology.mp3")
        self.assertGreater(abs(lufs_veena - lufs_myth), 18.0)

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            narr_wav = td_p / "narr.wav"
            _write_two_burst_wav(narr_wav, sr=44100)  # 6.0s w/ 0.85s quiet tail
            out_mix = td_p / "master_mix.wav"
            mix_manifest = {
                "audio": {"narration_full_path": str(narr_wav), "total_duration_sec": 6.0},
                "bgm_cues": [
                    {"track": "dramatic_mythology.mp3", "start_sec": 0.0, "end_sec": 3.0},
                    {"track": "veena_devotional_serene.mp3", "start_sec": 3.0, "end_sec": 6.0},
                ],
                "scenes": [
                    {"scene_index": 1, "start_sec": 0.0, "end_sec": 3.0, "visual_spec": {"props": []}},
                    {
                        "scene_index": 2,
                        "start_sec": 3.0,
                        "end_sec": 6.0,
                        "visual_spec": {"transition_sfx": "whoosh-short.mp3", "props": []},
                    },
                ],
            }
            schedule = parse_bgm_schedule(REPO_ROOT, mix_manifest, self.cfg)
            self.assertEqual(len(schedule), 2)

            result = mix_episode_audio(
                REPO_ROOT,
                mix_manifest,
                self.cfg,
                narration_path=narr_wav,
                output_wav_path=out_mix,
                allow_synth_fallback=False,
            )
            self.assertEqual(result["sample_rate"], 48000)
            self.assertEqual(result["channels"], 2)
            self.assertAlmostEqual(result["integrated_lufs"], -14.0, delta=0.5)
            self.assertLessEqual(result["true_peak_dbtp"], -1.5)
            tail_silences = [s for s in result["silences"] if s["end"] >= 5.8]
            self.assertTrue(tail_silences and tail_silences[-1]["duration"] >= 0.7)


if __name__ == "__main__":
    unittest.main()
