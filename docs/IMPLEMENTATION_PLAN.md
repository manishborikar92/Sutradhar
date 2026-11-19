# IMPLEMENTATION_PLAN.md
## Zero-External-API Autonomous Serialized YouTube Shorts Pipeline
### (Antigravity `/automation` + Series State Machine + Dual-Mode SVG Rigs + Kokoro-82M + HyperFrames + KinoCut 2.0)

---

### 1. Executive Summary & Architectural Decisions

This plan specifies a **100% Antigravity-native, zero-recurring-external-cost daily YouTube Shorts system** engineered for high-retention serialized edutainment, native **YouTube Shorts Series** compatibility, and sustainable **YouTube Partner Program (YPP) monetization**.

#### Core Design Principles
1. **Zero External AI APIs ($0.00 External API Spend):**
   - **Google Antigravity** acts as the sole intelligence engine—handling pillar rotation, multi-episode series planning, scriptwriting, bespoke SVG character/diagram rig authoring, and multimodal visual QA inspection. No external LLM, image, TTS, or video API keys are required.
2. **Single-Language Channel Cohesion + Native YouTube Auto-Dubbing:**
   - To protect seed-audience **Viewed vs. Swiped Away** metrics, each channel instance locks to **one primary language** (`global_english` by default for Tier-1 RPM, or `hindi_india` for a dedicated Indian-language channel) and rotates across **3 thematically cohesive pillars** (e.g., *Ancient Epics & Lore*, *Hidden History*, *Cosmic & Scientific Paradoxes*).
   - Cross-language expansion is delegated to **YouTube's free native Auto-Dubbing with Expressive Speech** (27 languages including English ↔ Hindi, enabled by setting `defaultAudioLanguage` on upload) rather than mixing languages on the same feed.
3. **Strict Series-Completion State Machine + YouTube Shorts Series Sync:**
   - Every topic is planned as a self-contained **3-to-6-episode mini-series** stored in SQLite (`episodes.db`).
   - Once a series starts (`status = 'ACTIVE'`), the pipeline strictly completes `Part 1` through `Part N` in sequence while automatically grouping episodes into a dedicated YouTube playlist (`youtube_playlist_id`) ready for native **YouTube Shorts Series** sequential playback.
4. **Commercial-Safe Local Neural TTS + Deterministic Word Alignment:**
   - Uses **Kokoro-82M** (`kokoro-onnx` / `kokoro`, Apache-2.0, fast on standard laptop CPUs) as the primary voiceover engine, paired with **`faster-whisper` (`tiny`/`base` `int8` CPU)** for 100% deterministic word-level caption timestamps.
   - Retains `edge-tts` strictly as an optional secondary Hindi voice engine (explicitly noting its commercial ToS gray zone and avoiding cross-language word-karaoke mismatches).
5. **YPP Originality-First Visual Pipeline (Pre-Render Snapshot Gate):**
   - Visuals render deterministically in `1080x1920` (30fps) via **HyperFrames** (`@hyperframes/cli`) + **GSAP** + HyperFrames Registry motion blocks, combining modular SVG character rigs, bespoke per-episode diagrams/props, sidechain-ducked BGM, and transition SFX to stay clear of YouTube's **"Inauthentic Content"** policy.
   - Runs a fast **pre-render snapshot QA gate** (`preview_frames.py`) before full `--quality high` rendering to eliminate wasted CPU render cycles during self-healing retries.
6. **Zero-Argument Pre-Whitelisted Commands:**
   - All stateful handoffs occur via JSON files inside `build/`, allowing unattended Antigravity `/automation` runs to execute a fixed list of **7 static, pre-whitelisted commands** with zero dynamic CLI arguments.

---

### 2. Verified Zero-Cost Technology Stack

