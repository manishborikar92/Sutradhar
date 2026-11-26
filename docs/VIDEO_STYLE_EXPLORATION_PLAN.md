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

## 7. Reference-Driven Exploration, Candidate Review & Refinement Log

### Cleanup & Status Decisions

- **Retained Provisional Benchmark (Unchanged):** [`V1 — Dawn Ridge`](file:///C:/Users/manis/Projects/Sutradhar/playground/v1_dawn_ridge_benchmark/v1_dawn_ridge.mp4) (`107.58 MB`, `63.503s`, `1080×1920@30fps`) remains preserved intact inside `playground/v1_dawn_ridge_benchmark/`.
- **Rejected Directions (Removed from Active Development):** `V2` (Paper-Cut Diorama), `V3` (WebGL 3D), Reference 2 (`XPWJGGvpA28`), Reference 3 (`UWjpa9rpkwk`), Round-2 drafts `exp_ref1..3`, and **Candidate A — Refined Dawn Ridge** (`candidate_a_dawn_ridge/`, `build_candidate_a.py`, `mix_candidate_a.wav`, `two_candidate_comparison.json` deleted cleanly while keeping shared assets intact).
- **Retained Under Active Refinement (`Candidate B`):** Reference-1 (`inbAAQMK8vs`) inspired story-vector short in [`playground/candidate_b_ref1_cinematic/`](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic.mp4) (neither V1 nor Candidate B is final yet — awaiting final selection after comparing updated Candidate B against V1).

### Clean Experimental Workspace (`playground/`)

All exploration materials live exclusively inside `playground/` (leaving every production file untouched):

- `playground/references/` — Reference 1 (`ref1_inbAAQMK8vs`) study video & metadata JSON (zero Ref-1 copyrighted assets reused)
- `playground/analysis/` — `ref1_analysis.md`, `ep3_script_timeline.txt`, `candidates_shot_plan.md`, `v1_timeline_sheet.jpg`, `tool_research.md`, `hf_catalog.json`
- `playground/shared/` — Cached Episode 3 narration-derived master audio (`master_mix_poc.wav`, custom `mix_candidate_b.wav` with **0** ElevenLabs credits spent), aligned Hindi captions (`captions_data.js`), local SIL OFL fonts, local GSAP
- `playground/v1_dawn_ridge_benchmark/` — Preserved untouched original V1 benchmark MP4, English thumbnail, grid, and report
- `playground/scripts/` — Shared shell generator (`poc_shared_composer.py`), audio mixer (`mix_candidate_audio.py`), check/preview/render runner (`poc_runner.py`), `build_candidate_b.py`
- `playground/candidate_b_ref1_cinematic/` — Corrected **Candidate B** MP4, English thumbnail, 15-frame preview & MP4 contact sheets, quality report, and sources

---

## 8. Candidate B Audit, Root Causes & Corrections Applied

After inspecting the previous rendered Candidate B MP4 and acting on user review, the following root causes and architectural defects were identified and fixed:

1. **Removed Top Progress Bar & All Top-Center Overlays:**
   - **Root Cause:** `poc_shared_composer.build_poc_shell()` unconditionally generated `#editorial`, `compositions/editorial.html`, `#progress-bar` / `#progress-fill` CSS, DOM nodes, GSAP progress tweens, and `#top-s1` motion assertions.
   - **Fix:** Updated [`poc_shared_composer.py`](file:///C:/Users/manis/Projects/Sutradhar/playground/scripts/poc_shared_composer.py) with `include_editorial=False, include_progress=False` and updated [`build_candidate_b.py`](file:///C:/Users/manis/Projects/Sutradhar/playground/scripts/build_candidate_b.py) with `anchors=[]`. Verified zero `<div id="editorial">`, zero `<div id="progress-bar">`, zero top CSS rules, and no `editorial.html` inside `src/`. Synchronized Hindi kinetic captions remain clean at bottom-center (`top: 1274px`, `data-layout-allow-safe-zone="true"`).
2. **Fixed Wall-vs-Floor Geometry Disconnection & Character Grounding (`HORIZON_Y = 1142`):**
   - **Root Cause:** `drawPalaceInterior()` previously placed the floor edge down at `Y = 1345` while characters stood at `Y = 1225..1270`, causing standing heroes to float `75–120px` up on the rear wall wainscoting. Characters also lacked drawn feet below garment hems, seated shadows offset negatively, `S3A` Gandharvas hovered without a stage, `S3B` hourglass hovered without a table, and `S4` Brahma hovered without a throne podium.
   - **Fix:** Unified palace wall baseboard at `HORIZON_Y = 1142` (gleaming gold trim + foreshortened 1-point perspective planks & trapezoidal carpets spanning `Y = 1142..1920`). Standing characters stand squarely on the floor plane (`Y = 1226..1230`) with sculpted sandaled feet, golden ankle cuffs (*nupura*), and two-layer cast shadows at `(0, 0)`. Built a stepped carpeted Royal Music Dais in `S3A` with seated *Padmasana* Gandharvas flush atop silk cushions (`seatY = 1112`), grounded the `S3B` hourglass on a turned temple pedestal table (`Y = 1228`) and expanded wainscoting pan range (`-450..W+1050`), placed `S4` Brahma's pink lotus atop a stepped golden throne podium sliding coherently with Brahma during `4B`, framed `S6B` mandap columns on floor plinths + grounded *Agni* kalash urn, and mounted `S1A`/`S7` clocks on stone console arches fading cleanly in `S7`.
3. **Character Anatomy, Hairlines & Prop Articulation:**
   - Replaced flat semicircle hairline across forehead (which left a dark bar over Brahma/Balarama) with a high-arched parted curve clear of brows/tilak; integrated Gandharva lap Sitar directly inside character rig coordinates (`-86..-112` below pearl collar); anchored Balarama's *Halayudha* shaft neatly in his outer grip; softened wedding hand-clasp aura behind visible joined palms.

---

## 9. Production Codebase Immutability Boundary

Until final style selection (`V1` vs `Candidate B`) and explicit implementation plan approval, all production pipeline code, templates, assets, and configs remain untouched:
`scripts/`, `templates/`, `assets/`, `tests/`, `config.yaml`, `requirements.txt`, `package.json`, `package-lock.json`, `docs/INSTRUCTIONS.md`, `docs/schema.sql`, `docs/SETUP_AND_OPERATIONS.md`, `README.md`, and `.venv/`. (`episodes.db`, `build/publish_result.json`, and `build/publish_verification.json` were synced specifically for the authorized Candidate B Episode 3 YouTube replacement documented below.)

---

## 10. Current Comparison Summary (`V1 Benchmark` vs Corrected `Candidate B`)

| Direction | Render Specs & Sizes | HyperFrames Strict Check | Look Telemetry (`luma / contrast / sat / bw / warmth`) | KinoCut Scores (`default` / `ui-capture-dark` / `static_frac`) | Visual Status |
| --- | --- | --- | --- | --- | --- |
| **Original `V1 — Dawn Ridge` (Benchmark)** ([MP4](file:///C:/Users/manis/Projects/Sutradhar/playground/v1_dawn_ridge_benchmark/v1_dawn_ridge.mp4)) | `107.58 MB` · `63.503s` · `1080×1920@30fps` | `ok: true` (`0` errors, `0` warnings) | `68.7 / 39.9 / 0.436 / 0% / —` | `57.0` / `88.8` / `3.7%` static | Untouched benchmark |
| **Corrected `Candidate B — Ref-1 Cinema`** ([MP4](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic.mp4) · [Thumb](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic_thumbnail.jpg) · [Grid](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic_review_grid.jpg) · [QA JSON](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic_quality_report.json)) | `36,921,509 B` · `63.533s` · `1080×1920@30fps` · `thumb 240,599 B` | **`ok: true` (`0` errors, `0` warnings)** | `46.5 / 41.1 / 0.604 / 0% / +13.4` | `52.7` / `89.4` (`temporal_motion 52.8`, `47.2%` static, audio `95.9`) | Clean top stage (zero top text/progress bar), grounded feet/seats/pedestals across all scenes |

---

## 11. Episode 3 YouTube Replacement & Record Sync (2026-11-26 UTC)

Corrected `Candidate B` replaced the earlier Episode 3 YouTube upload on `Sutradhar Chronicles` (`UCfuoX2JogzVfq-UJnt1DQLw`, Series 3 playlist `PLfT89QTc7oLs`):

- **New Public Replacement Video:** `oBcyiPy26rg` ([Watch](https://youtu.be/oBcyiPy26rg) · [Shorts](https://www.youtube.com/shorts/oBcyiPy26rg)), uploaded & published `2026-11-26T16:46:07Z`, verified `2026-11-26T16:49:10Z` (`uploadStatus=processed`, `processingStatus=succeeded`, `privacyStatus=public`, `definition=hd`, `duration=PT1M4S`, `defaultLanguage=en`, `defaultAudioLanguage=hi`, custom English thumbnail `maxresdefault.jpg` HTTP `200`, added to `PLfT89QTc7oLs`, all `26/26` live checks passed).
- **Previous Inferior Upload Permanently Deleted:** `Y63AyoTo-Jo` (*"जब ब्रह्मलोक के १ क्षण में पृथ्वी के करोड़ों साल बीत गए #Shorts"*), playlist item removed and video permanently deleted via YouTube Data API v3 at `2026-11-26T16:49:31Z`; independently verified inaccessible (`api_items_remaining=0`, `still_in_playlist=false`, `still_in_channel_uploads=false`, `oembed_http_status=404`).
- **Database, Audit & Local Assets Synced:**
  - Pre-mutation SQLite backup: [episodes_db_pre_ep3_replace_20261126T165040Z.sqlite](file:///C:/Users/manis/Projects/Sutradhar/playground/backups/episodes_db_pre_ep3_replace_20261126T165040Z.sqlite)
  - Updated `episodes` row `episode_id=3` + appended `publishing_history` audit entries (`INITIAL_UPLOAD_REPLACED`/`PERMANENTLY_DELETED` for `Y63AyoTo-Jo` and `REPLACEMENT_PUBLISHED`/`PUBLISHED` for `oBcyiPy26rg`) at `2026-11-26T16:50:40Z`; `PRAGMA integrity_check == "ok"` and `scripts/db_manager.py --context` verified.
  - Updated [publish_result.json](file:///C:/Users/manis/Projects/Sutradhar/build/publish_result.json), [publish_verification.json](file:///C:/Users/manis/Projects/Sutradhar/build/publish_verification.json), and [candidate_b_publish_report.json](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_publish_report.json).
  - Preserved local reference collections intact: Original `V1 — Dawn Ridge` (`playground/v1_dawn_ridge_benchmark/`), Reference 1 (`playground/references/ref1_inbAAQMK8vs.mp4` + `playground/analysis/`), and Corrected `Candidate B` (`playground/candidate_b_ref1_cinematic/`).

