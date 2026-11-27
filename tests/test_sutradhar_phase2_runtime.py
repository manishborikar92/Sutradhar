"""Phase 2 Verification Suite: Canonical Assets, HyperFrames Runtime, Deterministic Seek & Bounded Kailash."""

from __future__ import annotations

import functools
import hashlib
import http.server
import io
import json
import os
import shutil
import socketserver
import subprocess
import threading
import unittest
from pathlib import Path

import numpy as np
import yaml
from jinja2 import Environment, FileSystemLoader
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent


def _find_chrome_executable() -> Path:
    candidates = sorted((Path.home() / ".cache" / "hyperframes" / "chrome").rglob("chrome-headless-shell.exe"))
    if candidates:
        return candidates[-1]
    candidates = sorted((Path.home() / ".cache" / "hyperframes" / "chrome").rglob("chrome.exe"))
    if candidates:
        return candidates[-1]
    raise FileNotFoundError("HyperFrames cached headless Chrome binary not found under ~/.cache/hyperframes/chrome")


def _hyperframes_command() -> list[str]:
    node_bin = shutil.which("node.exe") or shutil.which("node")
    if not node_bin:
        raise FileNotFoundError("node CLI not found on PATH")
    hf_entry = REPO_ROOT / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    if not hf_entry.is_file():
        raise FileNotFoundError(f"Local HyperFrames CLI not found at {hf_entry}")
    return [node_bin, str(hf_entry)]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

    def handle_error(self, request: object, client_address: object) -> None:
        return


