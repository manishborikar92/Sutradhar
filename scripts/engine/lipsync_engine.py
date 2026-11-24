"""Sutradhar Video Engine — Akshara-Level Hindi Phonetic Lip-Sync (v4.0).

Parses spoken Devanagari text into orthographic syllables (Aksharas) and maps
them to the 5 SVG puppet mouth viseme states:
- mouth_calm (closure / neutral rest / bilabial consonants)
- mouth_talk (active conversational open vowel / neutral 'a')
- mouth_shout (wide open vowel 'aa' / dramatic exclamation)
- mouth_fear (tense rounded mouth / shock / distress)
- mouth_joy (spread grin / laughter / delight)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final, Optional

from .config import (
    ALL_MOUTH_STATES,
    MOUTH_CALM,
    MOUTH_FEAR,
    MOUTH_JOY,
    MOUTH_SHOUT,
    MOUTH_TALK,
)

# Devanagari Unicode Character Sets
CONSONANTS: Final[str] = "कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह"
VOWELS_INDEPENDENT: Final[str] = "अआइईउऊऋएऐओऔ"
VOWEL_MATRAS: Final[str] = "ािीुूृेैोौ"
MODIFIERS: Final[str] = "ंःँ"
HALANT: Final[str] = "्"

# Bilabial Consonants (cause momentary lip closure -> mouth_calm)
BILABIALS: Final[set[str]] = {"म", "ब", "प", "भ", "फ"}

# Open vowels (wide mouth opening)
OPEN_VOWELS: Final[set[str]] = {"ा", "आ", "ौ"}

# Rounded vowels (narrower, round mouth)
ROUNDED_VOWELS: Final[set[str]] = {"ो", "ू", "ु", "उ", "ऊ", "ओ"}

# Spread vowels (wide smiling/horizontal opening)
SPREAD_VOWELS: Final[set[str]] = {"े", "ै", "ी", "ि", "इ", "ई", "ए", "ऐ"}

# Comprehensive Akshara regex matching consonant clusters with halant + matra/modifier, or independent vowels
AKSHARA_REGEX: Final[re.Pattern[str]] = re.compile(
    r"(?:[" + CONSONANTS + r"]" + HALANT + r")*[" + CONSONANTS + r"][" + VOWEL_MATRAS + MODIFIERS + r"]*"
    r"|[" + VOWELS_INDEPENDENT + r"][" + MODIFIERS + r"]*"
    r"|[a-zA-Z0-9]+"
)


@dataclass(frozen=True)
class Akshara:
    syllable: str
    viseme: str
    weight: float


@dataclass(frozen=True)
class VisemeKeyframe:
    start_sec: float
    end_sec: float
    viseme: str
    syllable: str = ""

    @property
    def duration_sec(self) -> float:
        return round(self.end_sec - self.start_sec, 4)


def resolve_akshara_viseme(
    syllable: str,
    emotion: str = "calm",
    is_exclamation: bool = False,
) -> tuple[str, float]:
    """Determines the appropriate 5-state mouth viseme and proportional duration weight for an Akshara.

    Returns:
        (viseme_id, weight)
    """
    emotion_lower = (emotion or "calm").lower()

    # 1. Bilabial consonant closure check (e.g. 'म', 'प', 'ब')
    # If the syllable ends in a bilabial with halant or pure short consonant closure
    has_bilabial = any(b in syllable for b in BILABIALS)
    has_long_vowel = any(v in syllable for v in OPEN_VOWELS | ROUNDED_VOWELS | SPREAD_VOWELS)

    if has_bilabial and not has_long_vowel:
        return MOUTH_CALM, 0.35

    # 2. Open vowels ('ा', 'आ', 'ौ')
    if any(v in syllable for v in OPEN_VOWELS):
        if is_exclamation or emotion_lower in ("wrath", "shout", "anger", "command"):
            return MOUTH_SHOUT, 0.65
        if emotion_lower in ("fear", "shock"):
            return MOUTH_FEAR, 0.60
        if emotion_lower in ("joy", "smile", "smirk", "laugh"):
            return MOUTH_JOY, 0.60
        return MOUTH_TALK, 0.60

    # 3. Rounded vowels ('ो', 'ू', 'ु', 'उ', 'ऊ', 'ओ')
    if any(v in syllable for v in ROUNDED_VOWELS):
        if emotion_lower in ("fear", "shock", "tremble"):
            return MOUTH_FEAR, 0.55
        if is_exclamation:
            return MOUTH_SHOUT, 0.55
        return MOUTH_TALK, 0.50

    # 4. Spread vowels ('े', 'ै', 'ी', 'ि', 'इ', 'ई', 'ए', 'ऐ')
    if any(v in syllable for v in SPREAD_VOWELS):
        if emotion_lower in ("joy", "smile", "smirk", "laugh"):
            return MOUTH_JOY, 0.50
        if emotion_lower in ("fear", "shock"):
            return MOUTH_FEAR, 0.45
        return MOUTH_TALK, 0.45

    # 5. Default neutral short 'a'
    if emotion_lower in ("joy", "smile"):
        return MOUTH_JOY, 0.35
    if emotion_lower in ("fear", "shock"):
        return MOUTH_FEAR, 0.35

    return MOUTH_TALK, 0.35


def parse_hindi_aksharas(
    word: str,
    emotion: str = "calm",
) -> list[Akshara]:
    """Decomposes a Devanagari word into orthographic syllables with viseme mappings."""
    if not word or not word.strip():
        return []

    clean_word = word.strip()
    is_exclamation = "!" in clean_word

    aksharas: list[Akshara] = []
    matches = list(AKSHARA_REGEX.finditer(clean_word))

    if not matches:
        # Fallback for unexpected tokens / punctuation
        return [Akshara(syllable=clean_word, viseme=MOUTH_TALK, weight=0.4)]

    for m in matches:
        syl = m.group()
        viseme, weight = resolve_akshara_viseme(
            syllable=syl,
            emotion=emotion,
            is_exclamation=is_exclamation,
        )
        aksharas.append(Akshara(syllable=syl, viseme=viseme, weight=weight))

    return aksharas


def build_lipsync_timeline(
    words: list[dict[str, Any]],
    emotion: str = "calm",
    min_viseme_duration_sec: float = 0.060,  # ~16 FPS max switch rate to avoid chatter
    silence_gap_threshold_sec: float = 0.080, # Return to calm if pause between words
) -> list[VisemeKeyframe]:
    """Constructs a deterministic viseme switch timeline from timestamped words.

    Args:
        words: List of dicts with 'word', 'start_sec', 'end_sec' (or 'start', 'end').
        emotion: Theatrical emotion context ('calm', 'wrath', 'fear', 'joy').
        min_viseme_duration_sec: Minimum duration for any mouth state to prevent flicker.
        silence_gap_threshold_sec: Gap duration above which mouth returns to mouth_calm.

    Returns:
        List of continuous VisemeKeyframe objects.
    """
    if not words:
        return []

    raw_keyframes: list[VisemeKeyframe] = []
    last_end = 0.0

    for idx, w in enumerate(words):
        word_text = str(w.get("word") or "").strip()
        start = float(w.get("start_sec") if "start_sec" in w else w.get("start", 0.0))
        end = float(w.get("end_sec") if "end_sec" in w else w.get("end", start + 0.3))

        if end <= start:
            end = start + 0.2

        # 1. Fill inter-word pause with mouth_calm if gap exceeds threshold
        if start - last_end >= silence_gap_threshold_sec:
            raw_keyframes.append(
                VisemeKeyframe(
                    start_sec=round(last_end, 4),
                    end_sec=round(start, 4),
                    viseme=MOUTH_CALM,
                    syllable="[pause]",
                )
            )

        # 2. Decompose word into Aksharas
        aksharas = parse_hindi_aksharas(word_text, emotion=emotion)
        total_weight = sum(a.weight for a in aksharas) or 1.0
        word_dur = end - start

        curr_t = start
        for ak in aksharas:
            syl_dur = (ak.weight / total_weight) * word_dur
            syl_end = curr_t + syl_dur
            raw_keyframes.append(
                VisemeKeyframe(
                    start_sec=round(curr_t, 4),
                    end_sec=round(syl_end, 4),
                    viseme=ak.viseme,
                    syllable=ak.syllable,
                )
            )
            curr_t = syl_end

        last_end = end

    # 3. Post-process: merge adjacent identical visemes & enforce minimum duration
    merged: list[VisemeKeyframe] = []
    for kf in raw_keyframes:
        if not merged:
            merged.append(kf)
            continue

        prev = merged[-1]
        if prev.viseme == kf.viseme:
            # Merge contiguous identical mouth state
            merged[-1] = VisemeKeyframe(
                start_sec=prev.start_sec,
                end_sec=kf.end_sec,
                viseme=prev.viseme,
                syllable=f"{prev.syllable}{kf.syllable}",
            )
        else:
            if kf.duration_sec < min_viseme_duration_sec and merged:
                # If keyframe is too short, extend previous or current to smooth transition
                merged[-1] = VisemeKeyframe(
                    start_sec=prev.start_sec,
                    end_sec=kf.end_sec,
                    viseme=prev.viseme,
                    syllable=f"{prev.syllable}{kf.syllable}",
                )
            else:
                merged.append(kf)

    return merged


def generate_gsap_lipsync(
    timeline: list[VisemeKeyframe],
    wrapper_id: str,
) -> str:
    """Generates GSAP 3 JavaScript calls to drive the 5 SVG mouth layers."""
    if not timeline:
        return f"// No lipsync keyframes for #{wrapper_id}\n"

    lines = [
        f"// Akshara Lip-Sync Driver for #{wrapper_id}",
        f"(function() {{",
        f'  const wrap = document.getElementById("{wrapper_id}");',
        f"  if (!wrap) return;",
        f"  const mouthStates = {{",
    ]
    for state in ALL_MOUTH_STATES:
        lines.append(f'    "{state}": wrap.querySelector("#{state}"),')
    lines.extend([
        f"  }};",
        f"  function setMouth(activeState) {{",
        f"    for (const [name, el] of Object.entries(mouthStates)) {{",
        f"      if (!el) continue;",
        f"      gsap.set(el, {{ opacity: name === activeState ? 1 : 0 }});",
        f"    }}",
        f"  }}",
        f"  const lipTl = gsap.timeline();",
    ])

    for kf in timeline:
        lines.append(
            f'  lipTl.call(() => setMouth("{kf.viseme}"), null, {kf.start_sec:.3f});'
        )

    # Return to mouth_calm at the end of speech
    final_end = timeline[-1].end_sec if timeline else 0.0
    lines.append(f'  lipTl.call(() => setMouth("{MOUTH_CALM}"), null, {final_end:.3f});')
    lines.append("})();\n")

    return "\n".join(lines)
