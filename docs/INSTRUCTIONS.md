# Sutradhar — Master Authoritative Directing & Production Specification

> **Primary AI Directive:** Read and follow `docs/INSTRUCTIONS.md` to produce every Sutradhar YouTube Short.  
> **Architecture Standard:** *Sutradhar Kinetic Storycraft v2* — modular `Canvas2D + DOM` ES modules (`templates/runtime/`) orchestrated by `scripts/sutradhar/`.

---

## 1. Priority Hierarchy & Visual North Star

1. **Tier 1 — Explicit User Overrides (Highest Priority):**
   - If the user specifies a **Topic**, **Script**, **Format** (`standalone` or `episodic_series`), **Playlist**, or **Visual Direction**, treat those inputs as locked requirements and fill remaining fields autonomously.
   - Preserve user-provided script phrasing and dramatic beats while adding ElevenLabs `[vocal tags]` and `StoryboardIR` staging.
2. **Tier 2 — Autonomous Production & Visual North Star:**
   - Operate strictly within local/open-source tooling (`HyperFrames`, `GSAP`, `Canvas2D`, `FFmpeg`, `faster-whisper small`, `KinoCut`, `Pillow`) and configured ElevenLabs TTS.
   - Anchor every visual decision on expressive `traceCapsule` anatomy, `HORIZON_Y` spatial grounding, clean stage margins, and multi-plane atmospheric lighting.

---

## 2. Pure Language Split & Platform Policy

Enforced identically by `config.yaml`, `sutradhar.config.LanguagePolicy`, `EpisodePlanV2`, and `sutradhar.publishing.metadata_policy`:

| Surface | Required Language | Hard Validation Rule |
| --- | --- | --- |
| **Voiceover Audio** | Hindi (`hi`) | Devanagari source (`>= 70%` Devanagari tokens across scenes); Viraj (`eleven_v4`) |
| **Burned-In Kinetic Captions** | Hindi (`hi`) | Synchronized Devanagari phrases inside `#captions` sub-composition (`rect.bottom <= 1395px`) |
| **On-Screen Contextual Pills** | English / Hindi (Opt-in) | Disabled by default (`contextual_pill.enabled = false`); zero top progress bars or counters |
| **Cover Thumbnail** | English (`en`) | Zero Devanagari in `thumbnail_spec`; dedicated `1080x1920` JPEG (`2:3` crop safe) |
| **YouTube Metadata & Playlists** | English (`en`) | Zero Devanagari in `youtube_title` (incl. `#Shorts`), `youtube_description`, `youtube_tags` (`10-15` tags), and `series_title`; `defaultLanguage="en"`, `defaultAudioLanguage="hi"`, `categoryId="27"` |

---

## 3. Scriptwriting, Scriptural Grounding & Narration Limits

### 3.1 Per-Episode Narration & Tag Length Limits
- **Character Accounting:** `1` billed char includes inline `[...]` expression tags.
- **Per-Episode Budget Lock:**
  - **Target Sweet Spot:** **`760–840` billed characters** across all scenes (including `[tags]`).
  - **Soft Warning:** `> 850` billed chars (`SOFT_WARN_BILLED_CHARS`).
  - **Hard Pre-TTS Abort:** **`> 900` billed chars** (`tts.max_billed_chars_per_episode = 900`).
- **Pre-TTS Validation Mandate:** `build/episode_plan.json` MUST pass `EpisodePlanV2` validation **before** calling `build_audio.py` and **before** `preview_frames.py` (never invert plan creation after rendering).

### 3.2 Pacing, Scriptural Provenance & Anti-Cliffhanger Law
- **Retention & Duration Bounds (`config.yaml` `episode_pacing`):**
  - Shorts retention sweet spot: **`42–58s`** (config target `40–120s`, hard bounds `30–180s`).
  - Scene count: **`5–15` scenes**; target **`8–35` words/scene**.
- **Dramatic Arcs:** Select `five_phase_compact_arc` (40–65s), `in_medias_res` (boiling-point hook), or `eight_phase_complete_arc` (longer explainers). Open Scene 1 with an immediate paradox or high-stakes confrontation (`<= 2.5s` hook).
- **Authentic Scriptural Grounding (`story_research`):** Ground every episode in verifiable Puranic, Itihasic, astronomical, or epigraphic sources (*Srimad Bhagavatam*, *Vishnu/Skanda/Shiva/Padma Puranas*, *Valmiki Ramayana*, *Mahabharata*, *Surya Siddhanta*, *Aryabhatiya*, Gupta/Maurya/Nalanda records). Citations are formatted automatically into YouTube descriptions.
- **Universal Anti-Cliffhanger Mandate:** Every episode (standalone or `episodic_series`) must resolve its central conflict cleanly in the final beat. Hindi and English cliffhangers (*"अगले भाग में"*, *"जारी रहेगा"*, *"पार्ट 2"*, *"to be continued"*, *"part 2"*) fail validation.

