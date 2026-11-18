# IMPLEMENTATION_PLAN.md
## Zero-External-API Autonomous Multi-Niche YouTube Shorts Pipeline
### (Antigravity `/automation` + Series State Machine + Dual-Mode SVG Rigs + HyperFrames + KinoCut)

---

### 1. Executive Summary & Architectural Decisions

This plan specifies a **100% Antigravity-native, zero-recurring-external-cost daily YouTube Shorts system** engineered for high-retention serialized edutainment across **Sanatan Dharma, History, Science, Mysteries, and Viral Facts**, optimized for sustainable **YouTube Partner Program (YPP) monetization**.

#### Core Design Principles
1. **Zero External AI APIs ($0.00 External API Spend):**
   - **Google Antigravity** acts as the sole intelligence engine—handling niche rotation, multi-episode series planning, bilingual/English scriptwriting, SVG character/diagram rig authoring, and multimodal visual QA inspection. No external LLM, image, or video API keys are required.
2. **Strict Series-Completion State Machine:**
   - Every topic is planned as a self-contained **3-to-6-episode mini-series** stored in SQLite (`episodes.db`).
   - Once a series starts (`status = 'ACTIVE'`), the pipeline strictly completes every scheduled episode in sequence (`Part 1` through `Part N`) before allowing a new series or niche to begin—eliminating unfinished series and maximizing binge-watch subscriber conversion.
3. **Dual-Language Reach & RPM Optimization:**
   - Supports series-level language targeting (`hinglish_hybrid` for high-viral Indian cultural/historical arcs; `global_english` for high-RPM global science/mystery arcs) using free neural voices via `edge-tts`.
4. **Dual-Mode Modular SVG Rigs + Procedural Shaders (YPP Originality Compliant):**
   - Visuals are rendered deterministically in `1080x1920` (30fps) via **HyperFrames** (`@hyperframes/cli`) + **GSAP** using two reusable SVG modes:
     - **`character_drama`:** Skeletal character rigs + multi-plane backdrops (Sanatan Dharma, Historical figures).
     - **`explainer_diagram`:** Custom animated vector diagrams, cutaways, and timelines (Science, Space, Mysteries, Facts).
5. **Zero-Argument Pre-Whitelisted Commands:**
   - Antigravity background automations auto-deny unapproved shell commands or dynamic CLI arguments. All stateful handoffs occur via JSON files inside `build/`, allowing Antigravity to execute a fixed list of **6 static, pre-whitelisted commands** with zero argument variation.

---

### 2. Verified Zero-Cost Technology Stack

| Pipeline Layer | Tool / Service | Config / Version | License / Tier | Free Quota & Ceiling | External Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Orchestrator, Writer & Vision QA** | Google Antigravity IDE + `/automation` | Built-in frontier models | Developer's Antigravity plan | Runs locally via Antigravity Desktop / `agy` CLI | **$0 extra** |
| **Agent Skills** | `hyperframes` + `svg-character-animation` | `.agents/skills/` | Apache 2.0 / Open Skills | Local `SKILL.md` rules for vector rigging & GSAP | **$0.00** |
| **Multi-Lang Neural TTS & Timing** | `edge-tts` (Python) | `hi-IN-MadhurNeural`, `en-IN-PrabhatNeural`, `en-US-AndrewNeural` | LGPLv3 (Open Source) | Unlimited free neural TTS + native `WordBoundary` ticks (no key) | **$0.00** |
| **2.5D SVG & Shader Renderer** | `@hyperframes/cli` + GSAP | Node.js 22+ + Chromium + FFmpeg | Apache 2.0 | Unlimited local `1080x1920` 30fps renders; **no watermark** | **$0.00** |
| **Audio Mastering & Tech QA** | `kinocut` + `ffmpeg` | `kinocut==2.0.1` | Apache 2.0 / LGPL | Unlimited `-14.0 LUFS` loudness normalization, black-frame & silence checks | **$0.00** |
| **Series & Episode Database** | SQLite3 | `episodes.db` | Public Domain | Local relational DB enforcing strict series completion | **$0.00** |
| **YouTube Publishing** | `google-api-python-client` | YouTube Data API v3 | Google Cloud Free Quota | **10,000 units/day** free; `insert` (100) + `update` (50) = **150 units/day** | **$0.00** |

