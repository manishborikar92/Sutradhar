#!/usr/bin/env python3
"""Sutradhar YouTube Publishing & Read-Only Verification CLI Facade (`sutradhar.publishing`).

Supported commands:
    python scripts/publish_youtube.py                     # Default: --publish (6-step atomic runbook)
    python scripts/publish_youtube.py --publish           # Validate, upload, playlist, thumb CDN & atomic DB commit
    python scripts/publish_youtube.py --update-playlists  # Sync English playlist titles/privacy
    python scripts/publish_youtube.py --update-thumbnail  # Thumbnail-only upload + sardefault.jpg CDN verify
    python scripts/publish_youtube.py --verify-only       # Strictly read-only live YouTube/CDN/DB audit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sutradhar.config import StateError, get_project_root  # noqa: E402
from sutradhar.publishing.metadata_policy import (  # noqa: E402
    MetadataPolicyError,
    PlaylistResolutionError,
    format_description_with_citations,
)
from sutradhar.publishing.youtube_client import (  # noqa: E402
    PublishPipelineError,
    compute_scheduled_publish_time,
    load_env_file,
    publish_episode,
    update_playlists,
    update_thumbnail_only,
    verify_live_channel_state,
)


def run_publish_pipeline(root: Path, *, commit_db: Optional[bool] = None) -> dict[str, Any]:
    """Compatibility entry point delegating to ``sutradhar.publishing.youtube_client.publish_episode``."""
    return publish_episode(root, commit_db=commit_db)


class _StrictParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _StrictParser(
        prog="publish_youtube.py",
        description="Sutradhar YouTube publishing, playlist sync, thumbnail verification & read-only audit.",
    )
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--publish", action="store_true", help="Publish build/final_short.mp4 and commit DB atomically")
    mode.add_argument("--update-playlists", action="store_true", help="Synchronize English series playlists on YouTube")
    mode.add_argument("--update-thumbnail", action="store_true", help="Upload & CDN-verify custom thumbnail only")
    mode.add_argument("--verify-only", action="store_true", help="Read-only live audit of Ep 1-4, Series 1-3 & CDN")

    parser.add_argument("--video-id", default=None, help="Target video ID (for --update-thumbnail)")
    parser.add_argument("--thumbnail-path", default=None, help="Custom thumbnail path (for --update-thumbnail)")
    parser.add_argument("--series-id", type=int, default=None, help="Target series_id (for --update-playlists)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    try:
        args = parser.parse_args(raw_args)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    try:
        root = get_project_root()
        if args.verify_only:
            res = verify_live_channel_state(root)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0 if res.get("status") == "ok" else 1
        if args.update_playlists:
            res = update_playlists(root, series_id=args.series_id)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0
        if args.update_thumbnail:
            thumb_p = Path(args.thumbnail_path) if args.thumbnail_path else None
            res = update_thumbnail_only(root, video_id=args.video_id, thumbnail_path=thumb_p)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0

        res = run_publish_pipeline(root)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res.get("upload_status") in ("PUBLISHED", "PRIVATE_REVIEW") else 1
    except (PublishPipelineError, MetadataPolicyError, PlaylistResolutionError, StateError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"[FATAL] Unexpected error in publish_youtube.py: {exc}", file=sys.stderr)
        return 2


__all__ = [
    "MetadataPolicyError",
    "PlaylistResolutionError",
    "PublishPipelineError",
    "build_parser",
    "compute_scheduled_publish_time",
    "format_description_with_citations",
    "load_env_file",
    "main",
    "run_publish_pipeline",
]


if __name__ == "__main__":
    raise SystemExit(main())
