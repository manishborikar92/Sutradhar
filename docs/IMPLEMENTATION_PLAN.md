# IMPLEMENTATION_PLAN.md
## Sutradhar — Zero-External-API Autonomous Serialized YouTube Shorts Pipeline
### (Antigravity `/automation` + Series State Machine + Triple-Mode SVG Rigs + Kokoro-82M EN + HyperFrames + KinoCut 2.0)

---

### 1. Executive Summary & Architectural Decisions

This specification defines **Sutradhar**, a **100% Antigravity-native, zero-recurring-external-cost daily YouTube Shorts pipeline** engineered for high-retention serialized edutainment, native **YouTube Shorts Series** compatibility, and sustainable **YouTube Partner Program (YPP) monetization**.

#### Core Design Principles
1. **Zero External AI APIs ($0.00 External API Spend):**
   - **Google Antigravity** acts as the sole intelligence engine—handling pillar rotation, multi-episode series planning, scriptwriting, bespoke SVG rig authoring, and multimodal visual QA inspection. No external LLM, image, TTS, or video API keys are required.
2. **Global English Master (`en`) + YouTube Auto-Dubbing Hub:**
   - Sutradhar locks permanently to **Global English (`en`)** to maximize Tier-1 RPM, Kokoro-82M voice naturalness, and `faster-whisper` word-alignment precision.
   - Because English is YouTube’s primary Auto-Dubbing hub, setting `defaultAudioLanguage: "en"` unlocks automatic distribution into **Hindi and Telugu (with Expressive Speech)**, Tamil, Bengali, Malayalam, Punjabi, and 20+ global languages without fracturing the channel’s core Shorts feed.
   - A local **`pronunciations.yaml`** phonetic map ensures Sanskrit, Indian epic, and historical proper nouns sound natural and respectful in English narration while captions preserve exact spelling.
3. **Cohesive 3-Pillar Editorial Architecture + Strict Series State Machine:**
   - Rotates cleanly across **3 thematically unified pillars**—*Ancient Epics & Lore*, *Hidden History*, and *Cosmic & Scientific Paradoxes*—under one unified *Sutradhar* storyteller voice.
   - Every topic runs as a self-contained **3-to-6-episode mini-series** in SQLite (`episodes.db`), strictly completing `Part 1` through `Part N` while auto-syncing episodes into a dedicated YouTube playlist (`youtube_playlist_id`) ready for native **YouTube Shorts Series**.
4. **100% Offline, Commercial-Safe Audio Stack:**
   - **Kokoro-82M (`kokoro-onnx`, Apache-2.0)** synthesizes studio-grade English narration locally on CPU with a consistent signature narrator preset (or weighted blend of `am_fenrir` + `bm_george`).
   - **`faster-whisper` (`base`, `int8` CPU)** produces deterministic word-level timestamps for exact `#FFD700` active-word karaoke highlighting.
5. **YPP Originality-First Visual Pipeline + Pre-Render Snapshot Gate:**
   - Visuals render deterministically in `1080x1920` (30fps) via **HyperFrames** (`hyperframes` `^0.9.19`) + **GSAP**, combining modular SVG character rigs, **at least 1 newly authored bespoke SVG per episode**, kinetic callout cards, sidechain-ducked BGM, and transition SFX to stay fully compliant with YouTube’s **"Inauthentic Content"** policy.
   - A fast **pre-render snapshot QA gate** (`preview_frames.py`) verifies layout, safe zones, and SVG integrity before full `--quality high` rendering.
6. **Zero-Argument Pre-Whitelisted Commands:**
   - All stateful handoffs occur via JSON files inside `build/`, enabling unattended Antigravity `/automation` runs with **7 static, zero-argument whitelisted commands**.

---

### 2. Verified Zero-Cost Technology Stack

