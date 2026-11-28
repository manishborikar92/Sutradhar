"""English YouTube metadata policy, scriptural citations, and paginated playlist resolution."""

from __future__ import annotations

from typing import Any, Optional

from sutradhar.models import has_devanagari

DEFAULT_SHORTS_TAGS: list[str] = [
    "Shorts",
    "Sutradhar",
    "Sutradhar Chronicles",
    "Indian Mythology",
    "Hindu Mythology",
    "Vedic Stories",
    "Ancient India",
    "Indian History",
    "Sanatana Dharma",
    "Puranas",
]


class MetadataPolicyError(RuntimeError):
    """Raised when YouTube title, description, tags, or playlist metadata violate language/Shorts policy."""


class PlaylistResolutionError(RuntimeError):
    """Raised when episodic series playlist resolution, creation, or assignment fails."""


def format_description_with_citations(base_desc: str, research: Optional[dict[str, Any]]) -> str:
    """Format and append authentic research source citations to the YouTube description."""
    if not research or not isinstance(research, dict):
        return base_desc

    source_tradition = research.get("source_tradition")
    facts = research.get("key_verified_facts") or []
    variants = research.get("cross_checked_variants")
    references = research.get("source_references") or []

    if not source_tradition and not references and not facts:
        return base_desc

    lines = [base_desc.rstrip(), "", "--- Traditional Sources & References ---"]
    if source_tradition:
        lines.append(f"• Scripture / Source: {source_tradition}")
    if variants:
        lines.append(f"• Variants / Tradition: {variants}")
    if facts:
        lines.append("• Key Verified Facts:")
        for fact in facts:
            lines.append(f"  - {fact}")
    if references:
        lines.append("• Authoritative References:")
        for ref in references:
            lines.append(f"  - {ref}")

    formatted = "\n".join(lines).strip()
    return formatted[:5000]


def validate_english_playlist_title(title: Optional[str]) -> str:
    """Ensure series playlist title is non-empty pure English (zero Devanagari)."""
    cleaned = (title or "").strip()
    if len(cleaned) < 3:
        raise MetadataPolicyError(f"Playlist title must be at least 3 characters (got {cleaned!r}).")
    if has_devanagari(cleaned):
        raise MetadataPolicyError(
            f"Playlist title must be pure English with zero Devanagari characters (got {cleaned!r})."
        )
    return cleaned[:150]


def _normalize_tags(
    raw_tags: Optional[list[str]],
    *,
    series_title: Optional[str],
    pillar: Optional[str],
    strict_tag_count: bool,
) -> list[str]:
    if raw_tags is None:
        if strict_tag_count:
            raise MetadataPolicyError("youtube_tags is required (must contain 10-15 English tags).")
        candidates = list(DEFAULT_SHORTS_TAGS)
        if series_title and series_title not in candidates:
            candidates.insert(3, series_title)
        if pillar and pillar not in candidates:
            candidates.append(pillar)
        tags = candidates[:12]
    else:
        seen: set[str] = set()
        tags = []
        for item in raw_tags:
            t = str(item or "").strip()
            if not t:
                continue
            key = t.lower()
            if key not in seen:
                seen.add(key)
                tags.append(t)

    for tag in tags:
        if has_devanagari(tag):
            raise MetadataPolicyError(f"YouTube tag must be pure English (found Devanagari in {tag!r}).")

    if strict_tag_count and not (10 <= len(tags) <= 15):
        raise MetadataPolicyError(
            f"youtube_tags must contain 10-15 English tags (got {len(tags)}: {tags})."
        )

    total_chars = sum(len(t) for t in tags)
    if total_chars > 500:
        raise MetadataPolicyError(f"Total YouTube tag characters ({total_chars}) exceed 500-char limit.")
    return tags


