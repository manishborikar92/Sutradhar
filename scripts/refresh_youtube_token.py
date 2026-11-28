#!/usr/bin/env python3
"""Regenerate YOUTUBE_REFRESH_TOKEN using a local Google OAuth2 loopback + PKCE flow.

Run from the repository root:
    .\\.venv\\Scripts\\python.exe scripts\\refresh_youtube_token.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sutradhar.config import StateError, get_project_root  # noqa: E402
from sutradhar.publishing.oauth_refresh import (  # noqa: E402
    DEFAULT_CALLBACK_TIMEOUT_SECONDS,
    OAuthRefreshError,
    run_oauth_refresh_flow,
)


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for YouTube OAuth refresh token regeneration."""
    parser = argparse.ArgumentParser(
        prog="refresh_youtube_token.py",
        description=(
            "Regenerate YOUTUBE_REFRESH_TOKEN in .env.local using a local Google OAuth2 "
            "loopback + PKCE flow (pure Python stdlib, no secrets printed)."
        ),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Path to env file containing YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET (defaults to .env.local).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_CALLBACK_TIMEOUT_SECONDS,
        help=f"Seconds to wait for OAuth browser callback (default: {DEFAULT_CALLBACK_TIMEOUT_SECONDS}).",
    )
    return parser


def _print_auth_instructions(authorization_url: str) -> None:
    print("A browser window will open. Sign in with the Google account")
    print("that owns the YouTube channel, then approve the requested access.")
    print(f"If it does not open automatically, visit:\n{authorization_url}\n")


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for regenerating YOUTUBE_REFRESH_TOKEN."""
    parser = build_parser()
    args = parser.parse_args(argv)

    print("Sutradhar — YouTube OAuth refresh-token regeneration\n")
    try:
        root = get_project_root()
        env_file = args.env_file.resolve() if args.env_file else (root / ".env.local")
        updated_path = run_oauth_refresh_flow(
            env_file,
            timeout_seconds=args.timeout,
            on_auth_url=_print_auth_instructions,
        )
        print(f"\nSUCCESS: A new YouTube refresh token was saved to {updated_path}.")
        print("The token itself was not printed.")
        print("\nNow verify it with:")
        print(r".\.venv\Scripts\python.exe scripts\publish_youtube.py --verify-only")
        return 0
    except KeyboardInterrupt:
        print("\nCancelled. The environment file was not changed.")
        return 130
    except (OAuthRefreshError, StateError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
