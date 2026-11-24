"""Unit & integration test suite for Sutradhar Akshara Lip-Sync Engine (v4.0).

Verifies:
1. Devanagari Akshara parser decomposition across diverse phonetic structures.
2. Accurate mapping to the 5 SVG puppet mouth visemes:
   - mouth_calm, mouth_talk, mouth_shout, mouth_fear, mouth_joy
3. Theatrical emotion modulations (wrath, fear, joy, calm).
4. Proportional duration allocation and silence gap filling.
5. Deterministic GSAP 3 JavaScript lip-sync driver generation.
"""

from __future__ import annotations

import unittest

from scripts.engine.config import (
    ALL_MOUTH_STATES,
    MOUTH_CALM,
    MOUTH_FEAR,
    MOUTH_JOY,
    MOUTH_SHOUT,
    MOUTH_TALK,
)
from scripts.engine.lipsync_engine import (
    build_lipsync_timeline,
    generate_gsap_lipsync,
    parse_hindi_aksharas,
    resolve_akshara_viseme,
)


class TestAksharaParser(unittest.TestCase):
    """Tests orthographic syllable decomposition of Hindi Devanagari words."""

    def test_simple_words(self) -> None:
        aksharas = parse_hindi_aksharas("रावण")
        self.assertEqual(len(aksharas), 3)
        self.assertEqual(aksharas[0].syllable, "रा")
        self.assertEqual(aksharas[1].syllable, "व")
        self.assertEqual(aksharas[2].syllable, "ण")

    def test_conjunct_consonants_with_halant(self) -> None:
        # 'कृष्ण' -> 'कृ', 'ष्ण'
        aksharas = parse_hindi_aksharas("कृष्ण")
        self.assertEqual(len(aksharas), 2)
        self.assertEqual(aksharas[0].syllable, "कृ")
        self.assertEqual(aksharas[1].syllable, "ष्ण")

        # 'ब्रह्मांड' -> 'ब्र', 'ह्मां', 'ड'
        aksharas_brahmand = parse_hindi_aksharas("ब्रह्मांड")
        self.assertEqual(len(aksharas_brahmand), 3)
        self.assertEqual(aksharas_brahmand[0].syllable, "ब्र")
        self.assertEqual(aksharas_brahmand[1].syllable, "ह्मां")
        self.assertEqual(aksharas_brahmand[2].syllable, "ड")

        # 'प्रणाम' -> 'प्र', 'णा', 'म'
        aksharas_pranam = parse_hindi_aksharas("प्रणाम")
        self.assertEqual(len(aksharas_pranam), 3)
        self.assertEqual(aksharas_pranam[0].syllable, "प्र")
        self.assertEqual(aksharas_pranam[1].syllable, "णा")
        self.assertEqual(aksharas_pranam[2].syllable, "म")

    def test_independent_vowels(self) -> None:
        # 'अमर' -> 'अ', 'म', 'र'
        aksharas = parse_hindi_aksharas("अमर")
        self.assertEqual(len(aksharas), 3)
        self.assertEqual(aksharas[0].syllable, "अ")
        self.assertEqual(aksharas[1].syllable, "म")
        self.assertEqual(aksharas[2].syllable, "र")

    def test_empty_and_whitespace_input(self) -> None:
        self.assertEqual(parse_hindi_aksharas(""), [])
        self.assertEqual(parse_hindi_aksharas("   "), [])


