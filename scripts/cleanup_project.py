#!/usr/bin/env python3
"""Sutradhar Local Workspace & Database Cleanup Script.

Safely purges generated build artifacts, resets SQLite database,
and defragments storage after verifying that all required backups exist.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def verify_backups(root: Path) -> bool:
    """Ensure all required backups exist and are non-empty before any destructive action."""
    backup_dir = root / "backup"
    if not backup_dir.is_dir():
        print("[ERROR] Backup directory 'backup/' does not exist. Run backups first.", file=sys.stderr)
        return False

    # 1. Database SQL dump
    sql_dumps = list(backup_dir.glob("episodes_backup*.sql"))
    if not sql_dumps or not any(f.stat().st_size > 0 for f in sql_dumps):
        print("[ERROR] Missing non-empty database backup in backup/*.sql.", file=sys.stderr)
        return False

    # 2. Samples archive
    samples_archive = backup_dir / "samples_v2_archive"
    if not samples_archive.is_dir() or not any(samples_archive.iterdir()):
        print("[ERROR] Missing non-empty samples archive in backup/samples_v2_archive/.", file=sys.stderr)
        return False

    # 3. Config snapshot
    config_snapshot = backup_dir / "config_snapshot"
    if not config_snapshot.is_dir() or not (config_snapshot / "config.yaml").is_file():
        print("[ERROR] Missing config snapshot in backup/config_snapshot/.", file=sys.stderr)
        return False

    # 4. YouTube inventory
    yt_inventory = backup_dir / "youtube_inventory.json"
    if not yt_inventory.is_file() or yt_inventory.stat().st_size == 0:
        print("[ERROR] Missing non-empty YouTube inventory at backup/youtube_inventory.json.", file=sys.stderr)
        return False

    print("[OK] All pre-cleanup backups verified successfully:")
    print(f"  - Database dump: {sql_dumps[0].name} ({sql_dumps[0].stat().st_size} bytes)")
    print(f"  - Samples archive: {samples_archive.name} ({len(list(samples_archive.iterdir()))} directories)")
    print(f"  - Config snapshot: {config_snapshot.name} ({len(list(config_snapshot.iterdir()))} files)")
    print(f"  - YouTube inventory: {yt_inventory.name} ({yt_inventory.stat().st_size} bytes)")
    return True


def clean_build_directory(root: Path) -> list[str]:
    """Purge all ephemeral files and subdirectories in build/ and restore .gitkeep."""
    build_dir = root / "build"
    removed_items: list[str] = []

    if not build_dir.is_dir():
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / ".gitkeep").touch()
        return removed_items

    for item in build_dir.iterdir():
        if item.name == ".gitkeep":
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
                removed_items.append(f"dir: build/{item.name}/")
            else:
                item.unlink()
                removed_items.append(f"file: build/{item.name}")
        except Exception as exc:
            print(f"[WARN] Could not remove build item '{item.name}': {exc}", file=sys.stderr)

    # Ensure .gitkeep exists
    gitkeep = build_dir / ".gitkeep"
    if not gitkeep.is_file():
        gitkeep.touch()

    return removed_items


def clean_hyperframes_artifacts(root: Path) -> list[str]:
    """Clean ephemeral HyperFrames check/snapshot artifacts."""
    artifacts_dir = root / ".hyperframes" / "artifacts"
    removed: list[str] = []
    if not artifacts_dir.is_dir():
        return removed

    for sub in ["checks", "snapshots"]:
        target = artifacts_dir / sub
        if target.is_dir():
            count = len(list(target.iterdir()))
            if count > 0:
                shutil.rmtree(target)
                target.mkdir(parents=True, exist_ok=True)
                removed.append(f"hyperframes: .hyperframes/artifacts/{sub}/ ({count} items purged)")
    return removed


def clean_database(root: Path) -> dict[str, Any]:
    """Reset all records and auto-increment counters in episodes.db, then VACUUM."""
    db_path = root / "episodes.db"
    if not db_path.is_file():
        print(f"[WARN] Database file not found at {db_path}.", file=sys.stderr)
        return {"status": "skipped", "reason": "file_not_found"}

    initial_size = db_path.stat().st_size
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM episodes;")
        ep_count = cur.rowcount
        cur.execute("DELETE FROM series;")
        series_count = cur.rowcount
        # Reset autoincrement sequence
        seq_exists = cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if seq_exists:
            cur.execute("DELETE FROM sqlite_sequence;")
        conn.commit()
    finally:
        conn.close()

    # VACUUM in separate connection
    conn2 = sqlite3.connect(str(db_path))
    conn2.execute("VACUUM;")
    integrity = conn2.execute("PRAGMA integrity_check;").fetchone()[0]
    final_series = conn2.execute("SELECT COUNT(*) FROM series;").fetchone()[0]
    final_episodes = conn2.execute("SELECT COUNT(*) FROM episodes;").fetchone()[0]
    conn2.close()

    final_size = db_path.stat().st_size
    return {
        "status": "ok",
        "deleted_episodes": ep_count,
        "deleted_series": series_count,
        "integrity_check": integrity,
        "final_series_count": final_series,
        "final_episodes_count": final_episodes,
        "initial_size_bytes": initial_size,
        "final_size_bytes": final_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sutradhar Workspace & Database Cleanup")
    parser.add_argument("--execute", action="store_true", help="Execute local cleanup (build artifacts, HyperFrames, database)")
    args = parser.parse_args()

    root = REPO_ROOT

    if not args.execute:
        print("[INFO] Running cleanup in DRY-RUN mode. Pass --execute to perform local cleanup.")
        if verify_backups(root):
            print("\nBackups: VERIFIED")
            print("Actions that would be executed with --execute:")
            print("  1. Purge all files and subdirectories in build/ (restoring build/.gitkeep)")
            print("  2. Purge check/snapshot artifacts in .hyperframes/artifacts/")
            print("  3. Reset episodes and series tables in episodes.db, reset sqlite_sequence, and VACUUM")
            return 0
        else:
            return 1

    print("=== Step 1: Backup Verification ===")
    if not verify_backups(root):
        print("[FATAL] Backup verification failed. Aborting cleanup.", file=sys.stderr)
        return 1

    print("\n=== Step 2: Build Directory Cleanup ===")
    removed_build = clean_build_directory(root)
    print(f"[OK] Cleaned {len(removed_build)} items from build/:")
    for item in removed_build:
        print(f"  - Removed {item}")

    print("\n=== Step 3: HyperFrames Artifacts Cleanup ===")
    removed_hf = clean_hyperframes_artifacts(root)
    for item in removed_hf:
        print(f"  - {item}")

    print("\n=== Step 4: Database Reset & VACUUM ===")
    db_res = clean_database(root)
    print(f"[OK] Database reset complete:")
    print(f"  - Deleted series records: {db_res['deleted_series']}")
    print(f"  - Deleted episode records: {db_res['deleted_episodes']}")
    print(f"  - Active series remaining: {db_res['final_series_count']}")
    print(f"  - Episodes remaining: {db_res['final_episodes_count']}")
    print(f"  - Database integrity check: {db_res['integrity_check']}")
    print(f"  - Size: {db_res['initial_size_bytes']} bytes -> {db_res['final_size_bytes']} bytes")

    print("\n[SUCCESS] Local workspace cleanup completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