### 3.3 Pillar Rotation & Duplicate Prevention
Run `.\.venv\Scripts\python.exe scripts/db_manager.py --context` first to inspect:
1. `next_pillar` cycling across `Ancient Epics & Lore -> Hidden History -> Cosmic & Scientific Paradoxes` (computed from latest non-failed published episode).
2. `active_series_list` and `next_episode_number_in_series` / `next_global_episode_number`.
3. `previously_covered_topics` (`LIMIT 30`) and `previous_bespoke_assets` (never reuse a topic or `bespoke_asset_path`).
4. `monthly_tts_budget` (`audio_ledger` live usage and remaining quota).

---

## 4. Narrative-Adaptive Visual Modes (Zero Fixed Proscenium Box)

Select the scene's `visual_spec.atmosphere_mode` from story context (never force velvet theatre curtains or static black borders):
- **`palace_court`:** Architectural courtrooms, ashrams, and royal sabhas (`architectural_stage.js`, `dwaraka_durbar`, `brahmaloka_sabha`, `lanka_citadel`) with 1-point perspective floorboards, turned daises, diyas, and optional carved colonnades.
- **`dawn_epic`:** Outdoor Himalayan, cosmic-ocean, and celestial vistas (`atmosphere_v1.js`, `kailash_horizon`, `cosmic_ocean_manthan`, `ashram_twilight`) with multi-plane fog ridges, volumetric sun glow, feathered clouds, drifting mist, and bird flocks.
- **`archival`:** Historical and archaeological investigations (`nalanda_archival`, `mehrauli_iron_pillar`, `meru_route_scroll`) combining sandstone courtyards, parchment scrolls, and analytical magnifiers.
- **`cosmic_explainer`:** Relativistic/astronomical comparisons (`observatory_cosmos`, `brahmaloka_time_chakra`, `spacetime_comparator`, `earth_globe`, `brass_clock`) with deep-space starfields and progressive stage diagrams.

---

## 5. Anatomical Character Design & Rig Continuity

All characters render through `templates/runtime/rigs/character_engine.js` using JSON presets in `assets/characters/*.json`:
- **Tapered Capsule Limbs (`traceCapsule` / `drawAnatomicalArm`):** Two-pass organic shoulder-to-wrist contours with inner warm highlight (`#E8B186`) and crisp `#3B1E12` outlines (no uniform tube sticks, no brass rivet cutouts).
- **5-Finger Sculpted Hands (`drawSculptedHand`):** Wrist-anchored hand poses supporting `"neutral"`, `"namaskar"`, `"gesture"`, `"palm_cup"`, `"drink"`, `"shield"`, `"pull"`, `"bless"`, `"clasp"`, `"awed"`, `"throat_reach"`, `"veena_play"`, `"strum"`.
- **2.5D Head Turn Parallax (`drawMythFace`):** Continuous `turn` (`-0.45` to `+0.45`) shifts facial midline, nose bridge, brow curvature, iris gaze (`gaze_target`), and near/far ear visibility alongside natural blinking and phoneme-linked lip motion.
- **Hairlines & Series Continuity:** Use high-arched parted hairlines strictly clear of brows and *tilak* (zero dark forehead bars). Returning heroes (*Shiva, Devi, Brahma, Vishnu, Shani Dev, Kakudmi, Revati, Balarama, Ravana, Sutradhar*) preserve locked palettes and accessories across episodes.

---

## 6. Spatial Grounding Law (`HORIZON_Y`) & Peak Safety

- **`HORIZON_Y` Invariant:** Scene compositions lock wall baseboards and horizon plains to `HORIZON_Y = 1142` (`1445–1465` on subtitle-free covers).
- **Zero Floating Actors or Props (`GROUND_TOLERANCE_PX = 6.0`):**
  - Standing characters plant sandaled feet + dual cast shadows squarely at `(x, HORIZON_Y)` (`surface_type: "floor"` / `"terrain"` / `"rock"`).
  - Seated figures anchor flush onto `"dais"` (`-98px`) or `"lotus"` (`-54px`) pedestals; props declare explicit `mount` (`floor | dais | table | pedestal | terrain | sky`).
  - `storyboard_composer.py` verifies every character/prop vertical offset within `<= 6.0px` before rendering.
