# IMPLEMENTATION_PLAN.md
## Sutradhar — Autonomous Dual-Language YouTube Shorts Production Pipeline
### (Antigravity `/automation` + Series State Machine + 5-Shot Kathputli Folk-Art Visual Engine + Kokoro-82M Dual-Language + HyperFrames + KinoCut 2.0)

---

### 1. Executive Summary & Architectural Decisions

This specification defines **Sutradhar**, a **100% Antigravity-native, zero-recurring-external-cost daily YouTube Shorts production pipeline** engineered for serialized edutainment, native **YouTube Shorts Series** playlist grouping, and sustainable **YouTube Partner Program (YPP) monetization**.

#### Core Design Principles
1. **Zero External AI APIs ($0.00 External Spend):**
   - **Google Antigravity** acts as the sole intelligence engine—handling pillar rotation, multi-episode series planning, scriptwriting, bespoke SVG rig authoring, and multimodal visual QA inspection. No external LLM, image generation, or cloud TTS API keys are required.
2. **Clean-Canvas Video Format (Strict Removal of Captions & Title/Part Labels):**
   - Every Short is rendered on a clean canvas with **zero on-screen captions or subtitles**, **zero title cards**, and **zero series/part badges**.
   - Spoken narration and layered theatrical staging carry 100% of the narrative, while YouTube automatically generates closed captions for viewers who desire them.
   - The visual focus is preserved entirely for animated folk-art puppetry and multi-plane environments.
3. **Dual-Language Production Core (English `en` & Hindi `hi`):**
   - Sutradhar officially supports both **Global English (`en`)** and **Classical Hindi (`hi`)**, selectable per channel via `channel.primary_language` in `config.yaml`.
   - **English Voice Profile:** British Prestige blend (`bm_fable:0.55 + am_fenrir:0.45` @ 0.91x speed) for narration + `am_onyx` for dialogue.
   - **Hindi Voice Profile:** Classical *Katha* blend (`hf_alpha:0.70 + hf_beta:0.30` @ 0.95x speed) for narration + `hm_omega` for dialogue.
   - **Language-Specific Dictionaries:** `pronunciations_en.yaml` (IPA substitutions for Sanskrit and Indian proper nouns) and `pronunciations_hi.yaml` (Devanagari compound & halant clarity).
4. **Indian Kathputli / Folk-Art 2D Vector Puppetry Engine:**
   - Visuals employ traditional **Indian Kathputli puppet aesthetics** with warm shaded olive/ochre tones, ornate tiered mukut crowns, dhotis, white *janeu*, and gold jewelry.
   - **Hierarchical Rivet Rigging:** Movable limbs use CSS custom-property rotations (`--rot-...`) anchored to `0px 0px` local joint origins. Limbs remain permanently pinned to circular brass rivets across all poses with zero detachment.
   - **5-Shot Narrative Progression:** Each Short follows a dynamic 5-scene cinematic progression (Wide Establishing Curtain Reveal $\to$ Royal Court Advance $\to$ Wrathful Close-Up with Lip-Sync $\to$ Cosmic Summit Strike $\to$ Foreground Granite Crushing).
5. **Connected Context-Window Audio & Dynamic Dialogue DSP:**
   - Synthesizes multi-sentence narrative blocks in connected context windows, eliminating prosody resets and dead-air seams.
   - Applies dynamic sample-rate-preserved dialogue DSP (`asetrate={sr*0.917},aresample={sr},atempo=1.0905`) to character lines, providing deep resonant authority without chipmunk distortion or sample-rate mismatches.
   - 20ms cosine volume ramps on audio segments, two-pass EBU R128 loudness normalization to `-14.0 LUFS` (`-1.5 dBTP`), and zero digital trailing floor (-150.0 dBFS).
6. **Deterministic Composition Synchronizer (`scripts/generate_composition.py`):**
   - Automatically compiles and synchronizes `index.html`, `styles.css`, and `engine.js` from `assets/svg/` and `build/manifest.js`, maintaining 100% HyperFrames 0.9.70 compliance.