class TestVisemeResolutionAndEmotion(unittest.TestCase):
    """Tests phonetic viseme mapping to the 5 SVG mouth states."""

    def test_bilabial_consonant_closure(self) -> None:
        # 'म', 'प', 'ब' without long open vowels map to mouth_calm
        viseme, weight = resolve_akshara_viseme("म")
        self.assertEqual(viseme, MOUTH_CALM)
        self.assertEqual(weight, 0.35)

        viseme_p, _ = resolve_akshara_viseme("प")
        self.assertEqual(viseme_p, MOUTH_CALM)

    def test_open_vowels_under_calm_vs_wrath(self) -> None:
        # Calm context: open vowel 'रा' -> mouth_talk
        viseme_calm, weight = resolve_akshara_viseme("रा", emotion="calm")
        self.assertEqual(viseme_calm, MOUTH_TALK)
        self.assertEqual(weight, 0.60)

        # Wrath / shout context: open vowel 'रा' -> mouth_shout
        viseme_wrath, _ = resolve_akshara_viseme("रा", emotion="wrath")
        self.assertEqual(viseme_wrath, MOUTH_SHOUT)

        # Exclamation '!' -> mouth_shout
        viseme_excl, _ = resolve_akshara_viseme("हा", is_exclamation=True)
        self.assertEqual(viseme_excl, MOUTH_SHOUT)

    def test_fear_and_shock_emotions(self) -> None:
        viseme_fear, _ = resolve_akshara_viseme("भो", emotion="fear")
        self.assertEqual(viseme_fear, MOUTH_FEAR)

    def test_joy_and_smile_emotions(self) -> None:
        viseme_joy, _ = resolve_akshara_viseme("हे", emotion="joy")
        self.assertEqual(viseme_joy, MOUTH_JOY)

    def test_all_resolved_visemes_belong_to_five_svg_states(self) -> None:
        sample_syllables = ["क", "का", "कि", "की", "कु", "कू", "के", "कै", "को", "कौ", "म", "भ"]
        for syl in sample_syllables:
            for em in ["calm", "wrath", "fear", "joy"]:
                viseme, _ = resolve_akshara_viseme(syl, emotion=em)
                self.assertIn(viseme, ALL_MOUTH_STATES)


class TestLipsyncTimelineAndGSAP(unittest.TestCase):
    """Tests timeline generation and GSAP code output."""

    def test_build_lipsync_timeline_with_silence_gaps(self) -> None:
        words = [
            {"word": "काल", "start_sec": 0.0, "end_sec": 0.6},
            # Gap of 0.3s -> should insert mouth_calm
            {"word": "चक्र", "start_sec": 0.9, "end_sec": 1.5},
        ]
        timeline = build_lipsync_timeline(words, emotion="calm")
        self.assertGreater(len(timeline), 0)

        # Verify silence gap insertion
        pause_kfs = [kf for kf in timeline if kf.viseme == MOUTH_CALM and kf.syllable == "[pause]"]
        self.assertEqual(len(pause_kfs), 1)
        self.assertAlmostEqual(pause_kfs[0].start_sec, 0.6, places=2)
        self.assertAlmostEqual(pause_kfs[0].end_sec, 0.9, places=2)

    def test_proportional_duration_distribution(self) -> None:
        # Word 'रावण' duration 1.0s: 'रा' (weight 0.60) should get more time than 'व' (0.35) and 'ण' (0.35)
        words = [{"word": "रावण", "start_sec": 0.0, "end_sec": 1.0}]
        timeline = build_lipsync_timeline(words, emotion="wrath")

        ra_kf = [kf for kf in timeline if kf.viseme == MOUTH_SHOUT][0]
        # Total weight = 0.65 + 0.35 + 0.35 = 1.35; 'रा' gets ~0.48s
        self.assertGreater(ra_kf.duration_sec, 0.40)

    def test_gsap_lipsync_code_generation(self) -> None:
        words = [
            {"word": "शनि", "start_sec": 0.0, "end_sec": 0.6},
            {"word": "देव", "start_sec": 0.7, "end_sec": 1.2},
        ]
        timeline = build_lipsync_timeline(words, emotion="calm")
        js_code = generate_gsap_lipsync(timeline, "puppet_shani_dev")

        self.assertIn("Akshara Lip-Sync Driver for #puppet_shani_dev", js_code)
        self.assertIn('wrap.querySelector("#mouth_calm")', js_code)
        self.assertIn('wrap.querySelector("#mouth_talk")', js_code)
        self.assertIn('wrap.querySelector("#mouth_shout")', js_code)
        self.assertIn('wrap.querySelector("#mouth_fear")', js_code)
        self.assertIn('wrap.querySelector("#mouth_joy")', js_code)
        self.assertIn("lipTl.call", js_code)
        self.assertIn('setMouth("mouth_calm")', js_code)  # Return to calm at end


if __name__ == "__main__":
    unittest.main()