| Pipeline Layer | Tool / Service | Config / Version | License / Tier | Free Quota & Ceiling | External Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Orchestrator, Writer & Vision QA** | Google Antigravity IDE + `/automation` | Built-in frontier models | Developer's Antigravity plan | Runs locally via Antigravity Desktop / CLI | **$0 extra** |
| **Agent Skills** | `hyperframes` + `svg-character-animation` | `.agents/skills/` | Apache 2.0 / Open Skills | Local `SKILL.md` rules + HyperFrames registry blocks | **$0.00** |
| **Primary Neural TTS (Offline)** | `kokoro-onnx` (Kokoro-82M v1.0) | `am_michael`, `bm_george`, `af_heart` (EN); `hm_omega`, `hf_alpha` (HI) | **Apache 2.0** (Commercial-safe) | Unlimited local CPU synthesis; zero API keys | **$0.00** |
| **Optional Secondary TTS (Hindi)** | `edge-tts` (Python, fallback only) | `hi-IN-MadhurNeural`, `hi-IN-SwaraNeural` (`boundary="WordBoundary"`) | LGPLv3 client *(Consumer endpoint; review MS ToS before commercial scaling)* | Unofficial free endpoint (use only if Kokoro Hindi prosody is insufficient) | **$0.00** |
| **Word-Level Caption Alignment** | `faster-whisper` (CTranslate2) | `base` / `tiny` (`compute_type="int8"`, CPU) | MIT | Unlimited offline forced word timestamps (~2–4s per Short on CPU) | **$0.00** |
| **2.5D SVG & Shader Renderer** | `@hyperframes/cli` + GSAP | Node.js 22+ + Chromium + FFmpeg | Apache 2.0 | Unlimited local `1080x1920` 30fps renders; **no watermark** | **$0.00** |
| **Audio Mastering & Tech QA** | `kinocut` + `ffmpeg` | `kinocut==2.0.1` | Apache 2.0 / LGPL | Unlimited `-14.0 LUFS` mastering, sidechain ducking, quality gate (`>=80`) | **$0.00** |
| **Series & Episode Database** | SQLite3 | `episodes.db` | Public Domain | Local relational DB enforcing strict series completion & playlist sync | **$0.00** |
| **YouTube Publishing & Series** | `google-api-python-client` | YouTube Data API v3 | Google Cloud Free Quota | **100 `videos.insert` calls/day** (Uploads bucket) + **10,000 units/day** other (`playlists.insert`: 50, `playlistItems.insert`: 50) | **$0.00** |

---

### 3. Repository Structure

```text
auto-edutainment-shorts/
├── .agents/
│   └── skills/                         # Installed HyperFrames & SVG character skills
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
│       │   ├── ravana.svg
│       │   ├── shani_dev.svg
│       │   ├── narad_muni.svg
│       │   ├── lord_shiva.svg
│       │   └── scholar_narrator.svg
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
│   ├── build_audio.py                  # Kokoro-82M (or edge-tts) synthesis + faster-whisper word timestamps
│   ├── preview_frames.py               # HyperFrames lint + check --json + mid-scene snapshots -> qa_grid.jpg
│   ├── render_and_qa.py                # HyperFrames --quality high + FFmpeg sidechain/SFX + KinoCut QA (>=80)
│   └── publish_youtube.py              # Single-call videos.insert + playlist/Shorts Series sync
├── index.html                          # HyperFrames 1080x1920 master composition (triple visual mode)
├── styles.css                          # 2026 Safe-zone captions, series badge, SVG filters & mood themes
├── engine.js                           # GSAP skeletal acting, diagram reveals, kinetic stats, parallax & FX
├── config.yaml                         # Channel language lock, 3 pillars, voices, BGM/SFX, upload_mode, publish hour
├── episodes.db                         # SQLite series & episode ledger
├── MASTER_AUTOMATION_PROMPT.md         # Daily prompt executed by Antigravity /automation
├── IMPLEMENTATION_PLAN.md              # This architectural specification
├── package.json                        # @hyperframes/cli & gsap dependencies
├── requirements.txt                    # kokoro-onnx, faster-whisper, edge-tts, kinocut==2.0.1, google-api-python-client, pyyaml, pydantic, pillow
└── .env.youtube.example                # Dedicated YouTube OAuth2 env file (isolated from HyperFrames .env)

```

---

### 4. Series Management, Channel Cohesion & 2026 Retention Blueprint

#### 4.1 Channel Language Lock & Cohesive Pillar Rotation (`config.yaml` + `episodes.db`)

