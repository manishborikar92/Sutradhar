"""Em-dash-safe kinetic Devanagari caption chunking and dynamic keyword highlighting."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from sutradhar.audio.elevenlabs_tts import strip_audio_tags
from sutradhar.audio.whisper_aligner import write_text_atomic

COMPOUND_SPLIT_RE = re.compile(r"[—–\-/|,।!?…\"'“”‘’():;\s]+")
NON_WORD_CHAR_RE = re.compile(r"[^\u0900-\u097Fa-zA-Z0-9]+")
CLAUSE_END_PUNCT = ("।", "!", "?", "—", ",")


def normalize_kw_token(token: str) -> str:
    """Normalize a single Devanagari/Latin word for keyword comparison."""
    cleaned = NON_WORD_CHAR_RE.sub("", token.strip()).lower()
    cleaned = cleaned.replace("\u0901", "\u0902").replace("\u093c", "")
    return cleaned


def extract_subtokens(token: str) -> list[str]:
    """Split compound tokens across em-dashes, hyphens, and slashes BEFORE stripping punctuation.

    Example:
        `"बची—कैलाश"` -> `["बची", "कैलाश"]`
        `"कहलाए—नीलकंठ!"` -> `["कहलाए", "नीलकंठ"]`
    """
    parts = COMPOUND_SPLIT_RE.split(token.strip())
    subtokens: list[str] = []
    for part in parts:
        norm = normalize_kw_token(part)
        if norm:
            subtokens.append(norm)
    return subtokens


def extract_story_keywords(plan_or_scenes: Any) -> set[str]:
    """Dynamically harvest emphasis words and contextual pill terms from an EpisodePlan or scenes."""
    harvested: set[str] = set()
    scenes: Iterable[Any]
    if isinstance(plan_or_scenes, dict):
        scenes = plan_or_scenes.get("scenes", [])
        for kw in plan_or_scenes.get("keywords", []) or []:
            harvested.update(extract_subtokens(str(kw)))
    elif hasattr(plan_or_scenes, "scenes"):
        scenes = getattr(plan_or_scenes, "scenes", [])
    elif isinstance(plan_or_scenes, Iterable):
        scenes = plan_or_scenes
    else:
        return harvested

    for sc in scenes:
        if isinstance(sc, dict):
            emp = sc.get("emphasis_word")
            pill = (sc.get("visual_spec") or {}).get("contextual_pill", {}) if isinstance(sc.get("visual_spec"), dict) else {}
            pill_txt = pill.get("text") if isinstance(pill, dict) else None
            extra = sc.get("keywords") or []
        else:
            emp = getattr(sc, "emphasis_word", None)
            vs = getattr(sc, "visual_spec", None)
            cp = getattr(vs, "contextual_pill", None) if vs is not None else None
            pill_txt = getattr(cp, "text", None) if cp is not None else None
            extra = getattr(sc, "keywords", None) or []

        if emp:
            harvested.update(extract_subtokens(str(emp)))
        if pill_txt:
            harvested.update(extract_subtokens(str(pill_txt)))
        for kw in extra:
            harvested.update(extract_subtokens(str(kw)))
    return harvested


def is_keyword_token(
    token: str,
    *,
    keywords: Optional[Iterable[str]] = None,
    keyword_patterns: Optional[Iterable[str | re.Pattern[str]]] = None,
    emphasis_word: Optional[str] = None,
    story_keywords: Optional[Iterable[str]] = None,
) -> bool:
    """Return True if any em-dash/hyphen sub-token matches configured keywords or patterns."""
    subtokens = extract_subtokens(token)
    if not subtokens:
        return False

    kw_set: set[str] = set()
    for group in (keywords, story_keywords):
        if group:
            for item in group:
                kw_set.update(extract_subtokens(str(item)))
    if emphasis_word:
        kw_set.update(extract_subtokens(str(emphasis_word)))

    if any(sub in kw_set for sub in subtokens):
        return True

    if keyword_patterns:
        for pat in keyword_patterns:
            compiled = pat if isinstance(pat, re.Pattern) else re.compile(str(pat), re.IGNORECASE)
            if compiled.search(token) or any(compiled.search(sub) for sub in subtokens):
                return True
    return False


def build_caption_cues(
    scenes_manifest: list[dict[str, Any]],
    total_duration: float,
    *,
    keywords: Optional[Iterable[str]] = None,
    keyword_patterns: Optional[Iterable[str | re.Pattern[str]]] = None,
    story_keywords: Optional[Iterable[str]] = None,
    chunk_max_words: int = 4,
) -> list[dict[str, Any]]:
    """Group aligned words into 1–4 word non-overlapping kinetic cues (`end <= next_start - 0.03`)."""
    global_story_kws = set(extract_story_keywords(scenes_manifest))
    if story_keywords:
        for item in story_keywords:
            global_story_kws.update(extract_subtokens(str(item)))
    base_keywords = set()
    if keywords:
        for item in keywords:
            base_keywords.update(extract_subtokens(str(item)))

    cues: list[dict[str, Any]] = []
    cue_idx = 0
    max_words = max(1, int(chunk_max_words))

    for sc in scenes_manifest:
        scene_num = int(sc.get("scene_index", 1))
        scene_emphasis = sc.get("emphasis_word")
        scene_patterns = list(keyword_patterns or [])
        for pat in sc.get("keyword_patterns") or []:
            scene_patterns.append(pat)

        words = sc.get("words") or []
        buf: list[dict[str, Any]] = []

        def flush() -> None:
            nonlocal cue_idx, buf
            if not buf:
                return
            w_objs: list[dict[str, Any]] = []
            for w in buf:
                raw_word = strip_audio_tags(str(w.get("word") or w.get("text") or ""))
                gs = round(float(w.get("global_start", w.get("start", 0.0))), 3)
                ge = round(float(w.get("global_end", w.get("end", gs + 0.05))), 3)
                is_kw = is_keyword_token(
                    raw_word,
                    keywords=base_keywords,
                    keyword_patterns=scene_patterns,
                    emphasis_word=scene_emphasis,
                    story_keywords=global_story_kws,
                )
                w_objs.append(
                    {
                        "text": raw_word,
                        "start": gs,
                        "end": max(round(gs + 0.04, 3), ge),
                        "global_start": gs,
                        "global_end": max(round(gs + 0.04, 3), ge),
                        "kw": is_kw,
                    }
                )
            cues.append(
                {
                    "id": f"cap_{cue_idx:02d}",
                    "scene": scene_num,
                    "start": w_objs[0]["start"],
                    "end": w_objs[-1]["end"],
                    "words": w_objs,
                }
            )
            cue_idx += 1
            buf = []

        for w in words:
            buf.append(w)
            txt = str(w.get("word") or w.get("text") or "")
            ends_clause = txt.endswith(CLAUSE_END_PUNCT)
            if len(buf) >= max_words or (ends_clause and len(buf) >= 2):
                flush()
        flush()

    # Strict non-overlapping clamp across all cues (`end <= next_start - 0.03`)
    for i, c in enumerate(cues):
        next_start = cues[i + 1]["start"] if i + 1 < len(cues) else float(total_duration)
        prev_floor = round(cues[i - 1]["end"] + 0.03, 3) if i > 0 else 0.0

        c_end = round(min(c["end"] + 0.14, next_start - 0.03), 3)
        if c_end <= prev_floor:
            c_end = round(max(prev_floor + 0.04, next_start - 0.03), 3)
        c_start = round(max(prev_floor, min(c["start"], c_end - 0.04)), 3)
        c["start"] = c_start
        c["end"] = max(round(c_start + 0.04, 3), c_end)

        for j, wo in enumerate(c["words"]):
            w_prev = c["words"][j - 1]["end"] if j > 0 else c["start"]
            wo_s = round(max(w_prev, min(wo["start"], c["end"] - 0.02)), 3)
            w_next = c["words"][j + 1]["start"] if j + 1 < len(c["words"]) else c["end"]
            wo_e = round(min(max(wo_s + 0.02, wo["end"]), max(wo_s + 0.02, w_next)), 3)
            wo["start"] = wo_s
            wo["end"] = wo_e
            wo["global_start"] = wo_s
            wo["global_end"] = wo_e

    return cues


def write_captions_data_js(
    cues: list[dict[str, Any]],
    output_path: Path,
    *,
    var_name: str = "CAPTIONS_DATA",
) -> Path:
    """Atomically write caption cues to a JS payload readable by `captions.html.jinja2`."""
    js = f"window.{var_name} = {json.dumps(cues, indent=2, ensure_ascii=False)};\n"
    write_text_atomic(output_path, js)
    return output_path