- **Peak Silhouette Clamping:** Procedural mountain ridges and snow gullies (e.g., `drawKailashSacredPeak` in `atmosphere_v1.js`) MUST clip (`ctx.clip()`) inside their parent outer mountain polygon so no snow shard protrudes into open sky at `1.66x` thumbnail scale.

---

## 7. Cinematography, Framing, Motion Fluidity & Rack Focus

- **YouTube Shorts Safe Zones (`1080x1920`):**
  - Top clear: `0..288px` (`Y >= 288px` for heads/crowns/overlays).
  - Bottom clear: `1400..1920px` (`520px` bottom clear; keep hands, interactive props, and captions above `Y = 1400px`).
  - Left clear: `>= 48px`; Right clear: `192px` (`X <= 888px`).
- **Continuous Motion Law (`static_fraction <= 0.15`):**
  - Drive continuous evolution via `camera_move` (`slow_push_in`, `slow_pull_out`, `pan_left`, `pan_right`, `drift`, `static` micro-drift), parallax depth planes (`0.03` starfields -> `1.0` foreground actors), flowing aura/particles, and gesture progression. Never leave static holds `> 3.2s`.
- **Rack Focus & Lower-Third Composition:** Dim background layers (`0.35–0.45` rack-focus) during intense emotional close-ups; populate ocean/outdoor lower thirds with reflective water highlights, stone ledges, or flora silhouettes instead of empty dark voids.

---

## 8. Deterministic HyperFrames Contract & Bitrate Ceiling

- **Modular ES Runtime:** Compose exclusively from `templates/runtime/` (`index.html.jinja2`, `styles.css`, `core/seek_runtime.js`, `core/scene_director.js`, `backdrops/*.js`, `rigs/character_engine.js`, `props/props_library.js`, `fx/transitions.js`, `captions/captions.html.jinja2`). Never inline JS blobs inside Python strings.
- **Seek Determinism:**
  - Single GSAP timeline per composition (`paused: true`) tweening `proxy = { t }` with `ease: "none"`, `immediateRender: false`, `lazy: false`.
  - Listen to `hf-seek` events (`detail.time`) and expose `window.__timelines[id]`.
  - Use deterministic `mulberry32` seeded PRNG, wait on `document.fonts.ready`, and **forbid** `gsap.delayedCall()`, `.call()` timeline callbacks, `repeat: -1`, and unseeded `Math.random()`.
- **Bitrate & File Size Guardrail (`<= 55 MiB`):**
  - Never shift full-frame canvas noise every `1/30s` frame (which breaks H.264 inter-frame compression). Keep micro-grain static or throttled (`<= 0.03` alpha).
  - `render_optimizer.py` enforces `1080x1920 @ 30fps` H.264 (`yuv420p`, `+faststart`) strictly **`<= 57,671,680` bytes (`55 MiB`)**.

---

## 9. Motivated Transitions & VFX

Use clean story-motivated transitions from `fx/transitions.js`:
- `fade` / `crossfade`: Atmospheric time shifts and compassionate beats.
- `whip` (`wipe_left`, `wipe_right`): Energetic spatial travel or rapid cause-and-effect cuts.
- `iris`: Focused divine reveals and cosmic medallions.
- `cut` / `flash_cut`: Sudden crisis eruptions or thunderous confrontations.
Pair transitions with subtle aura pulses, particle motes (`golden_embers`, `starfield_warp`, `quantum_nodes`, `himalayan_snow`, `crimson_embers`, `mystic_mist`), and story props.

---

## 10. Synchronized Hindi Captions & Validated DOM Labels

- **Clean Top Frame:** Keep `0` permanent progress bars, `0` episode counters, and `0` subscribe badges at the top of the frame.
- **Opt-In DOM Contextual Pills (`contextual_pill`):**
  - Disabled by default (`enabled: false`). When enabled for brief location/concept cues (`2–4` words), render strictly inside `#contextual-overlay` (`.ctx-kicker` `28px` / `.ctx-title` `32px`) as observable DOM nodes within `x: 48..888`, `y: 288..1248` (`y_px` `295..1220`).
  - **Never** draw UI pills or titles inside `<canvas data-layout-ignore="true">`, which hides them from HyperFrames' `--safe-zone shorts` layout checker.
