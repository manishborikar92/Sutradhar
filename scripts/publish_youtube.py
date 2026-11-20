#!/usr/bin/env python3
"""Sutradhar YouTube Offline / Private-Review Publishing Pipeline.

Implements Milestone 6 YouTube Data API v3 publishing integration.
Strictly adheres to:
1. Zero CLI arguments (Antigravity 7-command whitelist).
2. Hard configuration lock: upload_mode='private_review', privacy_status='private',
   and allow_public_or_scheduled=false.
3. Isolated .env.youtube credential discovery.
4. Resilient offline/stub execution when live credentials are absent or SUTRADHAR_OFFLINE_STUB=1.
5. Strict db_manager.PublishResult schema compliance (extra='forbid').
6. Mandatory YouTube AI disclosure (containsSyntheticMedia=True).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from db_manager import get_project_root, load_config, PublishResult, StateError  # noqa: E402


class PublishPipelineError(RuntimeError):
    """Raised when YouTube publication or safety guardrails fail."""


def load_env_youtube(root: Path) -> dict[str, str]:
    """Parse .env.youtube if present without mutating parent process environment."""
    env_file = root / ".env.youtube"
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
            key = key.strip()
            val = val.strip().strip("'\"")
            creds[key] = val
    return creds


def run_publish_pipeline(root: Path) -> dict[str, Any]:
    cfg = load_config(root)
    pub_cfg = cfg.get("publishing", {})

    upload_mode = pub_cfg.get("upload_mode", "private_review")
    if upload_mode != "private_review":
        raise PublishPipelineError(
            f"Safety Violation: Sutradhar is locked to upload_mode='private_review', got '{upload_mode}'."
        )

    allow_pub = pub_cfg.get("allow_public_or_scheduled", False)
    if allow_pub:
        raise PublishPipelineError(
            "Safety Violation: config.yaml allow_public_or_scheduled must be false."
        )

    paths = cfg.get("paths", {})
    build_dir = (root / paths.get("build_dir", "build")).resolve()
    final_video_path = build_dir / "final_short.mp4"
    episode_plan_path = build_dir / "episode_plan.json"

    if not final_video_path.is_file():
        raise PublishPipelineError(f"Missing master video file at '{final_video_path}'. Run render_and_qa.py first.")

    if not episode_plan_path.is_file():
        raise PublishPipelineError(f"Missing episode plan at '{episode_plan_path}'.")

    try:
        plan_data = json.loads(episode_plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PublishPipelineError(f"Invalid JSON in '{episode_plan_path}': {exc}") from exc

    # Parse .env.youtube
    env_creds = load_env_youtube(root)
    client_id = os.environ.get("YOUTUBE_CLIENT_ID") or env_creds.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET") or env_creds.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN") or env_creds.get("YOUTUBE_REFRESH_TOKEN")

    offline_force = os.environ.get("SUTRADHAR_OFFLINE_STUB") == "1"
    has_valid_creds = bool(client_id and client_secret and refresh_token)
    is_offline_dry_run = offline_force or not has_valid_creds

    title = plan_data.get("youtube_title", "Sutradhar Episode #Shorts")
    description = plan_data.get("youtube_description", "Autonomous YouTube Shorts produced by Sutradhar.")
    series_title = plan_data.get("series_title", "Sutradhar Series")
    category_id = str(pub_cfg.get("category_id", "27"))

    if is_offline_dry_run:
        # Resilient Offline / Dry-Run Simulation Mode
        reason = "SUTRADHAR_OFFLINE_STUB active" if offline_force else "No OAuth refresh token in .env.youtube"
        print(f"[INFO] Running in OFFLINE / DRY-RUN mode ({reason}).", file=sys.stderr)
        print(f"[INFO] Upload Mode: private_review | Privacy: private | Category: {category_id}", file=sys.stderr)
        print(f"[INFO] Synthetic Media Disclosure (AI): True | Title: {title}", file=sys.stderr)

        ep_num = plan_data.get("global_episode_number", 1)
        series_id = plan_data.get("series_id", 1)
        simulated_video_id = f"dryrun_{ep_num:03d}_{int(time.time())}"
        simulated_playlist_id = f"PL_dryrun_{series_id:03d}"

        result_dict = {
            "video_id": simulated_video_id,
            "playlist_id": simulated_playlist_id,
            "upload_status": "PRIVATE_REVIEW",
            "scheduled_publish_at": None,
            "upload_mode": "private_review",
            "privacy_status": "private",
            "video_url": f"https://youtu.be/{simulated_video_id}",
            "error_message": None,
        }
    else:
        # Live YouTube Data API v3 Upload Flow
        print(f"[INFO] Live YouTube OAuth credentials detected. Uploading private review video...", file=sys.stderr)
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=[
                    "https://www.googleapis.com/auth/youtube.upload",
                    "https://www.googleapis.com/auth/youtube",
                ],
            )
            youtube = build("youtube", "v3", credentials=creds)

            # 1. Upload Video
            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": ["Shorts", "Sutradhar", series_title],
                    "categoryId": category_id,
                    "defaultLanguage": "en",
                    "defaultAudioLanguage": "en",
                },
                "status": {
                    "privacyStatus": "private",  # Strictly enforced private review
                    "selfDeclaredMadeForKids": False,
                    "containsSyntheticMedia": True,  # Mandatory AI disclosure
                },
            }

            media = MediaFileUpload(str(final_video_path), chunksize=-1, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = request.execute()
            video_id = response.get("id")

            # 2. Add to Series Playlist
            playlist_id = None
            try:
                pl_request = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
                pl_response = pl_request.execute()
                for item in pl_response.get("items", []):
                    if item.get("snippet", {}).get("title") == series_title:
                        playlist_id = item.get("id")
                        break

                if not playlist_id:
                    create_pl = youtube.playlists().insert(
                        part="snippet,status",
                        body={
                            "snippet": {
                                "title": series_title,
                                "description": f"Sutradhar Series: {series_title}",
                            },
                            "status": {"privacyStatus": "private"},
                        },
                    )
                    pl_res = create_pl.execute()
                    playlist_id = pl_res.get("id")

                if playlist_id and video_id:
                    youtube.playlistItems().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "playlistId": playlist_id,
                                "resourceId": {
                                    "kind": "youtube#video",
                                    "videoId": video_id,
                                },
                            }
                        },
                    ).execute()
            except Exception as pl_exc:
                print(f"[WARN] Playlist assignment non-fatal error: {pl_exc}", file=sys.stderr)

            result_dict = {
                "video_id": video_id,
                "playlist_id": playlist_id,
                "upload_status": "PRIVATE_REVIEW",
                "scheduled_publish_at": None,
                "upload_mode": "private_review",
                "privacy_status": "private",
                "video_url": f"https://youtu.be/{video_id}" if video_id else None,
                "error_message": None,
            }
        except Exception as exc:
            print(f"[ERROR] Live YouTube upload failed: {exc}", file=sys.stderr)
            result_dict = {
                "video_id": None,
                "playlist_id": None,
                "upload_status": "FAILED",
                "scheduled_publish_at": None,
                "upload_mode": "private_review",
                "privacy_status": "private",
                "video_url": None,
                "error_message": str(exc),
            }

    # Strict Validation against db_manager.PublishResult (extra='forbid')
    validated_res = PublishResult.model_validate(result_dict, context={"config": cfg})
    clean_dict = validated_res.model_dump()

    # Write output artifact
    out_path = build_dir / "publish_result.json"
    out_path.write_text(json.dumps(clean_dict, indent=2), encoding="utf-8")
    print(f"[INFO] Published result recorded to {out_path}", file=sys.stderr)
    return clean_dict


def main() -> int:
    if len(sys.argv) > 1:
        print("[ERROR] scripts/publish_youtube.py takes zero CLI arguments.", file=sys.stderr)
        return 1
    try:
        root = get_project_root()
        res = run_publish_pipeline(root)
        print(json.dumps(res, indent=2))
        return 0 if res.get("upload_status") in ("PUBLISHED", "PRIVATE_REVIEW") else 1
    except (PublishPipelineError, StateError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"[FATAL] Unexpected error in publish_youtube.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
