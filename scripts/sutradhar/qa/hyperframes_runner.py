"""Local HyperFrames CLI & headless Chromium/Puppeteer verification wrapper."""

from __future__ import annotations

import base64
import contextlib
import functools
import http.server
import io
import json
import os
import re
import shutil
import socketserver
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Iterator, Optional

import numpy as np
from PIL import Image, ImageDraw

from sutradhar.audio.whisper_aligner import write_text_atomic

_SENTINEL = "___SUTRADHAR_PROBE_JSON___"


class HyperFramesError(RuntimeError):
    """Raised when local HyperFrames CLI execution or Chromium probing fails."""


def find_hyperframes_cli(root: Path) -> tuple[str, Path]:
    """Locate local Node binary and repo-installed hyperframes.mjs (never uses npx)."""
    root = Path(root).resolve()
    node_exe = shutil.which("node.exe") or shutil.which("node")
    if not node_exe:
        raise HyperFramesError("node executable not found on PATH")
    hf_cli = root / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    if not hf_cli.is_file():
        raise HyperFramesError(f"Local HyperFrames CLI missing at {hf_cli}")
    return node_exe, hf_cli


def find_chromium_executable() -> Path:
    """Locate cached HyperFrames Chrome/chrome-headless-shell or explicit CHROME_PATH."""
    env_chrome = os.environ.get("CHROME_PATH") or os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if env_chrome:
        candidate = Path(env_chrome)
        if candidate.is_file():
            return candidate

    cache_root = Path.home() / ".cache" / "hyperframes" / "chrome"
    names = ("chrome-headless-shell.exe", "chrome.exe", "chrome-headless-shell", "chrome")
    if cache_root.is_dir():
        found: list[Path] = []
        for pattern in names:
            found.extend(cache_root.rglob(pattern))
        found = [p for p in found if p.is_file()]
        if found:
            found.sort(key=lambda p: str(p), reverse=True)
            return found[0]

    raise HyperFramesError(
        f"Headless Chromium executable not found in {cache_root} or CHROME_PATH"
    )


class _QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def copyfile(self, source: Any, outputfile: Any) -> None:
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


@contextlib.contextmanager
def serve_directory(directory: Path) -> Iterator[str]:
    """Serve a composition directory over localhost with ephemeral port."""
    directory = Path(directory).resolve()
    handler = functools.partial(_QuietHTTPHandler, directory=str(directory))
    server = _ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def _extract_json_blob(raw_stdout: str) -> dict[str, Any]:
    text = raw_stdout.strip()
    if not text:
        raise HyperFramesError("Empty JSON output from HyperFrames command")
    if _SENTINEL in text:
        after = text.split(_SENTINEL, 1)[1].strip().splitlines()[0].strip()
        return json.loads(after)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Handle occasional multi-line notices preceding the trailing JSON object
        for idx in range(len(text) - 1, -1, -1):
            if text[idx] == "{":
                candidate = text[idx:]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        raise HyperFramesError(f"Could not parse JSON from output: {text[-400:]}")


