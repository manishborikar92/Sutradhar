"""Sutradhar Video Engine — Word-by-Word Kinetic Subtitle Engine (v4.0).

Generates bottom-centered, word-by-word kinetic Hindi subtitles synchronized
with Whisper word-alignment timestamps and audio timeline.

Specifications:
1. Elegant Serif Typography: Playfair Display / EB Garamond in warm cream (#fef3c7).
2. Active-Word Highlighting: Scales 1.08x with bright white/gold glow.
3. Narrative Keyword Highlighting: Critical mythological and dramatic words in teal (#38bdf8).
4. Speech Gap Clearing: Fades down during pauses > 150ms to maintain theatrical cleanliness.
5. Deterministic GSAP 3 Timeline Generation for HyperFrames frame-seeking.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Final, Optional

from .config import (
    SUBTITLE_ACTIVE_SCALE,
    SUBTITLE_COLOR_ACTIVE,
    SUBTITLE_COLOR_GOLD,
    SUBTITLE_COLOR_KEYWORD,
    SUBTITLE_COLOR_NORMAL,
    SUBTITLE_SPEECH_GAP_FADE_SEC,
)

# Canonical list of pivotal mythological, astronomical, and dramatic keywords
DEFAULT_KEYWORD_PATTERNS: Final[tuple[str, ...]] = (
    # Deities and Characters
    "शनि", "शनिदेव", "रावण", "महादेव", "शिव", "सूर्य", "सूर्यदेव", "नारद",
    "मंदोदरी", "मेघनाद", "इंद्र", "यम", "काल", "नवग्रह", "ग्रह", "देवता", "असुर",
    # Mythological & Cosmic Concepts
    "स्वर्ण", "लंका", "कैलाश", "अमरता", "अमर", "कुण्डली", "दृष्टि", "श्राप",
    "वरदान", "मृत्यु", "विजय", "धर्म", "कर्म", "अहंकार", "क्रोध", "न्याय",
    "प्रचंड", "सिंहासन", "ब्रह्मांड", "पाताल", "आकाश", "कदम", "गदा", "चरण",
    # Numerical & Astrological
    "नौ", "दस", "बारह", "एकादश", "द्वादश", "अनंत", "पहला", "अंतिम", "कथा",
)

KEYWORD_REGEX: Final[re.Pattern[str]] = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in DEFAULT_KEYWORD_PATTERNS) + r")\b",
    re.UNICODE,
)


@dataclass
class WordCue:
    """Represents a single timed word within the subtitle stream."""

    word: str
    clean_word: str
    start_sec: float
    end_sec: float
    duration_sec: float
    is_keyword: bool = False
    keyword_type: str = "none"  # "teal", "gold", or "none"
    line_index: int = 0
    word_id: str = ""

    def __post_init__(self) -> None:
        if not self.word_id:
            safe_ts = str(round(self.start_sec, 3)).replace(".", "_")
            self.word_id = f"sub_w_{safe_ts}_{abs(hash(self.clean_word)) % 10000}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "word": self.word,
            "clean_word": self.clean_word,
            "start_sec": round(self.start_sec, 3),
            "end_sec": round(self.end_sec, 3),
            "duration_sec": round(self.duration_sec, 3),
            "is_keyword": self.is_keyword,
            "keyword_type": self.keyword_type,
            "line_index": self.line_index,
            "word_id": self.word_id,
        }


@dataclass
class SubtitleLine:
    """Represents a coherent phrase/line of subtitles (4-8 words)."""

    line_index: int
    words: list[WordCue] = field(default_factory=list)
    start_sec: float = 0.0
    end_sec: float = 0.0
    duration_sec: float = 0.0
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_index": self.line_index,
            "start_sec": round(self.start_sec, 3),
            "end_sec": round(self.end_sec, 3),
            "duration_sec": round(self.duration_sec, 3),
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
        }


def is_keyword_token(token: str) -> bool:
    """Check if a word token matches key mythological or dramatic keywords.

    Note: Indic matras (Unicode category Mn/Mc) cause ASCII \\b boundary checks
    to fail on words ending in vowels like 'शनि', so we match cleaned token roots.
    """
    clean = re.sub(r"[^\u0900-\u097Fa-zA-Z0-9]", "", token)
    if not clean:
        return False
    return any(
        kw == clean or (len(kw) >= 3 and kw in clean)
        for kw in DEFAULT_KEYWORD_PATTERNS
    )


def process_word_cues(raw_words: list[dict[str, Any]]) -> list[WordCue]:
    """Normalize and enrich raw word alignment timestamps with keyword detection."""
    cues: list[WordCue] = []
    for idx, w in enumerate(raw_words):
        raw_token = str(w.get("word", "")).strip()
        if not raw_token:
            continue

        clean_token = re.sub(r"[^\w\u0900-\u097F]", "", raw_token)
        start_t = float(w.get("start_sec", 0.0))
        end_t = float(w.get("end_sec", start_t + 0.3))
        dur = max(0.05, end_t - start_t)

        # Check keyword status
        explicit_kw = bool(w.get("is_keyword", False))
        auto_kw = is_keyword_token(clean_token)
        is_kw = explicit_kw or auto_kw

        kw_type = "teal" if is_kw else "none"
        if is_kw and any(g in clean_token for g in ("स्वर्ण", "अमरता", "विजय", "सिंहासन")):
            kw_type = "gold"

        cues.append(
            WordCue(
                word=raw_token,
                clean_word=clean_token,
                start_sec=round(start_t, 3),
                end_sec=round(end_t, 3),
                duration_sec=round(dur, 3),
                is_keyword=is_kw,
                keyword_type=kw_type,
            )
        )
    return cues


def group_words_into_lines(
    words: list[WordCue],
    max_words_per_line: int = 7,
    max_line_duration_sec: float = 3.2,
    pause_threshold_sec: float = SUBTITLE_SPEECH_GAP_FADE_SEC,
) -> list[SubtitleLine]:
    """Group sequential word cues into natural theatrical subtitle lines.

    Splits lines on:
    1. Punctuation boundaries ('।', ',', '!', '?').
    2. Significant speech pauses (> 150ms).
    3. Maximum word count (4-7 words) or line duration (~3.0s).
    """
    if not words:
        return []

    lines: list[SubtitleLine] = []
    current_words: list[WordCue] = []
    current_line_idx = 0

    for i, w in enumerate(words):
        current_words.append(w)
        w.line_index = current_line_idx

        # Check split conditions
        is_last = i == len(words) - 1
        has_punctuation = any(p in w.word for p in ("।", ",", "!", "?", "—", "-"))
        count_exceeded = len(current_words) >= max_words_per_line

        # Check pause gap to next word
        has_gap = False
        if not is_last:
            next_w = words[i + 1]
            gap = next_w.start_sec - w.end_sec
            if gap >= pause_threshold_sec:
                has_gap = True

        duration_so_far = w.end_sec - current_words[0].start_sec
        duration_exceeded = duration_so_far >= max_line_duration_sec

        if is_last or has_punctuation or has_gap or count_exceeded or duration_exceeded:
            line_start = current_words[0].start_sec
            line_end = current_words[-1].end_sec
            line_dur = round(line_end - line_start, 3)
            line_text = " ".join(cw.word for cw in current_words)

            lines.append(
                SubtitleLine(
                    line_index=current_line_idx,
                    words=list(current_words),
                    start_sec=line_start,
                    end_sec=line_end,
                    duration_sec=line_dur,
                    text=line_text,
                )
            )

            current_words.clear()
            current_line_idx += 1

    return lines


def generate_subtitle_html(lines: list[SubtitleLine]) -> str:
    """Generate static HTML wrapper for initial render."""
    return '<div id="subtitle_container" class="subtitle-box" data-layout-ignore="true">\n  <div id="subtitle_text" class="subtitle-line"></div>\n</div>'


def generate_gsap_subtitles(
    lines: list[SubtitleLine],
    container_id: str = "subtitle_text",
    master_timeline_var: str = "masterTl",
) -> str:
    """Generate deterministic GSAP 3 animation code driving word-by-word highlighting and gap fading.

    Code structure:
    1. Line Mount: Sets innerHTML with all words for that line at line_start - 0.05s.
    2. Active Word Highlighting: Scales 1.08x with class 'active' at word.start_sec,
       removes 'active' at word.end_sec.
    3. Gap Clearing: Clears innerHTML at line_end + 0.12s or when speech pauses > 150ms.
    """
    if not lines:
        return "// Zero subtitle lines to render.\n"

    js_lines: list[str] = [
        "  // ---------------------------------------------------------------------------",
        "  // Word-by-Word Kinetic Subtitle Timeline (v4.0)",
        "  // ---------------------------------------------------------------------------",
        f'  const subEl = document.getElementById("{container_id}");',
        "  if (subEl) {",
    ]

    for line in lines:
        line_start = max(0.0, line.start_sec - 0.04)
        line_end = line.end_sec

        # Pre-render HTML for this line
        word_spans: list[str] = []
        for w in line.words:
            kw_class = ""
            if w.is_keyword:
                kw_class = " keyword-gold" if w.keyword_type == "gold" else " keyword-teal"
            safe_text = html.escape(w.word)
            span = f'<span id="{w.word_id}" class="sub-word{kw_class}">{safe_text}</span>'
            word_spans.append(span)

        line_html_escaped = " ".join(word_spans).replace('"', '\\"')

        # 1. Mount line HTML on timeline
        js_lines.append(f"    // Subtitle Line {line.line_index}: {line.start_sec}s - {line.end_sec}s")
        js_lines.append(f'    {master_timeline_var}.call(() => {{')
        js_lines.append(f'      subEl.innerHTML = "{line_html_escaped}";')
        js_lines.append(f'      subEl.style.opacity = "1";')
        js_lines.append(f'    }}, null, {line_start:.3f});')

        # 2. Highlight each word at start_sec and un-highlight at end_sec
        for w in line.words:
            w_id = w.word_id
            js_lines.append(f'    {master_timeline_var}.call(() => {{')
            js_lines.append(f'      const wEl = document.getElementById("{w_id}");')
            js_lines.append(f'      if (wEl) wEl.classList.add("active");')
            js_lines.append(f'    }}, null, {w.start_sec:.3f});')

            js_lines.append(f'    {master_timeline_var}.call(() => {{')
            js_lines.append(f'      const wEl = document.getElementById("{w_id}");')
            js_lines.append(f'      if (wEl) wEl.classList.remove("active");')
            js_lines.append(f'    }}, null, {w.end_sec:.3f});')

        # 3. Clear line after finish with speech gap fade
        clear_time = round(line_end + 0.12, 3)
        js_lines.append(f'    {master_timeline_var}.call(() => {{')
        js_lines.append(f'      subEl.style.opacity = "0";')
        js_lines.append(f'      subEl.innerHTML = "";')
        js_lines.append(f'    }}, null, {clear_time:.3f});')
        js_lines.append("")

    js_lines.append("  }")
    return "\n".join(js_lines)