| Pipeline Layer | Tool / Service | Config / Version | License / Tier | Free Quota & Ceiling | External Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Orchestrator, Writer & Vision QA** | Google Antigravity IDE + `/automation` | Built-in frontier models | Developer's Antigravity plan | Runs locally via Antigravity Desktop / CLI | **$0 extra** |
| **Agent Skills** | `hyperframes` + `svg-character-animation` | Global: `$HOME/.agent/skills/` (`npx skills add -g`) | Apache 2.0 / Open Skills | Global `SKILL.md` rules + HyperFrames registry blocks | **$0.00** |
| **Local Neural TTS (English)** | `kokoro-onnx` (Kokoro-82M v1.0) | Signature voice: `am_fenrir` (or `0.65*am_fenrir + 0.35*bm_george`), fallback `am_michael` | **Apache 2.0** (Commercial-safe) | Unlimited offline CPU synthesis; zero API keys | **$0.00** |
| **Word-Level Caption Alignment** | `faster-whisper` (CTranslate2) | `base` (`compute_type="int8"`, CPU, `language="en"`) | MIT | Unlimited offline forced word timestamps (~2–4s per Short on CPU) | **$0.00** |
| **2.5D SVG & Shader Renderer** | `hyperframes` (`^0.9.19`) + GSAP | Node.js 22+ + Chromium + FFmpeg | Apache 2.0 | Unlimited local `1080x1920` 30fps renders; **no watermark** | **$0.00** |
| **Audio Mastering & Tech QA** | `kinocut` + `ffmpeg` | `kinocut==2.0.1` | Apache 2.0 / LGPL | Unlimited `-14.0 LUFS` mastering, sidechain ducking, quality gate (`>=80`) | **$0.00** |
| **Series & Episode Database** | SQLite3 | `episodes.db` | Public Domain | Local relational DB enforcing strict series completion & playlist sync | **$0.00** |
| **YouTube Publishing & Series** | `google-api-python-client` | YouTube Data API v3 | Google Cloud Free Quota | **100 `videos.insert` calls/day** (Uploads bucket) + **10,000 units/day** other (`playlists.insert`: 50, `playlistItems.insert`: 50) | **$0.00** |

---

### 3. Repository Structure

```text
sutradhar/
├── docs/
│   ├── IMPLEMENTATION_PLAN.md          # This architectural specification
│   └── MASTER_AUTOMATION_PROMPT.md     # Daily prompt executed by Antigravity /automation
│                                       # (Agent skills installed globally: $HOME/.agent/skills/ via npx skills add -g)
├── assets/
│   ├── bgm/
│   │   ├── dramatic_mythology.mp3      # Royalty-free CC0 / YouTube Audio Library bed
│   │   ├── cosmic_mystery.mp3          # Royalty-free ambient synth/space bed
│   │   └── epic_history.mp3            # Royalty-free cinematic percussion/strings bed
│   ├── sfx/
│   │   ├── whoosh_soft.wav             # CC0 scene-transition whoosh
│   │   ├── sub_hit.wav                 # CC0 dramatic reveal impact
│   │   └── riser_tension.wav           # CC0 hook / cliffhanger tension swell
│   └── svg/
│       ├── characters/                 # Modular rigged character SVGs (viewBox="0 0 800 1200")
│       │   ├── sutradhar_narrator.svg  # Signature host/storyteller character rig
│       │   ├── ravana.svg
│       │   ├── shani_dev.svg
│       │   ├── narad_muni.svg
│       │   └── lord_shiva.svg
│       ├── backdrops/                  # Multi-plane environment SVGs (viewBox="0 0 1080 1920")
│       │   ├── golden_lanka_throne.svg
│       │   ├── mount_kailash.svg
│       │   ├── deep_cosmos_nebula.svg
│       │   ├── ancient_temple_ruins.svg
│       │   └── quantum_grid_void.svg
│       └── diagrams/                   # Bespoke animated SVG diagrams & props (viewBox="0 0 900 900")
│           └── black_hole_anatomy.svg  # Starter diagram; Antigravity authors >=1 new asset per episode
├── build/                              # Ephemeral per-episode artifacts (gitignored)
│   ├── audio/                          # Scene WAVs + concatenated narration_full.wav
│   ├── new_series_plan.json            # Written by Antigravity only when starting a new series
│   ├── episode_plan.json               # Written by Antigravity for today's episode
│   ├── manifest.js                     # Generated by build_audio.py (window.EPISODE_MANIFEST)
│   ├── qa_grid.jpg                     # Pre-render 3x3 scene-midpoint snapshot sheet
│   ├── raw_video.mp4                   # Rendered by HyperFrames CLI (--quality high)
│   ├── final_short.mp4                 # Sidechain-ducked, SFX-mixed, -14.0 LUFS master
│   ├── final_qa_grid.jpg               # Post-render decoded frame verification sheet
│   └── publish_result.json             # Written by publish_youtube.py with video_id & playlist_id
├── scripts/
│   ├── db_manager.py                   # Fixed CLI: --init | --context | --create-series | --record-published
│   ├── build_audio.py                  # Kokoro-82M synthesis + pronunciations.yaml + faster-whisper alignment
│   ├── preview_frames.py               # HyperFrames lint + check --json + mid-scene snapshots -> qa_grid.jpg
│   ├── render_and_qa.py                # HyperFrames --quality high + FFmpeg sidechain/SFX + KinoCut QA (>=80)
│   └── publish_youtube.py              # Single-call videos.insert + playlist/Shorts Series sync
├── index.html                          # HyperFrames 1080x1920 master composition (triple visual mode)
├── styles.css                          # 2026 Safe-zone captions, series badge, SVG filters & mood themes
├── engine.js                           # GSAP skeletal acting, diagram reveals, kinetic stats, parallax & FX
├── config.yaml                         # Locked EN voice/blend, 3 pillars, BGM/SFX, upload_mode, publish hour
├── pronunciations.yaml                 # Phonetic overrides for Sanskrit, historical & scientific terms
├── episodes.db                         # SQLite series & episode ledger
├── package.json                        # hyperframes (^0.9.19) & gsap dependencies
├── requirements.txt                    # kokoro-onnx, faster-whisper, kinocut==2.0.1, google-api-python-client, pyyaml, pydantic, pillow, soundfile, numpy
└── .env.youtube.example                # Dedicated YouTube OAuth2 env file (isolated from HyperFrames .env)

```

