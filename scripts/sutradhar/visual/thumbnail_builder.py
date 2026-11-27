"""Deterministic English Shorts thumbnail builder + 2:3 center-crop verifier."""

from __future__ import annotations

import base64
import io
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from sutradhar.audio.whisper_aligner import write_text_atomic
from sutradhar.models import ThumbnailSpec
from sutradhar.qa.hyperframes_runner import run_node_puppeteer, serve_directory
from thumbnail_utils import validate_local_thumbnail

THUMBNAIL_WIDTH = 1080
THUMBNAIL_HEIGHT = 1920
THUMBNAIL_MAX_BYTES = 2_097_152
SHORTS_2X3_CROP_BOX = (0, 150, 1080, 1770)

THEME_COVER_CONFIGS: dict[str, dict[str, Any]] = {
    "dawn_epic": {
        "backdrop": "cosmic_dawn",
        "horizon_y": 1465,
        "kailash": {"x": 540, "base_y": 1465, "scale": 1.12, "t": 0.72, "gold_rim": 0.72},
        "floor_color": "#262544",
        "floor_trim": "#E6B245",
        "characters": [
            {"x": 540, "y": 1465, "scale": 1.24, "role": "shiva", "pose": "palm_cup", "expr": "determined", "neelakantha": 1.0, "halahalaInHand": 0.9}
        ],
    },
    "kailash_horizon": {
        "backdrop": "cosmic_dawn",
        "horizon_y": 1465,
        "kailash": {"x": 540, "base_y": 1465, "scale": 1.18, "t": 0.78, "gold_rim": 0.78},
        "floor_color": "#262544",
        "floor_trim": "#F6C453",
        "props": [{"id": "trishul", "x": 220, "y": 1465, "h": 430}],
        "characters": [
            {"x": 560, "y": 1465, "scale": 1.24, "role": "shiva", "pose": "palm_cup", "expr": "determined", "neelakantha": 1.0, "halahalaInHand": 0.9}
        ],
    },
    "brahmaloka_sabha": {
        "backdrop": "palace_court",
        "horizon_y": 1445,
        "kailash": False,
        "palette": {"wall_top": "#3B144A", "wall_bot": "#7A2D66", "dado_top": "#3E1938", "floor_a": "#6C3B34", "floor_b": "#36181A"},
        "props": [{"id": "brass_clock", "x": 540, "y": 820, "r": 140}],
        "characters": [
            {"x": 540, "y": 1445, "scale": 1.34, "role": "brahma", "pose": "bless", "expr": "serene"}
        ],
    },
    "palace_court": {
        "backdrop": "palace_court",
        "horizon_y": 1445,
        "kailash": False,
        "characters": [
            {"x": 540, "y": 1445, "scale": 1.32, "role": "kakudmi", "pose": "namaskar", "expr": "serene"}
        ],
    },
    "cosmic_ocean_manthan": {
        "backdrop": "cosmic_dawn",
        "horizon_y": 1445,
        "kailash": False,
        "sky": {"top": "#060B22", "mid": "#112256", "bot": "#284B78"},
        "props": [{"id": "samudra_manthan_halahala", "x": 540, "y": 1240, "erupt": 0.65, "scale": 0.95}],
        "characters": [
            {"x": 360, "y": 1445, "scale": 1.24, "role": "vishnu", "pose": "pull", "expr": "determined"},
            {"x": 740, "y": 1445, "scale": 1.24, "role": "shiva", "pose": "palm_cup", "expr": "determined", "neelakantha": 1.0},
        ],
    },
    "cosmic_explainer": {
        "backdrop": "cosmic_dawn",
        "horizon_y": 1445,
        "kailash": False,
        "sky": {"top": "#05091D", "mid": "#0D152E", "bot": "#070C1B"},
        "props": [{"id": "brahmaloka_time_chakra", "x": 540, "y": 880, "r": 210}],
        "characters": [
            {"x": 540, "y": 1445, "scale": 1.30, "role": "sutradhar_narrator", "pose": "gesture", "expr": "serene"}
        ],
    },
    "observatory_cosmos": {
        "backdrop": "cosmic_dawn",
        "horizon_y": 1445,
        "kailash": False,
        "sky": {"top": "#05091D", "mid": "#0D152E", "bot": "#070C1B"},
        "props": [{"id": "brahmaloka_time_chakra", "x": 540, "y": 880, "r": 210}],
        "characters": [
            {"x": 540, "y": 1445, "scale": 1.30, "role": "sutradhar_narrator", "pose": "gesture", "expr": "serene"}
        ],
    },
    "archival": {
        "backdrop": "palace_court",
        "horizon_y": 1445,
        "kailash": False,
        "palette": {"wall_top": "#2D1814", "wall_bot": "#5E2F1E", "dado_top": "#3B1D14", "floor_a": "#72492F", "floor_b": "#3A2216"},
        "characters": [
            {"x": 540, "y": 1445, "scale": 1.30, "role": "ancient_scholar", "pose": "gesture", "expr": "determined"}
        ],
    },
    "nalanda_archival": {
        "backdrop": "palace_court",
        "horizon_y": 1445,
        "kailash": False,
        "palette": {"wall_top": "#2D1814", "wall_bot": "#5E2F1E", "dado_top": "#3B1D14", "floor_a": "#72492F", "floor_b": "#3A2216"},
        "props": [{"id": "mehrauli_iron_pillar", "x": 280, "y": 1445}],
        "characters": [
            {"x": 580, "y": 1445, "scale": 1.30, "role": "ancient_scholar", "pose": "gesture", "expr": "determined"}
        ],
    },
}