7. **Deterministic Thumbnail Generation & Live Verified Publishing:**
   - `scripts/render_and_qa.py` extracts a clean-canvas, high-impact JPEG thumbnail (`build/thumbnail.jpg` $\le 2\text{ MB}$, 1080×1920) from the episode's peak hero shot.
   - `scripts/publish_youtube.py` uploads the video and custom thumbnail via `thumbnails().set()`, handles 403 phone verification gates gracefully, and executes mandatory live API read-back verification (`videos().list` and `playlistItems().list`), recording a structured audit in `build/publish_verification.json`.
8. **7 Static Pre-Whitelisted Commands (Windows `.venv` Explicit — Zero Dynamic CLI Arguments):**
   - All stateful handoffs occur via JSON files inside `build/`, enabling Manual Daily Execution on Pro and optional unattended Antigravity `/automation` runs with 7 static commands.

---

### 2. Verified Technology Stack

| Pipeline Layer | Tool / Dependency | Configuration / Version | License / Tier | Operational Ceiling | External Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Orchestrator & Vision QA** | Google Antigravity IDE (Pro Reasoning Model) + optional `/automation` | Built-in frontier models | Developer Plan | Runs locally via Antigravity Desktop / CLI | **$0 extra** |
| **Agent Skills** | `hyperframes` + `svg-character-animation` | Global: `C:\Users\manis\.agents\skills\` | Apache 2.0 | Global rules & HyperFrames templates | **$0.00** |
| **Local Neural TTS (EN & HI)** | `kokoro-onnx` (Kokoro-82M v1.0) | `kokoro-onnx==0.6.1`, ONNX Runtime | **Apache 2.0** | Unlimited offline CPU synthesis; 0 API keys | **$0.00** |
| **Word Alignment (Audition)** | `faster-whisper` (CTranslate2) | `faster-whisper==1.2.1` (`base`, `int8`) | MIT | Used for voice auditions; video uses `ffprobe` | **$0.00** |
| **2.5D Vector Video Engine** | `hyperframes` (`^0.9.19`) + GSAP | Node.js 24+ + Chromium + FFmpeg | Apache 2.0 | Local `1080x1920` 30fps high-quality renders | **$0.00** |
| **Mastering & Quality Gate** | `kinocut` + FFmpeg 7.1 | `kinocut==2.0.1` (`ui-capture-dark`) | Apache 2.0 / LGPL | `-14.0 LUFS` mastering, release gate ($\ge 80$) | **$0.00** |
| **State Machine & Ledger** | SQLite3 + Python `sqlite3` | `episodes.db` (foreign keys, atomic trans) | Public Domain | Strict series completion & playlist sync | **$0.00** |
| **YouTube Publishing & Sync** | `google-api-python-client` | YouTube Data API v3 | Google Cloud Quota | **10,000 units/day** free quota | **$0.00** |

---

### 3. Repository Structure

```text
Sutradhar/
├── docs/
│   ├── IMPLEMENTATION_PLAN.md          # Authoritative architectural specification & project roadmap
│   ├── MASTER_AUTOMATION_PROMPT.md     # Daily prompt for Manual Execution (Pro) & optional /automation
│   ├── MANUAL_SETUP_AND_OPERATIONS.md  # Operations manual, manual workflow guide & verification records
│   └── schema.sql                      # Reference SQLite schema for episodes.db
├── assets/
│   ├── AUDIO_LIBRARY_MANIFEST.md       # Audio specs, loudness criteria & CC0 search keywords
│   ├── bgm/
│   │   ├── dramatic_mythology.mp3      # Indian ethnic drone & tanpura resonance bed (<620Hz low-pass)
│   │   ├── cosmic_mystery.mp3          # Ambient synth/space drone bed
│   │   └── epic_history.mp3            # Cinematic historical percussion bed
│   ├── sfx/
│   │   ├── whoosh_soft.wav             # Scene-transition stereo whoosh
│   │   ├── sub_hit.wav                 # 55Hz cinematic sub bass drop
│   │   └── tension_swell.wav           # Restrained analog tension swell
│   ├── js/
│   │   └── gsap.min.js                 # GSAP 3.12.5 local runtime
│   └── svg/
│       ├── characters/                 # Hierarchical Kathputli character rigs (viewBox 0 0 800 1200)
│       │   ├── ravana.svg              # 10-headed King Ravana (rivet rig, expressions, lip-sync, janeu)
│       │   ├── shani_dev.svg           # Lord Shani (midnight indigo, dark mukut, piercing gaze, cosmic halo, danda)
│       │   ├── narad_muni.svg          # Devarshi Narada (saffron/ivory robes, jasmine topknot, Mahati Veena)
│       │   ├── hanuman.svg             # Mahavira Hanuman (vermilion athletic build, arched tail, golden Gada)
│       │   ├── ancient_scholar.svg     # Master Polymath (ivory/ochre, palm-leaf manuscript, brass astrolabe)
│       │   └── sutradhar_narrator.svg  # Signature host storyteller Kathputli rig
│       └── backdrops/                  # Theatrical multi-plane environment SVGs (viewBox 0 0 1080 1920)
│           ├── celestial_cosmos_court.svg # Midnight indigo starfield, golden astrolabe arch, stellar dust
│           ├── ancient_nalanda_courtyard.svg # Terracotta sandstone colonnades, carved arches, clay diyas
│           ├── forest_ashram_twilight.svg # Silhouette banyans, aerial roots, glowing havan kund fire
│           ├── ocean_sky_horizon.svg   # Golden-crimson sunset, layered folk waves, misty cliffs
│           ├── golden_lanka_citadel.svg # Full-bleed Lanka spires, twilight sky, courtyard waters
│           ├── lanka_sandstone_throne.svg # Sandstone throne room backdrop
│           ├── mount_kailash.svg       # Sacred summit with cosmic light shafts
│           ├── crushed_atmosphere.svg  # Deep cosmic void with atmospheric pressure
│           ├── granite_underside.svg   # Descending granite mountain underside
│           ├── ancient_temple_ruins.svg # Sandstone carved temple colonnades
│           └── deep_cosmos_nebula.svg  # Deep purple/indigo interstellar nebula
├── models/
│   └── kokoro/
│       ├── kokoro-v1.0.onnx            # Authoritative 325.5MB ONNX model (SHA-256 pinned)
│       └── voices-v1.0.bin             # 28.2MB voices tensor (54 voices, SHA-256 pinned)
├── scripts/
│   ├── db_manager.py                   # Context & state engine (--context | --create-series | --record-published)
│   ├── build_audio.py                  # Dual-language Kokoro synthesis + dialogue DSP + -14.0 LUFS
│   ├── preview_frames.py               # Composition sync + mid-scene snapshots -> qa_grid.jpg
│   ├── render_and_qa.py                # HyperFrames render + FFmpeg ducking + KinoCut gate + thumbnail.jpg
│   ├── publish_youtube.py              # Private review upload + thumbnails.set + API read-back verification
│   └── generate_composition.py         # Deterministic index.html / styles.css / engine.js synchronizer
├── tests/
│   ├── test_audition_voices.py         # Kokoro blend math, RMS dBFS, and immutability tests
│   ├── test_build_audio.py             # Audio pipeline, duration bounds, and model quarantine tests
│   ├── test_db_manager.py              # Database integrity, series lifecycle, and schema tests
│   ├── test_render_pipeline.py         # Preview grids, probe media, and thumbnail generation tests
│   └── test_publish_youtube.py         # Offline stub, mocked upload, thumbnail 403, and read-back tests
├── build/                              # Ephemeral build artifacts (gitignored)
│   ├── audio/                          # Active narration WAVs
│   ├── samples_v2/                     # Verified production sample bundles (EN & HI)
│   │   ├── prod_en_ravana_kailash/     # 42.4s English master (final_short.mp4, contact sheets)
│   │   └── prod_hi_ravana_kailash/     # 44.3s Hindi master (final_short.mp4, contact sheets)
│   ├── youtube_e2e_verification.json   # Live YouTube private_review upload & read-back proof
│   └── final_short.mp4                 # Active render master
├── config.yaml                         # Channel config (language, voice profiles, upload_mode, pillars)
├── pronunciations_en.yaml              # English IPA pronunciation dictionary
├── pronunciations_hi.yaml              # Hindi Devanagari pronunciation dictionary
├── pronunciations.yaml                 # Root fallback pronunciation dictionary
├── episodes.db                         # SQLite series & episode ledger (immutable baseline)
├── package.json                        # Node.js dependencies (hyperframes, gsap)
├── requirements.txt                    # Python dependencies
└── .gitignore                          # Git exclusions (build/, models/, .env.youtube, episodes.db)
```

---

### 4. Series Management, State Machine & Multi-Shot Pacing

#### 4.1 Brand Cohesion & 3-Pillar Rotation
Sutradhar rotates across three thematically connected curiosity pillars:
1. **`Ancient Epics & Lore`** (Sanatan Dharma, Puranic paradoxes, mythic cosmology, forgotten legends)
2. **`Hidden History`** (Ancient Indian & world empires, lost engineering, untold turning points)
3. **`Cosmic & Scientific Paradoxes`** (Astrophysics, quantum mysteries, deep time, reality-bending science)

#### 4.2 Multi-Shot 5-Beat Narrative Pacing (38–44 Seconds)
Each episode is structured for maximum Shorts retention across 5 dynamic shots (~6.5–9.5s each):
- **Shot 1 (Wide Establishing / Vista Hook, 0–8s):** Parting velvet curtains, full-bleed panoramic environment, opening paradox or confrontation.
- **Shot 2 (Character Advance / Tension Escalation):** Character enters with articulated walking gait and hierarchical rivet joints.
- **Shot 3 (Wrathful Close-Up / Dialogue Climax):** Dynamic camera push (2.15x) into character heads, angry facial expression swap (brows/eyes), multi-vowel lip-sync articulation, and rotating folk-art solar burst aura.
- **Shot 4 (Cosmic / Divine Counter-Strike):** Scale shift to a divine summit or cosmic realm with impact shockwaves and screen rumbles.
- **Shot 5 (Crushing Climax / Cliffhanger Payoff):** Physical environmental pressure (e.g. descending granite mountain) directly onto the character's bracing limbs; narrator delivers cliffhanger hook teasing tomorrow's episode.

---

### 5. Hierarchical Puppet Rigging Standard (`ravana.svg`)

All movable character limbs in `assets/svg/characters/` follow a strict kinematic hierarchy:
```text
#ravana_character
├── #lower_body
│   ├── #hip_left_joint ──> #thigh_left_rot ──> #knee_left_joint ──> #shin_left_rot
│   └── #hip_right_joint ──> #thigh_right_rot ──> #knee_right_joint ──> #shin_right_rot
├── #torso_group
│   ├── #torso_artwork (<clipPath id="torso_clip"> locks janeu permanently inside torso)
│   ├── #rear_arms_layer (4 left arms + 4 right arms with weapon props)
│   ├── #front_arms_layer (forearms, wrists, and gesture hands)
│   └── #heads_group
│       ├── #flanking_heads (4 heads left, 4 heads right with fan-out rotation)
│       └── #central_head (brows_neutral/angry, eyes_normal/wrath, mouth_calm/talk/shout)
└── #wrath_sunburst (folk-art solar rays & glowing aura revealed on dialogue climax)
```

**Joint Pin Kinematics:** Joint pins use circular brass rivets (`#puppet_pin`). Rotations are driven entirely by CSS custom properties (`--rot-thigh-left`, `--rot-shin-left`, etc.) defined in `styles.css` with `transform-origin: 0px 0px !important`.