---

### 4. Series Management, Editorial Identity & 2026 Retention Blueprint

#### 4.1 Brand Cohesion & Strict Pillar Rotation (`config.yaml` + `episodes.db`)

1. **Single-Language Global English Lock (`en`):**
* Every Sutradhar Short is written, narrated, and captioned in crisp, cinematic English (`defaultAudioLanguage: "en"`, `defaultLanguage: "en"`).
* **YouTube Auto-Dubbing** (enabled in Studio) handles automatic Expressive Speech distribution into Hindi and Telugu plus 20+ other languages without mixing spoken languages on the primary feed.


2. **Cohesive 3-Pillar Rotation:**
* Rotate across 3 tightly connected curiosity pillars so consecutive series retain the same viewer profile:
1. **`Ancient Epics & Lore`** (Sanatan Dharma, Puranic paradoxes, mythic cosmology, forgotten legends)
2. **`Hidden History`** (Ancient Indian & world empires, lost engineering, untold turning points)
3. **`Cosmic & Scientific Paradoxes`** (Astrophysics, quantum mysteries, deep time, reality-bending science)




3. **Active Series Lock & Automatic Completion:**
* Every series defines **3 to 6 episodes** (`total_planned_episodes`) stored in `series_bible_json`. While `status == 'ACTIVE'`, `db_manager.py --context` locks each daily run to `completed_episodes + 1`. On the final episode, `db_manager.py --record-published` flips `series.status = 'COMPLETED'`.



#### 4.2 Viral 2026 YouTube Shorts Pacing & YPP Compliance

* **36–46 Seconds Total Across 7–8 Dynamic Scenes (~4.5–6.0s each):** Targets the peak Shorts completion and rewatch zone.
* **12–22 Spoken Words per Scene (Kokoro Prosody Sweet Spot):** Avoids Kokoro-82M’s short-utterance artifacts (<10 tokens) while keeping delivery brisk and punchy.
* **0–2.5 Second Pattern-Interrupt Hook (Scene 1):** Drops viewers straight into a paradox, visual reveal, or high-stakes moment—never a channel intro or greeting.
* **Standalone Clarity + Serial Pull:** Every episode makes complete sense to a cold Shorts-feed viewer while planting an open-loop cliffhanger for the next part (or series finale).
* **YPP "Inauthentic Content" & Originality Safeguards:**
* **Mandatory Per-Episode Bespoke Asset:** Every episode authors at least **1 brand-new, topic-specific SVG asset** (diagram, cutaway, map, artifact, or backdrop variant).
* **Triple-Mode Visual Variety:** Alternates `character_drama`, `explainer_diagram`, and `kinetic_callout` scenes within each episode alongside sidechain-ducked BGM and scene transition SFX.
* **Full Metadata Compliance:** Declares `containsSyntheticMedia: True`, `selfDeclaredMadeForKids: False`, and `defaultAudioLanguage: "en"` on upload.



---

### 5. Triple-Mode Modular SVG Rig, Safe Zones & Shader Contract

All `.svg` files in `assets/svg/` follow strict DOM layer contracts so `engine.js` animates existing and newly authored SVGs automatically.

#### 5.1 Mode A: Character Drama (`visual_mode: "character_drama"`)

