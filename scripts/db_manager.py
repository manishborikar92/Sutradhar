#!/usr/bin/env python3
"""Sutradhar SQLite state machine and Pydantic schema validator CLI facade.

Fixed zero-argument CLI commands (for Antigravity /automation whitelist):
    python scripts/db_manager.py --init
    python scripts/db_manager.py --context
    python scripts/db_manager.py --create-series
    python scripts/db_manager.py --record-published
    python scripts/db_manager.py --repair
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sutradhar.config import (  # noqa: E402
    LanguagePolicy,
    StateError,
    get_language_policy,
    get_project_root,
    load_config,
    load_json_file,
    resolve_paths,
    validate_config,
)
from sutradhar.db import (  # noqa: E402
    SCHEMA_SQL,
    SCHEMA_VERSION,
    cmd_context,
    cmd_create_series,
    cmd_init,
    cmd_record_published,
    cmd_repair,
    compute_pillar_rotation,
    connect_db,
    ensure_db_initialized,
    ensure_episodes_table_columns,
    heal_and_backfill_live_db,
    immediate_transaction,
    migrate_database_schema,
)
from sutradhar.models import (  # noqa: E402
    BESPOKE_ASSET_DIRS,
    CANONICAL_ASSET_PREFIXES,
    NARRATIVE_TEMPLATES,
    CharacterPlacement,
    ContextualPill,
    EpisodePlan,
    EpisodePlanV2,
    NewSeriesPlan,
    PropPlacement,
    PublishResult,
    ScenePlan,
    SceneVisualSpec,
    SeriesBible,
    SeriesBibleEpisode,
    StoryboardIR,
    StoryArc,
    StoryPhase,
    StoryResearch,
    ThumbnailSpec,
    _validate_audio_filename,
    _validate_bespoke_asset_path,
    _validate_configured_bgm,
    _validate_rig_slug,
    _validate_tts_voice,
    count_billed_chars,
    devanagari_token_ratio,
    emit_pacing_warnings,
    has_devanagari,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="db_manager.py",
        description="Sutradhar SQLite series & episode state manager.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init", action="store_true", help="Initialize episodes.db Schema v4")
    group.add_argument("--context", action="store_true", help="Print lean series, budget & rotation context JSON")
    group.add_argument("--create-series", action="store_true", help="Insert ACTIVE series from build/new_series_plan.json")
    group.add_argument("--record-published", action="store_true", help="Record episode from build/episode_plan.json & build/publish_result.json")
    group.add_argument("--repair", action="store_true", help="Recompute counters, backfill audit history & verify integrity")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        root = get_project_root()
        cfg = load_config(root)

        if args.init:
            result = cmd_init(root, cfg)
        elif args.context:
            result = cmd_context(root, cfg)
        elif args.create_series:
            result = cmd_create_series(root, cfg)
        elif args.record_published:
            result = cmd_record_published(root, cfg)
        elif args.repair:
            result = cmd_repair(root, cfg)
        else:
            raise StateError("No valid command flag provided.")

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except StateError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive catch-all
        print(f"[FATAL] Unexpected error: {exc}", file=sys.stderr)
        return 2


__all__ = [
    "BESPOKE_ASSET_DIRS",
    "CANONICAL_ASSET_PREFIXES",
    "NARRATIVE_TEMPLATES",
    "SCHEMA_SQL",
    "SCHEMA_VERSION",
    "CharacterPlacement",
    "ContextualPill",
    "EpisodePlan",
    "EpisodePlanV2",
    "LanguagePolicy",
    "NewSeriesPlan",
    "PropPlacement",
    "PublishResult",
    "ScenePlan",
    "SceneVisualSpec",
    "SeriesBible",
    "SeriesBibleEpisode",
    "StateError",
    "StoryboardIR",
    "StoryArc",
    "StoryPhase",
    "StoryResearch",
    "ThumbnailSpec",
    "ValidationError",
    "_validate_audio_filename",
    "_validate_bespoke_asset_path",
    "_validate_configured_bgm",
    "_validate_rig_slug",
    "_validate_tts_voice",
    "build_parser",
    "cmd_context",
    "cmd_create_series",
    "cmd_init",
    "cmd_record_published",
    "cmd_repair",
    "compute_pillar_rotation",
    "connect_db",
    "count_billed_chars",
    "devanagari_token_ratio",
    "emit_pacing_warnings",
    "ensure_db_initialized",
    "ensure_episodes_table_columns",
    "get_language_policy",
    "get_project_root",
    "has_devanagari",
    "heal_and_backfill_live_db",
    "immediate_transaction",
    "load_config",
    "load_json_file",
    "main",
    "migrate_database_schema",
    "resolve_paths",
    "validate_config",
]


if __name__ == "__main__":
    raise SystemExit(main())