**Folk-Art Palette (Strictly Zero Teal):** Midnight obsidian `#060814`, deep twilight indigo `#1e1828`, sandstone amber `#d97706`, burnished gold `#ffd43b`, and bronze `#b45309`.

---

### 6. Dual-Language Audio Engine & Dynamic Dialogue DSP

#### 6.1 Connected Context-Window Synthesis
Sequential narrator sentences are synthesized within coherent connected context blocks rather than isolated fragments, eliminating sentence-by-sentence prosody resets and dead-air digital seams.

#### 6.2 Dynamic Dialogue DSP Chain
When `speaker_role: "character_dialogue"` is specified:
1. Dynamic pitch lowering: `asetrate={int(sr*0.917)},aresample={sr},atempo=1.0905` shifts pitch downward by 1.5 semitones while precisely maintaining duration and Kokoro's native 24kHz sample rate.
2. Low-shelf chest resonance boost (`+2.5dB @ 150Hz`).
3. Subtle stone-hall reverb echo (`aecho=0.8:0.88:35:0.25`).
4. Automated assertions: $\Delta\text{Duration} \le \pm 5\%$, pitch reduction verified, and trailing 500ms silence floor $< -65.0\text{ dBFS}$.

#### 6.3 Broadcast Mastering Standards
- Two-pass EBU R128 loudness normalization to **-14.0 LUFS** (True Peak $\le -1.5\text{ dBTP}$).
- Dynamic sidechain ducking (`sidechaincompress` threshold -24dB, ratio 4:1) dips BGM beneath narration.
- Digital zero trailing buffer with 20ms cosine volume ramp, yielding **-150.0 dBFS** trailing noise floor.