* **Character Rigs (`assets/svg/characters/*.svg`, `viewBox="0 0 800 1200"`):**
* Required `<g>` IDs (z-order back-to-front): `#char_aura`, `#char_body` (`data-pivot-x/y`), `#arm_left` (`data-pivot-x/y`), `#char_head` (`data-pivot-x/y`), `#eyes_open`, `#eyes_closed`, `#brows`, `#arm_right` (`data-pivot-x/y`), and nested `#prop_weapon`.
* Driven by `emotion` (`calm`, `wrath`, `shock`, `smirk`, `meditating`) and `action_gesture` (`idle_breathe`, `raise_weapon`, `point_accuse`, `bless_hand`, `tremble`).


* **Backdrop Rigs (`assets/svg/backdrops/*.svg`, `viewBox="0 0 1080 1920"`):**
* Required depth layers: `#bg_far_sky`, `#bg_mid_architecture`, `#bg_fg_pillars` styled via CSS variables (`var(--sky-top)`, `var(--sky-bottom)`, `var(--accent-glow)`, `var(--shadow-tint)`).



#### 5.2 Mode B: Explainer & Science Diagrams (`visual_mode: "explainer_diagram"`)

* **Diagram Rigs (`assets/svg/diagrams/*.svg`, `viewBox="0 0 900 900"`):**
* Required `<g>` IDs: `#diagram_base` (core structure/axis), progressive reveal groups `#stage_1` through `#stage_4` driven by `active_diagram_stage` (`1..4`), and `#highlight_pulse` styled with `#divine-bloom` or `#cosmic-glow`.



#### 5.3 Mode C: Kinetic Stat / Timeline Callout (`visual_mode: "kinetic_callout"`)

* High-contrast animated typography / counter / comparison card over a mood-tinted backdrop + particles using `callout_headline` and `callout_subtext`.

#### 5.4 Procedural Shaders, Particles & Verified 2026 Safe-Zone Layout

* **Inline SVG `<filter>` Graphs:** `#divine-bloom`, `#fire-haze` (`feTurbulence`), and `#parchment-grain`.
* **Frame-Locked Canvas Particles (`particle_theme`):** `<canvas id="fx-canvas">` driven by GSAP `onUpdate` progress renders `"golden_embers"`, `"starfield_warp"`, `"quantum_nodes"`, or `"mystic_mist"`.
* **Verified 2026 YouTube Shorts Safe-Zone Layout (`1080 × 1920`):**
* Keep clear: **Top `288px**`, **Bottom `520–672px**` (clears handle, title, Subscribe, and the Shorts Series *"Watch Series"* pill), **Right `192px**` (clears Like/Comment/Share/Remix stack), **Left `48px**`.
* **Top Series Badge:** `top: 300px; left: 64px; max-width: 816px;` (`PART 2 OF 4 • COSMIC PARADOXES`).
* **Primary Visual Focal Area (Characters / Diagrams):** Vertically centered between `y: 380px` and `y: 1220px`, horizontally constrained within `x: 64px..880px`.
* **Subtitles:** `bottom: 560px; left: 64px; right: 200px;` with high-contrast backing and `#FFD700` active-word highlight.



---

### 6. Database & JSON Schemas

#### 6.1 SQLite Schema (`episodes.db`)

```sql
CREATE TABLE IF NOT EXISTS series (
    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_title TEXT NOT NULL,
    pillar TEXT NOT NULL,                 -- 'Ancient Epics & Lore' | 'Hidden History' | 'Cosmic & Scientific Paradoxes'
    tts_voice TEXT NOT NULL,              -- Kokoro preset or blend spec from config.yaml
    bgm_track TEXT NOT NULL,
    total_planned_episodes INTEGER NOT NULL,
    completed_episodes INTEGER NOT NULL DEFAULT 0,
    series_bible_json TEXT NOT NULL,      -- Full planned episode-by-episode arc outline
    youtube_playlist_id TEXT,             -- Auto-created playlist ID for YouTube Shorts Series grouping
    status TEXT NOT NULL DEFAULT 'ACTIVE',-- 'ACTIVE' | 'COMPLETED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS episodes (
    episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL,
    episode_number_in_series INTEGER NOT NULL,
    global_episode_number INTEGER NOT NULL UNIQUE,
    youtube_title TEXT NOT NULL,
    summary TEXT NOT NULL,
    bespoke_asset_path TEXT NOT NULL,     -- Tracks unique SVG created for this episode (YPP originality audit)
    script_json TEXT NOT NULL,
    youtube_video_id TEXT,
    scheduled_publish_at TEXT,
    status TEXT NOT NULL,                 -- 'PUBLISHED' | 'PRIVATE_REVIEW' | 'FAILED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (series_id) REFERENCES series(series_id)
);

```