class ThumbnailBuildError(RuntimeError):
    """Raised when thumbnail specification, rendering, 2:3 crop, or validation fails."""


@dataclass
class ThumbnailBuildResult:
    """Outputs and telemetry produced by ``build_thumbnail``."""

    thumbnail_jpg: Path
    crop_2x3_jpg: Path
    width: int
    height: int
    file_bytes: int
    mean_stddev: float
    loaded_fonts: list[dict[str, Any]] = field(default_factory=list)
    text_bounds: dict[str, Any] = field(default_factory=dict)
    within_2x3_crop: bool = False
    kailash_bounds_ok: bool = True


def save_shorts_2x3_crop(source_jpg: Path, crop_output_jpg: Path) -> Path:
    """Generate exact 2:3 Shorts center-crop verification image (1080x1620, y=150..1770)."""
    source_jpg = Path(source_jpg)
    crop_output_jpg = Path(crop_output_jpg)
    if not source_jpg.is_file():
        raise ThumbnailBuildError(f"Thumbnail JPEG missing for 2:3 crop: {source_jpg}")
    with Image.open(source_jpg) as img:
        if img.size != (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT):
            raise ThumbnailBuildError(
                f"Expected {THUMBNAIL_WIDTH}x{THUMBNAIL_HEIGHT} source thumbnail, got {img.size}"
            )
        cropped = img.convert("RGB").crop(SHORTS_2X3_CROP_BOX)
    if cropped.size != (1080, 1620):
        raise ThumbnailBuildError(f"Unexpected 2:3 crop size: {cropped.size}")
    crop_output_jpg.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(crop_output_jpg, format="JPEG", quality=92, optimize=True)
    return crop_output_jpg


def _coerce_thumbnail_spec(spec: ThumbnailSpec | dict[str, Any]) -> ThumbnailSpec:
    if isinstance(spec, ThumbnailSpec):
        return spec
    if isinstance(spec, dict):
        try:
            return ThumbnailSpec.model_validate(spec)
        except Exception as exc:
            raise ThumbnailBuildError(f"Invalid ThumbnailSpec: {exc}") from exc
    raise ThumbnailBuildError(f"Unsupported thumbnail_spec type: {type(spec).__name__}")


def _resolve_cover_config(spec: ThumbnailSpec, override: dict[str, Any] | None) -> dict[str, Any]:
    base = dict(THEME_COVER_CONFIGS.get(spec.theme, THEME_COVER_CONFIGS["dawn_epic"]))
    if override:
        base.update(override)
    base.setdefault("seed", 701)
    base.setdefault("t", 1.0)
    base.setdefault("horizon_y", 1445)
    # Enforce character grounding on cover floor
    horizon_y = float(base["horizon_y"])
    for ch in base.get("characters") or []:
        if "y" not in ch or ch["y"] is None:
            ch["y"] = horizon_y
    return base