---

### 7. Deterministic Thumbnail Generation & YouTube Publishing

#### 7.1 Episode Thumbnail (`build/thumbnail.jpg`)
During `render_and_qa.py`, FFmpeg extracts a clean-canvas, high-impact JPEG thumbnail:
- **Source:** Peak dramatic hero moment (midpoint of Shot 3 wrath dialogue).
- **Dimensions:** Exactly `1080x1920` (9:16 vertical cover).
- **File Size:** Verified $\le 2\text{ MB}$ (YouTube custom thumbnail limit).

#### 7.2 YouTube Data API v3 Workflow (`scripts/publish_youtube.py`)
1. **Video Upload:** `videos().insert(part="snippet,status", ...)` setting title, description, category 27 (Education), default languages, `privacyStatus: "private"`, `selfDeclaredMadeForKids: False`, and `containsSyntheticMedia: True`.
2. **Thumbnail Upload:** `thumbnails().set(videoId=video_id, media_body=...)`. Catches HTTP 403 (e.g. channel phone verification / Intermediate Features pending) gracefully, logging a clear diagnostic without failing the upload or losing the video ID.
3. **Playlist Assignment:** Reuses active series playlist or creates a private series playlist via `playlists().insert` and appends the video via `playlistItems().insert`.
4. **Mandatory Live API Read-Back Verification:** Immediately executes `videos().list` and `playlistItems().list` to verify YouTube-stored values against expected metadata, recording a complete audit in `build/publish_verification.json`.