def validate_english_metadata(
    title: str,
    description: str,
    tags: Optional[list[str]],
    *,
    series_title: Optional[str] = None,
    pillar: Optional[str] = None,
    require_shorts_hashtag: bool = True,
    strict_tag_count: bool = True,
    require_scriptural_refs: bool = False,
) -> dict[str, Any]:
    """Validate English-only YouTube metadata contract (zero Devanagari, #Shorts, 10-15 tags)."""
    clean_title = (title or "").strip()
    if not (5 <= len(clean_title) <= 100):
        raise MetadataPolicyError(
            f"youtube_title length must be 5..100 chars (got {len(clean_title)})."
        )
    if "<" in clean_title or ">" in clean_title:
        raise MetadataPolicyError("youtube_title must not contain '<' or '>'.")
    if has_devanagari(clean_title):
        raise MetadataPolicyError(f"youtube_title must be pure English (found Devanagari in {clean_title!r}).")
    if require_shorts_hashtag and "#shorts" not in clean_title.lower():
        raise MetadataPolicyError(f"youtube_title must include '#Shorts' (got {clean_title!r}).")

    clean_desc = (description or "").strip()
    if not (10 <= len(clean_desc) <= 5000):
        raise MetadataPolicyError(
            f"youtube_description length must be 10..5000 chars (got {len(clean_desc)})."
        )
    if has_devanagari(clean_desc):
        raise MetadataPolicyError("youtube_description must be pure English (found Devanagari).")
    if require_scriptural_refs:
        desc_lower = clean_desc.lower()
        if (
            "--- traditional sources" not in desc_lower
            and "--- scriptural" not in desc_lower
            and "scripture" not in desc_lower
            and "reference" not in desc_lower
        ):
            raise MetadataPolicyError(
                "youtube_description must include scriptural or traditional references."
            )

    clean_tags = _normalize_tags(
        tags,
        series_title=series_title,
        pillar=pillar,
        strict_tag_count=strict_tag_count,
    )
    if series_title:
        validate_english_playlist_title(series_title)

    return {
        "title": clean_title[:100],
        "description": clean_desc[:5000],
        "tags": clean_tags,
    }


def build_video_metadata(
    plan_data: dict[str, Any],
    cfg: dict[str, Any],
    *,
    strict_v2: Optional[bool] = None,
) -> dict[str, Any]:
    """Build and policy-validate YouTube snippet metadata from EpisodePlan + config.yaml."""
    channel_cfg = cfg.get("channel") or {}
    pub_cfg = cfg.get("publishing") or {}

    is_v2 = bool(
        strict_v2
        if strict_v2 is not None
        else (
            plan_data.get("storyboard_ir") is not None
            or plan_data.get("thumbnail_spec") is not None
            or plan_data.get("youtube_tags") is not None
        )
    )

    raw_title = plan_data.get("youtube_title") or "Sutradhar Episode #Shorts"
    raw_desc = plan_data.get("youtube_description") or "Autonomous YouTube Shorts produced by Sutradhar."
    research = plan_data.get("story_research")
    description = format_description_with_citations(raw_desc, research)

    fmt = plan_data.get("content_format") or "episodic_series"
    series_title = plan_data.get("series_title")
    if fmt == "standalone" and not series_title:
        series_title_for_check = None
    else:
        series_title_for_check = series_title

    validated = validate_english_metadata(
        raw_title,
        description,
        plan_data.get("youtube_tags"),
        series_title=series_title_for_check,
        pillar=plan_data.get("pillar"),
        require_shorts_hashtag=True,
        strict_tag_count=is_v2,
        require_scriptural_refs=bool(is_v2 and research is not None),
    )

    is_legacy_plan = (
        not is_v2
        and "metadata_language" not in plan_data
        and "audio_language" not in plan_data
        and "language" not in plan_data
    )
    if is_legacy_plan:
        meta_lang = channel_cfg.get("primary_language", "en")
        audio_lang = channel_cfg.get("primary_language", "hi")
    else:
        meta_lang = (
            plan_data.get("metadata_language")
            or channel_cfg.get("metadata_language")
            or channel_cfg.get("default_language")
            or "en"
        )
        audio_lang = (
            plan_data.get("audio_language")
            or channel_cfg.get("audio_language")
            or channel_cfg.get("default_audio_language")
            or "hi"
        )
        if meta_lang != "en":
            raise MetadataPolicyError(f"metadata_language must be 'en' (got {meta_lang!r}).")
        if audio_lang != "hi":
            raise MetadataPolicyError(f"audio_language must be 'hi' (got {audio_lang!r}).")

    category_id = str(channel_cfg.get("category_id") or pub_cfg.get("category_id") or "27")

    return {
        "title": validated["title"],
        "description": validated["description"],
        "tags": validated["tags"],
        "categoryId": category_id,
        "defaultLanguage": meta_lang,
        "defaultAudioLanguage": audio_lang,
        "series_title": series_title_for_check,
        "strict_v2": is_v2,
    }