- **Kinetic Hindi Captions (`templates/runtime/captions/captions.html.jinja2`):**
  - Mounted as a HyperFrames sub-composition (`#captions` with `data-composition-src="captions/captions.html"`).
  - Positioned strictly at `top: 1244px`, `left: 52px`, `right: 204px`, `max-height: 148px` (`rect.bottom <= 1395px` — always clearing `Y >= 1400px`).
  - Uses local `Noto Sans Devanagari` (`46px`, weight `800`), `5`-word sliding windows, and em-dash-safe tokenization (`—`, `-`, `/`) so compound words like `"कहलाए—नीलकंठ!"` preserve keyword highlighting (`kw: true`).

---

## 11. Voice Direction, `faster-whisper small` & Multi-Act Audio Mix

- **Tag-Preserving Synthesis (`elevenlabs_tts.py`):**
  - Pronunciations (`pronunciations_hi.yaml`) run through `apply_pronunciations_preserving_tags` so `[slowly, solemn, deep]`, `[pause]`, `[sighs]`, and `[building energy, intense]` reach `eleven_v4` intact while display/alignment strips tags cleanly.
  - Cache per-scene WAVs by `SHA-256(tagged_text, voice_id, model_id, settings)` and log every hit/miss to SQLite `audio_ledger`.
- **Word Alignment (`whisper_aligner.py`):**
  - Resample WAVs to `16 kHz` mono PCM via `ffmpeg` and transcribe with locally cached **`WhisperModel("small", compute_type="int8", vad_filter=True, local_files_only=True)`** paired with RMS speech-burst snapping.
- **Multi-Act Mix & Mastering (`sound_mixer.py`):**
  - Use up to `3` distinct non-duplicate BGM stems from `assets/audio/bgm/` (`0` duplicate MD5s; `allow_synth_fallback: false` — never synthesize sine drones).
  - Schedule only story-referenced SFX from `assets/audio/sfx/` (zero orphaned UI pops), aligning sweep/transition crests to `+33ms` after visual cuts (`DEFAULT_CUT_CREST_OFFSET_SEC`).
  - Apply voice-to-BGM sidechain ducking at **`6.5:1` (`ratio: 6.5`**, `threshold: 0.03`, `attack_ms: 20`, `release_ms: 500`) and a **single 2-pass `loudnorm`** targeting **`-14.0 ± 0.5 LUFS`**, **`-2.2 dBTP` WAV headroom** (yielding AAC MP4 **`<= -1.5 dBTP`**), **`48,000 Hz` stereo**.

---

## 12. Dedicated English Cover Thumbnails (`1080x1920` & `2:3` Safe)

Never grab raw video frames for thumbnails. Render via `templates/thumbnail/cover_template.html.jinja2` and `sutradhar/visual/thumbnail_builder.py`:
- **Format & Size:** `1080x1920` RGB JPEG, `<= 2.0 MiB` (`2,097,152 B`), `mean_stddev >= 4.0`.
- **Typography:** English-only `ThumbnailSpec` (`pill`, `headline_line1`, `headline_line2`, optional `sub_pill`); use supported weights only (`Inter` **`500`, `700`, `800`**; `Cinzel` **`600`, `800`** — never `900`, which is unsupported).
- **2:3 Shorts Shelf Crop Verification:** `thumbnail_builder.py` emits `build/thumbnail_2x3_crop.jpg` (`y = 150..1770`, `1080x1620`). Keep top badges and bottom footers safely inside `y = 200..1710` so Shorts grids never clip text.

---

## 13. Asset Reuse First & Bespoke Canvas/JSON Authoring

- Inspect `assets/manifest.yaml` (Schema `v2.0.0`) and `npx hyperframes catalog --json` before authoring new assets.
- Canonical asset directories: `assets/fonts/` (`31` `.woff2` + `fonts.css`), `assets/characters/*.json`, `assets/environments/*.json`, `assets/props/*.json`, `assets/audio/bgm/`, `assets/audio/sfx/`, and `assets/episodes/<slug>/` for episode-specific custom modules.
- Every episode's `bespoke_asset_path` (`canvas_prop:<slug>`, `character:<slug>`, `environment:<slug>`, or `assets/episodes/<slug>/...`) must be unique against `previous_bespoke_assets` and actively rendered in at least one scene.

---

## 14. Pre-Render & Post-Render Fail-Closed Verification Protocol

1. **Pre-Render Gate (`preview_frames.py`):**
   - Runs `hyperframes lint` (`0` errors), `hyperframes check --strict --safe-zone shorts --json` (`ok: true`, `0` errors, `0` warnings), headless Chromium runtime probe (`__timelines`, `hf-seek`, font load, caption `rect.bottom <= 1395`, contextual pill bounds), and stitches **15-frame** `build/qa_grid.jpg` + `build/qa_grid_safezones.jpg`.
   - **Human/AI Checkpoint:** Visually inspect `build/qa_grid.jpg` via `read_file` before running full MP4 encode.