1. **Strict Single-Language Channel Policy:**
* Configure `channel_language_mode` once in `config.yaml`:
* **`global_english` (Recommended Default for RPM + Global Scale):** English narration (`kokoro-onnx` `am_michael` / `bm_george`) + word-synced English captions, with `defaultAudioLanguage: "en"` so **YouTube Auto-Dubbing** automatically generates expressive Hindi, Spanish, Portuguese, and 20+ other language tracks without fragmenting the channel feed.
* **`hindi_india` (For a Dedicated Indian Channel):** Hindi narration (`kokoro-onnx` `hm_omega` or `edge-tts` `hi-IN-MadhurNeural`) + synchronized Devanagari or Romanized Hinglish captions (`defaultAudioLanguage: "hi"`). *Never flip spoken languages between episodes on the same channel.*
* *Caption Sync Rule:* Word-by-word `#FFD700` active-word highlighting is used **only when audio and captions share the same language**. If bilingual translated captions are ever enabled explicitly, `engine.js` automatically switches to **clause-level subtitle blocks** to avoid SOV/SVO timing mismatches.




2. **Cohesive 3-Pillar Rotation:**
* Rather than jarring jumps across 5 unrelated topics, rotate across **3 tightly unified thematic pillars** under one editorial umbrella (e.g., *Ancient Epics & Lore*, *Hidden History*, *Cosmic & Scientific Paradoxes*), ensuring the same curiosity-driven viewer profile watches consecutive series.


3. **Active Series Lock & Automatic Completion:**
* Every series plans **3 to 6 episodes** (`total_planned_episodes`) stored in `series_bible_json`. While `status == 'ACTIVE'`, `db_manager.py --context` locks the daily run to `completed_episodes + 1`. Upon publishing the final episode, `db_manager.py --record-published` flips `series.status = 'COMPLETED'`.



#### 4.2 Viral 2026 YouTube Shorts Pacing & YPP Compliance

* **36–46 Seconds Total Across 7–8 Dynamic Scenes (~4.5–6.0s each):** Tuned to the 2026 Shorts retention sweet spot where completion and rewatch rates peak (avoiding bloated 55s+ pacing that kills Average Percentage Viewed).
* **0–2.5 Second Visual + Verbal Pattern Interrupt (Scene 1):** Opens immediately mid-conflict, mid-paradox, or with an arresting animated diagram reveal—zero channel intros or greetings.
* **Standalone Comprehension + Serial Hook (YouTube Shorts Series Best Practice):** Every episode must make immediate sense to a cold viewer discovering Part 3 in the Shorts feed, while delivering a crisp micro-payoff and planting an open-loop tease for the next episode (or finale).
* **YPP "Inauthentic Content" & Originality Safeguards:**
* **Mandatory Per-Episode Bespoke Asset:** Every episode must introduce at least **1 newly authored, topic-specific SVG asset** (diagram, cutaway, historical map, artifact, or backdrop variant) so no two episodes feel like mass-produced templates.
* **Visual Mode Variety:** Mix `character_drama`, `explainer_diagram`, and `kinetic_callout` (data/timeline/comparison cards) across scenes within an episode, plus HyperFrames registry motion transitions and subtle SFX stingers.
* **Disclosure & Metadata:** Every upload declares `containsSyntheticMedia: True`, `selfDeclaredMadeForKids: False`, and accurate `defaultAudioLanguage`.



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

* High-contrast animated typography / counter / comparison card layered over a mood-tinted backdrop + particles (ideal for shocking numbers, dates, scale comparisons, or pattern-interrupt hooks without repetitive character framing). Uses optional `callout_headline` and `callout_subtext` fields in `episode_plan.json`.

#### 5.4 Procedural Shaders, Particles & Verified 2026 Safe-Zone Layout

* **Inline SVG `<filter>` Graphs:** `#divine-bloom`, `#fire-haze` (`feTurbulence`), and `#parchment-grain`.
* **Frame-Locked Canvas Particles (`particle_theme`):** `<canvas id="fx-canvas">` driven by GSAP `onUpdate` progress renders `"golden_embers"`, `"starfield_warp"`, `"quantum_nodes"`, or `"mystic_mist"`.
* **Verified 2026 YouTube Shorts Safe-Zone Layout (`1080 × 1920`):**
* Keep clear: **Top `288px**`, **Bottom `520–672px**` (clears channel handle, title, Subscribe, and the new Shorts Series *"Watch Series"* pill), **Right `192px**` (clears Like/Comment/Share/Remix stack), **Left `48px**`.
* **Top Series Badge:** `top: 300px; left: 64px; max-width: 816px;` (`PART 2 OF 4 • COSMIC PARADOXES`).
* **Primary Visual Focal Area (Characters / Diagrams):** Vertically centered between `y: 380px` and `y: 1220px`, horizontally constrained within `x: 64px..880px`.
* **Subtitles:** `bottom: 560px; left: 64px; right: 200px;` with high-contrast stroke/pill backing and `#FFD700` active-word highlight (for same-language captions).



