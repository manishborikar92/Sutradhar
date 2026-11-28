# Sutradhar — System Architecture & Maintainer Reference

> **Scope:** Developer, maintainer, and historical engineering reference for the **Sutradhar** autonomous YouTube Shorts production system (*Sutradhar Kinetic Storycraft v2*).  
> **Note:** Production story-directing rules live in [INSTRUCTIONS.md](./INSTRUCTIONS.md); operator setup and the 6-command daily runbook live in [SETUP_AND_OPERATIONS.md](./SETUP_AND_OPERATIONS.md).

---

## 1. System Overview & Package Topology

Sutradhar is structured around deep, cohesive Python modules in `scripts/sutradhar/`, thin zero-argument CLI facades in `scripts/`, and a modular browser ES/JavaScript runtime in `templates/runtime/` + `templates/thumbnail/`.

```text
scripts/
├── sutradhar/
│   ├── config.py                    # Pydantic-validated config.yaml & strict LanguagePolicy
│   ├── db.py                        # SQLite Schema v4, migrations, pillar rotation, --context & --repair
│   ├── models.py                    # EpisodePlanV2, SceneVisualSpec (StoryboardIR), ThumbnailSpec, PublishResult
│   ├── audio/
│   │   ├── elevenlabs_tts.py        # Tag-preserving pronunciations, pre-TTS quota gate, SHA-256 scene cache
│   │   ├── whisper_aligner.py       # 16 kHz ffmpeg PCM + faster-whisper small + RMS speech-burst snapping
│   │   ├── caption_builder.py       # Em-dash-safe tokenizer, 5-word windows, non-overlap clamp, kw highlights
│   │   └── sound_mixer.py           # 3-act BGM crossfade, +33ms peak-aligned SFX, 6.5:1 ducking, single 2-pass loudnorm
│   ├── visual/
│   │   ├── storyboard_composer.py   # Compiles EpisodePlanV2 + StoryboardIR + AudioManifest -> build/composition/
│   │   └── thumbnail_builder.py     # 1080x1920 JPEG cover + automated y=150..1770 2:3 Shorts crop verification
│   ├── qa/
│   │   ├── hyperframes_runner.py    # hyperframes lint, check --strict --safe-zone shorts, snapshot, measure look, hf-seek parity
│   │   ├── render_optimizer.py      # CRF/VBV encode control enforcing <= 55 MiB 1080x1920@30fps H.264 output
│   │   └── quality_gate.py          # Fail-closed DOM/Canvas telemetry, ebur128, KinoCut dual-profile, thumbnail bounds
│   └── publishing/
│       ├── oauth_refresh.py         # Local loopback + PKCE OAuth refresh helper
│       ├── thumbnail_verifier.py    # Pre-upload validation, processing poll, live sardefault.jpg CDN MAE/dhash parity
│       ├── metadata_policy.py       # English titles/tags/descriptions + Hindi audio lock + scriptural citations
│       └── youtube_client.py        # Resumable upload, paginated playlist sync, atomic DB + publishing_history commit
├── db_manager.py                    # Thin CLI facade (--init, --context, --create-series, --record-published, --repair)
├── build_audio.py                   # Thin CLI facade for sutradhar.audio
├── preview_frames.py                # Thin CLI facade for StoryboardIR compile + strict Shorts check + 15-frame grid
├── render_and_qa.py                 # Thin CLI facade for <= 55 MiB render + 48 kHz mix + KinoCut + thumbnail
├── publish_youtube.py               # Thin CLI facade (--publish, --update-playlists, --update-thumbnail, --verify-only)
├── thumbnail_utils.py               # Compatibility re-export facade for sutradhar.publishing.thumbnail_verifier
└── audition_voices.py               # Standalone voice audition utility (build/auditions/)

templates/
├── runtime/
│   ├── index.html.jinja2            # Declarative HyperFrames composition shell + #captions sub-composition
│   ├── styles.css                   # Safe-zone calibrated stage & opt-in .ctx-pill styles
│   ├── core/                        # seek_runtime.js (proxy={t}, hf-seek, mulberry32), scene_director.js
│   ├── backdrops/                   # atmosphere_v1.js (V1 skies/ridges/peak-clamped Kailash), architectural_stage.js (HORIZON_Y)
│   ├── rigs/                        # character_engine.js (traceCapsule limbs, 5-finger sculpted hands, 2.5D head turn)
│   ├── props/                       # props_library.js (mounted props, infographics & mythic artifacts)
│   ├── fx/                          # transitions.js (crossfade, whip, iris, throttled micro-grain)
│   └── captions/                    # captions.html.jinja2 (top: 1244px, max-height: 148px, rect.bottom <= 1395px)
└── thumbnail/
    └── cover_template.html.jinja2   # Shared 1080x1920 English cover importing character_engine & backdrops (2:3 safe)
```