def list_channel_playlists_paginated(youtube: Any, *, max_pages: int = 20) -> list[dict[str, Any]]:
    """Fetch all channel playlists via paginated `playlists.list(mine=True)`."""
    items: list[dict[str, Any]] = []
    page_token: Optional[str] = None
    for _ in range(max_pages):
        kwargs: dict[str, Any] = {"part": "snippet,status,contentDetails", "mine": True, "maxResults": 50}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = youtube.playlists().list(**kwargs).execute() or {}
        items.extend(resp.get("items") or [])
        page_token = resp.get("nextPageToken")
        if not isinstance(page_token, str) or not page_token:
            break
    return items


def list_playlist_video_ids_paginated(youtube: Any, playlist_id: str, *, max_pages: int = 20) -> list[str]:
    """Fetch all video IDs inside a YouTube playlist with nextPageToken pagination."""
    video_ids: list[str] = []
    page_token: Optional[str] = None
    for _ in range(max_pages):
        kwargs: dict[str, Any] = {"part": "snippet,status", "playlistId": playlist_id, "maxResults": 50}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = youtube.playlistItems().list(**kwargs).execute() or {}
        for item in resp.get("items") or []:
            vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                video_ids.append(vid)
        page_token = resp.get("nextPageToken")
        if not isinstance(page_token, str) or not page_token:
            break
    return video_ids


def resolve_or_create_series_playlist(
    youtube: Any,
    *,
    series_title: str,
    explicit_playlist_id: Optional[str] = None,
    playlist_privacy: str = "public",
    auto_create: bool = True,
) -> str:
    """Resolve an English series playlist across all pages or create it cleanly; fails closed."""
    clean_title = validate_english_playlist_title(series_title)
    if explicit_playlist_id:
        return explicit_playlist_id

    try:
        playlists = list_channel_playlists_paginated(youtube)
    except Exception as exc:
        raise PlaylistResolutionError(f"Failed listing channel playlists for '{clean_title}': {exc}") from exc

    for item in playlists:
        snippet = item.get("snippet") or {}
        if (snippet.get("title") or "").strip() == clean_title:
            pl_id = item.get("id")
            if not pl_id:
                continue
            current_privacy = (item.get("status") or {}).get("privacyStatus")
            current_lang = snippet.get("defaultLanguage")
            if (playlist_privacy == "public" and current_privacy != "public") or current_lang != "en":
                try:
                    youtube.playlists().update(
                        part="id,snippet,status",
                        body={
                            "id": pl_id,
                            "snippet": {
                                "title": clean_title,
                                "description": snippet.get("description") or f"Sutradhar Series: {clean_title}",
                                "defaultLanguage": "en",
                            },
                            "status": {"privacyStatus": "public" if playlist_privacy == "public" else current_privacy or playlist_privacy},
                        },
                    ).execute()
                except Exception as exc:
                    raise PlaylistResolutionError(
                        f"Failed updating playlist '{pl_id}' metadata/privacy to English & {playlist_privacy}: {exc}"
                    ) from exc
            return pl_id

    if not auto_create:
        raise PlaylistResolutionError(f"Series playlist '{clean_title}' not found and auto_create=False.")

    try:
        created = (
            youtube.playlists()
            .insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": clean_title,
                        "description": f"Sutradhar Series: {clean_title}",
                        "defaultLanguage": "en",
                    },
                    "status": {"privacyStatus": playlist_privacy},
                },
            )
            .execute()
        )
    except Exception as exc:
        raise PlaylistResolutionError(f"Failed creating English playlist '{clean_title}': {exc}") from exc

    pl_id = (created or {}).get("id")
    if not pl_id:
        raise PlaylistResolutionError(f"YouTube playlists.insert returned no id for '{clean_title}': {created}")
    return pl_id
