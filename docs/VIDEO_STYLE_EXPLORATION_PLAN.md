# Sutradhar Video Style Exploration & Redesign Context

> **Status:** Active Visual Exploration Stage (Pre-Implementation)
> **Rule of Thumb:** Do **NOT** modify production code, assets, config, DB, docs instructions, tests, or dependencies until a visual direction is explicitly selected by the user and the full implementation plan is approved.

---

## 1. Purpose of This Document

This document preserves the complete audit context, hard resource constraints, language policy, previous Proof-of-Concept (POC) outcomes, and ongoing reference-video style experiments for **Sutradhar**. Any engineer or AI agent picking up this project should be able to resume directly from this record without re-auditing the repository from scratch.

---

## 2. Ultimate Objective

Build a highly automated, reliable, professional-quality **2D/2.5D animated YouTube Shorts** production pipeline in `Sutradhar` capable of producing **30 publication-ready Shorts per month** telling Indian cosmic, Vedic, Puranic, and ancient-science stories at cinematic visual standards — strictly within zero additional budget.

---

## 3. Non-Negotiable Constraints (Budget, Model & Tools)

1. **Available Paid Subscriptions ONLY:**
   - **Antigravity subscription** (access strictly limited to the **Hydrogen** model — no Carbon, Argon, or external paid LLM APIs).
   - **ElevenLabs Starter subscription** ONLY.
2. **$0 Additional Spending Requirement:**
   - No Nano Banana, Veo, HeyGen paid credits, Runway, Midjourney, paid stock subscriptions, or separately billed image/video generation APIs.
   - All visuals, rigging, procedural 2.5D animation, lighting, particles, shaders, camera movement, audio mixing, captioning, and thumbnail composition must execute using **Hydrogen**, **HyperFrames** (`0.9.70` installed locally), **FFmpeg**, open-source JS/CSS/Canvas/SVG/WebGL libraries (MIT/BSD/Apache/Unlicense/SIL OFL), and locally runnable free tools.
3. **Monthly Volume Target:** **30 YouTube Shorts per month**.

### ElevenLabs Starter Quota & Feasibility Math (Verified Against Live Account & DB)

- **Plan limits (verified on account):** `30,000` credits/month base renewal (unused credits roll over up to `3×`). Live snapshot at audit start: `used = 2,155`, `limit = 37,188`, `remaining = 35,033`.
- **Voice & model (`config.yaml`):** `eleven_v4` with Viraj (`uuyFQegRan8rpIQCGu9K`), billing **`1` credit per character** including inline v4 expression tags (e.g., `[slow]`, `[thoughtful]`, `[reverent]`).
- **Observed Episode 1–3 script lengths (`episodes.db`):** `1,018`, `805`, and `917` raw Devanagari characters (average `~913` raw chars; `~960–1,050` billed chars once inline tags are included).
- **30-Short Monthly Projection:**
  - At `~950–1,050` billed chars/Short and zero retries (`1.0×`), consumption is **`28,500–31,500` credits/month** — sitting right on or slightly above the `30,000` base renewal.
  - A modest `15%` regeneration/retry rate pushes usage to **`~32,800–36,200` credits/month**, exhausting the monthly base allowance.
- **Required Zero-Spend Mitigations (Target Design):**
  1. Strict pre-TTS Hindi script budget (`<= 850–900` billed chars including tags -> `~25,500–27,000` credits/month for 30 Shorts, leaving ~10–15% buffer).
  2. Strict pre-flight Devanagari + tag syntax validation before calling the ElevenLabs API.
  3. Zero automatic blind TTS retry loops; immutable SHA-256 content-addressed WAV/manifest caching per episode/scene.
  4. Zero paid TTS calls during visual experimentation/POC iterations (reuse cached Episode 3 narration `build/audio/narration_full.wav`).

---

## 4. Established Language & Metadata Policy

| Surface | Required Language | Notes |
| --- | --- | --- |
| **Voiceover / Narration** | Hindi (Devanagari source text) | Viraj (`eleven_v4`) |
| **Burned-In Kinetic Captions** | Hindi (Devanagari) | Centered bottom-center inside Shorts safe zone, accurately word/phrase-synced |
| **Contextual On-Screen Text** | Minimal Hindi / English where genuinely helpful | Strictly essential context only, **top-center** aligned, zero clutter/redundant headers |
| **Thumbnail Text** | English | Dedicated high-contrast thumbnail composition (`1080×1920` or channel standard), NOT a raw video frame grab |
| **YouTube Metadata (Title, Description, Tags, Playlists)** | English | `defaultAudioLanguage: hi`, `defaultLanguage: en` |