#### 7.3 Daily Quota Accounting
| API Method | Quota Cost per Call | Calls per Short | Total Daily Quota |
| :--- | :--- | :--- | :--- |
| `videos.insert` | 1,600 units | 1 | 1,600 units |
| `thumbnails.set` | 50 units | 1 | 50 units |
| `playlists.insert` | 50 units | 0–1 (Part 1 only) | 0–50 units |
| `playlistItems.insert` | 50 units | 1 | 50 units |
| `videos.list` (read-back) | 1 unit | 1 | 1 unit |
| `playlistItems.list` (read-back) | 1 unit | 1 | 1 unit |
| **Total Daily Usage** | — | — | **1,702 units / 10,000 units** (17% of free tier) |

---

### 8. Phase 1–5 Project Roadmap & Acceptance Criteria

```mermaid
flowchart LR
    P1["Phase 1: Pipeline & Model Fixes<br/>(COMPLETED)"] --> P2["Phase 2: Core V2 Migration<br/>(COMPLETED)"]
    P2 --> P3["Phase 3: Cleanup, Live Verification & Ops Docs<br/>(COMPLETED)"]
    P3 --> P4A["Phase 4A: Multi-Shot Engine & Cast Expansion<br/>(COMPLETED)"]
    P4A --> P4B["Phase 4B: Multi-Series Production Prep<br/>(NEXT)"]
    P4B --> P5["Phase 5: Production Calibration & Unlock<br/>(FINAL)"]
```

