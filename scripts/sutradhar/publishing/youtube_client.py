"""High-level YouTube publishing, playlist sync, thumbnail update, and read-only audit workflows."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sutradhar.config import StateError, load_config, resolve_paths
from sutradhar.db import (
    connect_db,
    ensure_db_initialized,
    immediate_transaction,
    record_published_episode,
)
from sutradhar.models import EpisodePlan, EpisodePlanV2, PublishResult, has_devanagari
from sutradhar.publishing.metadata_policy import (
    MetadataPolicyError,
    PlaylistResolutionError,
    build_video_metadata,
    list_channel_playlists_paginated,
    list_playlist_video_ids_paginated,
    resolve_or_create_series_playlist,
    validate_english_playlist_title,
)
from sutradhar.publishing.thumbnail_verifier import (
    ThumbnailValidationError,
    ThumbnailVerificationError,
    upload_thumbnail_and_verify,
    validate_local_thumbnail,
    verify_live_sardefault_parity,
)


class PublishPipelineError(RuntimeError):
    """Raised when YouTube publication, verification, or safety guardrails fail."""


def load_env_file(root: Path) -> dict[str, str]:
    """Parse .env.local if present without mutating parent process environment."""
    env_file = root / ".env.local"
    creds: dict[str, str] = {}
    if not env_file.is_file():
        return creds

    content = env_file.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            creds[key.strip()] = val.strip().strip("'\"")
    return creds


def _resolve_oauth_credentials(root: Path) -> tuple[Optional[str], Optional[str], Optional[str]]:
    env_creds = load_env_file(root)
    client_id = os.environ.get("YOUTUBE_CLIENT_ID") or env_creds.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET") or env_creds.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN") or env_creds.get("YOUTUBE_REFRESH_TOKEN")
    return client_id, client_secret, refresh_token


def build_youtube_client(root: Path, *, readonly: bool = False) -> Any:
    """Construct an authenticated YouTube Data API v3 client from `.env.local` or env vars."""
    client_id, client_secret, refresh_token = _resolve_oauth_credentials(root)
    if not (client_id and client_secret and refresh_token):
        raise PublishPipelineError(
            "Missing YouTube OAuth credentials (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN)."
        )

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    scopes = (
        ["https://www.googleapis.com/auth/youtube.readonly"]
        if readonly
        else [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
        ]
    )
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )
    return build("youtube", "v3", credentials=creds)


def compute_scheduled_publish_time(pub_cfg: dict[str, Any]) -> str:
    """Calculate next upcoming scheduled publication timestamp in UTC (ISO-8601 RFC 3339)."""
    now_utc = datetime.now(timezone.utc)
    sched_time_str = pub_cfg.get("scheduled_publish_time_utc", "13:00")
    try:
        hh, mm = map(int, sched_time_str.split(":"))
    except ValueError:
        hh, mm = 13, 0

    target_dt = now_utc.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target_dt <= now_utc + timedelta(minutes=15):
        target_dt += timedelta(days=1)
    return target_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_optional_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _extract_quality_metrics(
    build_dir: Path,
    final_video_path: Path,
    thumbnail_path: Path,
    plan_data: dict[str, Any],
) -> dict[str, Any]:
    qa_report = _load_optional_json(build_dir / "qa_report.json") or {}
    render_report = _load_optional_json(build_dir / "render_report.json") or {}
    if not qa_report and isinstance(render_report.get("v2_quality_gate"), dict):
        qa_report = render_report["v2_quality_gate"]

    motion_gate = qa_report.get("motion_and_look_gate") or {}
    kc = motion_gate.get("kinocut") or {}
    mp4_gate = qa_report.get("mp4_gate") or {}

    return {
        "file_bytes": final_video_path.stat().st_size if final_video_path.is_file() else render_report.get("file_bytes"),
        "duration_sec": mp4_gate.get("duration_sec") or render_report.get("duration_sec") or plan_data.get("target_duration_sec"),
        "kinocut_score": kc.get("dark_score") if kc.get("dark_score") is not None else render_report.get("kinocut_dark_score"),
        "static_fraction": kc.get("static_fraction"),
        "thumbnail_asset_path": "build/thumbnail.jpg" if thumbnail_path.is_file() else None,
        "video_asset_path": "build/final_short.mp4" if final_video_path.is_file() else None,
        "visual_direction_version": (
            (plan_data.get("storyboard_ir") or {}).get("visual_direction_version")
            or render_report.get("runtime_version")
            or "v2_storycraft"
        ),
    }


def _validate_pre_publish_artifacts(
    cfg: dict[str, Any],
    build_dir: Path,
    final_video_path: Path,
    episode_plan_path: Path,
    thumbnail_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not final_video_path.is_file():
        raise PublishPipelineError(f"Missing master video file at '{final_video_path}'. Run render_and_qa.py first.")
    if not episode_plan_path.is_file():
        raise PublishPipelineError(f"Missing episode plan at '{episode_plan_path}'.")

    try:
        plan_data = json.loads(episode_plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PublishPipelineError(f"Invalid JSON in '{episode_plan_path}': {exc}") from exc

    is_v2 = bool(plan_data.get("storyboard_ir") is not None or plan_data.get("thumbnail_spec") is not None)
    try:
        if is_v2:
            EpisodePlanV2.model_validate(plan_data, context={"config": cfg})
        else:
            legacy_payload = {k: v for k, v in plan_data.items() if k != "youtube_playlist_id"}
            EpisodePlan.model_validate(legacy_payload, context={"config": cfg})
    except Exception as exc:
        raise PublishPipelineError(f"EpisodePlan validation failed before publishing: {exc}") from exc

    max_file_bytes = int((cfg.get("video") or {}).get("max_file_bytes", 57_671_680))
    actual_bytes = final_video_path.stat().st_size
    if actual_bytes > max_file_bytes:
        raise PublishPipelineError(
            f"Master MP4 '{final_video_path.name}' ({actual_bytes:,} B) exceeds max_file_bytes ({max_file_bytes:,} B)."
        )

    qa_report = _load_optional_json(build_dir / "qa_report.json")
    if qa_report is not None and qa_report.get("passed") is False:
        raise PublishPipelineError(
            f"Pre-publish QA gate failed in '{build_dir / 'qa_report.json'}': {qa_report.get('failures')}"
        )

    if is_v2 and not thumbnail_path.is_file():
        raise PublishPipelineError(f"Missing required v2 English cover thumbnail at '{thumbnail_path}'.")

    metadata = build_video_metadata(plan_data, cfg, strict_v2=is_v2)
    quality_metrics = _extract_quality_metrics(build_dir, final_video_path, thumbnail_path, plan_data)
    return plan_data, metadata, quality_metrics


def publish_episode(
    root: Path,
    *,
    youtube_client: Any = None,
    commit_db: Optional[bool] = None,
) -> dict[str, Any]:
    """Validate EpisodePlan + QA artifacts, upload MP4, assign playlist, verify CDN thumb, and commit DB atomically."""
    root = Path(root).resolve()
    cfg = load_config(root)
    pub_cfg = cfg.get("publishing", {})

    upload_mode = pub_cfg.get("upload_mode", "public")
    if upload_mode not in ("public", "private_review", "scheduled"):
        raise PublishPipelineError(
            f"Invalid upload_mode '{upload_mode}' in config.yaml. Must be 'public', 'private_review', or 'scheduled'."
        )

    allow_pub = bool(pub_cfg.get("allow_public_or_scheduled", False))
    if upload_mode in ("public", "scheduled") and not allow_pub:
        raise PublishPipelineError(
            f"Safety Violation: config.yaml upload_mode='{upload_mode}' requires allow_public_or_scheduled=true."
        )

    scheduled_publish_at: Optional[str] = None
    if upload_mode == "public":
        target_privacy = "public"
        target_publish_status = "PUBLISHED"
    elif upload_mode == "scheduled":
        target_privacy = "private"
        target_publish_status = "PUBLISHED"
        scheduled_publish_at = compute_scheduled_publish_time(pub_cfg)
    else:
        target_privacy = "private"
        target_publish_status = "PRIVATE_REVIEW"

    paths = resolve_paths(root, cfg)
    build_dir = paths["build_dir"]
    build_dir.mkdir(parents=True, exist_ok=True)
    final_video_path = build_dir / "final_short.mp4"
    episode_plan_path = build_dir / "episode_plan.json"
    thumbnail_path = build_dir / "thumbnail.jpg"
    crop_path = build_dir / "thumbnail_2x3_crop.jpg"

    try:
        plan_data, metadata, quality_metrics = _validate_pre_publish_artifacts(
            cfg, build_dir, final_video_path, episode_plan_path, thumbnail_path
        )
    except MetadataPolicyError as exc:
        raise PublishPipelineError(str(exc)) from exc

    client_id, client_secret, refresh_token = _resolve_oauth_credentials(root)
    offline_force = os.environ.get("SUTRADHAR_OFFLINE_STUB") == "1"
    has_valid_creds = bool(client_id and client_secret and refresh_token) or (youtube_client is not None)
    is_offline_dry_run = offline_force or not has_valid_creds

    fmt = plan_data.get("content_format", "episodic_series")
    title = metadata["title"]
    description = metadata["description"]
    tags = metadata["tags"]
    category_id = metadata["categoryId"]
    default_lang = metadata["defaultLanguage"]
    default_audio_lang = metadata["defaultAudioLanguage"]
    series_title = metadata["series_title"] or plan_data.get("series_title") or "Sutradhar Series"

    verification_audit: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "offline_dry_run" if is_offline_dry_run else "live_youtube_api",
        "video_id": None,
        "playlist_id": None,
        "thumbnail_upload_status": None,
        "checks": {},
        "verification_verdict": "PENDING",
    }

    db_sync_result: Optional[dict[str, Any]] = None

    if is_offline_dry_run:
        if thumbnail_path.is_file():
            validate_local_thumbnail(
                thumbnail_path,
                expected_size=(1080, 1920),
                allowed_formats=("JPEG",),
                validate_2x3=True,
                crop_path=crop_path if crop_path.is_file() else None,
            )

        ep_num = int(plan_data.get("global_episode_number", 1))
        series_id = int(plan_data.get("series_id") or 1)
        simulated_video_id = f"dryrun_{ep_num:03d}_{int(time.time())}"
        simulated_playlist_id = None if fmt == "standalone" else (plan_data.get("youtube_playlist_id") or f"PL_dryrun_{series_id:03d}")

        result_dict = {
            "video_id": simulated_video_id,
            "playlist_id": simulated_playlist_id,
            "upload_status": target_publish_status,
            "scheduled_publish_at": scheduled_publish_at,
            "upload_mode": upload_mode,
            "privacy_status": target_privacy,
            "video_url": f"https://youtu.be/{simulated_video_id}",
            "error_message": None,
        }
        verification_audit.update(
            {
                "video_id": simulated_video_id,
                "playlist_id": simulated_playlist_id,
                "thumbnail_upload_status": "simulated_ok" if thumbnail_path.is_file() else "not_provided",
                "checks": {
                    "title": {"expected": title, "actual": title, "match": True},
                    "description": {"expected": description, "actual": description, "match": True},
                    "tags": {"expected": tags, "actual": tags, "match": True},
                    "categoryId": {"expected": category_id, "actual": category_id, "match": True},
                    "defaultAudioLanguage": {"expected": default_audio_lang, "actual": default_audio_lang, "match": True},
                    "defaultLanguage": {"expected": default_lang, "actual": default_lang, "match": True},
                    "privacyStatus": {"expected": target_privacy, "actual": target_privacy, "match": True},
                    "publishAt": {"expected": scheduled_publish_at, "actual": scheduled_publish_at, "match": True},
                    "selfDeclaredMadeForKids": {"expected": False, "actual": False, "match": True},
                    "containsSyntheticMedia": {"expected": True, "actual": True, "match": True},
                    "playlist_membership": {
                        "playlist_id": simulated_playlist_id,
                        "is_member": simulated_playlist_id is not None or fmt == "standalone",
                    },
                },
                "verification_verdict": "PASSED (OFFLINE SIMULATION)",
            }
        )
    else:
        try:
            from googleapiclient.http import MediaFileUpload

            youtube = youtube_client if youtube_client is not None else build_youtube_client(root, readonly=False)

            if thumbnail_path.is_file():
                validate_local_thumbnail(
                    thumbnail_path,
                    expected_size=(1080, 1920),
                    allowed_formats=("JPEG",),
                    validate_2x3=True,
                    crop_path=crop_path if crop_path.is_file() else None,
                )

            status_body: dict[str, Any] = {
                "privacyStatus": target_privacy,
                "selfDeclaredMadeForKids": False,
                "containsSyntheticMedia": True,
            }
            if scheduled_publish_at:
                status_body["publishAt"] = scheduled_publish_at

            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": category_id,
                    "defaultLanguage": default_lang,
                    "defaultAudioLanguage": default_audio_lang,
                },
                "status": status_body,
            }

            media = MediaFileUpload(str(final_video_path), chunksize=1 * 1024 * 1024, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None
            while response is None:
                _, response = request.next_chunk()
            video_id = (response or {}).get("id")
            if not video_id:
                raise PublishPipelineError(f"YouTube videos.insert returned no video ID: {response}")

            # Resolve & assign series playlist (fail closed for episodic_series / serial!)
            playlist_id = plan_data.get("youtube_playlist_id")
            playlist_privacy = "public" if upload_mode == "public" else "private"
            if fmt != "standalone" or playlist_id:
                auto_create = bool(pub_cfg.get("auto_create_series_playlist", True))
                playlist_id = resolve_or_create_series_playlist(
                    youtube,
                    series_title=series_title,
                    explicit_playlist_id=playlist_id,
                    playlist_privacy=playlist_privacy,
                    auto_create=auto_create,
                )
                try:
                    youtube.playlistItems().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "playlistId": playlist_id,
                                "resourceId": {"kind": "youtube#video", "videoId": video_id},
                            }
                        },
                    ).execute()
                except Exception as pl_exc:
                    raise PlaylistResolutionError(
                        f"Failed assigning video {video_id} to playlist '{playlist_id}': {pl_exc}"
                    ) from pl_exc

            # Wait for processing & verify live sardefault.jpg CDN parity
            thumbnail_status = "not_provided"
            thumbnail_verification: dict[str, Any] = {"upload_status": "not_provided", "match": True}
            if thumbnail_path.is_file():
                thumbnail_verification = upload_thumbnail_and_verify(
                    youtube,
                    video_id,
                    thumbnail_path,
                    is_short=True,
                    expected_build_dir=build_dir,
                    media_upload_cls=MediaFileUpload,
                )
                thumbnail_status = thumbnail_verification["upload_status"]

            verification_audit.update(
                {
                    "video_id": video_id,
                    "playlist_id": playlist_id,
                    "thumbnail_upload_status": thumbnail_status,
                }
            )

            # Live API read-back verification
            vid_read = youtube.videos().list(part="snippet,status", id=video_id).execute() or {}
            items = vid_read.get("items") or []
            if items:
                stored = items[0]
                s_snip = stored.get("snippet") or {}
                s_stat = stored.get("status") or {}
                verification_audit["checks"] = {
                    "title": {"expected": title, "actual": s_snip.get("title"), "match": s_snip.get("title") == title},
                    "description": {
                        "expected": description,
                        "actual": s_snip.get("description"),
                        "match": s_snip.get("description") == description,
                    },
                    "categoryId": {
                        "expected": category_id,
                        "actual": s_snip.get("categoryId"),
                        "match": s_snip.get("categoryId") == category_id,
                    },
                    "defaultAudioLanguage": {
                        "expected": default_audio_lang,
                        "actual": s_snip.get("defaultAudioLanguage"),
                        "match": s_snip.get("defaultAudioLanguage") == default_audio_lang,
                    },
                    "defaultLanguage": {
                        "expected": default_lang,
                        "actual": s_snip.get("defaultLanguage"),
                        "match": s_snip.get("defaultLanguage") == default_lang,
                    },
                    "privacyStatus": {
                        "expected": target_privacy,
                        "actual": s_stat.get("privacyStatus"),
                        "match": s_stat.get("privacyStatus") == target_privacy,
                    },
                    "publishAt": {
                        "expected": scheduled_publish_at,
                        "actual": s_stat.get("publishAt"),
                        "match": s_stat.get("publishAt") == scheduled_publish_at,
                    },
                    "selfDeclaredMadeForKids": {
                        "expected": False,
                        "actual": s_stat.get("selfDeclaredMadeForKids"),
                        "match": s_stat.get("selfDeclaredMadeForKids") is False,
                    },
                    "containsSyntheticMedia": {
                        "expected": True,
                        "actual": s_stat.get("containsSyntheticMedia", True),
                        "match": s_stat.get("containsSyntheticMedia", True) is True,
                    },
                    "thumbnail": {
                        **thumbnail_verification,
                        "snippet_thumbnails": list((s_snip.get("thumbnails") or {}).keys()),
                    },
                }
            else:
                verification_audit["checks"]["video_read_back"] = {"error": "No items returned for video ID", "match": False}

            if playlist_id:
                pl_vid_ids = list_playlist_video_ids_paginated(youtube, playlist_id)
                is_member = video_id in pl_vid_ids
                verification_audit["checks"]["playlist_membership"] = {
                    "playlist_id": playlist_id,
                    "is_member": is_member,
                    "playlist_items_count": len(pl_vid_ids),
                    "match": is_member,
                }
            elif fmt == "standalone":
                verification_audit["checks"]["playlist_membership"] = {
                    "playlist_id": None,
                    "is_member": True,
                    "note": "Standalone video: no playlist required",
                }

            all_checks_passed = all(
                c.get("match", True)
                for c in verification_audit.get("checks", {}).values()
                if isinstance(c, dict) and "match" in c
            )
            verification_audit["verification_verdict"] = "PASSED" if all_checks_passed else "WARNING"

            result_dict = {
                "video_id": video_id,
                "playlist_id": playlist_id,
                "upload_status": target_publish_status,
                "scheduled_publish_at": scheduled_publish_at,
                "upload_mode": upload_mode,
                "privacy_status": target_privacy,
                "video_url": f"https://youtu.be/{video_id}",
                "error_message": None,
            }
        except Exception as exc:
            verification_audit["verification_verdict"] = f"FAILED: {exc}"
            result_dict = {
                "video_id": None,
                "playlist_id": None,
                "upload_status": "FAILED",
                "scheduled_publish_at": scheduled_publish_at,
                "upload_mode": upload_mode,
                "privacy_status": target_privacy,
                "video_url": None,
                "error_message": str(exc),
            }

    # Validate result_dict strictly before DB commit or file output
    validated_res = PublishResult.model_validate(result_dict, context={"config": cfg})
    clean_dict = validated_res.model_dump()

    should_commit_db = (
        commit_db
        if commit_db is not None
        else (not is_offline_dry_run and paths["db_file"].is_file())
    )
    if should_commit_db and validated_res.upload_status in ("PUBLISHED", "PRIVATE_REVIEW"):
        ep_payload = plan_data if plan_data.get("storyboard_ir") is not None else {k: v for k, v in plan_data.items() if k != "youtube_playlist_id"}
        ep_model = EpisodePlan.model_validate(ep_payload, context={"config": cfg})
        db_sync_result = record_published_episode(
            root,
            cfg,
            ep_plan=ep_model,
            pub_res=validated_res,
            verification_audit=verification_audit,
            quality_metrics=quality_metrics,
        )
        verification_audit["db_sync"] = db_sync_result

    verif_path = build_dir / "publish_verification.json"
    verif_path.write_text(json.dumps(verification_audit, indent=2, ensure_ascii=False), encoding="utf-8")

    out_path = build_dir / "publish_result.json"
    out_path.write_text(json.dumps(clean_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    return clean_dict


def update_playlists(
    root: Path,
    *,
    youtube_client: Any = None,
    series_id: Optional[int] = None,
) -> dict[str, Any]:
    """Synchronize English playlist titles & privacy statuses for active/configured series."""
    root = Path(root).resolve()
    cfg = load_config(root)
    paths = resolve_paths(root, cfg)
    db_path = paths["db_file"]
    ensure_db_initialized(db_path)

    youtube = youtube_client if youtube_client is not None else build_youtube_client(root, readonly=False)
    pub_cfg = cfg.get("publishing", {})
    playlist_privacy = "public" if pub_cfg.get("upload_mode", "public") == "public" else "private"

    conn = connect_db(db_path)
    updated_rows: list[dict[str, Any]] = []
    try:
        query = "SELECT * FROM series WHERE status IN ('ACTIVE', 'COMPLETED')"
        params: tuple[Any, ...] = ()
        if series_id is not None:
            query += " AND series_id = ?"
            params = (series_id,)
        query += " ORDER BY series_id ASC"
        series_rows = conn.execute(query, params).fetchall()
        channel_playlists = {p.get("id"): p for p in list_channel_playlists_paginated(youtube) if p.get("id")}

        with immediate_transaction(conn) as cur:
            for row in series_rows:
                en_title = validate_english_playlist_title(row["series_title_en"] or row["series_title"])
                pl_id = row["youtube_playlist_id"]
                if pl_id and pl_id in channel_playlists:
                    pl_item = channel_playlists[pl_id]
                    snip = pl_item.get("snippet") or {}
                    stat = pl_item.get("status") or {}
                    desc = snip.get("description") or f"Sutradhar Series: {en_title}"
                    if (
                        (snip.get("title") or "").strip() != en_title
                        or snip.get("defaultLanguage") != "en"
                        or stat.get("privacyStatus") != playlist_privacy
                    ):
                        youtube.playlists().update(
                            part="id,snippet,status",
                            body={
                                "id": pl_id,
                                "snippet": {
                                    "title": en_title,
                                    "description": desc,
                                    "defaultLanguage": "en",
                                },
                                "status": {"privacyStatus": playlist_privacy},
                            },
                        ).execute()
                else:
                    pl_id = resolve_or_create_series_playlist(
                        youtube,
                        series_title=en_title,
                        explicit_playlist_id=pl_id,
                        playlist_privacy=playlist_privacy,
                        auto_create=bool(pub_cfg.get("auto_create_series_playlist", True)),
                    )
                    cur.execute(
                        "UPDATE series SET youtube_playlist_id = ?, updated_at = CURRENT_TIMESTAMP WHERE series_id = ?",
                        (pl_id, row["series_id"]),
                    )
                updated_rows.append({"series_id": row["series_id"], "title": en_title, "playlist_id": pl_id})
    finally:
        conn.close()

    return {"status": "ok", "action": "update_playlists", "synced": updated_rows}


def update_thumbnail_only(
    root: Path,
    *,
    video_id: Optional[str] = None,
    thumbnail_path: Optional[Path] = None,
    youtube_client: Any = None,
) -> dict[str, Any]:
    """Upload & CDN-verify a custom 1080x1920 JPEG thumbnail for an existing Short without touching video."""
    root = Path(root).resolve()
    cfg = load_config(root)
    paths = resolve_paths(root, cfg)
    build_dir = paths["build_dir"]

    resolved_thumb = Path(thumbnail_path).resolve() if thumbnail_path else (build_dir / "thumbnail.jpg")
    validate_local_thumbnail(resolved_thumb, expected_size=(1080, 1920), allowed_formats=("JPEG",), validate_2x3=True)

    resolved_vid = video_id
    if not resolved_vid:
        pub_res = _load_optional_json(build_dir / "publish_result.json")
        if pub_res and pub_res.get("video_id"):
            resolved_vid = pub_res["video_id"]
    if not resolved_vid and paths["db_file"].is_file():
        conn = connect_db(paths["db_file"])
        try:
            row = conn.execute(
                "SELECT youtube_video_id FROM episodes WHERE youtube_video_id IS NOT NULL ORDER BY episode_id DESC LIMIT 1"
            ).fetchone()
            if row:
                resolved_vid = row["youtube_video_id"]
        finally:
            conn.close()
    if not resolved_vid:
        raise PublishPipelineError("Cannot determine target video_id for --update-thumbnail.")

    from googleapiclient.http import MediaFileUpload

    youtube = youtube_client if youtube_client is not None else build_youtube_client(root, readonly=False)
    thumb_verif = upload_thumbnail_and_verify(
        youtube,
        resolved_vid,
        resolved_thumb,
        is_short=True,
        media_upload_cls=MediaFileUpload,
    )

    if paths["db_file"].is_file():
        conn = connect_db(paths["db_file"])
        try:
            ep_row = conn.execute(
                "SELECT episode_id, series_id FROM episodes WHERE youtube_video_id = ?",
                (resolved_vid,),
            ).fetchone()
            if ep_row is not None:
                pl_id = None
                if ep_row["series_id"] is not None:
                    srow = conn.execute(
                        "SELECT youtube_playlist_id FROM series WHERE series_id = ?",
                        (ep_row["series_id"],),
                    ).fetchone()
                    pl_id = srow["youtube_playlist_id"] if srow else None
                sim = thumb_verif.get("similarity") or {}
                with immediate_transaction(conn) as cur:
                    cur.execute(
                        """
                        INSERT INTO publishing_history (
                            episode_id, action, youtube_video_id, playlist_id, status, notes,
                            cdn_thumbnail_url, cdn_mae, cdn_dhash_distance, details_json
                        ) VALUES (?, 'THUMBNAIL_UPDATED', ?, ?, 'PUBLISHED', ?, ?, ?, ?, ?)
                        """,
                        (
                            ep_row["episode_id"],
                            resolved_vid,
                            pl_id,
                            f"Thumbnail updated & CDN verified for {resolved_vid}",
                            thumb_verif.get("cdn_url"),
                            sim.get("mae"),
                            sim.get("dhash_distance"),
                            json.dumps(thumb_verif, ensure_ascii=False),
                        ),
                    )
        finally:
            conn.close()

    return {
        "status": "ok",
        "action": "update_thumbnail",
        "video_id": resolved_vid,
        "thumbnail_verification": thumb_verif,
    }


def verify_live_channel_state(
    root: Path,
    *,
    youtube_client: Any = None,
    fetch_url_fn: Any = None,
) -> dict[str, Any]:
    """Strictly read-only live audit of DB integrity, Series 1-3 English playlists, and Ep 1-4 YouTube/CDN parity."""
    root = Path(root).resolve()
    cfg = load_config(root)
    paths = resolve_paths(root, cfg)
    db_path = paths["db_file"]
    if not db_path.is_file():
        raise StateError(f"Database file not found at {db_path}.")

    youtube = youtube_client if youtube_client is not None else build_youtube_client(root, readonly=True)

    conn = connect_db(db_path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        series_rows = [dict(r) for r in conn.execute("SELECT * FROM series ORDER BY series_id ASC").fetchall()]
        ep_rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM episodes WHERE status = 'PUBLISHED' AND youtube_video_id IS NOT NULL ORDER BY global_episode_number ASC"
            ).fetchall()
        ]
        history_counts = {
            r["episode_id"]: int(r["cnt"])
            for r in conn.execute(
                "SELECT episode_id, COUNT(*) AS cnt FROM publishing_history GROUP BY episode_id"
            ).fetchall()
        }
    finally:
        conn.close()

    failures: list[str] = []
    if integrity != "ok":
        failures.append(f"SQLite PRAGMA integrity_check returned {integrity!r}")

    # 1. Verify Playlists (Paginated read-only)
    try:
        channel_playlists = {p.get("id"): p for p in list_channel_playlists_paginated(youtube) if p.get("id")}
    except Exception as exc:
        raise PublishPipelineError(
            f"YouTube API read-only audit failed during OAuth/playlists.list ({exc}). "
            "If YOUTUBE_REFRESH_TOKEN expired or was revoked ('invalid_grant'), regenerate it per docs/SETUP_AND_OPERATIONS.md."
        ) from exc
    playlist_results: list[dict[str, Any]] = []
    playlist_video_cache: dict[str, set[str]] = {}

    for srow in series_rows:
        pl_id = srow.get("youtube_playlist_id")
        if not pl_id:
            continue
        pl_item = channel_playlists.get(pl_id)
        expected_en = srow.get("series_title_en") or srow.get("series_title") or ""
        pl_failures: list[str] = []
        if pl_item is None:
            pl_failures.append(f"Series {srow['series_id']} playlist '{pl_id}' not found on channel.")
            live_title = None
            live_lang = None
        else:
            snip = pl_item.get("snippet") or {}
            live_title = (snip.get("title") or "").strip()
            live_lang = snip.get("defaultLanguage")
            if has_devanagari(live_title):
                pl_failures.append(f"Playlist '{pl_id}' title contains Devanagari: {live_title!r}")
            if expected_en and live_title != expected_en:
                pl_failures.append(f"Playlist '{pl_id}' title mismatch: live={live_title!r} != db={expected_en!r}")
            if live_lang is not None and live_lang != "en":
                pl_failures.append(f"Playlist '{pl_id}' defaultLanguage={live_lang!r} != 'en'")
            playlist_video_cache[pl_id] = set(list_playlist_video_ids_paginated(youtube, pl_id))

        failures.extend(pl_failures)
        playlist_results.append(
            {
                "series_id": srow["series_id"],
                "playlist_id": pl_id,
                "expected_title_en": expected_en,
                "live_title": live_title,
                "default_language": live_lang,
                "passed": len(pl_failures) == 0,
                "failures": pl_failures,
            }
        )

    # 2. Verify Published Videos + CDN sardefault.jpg parity (mandatory from Episode 3 onward)
    video_ids = [ep["youtube_video_id"] for ep in ep_rows]
    live_videos: dict[str, dict[str, Any]] = {}
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start : start + 50]
        if not batch:
            continue
        resp = (
            youtube.videos()
            .list(part="snippet,status,contentDetails,processingDetails", id=",".join(batch))
            .execute()
            or {}
        )
        for item in resp.get("items") or []:
            if item.get("id"):
                live_videos[item["id"]] = item

    series_by_id = {s["series_id"]: s for s in series_rows}
    episode_results: list[dict[str, Any]] = []

    for ep in ep_rows:
        vid = ep["youtube_video_id"]
        g_num = int(ep["global_episode_number"])
        ep_failures: list[str] = []
        v_item = live_videos.get(vid)

        if history_counts.get(ep["episode_id"], 0) < 1:
            ep_failures.append(f"Episode {g_num} ({vid}) missing publishing_history audit row in episodes.db.")

        if v_item is None:
            ep_failures.append(f"Episode {g_num} ({vid}) not returned by YouTube videos.list.")
            thumb_audit: dict[str, Any] = {"passed": False}
        else:
            sn = v_item.get("snippet") or {}
            st = v_item.get("status") or {}
            pd = v_item.get("processingDetails") or {}

            if st.get("uploadStatus") != "processed":
                ep_failures.append(f"Episode {g_num} ({vid}) uploadStatus={st.get('uploadStatus')!r} != 'processed'")
            if pd.get("processingStatus") not in ("succeeded", None):
                ep_failures.append(
                    f"Episode {g_num} ({vid}) processingStatus={pd.get('processingStatus')!r} != 'succeeded'"
                )

            if g_num >= 3:
                live_title = sn.get("title") or ""
                live_desc = sn.get("description") or ""
                live_tags = sn.get("tags") or []
                if has_devanagari(live_title) or has_devanagari(live_desc) or any(has_devanagari(t) for t in live_tags):
                    ep_failures.append(f"Episode {g_num} ({vid}) contains Devanagari leak in YouTube metadata.")
                if live_title != ep["youtube_title"]:
                    ep_failures.append(f"Episode {g_num} ({vid}) title mismatch: live={live_title!r} != db={ep['youtube_title']!r}")
                if sn.get("defaultLanguage") != "en":
                    ep_failures.append(f"Episode {g_num} ({vid}) defaultLanguage={sn.get('defaultLanguage')!r} != 'en'")
                if sn.get("defaultAudioLanguage") != "hi":
                    ep_failures.append(f"Episode {g_num} ({vid}) defaultAudioLanguage={sn.get('defaultAudioLanguage')!r} != 'hi'")
                if ep.get("content_format") != "standalone" and ep.get("series_id") is not None:
                    pl_id = (series_by_id.get(ep["series_id"]) or {}).get("youtube_playlist_id")
                    if not pl_id or vid not in playlist_video_cache.get(pl_id, set()):
                        ep_failures.append(f"Episode {g_num} ({vid}) missing from series playlist '{pl_id}'.")

            local_thumb = (root / ep["thumbnail_asset_path"]).resolve() if ep.get("thumbnail_asset_path") else None
            thumb_audit = verify_live_sardefault_parity(
                v_item,
                local_thumb if (local_thumb is not None and local_thumb.is_file()) else None,
                global_episode_number=g_num,
                is_short=True,
                fetch_url_fn=fetch_url_fn,
            )
            if not thumb_audit["passed"]:
                ep_failures.extend(thumb_audit.get("failures") or [])

        failures.extend(ep_failures)
        episode_results.append(
            {
                "episode_id": ep["episode_id"],
                "global_episode_number": g_num,
                "video_id": vid,
                "content_format": ep.get("content_format"),
                "history_rows": history_counts.get(ep["episode_id"], 0),
                "thumbnail_cdn": thumb_audit,
                "passed": len(ep_failures) == 0,
                "failures": ep_failures,
            }
        )

    passed = len(failures) == 0
    return {
        "status": "ok" if passed else "failed",
        "action": "verify_only",
        "read_only": True,
        "db_integrity": integrity,
        "playlists": playlist_results,
        "episodes": episode_results,
        "failures": failures,
    }
