# Sutradhar Video Style Exploration & Redesign Context

> **Status:** Style Exploration Finalized (Tri-Milestone Synthesis & User Decisions Locked) -> Superseded for System Architecture & Implementation by [VIDEO_PRODUCTION_REDESIGN_PLAN.md](file:///C:/Users/manis/Projects/Sutradhar/docs/VIDEO_PRODUCTION_REDESIGN_PLAN.md)
> **Rule of Thumb (Planning Phase):** Keep this document preserved as the chronological visual exploration, Episode 3 replacement, and Episode 4 evaluation record. Do **NOT** modify production code, assets, config, DB schema, or live YouTube metadata until explicit Phase 1 implementation approval.

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
- **Observed Episode 1–4 script lengths (`episodes.db` & `ep4`):** Episodes 1–3 (`1,018`, `805`, and `917` raw Devanagari characters; `~860–1,075` billed chars incl. inline tags), plus Episode 4 (`776` total billed characters incl. tags for a full `61.97s` animated Short — proving the `<= 850` billed-char budget empirically).
- **30-Short Monthly Projection:**
  - At `~950–1,050` billed chars/Short and zero retries (`1.0×`), consumption is **`28,500–31,500` credits/month** — sitting right on or slightly above the `30,000` base renewal.
  - A modest `15%` regeneration/retry rate pushes usage to **`~32,800–36,200` credits/month**, exhausting the monthly base allowance.
- **Required Zero-Spend Mitigations (Locked in Redesign Plan):**
  1. Strict pre-TTS Hindi script budget (`760–840` target, `<= 900` billed chars hard cap incl. tags -> `~24,450` credits/month for 30 Shorts, leaving `~18.5%` buffer).
  2. Strict pre-flight Devanagari + tag syntax validation before calling the ElevenLabs API.
  3. Zero automatic blind TTS retry loops; immutable per-scene SHA-256 WAV/manifest caching.
  4. Zero paid TTS calls during visual experimentation/POC iterations (reuse cached Episode 3 narration `build/audio/narration_full.wav`).

---

## 4. Established Language & Metadata Policy

| Surface | Required Language | Notes |
| --- | --- | --- |
| **Voiceover / Narration** | Hindi (Devanagari source text) | Viraj (`eleven_v4`) |
| **Burned-In Kinetic Captions** | Hindi (Devanagari) | Centered bottom-center inside Shorts safe zone (`y <= 1395px`), accurately word/phrase-synced |
| **Contextual On-Screen Text** | Minimal Hindi / English where genuinely helpful | **Disabled by default** (`0` permanent progress bars or episode counters); opt-in DOM-validated overlays only inside safe zones when narrative clarity requires it |
| **Thumbnail Text** | English | Dedicated high-contrast `1080×1920` (`2:3` safe) thumbnail composition, NOT a raw video frame grab |
| **YouTube Metadata (Title, Description, Tags, Playlists)** | English | `defaultAudioLanguage: hi`, `defaultLanguage: en` |

> **Note:** Several existing legacy files conflict on captioning and metadata language (`docs/INSTRUCTIONS.md` line 24 vs line 35 vs line 165, `README.md`, `db_manager.py`, legacy `publish_youtube.py`). Episodes 3 & 4 applied the English metadata + Hindi audio policy directly; resolving remaining repo conflicts and legacy playlists happens in Phases 1–5 per `VIDEO_PRODUCTION_REDESIGN_PLAN.md`.

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
| **V1 — Dawn Ridge** | Painterly atmospheric 2.5D layered SVG/Canvas cosmic + mythological landscapes with cleaned top-center text & bottom-center Hindi kinetic captions | **PROVISIONALLY APPROVED (Benchmark Only — NOT Final Choice)** | `v1_dawn_ridge.mp4` (`112.81 MB` / `107.58 MiB`, `63.503s`, `1080×1920`, `30fps`, `-14.0 LUFS`). HyperFrames Strict Check **7/7 `ok: true` (`0` errors, `0` warnings)**. KinoCut default `57.0` (`y_avg=73.8`, `contrast=32.8`, `sat=8.9%`, `temporal_motion=96.3` / `3.68%` static); KinoCut dark `88.8`. Preserved in `playground/v1_dawn_ridge_benchmark/` until Phase 7 acceptance. |
| **V2 — Illuminated Paper-Cut Diorama** | Multi-layer parchment & paper-cut craft diorama | **COMPLETELY REJECTED** | Rejected by user. Do not pursue or reuse this visual direction. |
| **V3 — WebGL 3D Cosmic Cinema** | WebGL / Three.js 3D volumetric cosmic scene | **COMPLETELY REJECTED** | Rejected by user. Do not pursue or reuse this visual direction. |

> **Important:** `V1 — Dawn Ridge` is our minimum **quality baseline and comparison benchmark**, NOT our final selected visual direction.

---

## 7. Reference-Driven Exploration, Candidate Review & Refinement Log

### Cleanup & Status Decisions

- **Retained Provisional Benchmark (Unchanged):** [`V1 — Dawn Ridge`](file:///C:/Users/manis/Projects/Sutradhar/playground/v1_dawn_ridge_benchmark/v1_dawn_ridge.mp4) (`112.81 MB` / `107.58 MiB`, `63.503s`, `1080×1920@30fps`) remains preserved intact inside `playground/v1_dawn_ridge_benchmark/`.
- **Rejected Directions (Removed from Active Development):** `V2` (Paper-Cut Diorama), `V3` (WebGL 3D), Reference 2 (`XPWJGGvpA28`), Reference 3 (`UWjpa9rpkwk`), Round-2 drafts `exp_ref1..3`, and **Candidate A — Refined Dawn Ridge** (`candidate_a_dawn_ridge/`, `build_candidate_a.py`, `mix_candidate_a.wav`, `two_candidate_comparison.json` deleted cleanly while keeping shared assets intact).
- **Round 2 Outcome -> Superseded by Tri-Milestone Synthesis:** [`Candidate B — Ref-1 Cinema`](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic.mp4) (`36.92 MB`) progressed from Round-2 refinement into Episode 3's live replacement (Section 11), which then evolved into Episode 4 (Section 12) and the unified production standard locked in Section 13.

### Clean Experimental Workspace (`playground/`)

Exploration artifacts, pre-redesign DB snapshots, and benchmark renders live inside `playground/` (subject to Phase 1 `.gitignore` isolation and duplicate/cache pruning, keeping core production `scripts/engine/`, `templates/`, `assets/`, `tests/`, `docs/` untouched until Phase 1 starts):

- `playground/references/` — Reference 1 (`ref1_inbAAQMK8vs`) study video & metadata JSON (zero Ref-1 copyrighted assets reused)
- `playground/analysis/` — `ref1_analysis.md`, `ep3_script_timeline.txt`, `candidates_shot_plan.md`, `v1_timeline_sheet.jpg`, `tool_research.md`, `hf_catalog.json` (plus raw frame extraction scratch slated for Phase 1 cleanup)
- `playground/shared/` — Cached Episode 3 master audio, aligned Hindi captions (`captions_data.js`), local SIL OFL fonts (`31` `.woff2` files), local GSAP
- `playground/backups/` — Pre-Ep3-replacement SQLite backup (`episodes_db_pre_ep3_replace_20261126T165040Z.sqlite`)
- `playground/v1_dawn_ridge_benchmark/` — Untouched original V1 benchmark MP4 (`112.81 MB`), English thumbnail, grid, and report
- `playground/scripts/` — Shared shell generator (`poc_shared_composer.py`), audio mixer (`mix_candidate_audio.py`), check/preview/render runner (`poc_runner.py`), `build_candidate_b.py`, `replace_ep3_youtube.py`
- `playground/candidate_b_ref1_cinematic/` — Corrected **Candidate B** MP4 (`36.92 MB`, Ep 3 `oBcyiPy26rg` source), English thumbnail (`240,181 B`), `verified_live_sardefault.jpg`, contact sheets, and quality/publish reports
- `playground/ep4_neelakantha_shiva/` — Latest **Episode 4** MP4 (`553.76 MB`, `7PWFV7lQG6U` source), scripts (`build_ep4_*.py`, `mix_ep4_audio.py`, `run_ep4.py`, `publish_ep4.py`), thumbnail + `2:3` crop, contact sheets, audio, and quality/publish reports

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

Throughout visual exploration, Episode 3 replacement, Episode 4 playground prototyping, and architecture re-planning, core production modules, templates, legacy vector assets, tests, configs, and manuals remain untouched:
`scripts/` (except extracted shared [`thumbnail_utils.py`](file:///C:/Users/manis/Projects/Sutradhar/scripts/thumbnail_utils.py) and `sardefault.jpg` CDN hardening in [`publish_youtube.py`](file:///C:/Users/manis/Projects/Sutradhar/scripts/publish_youtube.py) authorized during Episode 3 thumbnail remediation), `templates/`, `assets/`, `tests/`, `config.yaml`, `requirements.txt`, `package.json`, `package-lock.json`, `docs/INSTRUCTIONS.md`, `docs/schema.sql`, `docs/SETUP_AND_OPERATIONS.md`, `README.md`, and `.venv/`. (`episodes.db`, `build/publish_result.json`, and `build/publish_verification.json` record live YouTube state for published Episodes 1–4.) No code edits, asset deletions, DB migrations, or YouTube updates will execute until your explicit authorization to start Phase 1.

---

## 10. Visual Milestone Comparison Summary (`Original V1` vs `Corrected Candidate B` vs `Episode 4`)

| Direction / Milestone | Render Specs & File Size | HyperFrames Strict Check | Look Telemetry (`luma / contrast / sat / bw / warmth`) | KinoCut Scores (`default` / `ui-capture-dark` / `static_frac`) | Key Strengths & Known Gaps |
| --- | --- | --- | --- | --- | --- |
| **Original `V1 — Dawn Ridge` (Benchmark)** ([MP4](file:///C:/Users/manis/Projects/Sutradhar/playground/v1_dawn_ridge_benchmark/v1_dawn_ridge.mp4)) | `112.81 MB` (`107.58 MiB`) · `63.503s` · `1080×1920@30fps` | `ok: true` (`0` errors, `0` warnings) | `68.7 / 39.9 / 0.436 / 0% / —` | `57.0` / `88.8` / `3.68%` static (`color_balance 48.0 FAIL`) | Untouched atmospheric benchmark: sunrise sky progression, 5-plane fog ridges, god-rays, feathered clouds, bird flocks, grain motion |
| **Corrected `Candidate B — Ref-1 Cinema` (Ep 3 `oBcyiPy26rg`)** ([MP4](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic.mp4) · [Thumb](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic_thumbnail.jpg) · [Grid](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic_review_grid.jpg) · [QA JSON](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_ref1_cinematic_quality_report.json)) | `36,921,509 B` (`36.92 MB`) · `63.533s` · `1080×1920@30fps` · `thumb 240,181 B` | **`ok: true` (`0` errors, `0` warnings)** | `46.5 / 41.1 / 0.604 / 0% / +13.4` | `52.7` / `89.4` (`temporal_motion 52.8`, `47.24%` static, `color_balance 51.0 FAIL`, audio `95.9`) | Clean top stage, grounded `HORIZON_Y=1142` interiors/furniture, progressive info props; high static fraction on explainer holds & stick-tube limbs |
| **Latest `Episode 4 — Neelakantha Shiva` (Ep 4 `7PWFV7lQG6U`)** ([MP4](file:///C:/Users/manis/Projects/Sutradhar/playground/ep4_neelakantha_shiva/ep4_neelakantha_shiva.mp4) · [Thumb](file:///C:/Users/manis/Projects/Sutradhar/playground/ep4_neelakantha_shiva/ep4_thumbnail.jpg) · [Grid](file:///C:/Users/manis/Projects/Sutradhar/playground/ep4_neelakantha_shiva/ep4_review_grid.jpg) · [QA JSON](file:///C:/Users/manis/Projects/Sutradhar/playground/ep4_neelakantha_shiva/ep4_quality_report.json)) | `553,759,709 B` (`553.76 MB`, `71.29 Mbps`) · `61.97s` · `1080×1920@30fps` · `thumb 273,736 B` | **`ok: true` (`0` errors, `0` warnings)** | `54.8 / 43.5 / 0.48 / 0% / -7.2` | **`59.8`** / **`94.0` (`all_passed: true`)** · `temporal_motion 99.5` (**`0.54%` static**) · **`color_balance 73.6 PASS` (`cast: null`)** · audio `96.2` | Major leap in anatomy (`traceCapsule`, `drawSculptedHand`, 2.5D head `turn`), action choreography, & Kailash V1 dawn fusion; defects identified below must be fixed in production architecture |

---

## 11. Episode 3 YouTube Replacement & Record Sync (2026-11-26 UTC)

Corrected `Candidate B` replaced the earlier Episode 3 YouTube upload on `Sutradhar Chronicles` (`UCfuoX2JogzVfq-UJnt1DQLw`, Series 3 playlist `PLfT89QTc7oLs`):

- **New Public Replacement Video:** `oBcyiPy26rg` ([Watch](https://youtu.be/oBcyiPy26rg) · [Shorts](https://www.youtube.com/shorts/oBcyiPy26rg)), uploaded & published `2026-11-26T16:46:07Z`, verified `2026-11-26T16:49:10Z` (`uploadStatus=processed`, `processingStatus=succeeded`, `privacyStatus=public`, `definition=hd`, `duration=PT1M4S`, `defaultLanguage=en`, `defaultAudioLanguage=hi`, custom English thumbnail `maxresdefault.jpg` HTTP `200`, added to `PLfT89QTc7oLs`, all `26/26` live checks passed).
- **Previous Inferior Upload Permanently Deleted:** `Y63AyoTo-Jo` (*"जब ब्रह्मलोक के १ क्षण में पृथ्वी के करोड़ों साल बीत गए #Shorts"*), playlist item removed and video permanently deleted via YouTube Data API v3 at `2026-11-26T16:49:31Z`; independently verified inaccessible (`api_items_remaining=0`, `still_in_playlist=false`, `still_in_channel_uploads=false`, `oembed_http_status=404`).
- **Database, Audit & Local Assets Synced:**
  - Pre-mutation SQLite backup: [episodes_db_pre_ep3_replace_20261126T165040Z.sqlite](file:///C:/Users/manis/Projects/Sutradhar/playground/backups/episodes_db_pre_ep3_replace_20261126T165040Z.sqlite)
  - Updated `episodes` row `episode_id=3` + appended `publishing_history` audit entries (`INITIAL_UPLOAD_REPLACED`/`PERMANENTLY_DELETED` for `Y63AyoTo-Jo` and `REPLACEMENT_PUBLISHED`/`PUBLISHED` for `oBcyiPy26rg`) at `2026-11-26T16:50:40Z`; `PRAGMA integrity_check == "ok"` and `scripts/db_manager.py --context` verified.
  - Updated [publish_result.json](file:///C:/Users/manis/Projects/Sutradhar/build/publish_result.json), [publish_verification.json](file:///C:/Users/manis/Projects/Sutradhar/build/publish_verification.json), and [candidate_b_publish_report.json](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/candidate_b_publish_report.json).
- **Thumbnail Root-Cause Fix & Live CDN Verification (Ep 3 `oBcyiPy26rg`):**
  - *Root cause:* Calling YouTube Data API v3 `thumbnails.set` immediately after `videos.insert` (while `processingStatus == "processing"`) returned HTTP `200` and `hasCustomThumbnail=true` on legacy `16:9`/`4:3` slots (`maxresdefault.jpg` / `hqdefault.jpg` blurred/pillarboxed), **but caused YouTube to drop `shortsAspectRatio` (`sardefault.jpg`, `1080×1920`)**, leaving Shorts grids (`@SutradharChronicles/shorts`, Search Shorts shelf, Playlist card) showing auto-captured `oar2.jpg` / `hq2.jpg` frames.
  - *Fixes applied:* Extracted shared validator & CDN verifier ([thumbnail_utils.py](file:///C:/Users/manis/Projects/Sutradhar/scripts/thumbnail_utils.py)), enforced `processingStatus == "succeeded"` gating + live `sardefault.jpg` CDN pixel-similarity verification in [publish_youtube.py](file:///C:/Users/manis/Projects/Sutradhar/scripts/publish_youtube.py) and [replace_ep3_youtube.py](file:///C:/Users/manis/Projects/Sutradhar/playground/scripts/replace_ep3_youtube.py), tightened `2:3` Shorts card safe-zone padding in [build_candidate_b.py](file:///C:/Users/manis/Projects/Sutradhar/playground/scripts/build_candidate_b.py) (`top: 255px`, `bottom: 208px`), re-uploaded the refined thumbnail (`240,181 B`) to `oBcyiPy26rg` only (MP4 untouched), and verified `https://i.ytimg.com/vi/oBcyiPy26rg/sardefault.jpg` (`1080×1920`, `184,955 B`, `MAE=0.24`, `dhash_distance=0`) plus [verified_live_sardefault.jpg](file:///C:/Users/manis/Projects/Sutradhar/playground/candidate_b_ref1_cinematic/verified_live_sardefault.jpg).
- **Preserved local reference collections intact:** Original `V1 — Dawn Ridge` (`playground/v1_dawn_ridge_benchmark/`), Reference 1 (`playground/references/ref1_inbAAQMK8vs.mp4` + `playground/analysis/`), and Corrected `Candidate B` (`playground/candidate_b_ref1_cinematic/`).

---

## 12. Episode 4 (`ep4_neelakantha_shiva` / `7PWFV7lQG6U`) Evolution & Critical Findings

Episode 4 (*"Why Lord Shiva Drank Poison Before the Gods Got Nectar #Shorts"*, [`7PWFV7lQG6U`](https://www.youtube.com/shorts/7PWFV7lQG6U), published `2026-11-27T07:34:17Z`, standalone in `episodes` row 4) validated the fusion of Candidate B's storytelling staging with V1's atmospheric landscape engine while advancing character anatomy, motion density, and audio differentiation:

- **Major Visual & Audio Advances Verified in Episode 4:**
  1. **Anatomical Character Rig Upgrade ([build_ep4_visuals.py](file:///C:/Users/manis/Projects/Sutradhar/playground/ep4_neelakantha_shiva/build_ep4_visuals.py) `SHARED_ILLUSTRATOR_JS`):** Upgraded Candidate B's thick round-line arms into tapered `traceCapsule` layered limb fills + gradient shading, 5-finger `drawSculptedHand` poses (`"cup"`, `"namaskar"`, `"grip"`, `"relax"`), sculpted jawline/cheekbones, and **`drawMythFace` 2.5D head `turn` (`-0.35..+0.35`)** parallax (`earVis`, `irisOff`, shifted nose/mouth).
  2. **True Multi-Plane Action & V1 Dawn Synthesis:** Choreographed active 4-character *Samudra Manthan* Vasuki rope-pulling + *Kurma* + swirling *Halahala* eruption waves (`S1`), V1-inspired 3-plane `RIDGES_KAILASH` + twilight-to-golden sunrise + `drawV1Birds` (`S3–S7`), radiant emerald *Halahala* -> sapphire *Neelakantha* throat transformation (`S5–S7`), and focus rack dimming (`S4`). Achieved **`static_fraction = 0.0054` (`0.54%`)**, **KinoCut `ui-capture-dark = 94.0` (`all_passed: true`)**, **`default = 59.8`**, and **`color_balance = 73.6 PASS` (`color_cast: null`)**.
  3. **Audio & CDN Hardening:** Preserved ElevenLabs `[pause]` tags (`apply_pronunciations_preserving_tags`), stayed strictly inside **`776` billed characters** across 7 scenes (`<= 850` target), resampled WAVs via `ffmpeg 16kHz` + RMS speech-burst snapping (rescuing Scene 5 even when Whisper `base` returned `0.0`), mixed **3 genuinely distinct BGM MD5s** (`tense_confrontation` `6de030fe3022`, `dramatic_mythology` `13fd74c89eb4`, `cosmic_mystery` `2ad448da0b96`), and automated `ep4_thumbnail_2x3_crop.jpg` (`y=150..1770`) + live `sardefault.jpg` CDN parity (`MAE = 0.273`, `dhash_distance = 1`, `20/20` checks).
- **Critical Defects & Shortcuts Caught in Episode 4 (Do NOT Carry Into Production):**
  1. **553.76 MB (`71.29 Mbps`) File Size Bloat:** Running `hyperframes render --quality looks` over a full-frame shifting `128×128` film-grain overlay (`world.js` `L2158–2167`, `has_b_frames=0`) bloated file size by **15×** vs Candidate B (`36.92 MB`). Production requires deterministic CRF/bitrate guardrails (`<= 55 MB`) and static/low-frequency grain.
  2. **Thumbnail Mountain Geometry Glitch & Font Weight Fallback:** In [`thumb/index.html`](file:///C:/Users/manis/Projects/Sutradhar/playground/ep4_neelakantha_shiva/thumb/index.html) (`L1272`) calling `drawKailashSacredPeak`, right-side snow gully `[122, -208, 62, 38]` extends horizontally to `x = 184`, overhanging Kailash's right ridge slope (`x = 175` at `y = -195`) and creating a jagged pale fin behind Shiva's crescent moon; `.pill` also requests `Inter font-weight: 900` while only weights `500/700/800` exist in `fonts.css`.
  3. **Canvas-Inlined Pills & Lower-Third Spacing:** S1 (`"FIRST TO EMERGE · HALAHALA"`, `y=354`) and S6 (`"NEELAKANTHA"`, `y=349`) badges were drawn inside `<canvas data-layout-ignore="true">`, bypassing HyperFrames' `--safe-zone shorts` DOM validation, while `.caption-group` (`top: 1256px`, `max-height: 148px` in [`captions.html`](file:///C:/Users/manis/Projects/Sutradhar/playground/ep4_neelakantha_shiva/src/compositions/captions.html)) extends to `y = 1404px` (`4px` past `Y = 1400`) and S1 ocean scenes leave an under-utilized dark navy lower third.
  4. **Inverted Plan-to-Render Pipeline & Dummy SVG Path:** `ep4_episode_plan.json` was generated *post-render* inside `publish_ep4.py --prepare-only` with mismatched speaking speeds (`0.90` vs `0.95/0.88`) and a fictional placeholder path (`assets/svg/backdrops/samudra_manthan_halahala.svg`), and `publish_ep4.py` inserted row 4 into `episodes` directly without logging to `publishing_history`.
  5. **Em-Dash Keyword Bug & `WhisperModel("base")` Drift:** `build_ep4_audio.py` `L412` strips non-word chars without splitting on `—`, turning `"बची—कैलाश"` into `"बचीकैलाश"` and `"कहलाए—नीलकंठ!"` into `"कहलाएनीलकंठ"` (`kw: false` in [`captions_data.js`](file:///C:/Users/manis/Projects/Sutradhar/playground/ep4_neelakantha_shiva/src/captions_data.js)); `L480` still loads `WhisperModel("base")` despite docstring notes, causing Scene 5's `0.0` Whisper match; `mix_ep4_audio.py` retains 3 orphaned UI SFX pops (`S2`, `S7`) and double `loudnorm` passes; `build_ep4_visuals.py` inlines `~2,200` JS lines into a `2,560`-line Python string template with `78` redundant font/lib file copies and unused `691 KB` `three.module.min.js`.

---

## 13. Unified Visual Direction, Locked Scope Decisions & Master Plan Link

- **Selected Visual Standard ("Sutradhar Kinetic Storycraft v2" — Tri-Milestone Synthesis):** Combine **Corrected Candidate B's** architectural wall-floor `HORIZON_Y` grounding, props/infographics, unobstructed stage margins, bottom-center Hindi kinetic captions (`y <= 1395px`), and `2:3`-safe English thumbnails; **Original V1 — Dawn Ridge's** multi-plane sunrise skies, horizon mist, god-rays, and bird/flora atmosphere; and **Episode 4's** upgraded `SHARED_ILLUSTRATOR_JS` anatomical limbs (`traceCapsule`), sculpted hands, `2.5D` head turns, active group choreography, `<= 1%` static motion fluidity, and balanced RGB contrast — while fixing Ep 4's `553.76 MB` encode bloat, Kailash thumbnail snow fin, post-render JSON inversion, caption tokenization bug, and monolithic Python string templates.
- **Locked User Decisions Guiding Execution (Confirmed 2026-11-27):**
  1. **Series 1–3 Playlist English Sync (Phase 1):** Translate Series 1 (`PLH-P2bxD4o-I`) and Series 2 (`PLZpM1QZQbBWw`) playlists alongside Series 3 (`PLfT89QTc7oLs`) on YouTube & in `episodes.db` (`series_title_en/hi`), leaving **Episodes 1–3 videos and Ep 3's `sardefault.jpg` untouched**.
  2. **Episode 4 Thumbnail-Only Polish (Phase 2):** Fix `drawKailashSacredPeak` ridge bounds and `.pill` font weight `800`, regenerate `ep4_thumbnail.jpg`, and perform a **thumbnail-only** `thumbnails.set` + live `sardefault.jpg` re-verification on `7PWFV7lQG6U`, leaving Ep 4's approved MP4 untouched.
  3. **Playground Binary Retention & Clutter Cleanup:** Keep the three milestone MP4s (`v1_dawn_ridge.mp4`, `candidate_b_ref1_cinematic.mp4`, `ep4_neelakantha_shiva.mp4`) in git-ignored `playground/` until Phase 7 acceptance passes, while cleaning duplicate fonts/libs, frame dumps, duplicate WAVs, and scratch extraction folders in Phase 1.
  4. **Episode 1 & 2 Historical Baselines:** Leave Ep 1 (`cd1cc1mhfwg`) and Ep 2 (`hcKmhzjQkz4`) videos and legacy thumbnails untouched, enforcing strict `sardefault.jpg` verification from Episode 3 onward.
- **Next Stage Document:** The revalidated codebase re-architecture, Ep 4 forensic delta, complete folder-by-folder legacy/compatibility/dependency cleanup matrix, schema v4 + Ep 1–4 DB reconciliation, redesigned `docs/INSTRUCTIONS.md` blueprint, ElevenLabs Starter (`30 Shorts/month`) economics, and acyclic 7-phase implementation roadmap live in **[VIDEO_PRODUCTION_REDESIGN_PLAN.md](file:///C:/Users/manis/Projects/Sutradhar/docs/VIDEO_PRODUCTION_REDESIGN_PLAN.md)** (ready for Phase 1 kickoff upon final user approval).