#### 6.2 `build/episode_plan.json` Schema

```json
{
  "series_id": 1,
  "series_title": "Secrets of the Event Horizon",
  "pillar": "Cosmic & Scientific Paradoxes",
  "episode_number_in_series": 2,
  "total_planned_episodes": 4,
  "global_episode_number": 2,
  "tts_voice": "am_fenrir:0.65+bm_george:0.35",
  "bgm_track": "cosmic_mystery.mp3",
  "bespoke_asset_path": "assets/svg/diagrams/spaghettification_tidal_gradient.svg",
  "youtube_title": "What Happens The Second You Cross a Black Hole? (Part 2/4) #Shorts",
  "youtube_description": "Part 2 of 4: Secrets of the Event Horizon. At the horizon, gravity stretches time and matter beyond recognition. Watch the full series on Sutradhar! #Science #Space #Shorts",
  "summary": "Explains gravitational time dilation and tidal spaghettification at a black hole's event horizon.",
  "scenes": [
    {
      "scene_index": 1,
      "narration_text": "Cross this invisible boundary, and the universe outside ages millions of years in a single heartbeat.",
      "caption_text": "Cross this invisible boundary, and the universe outside ages millions of years in a single heartbeat.",
      "visual_mode": "explainer_diagram",
      "backdrop_rig": "deep_cosmos_nebula",
      "diagram_rig": "spaghettification_tidal_gradient",
      "active_diagram_stage": 1,
      "primary_character": null,
      "secondary_character": null,
      "callout_headline": null,
      "callout_subtext": null,
      "emotion": "calm",
      "action_gesture": "idle_breathe",
      "mood_palette": "cosmic_indigo",
      "particle_theme": "starfield_warp",
      "camera_motion": "dramatic_zoom",
      "transition_sfx": "sub_hit.wav"
    }
  ]
}
```

#### 6.3 `build/new_series_plan.json` Schema

```json
{
  "series_title": "Secrets of the Event Horizon",
  "pillar": "Cosmic & Scientific Paradoxes",
  "tts_voice": "am_fenrir",
  "bgm_track": "cosmic_mystery.mp3",
  "total_planned_episodes": 3,
  "series_bible_json": {
    "arc_summary": "Overarching multi-episode season arc (>=15 chars).",
    "continuity_notes": "Optional visual/narrative continuity guidance.",
    "episodes": [
      {
        "episode_number": 1,
        "working_title": "Event Horizon Paradox Part 1",
        "hook": "Opening 0-2.5s curiosity hook (>=10 chars).",
        "narrative_direction": "Core story/explanation beats for this episode (>=15 chars).",
        "planned_bespoke_asset": "assets/svg/diagrams/horizon_clock_dilation.svg",
        "cliffhanger_or_payoff": "Bridge to Part 2 or finale payoff (>=10 chars)."
      }
    ]
  }
}
```

#### 6.4 `build/publish_result.json` Schema

```json
// build/publish_result.json (extra keys forbidden; locked to PRIVATE_REVIEW/FAILED while private_review lock is active)
{
  "video_id": "abc123XYZ",
  "playlist_id": "PL_SERIES_001",
  "upload_status": "PRIVATE_REVIEW",
  "upload_mode": "private_review",
  "privacy_status": "private",
  "scheduled_publish_at": null,
  "video_url": "https://youtube.com/shorts/abc123XYZ",
  "error_message": null
}
```

---

### 7. Specifications for the 7 Pre-Whitelisted Static Scripts (`scripts/`)

All 7 runtime commands take **zero dynamic arguments**, ensuring full compatibility with unattended Antigravity `/automation` `agent_permissions`:

1. **`python scripts/db_manager.py --context`** *(plus one-time setup `python scripts/db_manager.py --init`)*
* Outputs JSON containing: `channel_config` (`pillars`, default `tts_voice`, `upload_mode`), `active_series` (including `youtube_playlist_id` and `series_bible_json`), `next_episode_number_in_series`, `next_global_episode_number`, `completed_series_history` (last 20), and `available_rigs` across `characters/`, `backdrops/`, `diagrams/`, `bgm/`, and `sfx/`.


2. **`python scripts/db_manager.py --create-series`**
* Reads `build/new_series_plan.json`, validates schema via Pydantic (3–6 episodes, valid pillar), and inserts a new `ACTIVE` row into `series`.