---

### 3. Repository Structure

```text
auto-edutainment-shorts/
├── .agents/
│   └── skills/                         # Installed HyperFrames & SVG character skills
├── assets/
│   ├── bgm/
│   │   ├── dramatic_mythology.mp3      # Royalty-free CC0 / YouTube Audio Library drone
│   │   ├── cosmic_mystery.mp3          # Royalty-free ambient synth/space bed
│   │   └── epic_history.mp3            # Royalty-free cinematic percussion/strings bed
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
│       └── diagrams/                   # Topic-specific animated SVG diagrams (viewBox="0 0 900 900")
│           └── black_hole_anatomy.svg  # Starter science diagram; Antigravity adds new ones per series
├── build/                              # Ephemeral per-episode artifacts (gitignored)
│   ├── audio/                          # Scene MP3s + concatenated narration_full.wav
│   ├── new_series_plan.json            # Written by Antigravity only when starting a new series
│   ├── episode_plan.json               # Written by Antigravity for today's episode
│   ├── manifest.js                     # Generated by build_audio.py (window.EPISODE_MANIFEST)
│   ├── raw_video.mp4                   # Rendered by HyperFrames CLI
│   ├── final_short.mp4                 # Loudness-mastered (-14 LUFS) release candidate
│   ├── qa_grid.jpg                     # 3x3 storyboard contact sheet inspected by Antigravity
│   └── publish_result.json             # Written by publish_youtube.py with live video_id
├── scripts/
│   ├── db_manager.py                   # Fixed CLI: --init | --context | --create-series | --record-published
│   ├── build_audio.py                  # Multi-voice edge-tts synthesis + word-synced manifest.js
│   ├── render_and_qa.py                # HyperFrames render + KinoCut -14 LUFS mastering + qa_grid.jpg
│   └── publish_youtube.py              # Headless OAuth2 upload + publishAt + containsSyntheticMedia
├── index.html                          # HyperFrames 1080x1920 master composition (dual visual mode)
├── styles.css                          # Safe-zone captions, series badge, SVG filters & mood themes
├── engine.js                           # GSAP skeletal acting, diagram stage reveals, parallax & particles
├── config.yaml                         # Niches, voice presets, BGM tracks, mood palettes & publish hour
├── episodes.db                         # SQLite series & episode ledger
├── MASTER_AUTOMATION_PROMPT.md         # Daily prompt executed by Antigravity /automation
├── IMPLEMENTATION_PLAN.md              # This architectural specification
├── package.json                        # @hyperframes/cli & gsap dependencies
├── requirements.txt                    # edge-tts, kinocut, google-api-python-client, pyyaml, pydantic
└── .env.example                        # YouTube OAuth2 client ID, client secret & refresh token
```

---

### 4. Series Management, Niche Rotation & Retention Strategy

#### 4.1 Series Lifecycle Rules (`episodes.db`)
To prevent abandoned storylines and maximize returning viewers:
1. **Active Series Lock:** Every series defines `total_planned_episodes` (between **3 and 6 episodes**) and stores its complete episode-by-episode roadmap in `series_bible_json`. While `status == 'ACTIVE'`, `db_manager.py --context` locks the daily run to the next episode (`completed_episodes + 1`).
2. **Automatic Completion Transition:** When the final episode (`completed_episodes + 1 == total_planned_episodes`) is published, `db_manager.py --record-published` automatically marks the series `COMPLETED`.
3. **Smart Niche & Language Rotation:** When no `ACTIVE` series exists, Antigravity inspects `completed_series_history` and selects a **different niche** than the immediately preceding series, choosing the optimal `language_mode`:
   - **`hinglish_hybrid`:** Hindi voice (`hi-IN-MadhurNeural` or `hi-IN-SwaraNeural`) + English safe-zone captions (ideal for *Sanatan Dharma*, *Indian History*, *Cultural Mysteries*).
   - **`global_english`:** English voice (`en-IN-PrabhatNeural` or `en-US-AndrewNeural`) + English safe-zone captions (ideal for *Space*, *Science*, *Global Mysteries*, *World Facts* to maximize international Tier-1 RPM).
   - **`pure_hindi`:** Hindi voice + Devanagari Hindi captions (for deeply traditional *Puranic Katha* arcs).

