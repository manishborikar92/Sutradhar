"""Unit and integration tests for Word-by-Word Kinetic Subtitle Engine (Phase 2)."""

import pytest

from scripts.engine.config import (
    SUBTITLE_ACTIVE_SCALE,
    SUBTITLE_COLOR_ACTIVE,
    SUBTITLE_COLOR_GOLD,
    SUBTITLE_COLOR_KEYWORD,
    SUBTITLE_COLOR_NORMAL,
    SUBTITLE_SPEECH_GAP_FADE_SEC,
)
from scripts.engine.subtitle_engine import (
    SubtitleLine,
    WordCue,
    generate_gsap_subtitles,
    generate_subtitle_html,
    group_words_into_lines,
    is_keyword_token,
    process_word_cues,
)


class TestKeywordDetection:
    """Verifies mythological, astronomical, and dramatic keyword detection."""

    def test_canonical_mythological_keywords(self):
        deity_words = ["शनि", "रावण", "महादेव", "शिव", "सूर्य", "नारद", "मंदोदरी"]
        for w in deity_words:
            assert is_keyword_token(w) is True, f"Expected '{w}' to be recognized as keyword"

    def test_cosmic_and_dramatic_keywords(self):
        dramatic_words = ["स्वर्ण", "लंका", "कैलाश", "अमरता", "कुण्डली", "श्राप", "वरदान", "क्रोध", "अहंकार"]
        for w in dramatic_words:
            assert is_keyword_token(w) is True, f"Expected '{w}' to be recognized as keyword"

    def test_punctuation_tolerance(self):
        assert is_keyword_token("रावण!") is True
        assert is_keyword_token("शनिदेव,") is True
        assert is_keyword_token("—अमरता।") is True

    def test_non_keywords(self):
        common_words = ["और", "था", "थी", "एक", "में", "पर", "से", "किया", "गया"]
        for w in common_words:
            assert is_keyword_token(w) is False, f"Expected '{w}' NOT to be recognized as keyword"


class TestWordCueProcessing:
    """Verifies enrichment and normalization of Whisper word alignment cues."""

    def test_process_word_cues_normalization(self):
        raw_words = [
            {"word": "राजा", "start_sec": 1.0, "end_sec": 1.4},
            {"word": "रावण", "start_sec": 1.45, "end_sec": 1.95},
            {"word": "ने", "start_sec": 2.0, "end_sec": 2.2},
            {"word": "स्वर्ण", "start_sec": 2.3, "end_sec": 2.7},
            {"word": "लंका", "start_sec": 2.75, "end_sec": 3.2},
        ]
        cues = process_word_cues(raw_words)
        assert len(cues) == 5

        # Check word cues properties
        assert cues[0].clean_word == "राजा"
        assert cues[0].is_keyword is False

        # Check keyword detection (teal vs gold)
        assert cues[1].clean_word == "रावण"
        assert cues[1].is_keyword is True
        assert cues[1].keyword_type == "teal"

        assert cues[3].clean_word == "स्वर्ण"
        assert cues[3].is_keyword is True
        assert cues[3].keyword_type == "gold"  # Special gold category

        # Verify word IDs are deterministic and valid HTML IDs
        for c in cues:
            assert c.word_id.startswith("sub_w_")
            assert " " not in c.word_id

    def test_empty_raw_words(self):
        assert process_word_cues([]) == []