---

### 6. Database & JSON Schemas

#### 6.1 SQLite Schema (`episodes.db`)

```sql
CREATE TABLE IF NOT EXISTS series (
    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_title TEXT NOT NULL,
    pillar TEXT NOT NULL,
    language_mode TEXT NOT NULL,          -- Locked to channel config: 'global_english' | 'hindi_india'
    tts_engine TEXT NOT NULL,             -- 'kokoro' | 'edge_tts'
    tts_voice TEXT NOT NULL,
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
  "language_mode": "global_english",
  "audio_language_code": "en",
  "tts_engine": "kokoro",
  "tts_voice": "am_michael",
  "bgm_track": "cosmic_mystery.mp3",
  "bespoke_asset_path": "assets/svg/diagrams/spaghettification_tidal_gradient.svg",
  "youtube_title": "What Happens The Second You Cross a Black Hole? (Part 2/4) #Shorts",
  "youtube_description": "Part 2 of 4: Secrets of the Event Horizon. At the horizon, gravity stretches time and matter beyond recognition. Watch the full series on our channel! #Science #Space #Shorts",
  "summary": "Explains gravitational time dilation and tidal spaghettification at a black hole's event horizon.",
  "scenes": [
    {
      "scene_index": 1,
      "narration_text": "Cross this invisible boundary, and the universe outside ages millions of years in one heartbeat.",
      "caption_text": "Cross this invisible boundary, and the universe outside ages millions of years in one heartbeat.",
      "caption_sync_mode": "word_karaoke",
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

---

### 7. Specifications for the 7 Pre-Whitelisted Static Scripts (`scripts/`)

All 7 runtime commands take **zero dynamic arguments**, ensuring full compatibility with unattended Antigravity `/automation` `agent_permissions`:

1. **`python scripts/db_manager.py --context`** *(plus one-time setup `python scripts/db_manager.py --init`)*
* Outputs JSON containing: `channel_config` (`language_mode`, `pillars`, `upload_mode`), `active_series` (including `youtube_playlist_id` and `series_bible_json`), `next_episode_number_in_series`, `next_global_episode_number`, `completed_series_history` (last 20), and `available_rigs` across `characters/`, `backdrops/`, `diagrams/`, and `sfx/`.


2. **`python scripts/db_manager.py --create-series`**
* Reads `build/new_series_plan.json`, validates schema via Pydantic (3–6 episodes, locked channel language), and inserts a new `ACTIVE` row into `series`.


3. **`python scripts/build_audio.py`**
* Reads `build/episode_plan.json`.
* Synthesizes `build/audio/scene_{1..N}.wav` via **`kokoro-onnx`** (or optional `edge-tts` if configured for Hindi), normalizes per-scene silence trims, measures exact durations via `ffprobe`, and concatenates `build/audio/narration_full.wav`.
* Runs **`faster-whisper` (`base`, `int8`, CPU, `word_timestamps=True`)** on each scene WAV to generate 100% deterministic word-level timestamps mapped to `caption_text` (or clause timings if `caption_sync_mode == "clause_block"`), and writes `build/manifest.js` (`window.EPISODE_MANIFEST = {...};`).


4. **`python scripts/preview_frames.py`** *(Fast Pre-Render Visual QA Gate)*
* Runs `npx hyperframes lint` and `npx hyperframes check --json` (failing fast on HTML/layout/contrast/static-sweep errors).
* Computes midpoint timestamps for every scene in `build/manifest.js` and runs `npx hyperframes snapshot --at <midpoints>` (~10 seconds total without full MP4 encoding).
* Stitches the snapshots (with optional safe-zone guide overlay on a debug copy) into `build/qa_grid.jpg` for Antigravity multimodal visual inspection.


5. **`python scripts/render_and_qa.py`**
* Runs `npx hyperframes render --quality high --output build/raw_video.mp4`.
* Mixes scene transition SFX (`assets/sfx/`) at exact scene boundaries and applies **FFmpeg `sidechaincompress**` dynamic ducking to `bgm_track` under `narration_full.wav`.
* Normalizes final audio to **`-14.0 LUFS`** via `kinocut.Client().normalize_audio(..., target_lufs=-14.0)` into `build/final_short.mp4`.
* Runs `kino.quality_check("build/final_short.mp4")` and `kino.release_checkpoint("build/final_short.mp4", min_score=80)` (strict production threshold—exiting non-zero on black/frozen frames, silence gaps, or loudness faults), verifies `ffprobe` duration matches `manifest.js`, and writes decoded verification sheet `build/final_qa_grid.jpg`.


6. **`python scripts/publish_youtube.py`**
* Loads OAuth2 credentials from **`.env.youtube`** (kept separate from `.env` so HyperFrames CLI emits zero unrecognized-key warnings).
* Executes a **single `videos().insert(part="snippet,status", ...)**` call setting:
* `snippet`: `title`, `description`, `categoryId: "27"` (Education), `defaultAudioLanguage`, `defaultLanguage`.
* `status`: `privacyStatus: "private"`, `publishAt` (next `18:30 IST` / `13:00 UTC` if `upload_mode == "scheduled"`, omitted if `upload_mode == "private_review"`), `selfDeclaredMadeForKids: False`, and **`containsSyntheticMedia: True`** natively on insert.


* If `series.youtube_playlist_id` is null (Episode 1), calls `playlists().insert` to create a dedicated series playlist; then calls `playlistItems().insert` to append the uploaded `video_id` in exact episode order (ready for 1-click conversion into a native **YouTube Shorts Series** in Studio).
* Writes `video_id`, `playlist_id`, `upload_status`, and `scheduled_publish_at` to `build/publish_result.json`.


7. **`python scripts/db_manager.py --record-published`**
* Reads `build/episode_plan.json` and `build/publish_result.json`, persists `youtube_playlist_id` (if newly created), inserts the episode row into `episodes`, increments `completed_episodes`, and flips `series.status = 'COMPLETED'` when `completed_episodes == total_planned_episodes`.



---

### 8. Setup & Antigravity `/automation` Runbook

1. **Install Dependencies, Models & Skills:**
```bash
npm install
npx hyperframes browser ensure
npx skills add heygen-com/hyperframes
npx skills add het8802/OpenNolan --skill svg-character-animation
pip install -r requirements.txt
python scripts/db_manager.py --init