def run_node_puppeteer(
    root: Path,
    script_body: str,
    payload: dict[str, Any],
    *,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    """Execute a Node script using repo-local puppeteer-core and cached Chromium."""
    root = Path(root).resolve()
    node_exe, _ = find_hyperframes_cli(root)
    puppeteer_pkg = root / "node_modules" / "puppeteer-core"
    if not puppeteer_pkg.is_dir():
        raise HyperFramesError(f"puppeteer-core missing at {puppeteer_pkg}")
    chrome_exe = find_chromium_executable()

    with tempfile.TemporaryDirectory(prefix="hf_probe_", ignore_cleanup_errors=True) as td:
        td_path = Path(td)
        payload_path = td_path / "payload.json"
        script_path = td_path / "probe.mjs"
        write_text_atomic(payload_path, json.dumps(payload, ensure_ascii=False))
        wrapper = f"""import fs from "node:fs";
import {{ pathToFileURL }} from "node:url";

const puppeteerMod = await import(pathToFileURL({json.dumps(str(puppeteer_pkg / "lib" / "puppeteer" / "puppeteer-core.js"))}).href);
const puppeteer = puppeteerMod.default || puppeteerMod;
const payload = JSON.parse(fs.readFileSync({json.dumps(str(payload_path))}, "utf8"));
const chromeExecutable = {json.dumps(str(chrome_exe))};
const browser = await puppeteer.launch({{
  executablePath: chromeExecutable,
  headless: {json.dumps("shell" if "headless-shell" in chrome_exe.name.lower() else True)},
  args: [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
}});
try {{
  const runProbe = async (payload, browser) => {{
{script_body}
  }};
  const result = await runProbe(payload, browser);
  process.stdout.write({json.dumps(_SENTINEL)} + JSON.stringify(result) + "\\n");
}} finally {{
  await browser.close();
}}
"""
        write_text_atomic(script_path, wrapper)
        proc = subprocess.run(
            [node_exe, str(script_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if proc.returncode != 0:
            raise HyperFramesError(
                f"Chromium Puppeteer probe failed (exit={proc.returncode}): "
                f"{(proc.stderr or proc.stdout)[-800:]}"
            )
        return _extract_json_blob(proc.stdout)


def run_hf_lint(root: Path, project_dir: Path, *, timeout_sec: int = 60) -> dict[str, Any]:
    """Run ``hyperframes lint <dir> --json`` without invoking npx."""
    node_exe, hf_cli = find_hyperframes_cli(root)
    proc = subprocess.run(
        [node_exe, str(hf_cli), "lint", str(project_dir), "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    try:
        parsed = _extract_json_blob(proc.stdout or proc.stderr)
    except HyperFramesError as exc:
        raise HyperFramesError(
            f"hyperframes lint failed (exit={proc.returncode}): {(proc.stderr or proc.stdout)[-500:]}"
        ) from exc
    parsed.setdefault("exit_code", proc.returncode)
    raw_ok = bool(parsed.get("ok", proc.returncode == 0))
    err_cnt = int(parsed.get("errorCount") or 0)
    warn_cnt = int(parsed.get("warningCount") or 0)
    parsed["raw_ok"] = raw_ok
    parsed["ok"] = (proc.returncode == 0) and raw_ok and err_cnt == 0 and warn_cnt == 0
    return parsed


def _collect_hf_check_issues(check_res: dict[str, Any]) -> tuple[int, int, list[str]]:
    """Count all errors and warnings across top-level and sub-report sections of `hyperframes check`."""
    total_errors = 0
    total_warnings = 0
    issues: list[str] = []

    if check_res.get("raw_ok", check_res.get("ok")) is False:
        issues.append("hyperframes check reported ok=false")
    exit_code = check_res.get("exit_code")
    if exit_code not in (None, 0):
        issues.append(f"hyperframes check exited with code {exit_code}")

    top_errs = check_res.get("errors") or []
    top_warns = check_res.get("warnings") or []
    top_err_cnt = int(check_res.get("errorCount") or 0)
    top_warn_cnt = int(check_res.get("warningCount") or 0)
    if top_err_cnt or top_errs:
        total_errors += max(top_err_cnt, len(top_errs))
        for item in top_errs:
            issues.append(f"top-level error: {item}")
    if top_warn_cnt or top_warns:
        total_warnings += max(top_warn_cnt, len(top_warns))
        for item in top_warns:
            issues.append(f"top-level warning: {item}")

    section_names = ("lint", "runtime", "layout", "motion", "contrast", "craft", "audio")
    seen_sections: set[str] = set()
    ordered_sections: list[tuple[str, dict[str, Any]]] = []
    for name in section_names:
        val = check_res.get(name)
        if isinstance(val, dict):
            seen_sections.add(name)
            ordered_sections.append((name, val))
    for name, val in check_res.items():
        if name not in seen_sections and isinstance(val, dict) and any(
            k in val for k in ("errorCount", "warningCount", "findings", "errors", "warnings")
        ):
            ordered_sections.append((name, val))

    for sec_name, sec in ordered_sections:
        sec_findings = sec.get("findings") or []
        sec_errs = sec.get("errors") or []
        sec_warns = sec.get("warnings") or []
        finding_errs = [f for f in sec_findings if isinstance(f, dict) and f.get("severity") == "error"]
        finding_warns = [f for f in sec_findings if isinstance(f, dict) and f.get("severity") == "warning"]

        sec_err_cnt = max(int(sec.get("errorCount") or 0), len(finding_errs), len(sec_errs))
        sec_warn_cnt = max(int(sec.get("warningCount") or 0), len(finding_warns), len(sec_warns))
        total_errors += sec_err_cnt
        total_warnings += sec_warn_cnt

        for f in finding_errs + finding_warns:
            code = f.get("code") or "finding"
            sev = f.get("severity") or "issue"
            msg = f.get("message") or str(f)
            issues.append(f"{sec_name}.{code} ({sev}): {msg}")
        for item in sec_errs:
            issues.append(f"{sec_name} error: {item}")
        for item in sec_warns:
            issues.append(f"{sec_name} warning: {item}")
        if sec_err_cnt > 0 and not finding_errs and not sec_errs:
            issues.append(f"{sec_name}: errorCount={sec_err_cnt}")
        if sec_warn_cnt > 0 and not finding_warns and not sec_warns:
            issues.append(f"{sec_name}: warningCount={sec_warn_cnt}")

    return total_errors, total_warnings, issues


def validate_hf_check_report(check_res: dict[str, Any]) -> list[str]:
    """Fail closed unless `hyperframes check` reports ok=true with 0 errors and 0 warnings everywhere."""
    total_errors, total_warnings, issues = _collect_hf_check_issues(check_res)
    if total_errors == 0 and total_warnings == 0 and not issues:
        return []
    if not issues:
        issues.append(f"total_errors={total_errors}, total_warnings={total_warnings}")
    return [
        f"hyperframes check --strict --safe-zone shorts failed "
        f"(errors={total_errors}, warnings={total_warnings}): " + "; ".join(issues)
    ]


def validate_runtime_probe_and_hf_check(
    probe_res: dict[str, Any],
    hf_check_res: dict[str, Any] | None = None,
    *,
    caption_safe_bottom_max: float = 1395.0,
    pill_min_x: float = 48.0,
    pill_max_x: float = 888.0,
    pill_min_y: float = 288.0,
    pill_max_y: float = 1248.0,
) -> list[str]:
    """Shared fail-closed validation for Chromium DOM/seek probe and HyperFrames Shorts check."""
    failures: list[str] = []
    if probe_res.get("console_errors") or probe_res.get("page_errors") or probe_res.get("failed_requests"):
        failures.append(
            f"chromium runtime errors: console={probe_res.get('console_errors')}, "
            f"page={probe_res.get('page_errors')}, network={probe_res.get('failed_requests')}"
        )
    if not probe_res.get("loaded_fonts_main"):
        failures.append("chromium runtime loaded 0 main webfonts")
    if not probe_res.get("idempotency_passed"):
        failures.append(
            f"hf-seek({probe_res.get('idempotency_time_sec')}s) pixel-parity "
            f"MAE={probe_res.get('idempotency_mae')} > 0.5"
        )
    cap_mount = probe_res.get("caption_mount_status") or {}
    if not cap_mount.get("mounted") or not cap_mount.get("hasChildren"):
        failures.append(
            "#captions sub-composition not mounted in index.html "
            "(data-composition-src/data-composition-id missing or failed to load)"
        )
    elif not probe_res.get("caption_checks") or not cap_mount.get("hasDevanagari"):
        failures.append(
            "#captions sub-composition rendered zero Devanagari cues inside index.html at spoken timestamps"
        )
    hf_tl = probe_res.get("hf_timeline_captions")
    if not isinstance(hf_tl, dict) or not hf_tl.get("mounted"):
        failures.append(
            f"hyperframes timeline #captions sub-composition not mounted: {hf_tl}"
        )
    for box in probe_res.get("caption_checks") or []:
        if float(box["bottom"]) > caption_safe_bottom_max:
            failures.append(
                f"caption bottom {box['bottom']:.1f}px > {caption_safe_bottom_max}px (< Y=1400) at t={box['t']}s"
            )
    for pill in probe_res.get("pill_boxes") or []:
        if (
            float(pill["left"]) < pill_min_x
            or float(pill["right"]) > pill_max_x
            or float(pill["top"]) < pill_min_y
            or float(pill["bottom"]) > pill_max_y
            or int(pill["scrollHeight"]) > int(pill["clientHeight"]) + 2
        ):
            failures.append(f"contextual pill out of Shorts bounds or clipped: {pill}")

    if hf_check_res is not None and not hf_check_res.get("skipped"):
        failures.extend(validate_hf_check_report(hf_check_res))
    return failures


def run_hf_timeline(root: Path, project_dir: Path, *, timeout_sec: int = 60) -> dict[str, Any]:
    """Run ``hyperframes timeline <dir> --json`` to inspect mounted tracks and sub-compositions."""
    node_exe, hf_cli = find_hyperframes_cli(root)
    proc = subprocess.run(
        [node_exe, str(hf_cli), "timeline", str(project_dir), "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise HyperFramesError(
            f"hyperframes timeline failed (exit={proc.returncode}): {(proc.stderr or proc.stdout)[-500:]}"
        )
    return _extract_json_blob(proc.stdout or proc.stderr)


def run_hf_check(
    root: Path,
    project_dir: Path,
    *,
    safe_zone: str = "shorts",
    strict: bool = True,
    no_craft: bool = False,
    at: list[float] | None = None,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    """Run ``hyperframes check`` strictly for Shorts safe-zone, contrast, and motion."""
    node_exe, hf_cli = find_hyperframes_cli(root)
    cmd = [
        node_exe,
        str(hf_cli),
        "check",
        str(project_dir),
        "--safe-zone",
        safe_zone,
        "--no-cache",
        "--no-browser-gpu",
        "--json",
    ]
    if strict:
        cmd.append("--strict")
    if no_craft:
        cmd.append("--no-craft")
    if at:
        cmd.extend(["--at", ",".join(f"{float(t):.3f}" for t in at)])

    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    try:
        parsed = _extract_json_blob(proc.stdout or proc.stderr)
    except HyperFramesError as exc:
        raise HyperFramesError(
            f"hyperframes check failed (exit={proc.returncode}): {(proc.stderr or proc.stdout)[-600:]}"
        ) from exc
    parsed.setdefault("exit_code", proc.returncode)
    raw_ok = bool(parsed.get("ok", proc.returncode == 0))
    total_errors, total_warnings, issue_messages = _collect_hf_check_issues(parsed)
    parsed["raw_ok"] = raw_ok
    parsed["total_error_count"] = total_errors
    parsed["total_warning_count"] = total_warnings
    parsed["issue_messages"] = issue_messages
    parsed["ok"] = (
        proc.returncode == 0
        and raw_ok
        and total_errors == 0
        and total_warnings == 0
    )
    return parsed


def run_hf_measure_look(
    root: Path,
    video_path: Path,
    *,
    fps: float = 2.0,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    """Run ``hyperframes measure look <video> --json`` cleanly."""
    video_path = Path(video_path)
    if not video_path.is_file():
        raise HyperFramesError(f"Video file not found for measure look: {video_path}")
    node_exe, hf_cli = find_hyperframes_cli(root)
    proc = subprocess.run(
        [node_exe, str(hf_cli), "measure", "look", str(video_path), "--fps", str(fps), "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise HyperFramesError(
            f"hyperframes measure look failed (exit={proc.returncode}): {(proc.stderr or proc.stdout)[-500:]}"
        )
    return _extract_json_blob(proc.stdout)


def _snapshot_sort_key(path: Path) -> tuple[float, str]:
    match = re.search(r"at-([0-9]+(?:\.[0-9]+)?)s", path.stem)
    if match:
        return (float(match.group(1)), path.name)
    return (float("inf"), path.name)


def capture_hf_snapshots(
    root: Path,
    project_dir: Path,
    timestamps: list[float],
    output_dir: Path,
    *,
    timeout_sec: int = 180,
) -> list[Path]:
    """Capture composition frames at exact timestamps into output_dir via ``hyperframes snapshot``."""
    if not timestamps:
        raise HyperFramesError("timestamps list must not be empty")
    node_exe, hf_cli = find_hyperframes_cli(root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Clean any stale stills before --keep writes exact per-timestamp at-<sec>s.png files
    for stale in output_dir.glob("at-*.png"):
        stale.unlink(missing_ok=True)

    at_arg = ",".join(f"{max(0.0, float(t)):.3f}" for t in timestamps)
    proc = subprocess.run(
        [
            node_exe,
            str(hf_cli),
            "snapshot",
            str(project_dir),
            "--at",
            at_arg,
            "--no-end",
            "--keep",
            "--output",
            str(output_dir),
            "--no-browser-gpu",
            "--json",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise HyperFramesError(
            f"hyperframes snapshot failed (exit={proc.returncode}): {(proc.stderr or proc.stdout)[-600:]}"
        )
    images = sorted(
        [p for p in output_dir.glob("*.png") if not p.name.startswith(("sheet", "contact", "review-"))],
        key=_snapshot_sort_key,
    )
    if not images:
        raise HyperFramesError(f"hyperframes snapshot produced 0 images in {output_dir}")
    return images[: len(timestamps)]


def select_storyboard_timestamps(
    duration_sec: float,
    scene_ranges: list[tuple[float, float]] | None = None,
    count: int = 15,
) -> list[float]:
    """Choose deterministic multi-beat timestamps covering hook, middles, seams, and tail."""
    dur = max(0.5, float(duration_sec))
    max_t = max(0.08, dur - 0.12)
    candidates: list[float] = [min(0.25, max_t * 0.2), max_t]
    if scene_ranges:
        for idx, (s0, s1) in enumerate(scene_ranges):
            span = max(0.05, float(s1) - float(s0))
            candidates.append(min(max_t, max(0.05, float(s0) + span * 0.5)))
            if idx > 0:
                candidates.append(min(max_t, max(0.05, float(s0) + 0.18)))
    # Uniform grid fill so we always reach exact requested count (default 15)
    grid_n = max(count * 2, count)
    for k in range(grid_n):
        frac = (k + 0.5) / grid_n
        candidates.append(round(min(max_t, max(0.05, frac * dur)), 3))

    deduped: list[float] = []
    for t in sorted(round(min(max_t, max(0.05, c)), 3) for c in candidates):
        if all(abs(t - prev) >= 0.04 for prev in deduped):
            deduped.append(t)
    if len(deduped) < count:
        for k in range(count):
            t = round(0.05 + (max_t - 0.05) * (k / max(1, count - 1)), 3)
            if t not in deduped:
                deduped.append(t)
    if len(deduped) > count:
        # Subsample evenly while preserving first and last timestamps
        step = (len(deduped) - 1) / (count - 1)
        picked = [deduped[round(i * step)] for i in range(count)]
        deduped = sorted(set(picked))
        while len(deduped) < count:
            for item in sorted(candidates):
                r = round(min(max_t, max(0.05, item)), 3)
                if r not in deduped:
                    deduped.append(r)
                    if len(deduped) == count:
                        break
        deduped = sorted(deduped)[:count]
    return deduped


def stitch_contact_sheet(
    image_paths: list[Path],
    scene_labels: list[str],
    output_path: Path,
    *,
    cols: int = 3,
    thumb_w: int = 360,
    thumb_h: int = 640,
    overlay_safe_zones: bool = False,
    safe_zones: dict[str, int] | None = None,
) -> Path:
    """Stitch storyboard/QA frames into a labeled contact sheet JPEG with exact cols*thumb_w x rows*thumb_h size."""
    if not image_paths:
        raise HyperFramesError("No images provided to stitch_contact_sheet")
    if cols < 1:
        raise HyperFramesError(f"cols must be >= 1, got {cols}")

    n = len(image_paths)
    rows = (n + cols - 1) // cols
    sheet_w = cols * thumb_w
    sheet_h = rows * thumb_h
    sheet = Image.new("RGB", (sheet_w, sheet_h), (10, 10, 15))
    draw = ImageDraw.Draw(sheet)

    sx = thumb_w / 1080.0
    sy = thumb_h / 1920.0
    sz = safe_zones or {}
    top_clear = int(sz.get("top_clear_px", sz.get("top_px", 288)) * sy)
    bot_clear = int(thumb_h - (sz.get("bottom_clear_px", sz.get("bottom_px", 520)) * sy))
    right_clear = int(thumb_w - (sz.get("right_clear_px", sz.get("right_px", 192)) * sx))
    left_clear = int(sz.get("left_clear_px", sz.get("left_px", 48)) * sx)

    for idx, img_path in enumerate(image_paths):
        r = idx // cols
        c = idx % cols
        x_off = c * thumb_w
        y_off = r * thumb_h

        if img_path.is_file():
            with Image.open(img_path) as im:
                resized = im.convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(resized, (x_off, y_off))
        else:
            draw.rectangle([x_off, y_off, x_off + thumb_w, y_off + thumb_h], fill=(40, 20, 20))
            draw.text((x_off + 16, y_off + thumb_h // 2), f"Missing: {img_path.name}", fill=(255, 100, 100))

        if overlay_safe_zones:
            overlay = Image.new("RGBA", (thumb_w, thumb_h), (0, 0, 0, 0))
            ov_draw = ImageDraw.Draw(overlay)
            ov_draw.rectangle([0, 0, thumb_w, top_clear], fill=(255, 0, 0, 45))
            ov_draw.rectangle([0, bot_clear, thumb_w, thumb_h], fill=(255, 0, 0, 60))
            ov_draw.rectangle([right_clear, top_clear, thumb_w, bot_clear], fill=(255, 0, 0, 45))
            ov_draw.rectangle([left_clear, top_clear, right_clear, bot_clear], outline=(0, 255, 255, 180), width=2)
            sheet.paste(overlay, (x_off, y_off), mask=overlay)

        banner_h = 28
        label = scene_labels[idx] if idx < len(scene_labels) else f"F{idx + 1}"
        draw.rectangle([x_off, y_off + thumb_h - banner_h, x_off + thumb_w, y_off + thumb_h], fill=(16, 18, 30))
        draw.text((x_off + 8, y_off + thumb_h - banner_h + 6), str(label)[:44], fill=(255, 215, 0))
        draw.rectangle([x_off, y_off, x_off + thumb_w - 1, y_off + thumb_h - 1], outline=(60, 60, 70), width=1)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp.jpg")
    sheet.save(tmp_path, format="JPEG", quality=90, optimize=True)
    os.replace(tmp_path, output_path)
    return output_path


def generate_storyboard_preview_sheet(
    root: Path,
    project_dir: Path,
    duration_sec: float,
    output_jpg: Path,
    *,
    scene_ranges: list[tuple[float, float]] | None = None,
    safe_zone_jpg: Path | None = None,
    count: int = 15,
    timeout_sec: int = 180,
) -> dict[str, Any]:
    """Snapshot composition at multi-beat timestamps and render 15-frame qa_grid.jpg."""
    timestamps = select_storyboard_timestamps(duration_sec, scene_ranges=scene_ranges, count=count)
    with tempfile.TemporaryDirectory(prefix="hf_snaps_", ignore_cleanup_errors=True) as td:
        snap_dir = Path(td)
        images = capture_hf_snapshots(root, project_dir, timestamps, snap_dir, timeout_sec=timeout_sec)
        labels = [
            f"#{i + 1} t={timestamps[i]:.2f}s" if i < len(timestamps) else f"#{i + 1} {img.stem}"
            for i, img in enumerate(images)
        ]
        cols = 5 if len(images) >= 10 else 3
        stitch_contact_sheet(
            images,
            labels,
            output_jpg,
            cols=cols,
            thumb_w=270,
            thumb_h=480,
            overlay_safe_zones=False,
        )
        if safe_zone_jpg is not None:
            stitch_contact_sheet(
                images,
                labels,
                safe_zone_jpg,
                cols=cols,
                thumb_w=270,
                thumb_h=480,
                overlay_safe_zones=True,
            )
    return {
        "frame_count": len(images),
        "timestamps": timestamps[: len(images)],
        "qa_grid": str(output_jpg),
        "qa_grid_safezones": str(safe_zone_jpg) if safe_zone_jpg is not None else None,
    }


def _compute_png_rgb_mae(png_a_b64: str, png_b_b64: str) -> float:
    img_a = Image.open(io.BytesIO(base64.b64decode(png_a_b64))).convert("RGB")
    img_b = Image.open(io.BytesIO(base64.b64decode(png_b_b64))).convert("RGB")
    if img_a.size != img_b.size:
        raise HyperFramesError(f"Idempotency image size mismatch: {img_a.size} vs {img_b.size}")
    arr_a = np.asarray(img_a, dtype=np.float32)
    arr_b = np.asarray(img_b, dtype=np.float32)
    return float(np.mean(np.abs(arr_a - arr_b)))


def _load_caption_sample_times(project_dir: Path, duration_sec: float, limit: int = 6) -> list[float]:
    cap_js = project_dir / "captions" / "captions_data.js"
    if not cap_js.is_file():
        return [round(min(max(0.2, duration_sec * 0.35), max(0.2, duration_sec - 0.1)), 3)]
    raw = cap_js.read_text(encoding="utf-8").strip()
    raw = re.sub(r"^(?:window\.)?CAPTIONS_DATA\s*=\s*", "", raw, count=1)
    if raw.endswith(";"):
        raw = raw[:-1].strip()
    try:
        cues = json.loads(raw)
    except Exception:
        return []
    mids: list[float] = []
    for cue in cues:
        s = float(cue.get("start", 0.0))
        e = float(cue.get("end", 0.0))
        if e > s:
            mids.append(round((s + e) * 0.5, 3))
    if len(mids) <= limit:
        return mids
    step = (len(mids) - 1) / max(1, limit - 1)
    return [mids[round(i * step)] for i in range(limit)]


def _load_pill_sample_times(project_dir: Path) -> list[float]:
    meta_path = project_dir / "storyboard_compiled.json"
    if not meta_path.is_file():
        return []
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        rt = meta.get("episode_runtime") or {}
        if not rt.get("enable_contextual_pills"):
            return []
        times: list[float] = []
        for sc in rt.get("scenes") or []:
            if sc.get("pill_kicker") or sc.get("pill_title"):
                times.append(round((float(sc["s0"]) + float(sc["s1"])) * 0.5, 3))
        return times
    except Exception:
        return []


def run_chromium_runtime_probe(
    root: Path,
    index_html: Path,
    *,
    duration_sec: float,
    idempotency_time_sec: float = 12.6,
    caption_sample_times: list[float] | None = None,
    pill_sample_times: list[float] | None = None,
    max_idempotency_mae: float = 0.5,
    timeout_sec: int = 150,
) -> dict[str, Any]:
    """Run live headless Chromium telemetry: console/errors, fonts, DOM pills, captions, hf-seek MAE."""
    index_html = Path(index_html).resolve()
    if not index_html.is_file():
        raise HyperFramesError(f"Composition entry HTML not found: {index_html}")
    project_dir = index_html.parent

    dur = max(0.5, float(duration_sec))
    seek_t = float(idempotency_time_sec) if dur >= float(idempotency_time_sec) + 0.1 else round(max(0.25, dur * 0.5), 3)
    cap_times = caption_sample_times if caption_sample_times is not None else _load_caption_sample_times(project_dir, dur)
    pill_times = pill_sample_times if pill_sample_times is not None else _load_pill_sample_times(project_dir)
    has_captions_page = (project_dir / "captions" / "captions.html").is_file()

    script_body = """
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => {
    pageErrors.push(String(err && err.message ? err.message : err));
  });
  page.on("requestfailed", (req) => {
    const reason = req.failure() ? req.failure().errorText : "failed";
    if (reason === "net::ERR_ABORTED" && req.resourceType() === "media") return;
    failedRequests.push({ url: req.url(), reason, resourceType: req.resourceType() });
  });
  page.on("response", (res) => {
    if (res.status() >= 400) failedRequests.push({ url: res.url(), status: res.status() });
  });

  await page.goto(payload.indexUrl, { waitUntil: "networkidle0" });
  await page.evaluate(async () => {
    if (window.__sutradharFontsReady) await window.__sutradharFontsReady;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
  });

  const fontsMain = await page.evaluate(() => {
    const out = [];
    if (document.fonts) {
      for (const f of document.fonts) {
        out.push({ family: f.family, weight: String(f.weight), status: f.status });
      }
    }
    return out;
  });

  const pillBoxes = [];
  for (const pt of payload.pillTimes || []) {
    const info = await page.evaluate((t) => {
      window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: t } }));
      const el = document.querySelector(".ctx-pill");
      if (!el) return null;
      const st = window.getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return {
        t,
        opacity: Number(st.opacity || 0),
        display: st.display,
        text: (el.innerText || "").trim(),
        left: r.left,
        top: r.top,
        right: r.right,
        bottom: r.bottom,
        width: r.width,
        height: r.height,
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
      };
    }, pt);
    if (info && info.opacity > 0.05 && info.width > 0 && info.height > 0) {
      pillBoxes.push(info);
    }
  }

  // Sequential scrub -> target seekTime
  const seqSteps = [0.0, payload.seekTime * 0.25, payload.seekTime * 0.5, payload.seekTime * 0.75, payload.seekTime];
  const seqDataUrl = await page.evaluate(async (steps) => {
    for (const t of steps) {
      window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: t } }));
    }
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const canvas = document.getElementById("world-canvas");
    if (!canvas) throw new Error("#world-canvas missing");
    return canvas.toDataURL("image/png");
  }, seqSteps);

  // Fresh reload -> direct hf-seek(seekTime)
  await page.reload({ waitUntil: "networkidle0" });
  await page.evaluate(async () => {
    if (window.__sutradharFontsReady) await window.__sutradharFontsReady;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
  });
  const directDataUrl = await page.evaluate(async (t) => {
    window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: t } }));
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const canvas = document.getElementById("world-canvas");
    if (!canvas) throw new Error("#world-canvas missing");
    return canvas.toDataURL("image/png");
  }, payload.seekTime);

  const captionChecks = [];
  let captionFonts = [];
  let captionMountStatus = { mounted: false, hasChildren: false, hasDevanagari: false };
  // Mount & probe #captions sub-composition INSIDE index.html via data-composition-src
  {
    const mountMeta = await page.evaluate(() => {
      const captionsEl = document.getElementById("captions");
      if (!captionsEl) return { ok: false, reason: "#captions element missing" };
      const compSrc = (captionsEl.getAttribute("data-composition-src") || "").trim();
      const compId = (captionsEl.getAttribute("data-composition-id") || "").trim();
      if (!compSrc || !compId) {
        return { ok: false, reason: "data-composition-src or data-composition-id missing on #captions" };
      }
      return { ok: true, compSrc, compId };
    });

    if (mountMeta.ok) {
      const iframeLoaded = await page.evaluate(async (compSrc) => {
        const captionsEl = document.getElementById("captions");
        if (!captionsEl) return false;
        const iframe = document.createElement("iframe");
        iframe.id = "__hf_probe_captions_frame";
        iframe.style.cssText = "position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent;";
        const resolvedUrl = new URL(compSrc, window.location.href).href;
        await new Promise((resolve) => {
          let settled = false;
          const done = (val) => { if (!settled) { settled = true; resolve(val); } };
          iframe.addEventListener("load", () => done(true), { once: true });
          iframe.addEventListener("error", () => done(false), { once: true });
          setTimeout(() => done(true), 4000);
          iframe.src = resolvedUrl;
          captionsEl.appendChild(iframe);
        });
        if (!iframe.contentDocument) return false;
        if (iframe.contentWindow && iframe.contentWindow.__sutradharFontsReady) {
          await iframe.contentWindow.__sutradharFontsReady.catch(() => {});
        }
        if (iframe.contentDocument.fonts && iframe.contentDocument.fonts.ready) {
          await iframe.contentDocument.fonts.ready.catch(() => {});
        }
        return true;
      }, mountMeta.compSrc);

      if (iframeLoaded) {
        captionFonts = await page.evaluate(() => {
          const out = [];
          const iframe = document.getElementById("__hf_probe_captions_frame");
          if (iframe && iframe.contentDocument && iframe.contentDocument.fonts) {
            for (const f of iframe.contentDocument.fonts) {
              out.push({ family: f.family, weight: String(f.weight), status: f.status, source: "captions-iframe" });
            }
          }
          return out;
        });

        for (const ct of payload.captionTimes || []) {
          const capBox = await page.evaluate((t) => {
            window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: t } }));
            const captionsEl = document.getElementById("captions");
            const iframe = document.getElementById("__hf_probe_captions_frame");
            if (!captionsEl || !iframe || !iframe.contentDocument || !iframe.contentWindow) return null;
            iframe.contentWindow.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: t } }));
            const doc = iframe.contentDocument;
            const line = doc.getElementById("caption-line");
            const grp = doc.getElementById("caption-group");
            const target = line && line.textContent.trim().length ? line : grp;
            if (!target) return null;
            const hostRect = captionsEl.getBoundingClientRect();
            const innerRect = target.getBoundingClientRect();
            const text = (target.textContent || "").trim();
            return {
              t,
              text,
              left: hostRect.left + innerRect.left,
              top: hostRect.top + innerRect.top,
              right: hostRect.left + innerRect.right,
              bottom: hostRect.top + innerRect.bottom,
              width: innerRect.width,
              height: innerRect.height,
              hasDevanagari: /[\u0900-\u097F]/.test(text),
            };
          }, ct);
          if (capBox) captionChecks.push(capBox);
        }

        captionMountStatus = await page.evaluate(() => {
          const iframe = document.getElementById("__hf_probe_captions_frame");
          const doc = iframe ? iframe.contentDocument : null;
          if (!doc) return { mounted: false, hasChildren: false, hasDevanagari: false };
          const lineEl = doc.getElementById("caption-line");
          const grpEl = doc.getElementById("caption-group");
          const hasChildren = !!(lineEl || grpEl);
          return { mounted: true, hasChildren, hasDevanagari: false };
        });
        captionMountStatus.hasDevanagari = captionChecks.some((b) => Boolean(b.hasDevanagari));
      }
    }
  }

  return {
    consoleErrors,
    pageErrors,
    failedRequests,
    fontsMain,
    captionFonts,
    pillBoxes,
    captionChecks,
    seqPngB64: seqDataUrl.split(",", 2)[1],
    directPngB64: directDataUrl.split(",", 2)[1],
    captionMountStatus,
  };
"""
    hf_tl_captions = {"mounted": False, "src": None, "sourceFile": None}
    try:
        tl_json = run_hf_timeline(root, project_dir, timeout_sec=60)
        for tr in (tl_json.get("timeline") or {}).get("tracks") or []:
            if tr.get("kind") == "captions":
                for row in tr.get("rows") or []:
                    if row.get("id") == "captions" or row.get("trackKind") == "captions":
                        src = row.get("src")
                        sf = row.get("sourceFile")
                        hf_tl_captions = {
                            "mounted": bool(src and sf and (project_dir / sf).is_file()),
                            "src": src,
                            "sourceFile": sf,
                        }
                        break
    except Exception as exc:
        hf_tl_captions["error"] = str(exc)

    with serve_directory(project_dir) as base_url:
        payload = {
            "indexUrl": f"{base_url}/{index_html.name}",
            "captionsUrl": f"{base_url}/captions/captions.html" if has_captions_page else None,
            "seekTime": seek_t,
            "captionTimes": cap_times,
            "pillTimes": pill_times,
        }
        raw = run_node_puppeteer(root, script_body, payload, timeout_sec=timeout_sec)

    mae = _compute_png_rgb_mae(raw["seqPngB64"], raw["directPngB64"])
    loaded_main = [f for f in raw.get("fontsMain", []) if f.get("status") == "loaded"]
    loaded_cap = [f for f in raw.get("captionFonts", []) if f.get("status") == "loaded"]

    return {
        "console_errors": raw.get("consoleErrors", []),
        "page_errors": raw.get("pageErrors", []),
        "failed_requests": raw.get("failedRequests", []),
        "loaded_fonts_main": loaded_main,
        "loaded_fonts_captions": loaded_cap,
        "pill_boxes": raw.get("pillBoxes", []),
        "caption_checks": raw.get("captionChecks", []),
        "caption_mount_status": raw.get("captionMountStatus", {"mounted": False, "hasChildren": False, "hasDevanagari": False}),
        "hf_timeline_captions": hf_tl_captions,
        "idempotency_time_sec": seek_t,
        "idempotency_mae": round(mae, 6),
        "idempotency_passed": mae <= max_idempotency_mae,
    }