---

## 2. Core Architectural Decisions & Rationale

### 2.1 Canvas2D + HyperFrames `data-composition-src` vs Legacy DOM/SVG Puppets
- **Why legacy DOM/SVG failed:** The pre-redesign `scripts/engine/` + `templates/composition/` pipeline mounted brittle SVG puppets inside mismatched `480x960` wrappers, relied on un-seekable `gsap.delayedCall()` / `.call()` mutations, and suffered broken subtitle key mismatches (`start_sec` vs `start`).
- **Modular Canvas2D + DOM solution:** Visuals render inside a declarative `Canvas2D` ES module runtime (`templates/runtime/`), while kinetic Hindi captions mount as a separate HyperFrames sub-composition (`#captions` with `data-composition-src="captions/captions.html"`).
- **No hidden canvas UI labels:** `<canvas data-layout-ignore="true">` is reserved strictly for scene artwork. Any opt-in contextual pill (`#contextual-overlay`) MUST render as an observable HTML/DOM node so `hyperframes check --strict --safe-zone shorts` validates contrast, clipping, and safe-zone bounds.

### 2.2 Seek Determinism
- Every composition registers a single GSAP timeline (`paused: true`) tweening `proxy = { t }` with `ease: "none"`, `immediateRender: false`, and `lazy: false`, listening to `hf-seek` (`detail.time`) and exposing `window.__timelines[id]`.
- Procedural randomness uses a seeded `mulberry32` PRNG (never `Math.random()`), and rendering gates on `document.fonts.ready` so headless Chromium frame workers produce byte-identical frames whether stepped sequentially or sought randomly (`hf-seek(12.6s)` parity `MAE <= 0.5`).

### 2.3 Bitrate & Compression Control (`<= 55 MiB`)
- Shifting full-screen `128x128` film-grain every `1/30s` frame under HyperFrames `--quality looks` (`has_b_frames=0`) defeated H.264 inter-frame compression on Episode 4, inflating the MP4 to `553.76 MB` (`71.29 Mbps`).
- Production caps micro-grain to static or `6 fps`-quantized overlays (`<= 0.03` alpha) and enforces a deterministic `libx264` CRF/VBV pass in `render_optimizer.py` (`1080x1920 @ 30fps`, `yuv420p`, `+faststart`), guaranteeing `file_bytes <= 57,671,680` (`55 MiB`).

### 2.4 KinoCut Dual-Profile & Full-Res Motion Telemetry
- `quality_gate.py` enforces **both** KinoCut profiles: `ui-capture-dark >= 88.0` (`all_passed: true`) and `default >= 55.0`, with `color_balance PASS`.
- Temporal motion uses full-resolution `extractplanes=y` frame diffs (avoiding downscaled-luma false positives) to enforce `static_fraction <= 0.15` and zero holds `> 3.2s`.