> **Note:** Several existing production files conflict on captioning and metadata language (`docs/INSTRUCTIONS.md` line 24 vs line 35 vs line 165, `README.md`, `db_manager.py`, `publish_youtube.py`). Those conflicts remain documented for the eventual production implementation phase and must NOT be modified yet.

---

## 5. Original Codebase Audit Summary (Baseline ~1/10 Video Quality Root Causes)

Baseline `pytest -q` passed (`249 passed in 198.29s`), proving unit tests pass while the rendered video suffers severe defects:

1. **Broken HyperFrames Deterministic Seek Contract:** Production generates `paused: false` timelines, uses `.call()` DOM mutations that vanish/skip during headless Chromium frame seeking (`render --workers`), detaches `lipTl` and runs standalone `gsap.to`/`delayedCall`, and drops a monolithic 4,606-line `index.html` outside the project root — yielding `sweep_static` failures and ~`62.5%` static frames.
2. **Silent Vanished Subtitles:** `subtitle_engine.py` reads `"start_sec"`/`"end_sec"` while `build_audio.py` writes `"start"`/`"global_start"`, collapsing all cues to `0..0.42s` behind closed theater curtains, compounded by missing Devanagari `@font-face` declarations.
3. **Broken Whisper Alignment on Episode 3:** `faster-whisper base` fails on PyAV stream decode unless fed `ffmpeg 16kHz` PCM, and drifts heavily on Scene 6 (`45.53s..53.98s`), requiring RMS speech-burst alignment verification.
4. **Frozen Puppet Rigging & Staging:** `composer.py` ignores single-character framing (`primaryStagingStyle`) and camera instructions like `"slow_push"`, mounts all characters together, lacks target CSS variables/group IDs (`--rot-*`, `#torso_group`, `#eyes_normal`, `#mouth_shout/fear/joy`) on SVGs like `sutradhar_narrator.svg`, and hides SVG elements with `display: none`.
5. **Dropped VFX / Infographics / Transitions:** Production manifests leave `"vfx_elements": []`, omitting meaningful atmosphere, transitions, and scientific/cosmic explanatory visuals.
6. **Low-Craft Stage Framing & Dark Cast:** Rigid `48px` proscenium pillars, `120px` top valance, and `520px` dead black bottom void box stick-doll SVGs into a dim frame (`y_avg = 43.8`, `sat = 7.83%`, `53.7%` magenta/red cast).
7. **False-Green QA Gates:** `preview_frames.py` skips `hyperframes check --json`; `render_and_qa.py` inspects a nonexistent `checkpoint_res.get("passed")` key while running KinoCut on `ui-capture-dark`.
8. **Weak Thumbnail & Synthetic BGM:** Thumbnail saves a raw JPEG grab from the dark MP4 instead of a designed English-title poster; BGM relies on pure synthetic sine drones in `build_assets.py`.

---

## 6. Previous POC Phase Outcomes (Round 1: V1, V2, V3)

All Round 1 POCs used cached Episode 3 narration (`63.503s`, `0` ElevenLabs credits), local OFL fonts (`Noto Sans Devanagari`, `Tiro Devanagari Hindi`, `Rozha One`, `Cormorant Garamond`, `Cinzel`, `Inter`), local GSAP, and `1080×1920 @ 30fps` inside `%LOCALAPPDATA%\Temp\sutradhar_poc\`.

### Summary of Round 1 Decisions

| Version | Direction | Status | Measured Metrics & User Verdict |
| --- | --- | --- | --- |
| **V1 — Dawn Ridge** | Painterly atmospheric 2.5D layered SVG/Canvas cosmic + mythological landscapes with cleaned top-center text & bottom-center Hindi kinetic captions | **PROVISIONALLY APPROVED (Benchmark Only — NOT Final Choice)** | `v1_dawn_ridge.mp4` (`107.58 MB`, `63.503s`, `1080×1920`, `30fps`, `-14.0 LUFS`). HyperFrames Strict Check **7/7 `ok: true` (`0` errors, `0` warnings)**. KinoCut default `57.0` (`y_avg=73.8`, `contrast=32.8`, `sat=8.9%`, `temporal_motion=96.3` / `4%` static); KinoCut dark `88.8`. Preserved intact in `playground/v1_dawn_ridge_benchmark/` and `%LOCALAPPDATA%\Temp\sutradhar_poc\v1_dawn_ridge*`. |
| **V2 — Illuminated Paper-Cut Diorama** | Multi-layer parchment & paper-cut craft diorama | **COMPLETELY REJECTED** | Rejected by user. Do not pursue or reuse this visual direction. |
| **V3 — WebGL 3D Cosmic Cinema** | WebGL / Three.js 3D volumetric cosmic scene | **COMPLETELY REJECTED** | Rejected by user. Do not pursue or reuse this visual direction. |

> **Important:** `V1 — Dawn Ridge` is our minimum **quality baseline and comparison benchmark**, NOT our final selected visual direction.

---

## 7. Current Phase: Reference-Driven Style Exploration (Round 2)

### Reference Videos Under Study

1. **Reference 1:** `https://www.youtube.com/shorts/inbAAQMK8vs`
2. **Reference 2:** `https://www.youtube.com/shorts/XPWJGGvpA28`
3. **Reference 3:** `https://www.youtube.com/shorts/UWjpa9rpkwk`

