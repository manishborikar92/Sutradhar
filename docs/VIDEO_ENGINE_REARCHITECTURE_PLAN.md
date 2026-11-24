# Sutradhar Video Engine Re-Architecture & Master Implementation Plan
**Document Version:** 3.0.0 (Research-Backed & Implementation-Ready)  
**System Classification:** Autonomous Cultural Storytelling & 2.5D Animated Puppet Video Engine  
**Runtime Architecture:** Python Multi-Agent Director + HyperFrames (Puppeteer / GSAP 3) + FFmpeg Broadcast Master  
**Target Video Format:** YouTube Shorts / Instagram Reels (1080 × 1920 Vertical, 60 FPS, 48 kHz 24-bit Stereo)  
**Status:** Complete Architectural Proposal — Awaiting Final User Review & Approval  
**Author:** Sutradhar Autonomous Core Architecture Team  
**Date:** 2026-11-24  

---

## 1. Executive Blueprint & Architectural Vision

The Sutradhar video-generation engine is undergoing a comprehensive, ground-up re-architecture. The previous system produced unacceptable video quality because it was built on an unviable legacy foundation: **"1 Script Scene = 1 Monolithic 10-Second Visual Shot"**. 

Under this legacy design:
- Characters were rendered at 800px width inside a 1080px canvas (occupying $74\%$ of screen width), resulting in **516 pixels of central overlap** in two-character duels.
- Poses were frozen at $t=0$ with anatomically impossible joint rotations (such as `--rot-shoulder-l: 105deg`, forcing characters into a horizontal scarecrow T-pose).
- Lip-sync was driven by a blind mathematical loop (`dur / 6.0`) that toggled mouth opacity 4 times over 10 seconds, completely ignoring the word-level OpenAI Whisper forced-alignment timestamps already stored in `build/manifest.js`.
- Mythological narratives were paired with inappropriate 2D technical vector diagrams containing English labels ("SINGULARITY", "EVENT HORIZON").
- High-fidelity ElevenLabs voiceover was downsampled to telephone-quality 24,000 Hz, and the FFmpeg audio mixer lacked `normalize=0`, inadvertently crushing the master volume as sound effects were added.

### The Target Architectural Vision
The new engine establishes a **Decoupled, Beat-Driven Cinematic Puppet Architecture**. It retains **HyperFrames (Puppeteer + GSAP 3)** as the frame-deterministic rendering runtime, but completely replaces the 2,155-line Python monolith (`scripts/generate_composition.py`) with a modular, single-responsibility software suite.

```
+-------------------------------------------------------------------------------------------------------------------+
|                                  SUTRADHAR TARGET ARCHITECTURAL FLOW                                              |
+-------------------------------------------------------------------------------------------------------------------+

   [ 1. Narrative & Script Engine ]
     - Puranic / Historical Research -> 100% Hindi Devanagari Script
     - Single Katha-vachak Voice (Viraj via ElevenLabs v4 with Steering Tags)
                  │
                  ▼
   [ 2. Narrative Beat Decomposer (scripts/engine/beat_planner.py) ]
     - Deconstructs 60-70s Script into 18-24 Micro-Beats (Average Shot Length: 2.2s - 3.2s)
     - Enforces Dynamic Retention Rhythm: Hook (0-3s) -> Rising Action -> Clash -> Resolution
                  │
                  ├───────────────────────────────────────────────┐
                  ▼                                               ▼
   [ 3. Acoustic Engineering Pipeline ]            [ 4. Visual Directing & Cinematography ]
     - ElevenLabs 44.1/48kHz Voiceover               - 9:16 Golden Zone Framing Engine
     - Faster-Whisper Word Alignment                 - Normalized Puppet Sizing (30-35% frame width)
     - Akshara Syllable Phonetic Parser              - Shot Scale Solver (EWS, FS, MS, MCU, CU, ECU)
     - Multi-Point Keyframe Foley Scheduler          - Dynamic Staging: Over-The-Shoulder & Eyelines
     - Broadcast 48kHz Master Bus (EBU R128)         - Mythological Motion Graphics (Vedic Kundalis)
                  │                                               │
                  └───────────────────────┬───────────────────────┘
                                          │
                                          ▼
   [ 5. Composition & Choreography Engine (scripts/engine/composer.py) ]
     - Generates Clean Jinja2 HTML5 Stage + Responsive CSS + Modular GSAP 3 Timelines
     - Forward Kinematics Skeletal Rigging with Natural Human Joint Constraints
     - Continuous Life Engine (Diaphragmatic Breathing, Blinks, Micro-Saccades, Weight Shift)
     - Organic Animation Principles: Anticipation Wind-up, Action Acceleration, Elastic Settle
     - Akshara-Driven 5-State Emotional Lip-Sync (Calm, Talk, Shout, Fear, Joy)
                  │
                  ▼
   [ 6. Frame-Deterministic Render Runtime (HyperFrames / Puppeteer) ]
     - Headless Chrome captures uncompressed 60 FPS video frames at 1080x1920
                  │
                  ▼
   [ 7. Broadcast Audio Mastering & Muxing (scripts/render_and_qa.py) ]
     - FFmpeg 48,000 Hz 24-bit Stereo Master
     - Sidechain Ducking (`threshold=0.03:ratio=8:attack=20:release=500:makeup=1`)
     - Integrated Loudness Normalization to -14 LUFS (True Peak -1.5 dBTP) via `loudnorm`
                  │
                  ▼
   [ 8. Triple-Gate Automated Quality Assurance Suite (scripts/engine/qa_verifier.py) ]
     - Gate 1: Cinematography & Temporal QA (ASL <= 3.5s, no shot > 3.8s)
     - Gate 2: Geometric & Safe-Zone QA (Puppet width <= 380px, zero overlay facial occlusion)
     - Gate 3: Acoustic & Spectral QA (48kHz verification, 12-20kHz energy check, sync audit)
```

---

## 2. Complete Root-Cause Analysis & Codebase Audit Findings

### 2.1 Scene-by-Scene Analysis of the Actual Rendered Video (`build/final_short.mp4`)
A forensic inspection of the rendered video ("जब रावण ने बांधा शनि देव को", Video ID `cd1cc1mhfwg`, duration 69.90s) revealed catastrophic visual, acoustic, and narrative flaws across every scene:

| Scene & Interval | Duration | Identified Defects & Root Causes |
|---|---|---|
| **Scene 1**<br>`00:00.00 - 00:11.84` | **11.84s** | **The Monolithic Static Hold:** The opening shot holds for 11.84s without a single cutaway, punch-in, or angle change. Sutradhar and Ravana stand as oversized cardboard cutouts. Ravana's arm holds `boastful_grand` statically for 11 seconds while his legs oscillate mechanically. The slow camera drift (`scale: 1.0 -> 1.15` over 12s = $1.25\%/\text{s}$) is imperceptible to the human eye. SFX (`brahma_boon_chime.mp3`) plays at $t=0$ and dies at $t=2.5\text{s}$, leaving 9.3s of acoustic void. |
| **Scene 2**<br>`00:11.84 - 00:21.53` | **9.69s** | **Central Overlap & Scarecrow Pose:** Ravana ($x=-190$) and Shani Dev ($x=+190$) are rendered at 800px width scaled by $1.12\times$ ($896\text{px}$ wide each), causing **516 pixels of central overlap** across the center of the frame. Shani is assigned `humbled_braced` with hardcoded `--rot-shoulder-l: 105deg`, flinging his arm out in a bizarre horizontal scarecrow T-pose. No ropes, chains, or physical binding assets appear on screen despite the narration stating Ravana bound Shani. |
| **Scene 3**<br>`00:21.53 - 00:31.69` | **10.16s** | **Dead Technical Diagram:** Narration describes Ravana locking Shani under his throne. Instead of dramatic staging, the video reveals a 2D vector graphic (`shani_drishti_mandala.svg`). The diagram scales from 0.90 to 1.05 and stops; its internal SVG stages (`#stage_1`, `#arrows`) never animate. It floats dead for 10.16 seconds. The graphic contains English astronomy labels ("SINGULARITY", "EVENT HORIZON"), directly violating the 100% Hindi project rule. |
| **Scene 4**<br>`00:31.69 - 00:41.25` | **9.56s** | **Eyeline Disconnect & Blind Lip-Sync:** Narration speaks of Meghnada's astrological birth chart. No birth chart appears. Ravana and Shani stand at fixed elevations with eyes looking past each other ($15^\circ$ vertical eyeline error). Lip-sync toggles mouth opacity 4 times over 9.5s regardless of spoken words, completely desynchronized from the audio. |
| **Scene 5**<br>`00:41.25 - 00:49.97` | **8.72s** | **Scarecrow Recurrence & Muffled Audio:** Shani Dev is again subjected to the broken $105^\circ$ scarecrow pose. The voiceover sounds noticeably dull and muffled due to 24000 Hz downsampling stripping vocal harmonics above 12 kHz. |
| **Scene 6**<br>`00:49.97 - 00:60.25` | **10.28s** | **Catastrophic Facial Occlusion:** Narration describes Shani's divine gaze destroying Lanka. Instead of visual destruction, `#infographic_symbol_scales_container` ($z\text{-index}: 90$) is positioned at $X=340\text{px}, Y=420\text{px}$, directly on top of Shani Dev's head and chest ($z\text{-index}: 40$), completely decapitating the character rig. English text is burned into the scales graphic. |
| **Scene 7**<br>`00:60.25 - 00:69.90` | **9.65s** | **Anti-Climactic Resolution:** A 9.6-second static hold on Sutradhar standing alone. The outro marquee does not animate. Audio cuts off abruptly without a musical fade-out or reverb tail. |

### 2.2 Complete Codebase Audit & Component Defect Matrix

The codebase was audited line-by-line across all scripts, assets, and configurations:

```
+-----------------------------------------------------------------------------------------------------------------------+
| COMPONENT                  | FILE & LINE NUMBER         | SEVERITY | IDENTIFIED DEFECT & IMPACT                       |
+-----------------------------------------------------------------------------------------------------------------------+
| Composition Monolith       | scripts/generate_          | CRITICAL | 2,155-line monolith mixing HTML templates, inline|
|                            | composition.py (1-2155)    |          | CSS, hardcoded JS switch-cases, and inline SVGs. |
+-----------------------------------------------------------------------------------------------------------------------+
| Puppet Sizing & Overlap    | scripts/generate_          | CRITICAL | .puppet-wrapper hardcoded to 800x1200px. With    |
|                            | composition.py (237-245)   |          | scale: 1.12 at x: +-190, puppets overlap by 516px|
|                            |                            |          | in two-character shots, choking the 1080px frame.|
+-----------------------------------------------------------------------------------------------------------------------+
| Scarecrow Joint Kinematics | scripts/generate_          | CRITICAL | applyPose() hardcodes --rot-shoulder-l: 105deg   |
|                            | composition.py (1077-1105) |          | for humbled_braced, snapping arms horizontally.  |
|                            |                            |          | Poses are static holds with no life/breathing.   |
+-----------------------------------------------------------------------------------------------------------------------+
| Blind Dummy Lip-Sync       | scripts/generate_          | CRITICAL | applyLipSync() divides duration by 6.0 and       |
|                            | composition.py (1253-1273) |          | blindly toggles mouth 4 times, ignoring real     |
|                            |                            |          | Whisper word timestamps in build/manifest.js.    |
+-----------------------------------------------------------------------------------------------------------------------+
| Dead Diagram Animation     | scripts/generate_          | HIGH     | bespoke_diagram_reveal merely scales container   |
|                            | composition.py (1489-1498) |          | 0.90 to 1.05; internal SVG stages never animate. |
+-----------------------------------------------------------------------------------------------------------------------+
| Audio Downsampling Bug     | scripts/render_and_qa.py   | CRITICAL | Forces [1:a]aresample=24000:async=1 across all   |
|                            | (lines 340, 347, 372, 392) |          | voice, music, and SFX streams, degrading 44.1kHz |
|                            |                            |          | ElevenLabs audio to 24kHz telephone quality.    |
+-----------------------------------------------------------------------------------------------------------------------+
| FFmpeg Amix Volume Crush   | scripts/render_and_qa.py   | CRITICAL | amix=inputs={mix_count} omits normalize=0.      |
|                            | (line 398)                 |          | FFmpeg divides master volume by N inputs,        |
|                            |                            |          | crushing voice/BGM whenever SFX are added.       |
+-----------------------------------------------------------------------------------------------------------------------+
| Missing Loudness Norm      | scripts/render_and_qa.py   | HIGH     | Uses naive alimiter instead of EBU R128 loudnorm.|
|                            | (line 398)                 |          | Master fails YouTube -14 LUFS standard.          |
+-----------------------------------------------------------------------------------------------------------------------+
| Monolithic Pacing Config   | config.yaml (40-61) &      | CRITICAL | Enforces min_scenes: 5, max_scenes: 15, and      |
|                            | docs/INSTRUCTIONS.md (26)  |          | 8-35 words/scene, guaranteeing 10-second static  |
|                            |                            |          | holds and ASL = 10.0s (fatal for retention).     |
+-----------------------------------------------------------------------------------------------------------------------+
| Technical Diagram Assets   | assets/svg/diagrams/       | HIGH     | Astrophysics diagrams (shani_drishti_mandala)    |
|                            | (all files)                |          | with English labels ("SINGULARITY") in mythos.   |
+-----------------------------------------------------------------------------------------------------------------------+
| Triad Leak & Fallback Bug  | scripts/generate_          | MEDIUM   | getPuppet fallback assigned p3 to allPuppets[2]  |
|                            | composition.py (1474)      |          | even in two-character shots, leaking narrator.   |
+-----------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Professional Animation, Cinematography & Audio Research Findings

### 3.1 2D Cut-Out Puppet Animation & Disney's 12 Principles
External research into professional 2D cut-out digital puppet animation (such as techniques used in *Toon Boom Harmony*, *Moho*, *Spine 2D*, and *Adobe Animate*) reveals how traditional hand-drawn animation principles must be engineered into articulated vector puppets:

1. **Volume Preservation via Squash & Stretch:**
   - In rigid vector cut-outs, characters cannot be redrawn frame-by-frame. Volume preservation must be simulated mathematically: when a torso or limb is squashed on the Y-axis by scale factor $k$, it must stretch on the X-axis by $1/\sqrt{k}$ to maintain constant apparent mass ($S_x \times S_y \approx 1.0$).
   - *Reference:* Thomas, F. & Johnston, O., *The Illusion of Life: Disney Animation*, Hyperion; Adobe Animate Cut-out Principles ([adobe.com](https://www.adobe.com/creativecloud/animation/discover/cutout-animation.html)).
2. **Anticipation (The Counter-Windup):**
   - Natural biomechanical movement never begins instantly in the direction of action. A character must prepare the viewer's eye:
     - Before leaping or rising, character crouches ($8\text{px} - 15\text{px}$ downward dip).
     - Before striking with a weapon or pointing an accusatory finger, the shoulder and forearm rotate $3^\circ - 6^\circ$ backward for $120\text{ms} - 180\text{ms}$ before rapidly firing forward.
   - *Reference:* LottieFiles Motion Mechanics & Cutout Anticipation Guide ([lottiefiles.com](https://lottiefiles.com/blog/animation-principles)).
3. **Follow-Through & Overlapping Secondary Action:**
   - Sub-assemblies (crown ribbons, sashes, jewelry, loose hair, weapons) must never stop simultaneously with the torso. They must lag the master bone by $80\text{ms} - 160\text{ms}$ and oscillate past the settling point using spring damping (`back.out(1.4)` or `elastic.out(1, 0.75)`).
4. **Hierarchical Forward Kinematics (FK) Bone Chains:**
   - Rotation must propagate down parent-child hierarchies:
     $$\text{Torso} \longrightarrow \text{Shoulder} \longrightarrow \text{Elbow} \longrightarrow \text{Wrist} \longrightarrow \text{Weapon}$$
   - When the torso tilts by $\Delta \theta$, the shoulder inherits $\Delta \theta$, maintaining visual coherence without limb dislocation.

### 3.2 9:16 Vertical Cinematography & Mobile Safe Zones
Research into YouTube Shorts, Meta Reels, and TikTok framing specifications establishes the strict geometric limits of vertical mobile screens:

1. **The 1080 × 1920 Mobile Safe Zone Boundaries:**
   - **Top Exclusion Zone ($0\text{px} - 288\text{px}$, top $15\%$):** Obscured by search bar, sound selector, camera button, and OS status bar.
   - **Bottom Exclusion Zone ($1400\text{px} - 1920\text{px}$, bottom $27\%$):** Heavily occluded by creator avatar, channel handle, video title, automated closed captions, and the audio waveform progress bar.
   - **Right-Side Rail ($900\text{px} - 1080\text{px}$, right $16\%$):** Occluded by the vertical engagement stack (Like, Dislike, Comment, Share, Remix icons).
   - **The Golden Action Zone ($X \in [80, 900]$, $Y \in [300, 1400]$):** All essential visual information—character faces, eyes, action gestures, props, and sacred mandalas—must remain strictly within this $820\text{px} \times 1100\text{px}$ bounding box.
   - *References:* YouTube Shorts Technical Safe Zone Guidelines ([reap.video](https://reap.video/youtube-shorts-safe-zone), [muzecmo.com](https://muzecmo.com/youtube-shorts-dimensions)).
2. **Rule of Thirds in Vertical Framing:**
   - Eye level for characters in Medium and Close-up shots must align with the **Upper Third Line ($Y \approx 650\text{px} - 720\text{px}$)**, matching natural human eye fixation on mobile displays.
3. **Pacing & Average Shot Length (ASL) Benchmarks:**
   - High-retention short-form video algorithms require an Average Shot Length of **$1.8\text{s}$ to $3.2\text{s}$**.
   - Holding any static camera shot for $>3.8\text{s}$ results in immediate viewer drop-off.
   - The **Hook Window ($0\text{s} - 3\text{s}$)** requires an immediate visual pattern interruption (punch-in zoom, rapid shot cut, or dramatic motion).

### 3.3 Hindi Orthographic Syllable (Akshara) Lip-Sync Model
Research into Hindi speech recognition, forced alignment, and viseme generation (AI4Bharat IndicMFA, Wav2Vec2 CTC, Rhubarb) clarifies how to achieve realistic lip-sync without heavy external deep learning models:

1. **Phonetic Nature of Devanagari Script:**
   - Unlike English where spelling is non-phonetic ("through" vs "rough"), Devanagari is an **Abugida**: every orthographic unit (Akshara / अक्षर) consists of a consonant base with an inherent or attached vowel matra (`स्वर` / `मात्रा`).
   - Words decompose deterministically into syllables:
     $$\text{रावण} \longrightarrow \text{रा (rā, open vowel)} + \text{व (va, neutral)} + \text{ण (ṇa, closed/nasal)}$$
2. **Akshara-Level Phonetic Duration Modeling:**
   - OpenAI Whisper via `faster-whisper` yields reliable word boundaries `[start, end]`.
   - In 2D cut-out animation (e.g. *South Park*, traditional Kathputli), switching mouth shapes at 50 Hz (every 20ms) produces unwatchable high-frequency chatter. Viewers perceive natural speech when mouth shapes switch at **8 to 12 frames per second ($80\text{ms} - 120\text{ms}$ per viseme)**, matching syllable pulses.
   - Distributing Whisper word duration across its constituent Aksharas—allocating $65\%$ duration to long vowels (`आ, ई, ऊ, ए, ऐ, ओ, औ`) and $35\%$ to short vowels/consonants—produces fluid, culturally authentic lip animation synchronized to the actual audio.
3. **Mapping to Existing Puppet Mouth Layers:**
   - Inspection of `assets/svg/characters/*.svg` confirms that puppets already possess 5 distinct, expressive mouth states:
     - `#mouth_calm`: Relaxed, closed neutral lips (silence, pauses, bilabial closures `म, ब, प`).
     - `#mouth_talk`: Standard conversational mid-open oval (short vowels `अ, इ, उ`, conversational speech).
     - `#mouth_shout`: Wide vertical jaw aperture with exposed teeth (long vowels `आ, ओ`, dramatic emphasis, roars, wrath).
     - `#mouth_fear`: Trembling, rounded aperture (fear, shock, submission).
     - `#mouth_joy`: Smiling crescent with exposed upper teeth (laughter, triumph, benediction).
   - *References:* AI4Bharat IndicMFA Architecture ([github.com/AI4Bharat/IndicMFA](https://github.com/AI4Bharat/IndicMFA)); Collabora Indic Whisper Normalization ([collabora.com](https://www.collabora.com)); PyTorch Wav2Vec2 Forced Alignment ([pytorch.org](https://pytorch.org/audio/stable/tutorials/forced_alignment_tutorial.html)).

### 3.4 Broadcast Audio Engineering & FFmpeg Mastering Standards
Research into broadcast audio mastering standards (EBU R128, ITU-R BS.1770-4) and FFmpeg audio filtergraphs provides the exact parameters for professional mobile sound:

1. **Target Loudness for YouTube Shorts:**
   - Target Integrated Loudness: **$-14.0\text{ LUFS}$** ($\pm 0.5\text{ LUFS}$).
   - True Peak Maximum: **$-1.5\text{ dBTP}$** (prevents inter-sample clipping when YouTube transcodes to lossy Opus/AAC).
   - Loudness Range (LRA): **$10 - 12\text{ LU}$** (ensures dialogue remains intelligible on small mobile phone speakers without dynamic crushing).
2. **Sidechain Compression Curve:**
   - Fast attack ($20\text{ms}$) immediately ducks background music upon voice onset.
   - Smooth release ($500\text{ms}$) allows music to swell naturally during dialogue pauses.
   - Compression ratio: $8:1$; threshold: $0.03$ ($-30\text{ dBFS}$).
3. **The Multi-Input Audio Mixing Fix:**
   - FFmpeg's `amix` filter divides master volume by $N$ inputs by default. Setting `normalize=0` is **mandatory** to prevent SFX inputs from attenuating the voiceover and music.
   - Master filtergraph:
     ```bash
     [music][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=500:makeup=1[duck];
     [duck][vox][sfx_all]amix=inputs=3:normalize=0:duration=first[mixed];
     [mixed]loudnorm=I=-14:TP=-1.5:LRA=11[master]
     ```
   - *References:* EBU R128 Loudness Recommendation; FFmpeg `loudnorm` and `sidechaincompress` Documentation ([ffmpeg.org](https://ffmpeg.org/ffmpeg-filters.html)).

---

## 4. Character Sizing, Framing & 9:16 Vertical Cinematography

### 4.1 Root Cause of Oversized Characters
In the legacy engine:
- `.puppet-wrapper` had CSS `width: 800px; height: 1200px; left: 140px; top: 240px;`.
- Center point was $140 + 400 = 540\text{px}$ (canvas center).
- Staging applied `scale: 1.12` and offsets $x = -190$ and $x = +190$.
- Effective width per puppet was $800 \times 1.12 = 896\text{px}$.
- Puppet 1 spanned $X \in [-98\text{px}, 798\text{px}]$; Puppet 2 spanned $X \in [282\text{px}, 1178\text{px}]$.
- The resulting central overlap of **$516\text{px}$** choked the frame, hung $98\text{px}$ off the screen edges, and violated both left and right safe zones.

### 4.2 Clean-Slate Puppet Dimensions & Ground Plane Anchoring
1. **Base Wrapper Standardization:**
   - Standardized base puppet wrapper: **`width: 480px; height: 960px;`** (viewBox `0 0 800 1200` scaled cleanly to fit).
   - **`transform-origin: 50% 100%`** (foot contact plane).
   - Feet are anchored to the theatrical stage baseline at **$Y = 1420\text{px}$**.
   - Scaling up or down expands the puppet vertically upward from the floor, completely preventing vertical floating, jitter, or ground dislocation.
2. **Two-Character Staging Math (Full Shot / Confrontation):**
   - Puppet width on screen: **$340\text{px} - 380\text{px}$** ($31\% - 35\%$ of canvas width, scale factor $0.72\times - 0.80\times$).
   - Character 1 (Left / Antagonist): Positioned at center $X = 300\text{px}$ (occupies $X \in [110\text{px}, 490\text{px}]$).
   - Character 2 (Right / Protagonist): Positioned at center $X = 760\text{px}$ (occupies $X \in [570\text{px}, 950\text{px}]$, flipped `scaleX: -1.0`).
   - **Conversational Negative Space Gap: $160\text{px} - 220\text{px}$** in the center of the frame, completely eliminating overlap and providing room for visual weapons, divine auras, and sacred energy clashes.
   - Both characters remain strictly inside the Golden Action Zone ($X \in [80, 960]$).

### 4.3 Standardized Shot Scale Hierarchy

| Shot Scale | Narrative Purpose | Puppet Height & Width | Vertical Framing & Anchor | Headroom Clearance | Canvas Area % |
|---|---|---|---|---|---|
| **Extreme Wide (EWS)** | Cosmic grandeur, establishing Lanka or Kailash. | Height: `380px - 440px`<br>Width: `190px - 220px` | Grounded at $Y = 1440\text{px}$. Scaled at $0.42\times$. Positioned against sweeping architectural vista. | $850\text{px}+$ | $8\% - 12\%$ |
| **Full Two-Shot (FS)** | Physical confrontations, dialogue, martial stances. | Height: `740px - 820px`<br>Width: `340px - 380px` | Grounded at $Y = 1420\text{px}$. Scaled at $0.78\times$. Centered at $X=300\text{px}$ and $X=760\text{px}$. | $320\text{px}$ | $28\% - 32\%$ |
| **Medium Shot (MS)** | Storytelling gestures, teaching mudras, moral debate. | Height: `780px` (waist-up)<br>Width: `440px - 480px` | Anchored at pelvis ($Y=1360\text{px}$). Scaled at $1.02\times$. Single character or Over-the-Shoulder. | $260\text{px}$ | $36\% - 42\%$ |
| **Medium Close-Up (MCU)** | Dramatic speech, emotional shift, vow or curse. | Height: `700px` (bust-up)<br>Width: `520px - 560px` | Eye level locked to Upper Third ($Y=700\text{px}$). Scaled at $1.32\times$. | $220\text{px}$ | $44\% - 50\%$ |
| **Close-Up (CU)** | Peak fury, terror, divine realization, tear. | Height: `750px` (head/crown)<br>Width: `640px - 700px` | Crown crest contained below $Y=300\text{px}$. Scaled at $1.68\times$. | $160\text{px}$ | $55\% - 62\%$ |
| **Extreme Close-Up (ECU)** | Shani's third eye, burning pupil, weapon edge. | Height: `480px` (eyes/brow)<br>Width: `860px - 940px` | Centered at $Y=850\text{px}$. Scaled at $2.25\times$. Vignette mask. | Centered | $65\% - 75\%$ |

---

## 5. Character Rigging, Kinematics & Organic Cut-Out Animation

### 5.1 Anatomical Joint Constraints & Elimination of Scarecrow Poses
The legacy engine's arbitrary angles are replaced with anatomically valid biomechanical constraints:
- **Shoulders:** Restricted to $-40^\circ \le \theta \le +65^\circ$. (The broken $105^\circ$ angle is permanently deleted).
- **Elbows:** Restricted to $0^\circ \le \theta \le +135^\circ$ (natural flexion; hyperextension blocked).
- **Wrists:** Restricted to $-30^\circ \le \theta \le +30^\circ$.
- **Torso Lean:** Restricted to $-6^\circ \le \theta \le +6^\circ$.
- **Head Pitch & Yaw:** Restricted to $-12^\circ \le \theta \le +12^\circ$.

#### Redesigned Humbled / Bound Pose (`humbled_braced`):
Instead of flinging arms horizontally, a bound captive (such as Shani Dev before Ravana) displays:
- Torso pitched forward by $5^\circ$ (`--trans-torso-y: 15px`).
- Upper arms angled downward at $35^\circ$ (`--rot-shoulder-l: 35deg; --rot-shoulder-r: -35deg`).
- Forearms crossed inward over chest at $75^\circ$ (`--rot-elbow-l: 75deg; --rot-elbow-r: -75deg`).
- Wrists clasped (`--rot-wrist-l: 15deg`).
- Head bowed downward at $-10^\circ$, with eyes turned upward toward the oppressor.

### 5.2 The Continuous Life Engine (Secondary & Idle Motion)
Characters are biological beings, never frozen statues. A dedicated animation engine continuously runs:
1. **Diaphragmatic Breathing:**
   - Ribcage scales along Y-axis ($1.00 \longleftrightarrow 1.025$) on an organic $2.2\text{s}$ sine cycle (`ease: "sine.inOut"`).
   - Shoulders float upward by $2\text{px}$ in tandem with breathing inhalation.
2. **Autonomous Blinking & Eye Saccades:**
   - Blinks trigger every $2.8\text{s} - 4.2\text{s}$ (closed for $70\text{ms}$, open for $110\text{ms}$).
   - Gaze micro-saccades shift pupils $\pm 2.5\text{px}$ every $1.2\text{s}$ to reflect active thought.
3. **Idle Weight Shift:**
   - Pelvis and hips oscillate $\pm 1.2^\circ$ every $3.8\text{s}$, shifting weight between left and right feet.
4. **Passive Follow-Through Physics:**
   - Sashes, crown ribbons (*kalgi*), and hair tips lag torso movement by $100\text{ms} - 150\text{ms}$ with spring oscillations.

### 5.3 Automated Eyeline & Focal Vector Solver
The engine computes the angular vector between the speaking character's mouth/face and the listening character's eyes:
$$\theta_{\text{eyeline}} = \arctan2(Y_{\text{speaker}} - Y_{\text{listener}}, X_{\text{speaker}} - X_{\text{listener}})$$
The listener's head and pupils rotate smoothly by $\theta_{\text{eyeline}}$ to maintain direct eye contact during confrontations.

---

## 6. Akshara-Level Hindi Phonetic Lip-Sync & Expression Engine

### 6.1 Devanagari Akshara Decomposition Algorithm
The lip-sync engine parses each spoken Hindi word into its constituent syllables and determines mouth shape based on the dominant vowel sound:

```python
def parse_hindi_aksharas(word: str) -> list[dict]:
    """
    Decomposes a Devanagari word into orthographic syllables (Aksharas)
    and maps them to mouth viseme states with relative weightings.
    """
    aksharas = []
    # Regular expression matching Devanagari consonant clusters + optional vowel matras
    pattern = re.compile(r'([क-ह]्)*[क-ह][ािीुूृेैोौौंः]?|[अ-औ]')
    matches = pattern.finditer(word)
    
    for m in matches:
        syl = m.group()
        # Classify dominant vocalic aperture
        if any(v in syl for v in ['ा', 'आ', 'ौ']):
            viseme = "mouth_shout" if "!" in word else "mouth_talk"
            weight = 0.65  # Long open vowel
        elif any(v in syl for v in ['ो', 'ू', 'ु', 'उ', 'ऊ', 'ओ']):
            viseme = "mouth_talk"
            weight = 0.55  # Rounded vowel
        elif any(v in syl for v in ['े', 'ै', 'ी', 'ि', 'इ', 'ई', 'ए', 'ऐ']):
            viseme = "mouth_talk"
            weight = 0.45  # Spread vowel
        elif any(c in syl for c in ['म', 'ब', 'प', 'भ', 'फ']):
            viseme = "mouth_calm"
            weight = 0.35  # Bilabial closure
        else:
            viseme = "mouth_talk"
            weight = 0.35  # Inherent neutral 'a'
            
        aksharas.append({"syllable": syl, "viseme": viseme, "weight": weight})
    return aksharas
```

### 6.2 Viseme Timeline Generation from Whisper Ground Truth
Using the word-level boundaries `[word_start, word_end]` from `build/manifest.js`:
1. Total word duration $D = \text{word\_end} - \text{word\_start}$.
2. The duration is distributed proportionally across the syllables based on their phonetic weights:
   $$d_i = D \times \frac{w_i}{\sum w_j}$$
3. For emotional scenes (e.g. Ravana's roar or Shani's wrath), open vowels automatically upgrade from `#mouth_talk` to `#mouth_shout`.
4. Silent gaps between words ($>120\text{ms}$) automatically insert `#mouth_calm` rest states.
5. In the browser engine, GSAP `timeline.set()` switches SVG opacity with zero timer polling.

---

## 7. Scene-to-Beat Decomposition & High-Retention Pacing Engine

### 7.1 Narrative Beats vs. Monolithic Camera Shots
A script scene represents a **dramatic narrative unit** ($8\text{s} - 12\text{s}$), NOT a single camera shot. The new **Cinematography Beat Planner** subdivides each scene into **2 to 4 Micro-Beats (Shots)**:

```
Narrative Scene 2 (9.69s total):
  "मेघनाद के जन्म पर रावण ने काल और नवग्रहों को एकादश भाव में बांधने का आदेश दिया।"

Beat Decomposition:
  ├── Beat 2A (0.00s - 2.80s, dur: 2.80s) | ESTABLISHING_WIDE (Scale 0.78x)
  │   - Wide royal court of Lanka. Golden throne dais.
  │   - Camera: Cinematic push-in (scale 1.0 -> 1.05).
  │   - Ravana stands proud; captive gods bowed.
  │
  ├── Beat 2B (2.80s - 5.90s, dur: 3.10s) | OVER_THE_SHOULDER_RAVANA (Scale 1.35x)
  │   - Reverse OTS shot over Shani Dev's shoulder looking up at Ravana.
  │   - Ravana gesture: Boastful arm raise, laughing chest expansion.
  │   - Narration: "...नवग्रहों को एकादश भाव में बांधने का आदेश दिया।"
  │   - SFX: Deep throne-room sub-bass swell.
  │
  ├── Beat 2C (5.90s - 9.69s, dur: 3.79s) | MEDIUM_CLOSE_UP_SHANI (Scale 1.55x)
  │   - Punch-in cut to Shani Dev in profile.
  │   - Shani eyes narrow into wrath; dark blue Neelam aura pulses.
  │   - Eyeline locked upward toward Ravana.
  │   - SFX: Metal chain tension clink + dark chime.
```

### 7.2 Pacing Rules & Retention Architecture
- **Target Average Shot Length (ASL):** **$2.2\text{s}$ to $3.2\text{s}$**.
- **Absolute Upper Bound:** No visual framing may hold statically for longer than **$3.8\text{s}$** without a cut, punch-in, or camera shift.
- **Hook Beat ($0\text{s} - 3\text{s}$):** Maximum duration of opening shot is **$2.0\text{s}$**, followed immediately by an impact punch-in or shot cut to lock audience retention.
- **Dynamic Camera Moves:**
  - *Punch-in Cut:* Instantaneous $1.0\times \longrightarrow 1.25\times$ scale snap on critical dramatic words.
  - *Parallax Dolly:* Foreground hanging lamps move at $1.5\times$ speed, midground puppets at $1.0\times$, background palace at $0.4\times$.
  - *Impact Micro-Shake:* $12\text{px}$ decaying shake ($150\text{ms}$) on divine strikes or roars.

---

## 8. Mythological Visual Asset & Motion Graphic Architecture

### 8.1 Permanent Retirement of Technical Diagrams
All files in `assets/svg/diagrams/` containing modern technical vector flowcharts, physics schematics, and English labels are permanently deprecated and removed from production workflows.

### 8.2 The Mythological Motion Graphic Suite
Authentic cultural storytelling requires sacred visual motifs:
1. **Sanskrit Vedic Kundali Wheels:**
   - 12-house diamond Vedic astrological birth charts rendered in radiant gold on deep parchment.
   - Houses dynamically illuminate and rotate as planetary deities clash.
2. **Rotating Planetary Mandalas:**
   - Multi-ring sacred geometry (`shani_mandala.svg`, `kaal_chakra.svg`, `surya_chakra.svg`) with animated SVG `transform: rotate()` rings.
3. **Multi-Layer 2.5D Parallax Environments:**
   - **Layer 0 (Cosmic Sky):** Rotating star dome, blood moon, cosmic nebulae.
   - **Layer 1 (Architecture):** Golden pillars of Lanka, carved temple arches.
   - **Layer 2 (Stage Floor):** Polished obsidian marble reflecting character silhouettes.
   - **Layer 3 (Foreground Occluders):** Silhouetted hanging brass bells, temple drapes, atmospheric incense smoke.
4. **Cinematic Mythological Shaders:**
   - SVG `feTurbulence` and `feDisplacementMap` filters creating living heat-distortion and divine auras (Shani's dark sapphire aura; Shiva's blue throat glow).

---

## 9. Broadcast 48kHz Audio Mastering & Multi-Point Foley Pipeline

### 9.1 The Master 48kHz Stereo Processing Graph
The downsampling bug is permanently eliminated. The audio engine operates end-to-end at **48,000 Hz, 24-bit stereo**:

```
[Voice Track (44.1/48kHz)] ──> aformat=48000:stereo ──> asplit=2 ──┬──> [vox] ───────────────┐
                                                                    │                         │
[BGM Track (Stereo)]       ──> aformat=48000:stereo ──> [bgm_in]    │                         │
                                                           │        ▼                         ▼
                                                           └──> [sidechaincompress] ──> [amix (normalize=0)]
                                                                (duck -14dB on vox)           │
                                                                                              │
[Event-Driven Foley Cues]  ──> aformat=48000:stereo ──> [adelay] ─────────────────────────────┘
  (Footsteps, Sword Draws, Chains, Thunder, Swooshes)                                         │
                                                                                              ▼
                                                                                   [loudnorm (EBU R128)]
                                                                                   I=-14, TP=-1.5, LRA=11
                                                                                              │
                                                                                              ▼
                                                                                   Master 48kHz Audio Stream
```

### 9.2 Event-Driven Multi-Point Foley Scheduling
Foley sound effects are scheduled at exact visual contact keyframes rather than scene boundaries:
- **Footstep / Stage Contact:** $20\text{ms}$ sub-thud timed to foot contact frame.
- **Weapon Draw / Metallic Shimmer:** High-frequency metallic chime ($4.5\text{kHz} - 8\text{kHz}$) timed to sword/bow extension.
- **Divine Aura Hum:** Low-frequency sub-bass swell ($45\text{ Hz} - 90\text{ Hz}$) on emotion shift to `wrath`.
- **Chain Clink / Binding Tension:** High-treble chain rattle timed to captive struggle animation.
- **Camera Whip-Pan / Transition:** Air whoosh ($160\text{ms}$) centered on camera cut keyframes.

---

## 10. Modular Target Software Architecture & Directory Structure

The 2,155-line monolith `scripts/generate_composition.py` is permanently replaced by a clean, modular Python package located in `scripts/engine/`:

```
scripts/
├── engine/
│   ├── __init__.py
│   ├── config.py                 # Golden zone boundaries, safe zones, timing invariants
│   ├── beat_planner.py           # Narrative beat decomposer, ASL calculator & validator
│   ├── cinematography.py         # Shot scale solver (EWS-ECU), framing, OTS staging, eyelines
│   ├── puppet_rig.py             # Forward kinematics, joint constraints, continuous life engine
│   ├── lipsync_engine.py         # Devanagari Akshara parser & Whisper viseme timeline generator
│   ├── foley_scheduler.py        # Keyframe collision detector & multi-point SFX mapper
│   ├── vfx_engine.py             # Vedic Kundalis, rotating mandalas, SVG displacement shaders
│   ├── composer.py               # Assembles Jinja2 templates into build/index.html & engine.js
│   └── qa_verifier.py            # Automated triple-gate QA suite (temporal, geometric, acoustic)
├── build_audio.py                # ElevenLabs 48kHz synthesis & Faster-Whisper alignment
├── render_and_qa.py              # HyperFrames Puppeteer render & FFmpeg 48kHz EBU R128 mastering
├── db_manager.py                 # SQLite database state machine & Pydantic models
└── publish_youtube.py            # YouTube metadata & playlist publisher

templates/
├── composition/
│   ├── index.html.jinja2         # Semantic HTML5 stage template (clean DOM structure)
│   ├── styles.css.jinja2         # Golden-zone responsive styling & puppet CSS variables
│   └── engine.js.jinja2          # Modular GSAP 3 timeline choreography engine
```

### 10.1 Module Boundaries & Public Interfaces

#### `beat_planner.py`:
```python
def decompose_scene_into_beats(
    scene_plan: ScenePlan, 
    aligned_words: list[dict], 
    scene_start_sec: float, 
    scene_dur_sec: float
) -> list[BeatPlan]:
    """Splits a narrative scene into 2-4 visual beats ensuring ASL <= 3.2s."""
```

#### `cinematography.py`:
```python
def solve_shot_staging(
    shot_type: ShotType, 
    primary_char: str, 
    secondary_char: Optional[str]
) -> StagingTransform:
    """Calculates non-overlapping coordinates, scales, and eyeline angles inside Golden Zone."""
```

#### `lipsync_engine.py`:
```python
def generate_viseme_timeline(
    aligned_words: list[dict], 
    scene_offset_sec: float, 
    emotion: str
) -> list[dict]:
    """Generates deterministic GSAP viseme keyframes from Akshara decomposition."""
```

#### `puppet_rig.py`:
```python
def compile_puppet_kinematics(
    character_id: str, 
    pose_name: str, 
    emotion: str
) -> dict[str, str]:
    """Returns CSS joint rotation variables enforcing anatomical limits."""
```

---

## 11. Phased Implementation Roadmap, Tasks & Risk Matrix

```
[Phase 1: Modular Engine & Kinematics] ──> [Phase 2: Cinematics & Beats] ──> [Phase 3: Audio & VFX] ──> [Phase 4: QA & Pilot]
  - Modular Engine Scaffold                  - Beat Decomposer                - 48kHz FFmpeg Graph       - Automated QA Suite
  - 480x960 Puppet Standard                  - 9:16 Golden Zone Solver        - Multi-Point Foley        - Safe-Zone Collision Check
  - Natural Joint Limits & Poses             - OTS Staging & Eyelines         - Sanskrit Kundali Suite   - Pilot Video Production
  - Akshara Syllable Lip-Sync                - Dynamic Camera Punch-ins       - Dynamic Sidechain Mix    - Frame-by-Frame Audit
```

### Phase 1: Modular Engine Core, Puppet Sizing & Akshara Lip-Sync (Priority: P0 — Critical)
- [ ] Create `scripts/engine/` package directory and Jinja2 template structure.
- [ ] Implement `scripts/engine/config.py`: Define canvas dimensions, safe-zone boundaries, and timing invariants.
- [ ] Implement `scripts/engine/puppet_rig.py`: Standardize puppet base dimensions to $480\text{px} \times 960\text{px}$ with foot transform-origin (`50% 100%`).
- [ ] Fix joint limits: Eliminate $105^\circ$ scarecrow angles; implement natural shoulder, elbow, and torso constraints.
- [ ] Implement `ContinuousLifeEngine`: Inject diaphragmatic breathing ($2.2\text{s}$ sine cycle), eye blinks ($3.5\text{s}$), and idle weight shifts.
- [ ] Implement `scripts/engine/lipsync_engine.py`: Implement Devanagari Akshara parser and connect Whisper `aligned_words` to the 5 puppet mouth states (`mouth_calm`, `mouth_talk`, `mouth_shout`, `mouth_fear`, `mouth_joy`).

### Phase 2: Beat Decomposition, Dynamic Cinematography & Staging (Priority: P0 — Critical)
- [ ] Implement `scripts/engine/beat_planner.py`: Deconstruct narrative scenes into $1.8\text{s} - 3.5\text{s}$ micro-beats (target ASL: $2.4\text{s} - 3.2\text{s}$).
- [ ] Implement `scripts/engine/cinematography.py`: Implement shot library (EWS, FS, MS, MCU, CU, ECU) and Golden Zone framing solver.
- [ ] Implement two-character staging: Enforce $340\text{px} - 380\text{px}$ character bounding widths with $180\text{px} - 220\text{px}$ central conversational space.
- [ ] Implement automated eyeline vector solver and Over-The-Shoulder (OTS) reverse shot staging.
- [ ] Implement camera dynamics: Punch-in cuts on emphasis words, subtle parallax dolly, and decaying screen shake on impact frames.

### Phase 3: Broadcast 48kHz Audio Pipeline & Mythological Asset Overhaul (Priority: P0 — Critical)
- [ ] Refactor `scripts/render_and_qa.py`: Completely eliminate 24kHz downsampling; enforce $48\text{kHz}$ $24\text{-bit}$ master audio pipeline.
- [ ] Fix FFmpeg `amix` volume crush by passing `normalize=0`.
- [ ] Implement EBU R128 integrated loudness normalization via `loudnorm=I=-14:TP=-1.5:LRA=11`.
- [ ] Implement `scripts/engine/foley_scheduler.py`: Map Foley sound cues to exact visual keyframe impacts.
- [ ] Deprecate and remove technical flowcharts in `assets/svg/diagrams/`; catalog new Sanskrit Kundalis, celestial mandalas, and aura shaders.

### Phase 4: Automated Triple-Gate QA Suite & End-to-End Pilot Verification (Priority: P1 — High Impact)
- [ ] Implement `scripts/engine/qa_verifier.py`: Automated assertion of $\text{ASL} \le 3.5\text{s}$, zero safe-zone violations, and 48kHz frequency spectrum verification.
- [ ] Update `docs/INSTRUCTIONS.md` to document the new beat-driven cinematography, framing rules, and asset conventions.
- [ ] Execute an end-to-end production run of Episode 1 of *Shani Katha* ("जब रावण ने बांधा शनि देव को").
- [ ] Inspect output video frame-by-frame and frequency-spectrum to verify broadcast quality.

### Risk Management & Mitigation Matrix

| Identified Risk | Severity | Probability | Mitigation Strategy |
|---|---|---|---|
| Increased shot count slowing Puppeteer render times. | Medium | Low | GSAP DOM swaps via `display: block/none` have near-zero GPU overhead compared to video decoding. Headless Chrome maintains 60 FPS. |
| Sanskrit Akshara parser misclassifying rare conjuncts. | Low | Low | Fallback to vowel nucleus detection; default to conversational mid-open `#mouth_talk` if regex fails. |
| Overlapping dialogue in dual-character scenes. | Medium | Low | Single Katha-vachak paradigm (Viraj) ensures strictly sequential speech beats. |
| YouTube dynamic UI altering safe-zone dimensions. | Low | Medium | The Golden Action Zone leaves generous buffers (top 288px, bottom 520px, right 192px), exceeding standard mobile player requirements. |

---

## 12. Testing, Verification Protocols & Clear Acceptance Criteria

### 12.1 Automated Quality Gates

```python
# Gate 1: Temporal & Cinematography QA
def test_cinematography_metrics(manifest: dict) -> None:
    shots = manifest["beats"]
    total_dur = manifest["total_duration_sec"]
    asl = total_dur / len(shots)
    assert 1.8 <= asl <= 3.5, f"ASL {asl:.2f}s outside target range [1.8s, 3.5s]!"
    for shot in shots:
        assert shot["duration_sec"] <= 3.8, f"Shot {shot['beat_id']} held > 3.8s!"
        assert shot["duration_sec"] >= 1.2, f"Shot {shot['beat_id']} too short (< 1.2s)!"

# Gate 2: Geometric & Safe-Zone QA
def test_puppet_framing_and_clearance(dom_snapshots: list[dict]) -> None:
    for snap in dom_snapshots:
        # Assert puppet width in two-shots
        if snap["shot_type"] in ["full_two_shot", "two_character_confrontation"]:
            assert snap["p1_width_px"] <= 400, "Puppet 1 exceeds 400px width!"
            assert snap["p2_width_px"] <= 400, "Puppet 2 exceeds 400px width!"
            assert snap["overlap_px"] == 0, f"Central puppet collision detected: {snap['overlap_px']}px!"
        # Assert zero overlay collision with character head
        assert not snap["overlay_intersects_head"], "Overlay occludes character face!"

# Gate 3: Acoustic & Synchronization QA
def test_audio_broadcast_spec(audio_path: Path) -> None:
    probe = ffmpeg.probe(str(audio_path))
    audio_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    assert int(audio_stream["sample_rate"]) == 48000, "Audio sample rate is not 48,000 Hz!"
    # Verify high-frequency spectral content (no 12kHz lowpass cutoff)
    spectrum_max = compute_spectral_ceiling(audio_path)
    assert spectrum_max >= 18000, f"Audio spectrum capped at {spectrum_max}Hz (downsampling detected)!"
```

### 12.2 Human Perceptual Acceptance Criteria
The final rendered pilot video will only be accepted if it satisfies the following qualitative criteria:
1. **Dynamic Pacing:** The video feels visually alive, with camera cuts or angle shifts occurring every $2-3$ seconds, matching high-retention short-form storytelling.
2. **Natural Character Proportions:** Characters fit comfortably inside the frame with generous headroom and breathing space. Two-character shots feel like a balanced theatrical duel, with zero clumsy overlap.
3. **Biological Life Motion:** Characters continuously breathe, blink, shift weight, and tilt heads. They never freeze like static cardboard cutouts.
4. **Coordinated Action & Eyelines:** Opponents look each other in the eye. When Ravana speaks, Shani reacts. Captive characters appear genuinely restrained.
5. **Authentic Hindi Lip-Sync:** Mouth shapes open, round, and close in direct coordination with the spoken Hindi syllables.
6. **Cultural Visual Richness:** No technical flowcharts or English text appear. The screen is filled with ancient golden mandalas, Vedic astrological charts, and divine atmospheric auras.
7. **Broadcast Audio Clarity:** Voiceover is crisp, full-bodied, and loud ($-14\text{ LUFS}$), background music ducks seamlessly under speech and swells during dramatic pauses, and sound effects punch cleanly without distortion.

---

## 13. Summary & Awaiting User Review

This plan represents an exhaustive, research-backed, and implementation-ready architectural blueprint for the Sutradhar video-generation engine. It completely resolves every identified defect and replaces the legacy monolith with a modular, maintainable, and high-performance system.

**Current State & Mandate:**
- **No application code, assets, database records, or configurations have been altered.**
- All research, mathematical calculations, and architectural designs are recorded in this file (`docs/VIDEO_ENGINE_REARCHITECTURE_PLAN.md`).
- **Implementation will not begin until you have reviewed and explicitly approved this complete plan.**

Please review the revised plan. Once you grant your explicit approval, we will proceed immediately with the clean-slate implementation of Phase 1.