```


*(First run of `build_audio.py` caches Kokoro-82M ONNX weights and `faster-whisper` `base` int8 weights locally for offline execution.)*
2. **Configure YouTube OAuth2 (`.env.youtube`) & Channel Studio Settings:**
* Enable **YouTube Data API v3** in Google Cloud Console, publish the OAuth Consent Screen to **Production** (prevents 7-day refresh-token expiry; note that as of **Nov 2, 2026**, Google lifted the private-viewing lock on uploads from unverified API projects), and store `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN` in `.env.youtube`.
* In **YouTube Studio → Settings → Channel → Advanced Settings**, enable **Automatic Dubbing** (with Expressive Speech) so every `global_english` Short automatically reaches Hindi and global audiences.


3. **Calibration Pass (`upload_mode: "private_review"`):**
* Set `upload_mode: "private_review"` in `config.yaml` for the first 3–5 episodes (avoiding the need to delete/re-upload Shorts, which risks spam flags).
* Open the workspace in **Google Antigravity IDE**, set project permissions to `Auto` (or add explicit project allow-rules in `agent_permissions` for the 7 exact commands), and run one interactive pass of `MASTER_AUTOMATION_PROMPT.md`.
* Verify the uploaded private Short in the mobile YouTube app (confirming safe zones, audio punch, and Auto-Dubbing track quality).


4. **Enable Daily `/automation` Schedule:**
* Switch `upload_mode: "scheduled"` in `config.yaml`.
* Configure `/automation` to run **Daily at 16:30 IST** with `MASTER_AUTOMATION_PROMPT.md`, scheduling finished Shorts for `18:30 IST` peak traffic.
* Once a series reaches Episode 1–2, open **YouTube Studio → Content → Shows** and toggle the auto-created series playlist into a native **Shorts Series** (serial mode) for sequential playback and TV/mobile discovery.