def _serve_directory(directory: Path):
    handler = functools.partial(_QuietHandler, directory=str(directory))
    server = _ReusableTCPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _stage_sample_composition(stage_dir: Path) -> None:
    """Renders v2 runtime Jinja2 templates + copies canonical assets into a standalone HyperFrames bundle."""
    (stage_dir / "fonts").mkdir(parents=True, exist_ok=True)
    (stage_dir / "lib").mkdir(parents=True, exist_ok=True)
    (stage_dir / "captions").mkdir(parents=True, exist_ok=True)
    (stage_dir / "thumb").mkdir(parents=True, exist_ok=True)
    (stage_dir / "audio").mkdir(parents=True, exist_ok=True)

    shutil.copytree(REPO_ROOT / "assets" / "fonts", stage_dir / "fonts", dirs_exist_ok=True)
    shutil.copy2(REPO_ROOT / "assets" / "js" / "gsap.min.js", stage_dir / "lib" / "gsap.min.js")
    shutil.copytree(REPO_ROOT / "templates" / "runtime", stage_dir / "runtime", dirs_exist_ok=True)
    # Use a 10s sample audio clip (riser.mp3 is 10.03s) + silence/loop pad or copy cosmic_mystery clipped to 15s via ffmpeg,
    # or simple sample audio so HyperFrames --craft sees real audio
    shutil.copy2(REPO_ROOT / "assets" / "audio" / "bgm" / "veena_devotional_serene.mp3", stage_dir / "audio" / "bgm.mp3")
    shutil.copy2(REPO_ROOT / "templates" / "runtime" / "styles.css", stage_dir / "styles.css")

    captions_data = [
        {
            "start": 0.4,
            "end": 4.5,
            "gloss": "Mount Kailash rises in stillness",
            "words": [
                {"word": "कैलाश", "start": 0.4, "end": 1.1},
                {"word": "पर्वत", "start": 1.1, "end": 1.9},
                {"word": "शांत", "start": 1.9, "end": 2.8},
                {"word": "खड़ा", "start": 2.8, "end": 3.6},
                {"word": "था", "start": 3.6, "end": 4.4},
            ],
        },
        {
            "start": 5.5,
            "end": 9.5,
            "gloss": "Time bent inside Brahmaloka",
            "words": [
                {"word": "ब्रह्मलोक", "start": 5.5, "end": 6.6},
                {"word": "में", "start": 6.6, "end": 7.2},
                {"word": "समय", "start": 7.2, "end": 8.3},
                {"word": "मुड़ा", "start": 8.3, "end": 9.4},
            ],
        },
        {
            "start": 10.4,
            "end": 14.5,
            "gloss": "Cosmic ocean churned Halahala",
            "words": [
                {"word": "समुद्र", "start": 10.4, "end": 11.4},
                {"word": "मंथन", "start": 11.4, "end": 12.5},
                {"word": "शुरू", "start": 12.5, "end": 13.5},
                {"word": "हुआ", "start": 13.5, "end": 14.5},
            ],
        },
    ]
    (stage_dir / "captions" / "captions_data.js").write_text(
        f"window.CAPTIONS_DATA = {json.dumps(captions_data, ensure_ascii=False, indent=2)};\n",
        encoding="utf-8",
    )

    episode_plan = {
        "duration_sec": 15.0,
        "enable_contextual_pills": True,
        "vignette_strength": 0.40,
        "grain_alpha": 0.022,
        "scenes": [
            {
                "s0": 0.0,
                "s1": 5.0,
                "pill_kicker": "SACRED PEAK",
                "pill_title": "Kailash Horizon & Shiva",
                "environment": {
                    "atmosphere_mode": "kailash_twilight",
                    "horizon_y": 1142,
                    "has_kailash": True,
                    "kailash_scale": 1.24,
                    "flora": True,
                    "snow_boulders": True,
                },
                "props": [{"id": "trishul", "x": 210, "y": 1142, "h": 410}],
                "characters": [
                    {
                        "x": 540,
                        "y": 1142,
                        "scale": 1.18,
                        "role": "shiva",
                        "pose": "palm_cup",
                        "expr": "determined",
                        "speaking": True,
                        "neelakantha": 1.0,
                        "halahalaInHand": 0.9,
                    }
                ],
            },
            {
                "s0": 5.0,
                "s1": 10.0,
                "transition_type": "iris",
                "transition_duration_sec": 0.36,
                "pill_kicker": "BRAHMALOKA SABHA",
                "pill_title": "King Kakudmi & Revati",
                "environment": {
                    "atmosphere_mode": "palace_interior",
                    "horizon_y": 1142,
                    "has_diyas": True,
                },
                "stage_elements": [
                    {"type": "royal_music_stage", "x": 540, "daisBot": 1218},
                    {"type": "pillar", "x": 140, "floorY": 1142, "topY": 0, "w": 64},
                ],
                "props": [
                    {"id": "brass_clock", "x": 540, "y": 540, "r": 128},
                    {"id": "hourglass_stand", "x": 850, "y": 1142},
                ],
                "characters": [
                    {"x": 380, "y": 1142, "scale": 1.05, "role": "kakudmi", "pose": "namaskar", "expr": "awed"},
                    {"x": 690, "y": 1142, "scale": 1.0, "role": "revati", "pose": "veena_play", "expr": "serene"},
                ],
            },
            {
                "s0": 10.0,
                "s1": 15.0,
                "transition_type": "whip",
                "transition_duration_sec": 0.36,
                "environment": {
                    "atmosphere_mode": "cosmic_manthan",
                    "horizon_y": 1142,
                    "ridge_set": "cosmos",
                    "flora": False,
                    "snow_boulders": False,
                },
                "props": [
                    {"id": "kalachakra", "x": 540, "y": 640, "r": 210},
                    {"id": "kurma_avatar", "x": 540, "y": 1180, "scale": 0.9},
                    {"id": "mount_mandara", "x": 540, "y": 1120, "erupt": 0.3, "scale": 0.9},
                    {"id": "cosmic_ocean", "erupt": 0.3, "baseStartY": 1140},
                    {"id": "vasuki_serpent", "erupt": 0.3, "churnOsc": 0.25, "layer": "front"},
                    {"id": "amrita_kalash", "x": 220, "y": 1142, "scale": 0.95},
                    {"id": "iron_pillar", "x": 870, "y": 1142, "height": 420},
                ],
                "characters": [
                    {"x": 340, "y": 1142, "scale": 1.02, "role": "vishnu", "pose": "pull", "expr": "determined"},
                ],
            },
        ],
    }

    cover_config = {
        "seed": 701,
        "backdrop": "cosmic_dawn",
        "horizon_y": 1445,
        "kailash": {"x": 540, "base_y": 1452, "scale": 1.66, "snow_tint": "rgba(226, 240, 255, 0.72)", "shadow_tint": "#181E46", "gold_rim": 0.75},
        "props": [{"id": "trishul", "x": 195, "y": 1585, "scale": 1.35, "h": 452}],
        "characters": [
            {
                "x": 495,
                "y": 1640,
                "scale": 1.38,
                "dir": 1,
                "role": "shiva",
                "pose": "palm_cup",
                "expr": "determined",
                "turn": 0.08,
                "neelakantha": 1.0,
                "halahalaInHand": 1.18,
                "halahalaColor": "emerald",
            }
        ],
    }

    jenv_rt = Environment(loader=FileSystemLoader(str(REPO_ROOT / "templates" / "runtime")))
    (stage_dir / "index.html").write_text(
        jenv_rt.get_template("index.html.jinja2").render(
            title="Phase 2 Verification Sample",
            fonts_css="fonts/fonts.css",
            styles_css="styles.css",
            gsap_src="lib/gsap.min.js",
            captions_data_js="captions/captions_data.js",
            captions_src="captions/captions.html",
            runtime_base="./runtime",
            audio_src="audio/bgm.mp3",
            duration_sec=15.0,
            episode_runtime_json=json.dumps(episode_plan, ensure_ascii=False),
        ),
        encoding="utf-8",
    )

    jenv_cap = Environment(loader=FileSystemLoader(str(REPO_ROOT / "templates" / "runtime" / "captions")))
    (stage_dir / "captions" / "captions.html").write_text(
        jenv_cap.get_template("captions.html.jinja2").render(
            fonts_css="../fonts/fonts.css",
            gsap_src="../lib/gsap.min.js",
            captions_data_js="captions_data.js",
            duration_sec=15.0,
        ),
        encoding="utf-8",
    )

    jenv_cov = Environment(loader=FileSystemLoader(str(REPO_ROOT / "templates" / "thumbnail")))
    thumb_dir = stage_dir / "thumb"
    shutil.copytree(REPO_ROOT / "assets" / "fonts", thumb_dir / "fonts", dirs_exist_ok=True)
    (thumb_dir / "lib").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "assets" / "js" / "gsap.min.js", thumb_dir / "lib" / "gsap.min.js")
    shutil.copytree(REPO_ROOT / "templates" / "runtime", thumb_dir / "runtime", dirs_exist_ok=True)
    (thumb_dir / "index.html").write_text(
        jenv_cov.get_template("cover_template.html.jinja2").render(
            page_title="Episode 4 Thumbnail Verification",
            fonts_css="fonts/fonts.css",
            gsap_src="lib/gsap.min.js",
            runtime_base="./runtime",
            pill_text="SAMUDRA MANTHAN",
            headline_1="WHY SHIVA",
            headline_2="DRANK POISON",
            sub_pill="THE ORIGIN OF NEELAKANTHA",
            footer_text="SUTRADHAR · ANCIENT EPICS",
            cover_config_json=json.dumps(cover_config, ensure_ascii=False),
        ),
        encoding="utf-8",
    )