> Strictly for technical study and inspiration. Zero copyrighted video, audio, artwork, or brand assets from any reference may ever be reused directly.

### Organized Experimental Workspace (`playground/`)

All new exploration materials live exclusively inside `playground/` (leaving every production file untouched):

- `playground/references/` — Downloaded reference MP4s and metadata JSONs
- `playground/analysis/` — Scene-by-scene technical breakdowns (`ref1_analysis.md`, `ref2_analysis.md`, `ref3_analysis.md`) + `tool_research.md` + extracted timeline contact sheets & cut closeups
- `playground/shared/` — Cached master Episode 3 audio (`master_mix_poc.wav`), aligned Hindi captions (`captions_data.js`), local SIL OFL fonts, local GSAP
- `playground/v1_dawn_ridge_benchmark/` — Preserved copy of V1 MP4, English thumbnail, contact sheet, quality report, and HTML/JS sources
- `playground/scripts/` — Reusable POC analysis, frame-check, render, grid, and quality-report tooling
- `playground/exp_ref1/`, `playground/exp_ref2/`, `playground/exp_ref3/` — Three genuinely distinct new 2.5D style POCs (sources, preview captures, final MP4s, English thumbnails, review grids, quality reports)

### Fixed Composition & Verification Rules Across All New POCs

- Story & Audio: Episode 3 (`ब्रह्मलोक और राजा ककुद्मी की समय-यात्रा`, `63.503s`, cached `master_mix_poc.wav`, **0** ElevenLabs credits spent).
- Typography Layout:
  - No top-left episode banners, badges, or redundant metadata boxes.
  - Strictly necessary minimal contextual labels at **top-center** only (`top >= 288px`, centered cleanly around `X = 540px`).
  - Hindi kinetic captions at **bottom-center** inside YouTube Shorts safe band (`top ~1248–1280px`, `Y <= 1400px` clear of bottom UI).
  - Dedicated **English thumbnail** created specifically for each style.
- Quality Gates:
  - Must pass `hyperframes check --strict --safe-zone shorts` (`0` errors) and custom temporal/frame visual inspections directly on the **rendered MP4s** before reporting results.

---

## 8. Production Codebase Immutability Boundary

Until the user reviews the 4-way comparison (`V1 Dawn Ridge` vs `Ref 1 POC` vs `Ref 2 POC` vs `Ref 3 POC`), picks a direction, and approves an implementation plan, the following MUST remain completely untouched:

- `scripts/`, `templates/`, `assets/`, `tests/`
- `config.yaml`, `episodes.db`, `requirements.txt`, `package.json`, `package-lock.json`
- `docs/INSTRUCTIONS.md`, `docs/schema.sql`, `docs/SETUP_AND_OPERATIONS.md`, `README.md`
- `.venv/` Python environment

---

## 9. Reference Breakdowns & Experiment Log (Updated As Work Progresses)

- *Pending Step 2–3:* Download and scene-by-scene technical breakdown of `inbAAQMK8vs`, `XPWJGGvpA28`, `UWjpa9rpkwk`.
- *Pending Step 4:* Free/OSS tooling & library verification (`tool_research.md`).
- *Pending Step 5–6:* Rendered metrics and visual review links for `exp_ref1`, `exp_ref2`, `exp_ref3`.