2. **Post-Render Gate (`render_and_qa.py` -> `quality_gate.py`):**
   - Verifies MP4 contract (`1080x1920@30fps` H.264 + `48 kHz` stereo AAC, **`<= 55 MiB`**), `hf-seek` parity, zero black frames / frozen scenes, `hyperframes measure look`, **dual KinoCut profiles** (`ui-capture-dark >= 88.0` with `all_passed: true`, `default >= 55.0`, `color_balance PASS`, `static_fraction <= 0.15`), `ebur128` loudness + quiet `0.7s` tail (`<= -16.0 dBFS`) + zero mid-episode silences, `whisper_alignment` match ratios, `build/final_qa_grid.jpg`, and `build/thumbnail.jpg` + `build/thumbnail_2x3_crop.jpg`.
   - Visually inspect `build/final_qa_grid.jpg`, `build/thumbnail.jpg`, and `build/thumbnail_2x3_crop.jpg` before publishing.

---

## 15. YouTube Publishing & `sardefault.jpg` CDN Parity

Handled cohesively by `scripts/sutradhar/publishing/` (`youtube_client.py`, `metadata_policy.py`, `thumbnail_verifier.py`):
1. Re-validate `EpisodePlanV2`, `final_short.mp4` (`<= 55 MiB`), `qa_report.json`, English metadata (`#Shorts`, 10–15 tags, citations), and `1080x1920` JPEG + `2:3` crop before consuming upload quota.
2. Upload video (`containsSyntheticMedia=True`, `selfDeclaredMadeForKids=False`, `defaultLanguage="en"`, `defaultAudioLanguage="hi"`).
3. Resolve/create English series playlist via paginated `playlists.list` and assign video (fail closed if `episodic_series` playlist assignment fails).
4. Poll `videos.list` until **`uploadStatus == "processed"` AND `processingDetails.processingStatus == "succeeded"`** before calling `thumbnails.set`.
5. Verify live `shortsAspectRatio` (`sardefault.jpg`) from `i.ytimg.com` (`HTTP 200`, `1080x1920`, **`MAE <= 12.0`**, **`dhash <= 16`**).
6. Atomically persist `episodes` + `publishing_history` + `series.completed_episodes` in SQLite via `sutradhar.db.record_published_episode`, and write `build/publish_result.json` + `build/publish_verification.json`.

---

## 16. Safety Boundaries, 6-Command Atomic Runbook & Max-2-Repair Loop

### 16.1 Six-Command Daily Production Runbook
```powershell
# 1. Inspect series state, pillar rotation, topic history & TTS quota
.\.venv\Scripts\python.exe scripts/db_manager.py --context

# 2. Initialize new series universe ONLY when starting a new episodic series
.\.venv\Scripts\python.exe scripts/db_manager.py --create-series

# 3. Synthesize Hindi narration (pre-TTS <= 900 cap), Whisper small + RMS align & build captions
.\.venv\Scripts\python.exe scripts/build_audio.py

# 4. Compile StoryboardIR, run HyperFrames --strict --safe-zone shorts & stitch 15-frame qa_grid.jpg
.\.venv\Scripts\python.exe scripts/preview_frames.py

# 5. Render <= 55 MiB MP4, mix 48 kHz audio, render cover + 2:3 crop & run fail-closed Quality Gate
.\.venv\Scripts\python.exe scripts/render_and_qa.py

# 6. Upload, assign English playlist, verify sardefault.jpg CDN parity & commit SQLite atomically
.\.venv\Scripts\python.exe scripts/publish_youtube.py
```
*(Manual recovery & read-only utilities: `scripts/db_manager.py --record-published`, `scripts/db_manager.py --repair`, and `scripts/publish_youtube.py --verify-only` / `--update-playlists` / `--update-thumbnail`.)*

### 16.2 Repair Ceiling & Hard Safety Rules
- **Max 2 Repair Loops:** If `preview_frames.py` or `render_and_qa.py` fails, diagnose and repair `episode_plan.json` / runtime specs at most **2 times**. If defects persist, **abort without uploading** (zero extra TTS spend if script unchanged via SHA-256 cache).
- **Never run `git add`, `git commit`, `git push`, `git reset`, or `git rm`** without explicit user authorization in the current turn.
- **Never edit `episodes.db` directly** outside `scripts/db_manager.py` / `sutradhar.db`, and **never log or print secrets** from `.env.local`.
