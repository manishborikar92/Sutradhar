#!/usr/bin/env python3
"""Thin re-export facade for thumbnail validation & YouTube CDN parity checks."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from sutradhar.publishing.thumbnail_verifier import (  # noqa: E402
    SHORTS_2X3_CROP_BOX,
    YOUTUBE_MAX_THUMBNAIL_BYTES,
    ThumbnailValidationError,
    ThumbnailVerificationError,
    compare_thumbnail_images,
    compute_dhash,
    fetch_cdn_image,
    hamming_distance,
    upload_thumbnail_and_verify,
    validate_2x3_crop_bounds,
    validate_local_thumbnail,
    verify_live_sardefault_parity,
    wait_for_video_processing,
)

__all__ = [
    "SHORTS_2X3_CROP_BOX",
    "YOUTUBE_MAX_THUMBNAIL_BYTES",
    "ThumbnailValidationError",
    "ThumbnailVerificationError",
    "compare_thumbnail_images",
    "compute_dhash",
    "fetch_cdn_image",
    "hamming_distance",
    "upload_thumbnail_and_verify",
    "validate_2x3_crop_bounds",
    "validate_local_thumbnail",
    "verify_live_sardefault_parity",
    "wait_for_video_processing",
]
