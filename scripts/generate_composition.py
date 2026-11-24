#!/usr/bin/env python3
"""Sutradhar — Composition Generator CLI & Engine Bridge (v4.0).

Delegates directly to scripts.engine.composer for Jinja2 template rendering
under build/composition/ (strictly eliminating repo root code pollution).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.engine.composer import (  # noqa: E402
    CompositionError,
    compose_episode,
    generate_composition,
)


def generate_root_composition(root: Optional[Path] = None) -> dict[str, Any]:
    """Generates composition into build/composition/ using the v4.0 Jinja2 engine."""
    if root is None:
        root = REPO_ROOT
    return compose_episode(root)


if __name__ == "__main__":
    res = generate_root_composition(REPO_ROOT)
    print(
        f"[INFO] Composition generated at {res['composition_dir']} "
        f"({res['scenes_count']} shots, {len(res['characters'])} puppets)"
    )