#### Phase 1 — Environment & Audio Pipeline Fixes: COMPLETED
- Downloaded authoritative 325.5MB Kokoro ONNX model (SHA-256: `7d5df8ec...`) and voices tensor.
- Quarantined corrupt model file.
- HyperFrames 0.9.70 audio duration sync (`+0.30s`).
- 35/35 automated tests passed.

#### Phase 2 — Production Core V2 Migration: COMPLETED
- Promoted V2.2 multi-shot Kathputli visual engine and Stage 1.5 dual-language audio engine into root production codebase.
- Verified two full-length 38–44s production Shorts in `build/samples_v2/`:
  - `prod_en_ravana_kailash` (42.4s, KinoCut **83.2 / 100**, PASS)
  - `prod_hi_ravana_kailash` (44.3s, KinoCut **82.4 / 100**, PASS)
- Root `episodes.db` confirmed bit-for-bit unchanged (SHA-256: `729ACCE0CD4F31CC69CECA61470D331ABCBCE5E62B51728AB372CD28F83F8011`).

#### Phase 3 — Operational Readiness, Codebase Cleanup, Live Verification & Operations Docs: COMPLETED
- **Stage 3A (Cleanup):** Audited and removed obsolete scratch files, old benchmark directories, and quarantined model files. Verified zero broken references. Full test suite: **37/37 PASSED**.
- **Stage 3B (Thumbnail & Live YouTube Verification):** Added `build/thumbnail.jpg` generation ($\le 2\text{ MB}$, 1080×1920) in `render_and_qa.py`. Upgraded `publish_youtube.py` with `thumbnails.set`, 403 handling, and mandatory API read-back verification. Successfully executed a real live `private_review` upload in an isolated workspace:
  - Video ID: `vdkMMm5ucPQ` (`https://youtu.be/vdkMMm5ucPQ`)
  - Playlist ID: `PLV5anx_T8pUw`
  - Privacy Status: `private`
  - Read-back verification: **PASSED** (all fields verified against YouTube Data API).
  - Recorded in `build/youtube_e2e_verification.json`.
- **Stage 3C (Documentation):** Complete rewrite of `IMPLEMENTATION_PLAN.md`, `MASTER_AUTOMATION_PROMPT.md`, and `MANUAL_SETUP_AND_OPERATIONS.md`. Retired obsolete interim docs.
- **Stage 3D (Operational Workflow Selection & Automation Documentation):** Established **Manual Daily Execution** on Antigravity's highest-capability / Pro reasoning model as Sutradhar's recommended primary daily workflow. Documented Antigravity App `/automation` as an optional future upgrade with verified local sidecar, machine-awake, Pro model, and Windows Terminal Sandbox permission requirements.

#### Phase 4A — Generalized Multi-Shot Engine, Kathputli Cast Expansion & Real Audio Hardening: COMPLETED
- **Generalized Multi-Shot Engine (`scripts/generate_composition.py` + `engine.js`):**
  - Removed all hardcoded Phase 2 Ravana/Lanka/Kailash/Granite references.
  - Implemented 100% manifest-driven generator supporting any 5–8 scene sequence across all 3 editorial pillars.
  - Dynamic SVG injection: backdrops, diagrams, and characters resolved from `assets/svg/`.
  - Universal Hierarchical Rivet Joint Controls in `styles.css`: stable `0px 0px` joint origins across all limbs and joints, full support for both two-armed and multi-armed puppet rigs.
  - Declarative shot choreography in `engine.js`: 7 shot types (`curtain_establishing`, `character_medium`, `character_closeup_dialogue`, `two_character_confrontation`, `landscape_cutaway`, `bespoke_diagram_reveal`, `dramatic_climax`), 5 standardized puppet poses (`idle_royal`, `action_raised`, `wrath_dialogue`, `blessing_calm`, `humbled_braced`), camera motions, and 0.25–0.35s transitions.
  - Validated with `npx hyperframes lint` (0 errors) and `npx hyperframes check --json` (0 errors, `ok: true`).