3. **`python scripts/build_audio.py`**
* Reads `build/episode_plan.json` and `pronunciations.yaml`.
* Applies whole-word case-insensitive phonetic replacements from `pronunciations.yaml` to `narration_text` before passing to **`kokoro-onnx`** (preserving clean spelling in `caption_text`). Supports single voice IDs (e.g., `am_fenrir`) or weighted voice blends (`am_fenrir:0.65+bm_george:0.35`) via vector averaging.
* Trims dead silence, measures exact durations via `ffprobe`, concatenates `build/audio/narration_full.wav`, and runs **`faster-whisper` (`base`, `int8`, CPU, `language="en"`, `word_timestamps=True`)** on each scene WAV to align exact word timings onto `caption_text`.
* Validates total runtime (34–50s) and writes `build/manifest.js` (`window.EPISODE_MANIFEST = {...};`).


4. **`python scripts/preview_frames.py`** *(Fast Pre-Render Visual QA Gate)*
* Runs `npx hyperframes lint` and `npx hyperframes check --json`.
* Computes scene midpoint timestamps from `build/manifest.js` and runs `npx hyperframes snapshot --at <midpoints>` (~10s total without full MP4 encoding).
* Stitches snapshots into `build/qa_grid.jpg` for Antigravity multimodal visual inspection.


5. **`python scripts/render_and_qa.py`**
* Runs `npx hyperframes render --quality high --output build/raw_video.mp4`.
* Mixes scene transition SFX (`assets/sfx/`) at exact scene timestamps and applies **FFmpeg `sidechaincompress**` dynamic ducking to `bgm_track` under `narration_full.wav`.
* Normalizes final audio to **`-14.0 LUFS`** via `kinocut.Client().normalize_audio(..., target_lufs=-14.0)` into `build/final_short.mp4`.
* Runs `kino.quality_check("build/final_short.mp4")` and `kino.release_checkpoint("build/final_short.mp4", min_score=80)`, verifies `ffprobe` duration matches `manifest.js`, and writes decoded frame sheet `build/final_qa_grid.jpg`.


6. **`python scripts/publish_youtube.py`**
* Loads OAuth2 credentials from **`.env.youtube`** (isolated from `.env` so HyperFrames CLI emits zero unrecognized-key warnings).
* Executes a **single `videos().insert(part="snippet,status", ...)**` call with:
* `snippet`: `title`, `description`, `categoryId: "27"` (Education), `defaultAudioLanguage: "en"`, `defaultLanguage: "en"`.
* `status`: `privacyStatus: "private"`, `publishAt` (next `18:30 IST` / `13:00 UTC` if `upload_mode == "scheduled"`, omitted if `upload_mode == "private_review"`), `selfDeclaredMadeForKids: False`, and **`containsSyntheticMedia: True`** natively on insert.


* Creates the series playlist via `playlists().insert` on Part 1 (if `youtube_playlist_id` is null) and appends `video_id` via `playlistItems().insert` in episode order for native **YouTube Shorts Series** grouping.
* Writes `video_id`, `playlist_id`, `upload_status`, and `scheduled_publish_at` to `build/publish_result.json`.


7. **`python scripts/db_manager.py --record-published`**
* Reads `build/episode_plan.json` and `build/publish_result.json`, persists `youtube_playlist_id` (if newly created), records the episode in `episodes`, increments `completed_episodes`, and flips `series.status = 'COMPLETED'` on the final episode.



---

### 8. Setup & Antigravity `/automation` Runbook

1. **Install Dependencies, Local Models & Skills:**
```bash
npm install
npx hyperframes browser ensure
npx skills add heygen-com/hyperframes
npx skills add het8802/OpenNolan --skill svg-character-animation
pip install -r requirements.txt
python scripts/db_manager.py --init

```


*(First run of `build_audio.py` caches Kokoro-82M ONNX weights + voices and `faster-whisper` `base` int8 weights locally for 100% offline execution.)*
2. **Configure YouTube OAuth2 (`.env.youtube`) & Studio Auto-Dubbing:**
* Enable **YouTube Data API v3** in Google Cloud Console, publish the OAuth Consent Screen to **Production** (prevents 7-day token expiry), and store `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN` in `.env.youtube`.
* In **YouTube Studio → Settings → Channel → Advanced Settings**, enable **Automatic Dubbing** (with Expressive Speech) so every Global English Short automatically reaches Hindi, Telugu, and global audiences.