### 2.5 Audio Mastering (`-14.0 LUFS`, `-2.2 dBTP` WAV Headroom, `+33ms` SFX, `6.5:1` Ducking)
- Voiceover (`44.1 kHz` ElevenLabs synthesis) is EQ-shaped, mixed with up to `3` distinct non-duplicate BGM stems (`0` duplicate MD5s, `allow_synth_fallback: false`), and ducked via `6.5:1` sidechain compression (`ratio: 6.5`, `threshold: 0.03`, `attack_ms: 20`, `release_ms: 500`).
- Transition/sweep SFX (`whoosh-cinematic.mp3`, `riser.mp3`) compute negative pre-roll offsets so energy crests land `+33ms` after visual cuts (`DEFAULT_CUT_CREST_OFFSET_SEC`), with zero orphaned UI pops.
- A **single** 2-pass `loudnorm` targets **`-14.0 ± 0.5 LUFS`** and **`-2.2 dBTP`** in the `48,000 Hz` stereo WAV master so AAC encoding stays safely **`<= -1.5 dBTP`** without inter-sample clipping.

### 2.6 Speech Alignment & Em-Dash Compound Caption Tokenization
- `whisper_aligner.py` resamples scene WAVs to `16 kHz` mono PCM via `ffmpeg` and runs locally cached `WhisperModel("small", compute_type="int8", vad_filter=True, local_files_only=True)` paired with RMS speech-burst onset snapping.
- `caption_builder.py` splits tokens on internal punctuation (`—`, `-`, `/`) before stripping non-word characters so compound Devanagari phrases like `"कहलाए—नीलकंठ!"` preserve titular keyword highlighting (`kw: true`) inside `5`-word sliding windows (`rect.bottom <= 1395px`).

### 2.7 Database Schema v4 (`docs/schema.sql` & `sutradhar/db.py`)
- Formalizes four tables: `series` (with `series_title_en`, `series_title_hi`, `metadata_language`, `audio_language`), `episodes` (with `duration_sec`, `file_bytes`, `kinocut_score`, `static_fraction`, `tts_billed_chars`, `visual_direction_version`, `legacy_asset_path`, `published_at`, `video_url`), `publishing_history` (full upload/thumbnail/CDN audit log), and `audio_ledger` (per-scene SHA-256 cache & TTS telemetry).
- `compute_pillar_rotation` queries the latest non-failed `PUBLISHED` episode to cycle cleanly across `Ancient Epics & Lore -> Hidden History -> Cosmic & Scientific Paradoxes` even for open-ended (`total_planned_episodes IS NULL`) series.