- **Kathputli Cast Expansion (`assets/svg/characters/`):**
  - Authored 4 new reusable Kathputli puppet rigs at `800×1200 viewBox`: `shani_dev.svg`, `narad_muni.svg`, `hanuman.svg`, `ancient_scholar.svg`.
  - Built with local joint anchors (`transform-origin: 0px 0px !important`), `<clipPath>` for torso ornaments, and switchable facial states (`#mouth_calm`, `#mouth_talk`, `#mouth_shout`, `#eyes_normal`, `#eyes_wrath`, `#brows_neutral`, `#brows_angry`).
  - Rendered 4-pose contact verification sheets under `build/phase4_qa/<char>_pose_sheet.png` (Idle, Action Raised inside `x: 90..990`, Close-up Dialogue, Alternate/Calm) and visually inspected each PNG.
- **Theatrical Full-Bleed Backdrops (`assets/svg/backdrops/`):**
  - Authored 4 new full-bleed `1080×1920` backdrops: `celestial_cosmos_court.svg`, `ancient_nalanda_courtyard.svg`, `forest_ashram_twilight.svg`, `ocean_sky_horizon.svg`.
  - Structured with 4-plane depth layering (`#bg_sky`, `#bg_far`, `#bg_mid`, `#bg_near`). Strictly zero teal/cyan.
  - Verified automatic discovery via `python scripts/db_manager.py --context`.
- **Audio Pipeline Hardening (`scripts/render_and_qa.py` + `assets/AUDIO_LIBRARY_MANIFEST.md`):**
  - Enforced explicit 24,000 Hz resampling (`aresample=24000:async=1`) across BGM and SFX inputs, eliminating sample-rate drift.
  - Added smooth 1.20s tail fade-out (`afade=t=out:st={duration-1.2}:d=1.2`) on background music.
  - Preserved procedural acoustic drone fallback (`aevalsrc`) when BGM files are absent.
  - Authored `assets/AUDIO_LIBRARY_MANIFEST.md` documenting technical specs, loudness targets (-14.0 LUFS), and CC0 / YouTube Audio Library search keywords.
- **Automated Test Suite:**
  - Expanded test coverage in `tests/test_render_pipeline.py`.
  - Full suite: **39/39 PASSED** (100% pass, 0 failures, 0 skips).
- **End-to-End Cross-Cast Verification Short:**
  - Rendered full isolated 38–44s short (*Shani Dev & Narad Muni: Cosmic Scales of Karma*) in an isolated temporary workspace.
  - Duration: **39.10s** (target sweet spot [36s, 46s]).
  - Resolution: **1080×1920 @ 30fps**.
  - Loudness: **-14.3 LUFS** (target: -14.0 LUFS ± 0.5).
  - KinoCut Score: **85.0 / 100.0** (target: $\ge 80.0$).
  - Clean canvas: **100% verified** (zero captions, zero title/part badges).
  - Archived to `build/samples_v2/phase4_crosscast_verify/` (`final_short.mp4`, `qa_grid.jpg`, `final_qa_grid.jpg`, `thumbnail.jpg`, `manifest.js`, `episode_plan.json`, `verification_report.json`).
- **Database Immutability:**
  - Root `episodes.db` confirmed bit-for-bit unchanged (SHA-256: `729ACCE0CD4F31CC69CECA61470D331ABCBCE5E62B51728AB372CD28F83F8011`).

#### Phase 4B — Automated Multi-Pillar & Real-Audio Swap Readiness: COMPLETED
- **Full-Repository Gemini Reference Audit & Removal (Mandatory Gate):**
  - Completed case-insensitive search across all codebase files, configs, and documentation.
  - Replaced all legacy model strings with clean, model-agnostic Antigravity phrasing (`Antigravity's highest-capability / Pro reasoning model`, `Pro`, `Never call external LLM, TTS, or image APIs`).
  - Verified 0 model references remain across all tracked and workspace files.
