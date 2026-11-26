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

## 7. Reference-Driven Exploration & Cleanup History (Round 2 -> Two Final Candidates)

### Rejected Experiments & Cleanup Completed

- **Rejected Styles (Removed from Active Development):** `V2` (Paper-Cut Diorama), `V3` (WebGL 3D), Reference 2 (`XPWJGGvpA28`), Reference 3 (`UWjpa9rpkwk`), and Round-2 drafts `exp_ref1`, `exp_ref2`, `exp_ref3`. All rejected POC directories, temporary proxies, and download copies were cleanly removed so `playground/` remains focused and uncluttered.
- **Preserved Benchmark:** Original [`V1 — Dawn Ridge`](file:///C:/Users/manis/Projects/Sutradhar/playground/v1_dawn_ridge_benchmark/v1_dawn_ridge.mp4) (`107.58 MB`, `63.503s`, `1080×1920@30fps`) remains intact inside `playground/v1_dawn_ridge_benchmark/` as the quality baseline.
- **Retained Study Reference:** Reference 1 ([`inbAAQMK8vs`](file:///C:/Users/manis/Projects/Sutradhar/playground/analysis/ref1_analysis.md), `Ravin docx`, `3.66M` views) studied for anatomical vector rig staging, theatrical wainscoting/perspective interiors, infographic flow props, horizontal camera pans/whip-pans, and snappy acoustic foley pacing. Zero copyrighted Ref-1 assets are reused.

### Clean Experimental Workspace (`playground/`)

All exploration materials live exclusively inside `playground/` (leaving every production file untouched):

- `playground/references/` — Reference 1 (`ref1_inbAAQMK8vs`) study video & metadata JSON
- `playground/analysis/` — `ref1_analysis.md`, `ep3_script_timeline.txt`, `candidates_shot_plan.md`, `v1_timeline_sheet.jpg`, `tool_research.md`, `hf_catalog.json`
- `playground/shared/` — Cached Episode 3 narration-derived master audio (`master_mix_poc.wav`, custom `mix_candidate_a.wav` & `mix_candidate_b.wav` with **0** ElevenLabs credits spent), aligned Hindi captions (`captions_data.js`), local SIL OFL fonts, local GSAP
- `playground/v1_dawn_ridge_benchmark/` — Preserved untouched copy of original V1 benchmark MP4, English thumbnail, grid, and report
- `playground/scripts/` — Shared HTML/caption composer (`poc_shared_composer.py`), audio mixer (`mix_candidate_audio.py`), check/preview/render runner (`poc_runner.py`), `build_candidate_a.py`, `build_candidate_b.py`
- `playground/candidate_a_dawn_ridge/` — Final **Candidate A** full MP4, bespoke English thumbnail, 15-frame preview & MP4 contact sheets, quality report, and sources
- `playground/candidate_b_ref1_cinematic/` — Final **Candidate B** full MP4, bespoke English thumbnail, 15-frame preview & MP4 contact sheets, quality report, and sources

### Fixed Composition & Verification Rules Across Final Candidates

- **Story & Audio:** Episode 3 (*ब्रह्मलोक और राजा ककुद्मी की समय-यात्रा*, `63.503s`, cached narration + local `assets/bgm/` + local/HyperFrames SFX, **0** ElevenLabs credits spent).
- **Typography Layout (`>= 28px` craft floor):** Zero top-left episode labels; minimal contextual top-center anchors (`top: 288px`); bottom-center synchronized Devanagari kinetic captions (`top: 1250px`, generous inter-word padding/gap preventing collision on scaled Devanagari words); custom English `1080×1920` poster thumbnails built via dedicated `thumb/index.html`.
- **Quality Gates:** Verified end-to-end via `hyperframes check --strict --safe-zone shorts` (**0 errors, 0 warnings**), `hyperframes measure look`, FFprobe, KinoCut `default`/`ui-capture-dark`, 15-frame MP4 review sheets, and full visual/audio playback watch-through directly on the rendered MP4s.

---

## 8. Production Codebase Immutability Boundary

Until the user reviews the side-by-side comparison between **Candidate A** and **Candidate B**, selects a final direction, and approves the implementation plan, the following MUST remain completely untouched:

- `scripts/`, `templates/`, `assets/`, `tests/`
- `config.yaml`, `episodes.db`, `requirements.txt`, `package.json`, `package-lock.json`
- `docs/INSTRUCTIONS.md`, `docs/schema.sql`, `docs/SETUP_AND_OPERATIONS.md`, `README.md`
- `.venv/` Python environment

---

## 9. Final Two-Candidate Comparison & Measured Telemetry (`playground/two_candidate_comparison.json`)

| Direction | Render Specs & Sizes | HyperFrames Strict Check | Look Telemetry (`luma / contrast / sat / warmth`) | KinoCut Scores (`default` / `ui-capture-dark` / `static_frac`) | Creative & Motion Summary |
| --- | --- | --- | --- | --- | --- |
| **Baseline `V1 — Dawn Ridge`** ([MP4](file:///C:/Users/manis/Projects/Sutradhar/playground/v1_dawn_ridge_benchmark/v1_dawn_ridge.mp4)) | `107.58 MB` · `63.503s` · `1080×1920@30fps` | `ok: true` (`0` errors, `0` warnings) | `68.7 / 39.9 / 0.436 / —` | `57.0` / `88.8` / `3.7%` static | Original benchmark with atmospheric silhouettes, static mid-scenes & matte dark bottom void |
| **Candidate A — Refined Dawn Ridge** ([MP4](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_a_dawn_ridge/candidate_a_dawn_ridge.mp4) · [Thumb](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_a_dawn_ridge/candidate_a_dawn_ridge_thumbnail.jpg) · [Grid](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_a_dawn_ridge/candidate_a_dawn_ridge_review_grid.jpg)) | `49.08 MB` · `63.533s` · `1080×1920@30fps` · `thumb 270 KB` | **`ok: true` (`0` errors, `0` warnings)** | `51.0 / 37.9 / 0.570 / -4.9` | `50.2` / `86.6` (**`temporal_motion 88.2`**, **`11.8%` static**, audio `96.4`) | Elevated V1 painter-cinematic style: `14` continuous sub-beats, mirrored starlight lake/ghat lower third + floating clay diyas, 3-dome Vimana ascent, Rajasthani cusped Sabha + Veena soundwaves + dolly pan, sculptural 4-armed Lotus Brahma & 27 spokes, 3D spacetime mesh + Vedic Armillary Sphere, Marigold/Agni Halayudha Balarama wedding, fracturing clock -> 27-star Infinity Prana finale |
| **Candidate B — Ref-1 Cinematic Vector** ([MP4](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic.mp4) · [Thumb](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic_thumbnail.jpg) · [Grid](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic_review_grid.jpg)) | `36.99 MB` · `63.533s` · `1080×1920@30fps` · `thumb 235 KB` | **`ok: true` (`0` errors, `0` warnings)** | `48.9 / 40.0 / 0.603 / +10.8` | `53.4` / **`90.6` (`all_passed: true`)** (`temporal_motion 55.6`, `44.4%` static, `color_balance 57.0`, audio `95.9`) | Original `Ravin docx`-inspired story-vector film: articulated `~600–740px` anatomy rigs (winged crowns, lashed blinking eyes, curled palm/thumb hands, pleated silk dhotis/lehengas), wainscoting dado halls & perspective planks, clock smear -> whip-pan globe -> spotlight 4-branch `× 27` tree -> unfurling Mt. Meru scroll map -> lateral column truck-pan -> seated Brahma & `27`-sector Magnifying Glass -> Relativity/Siddhanta schematic & 2-Clock Race -> Dwapara `"?"` bubbles & sky-blue Balarama glowing hand-clasp wedding -> Cosmic Lotus finale |

*Ready for final user selection between Candidate A (`candidate_a_dawn_ridge`) and Candidate B (`candidate_b_ref1_cinematic`) (or specific refinements) before designing and implementing the production architecture.*