### 2.8 YouTube Publishing & OAuth Hardening
- `youtube_client.py` polls `videos.list` until `uploadStatus == "processed"` AND `processingDetails.processingStatus == "succeeded"` before calling `thumbnails.set` (uploading while `"processing"` drops YouTube's `shortsAspectRatio` / `sardefault.jpg` slot).
- Live `sardefault.jpg` CDN parity (`HTTP 200`, `1080x1920`, `MAE <= 12.0`, `dhash <= 16`) is mandatory from Episode 3 onward; Episodes 1–2 remain untouched historical baselines.
- `oauth_refresh.py` implements local loopback + PKCE token refresh; `verify_live_channel_state(..., readonly=True)` uses `scopes=None` so read-only verification works with any valid token scope set.

---

## 3. ElevenLabs Scene Caching & Telemetry

- **Voice & Model:** `eleven_v4`, Viraj (`uuyFQegRan8rpIQCGu9K`), with read-only live subscription diagnostics via `scripts/elevenlabs_engine.py --check-subscription` (`GET /v1/user/subscription`).
- **SHA-256 Scene Caching:** Per-scene WAVs are content-addressed by `SHA-256(tagged_text, voice_id, model_id, settings)` in `build/cache/audio/` and logged in SQLite `audio_ledger` (`cache_hit`, `billed_chars`). Visual, caption, or thumbnail iterations hit the local cache with zero TTS API calls; single-scene script edits re-synthesize only the modified scene.

---

## 4. Historical Milestone Benchmarks & Design Evolution

| Milestone | Video ID | Size / Duration | KinoCut (`dark` / `default`) | Static Fraction | Billed Chars | Key Engineering Lesson |
| --- | --- | --- | --- | --- | --- | --- |
| **Legacy Pre-Redesign** | `cd1cc1mhfwg` (Ep 1), `hcKmhzjQkz4` (Ep 2) | `14.5–25.2 MB` | Synthetic / `~90` fake | `62.5%` | `1,018` / `805` | Un-seekable DOM/SVG puppets, broken captions, `sine=` BGM, `404` `sardefault.jpg` |
| **V1 — Dawn Ridge** | Benchmark only | `112.81 MB` / `63.50s` | `88.8` / `57.0` | `3.68%` | Reused Ep 3 | Proved deterministic Canvas2D atmospheric ridges, volumetric sun & bird flocks |
| **Candidate B — Ref-1 Cinema** | `oBcyiPy26rg` (Ep 3) | `36.92 MB` / `63.53s` | `89.4` / `52.7` | `47.24%` | `917` | Proved `HORIZON_Y = 1142` grounding, clean top bar, `2:3` English cover & `sardefault.jpg` CDN parity |
| **Episode 4 — Neelakantha Shiva** | `7PWFV7lQG6U` (Ep 4) | `553.76 MB` / `61.97s` | `94.0` / `59.8` | `0.54%` | `776` | Proved `traceCapsule` anatomy, `2.5D` head turn & `color_balance PASS`; exposed `553 MB` grain bloat & em-dash tokenizer bug |
| **Episode 5 — Nalanda Archive** | `kdTCMC9q7S4` (Ep 5) | `45.65 MiB` (`47.86 MB`) | `93.6` / `>= 55` | `5.87%` | `799` | First full end-to-end production Short on the unified `sutradhar/` + `templates/runtime/` architecture |

---

## 5. Maintainer Tooling, Test Architecture & Repo Layout

### 5.1 Maintainer CLI Flags
- `.\.venv\Scripts\python.exe scripts/db_manager.py --init`: Initialize or migrate `episodes.db` to Schema v4.
- `.\.venv\Scripts\python.exe scripts/db_manager.py --repair`: Run `PRAGMA integrity_check` and Schema v4 consistency repair.
- `.\.venv\Scripts\python.exe scripts/db_manager.py --record-published`: Manual DB recovery if a publish was interrupted after upload.
- `.\.venv\Scripts\python.exe scripts/publish_youtube.py --verify-only`: Strictly read-only live audit of published episodes, series playlists, `sardefault.jpg` CDN parity, and DB state.
- `.\.venv\Scripts\python.exe scripts/publish_youtube.py --update-playlists`: Sync English playlist titles/privacy on YouTube.
- `.\.venv\Scripts\python.exe scripts/publish_youtube.py --update-thumbnail --video-id <ID>`: Upload and CDN-verify custom thumbnail only.

### 5.2 Domain Test Suite (`tests/`)
All tests run in isolated temporary directories with zero live ElevenLabs or YouTube write calls:
- `test_db_models.py`: Schema v4 migrations, `EpisodePlanV2` / `StoryboardIR` validation, pillar rotation, `audio_ledger`.
- `test_runtime.py`: Canonical assets, `templates/runtime/` ES modules, deterministic `hf-seek`, peak-clamped Kailash geometry.
- `test_audio_pipeline_v2.py`: Tag-preserving pronunciations, `>= 70%` Devanagari validation, `faster-whisper small` + RMS alignment, em-dash tokenization, `sound_mixer`.
- `test_render_qa.py`: Storyboard compilation, `<= 55 MiB` `render_optimizer`, fail-closed `quality_gate` & end-to-end Chromium/KinoCut checks.
- `test_publishing_v2.py`: Metadata policy, `sardefault.jpg` CDN parity, playlist pagination, read-only verify, cross-document consistency.
- Supporting unit/contract suites: `test_config_standardization.py`, `test_db_manager.py`, `test_build_audio.py`, `test_elevenlabs_engine.py`, `test_audio_speed_pacing.py`, `test_audition_voices.py`, `test_render_pipeline.py`, `test_publish_youtube.py`, `test_thumbnail_utils.py`, `test_sutradhar_oauth_refresh.py`, `test_production_acceptance.py`.
