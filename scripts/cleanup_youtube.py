#!/usr/bin/env python3
"""Sutradhar YouTube Cleanup & Channel Reset Utility.

Provides:
1. Full channel video & playlist inventory export to backup/youtube_inventory.json.
2. Safe dry-run mode listing all items slated for deletion.
3. Explicit double-guarded deletion requiring both --delete and --confirm-delete-all.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from publish_youtube import load_env_youtube


def get_youtube_client(root: Path) -> Any:
    """Build authenticated YouTube Data API v3 client using .env.youtube."""
    env_creds = load_env_youtube(root)
    client_id = os.environ.get("YOUTUBE_CLIENT_ID") or env_creds.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET") or env_creds.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN") or env_creds.get("YOUTUBE_REFRESH_TOKEN")

    if not (client_id and client_secret and refresh_token):
        print("[ERROR] Missing YouTube OAuth credentials in .env.youtube or environment.", file=sys.stderr)
        return None

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        print(f"[ERROR] Required google libraries not installed: {exc}", file=sys.stderr)
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube"],
    )
    return build("youtube", "v3", credentials=creds)


def get_channel_inventory(youtube: Any) -> dict[str, Any]:
    """Retrieve all uploaded videos and playlists on the channel."""
    inventory: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "channel_title": None,
        "channel_id": None,
        "videos": [],
        "playlists": [],
    }

    # 1. Fetch Channel Uploads Playlist
    channels_res = youtube.channels().list(part="snippet,contentDetails", mine=True).execute()
    items = channels_res.get("items", [])
    if not items:
        print("[WARN] No channel found for authenticated user.", file=sys.stderr)
        return inventory

    channel = items[0]
    inventory["channel_title"] = channel.get("snippet", {}).get("title")
    inventory["channel_id"] = channel.get("id")
    uploads_playlist_id = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")

    # 2. Enumerate All Uploaded Videos via Uploads Playlist
    if uploads_playlist_id:
        video_ids: list[str] = []
        next_page_token: Optional[str] = None
        while True:
            pl_items = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            ).execute()
            for it in pl_items.get("items", []):
                vid = it.get("snippet", {}).get("resourceId", {}).get("videoId")
                if vid:
                    video_ids.append(vid)
            next_page_token = pl_items.get("nextPageToken")
            if not next_page_token:
                break

        # Batch-fetch video details (50 at a time)
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            v_res = youtube.videos().list(
                part="snippet,status,statistics",
                id=",".join(batch),
            ).execute()
            for v_item in v_res.get("items", []):
                snip = v_item.get("snippet", {})
                stat = v_item.get("status", {})
                metrics = v_item.get("statistics", {})
                inventory["videos"].append({
                    "video_id": v_item.get("id"),
                    "title": snip.get("title"),
                    "privacy_status": stat.get("privacyStatus"),
                    "published_at": snip.get("publishedAt"),
                    "view_count": int(metrics.get("viewCount", 0)),
                    "like_count": int(metrics.get("likeCount", 0)),
                    "comment_count": int(metrics.get("commentCount", 0)),
                })

    # 3. Enumerate Playlists
    pl_next_token: Optional[str] = None
    while True:
        pl_res = youtube.playlists().list(
            part="snippet,status,contentDetails",
            mine=True,
            maxResults=50,
            pageToken=pl_next_token,
        ).execute()
        for pl_item in pl_res.get("items", []):
            snip = pl_item.get("snippet", {})
            stat = pl_item.get("status", {})
            cnt = pl_item.get("contentDetails", {}).get("itemCount", 0)
            inventory["playlists"].append({
                "playlist_id": pl_item.get("id"),
                "title": snip.get("title"),
                "description": snip.get("description"),
                "privacy_status": stat.get("privacyStatus"),
                "item_count": cnt,
            })
        pl_next_token = pl_res.get("nextPageToken")
        if not pl_next_token:
            break

    inventory["total_videos"] = len(inventory["videos"])
    inventory["total_playlists"] = len(inventory["playlists"])
    return inventory


def run_inventory(root: Path, output_file: Optional[Path] = None) -> dict[str, Any]:
    """Export channel inventory to backup/youtube_inventory.json."""
    youtube = get_youtube_client(root)
    if not youtube:
        raise RuntimeError("Failed to initialize YouTube API client.")

    inv = get_channel_inventory(youtube)
    if output_file is None:
        backup_dir = root / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        output_file = backup_dir / "youtube_inventory.json"

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] YouTube channel inventory saved to {output_file} ({inv['total_videos']} videos, {inv['total_playlists']} playlists).")
    return inv


def main() -> int:
    parser = argparse.ArgumentParser(description="Sutradhar YouTube Cleanup & Review Utility")
    parser.add_argument("--inventory", action="store_true", help="Fetch and record full YouTube channel inventory to backup/youtube_inventory.json")
    parser.add_argument("--dry-run", action="store_true", help="List videos and playlists that would be deleted without deleting anything")
    parser.add_argument("--delete", action="store_true", help="Initiate deletion process (requires --confirm-delete-all)")
    parser.add_argument("--confirm-delete-all", action="store_true", help="Explicit confirmation to permanently delete all inventoried videos and playlists")

    args = parser.parse_args()

    root = REPO_ROOT
    backup_file = root / "backup" / "youtube_inventory.json"

    if args.inventory:
        try:
            inv = run_inventory(root, backup_file)
            print(f"Channel: {inv.get('channel_title')} (ID: {inv.get('channel_id')})")
            print(f"Total Videos: {inv['total_videos']}")
            for idx, v in enumerate(inv["videos"], 1):
                print(f"  [{idx}] ID: {v['video_id']} | Privacy: {v['privacy_status']} | Views: {v['view_count']} | Title: {v['title']}")
            print(f"Total Playlists: {inv['total_playlists']}")
            for idx, p in enumerate(inv["playlists"], 1):
                print(f"  [{idx}] ID: {p['playlist_id']} | Items: {p['item_count']} | Title: {p['title']}")
            return 0
        except Exception as exc:
            print(f"[ERROR] Inventory failed: {exc}", file=sys.stderr)
            return 1

    if args.dry_run:
        # Load or refresh inventory
        if not backup_file.is_file():
            print("[INFO] Inventory file not found; fetching live inventory first...")
            try:
                inv = run_inventory(root, backup_file)
            except Exception as exc:
                print(f"[ERROR] Could not fetch inventory: {exc}", file=sys.stderr)
                return 1
        else:
            inv = json.loads(backup_file.read_text(encoding="utf-8"))

        print("\n=== [DRY-RUN] PENDING YOUTUBE CLEANUP INVENTORY ===")
        print(f"Channel: {inv.get('channel_title')} ({inv.get('channel_id')})")
        print("\nVideos Slated For Deletion (PENDING USER EXPLICIT APPROVAL):")
        if not inv["videos"]:
            print("  (None found - channel has 0 videos)")
        for idx, v in enumerate(inv["videos"], 1):
            print(f"  {idx}. Video ID: {v['video_id']}")
            print(f"     Title: {v['title']}")
            print(f"     Privacy: {v['privacy_status']} | Views: {v['view_count']} | Published: {v['published_at']}")

        print("\nPlaylists Slated For Deletion (PENDING USER EXPLICIT APPROVAL):")
        if not inv["playlists"]:
            print("  (None found - channel has 0 custom playlists)")
        for idx, p in enumerate(inv["playlists"], 1):
            print(f"  {idx}. Playlist ID: {p['playlist_id']}")
            print(f"     Title: {p['title']} ({p['item_count']} items) | Privacy: {p['privacy_status']}")

        print("\n[SAFETY GUARD] NO deletions have been performed. Permanent deletion requires explicit user confirmation.")
        print("=== END DRY-RUN ===\n")
        return 0

    if args.delete:
        if not args.confirm_delete_all:
            print("[ERROR] Safety Violation: --delete requires --confirm-delete-all flag.", file=sys.stderr)
            return 1

        confirm_env = os.environ.get("SUTRADHAR_CONFIRM_DELETE_YOUTUBE") == "1"
        if not confirm_env:
            print("[ERROR] Safety Violation: SUTRADHAR_CONFIRM_DELETE_YOUTUBE=1 environment variable must be set.", file=sys.stderr)
            return 1

        print("[INFO] User explicit confirmation verified. Beginning permanent YouTube deletion...")
        youtube = get_youtube_client(root)
        if not youtube:
            print("[ERROR] Cannot authenticate with YouTube.", file=sys.stderr)
            return 1

        inv = run_inventory(root, backup_file)
        
        # User explicitly authorized ONLY these exact items
        approved_video_ids = {"MUdwEV8Lk0g", "QZ4PHaY6r1o"}
        approved_playlist_ids = {"PLHUH-vljiqfA", "PLV5anx_T8pUw"}

        # Delete approved videos
        deleted_vids = []
        for v in inv["videos"]:
            vid = v["video_id"]
            if vid not in approved_video_ids:
                print(f"[SKIP] Video {vid} ('{v['title']}') is not in the approved deletion list. Skipping.")
                continue
            try:
                youtube.videos().delete(id=vid).execute()
                print(f"[DELETED] Video: {vid} ('{v['title']}')")
                deleted_vids.append(vid)
                time.sleep(1.0)
            except Exception as e:
                print(f"[WARN] Failed to delete video {vid}: {e}", file=sys.stderr)

        # Delete approved playlists
        deleted_pls = []
        for p in inv["playlists"]:
            pid = p["playlist_id"]
            if pid not in approved_playlist_ids:
                print(f"[SKIP] Playlist {pid} ('{p['title']}') is not in the approved deletion list. Skipping.")
                continue
            try:
                youtube.playlists().delete(id=pid).execute()
                print(f"[DELETED] Playlist: {pid} ('{p['title']}')")
                deleted_pls.append(pid)
                time.sleep(1.0)
            except Exception as e:
                print(f"[WARN] Failed to delete playlist {pid}: {e}", file=sys.stderr)

        print(f"[OK] YouTube cleanup completed: {len(deleted_vids)} videos and {len(deleted_pls)} playlists deleted.")
        # Re-fetch inventory to verify clean channel
        run_inventory(root, backup_file)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