#### 4.2 Viral YouTube Shorts Pacing & Monetization Blueprint
- **8 Brisk Scenes (~5.5–6.5s each = ~48–52s total):** Rapid visual progression every ~6 seconds eliminates mid-video drop-offs.
- **0–3 Second Pattern-Interrupt Hook (Scene 1):** Opens immediately with a shocking paradox, dramatic visual close-up, or high-stakes question—never a slow channel greeting.
- **Series Progress Badge:** A clean, non-intrusive pill badge at the top safe zone (`PART 2 OF 4 • COSMIC MYSTERIES`) anchors viewer context and encourages profile binge-watching.
- **Open-Loop Ending (Scene 8):** Delivers a satisfying micro-payoff for today's episode while planting an urgent cliffhanger for the next part (or teasing the upcoming finale), boosting subscriber conversion.
- **YPP Compliance:** Every episode combines original scripting, custom SVG rig animation/diagrams, original TTS narration, and `containsSyntheticMedia: True` metadata disclosure.

---

### 5. Dual-Mode Modular SVG Rig & Shader Contract

All `.svg` files in `assets/svg/` follow strict DOM layer contracts so `engine.js` animates any existing or newly authored SVG automatically.

#### 5.1 Mode A: Character Drama (`visual_mode: "character_drama"`)
- **Character Rigs (`assets/svg/characters/*.svg`, `viewBox="0 0 800 1200"`):**
  - Required `<g>` IDs (z-order back-to-front): `#char_aura`, `#char_body` (`data-pivot-x/y`), `#arm_left` (`data-pivot-x/y`), `#char_head` (`data-pivot-x/y`), `#eyes_open`, `#eyes_closed`, `#brows`, `#arm_right` (`data-pivot-x/y`), and nested `#prop_weapon`.
  - Driven by `emotion` (`calm`, `wrath`, `shock`, `smirk`, `meditating`) and `action_gesture` (`idle_breathe`, `raise_weapon`, `point_accuse`, `bless_hand`, `tremble`).
- **Backdrop Rigs (`assets/svg/backdrops/*.svg`, `viewBox="0 0 1080 1920"`):**
  - Required depth layers: `#bg_far_sky`, `#bg_mid_architecture`, `#bg_fg_pillars` styled via CSS variables (`var(--sky-top)`, `var(--sky-bottom)`, `var(--accent-glow)`, `var(--shadow-tint)`).

#### 5.2 Mode B: Explainer & Science Diagrams (`visual_mode: "explainer_diagram"`)
- **Diagram Rigs (`assets/svg/diagrams/*.svg`, `viewBox="0 0 900 900"`):**
  - Used for Science, Space, Historical timelines, and Mystery breakdowns.
  - Required `<g>` IDs:
    - `#diagram_base`: Core structure, planet, temple cutaway, or timeline axis (always visible).
    - `#stage_1`, `#stage_2`, `#stage_3`, `#stage_4`: Progressive visual layers, force vectors, orbit paths, or cutaway callouts that GSAP reveals and highlights sequentially based on the scene's `active_diagram_stage` (`1..4`)!
    - `#highlight_pulse`: Glowing focal indicator styled with `#divine-bloom` or `#cosmic-glow`.