def _encode_png_bytes_to_jpeg(png_bytes: bytes, output_jpg: Path) -> int:
    output_jpg.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(png_bytes)) as img:
        rgb = img.convert("RGB")
        if rgb.size != (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT):
            rgb = rgb.resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)
        for q in (92, 86, 80, 72):
            rgb.save(output_jpg, format="JPEG", quality=q, optimize=True)
            size = output_jpg.stat().st_size
            if size <= THUMBNAIL_MAX_BYTES:
                return size
    raise ThumbnailBuildError(
        f"Thumbnail JPEG {output_jpg} exceeds 2.0 MB limit ({output_jpg.stat().st_size} bytes)"
    )


def build_thumbnail(
    root: Path,
    thumbnail_spec: ThumbnailSpec | dict[str, Any],
    output_jpg: Path,
    *,
    crop_output_jpg: Path | None = None,
    cover_config: dict[str, Any] | None = None,
    footer_text: str = "SUTRADHAR",
    timeout_sec: int = 90,
) -> ThumbnailBuildResult:
    """Compile templates/thumbnail/cover_template.html.jinja2 -> 1080x1920 JPEG + 2:3 Shorts crop."""
    from jinja2 import Environment, FileSystemLoader

    root = Path(root).resolve()
    spec = _coerce_thumbnail_spec(thumbnail_spec)
    output_jpg = Path(output_jpg).resolve()
    crop_jpg = Path(crop_output_jpg).resolve() if crop_output_jpg else output_jpg.with_name(f"{output_jpg.stem}_2x3_crop.jpg")
    resolved_cover = _resolve_cover_config(spec, cover_config)

    tpl_dir = root / "templates" / "thumbnail"
    if not (tpl_dir / "cover_template.html.jinja2").is_file():
        raise ThumbnailBuildError(f"Missing thumbnail template in {tpl_dir}")

    with tempfile.TemporaryDirectory(prefix="sutradhar_thumb_", ignore_cleanup_errors=True) as td:
        stage = Path(td)
        for sub in ("fonts", "lib", "runtime"):
            (stage / sub).mkdir(parents=True, exist_ok=True)
        shutil.copytree(root / "assets" / "fonts", stage / "fonts", dirs_exist_ok=True)
        shutil.copy2(root / "assets" / "js" / "gsap.min.js", stage / "lib" / "gsap.min.js")
        shutil.copytree(root / "templates" / "runtime", stage / "runtime", dirs_exist_ok=True)

        h1_len = len(spec.headline_line1.strip())
        h2_len = len(spec.headline_line2.strip())
        h1_size_px = 94 if h1_len <= 11 else max(68, int(94 * 11 / h1_len))
        h2_size_px = 102 if h2_len <= 11 else max(72, int(102 * 11.5 / h2_len))

        jenv = Environment(loader=FileSystemLoader(str(tpl_dir)))
        html_text = jenv.get_template("cover_template.html.jinja2").render(
            lang="en",
            page_title=f"{spec.headline_line1} {spec.headline_line2}".strip(),
            fonts_css="fonts/fonts.css",
            gsap_src="lib/gsap.min.js",
            runtime_base="./runtime",
            pill_text=spec.pill,
            headline_1=spec.headline_line1,
            headline_2=spec.headline_line2,
            sub_pill=spec.sub_pill or "",
            footer_text=footer_text,
            badge_top_px=190,
            foot_bottom_px=208,
            h1_size_px=h1_size_px,
            h2_size_px=h2_size_px,
            cover_config_json=json.dumps(resolved_cover, ensure_ascii=False),
        )
        # Honor ThumbnailSpec.font_weight cleanly while capping <= 800
        if int(spec.font_weight) != 800:
            html_text = html_text.replace("font-weight: 800;", f"font-weight: {int(spec.font_weight)};")

        cover_html = stage / "cover.html"
        write_text_atomic(cover_html, html_text)

        probe_script = """
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e && e.message ? e.message : e)));
  page.on("response", (res) => { if (res.status() >= 400) errors.push(`HTTP ${res.status()} ${res.url()}`); });

  await page.goto(payload.coverUrl, { waitUntil: "networkidle0" });
  await page.evaluate(async () => {
    if (window.__sutradharFontsReady) await window.__sutradharFontsReady;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  });

  const telemetry = await page.evaluate(() => {
    const fonts = [];
    if (document.fonts) {
      for (const f of document.fonts) {
        if (f.status === "loaded") fonts.push({ family: f.family, weight: String(f.weight) });
      }
    }
    const measure = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      const cs = window.getComputedStyle(el);
      return {
        top: r.top,
        bottom: r.bottom,
        left: r.left,
        right: r.right,
        fontWeight: Number(cs.fontWeight || 400),
      };
    };
    return {
      fonts,
      pill: measure(".pill"),
      h1: measure(".h1"),
      h2: measure(".h2"),
      subPill: measure(".sub-pill"),
      foot: measure(".foot"),
    };
  });

  const pngBuf = await page.screenshot({ type: "png" });
  return {
    errors,
    telemetry,
    pngB64: Buffer.from(pngBuf).toString("base64"),
  };
"""
        with serve_directory(stage) as base_url:
            probe_res = run_node_puppeteer(
                root,
                probe_script,
                {"coverUrl": f"{base_url}/cover.html"},
                timeout_sec=timeout_sec,
            )

    if probe_res.get("errors"):
        raise ThumbnailBuildError(f"Thumbnail render errors: {probe_res['errors']}")

    png_bytes = base64.b64decode(probe_res["pngB64"])
    _encode_png_bytes_to_jpeg(png_bytes, output_jpg)

    try:
        val = validate_local_thumbnail(
            output_jpg,
            expected_size=(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT),
            max_bytes=THUMBNAIL_MAX_BYTES,
            min_stddev=4.0,
            allowed_formats=("JPEG",),
        )
        if int(val["bytes"]) < 10_240:
            raise ThumbnailBuildError(f"Thumbnail JPEG too small ({val['bytes']} < 10240 bytes)")
    except Exception as exc:
        raise ThumbnailBuildError(f"Thumbnail validation failed: {exc}") from exc

    save_shorts_2x3_crop(output_jpg, crop_jpg)

    t_info = probe_res.get("telemetry") or {}
    # Verify headlines & pills stay strictly inside the 2:3 Shorts center crop [150..1770] and weights <= 800
    within_crop = True
    for key in ("pill", "h1", "h2", "subPill"):
        box = t_info.get(key)
        if not box:
            continue
        if float(box["fontWeight"]) > 800.0:
            raise ThumbnailBuildError(
                f"Thumbnail {key} computed font-weight {box['fontWeight']} exceeds 800 ceiling"
            )
        if float(box["top"]) < SHORTS_2X3_CROP_BOX[1] or float(box["bottom"]) > SHORTS_2X3_CROP_BOX[3]:
            within_crop = False
    if not within_crop:
        raise ThumbnailBuildError(
            f"Thumbnail text overflows 2:3 Shorts center-crop y=[150..1770]: {t_info}"
        )

    # Check Kailash cover config horizontal/vertical bounds when active
    kailash_ok = True
    k_cfg = resolved_cover.get("kailash")
    if isinstance(k_cfg, dict):
        cx = float(k_cfg.get("x", k_cfg.get("cx", 540)))
        scale = float(k_cfg.get("scale", 1.15))
        base_y = float(k_cfg.get("base_y", 1445))
        peak_top_y = base_y - 404.0 * scale
        if not (200.0 <= cx <= 880.0 and 0.6 <= scale <= 1.6 and peak_top_y >= 420.0):
            kailash_ok = False
            raise ThumbnailBuildError(
                f"Thumbnail Kailash geometry out of bounds: x={cx}, scale={scale}, peak_top_y={peak_top_y}"
            )

    return ThumbnailBuildResult(
        thumbnail_jpg=output_jpg,
        crop_2x3_jpg=crop_jpg,
        width=int(val["width"]),
        height=int(val["height"]),
        file_bytes=int(val["bytes"]),
        mean_stddev=float(val["mean_stddev"]),
        loaded_fonts=t_info.get("fonts", []),
        text_bounds=t_info,
        within_2x3_crop=within_crop,
        kailash_bounds_ok=kailash_ok,
    )