3. **Calibration Pass (`upload_mode: "private_review"`):**
* Keep `upload_mode: "private_review"` in `config.yaml` for the first 3–5 episodes.
* Open `sutradhar/` in **Google Antigravity IDE**, configure `agent_permissions` to allow the 7 exact commands, and run an interactive pass of `docs/MASTER_AUTOMATION_PROMPT.md`.
* Inspect the uploaded private Short on a real mobile device (safe zones, voice clarity, pronunciation of Sanskrit/historical terms, and Auto-Dubbing track quality).


4. **Enable Daily `/automation` Schedule:**
* Switch `upload_mode: "scheduled"` in `config.yaml`.
* Schedule `/automation` **Daily at 16:30 IST** pointing to `docs/MASTER_AUTOMATION_PROMPT.md` so each Short is scheduled for `18:30 IST` peak traffic.
* On Episode 1–2 of each series, open **YouTube Studio → Content → Shows** and toggle the auto-created series playlist into a native **Shorts Series** (serial mode).

---

### 9. Milestone Status & Verification Log

#### Milestone 1 — Repository Scaffold & Environment Setup: COMPLETED
- **Environment:** Windows 11 (PowerShell), Node.js v24.22.1, Python 3.12.10 (`.venv`), FFmpeg/FFprobe 7.1, `hyperframes` 0.9.70 (Chromium verified via `npx hyperframes browser ensure` and `npx hyperframes doctor`), `kinocut==2.0.1` (`kino doctor` passed).
- **Global Agent Skills:** Installed globally at `C:\Users\manis\.agents\skills\` (`hyperframes`, `svg-character-animation`, and companion skills; verified via `npx skills list -g`).

#### Milestone 2 — Database & State Management (`scripts/db_manager.py`): COMPLETED
- **Automated Compliance Tests:** `python -m unittest tests/test_db_manager.py -v` — **Ran 11 tests ... OK** (0 failures, 0 skips, executed in isolated temporary workspaces via `SUTRADHAR_ROOT`).
- **Live Database Verification:** `python scripts/db_manager.py --context` verified against initialized `episodes.db`: `active_series: null`, `next_episode_number_in_series: 1`, `next_global_episode_number: 1`, `upload_mode: "private_review"`, `allow_public_or_scheduled: false`, `completed_private_review_episodes: 0`.
- **Enforced Contracts:** Identical `narration_text`/`caption_text`, complete `series_bible_json` roadmap validation, strict `private_review` publishing lock (`PUBLISHED` and `scheduled_publish_at` rejected while locked), pillar rotation, bespoke asset uniqueness, and atomic `BEGIN IMMEDIATE` transactions with SQLite foreign keys and partial unique indexes.
- **Remaining Limitations (By Design, Deferred to Later Milestones):**
  - Physical `.svg`, BGM, and SFX file existence on disk is validated in Milestones 3–5 rather than `db_manager.py`.
  - Audio runtime bounds (`34–50s` hard, `36–46s` target) are enforced in Milestone 3 (`scripts/build_audio.py`).
  - Zero Milestone 2 requirements remain incomplete.

#### Milestone 3 — Audio Synthesis & Forced Alignment (`scripts/build_audio.py`, `scripts/audition_voices.py`): COMPLETED
- **Kokoro ONNX Model Integrity:** Quarantined corrupt 158.5MB model; downloaded authoritative 325,532,387-byte model (SHA-256: `7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5`). Verified `voices-v1.0.bin` (28,214,398 bytes, SHA-256: `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d`, 54 voices).
- **Hardened Resilient Download:** Added HTTP Range resume, size bounds (250MB/10MB), SHA-256 checksum pins, and structural `onnxruntime.InferenceSession` validation in `scripts/build_audio.py`.
- **Voice Auditions:** Auditioned 20 candidate voices and blends via `scripts/audition_voices.py`. Generated 20 WAVs in `build/audition/` and `audition_report.json`. Top performer: `bm_daniel` (155.7 WPM, 1.0000 match ratio). Held `tts.default_voice: "am_fenrir"` and `voice_provisional: true` unchanged in `config.yaml` for user signoff.
- **Forced Alignment Integration:** Added PyAV 19 compatibility shim for `faster-whisper 1.2.1`. Validated word-level alignment, monotonically increasing timestamps, and exact `build/manifest.js` emission.
- **Automated Tests:** `python -m unittest tests/test_audition_voices.py tests/test_build_audio.py -v` — **Ran 14 tests ... OK**.

#### Milestone 4 — Visual Composition Engine & Starter Assets: COMPLETED
- **Visual Composition Engine:** Authored `index.html`, `styles.css`, and `engine.js` complying with HyperFrames 0.9.70 contract. Built-in 2026 YouTube Shorts safe zones (130px top, 560px bottom, 120px right), 5 mood palettes (`golden_imperial`, `cosmic_indigo`, `crimson_wrath`, `mystic_slate`, `obsidian_amber`), 4 particle themes, and word-level karaoke subtitles.
- **HyperFrames Lint Cleanliness:** Verified `npx hyperframes lint` passes with 0 errors.
- **Procedural BGM & SFX:** Generated `cosmic_mystery.mp3`, `dramatic_mythology.mp3`, `epic_history.mp3` in `assets/bgm/`; generated `sub_hit.wav`, `whoosh_soft.wav`, `riser_tension.wav` in `assets/sfx/`.
- **Starter SVG Rigs:** Authored characters (`sutradhar_narrator.svg`, `ravana.svg`), backdrops (`deep_cosmos_nebula.svg`, `mount_kailash.svg`, `ancient_temple_ruins.svg`), and bespoke diagrams (`black_hole_anatomy.svg`, `gravitational_time_dilation_clock.svg`, `kailash_axis_alignments.svg`).

#### Milestone 5 — Snapshot QA, Render Pipeline & Sample Production: COMPLETED
- **Preview & QA Pipeline:** Implemented zero-argument `scripts/preview_frames.py` capturing 2x3 contact sheets (`qa_grid.jpg`, `qa_grid_safezones.jpg`) with visual safe-zone overlay guides.
- **Master Render & Audio Engineering:** Implemented zero-argument `scripts/render_and_qa.py`: HyperFrames CLI 1080x1920 render, FFmpeg dynamic sidechain ducking (`sidechaincompress`), KinoCut loudness normalization to `-14.0 LUFS`, and release checkpoint gate (`min_score=80.0`).
- **End-to-End Local Sample Videos (Verified in Isolated Environments):**
  - **Sample 1 (`sample_01_cosmos`):** 40.70s, 1080x1920 @ 30fps, H.264/AAC, -14.0 LUFS, KinoCut Score: **90.6 / 100**, archived with all QA contact sheets under `build/samples/sample_01_cosmos/`.
  - **Sample 2 (`sample_02_epics`):** 46.60s, 1080x1920 @ 30fps, H.264/AAC, -14.0 LUFS, KinoCut Score: **90.8 / 100**, archived with all QA contact sheets under `build/samples/sample_02_epics/`.
- **Automated Tests:** `python -m unittest tests/test_render_pipeline.py -v` — **Ran 4 tests ... OK**.

#### Milestone 6 — Offline YouTube Publisher & Safeguards (`scripts/publish_youtube.py`): COMPLETED (Offline Engine Verified; Live Publishing Pending User OAuth)
- **Zero-Argument Publisher CLI:** Implemented `scripts/publish_youtube.py` strictly enforcing `upload_mode: "private_review"`, `allow_public_or_scheduled: false`, and `containsSyntheticMedia=True`.
- **Isolated `.env.youtube` Credential Discovery:** Loads credentials without leaking into parent environment; falls back gracefully to offline dry-run stub mode when credentials are absent or `SUTRADHAR_OFFLINE_STUB=1`.
- **Strict Schema Compliance:** Emits `build/publish_result.json` validating against `db_manager.PublishResult` (`extra="forbid"`).
- **Cross-Module Contract Verification:** Successfully piped `publish_youtube.py` output directly into `db_manager.py --record-published` in isolated temp workspace.
- **Automated Tests:** `python -m unittest tests/test_publish_youtube.py -v` — **Ran 6 tests ... OK**.
- **Live Publishing Status:** Marked as **Pending User OAuth Setup & Voice/Sample Approval** per non-negotiable safety guardrails.

#### Milestone 7 — User Handoff Guide & Comprehensive Verification: COMPLETED
- **Operations Manual:** Created `docs/MANUAL_SETUP_AND_OPERATIONS.md` covering Google Cloud setup, OAuth token generation script, Studio Auto-Dubbing, voice/sample approval decisions, routine 6-step operations, and troubleshooting.
- **Repository-Wide Test Discovery:** `python -m unittest discover -s tests -v` — **Ran 35 tests ... OK** (35 passed, 0 failed, 0 skipped).
- **Database Immutability Re-Verification:** Root `episodes.db` confirmed identical to initial baseline (SHA-256: `729acce0cd4f31cc69ceca61470d331abcbce5e62b51728ab372cd28f83f8011`, size: 36,864 bytes).