class TestSutradharPhase2Runtime(unittest.TestCase):
    def test_manifest_v2_and_curated_assets(self) -> None:
        manifest_path = REPO_ROOT / "assets" / "manifest.yaml"
        self.assertTrue(manifest_path.is_file(), "assets/manifest.yaml missing")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("schema_version"), "2.0.0")

        # Fonts promoted cleanly with zero remote links
        fonts_dir = REPO_ROOT / "assets" / "fonts"
        woffs = list(fonts_dir.glob("*.woff2"))
        self.assertEqual(len(woffs), 31)
        fonts_css = (fonts_dir / "fonts.css").read_text(encoding="utf-8")
        self.assertNotIn("https://", fonts_css)
        self.assertNotIn("http://", fonts_css)
        for wf in woffs:
            self.assertIn(wf.name, fonts_css)

        # Curated unique BGM library (0 duplicate MD5s)
        bgm_dir = REPO_ROOT / "assets" / "audio" / "bgm"
        self.assertTrue((bgm_dir / "CREDITS.md").is_file())
        bgm_files = sorted(bgm_dir.glob("*.mp3"))
        self.assertGreaterEqual(len(bgm_files), 8)
        md5s = [hashlib.md5(p.read_bytes()).hexdigest() for p in bgm_files]
        self.assertEqual(len(md5s), len(set(md5s)), "Duplicate MD5 hashes found in assets/audio/bgm/")
        for stem, info in manifest["audio"]["bgm"].items():
            self.assertTrue((REPO_ROOT / info["file"]).is_file(), f"Missing manifest BGM: {stem}")

        # Unified SFX catalog
        sfx_dir = REPO_ROOT / "assets" / "audio" / "sfx"
        self.assertTrue((sfx_dir / "CREDITS.md").is_file())
        self.assertGreaterEqual(len(list(sfx_dir.glob("*.mp3"))), 19)
        self.assertGreaterEqual(len(list(sfx_dir.glob("*.wav"))), 17)

        # Parametric JSON registries match manifest v2
        self.assertEqual(len(manifest["characters"]), 12)
        self.assertEqual(len(manifest["environments"]), 8)
        self.assertEqual(len(manifest["props"]), 17)
        for section in ("characters", "environments", "props"):
            for item_id, entry in manifest[section].items():
                p = REPO_ROOT / entry["file"]
                self.assertTrue(p.is_file(), f"Missing {section}/{item_id}: {p}")
                parsed = json.loads(p.read_text(encoding="utf-8"))
                self.assertEqual(parsed["id"], item_id)

        # Cover template uses Inter 800 (matching bundled Inter woff2 weights) and no 900 fallback
        cover_tpl = (REPO_ROOT / "templates" / "thumbnail" / "cover_template.html.jinja2").read_text(encoding="utf-8")
        self.assertIn("font-weight: 800;", cover_tpl)
        self.assertNotIn("font-weight: 900", cover_tpl)

    def test_hyperframes_strict_check_and_chromium_determinism(self) -> None:
        import tempfile

        chrome_exe = _find_chrome_executable()
        with tempfile.TemporaryDirectory(prefix="sutradhar_p2_rt_", ignore_cleanup_errors=True) as tmp:
            stage_dir = Path(tmp)
            _stage_sample_composition(stage_dir)

            # 1. Run HyperFrames strict Shorts safe-zone check on video + standard safe-zone check on cover
            # NOTE: --no-craft avoids complaining when a 15s test fixture omits multi-track narration/SFX checks
            # while still running HTML/JS lint, Chromium runtime validation, contrast, and layout safe-zone checks.
            for label, check_cwd, safe_zone in [
                ("main", stage_dir, "shorts"),
                ("thumb", stage_dir / "thumb", "standard"),
            ]:
                cmd = _hyperframes_command() + [
                    "check",
                    ".",
                    "--strict",
                    "--safe-zone",
                    safe_zone,
                    "--no-craft",
                    "--no-cache",
                    "--no-browser-gpu",
                    "--json",
                ]
                proc = subprocess.run(cmd, cwd=str(check_cwd), capture_output=True, text=True, timeout=180)
                self.assertEqual(
                    proc.returncode,
                    0,
                    f"hyperframes check failed for {label} (rc={proc.returncode}):\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
                )

            # 2. Run headless Chromium runtime probe via installed puppeteer-core:
            #    - 0 console/page errors
            #    - Inter 800, Cinzel 800, Noto Sans Devanagari 800 loaded
            #    - Contextual pill inside [48..888, 288..1248]
            #    - Captions inside [48..888, 1244..1390]
            #    - Kailash snow mask strictly bounded inside KAILASH_SILHOUETTE_POINTS (0 pixel overhang)
            #    - hf-seek(7.5s) deterministic parity against scrub 0 -> 2.5 -> 5.0 -> 12.6 -> 7.5s
            server, port = _serve_directory(stage_dir)
            try:
                node_script = r"""
const fs = require("fs");
const path = require("path");
const puppeteer = require(path.join(process.env.REPO_ROOT, "node_modules", "puppeteer-core"));

(async () => {
  const chromePath = process.env.CHROME_EXE;
  const baseUrl = process.env.BASE_URL;
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ["--no-sandbox", "--disable-gpu", "--use-gl=angle", "--use-angle=swiftshader-webgl", "--enable-webgl"],
  });
  const errors = [];
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
    page.on("pageerror", (err) => errors.push("pageerror: " + err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push("console.error: " + msg.text());
    });

    // Check main composition
    await page.goto(baseUrl + "/index.html", { waitUntil: "networkidle0" });
    await page.evaluate(() => window.__sutradharFontsReady);

    const fontStatus = await page.evaluate(async () => {
      await document.fonts.load('800 46px "Noto Sans Devanagari"', "शांत");
      return {
        inter800: document.fonts.check('800 31px "Inter"'),
        cinzel800: document.fonts.check('800 98px "Cinzel"'),
        devanagari800: document.fonts.check('800 46px "Noto Sans Devanagari"', "शांत"),
      };
    });

    // Seek directly to 2.5s to verify pill box
    const pillRect = await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: 2.5 } }));
      const el = document.getElementById("contextual-overlay");
      const r = el.getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, opacity: Number(getComputedStyle(el).opacity) };
    });

    // Deterministic hf-seek test: jump direct to 7.5s, then scrub forward/backward back to 7.5s
    const capturePng = async (t) => {
      return await page.evaluate((sec) => {
        window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: sec } }));
        return document.getElementById("world-canvas").toDataURL("image/png");
      }, t);
    };
    const seek2_5 = await capturePng(2.5);
    const seek7_5_direct = await capturePng(7.5);
    await capturePng(12.6);
    await capturePng(0.0);
    const seek7_5_after_scrub = await capturePng(7.5);
    const seek12_6 = await capturePng(12.6);

    // Check Kailash snow peak clipping bounds directly inside module context:
    // 1) All snow fills (goldRim=0, bright pixels b > 130) lie 100% inside the un-stroked silhouette fill
    // 2) Entire drawing incl. 3.2px dark/gold rim strokes stays within perimeter stroke tolerance (lineWidth = 8)
    const kailashBounds = await page.evaluate(async () => {
      const mod = await import(window.location.origin + "/runtime/backdrops/atmosphere_v1.js");
      const cFillMask = document.createElement("canvas");
      cFillMask.width = 1080; cFillMask.height = 1920;
      const fCtx = cFillMask.getContext("2d");
      fCtx.save();
      fCtx.translate(540, 1452);
      fCtx.scale(1.66, 1.66);
      mod.traceKailashSilhouette(fCtx);
      fCtx.fillStyle = "#FFFFFF";
      fCtx.fill();
      fCtx.restore();

      const cStrokeMask = document.createElement("canvas");
      cStrokeMask.width = 1080; cStrokeMask.height = 1920;
      const sCtx = cStrokeMask.getContext("2d");
      sCtx.save();
      sCtx.translate(540, 1452);
      sCtx.scale(1.66, 1.66);
      mod.traceKailashSilhouette(sCtx);
      sCtx.fillStyle = "#FFFFFF";
      sCtx.fill();
      sCtx.lineWidth = 8.0;
      sCtx.lineJoin = "miter";
      sCtx.strokeStyle = "#FFFFFF";
      sCtx.stroke();
      sCtx.restore();

      const cPeak = document.createElement("canvas");
      cPeak.width = 1080; cPeak.height = 1920;
      const pCtx = cPeak.getContext("2d");
      mod.drawKailashSacredPeak(pCtx, 540, 1452, 1.66, "rgba(226, 240, 255, 0.72)", "#181E46", 0.0);

      const fData = fCtx.getImageData(0, 0, 1080, 1920).data;
      const sData = sCtx.getImageData(0, 0, 1080, 1920).data;
      const pData = pCtx.getImageData(0, 0, 1080, 1920).data;
      let leakedOuter = 0;
      let leakedSnow = 0;
      let drawn = 0;
      for (let i = 0; i < pData.length; i += 4) {
        const a = pData[i + 3];
        if (a > 0) {
          drawn++;
          if (sData[i + 3] === 0) leakedOuter++;
          if (fData[i + 3] === 0 && pData[i + 2] > 110) leakedSnow++;
        }
      }
      return { drawn, leakedOuter, leakedSnow };
    });

    // Check captions composition
    await page.goto(baseUrl + "/captions/captions.html", { waitUntil: "networkidle0" });
    await page.evaluate(() => window.__sutradharFontsReady);
    const captionCheck = await page.evaluate(async () => {
      window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: 2.3 } }));
      await document.fonts.ready;
      const loadedDeva = [...document.fonts].some(
        (f) => f.family.replace(/['"]/g, "") === "Noto Sans Devanagari" && f.weight === "800" && f.status === "loaded"
      );
      const g = document.getElementById("caption-group").getBoundingClientRect();
      const active = document.querySelector(".cap-word.active");
      const at0 = (() => {
        window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: 0.0 } }));
        return document.getElementById("caption-line").textContent;
      })();
      window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: 2.3 } }));
      const at23 = document.getElementById("caption-line").textContent;
      return {
        left: g.left, top: g.top, right: g.right, bottom: g.bottom,
        loadedDeva,
        activeWord: active ? active.textContent : null,
        at0, at23,
      };
    });

    // Check cover composition
    await page.goto(baseUrl + "/thumb/index.html", { waitUntil: "networkidle0" });
    await page.evaluate(() => window.__sutradharFontsReady);
    const thumbFontCheck = await page.evaluate(() => {
      const pill = document.querySelector(".pill");
      return {
        inter800: document.fonts.check('800 31px "Inter"'),
        cinzel800: document.fonts.check('800 98px "Cinzel"'),
        pillWeight: getComputedStyle(pill).fontWeight,
        canvasBytes: document.getElementById("thumb-canvas").toDataURL("image/png").length,
      };
    });

    console.log(JSON.stringify({
      errors,
      fontStatus,
      pillRect,
      kailashBounds,
      captionCheck,
      thumbFontCheck,
      seekExactParity: seek7_5_direct === seek7_5_after_scrub,
      seekDistinct25vs75: seek2_5 !== seek7_5_direct,
      seekDistinct75vs126: seek7_5_direct !== seek12_6,
    }));
  } finally {
    await browser.close();
  }
})();
"""
                env = os.environ.copy()
                env["REPO_ROOT"] = str(REPO_ROOT)
                env["CHROME_EXE"] = str(chrome_exe)
                env["BASE_URL"] = f"http://127.0.0.1:{port}"
                res = subprocess.run(
                    ["node", "-"],
                    input=node_script,
                    text=True,
                    capture_output=True,
                    env=env,
                    timeout=120,
                    check=True,
                )
                telemetry = json.loads(res.stdout.strip().splitlines()[-1])
                self.assertEqual(telemetry["errors"], [], f"Browser console/page errors: {telemetry['errors']}")
                self.assertTrue(telemetry["fontStatus"]["inter800"])
                self.assertTrue(telemetry["fontStatus"]["cinzel800"])
                self.assertTrue(telemetry["fontStatus"]["devanagari800"])

                pill = telemetry["pillRect"]
                self.assertGreaterEqual(pill["left"], 48)
                self.assertLessEqual(pill["right"], 888)
                self.assertGreaterEqual(pill["top"], 288)
                self.assertLessEqual(pill["bottom"], 1248)
                self.assertGreater(pill["opacity"], 0.9)

                self.assertGreater(telemetry["kailashBounds"]["drawn"], 10000)
                self.assertEqual(
                    telemetry["kailashBounds"]["leakedOuter"],
                    0,
                    f"Kailash drawing leaked past outer stroke envelope: {telemetry['kailashBounds']}",
                )
                self.assertEqual(
                    telemetry["kailashBounds"]["leakedSnow"],
                    0,
                    f"Kailash bright snow pixels leaked past polygon fill: {telemetry['kailashBounds']}",
                )

                cap = telemetry["captionCheck"]
                self.assertGreaterEqual(cap["left"], 48)
                self.assertLessEqual(cap["right"], 888)
                self.assertGreaterEqual(cap["top"], 1244)
                self.assertLessEqual(cap["bottom"], 1390)
                self.assertTrue(cap["loadedDeva"], "Noto Sans Devanagari 800 font failed to load in captions")
                self.assertEqual(cap["activeWord"], "शांत")
                self.assertEqual(cap["at0"], "")

                self.assertEqual(telemetry["thumbFontCheck"]["pillWeight"], "800")
                self.assertTrue(telemetry["thumbFontCheck"]["inter800"])
                self.assertTrue(telemetry["thumbFontCheck"]["cinzel800"])

                self.assertTrue(telemetry["seekExactParity"], "hf-seek parity failed after scrub")
                self.assertTrue(telemetry["seekDistinct25vs75"])
                self.assertTrue(telemetry["seekDistinct75vs126"])
            finally:
                server.shutdown()
                server.server_close()