- **Script Directory Hygiene & Developer Tooling Separation:**
  - Removed one-off test runner `scripts/run_crosscast_e2e.py`.
  - Formalized strict classification: the 7 static whitelisted production pipeline commands (`scripts/db_manager.py`, `scripts/build_audio.py`, `scripts/generate_composition.py`, `scripts/preview_frames.py`, `scripts/render_and_qa.py`, `scripts/publish_youtube.py`) remain completely decoupled from developer utilities (`scripts/audition_voices.py`, `scripts/generate_pose_sheets.py`).
- **Multi-Pillar Theatrical & Diagram Asset Proof:**
  - Authored bespoke diagram `assets/svg/diagrams/nalanda_scroll_astrolabe.svg` (`viewBox="0 0 900 900"`), implementing an ancient Sanskrit astronomical parchment scroll and brass astrolabe with warm folk-art gold/ochre/obsidian palette, zero teal, and kinetic path classes (`#diagram_base`, `#stage_1`, `#stage_2`, `#stage_3`).
  - Generated and visually verified multi-shot snapshot contact sheets for both remaining pillars:
    - **Pillar 2 (Hidden History):** `ancient_scholar` + `ancient_nalanda_courtyard` + `nalanda_scroll_astrolabe` -> `build/phase4_qa/pillar_history_qa_grid.jpg`.
    - **Pillar 3 (Cosmic & Scientific Paradoxes):** `ancient_scholar` / `sutradhar_narrator` + `celestial_cosmos_court` + `black_hole_anatomy` -> `build/phase4_qa/pillar_cosmos_qa_grid.jpg`.
  - Confirmed 100% clean canvas (zero captions, zero titles or part badges) and zero visual styling anomalies across all 3 editorial pillars.
- **Drop-In Real Audio Handling & Audio Engine Verification:**
  - Verified 1:1 match between `assets/AUDIO_LIBRARY_MANIFEST.md` and `config.yaml` (`bgm_by_pillar` and `sfx_tracks`).
  - Added automated unit test `test_08_audio_mixing_real_bgm_resampling_loop_and_fade` in `tests/test_render_pipeline.py` verifying real 44.1 kHz stereo audio looping (`-stream_loop -1`), 48 kHz stereo audio trimming with 1.2s exponential fade-out, and multi-track SFX ducking.
  - Verified full test suite: **40/40 PASSED** (100% pass, 0 failures).
  - Validated HyperFrames: `npx hyperframes lint` (0 errors) and `npx hyperframes check --json` (0 runtime/layout/contrast errors, `ok: true`).
- **Database Immutability:**
  - Root `episodes.db` confirmed bit-for-bit untouched (SHA-256: `729ACCE0CD4F31CC69CECA61470D331ABCBCE5E62B51728AB372CD28F83F8011`).
- **Manual Hand-off to Creator:**
  - Production workflow is fully documented and ready for creator-driven daily execution via [docs/MASTER_AUTOMATION_PROMPT.md](file:///c:/Users/manis/Projects/Sutradhar/docs/MASTER_AUTOMATION_PROMPT.md).

#### Phase 5 — Production Calibration & Scheduled Publishing Unlock: NEXT / FINAL
- **Step 1 (Pre-Launch Calibration):** Execute 3 consecutive daily calibration episodes across the 3 editorial pillars in strict `private_review` mode (`allow_public_or_scheduled: false`).
- **Step 2 (Mobile Quality Audit):** Review each private Short in YouTube Studio on mobile devices to verify pacing, audio loudness (-14 LUFS), zero mobile DAC clipping, and clean-canvas aesthetics.
- **Step 3 (Scheduled Publishing Unlock):** Once all 3 calibration episodes pass inspection, toggle `publishing.upload_mode: "scheduled"` and `publishing.allow_public_or_scheduled: true` in `config.yaml` to begin scheduled distribution (defaulting to 18:30 IST / 13:00 UTC).