class TestLineGrouping:
    """Verifies natural theatrical grouping of words into display lines."""

    def test_split_on_speech_gap_pause(self):
        # 160ms pause between word 2 and word 3 (> 150ms threshold)
        raw_words = [
            {"word": "राजा", "start_sec": 1.0, "end_sec": 1.3},
            {"word": "रावण", "start_sec": 1.35, "end_sec": 1.7},
            # Gap of 1.9 - 1.7 = 0.20s (200ms > 150ms)
            {"word": "क्रोध", "start_sec": 1.9, "end_sec": 2.3},
            {"word": "में", "start_sec": 2.35, "end_sec": 2.6},
        ]
        cues = process_word_cues(raw_words)
        lines = group_words_into_lines(cues, pause_threshold_sec=0.15)

        assert len(lines) == 2
        assert len(lines[0].words) == 2
        assert lines[0].text == "राजा रावण"
        assert len(lines[1].words) == 2
        assert lines[1].text == "क्रोध में"

    def test_split_on_punctuation_boundary(self):
        raw_words = [
            {"word": "महादेव,", "start_sec": 1.0, "end_sec": 1.4},
            {"word": "मुझे", "start_sec": 1.45, "end_sec": 1.7},
            {"word": "वरदान", "start_sec": 1.75, "end_sec": 2.1},
            {"word": "दें।", "start_sec": 2.15, "end_sec": 2.5},
            {"word": "तथास्तु", "start_sec": 2.55, "end_sec": 2.9},
        ]
        cues = process_word_cues(raw_words)
        lines = group_words_into_lines(cues)

        # "महादेव," has comma -> split line 1
        # "दें।" has danda -> split line 2
        # "तथास्तु" -> line 3
        assert len(lines) == 3
        assert lines[0].text == "महादेव,"
        assert lines[1].text == "मुझे वरदान दें।"
        assert lines[2].text == "तथास्तु"

    def test_split_on_max_word_count(self):
        # 10 words with continuous speech (< 100ms gaps)
        raw_words = [
            {"word": f"शब्द{i}", "start_sec": i * 0.3, "end_sec": i * 0.3 + 0.25}
            for i in range(10)
        ]
        cues = process_word_cues(raw_words)
        lines = group_words_into_lines(cues, max_words_per_line=5)

        assert len(lines) == 2
        assert len(lines[0].words) == 5
        assert len(lines[1].words) == 5


class TestGsapSubtitleGeneration:
    """Verifies deterministic GSAP 3 animation code generation for subtitles."""

    def test_gsap_code_structure_and_highlighting(self):
        raw_words = [
            {"word": "राजा", "start_sec": 2.0, "end_sec": 2.4},
            {"word": "रावण", "start_sec": 2.45, "end_sec": 2.95},
        ]
        cues = process_word_cues(raw_words)
        lines = group_words_into_lines(cues)
        js_code = generate_gsap_subtitles(lines, container_id="subtitle_text", master_timeline_var="masterTl")

        # 1. Timeline target check
        assert 'document.getElementById("subtitle_text")' in js_code
        assert "masterTl.call" in js_code

        # 2. Mounting check
        assert 'subEl.innerHTML = ' in js_code
        assert 'subEl.style.opacity = "1";' in js_code

        # 3. Word active class addition and removal
        for w in cues:
            assert f'const wEl = document.getElementById("{w.word_id}");' in js_code
            assert 'wEl.classList.add("active");' in js_code
            assert 'wEl.classList.remove("active");' in js_code

        # 4. Gap clearing check
        assert 'subEl.style.opacity = "0";' in js_code
        assert 'subEl.innerHTML = "";' in js_code

    def test_html_escaping_in_words(self):
        raw_words = [
            {"word": "अहंकार & क्रोध <विनाश>", "start_sec": 1.0, "end_sec": 1.8},
        ]
        cues = process_word_cues(raw_words)
        lines = group_words_into_lines(cues)
        js_code = generate_gsap_subtitles(lines)

        assert "&amp;" in js_code
        assert "&lt;विनाश&gt;" in js_code
        assert "<विनाश>" not in js_code

    def test_empty_lines_generates_comment(self):
        js_code = generate_gsap_subtitles([])
        assert "Zero subtitle lines" in js_code

    def test_subtitle_html_wrapper(self):
        html_code = generate_subtitle_html([])
        assert 'id="subtitle_container"' in html_code
        assert 'id="subtitle_text"' in html_code