#### 5.3 Procedural Shaders, Particle Themes & Safe-Zone Captions
- **Inline SVG `<filter>` Graphs:** `#divine-bloom` (golden/cyan luminescence), `#fire-haze` (`feTurbulence` heat shimmer), and `#parchment-grain` (organic surface texture overlay).
- **Frame-Locked Canvas Particles (`particle_theme`):** `<canvas id="fx-canvas">` driven by GSAP's `onUpdate` progress renders `"golden_embers"` (mythology/history), `"starfield_warp"` (space/science), `"quantum_nodes"` (physics/tech), or `"mystic_mist"` (mysteries).
- **YouTube Shorts Safe-Zone Layout:**
  - Top series badge: `top: 150px; left: 85px;` (below YouTube's top status/search bar).
  - Subtitles: `bottom: 430px; left: 85px; right: 165px;` (clear of bottom title/channel overlay and right-hand Like/Comment/Share icons) with active-word `#FFD700` highlight.

---

### 6. Database & JSON Schemas

#### 6.1 SQLite Schema (`episodes.db`)
```sql
CREATE TABLE IF NOT EXISTS series (
    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_title TEXT NOT NULL,
    niche TEXT NOT NULL,
    language_mode TEXT NOT NULL,         -- 'hinglish_hybrid' | 'global_english' | 'pure_hindi'
    tts_voice TEXT NOT NULL,
    bgm_track TEXT NOT NULL,
    total_planned_episodes INTEGER NOT NULL,
    completed_episodes INTEGER NOT NULL DEFAULT 0,
    series_bible_json TEXT NOT NULL,     -- Full planned episode-by-episode arc outline
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE' | 'COMPLETED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS episodes (
    episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL,
    episode_number_in_series INTEGER NOT NULL,
    global_episode_number INTEGER NOT NULL UNIQUE,
    youtube_title TEXT NOT NULL,
    summary TEXT NOT NULL,
    script_json TEXT NOT NULL,
    youtube_video_id TEXT,
    scheduled_publish_at TEXT,
    status TEXT NOT NULL,                -- 'PUBLISHED' | 'FAILED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (series_id) REFERENCES series(series_id)
);
```

#### 6.2 `build/episode_plan.json` Schema
```json
{
  "series_id": 1,
  "series_title": "Secrets of the Cosmos",
  "niche": "Science & Space",
  "episode_number_in_series": 2,
  "total_planned_episodes": 4,
  "global_episode_number": 2,
  "language_mode": "global_english",
  "tts_voice": "en-IN-PrabhatNeural",
  "bgm_track": "cosmic_mystery.mp3",
  "youtube_title": "What Happens The Second You Fall Into a Black Hole? (Part 2/4) #Shorts",
  "youtube_description": "Part 2 of 4: Secrets of the Cosmos. Crossing the Event Horizon breaks time itself. Subscribe for Part 3 tomorrow! #Science #Space #Shorts",
  "summary": "Explains time dilation and spaghettification at a black hole's event horizon.",
  "scenes": [
    {
      "scene_index": 1,
      "narration_text": "If you fell toward a black hole right now, the universe outside would age millions of years in seconds.",
      "caption_text": "If you fell into a black hole, the outside universe would age millions of years in seconds.",
      "visual_mode": "explainer_diagram",
      "backdrop_rig": "deep_cosmos_nebula",
      "diagram_rig": "black_hole_anatomy",
      "active_diagram_stage": 1,
      "primary_character": null,
      "secondary_character": null,
      "emotion": "calm",
      "action_gesture": "idle_breathe",
      "mood_palette": "cosmic_indigo",
      "particle_theme": "starfield_warp",
      "camera_motion": "dramatic_zoom"
    }
  ]
}
```

---

### 7. Specifications for the Four Pre-Whitelisted Scripts (`scripts/`)

All 6 command invocations take **zero dynamic arguments**, ensuring 100% compatibility with Antigravity's `agent_permissions` sandbox:

1. **`python scripts/db_manager.py --init`**
   - Creates `episodes.db` with `series` and `episodes` tables.
2. **`python scripts/db_manager.py --context`**
   - Prints JSON containing:
     - `active_series`: Full record + `series_bible_json` if an `ACTIVE` series exists, or `null` if a new series must be created.
     - `next_episode_number_in_series` & `next_global_episode_number`.
     - `completed_series_history`: Last 20 completed series (`series_title`, `niche`, `language_mode`) so Antigravity rotates niches and avoids duplicate topics.
     - `available_rigs`: Live file lists of `assets/svg/characters/`, `assets/svg/backdrops/`, and `assets/svg/diagrams/`.
3. **`python scripts/db_manager.py --create-series`**
   - Reads `build/new_series_plan.json` and inserts a new `ACTIVE` row into `series` (3–6 planned episodes).
4. **`python scripts/build_audio.py`**
   - Reads `build/episode_plan.json` (`tts_voice`, `narration_text`, `caption_text`).
   - Synthesizes `build/audio/scene_{1..8}.mp3` via `edge-tts` while capturing `WordBoundary` ticks (`offset / 10_000_000` seconds).
   - Measures exact scene durations via `ffprobe`, concatenates `build/audio/narration_full.wav`, maps caption chunks to spoken word timings, and writes `build/manifest.js` (`window.EPISODE_MANIFEST = {...};`).
5. **`python scripts/render_and_qa.py`**
   - Runs `npx hyperframes lint`, `npx hyperframes check --json`, and `npx hyperframes render --quality looks --output build/raw_video.mp4`.
   - Mixes the episode's selected `bgm_track` from `assets/bgm/` at `-23 dB` under `narration_full.wav` and normalizes final output to **`-14.0 LUFS`** via `kinocut.Client().normalize_audio(..., target_lufs=-14.0)` into `build/final_short.mp4`.
   - Runs `kino.quality_check("build/final_short.mp4")` and `kino.release_checkpoint("build/final_short.mp4", min_score=50)` (exiting non-zero on black/frozen frames or silence gaps), and renders `build/qa_grid.jpg` (3x3 contact sheet).
6. **`python scripts/publish_youtube.py` & `python scripts/db_manager.py --record-published`**
   - `publish_youtube.py` uploads `build/final_short.mp4` via OAuth2 refresh token, schedules `publishAt` for the next `18:30 IST` (`13:00 UTC`) peak slot, patches `containsSyntheticMedia: True` via `videos().update(part="status", ...)` with exponential backoff, and saves `build/publish_result.json`.
   - `db_manager.py --record-published` reads `build/episode_plan.json` and `build/publish_result.json`, inserts the `PUBLISHED` episode into `episodes`, increments `completed_episodes`, and flips `series.status = 'COMPLETED'` when the final episode of the series is published.

---

### 8. Setup & Antigravity `/automation` Runbook

1. **Install Dependencies & Skills:**
   ```bash
   npm install
   npx hyperframes browser ensure
   npx skills add heygen-com/hyperframes
   npx skills add het8802/OpenNolan --skill svg-character-animation
   pip install -r requirements.txt
   python scripts/db_manager.py --init
   ```
2. **Configure YouTube OAuth2 (`.env`):**
   - Enable **YouTube Data API v3** in Google Cloud Console, publish the OAuth Consent Screen to **Production** (prevents 7-day token expiration), and save `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN` in `.env`.
3. **Interactive Whitelist Calibration Run:**
   - Open the project in **Google Antigravity IDE**, run one interactive test pass using `MASTER_AUTOMATION_PROMPT.md` (with `publish_youtube.py` in `--dry-run` or test mode), and approve all 6 exact commands in `agent_permissions`.
4. **Enable Daily `/automation` Schedule:**
   - Configure `/automation` to run **Daily at 16:30 IST** with `MASTER_AUTOMATION_PROMPT.md` so each Short is planned, animated, visually verified, and scheduled for `18:30 IST` peak traffic.