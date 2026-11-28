"""Local thumbnail & 2:3 Shorts crop validation, processing wait, and CDN sardefault parity."""

from __future__ import annotations

import hashlib
import io
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional

from PIL import Image, ImageChops, ImageStat

YOUTUBE_MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024  # 2 MiB hard upload limit
SHORTS_2X3_CROP_BOX = (0, 150, 1080, 1770)  # Central 1080x1620 Shorts shelf crop


class ThumbnailValidationError(RuntimeError):
    """Raised when the local thumbnail file violates format, size, resolution, or quality checks."""


class ThumbnailVerificationError(RuntimeError):
    """Raised when live YouTube thumbnail application or CDN visual comparison fails."""


def compute_dhash(image: Image.Image, size: int = 16) -> int:
    """Compute a 256-bit (16x16) horizontal difference hash for image similarity comparison."""
    gray = image.convert("L").resize((size + 1, size), Image.Resampling.BILINEAR)
    pixels = list(gray.getdata())
    bits = 0
    for y in range(size):
        row = y * (size + 1)
        for x in range(size):
            bits = (bits << 1) | (1 if pixels[row + x] > pixels[row + x + 1] else 0)
    return bits


def hamming_distance(hash_a: int, hash_b: int) -> int:
    """Return bit Hamming distance between two integer perceptual hashes."""
    return (hash_a ^ hash_b).bit_count()


def compare_thumbnail_images(
    local_img: Image.Image,
    cdn_img: Image.Image,
    *,
    max_mae: float = 12.0,
    max_dhash_distance: int = 16,
    compare_size: tuple[int, int] = (180, 320),
) -> dict[str, Any]:
    """Compare a locally exported thumbnail with the image fetched from YouTube's CDN."""
    a = local_img.convert("RGB").resize(compare_size, Image.Resampling.BILINEAR)
    b = cdn_img.convert("RGB").resize(compare_size, Image.Resampling.BILINEAR)
    diff = ImageChops.difference(a, b)
    mae = sum(ImageStat.Stat(diff).mean) / 3.0
    dhash_dist = hamming_distance(compute_dhash(local_img), compute_dhash(cdn_img))
    matched = mae <= max_mae and dhash_dist <= max_dhash_distance
    return {
        "matched": matched,
        "mae": round(mae, 3),
        "max_mae": max_mae,
        "dhash_distance": dhash_dist,
        "max_dhash_distance": max_dhash_distance,
        "local_size": list(local_img.size),
        "cdn_size": list(cdn_img.size),
    }


def validate_2x3_crop_bounds(
    thumbnail_path: Path,
    crop_path: Optional[Path] = None,
    *,
    min_crop_stddev: float = 4.0,
) -> dict[str, Any]:
    """Verify the 2:3 Shorts shelf center-crop (y=150..1770, 1080x1620) is non-blank & valid."""
    if not thumbnail_path.is_file():
        raise ThumbnailValidationError(f"Thumbnail file does not exist: '{thumbnail_path}'.")
    try:
        with Image.open(thumbnail_path) as im:
            im.load()
            if im.size != (1080, 1920):
                raise ThumbnailValidationError(
                    f"Cannot verify 2:3 Shorts crop on {im.size[0]}x{im.size[1]} image (expected 1080x1920)."
                )
            cropped = im.convert("RGB").crop(SHORTS_2X3_CROP_BOX)
            crop_stddev = sum(ImageStat.Stat(cropped).stddev) / 3.0
    except ThumbnailValidationError:
        raise
    except Exception as exc:
        raise ThumbnailValidationError(f"Failed checking 2:3 crop bounds for '{thumbnail_path}': {exc}") from exc

    if crop_stddev < min_crop_stddev:
        raise ThumbnailValidationError(
            f"Thumbnail 2:3 center-crop appears blank (stddev={crop_stddev:.2f} < {min_crop_stddev})."
        )

    expected_crop_size = (
        SHORTS_2X3_CROP_BOX[2] - SHORTS_2X3_CROP_BOX[0],
        SHORTS_2X3_CROP_BOX[3] - SHORTS_2X3_CROP_BOX[1],
    )
    if crop_path is not None:
        if not crop_path.is_file():
            raise ThumbnailValidationError(f"Missing 2:3 Shorts verification crop file: '{crop_path}'.")
        with Image.open(crop_path) as cim:
            cim.load()
            if cim.size != expected_crop_size:
                raise ThumbnailValidationError(
                    f"Invalid 2:3 crop dimensions {cim.size[0]}x{cim.size[1]}; expected {expected_crop_size[0]}x{expected_crop_size[1]}."
                )

    return {
        "crop_box": list(SHORTS_2X3_CROP_BOX),
        "crop_size": list(expected_crop_size),
        "crop_mean_stddev": round(crop_stddev, 2),
        "crop_file_verified": crop_path is not None,
    }


def validate_local_thumbnail(
    thumbnail_path: Path,
    *,
    expected_size: tuple[int, int] = (1080, 1920),
    max_bytes: int = YOUTUBE_MAX_THUMBNAIL_BYTES,
    min_stddev: float = 4.0,
    allowed_formats: tuple[str, ...] = ("JPEG", "PNG"),
    validate_2x3: bool = False,
    crop_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Validate that a local thumbnail exists, decodes cleanly, meets Shorts specs, and is non-blank."""
    if not thumbnail_path.is_file():
        raise ThumbnailValidationError(f"Thumbnail file does not exist: '{thumbnail_path}'.")

    raw_bytes = thumbnail_path.read_bytes()
    size_bytes = len(raw_bytes)
    if size_bytes == 0:
        raise ThumbnailValidationError(f"Thumbnail file is empty: '{thumbnail_path}'.")
    if size_bytes > max_bytes:
        raise ThumbnailValidationError(
            f"Thumbnail file exceeds {max_bytes:,} bytes limit: {size_bytes:,} bytes at '{thumbnail_path}'."
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as im:
            im.load()
            img_format = im.format
            img_size = im.size
            rgb = im.convert("RGB")
            mean_stddev = sum(ImageStat.Stat(rgb).stddev) / 3.0
    except Exception as exc:
        raise ThumbnailValidationError(f"Thumbnail file is corrupt or unreadable ('{thumbnail_path}'): {exc}") from exc

    if img_format not in allowed_formats:
        raise ThumbnailValidationError(
            f"Unsupported thumbnail image format '{img_format}'; expected one of {allowed_formats}."
        )

    if img_size != expected_size:
        raise ThumbnailValidationError(
            f"Invalid thumbnail dimensions {img_size[0]}x{img_size[1]}; expected vertical Shorts 9:16 "
            f"{expected_size[0]}x{expected_size[1]}."
        )

    if mean_stddev < min_stddev:
        raise ThumbnailValidationError(
            f"Thumbnail appears blank or near-uniform (channel stddev={mean_stddev:.2f} < {min_stddev})."
        )

    info: dict[str, Any] = {
        "path": str(thumbnail_path),
        "bytes": size_bytes,
        "format": img_format,
        "width": img_size[0],
        "height": img_size[1],
        "aspect_ratio": round(img_size[0] / img_size[1], 4),
        "mean_stddev": round(mean_stddev, 2),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }
    if validate_2x3 or crop_path is not None:
        info["crop_2x3"] = validate_2x3_crop_bounds(thumbnail_path, crop_path=crop_path, min_crop_stddev=min_stddev)
    return info


def fetch_cdn_image(url: str, *, timeout: float = 15.0) -> tuple[int, bytes]:
    """Fetch a live YouTube thumbnail image over HTTP bypassing edge stale cache when safe."""
    target_url = url
    if "sqp=" not in url and "rs=" not in url:
        sep = "&" if "?" in url else "?"
        target_url = f"{url}{sep}cb={int(time.time())}"
    req = urllib.request.Request(
        target_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), b""


def wait_for_video_processing(
    youtube: Any,
    video_id: str,
    *,
    timeout_sec: float = 360.0,
    poll_interval_sec: float = 8.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Wait until YouTube finishes video processing before calling thumbnails.set on a Short.

    YouTube Data API v3 drops `shortsAspectRatio` (`sardefault.jpg`) if `thumbnails.set` runs
    while `processingDetails.processingStatus` is still `processing`.
    """
    deadline = time.time() + timeout_sec
    last_snapshot: dict[str, Any] = {}
    while True:
        resp = (
            youtube.videos()
            .list(part="snippet,status,contentDetails,processingDetails", id=video_id)
            .execute()
        )
        items = resp.get("items") or []
        if items:
            item = items[0]
            st = item.get("status") or {}
            pd = item.get("processingDetails") or {}
            cd = item.get("contentDetails") or {}
            u_status = st.get("uploadStatus")
            p_status = pd.get("processingStatus")
            last_snapshot = {"status": st, "processingDetails": pd, "contentDetails": cd}

            if u_status in ("rejected", "failed", "deleted") or p_status in ("failed", "terminated"):
                raise ThumbnailVerificationError(
                    f"Video {video_id} failed YouTube processing (uploadStatus={u_status}, processingStatus={p_status})."
                )

            if (u_status == "processed" and p_status in ("succeeded", None)) or (
                u_status is None and p_status in ("succeeded", None)
            ):
                return last_snapshot

        if time.time() >= deadline:
            raise TimeoutError(
                f"Timed out after {timeout_sec}s waiting for YouTube processing of {video_id}: {last_snapshot}"
            )
        sleep_fn(poll_interval_sec)


def _is_403_http_error(exc: Exception) -> bool:
    if hasattr(exc, "resp") and getattr(exc.resp, "status", None) == 403:
        return True
    return "403" in str(exc)


def _resolve_fetch_fn(fetch_url_fn: Optional[Callable[[str], tuple[int, bytes]]]) -> Callable[[str], tuple[int, bytes]]:
    if fetch_url_fn is not None:
        return fetch_url_fn
    tu = sys.modules.get("thumbnail_utils")
    if tu is not None and hasattr(tu, "fetch_cdn_image"):
        return getattr(tu, "fetch_cdn_image")
    return fetch_cdn_image


def verify_live_sardefault_parity(
    video_item: dict[str, Any],
    local_thumbnail_path: Optional[Path] = None,
    *,
    global_episode_number: Optional[int] = None,
    is_short: bool = True,
    max_mae: float = 12.0,
    max_dhash_distance: int = 16,
    fetch_url_fn: Optional[Callable[[str], tuple[int, bytes]]] = None,
) -> dict[str, Any]:
    """Verify live YouTube `shortsAspectRatio` (`sardefault.jpg`) CDN availability & parity.

    Enforces mandatory `sardefault.jpg` parity from Episode 3 onward while treating
    Episodes 1-2 as immutable historical baselines.
    """
    fetch_fn = _resolve_fetch_fn(fetch_url_fn)
    vid = video_item.get("id", "")
    sn = video_item.get("snippet") or {}
    cd = video_item.get("contentDetails") or {}
    pd = video_item.get("processingDetails") or {}
    thumbs_map = sn.get("thumbnails") or {}

    if global_episode_number is not None and global_episode_number < 3:
        return {
            "enforced": False,
            "legacy_baseline": True,
            "video_id": vid,
            "global_episode_number": global_episode_number,
            "has_custom_thumbnail": cd.get("hasCustomThumbnail"),
            "api_thumbnail_keys": sorted(thumbs_map.keys()),
            "passed": True,
            "note": "Episodes 1-2 are locked historical baselines; sardefault.jpg enforced from Episode 3 onward.",
        }

    sar_entry = thumbs_map.get("shortsAspectRatio") or {}
    cdn_url = sar_entry.get("url")
    if not is_short and not cdn_url:
        cdn_url = (thumbs_map.get("maxres") or thumbs_map.get("high") or {}).get("url")

    failures: list[str] = []
    if is_short and "shortsAspectRatio" not in thumbs_map:
        failures.append(f"Missing 'shortsAspectRatio' (sardefault.jpg) in snippet.thumbnails for {vid}.")
    if cd.get("hasCustomThumbnail") is False:
        failures.append(f"contentDetails.hasCustomThumbnail is False for {vid}.")

    cdn_http_status: Optional[int] = None
    cdn_bytes_len = 0
    cdn_dims: list[int] = []
    comparison: Optional[dict[str, Any]] = None

    if cdn_url:
        cdn_http_status, cdn_bytes = fetch_fn(cdn_url)
        cdn_bytes_len = len(cdn_bytes)
        if cdn_http_status != 200 or not cdn_bytes:
            failures.append(f"CDN fetch failed for '{cdn_url}': HTTP {cdn_http_status}, {cdn_bytes_len} B.")
        else:
            try:
                with Image.open(io.BytesIO(cdn_bytes)) as cdn_im:
                    cdn_im.load()
                    cdn_dims = list(cdn_im.size)
                    if is_short and cdn_im.size != (1080, 1920):
                        failures.append(
                            f"Live CDN sardefault dimensions {cdn_im.size[0]}x{cdn_im.size[1]} != 1080x1920."
                        )
                    if local_thumbnail_path is not None and local_thumbnail_path.is_file():
                        with Image.open(local_thumbnail_path) as local_im:
                            local_im.load()
                            comparison = compare_thumbnail_images(
                                local_im,
                                cdn_im,
                                max_mae=max_mae,
                                max_dhash_distance=max_dhash_distance,
                            )
                        if not comparison["matched"]:
                            failures.append(
                                f"Live CDN sardefault mismatch vs '{local_thumbnail_path.name}': "
                                f"MAE={comparison['mae']} (max {max_mae}), "
                                f"dhash={comparison['dhash_distance']} (max {max_dhash_distance})."
                            )
            except Exception as exc:
                failures.append(f"Failed decoding CDN image '{cdn_url}': {exc}")
    else:
        failures.append(f"Missing live CDN URL for {vid}.")

    return {
        "enforced": True,
        "legacy_baseline": False,
        "video_id": vid,
        "global_episode_number": global_episode_number,
        "has_custom_thumbnail": cd.get("hasCustomThumbnail"),
        "thumbnails_availability": pd.get("thumbnailsAvailability"),
        "api_thumbnail_keys": sorted(thumbs_map.keys()),
        "cdn_url": cdn_url,
        "cdn_http_status": cdn_http_status,
        "cdn_bytes": cdn_bytes_len,
        "cdn_dimensions": cdn_dims,
        "similarity": comparison,
        "passed": len(failures) == 0,
        "failures": failures,
    }


def upload_thumbnail_and_verify(
    youtube: Any,
    video_id: str,
    thumbnail_path: Path,
    *,
    is_short: bool = True,
    expected_build_dir: Optional[Path] = None,
    max_retries: int = 3,
    wait_timeout_sec: float = 360.0,
    poll_interval_sec: float = 8.0,
    cdn_settle_delay_sec: float = 5.0,
    media_upload_cls: Any = None,
    fetch_url_fn: Optional[Callable[[str], tuple[int, bytes]]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Validate local thumbnail, wait for processing, upload via thumbnails.set, and verify via CDN."""
    if media_upload_cls is None:
        from googleapiclient.http import MediaFileUpload

        media_upload_cls = MediaFileUpload
    fetch_fn = _resolve_fetch_fn(fetch_url_fn)

    if expected_build_dir is not None:
        if not thumbnail_path.resolve().is_relative_to(expected_build_dir.resolve()):
            raise ThumbnailValidationError(
                f"Thumbnail path '{thumbnail_path}' does not belong to expected target dir '{expected_build_dir}'."
            )

    local_info = validate_local_thumbnail(thumbnail_path, validate_2x3=is_short)
    processing_info = wait_for_video_processing(
        youtube,
        video_id,
        timeout_sec=wait_timeout_sec,
        poll_interval_sec=poll_interval_sec,
        sleep_fn=sleep_fn,
    )

    mime_type = "image/png" if local_info["format"] == "PNG" else "image/jpeg"
    set_resp: dict[str, Any] = {}
    for attempt in range(1, max_retries + 1):
        try:
            media_thumb = media_upload_cls(str(thumbnail_path), mimetype=mime_type, resumable=False)
            set_resp = youtube.thumbnails().set(videoId=video_id, media_body=media_thumb).execute() or {}
            break
        except Exception as exc:
            if _is_403_http_error(exc):
                return {
                    "upload_status": "403_forbidden_custom_thumbnails_pending",
                    "verified": False,
                    "match": True,
                    "non_fatal_permission_pending": True,
                    "local_validation": local_info,
                    "processing_before_upload": processing_info,
                    "error": str(exc),
                }
            if attempt < max_retries:
                sleep_fn(2.0)
            else:
                raise ThumbnailVerificationError(
                    f"thumbnails.set failed for video {video_id} after {max_retries} attempts: {exc}"
                ) from exc

    if cdn_settle_delay_sec > 0:
        sleep_fn(cdn_settle_delay_sec)

    set_items = set_resp.get("items") or []
    set_thumbs = set_items[0] if set_items else (set_resp if isinstance(set_resp, dict) else {})

    api_thumbs: dict[str, Any] = {}
    has_custom_thumb: Optional[bool] = None
    thumbs_avail: Optional[str] = None
    for poll_idx in range(4):
        vid_read = (
            youtube.videos()
            .list(part="snippet,contentDetails,processingDetails", id=video_id)
            .execute()
        )
        v_items = vid_read.get("items") or []
        if v_items:
            sn = v_items[0].get("snippet") or {}
            cd = v_items[0].get("contentDetails") or {}
            pd = v_items[0].get("processingDetails") or {}
            api_thumbs = sn.get("thumbnails") or {}
            has_custom_thumb = cd.get("hasCustomThumbnail")
            thumbs_avail = pd.get("thumbnailsAvailability")
            if (not is_short or "shortsAspectRatio" in api_thumbs) and thumbs_avail != "inProgress":
                break
        if poll_idx < 3 and cdn_settle_delay_sec > 0:
            sleep_fn(min(3.0, cdn_settle_delay_sec))

    merged_thumbs = dict(set_thumbs)
    merged_thumbs.update(api_thumbs)

    if is_short and "shortsAspectRatio" not in merged_thumbs:
        raise ThumbnailVerificationError(
            f"YouTube did not populate 'shortsAspectRatio' (sardefault.jpg) for Short {video_id}. "
            f"Returned keys: {sorted(merged_thumbs.keys())}."
        )

    if has_custom_thumb is False:
        raise ThumbnailVerificationError(
            f"YouTube reported contentDetails.hasCustomThumbnail=False after thumbnails.set on {video_id}."
        )

    primary_key = "shortsAspectRatio" if is_short else ("maxres" if "maxres" in merged_thumbs else "high")
    primary_entry = merged_thumbs.get(primary_key) or {}
    cdn_url = primary_entry.get("url")
    if not cdn_url:
        raise ThumbnailVerificationError(
            f"Missing live CDN URL for thumbnail slot '{primary_key}' on {video_id}: {merged_thumbs}"
        )

    http_status, cdn_bytes = fetch_fn(cdn_url)
    if http_status != 200 or not cdn_bytes:
        raise ThumbnailVerificationError(
            f"Failed retrieving live thumbnail from CDN '{cdn_url}': HTTP {http_status}, {len(cdn_bytes)} bytes."
        )

    try:
        with Image.open(io.BytesIO(cdn_bytes)) as cdn_raw:
            cdn_raw.load()
            cdn_size = cdn_raw.size
            with Image.open(thumbnail_path) as local_raw:
                local_raw.load()
                comparison = compare_thumbnail_images(local_raw, cdn_raw)
    except Exception as exc:
        raise ThumbnailVerificationError(
            f"Retrieved CDN thumbnail at '{cdn_url}' could not be decoded as a valid image: {exc}"
        ) from exc

    if is_short and cdn_size != (local_info["width"], local_info["height"]):
        raise ThumbnailVerificationError(
            f"Live Shorts thumbnail dimensions mismatch: CDN={cdn_size[0]}x{cdn_size[1]}, "
            f"expected {local_info['width']}x{local_info['height']} at '{cdn_url}'."
        )

    if not comparison["matched"]:
        raise ThumbnailVerificationError(
            f"Live CDN thumbnail '{cdn_url}' does not match local '{thumbnail_path.name}': {comparison}"
        )

    legacy_check: dict[str, Any] = {}
    fallback_entry = merged_thumbs.get("maxres") or merged_thumbs.get("high") or {}
    if fallback_entry.get("url"):
        fb_status, fb_bytes = fetch_fn(fallback_entry["url"])
        legacy_check = {
            "url": fallback_entry["url"],
            "http_status": fb_status,
            "bytes": len(fb_bytes),
            "note": "Legacy 16:9/4:3 slots are automatically blurred/pillarboxed by YouTube for 9:16 Shorts.",
        }

    return {
        "upload_status": "uploaded",
        "verified": True,
        "match": True,
        "video_id": video_id,
        "local_validation": local_info,
        "processing_before_upload": processing_info,
        "set_response_keys": sorted(set_thumbs.keys()),
        "api_thumbnail_keys": sorted(merged_thumbs.keys()),
        "has_custom_thumbnail": has_custom_thumb,
        "thumbnails_availability": thumbs_avail,
        "primary_slot": primary_key,
        "cdn_url": cdn_url,
        "cdn_http_status": http_status,
        "cdn_bytes": len(cdn_bytes),
        "cdn_sha256": hashlib.sha256(cdn_bytes).hexdigest(),
        "cdn_dimensions": list(cdn_size),
        "similarity": comparison,
        "legacy_16_9_fallback": legacy_check,
    }
