# Sutradhar Video Engine Re-Architecture & Implementation Plan
**Document Version:** 2.0.0  
**Target Architecture:** Modular Beat-Driven Cinematic Puppet Engine (HyperFrames Runtime)  
**Status:** Pending User Approval — Ready for Review  
**Date:** 2026-11-24  

---

## 1. Executive Blueprint & Architectural Vision

The Sutradhar video-generation engine is being fundamentally re-engineered from the ground up. The previous system relied on an unviable architectural premise: **"1 Script Scene = 1 Monolithic 10-Second Visual Shot"**, with oversized puppet assets (taking 75%+ of canvas width), rigid scarecrow T-poses, blind periodic lip-sync, scientific diagram assets in ancient mythos, and a damaged 24kHz downsampled audio pipeline.

The target architecture replaces this legacy monolith with a **Decoupled, Beat-Driven Cinematic Engine** operating on top of the deterministic **HyperFrames (Puppeteer + GSAP 3)** web-canvas render pipeline.

```
+---------------------------------------------------------------------------------------------------+
|                                 SUTRADHAR TARGET ARCHITECTURE                                     |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
                                    [ Episode Script & Narrative ]
                                                  │
                                                  ▼
                                   [ Narrative Beat Decomposer ]
                 Splits 60s script into 18-24 Visual Beats (Target ASL: 2.2s - 3.5s)
                                                  │
                   ┌──────────────────────────────┴──────────────────────────────┐
                   ▼                                                             ▼
     [ Audio & Acoustic Pipeline ]                                [ Cinematography & Visual Planner ]
     - ElevenLabs 48kHz Voiceover                                  - 9:16 Golden Zone Framing Engine
     - OpenAI Whisper Forced-Alignment                            - Shot Hierarchy (EWS, FS, MS, MCU, CU, ECU)
       (Word + Phoneme Timelines)                                  - Safe-Zone Collision Solver
     - Event-Driven Foley Scheduler                               - Depth-Layered Parallax Environments
     - 48kHz 24-bit Stereo Master Bus                              - Dynamic Camera (Punch-in, Pan, Shake)
                   │                                                             │
                   └──────────────────────────────┬──────────────────────────────┘
                                                  │
                                                  ▼
                                 [ Modular Composition Generator ]
                                                  │
    ┌─────────────────────────────────────────────┼─────────────────────────────────────────────┐
    ▼                                             ▼                                             ▼
[ Puppet Kinematics & Rigging ]          [ Whisper Lip-Sync Engine ]                   [ Mythological VFX Engine ]
- Normalized Scale (30-40% width)        - Phoneme-to-Viseme Mapper                    - Sanskrit Mandalas & Kundalis
- Foot-Anchored Transform Origins         (Rest, Wide A, Round O, Spread E, M/B/P)      - Multi-layer Parallax Backdrops
- Forward Kinematic Bone Chains          - Natural Attack/Sustain/Release Easing       - SVG Filter Displacement Shaders
- Continuous Life Engine                 - Zero Blind Periodic Looping                 - Divine Energy Auras & Beams
  (Breathing, Blinks, Weight Shift)                                                     - Atmospheric Ember & Smoke Fields
- Expressive Eyeline Solver
    └─────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                                  │
                                                  ▼
                                    [ HyperFrames Render Runtime ]
                             Headless Chrome / Puppeteer 60 FPS Capture
                                                  │
                                                  ▼
                                    [ Broadcast Audio/Video Master ]
                           FFmpeg 48kHz 24-bit PCM Mixing + H.264 High Profile
                                                  │
                                                  ▼
                                    [ Automated Cinematic QA Suite ]
                      ASL <= 3.8s | Safe-Zone Clearance | Headroom | 20kHz Audio Check
```

### Core Architectural Invariants:
1. **Average Shot Length (ASL) Invariant:** Every visual shot must last between $1.8\text{s}$ and $3.8\text{s}$. No static framing may ever hold longer than $3.8\text{s}$.
2. **Golden Zone Framing Invariant:** In a 1080x1920 vertical canvas, all primary action, character eyes, gestures, and focal points must remain strictly within $X \in [80\text{px}, 1000\text{px}]$ and $Y \in [300\text{px}, 1500\text{px}]$ (leaving top 288px and bottom 384px clear of critical elements).
3. **Proportional Puppet Sizing Invariant:** In standard two-character full/medium shots, a character puppet must never exceed $320\text{px} - 400\text{px}$ in bounding width ($30\% - 37\%$ of canvas width) and must be grounded at $Y = 1420\text{px}$ with a minimum $250\text{px}$ headroom.
4. **Deterministic Synchronization Invariant:** All mouth visemes, Foley effects, camera punch-ins, and character reactions must be indexed to absolute Whisper word timestamps (`aligned_words`). Blind periodic timer loops (`dur / 6.0`) are permanently banned.
5. **Broadcast Fidelity Invariant:** Master audio pipeline must maintain end-to-end $48,000\text{ Hz}$, $24\text{-bit}$ stereo fidelity. Downsampling to $24\text{ kHz}$ is permanently removed.

---

## 2. Current System Deconstruction & Deprecation Matrix

The following components from the legacy implementation will be permanently deprecated, removed, or rewritten:

| Component / File | Legacy State & Defects | Architectural Verdict | Replacement / Clean-Slate Solution |
|---|---|---|---|
| `scripts/generate_composition.py` (2,155 lines) | Monolithic file combining HTML template strings, inline CSS coordinates, giant switch-case JS engine, and inline SVG puppet strings. Hardcodes 800px puppet widths and broken scarecrow poses. | **DEPRECATE & REPLACE ENTIRELY** | Split into modular Python package `scripts/engine/` (`composer.py`, `cinematography.py`, `puppet_rig.py`, `lipsync.py`, `vfx.py`). Clean template files for HTML/CSS/JS. |
| `applyPose()` in `generate_composition.py` | Sets hardcoded static angles at $t_{\text{start}}$ (e.g., `humbled_braced` has `--rot-shoulder-l: 105deg`, causing scarecrow T-pose). Character freezes for 10s with mechanical leg wobble. | **DELETE & REPLACE** | Hierarchical bone kinematic engine with natural joint limits, spring easing, anticipation/overshoot, and continuous idle life (breathing, weight shift, blinks). |
| `applyLipSync()` in `generate_composition.py` | Blind periodic loop dividing scene duration by 6 (`dur / 6.0`) to toggle mouth open/closed 4 times regardless of speech. | **DELETE & REPLACE** | Whisper-aligned Viseme Engine (`scripts/engine/lipsync.py`) driven by `aligned_words` intervals, mapping vowels and consonants to specific mouth shapes. |
| `assets/svg/diagrams/` (`shani_drishti_mandala.svg`, etc.) | Astrophysics-style 2D flowcharts with English labels ("SINGULARITY", "EVENT HORIZON") and static GSAP scale tweens. | **PURGE & DELETE** | Replace with Mythological Motion Graphics: Sanskrit Kundalis, animated astrological birth charts, celestial rings, and dynamic aura shaders. |
| `shotType === "two_character_confrontation"` | Places 800px puppets at $x = -190$ and $x = 190$, causing massive center overlap, crowded frame, zero physical interaction, and no eyeline alignment. | **DELETE & REPLACE** | Dynamic Staging Engine: Over-The-Shoulder (OTS), foreground-background depth staging, conversational spacing ($220\text{px}$ gap), and automated eyeline vector calculation. |
| `render_and_qa.py` (Audio Pipeline) | Downsamples audio to 24000 Hz (`aresample=24000:async=1`), degrading high frequencies above 12 kHz. Clumps SFX at scene start. | **REWRITE AUDIO PIPELINE** | Broadcast 48,000 Hz 24-bit mastering pipeline. Multi-point event-driven Foley scheduler mapped to animation keyframes. |
| `config.yaml` & `docs/INSTRUCTIONS.md` (Pacing Rules) | Mandates `min_scenes: 5, max_scenes: 15`, producing 10-second static scenes for 60-70s shorts. | **REWRITE PACING RULES** | Re-define narrative structure into **Scenes $\rightarrow$ Micro-Beats (Shots)**. Target 18–24 shots per 60s short ($2.5\text{s} - 3.5\text{s}$ ASL). |
| `db_manager.py` (`ScenePlan` model) | Data model assumes 1 Scene = 1 Shot, mixing narration, backdrop, diagram, and camera motion in a flat schema. | **REFACTOR SCHEMA** | Introduce `BeatPlan` list inside `ScenePlan` or generate beats deterministically in the cinematography planner while keeping database backwards compatibility. |

---

## 3. Cinematography, Framing & Character Sizing Specifications

### 3.1 9:16 Vertical Canvas Geometry & Safe Zones (1080 x 1920)

```
0px ------------------------------------------------------------- 1080px
    | TOP EXCLUSION ZONE (0 - 288px)                            |
    | YouTube Shorts Search, Channel Bar, Account Controls       |
288px -----------------------------------------------------------
    |                                                           |
    |                   GOLDEN ACTION ZONE                      |
    |                X: 80px - 1000px | Y: 300px - 1500px       |
    |                                                           |
    |   [Upper Third Line: Y = 700px] <--- Character Eye Level  |
    |                                                           |
    |   [Center Point: X = 540px, Y = 900px]                    |
    |                                                           |
    |   [Lower Third Line: Y = 1180px] <--- Waist / Props       |
    |                                                           |
    |   [Ground Plane Baseline: Y = 1420px] <--- Puppet Feet    |
    |                                                           |
1536px ----------------------------------------------------------
    | BOTTOM EXCLUSION ZONE (1536 - 1920px)                     |
    | Captions, Video Title, Channel Handle, Audio Track,       |
    | Subscribe Pill, Right-side Like/Comment/Share Rail        |
1920px ----------------------------------------------------------
```

### 3.2 Standardized Shot Scale Hierarchy for Puppets

To ensure characters never overwhelm the canvas, every shot type follows strict geometric constraints:

| Shot Scale | Narrative Purpose | Puppet Bounding Dimensions | Staging & Y-Anchor | Canvas Area % | Headroom Clear |
|---|---|---|---|---|---|
| **Extreme Wide Shot (EWS)** | Establishing grandeur, cosmic scale, army face-offs. | Width: `180px - 240px`<br>Height: `360px - 450px` | Grounded at $Y = 1440\text{px}$. Scaled at $0.45\times$. Characters set against sweeping palace/sky architecture. | $8\% - 12\%$ | $900\text{px}+$ |
| **Full Shot (FS / Two-Shot)** | Confrontations, martial stances, physical dialogue. | Width: `320px - 380px`<br>Height: `750px - 850px` | Grounded at $Y = 1420\text{px}$. Scaled at $0.85\times$. Two puppets positioned at $X = 300\text{px}$ and $X = 780\text{px}$ ($180\text{px}$ conversational gap). | $25\% - 30\%$ | $320\text{px}$ |
| **Medium Shot (MS / Cowboy)** | Standard dialogue, hand gestures, weapon drawn. | Width: `420px - 480px`<br>Height: `800px` (waist up) | Centered at $Y = 1350\text{px}$. Scaled at $1.05\times$. Transform-origin at pelvis ($50\% \text{ } 65\%$). | $35\% - 42\%$ | $260\text{px}$ |
| **Medium Close-Up (MCU)** | Dramatic speech, emotional shift, intensity. | Width: `520px - 580px`<br>Height: `700px` (bust up) | Centered at $Y = 1300\text{px}$. Scaled at $1.35\times$. Eye level locked to Upper Third ($Y = 720\text{px}$). | $45\% - 52\%$ | $220\text{px}$ |
| **Close-Up (CU)** | Climax dialogue, fury, fear, revelation. | Width: `650px - 720px`<br>Height: `750px` (head/shoulders) | Centered at $Y = 1250\text{px}$. Scaled at $1.75\times$. Ornaments/crown fit inside $Y = 320\text{px}$. | $55\% - 62\%$ | $160\text{px}$ |
| **Extreme Close-Up (ECU)** | Eye of Shani, weapon edge, third eye flash. | Width: `850px - 950px`<br>Height: `500px` (eyes/brow) | Centered at $Y = 850\text{px}$. Scaled at $2.30\times$. Dramatic vignette mask. | $65\% - 75\%$ | Centered |

### 3.3 Puppet Transform Origin & Ground Plane Standard
- **The Problem:** Legacy `.puppet-wrapper` had `transform-origin: 400px 700px`, causing puppets to float, expand into camera space, and dislocate feet when scaled.
- **The Fix:**
  - Base puppet wrapper size standardized to **`width: 480px; height: 960px;`** (down from 800x1200).
  - Transform origin anchored strictly at **`transform-origin: 50% 100%`** (bottom center foot contact plane).
  - When scaling from $0.5\times$ to $1.2\times$, puppet feet stay solidly planted on the stage floor ($Y = 1420\text{px}$), expanding organically upward without vertical jitter.
  - For bust/close-up shots, transform origin dynamically shifts to pelvis/neck (`50% 45%`).

### 3.4 Dynamic Two-Character Staging (Depth & Over-The-Shoulder)
Instead of placing two static puppets side-by-side:
1. **Depth Layering (Speaker Staging):**
   - Active Speaker: Positioned slightly forward ($Z=45$, scale $0.95\times$, sharp focus).
   - Reactive Listener: Positioned slightly back ($Z=40$, scale $0.80\times$, subtle depth-of-field blur `filter: blur(1.5px)`).
2. **Over-The-Shoulder (OTS) Framing:**
   - Shot A (Speaker 1): Camera behind Speaker 2's silhouette/shoulder ($X = 180\text{px}$, scale $1.4\times$, opacity $0.85$, blurred), looking directly at Speaker 1 ($X = 640\text{px}$, scale $1.15\times$, in sharp focus).
   - Shot B (Reverse on Speaker 2): Camera flips behind Speaker 1's shoulder.

---

## 4. Character Rigging, Kinematics & Natural Animation System

### 4.1 Standardized SVG Puppet Skeletal Schema
All character puppets (`assets/characters/*.svg`) must conform to a standardized hierarchical `<g>` group structure with explicit pivot coordinates embedded as `data-pivot-x` and `data-pivot-y`:

```xml
<g id="puppet_{character_id}" class="puppet-rig" data-height="960" data-width="480">
  <!-- Pelvis & Root Anchor -->
  <g id="bone_pelvis" data-pivot="240,620">
    <!-- Legs & Feet -->
    <g id="bone_leg_l" data-pivot="190,640">
      <g id="bone_shin_l" data-pivot="185,780">
        <path id="foot_l" ... />
      </g>
    </g>
    <g id="bone_leg_r" data-pivot="290,640">
      <g id="bone_shin_r" data-pivot="295,780">
        <path id="foot_r" ... />
      </g>
    </g>
    <!-- Spine & Torso -->
    <g id="bone_torso" data-pivot="240,600">
      <!-- Left Arm (Behind or Front based on depth) -->
      <g id="bone_shoulder_l" data-pivot="160,380">
        <g id="bone_forearm_l" data-pivot="120,490">
          <g id="bone_hand_l" data-pivot="100,580">...</g>
        </g>
      </g>
      <!-- Neck & Head Assembly -->
      <g id="bone_neck" data-pivot="240,350">
        <g id="bone_head" data-pivot="240,320">
          <g id="face_base">...</g>
          <g id="eyes_container" data-pivot="240,240">
            <g id="eyebrow_l" data-pivot="200,210">...</g>
            <g id="eyebrow_r" data-pivot="280,210">...</g>
            <g id="eye_pupils">...</g>
            <g id="eyelids_blink">...</g>
          </g>
          <g id="mouth_container" data-pivot="240,290">
            <g id="mouth_rest" class="viseme">...</g>
            <g id="mouth_wide_a" class="viseme">...</g>
            <g id="mouth_round_o" class="viseme">...</g>
            <g id="mouth_spread_e" class="viseme">...</g>
            <g id="mouth_closed_m" class="viseme">...</g>
          </g>
          <g id="crown_and_ornaments">...</g>
        </g>
      </g>
      <!-- Right Arm -->
      <g id="bone_shoulder_r" data-pivot="320,380">
        <g id="bone_forearm_r" data-pivot="360,490">
          <g id="bone_hand_r" data-pivot="380,580">...</g>
        </g>
      </g>
    </g>
  </g>
</g>
```

### 4.2 Natural Motion & Kinematic Principles
Puppet motion must abandon static CSS snapping in favor of forward kinematic chains governed by organic animation principles:
1. **Anticipation (Wind-up):** Before any major action (striking, pointing, raising arm), character dips down by $8\text{px} - 12\text{px}$ and rotates opposite by $3^\circ - 5^\circ$ for $0.15\text{s}$.
2. **Action & Acceleration:** The primary gesture snaps forward rapidly over $0.2\text{s} - 0.28\text{s}$ using cubic acceleration (`power2.in`).
3. **Overshoot & Elastic Settle:** The limb travels $4^\circ - 6^\circ$ past target pose, then gently settles back over $0.22\text{s}$ using `back.out(1.4)` or `elastic.out(1, 0.75)`.
4. **Joint Limit Constraints:**
   - Shoulder: $-45^\circ \le \theta \le +65^\circ$ (natural human reach; no $105^\circ$ scarecrows).
   - Elbow: $0^\circ \le \theta \le +135^\circ$ (no hyperextension).
   - Head Tilt: $-12^\circ \le \theta \le +12^\circ$.
   - Neck Yaw/Pitch: $-8^\circ \le \theta \le +8^\circ$.

### 4.3 Continuous Life Engine (Secondary & Idle Motion)
Characters are biological entities, never statues. A dedicated `ContinuousLifeEngine` injects subtle micro-motion continuously:
- **Diaphragmatic Breathing:** Torso scales along Y-axis ($1.00 \leftrightarrow 1.025$) on an organic $2.2\text{s}$ sine cycle (`sine.inOut`), coupled with a $2\text{px}$ vertical shoulder float.
- **Micro-Weight Shift:** Pelvis and hips shift $\pm 1.5^\circ$ every $3.5\text{s}$ to simulate natural balance adjustments.
- **Autonomous Blinking & Eye Saccades:**
  - Eyes blink every $2.8\text{s} - 4.5\text{s}$ (closed for $75\text{ms}$, open for $110\text{ms}$).
  - Gaze micro-saccades shift pupils $\pm 2.5\text{px}$ every $1.4\text{s}$ to convey active thought.
- **Passive Follow-Through Physics:** Crown ribbons, sash cloth, and hair tips lag torso movement by $80\text{ms} - 140\text{ms}$ with spring oscillations.

### 4.4 Automated Eyeline & Focal Target Solver
- The engine calculates the angle vector between Character A's head pivot and Character B's eye coordinates:
  $$\theta_{\text{eyeline}} = \arctan2(Y_B - Y_A, X_B - X_A)$$
- Head and pupil groups rotate smoothly to track the focal target (the speaking opponent, the divine artifact, or the viewer during direct narration).

---

## 5. Whisper-Driven High-Fidelity Lip-Sync Engine

### 5.1 Hindi Phoneme-to-Viseme Mapping
The mouth rig features 5 discrete viseme states. The engine translates Whisper word timestamps and duration intervals into visemes:

| Viseme State | Visual Shape | Phoneme Triggers (Devanagari & IAST) | Typical Duration |
|---|---|---|---|
| **`rest`** | Mouth closed, relaxed neutral lips. | Silence, pauses, breathing gaps. | $> 150\text{ms}$ non-speech |
| **`wide_a`** | Jaw dropped, vertical oral opening. | आ (ā), अ (a), ऐ (ai), औ (au), हा (hā), रा (rā) | $180\text{ms} - 350\text{ms}$ |
| **`round_o`** | Lips pursed, rounded circular aperture. | ओ (o), ऊ (ū), उ (u), वो (vo), को (ko) | $140\text{ms} - 260\text{ms}$ |
| **`spread_e`** | Teeth lightly exposed, horizontal lip stretch. | ई (ī), इ (i), ए (e), सी (sī), ती (tī), य (ya) | $120\text{ms} - 220\text{ms}$ |
| **`closed_m`** | Bilabial seal, lips pressed firmly shut. | म (ma), ब (ba), प (pa), भ (bha), फ (pha) | $90\text{ms} - 160\text{ms}$ |

### 5.2 Deterministic Viseme Generation Algorithm
```python
def generate_viseme_timeline(aligned_words: list[dict], scene_offset_sec: float) -> list[dict]:
    timeline = []
    for word in aligned_words:
        w_start = word["start"] - scene_offset_sec
        w_end = word["end"] - scene_offset_sec
        w_dur = w_end - w_start
        text = word["word"].strip()
        
        # Analyze leading consonant and dominant vowel
        primary_viseme = classify_hindi_viseme(text)
        
        # Attack phase (open) -> Hold phase -> Decay to neutral
        attack_t = max(0.04, min(0.08, w_dur * 0.2))
        timeline.append({"t": round(w_start, 3), "viseme": primary_viseme, "transition": "snap"})
        
        if w_dur > 0.25 and primary_viseme != "closed_m":
            # For prolonged vowels, hold then slightly close to secondary
            timeline.append({"t": round(w_start + w_dur * 0.6, 3), "viseme": "spread_e", "transition": "ease"})
            
        timeline.append({"t": round(w_end, 3), "viseme": "rest", "transition": "decay"})
    return timeline
```
In the browser engine, GSAP `timeline.set()` calls execute this exact array. Blind periodic loops are completely eliminated.

---

## 6. Scene-to-Beat Decomposition & Dynamic Pacing Engine

### 6.1 Beat Decomposer Architecture
A short script consists of 6 to 8 narrative scenes. The **Cinematography Beat Planner** subdivides each scene into **Micro-Beats (Shots)** based on dialogue beats, dramatic pauses, and character actions:

```
Script Scene (10.0s total):
  "जब रावण ने सारे ग्रहों को बंदी बना लिया, तब केवल शनि देव ने झुकने से मना किया।"

Beat Decomposition:
  ├── Beat 1 (0.0s - 3.2s) | ESTABLISHING_WIDE (Scale 0.85x)
  │   - Wide royal court of Lanka. Ravana sits triumphant on throne.
  │   - Camera: Slow dramatic push-in (scale 1.0 -> 1.06).
  │   - Narration: "जब रावण ने सारे ग्रहों को बंदी बना लिया..."
  │
  ├── Beat 2 (3.2s - 6.4s) | MEDIUM_CLOSE_UP (Scale 1.35x, OTS)
  │   - Cut to Ravana over-the-shoulder looking down at the captive gods.
  │   - Ravana gesture: Boastful laugh, chest expands, crown glints.
  │   - Camera: Punch-in cut (ASL reset).
  │
  ├── Beat 3 (6.4s - 10.0s) | REVERSE_CLOSE_UP_SHANI (Scale 1.65x)
  │   - Dramatic reverse cut to Shani Dev.
  │   - Shani eyes narrow; blue Neelam aura begins dark pulse.
  │   - Narration: "...तब केवल शनि देव ने झुकने से मना किया।"
  │   - SFX: Deep sub-bass surge + celestial chord.
```

### 6.2 Pacing Rules & Average Shot Length (ASL) Target
- **Target ASL:** $2.4\text{s} - 3.4\text{s}$.
- **Hard Upper Bound:** No shot may exceed $3.8\text{s}$ without a camera cut, punch-in, or angle switch.
- **Hook Beat (0s - 3s):** Maximum duration of first shot is $2.0\text{s}$, immediately followed by an action/impact cut to lock viewer retention.
- **Climax Beats (35s - 50s):** Rapid cuts ($1.2\text{s} - 2.0\text{s}$) with camera micro-shakes ($12\text{px}$ amplitude over $0.15\text{s}$).

---

## 7. Asset Ecosystem & Mythological Motion Graphics

### 7.1 Permanent Retirement of Technical Schematics
All files in `assets/svg/diagrams/` containing modern technical drawings, flowchart nodes, and English astrophysics terminology are removed from the production pipeline.

### 7.2 The Mythological Motion Graphic Asset Suite
Modern high-retention cultural storytelling demands authentic, stylized visual elements:
1. **Sanskrit Astrological Kundali Wheels:**
   - 12-house Vedic birth chart geometry rendered in luminous gold lines on deep parchment/cosmic void.
   - Houses highlight dynamically as planets align or clash.
2. **Divine Planetary Mandalas:**
   - Rotating sacred geometry rings (`shani_mandala.svg`, `surya_chakra.svg`, `kaal_chakra.svg`) with animated SVG `transform: rotate()` rings.
3. **Multi-Layer 2.5D Parallax Environments:**
   - **Layer 0 (Far Sky/Cosmos):** Deep twilight, rotating starry dome, blood moon.
   - **Layer 1 (Midground Architecture):** Golden pillars of Lanka, throne dais, carved temple arches.
   - **Layer 2 (Stage Floor Plane):** Polished black marble floor with reflections.
   - **Layer 3 (Foreground Occluders):** Silhouetted hanging brass lamps, temple curtains, atmospheric incense smoke.
4. **Cinematic Mythological VFX:**
   - Dark sapphire blue divine aura for Shani Dev (feTurbulence displacement shader).
   - Golden solar flare aura for Ravana / Surya.
   - Dynamic celestial chains snapping and vibrating with tension lines.

---

## 8. Audio Engineering, Foley Choreography & Sound Design

### 8.1 Broadcast 48kHz / 24-bit Master Pipeline
1. **Source Generation:** ElevenLabs voiceover synthesized at $44.1\text{kHz}$ or $48\text{kHz}$ (128kbps+ or lossless PCM).
2. **FFmpeg Processing:**
   - Deprecate `aresample=24000`.
   - Master bus configured to `-ar 48000 -c:a aac -b:a 320k` (or 24-bit uncompressed PCM for intermediate steps).
   - Frequency response verified flat from $20\text{ Hz}$ to $20,000\text{ Hz}$.

### 8.2 Event-Driven Multi-Point Foley Scheduling
Rather than clumping SFX at the start of a scene, the Foley Scheduler schedules sounds at exact visual collision frames:
- **Footstep / Stage Stride:** $18\text{ms}$ low-thud on foot contact keyframe.
- **Weapon Draw / Metal Gleam:** High-frequency metallic chime ($4.5\text{kHz} - 8\text{kHz}$) timed to sword/bow extension.
- **Divine Aura Surge:** Low-frequency sub-bass swell ($45\text{ Hz} - 90\text{ Hz}$) on character emotion shift to `wrath`.
- **Chain Clink / Tension:** Rattle SFX timed to captive struggle animation.
- **Camera Whip-Pan / Transition:** Air swoosh ($150\text{ms}$ duration) centered on camera cuts.

### 8.3 Dynamic BGM Mixing & Sidechain Ducking
- **Bed Level:** Continuous thematic music bed sits at $-20\text{ LUFS}$ under speech.
- **Fast Attack Ducking:** When voiceover is active, BGM ducks by $-14\text{ dB}$ (attack: $40\text{ms}$, release: $250\text{ms}$).
- **Dramatic Swells:** During beat pauses ($>400\text{ms}$ gap in narration), BGM swells by $+8\text{ dB}$ to punctuate the drama.

---

## 9. Target Software Architecture & Directory Structure

To replace the 2,155-line monolith, the system is partitioned into modular, single-responsibility components under `scripts/engine/`:

```
scripts/
├── engine/
│   ├── __init__.py
│   ├── config.py                 # Golden zone, canvas dimensions, safe-zone constants
│   ├── beat_planner.py           # Narrative beat decomposer, ASL calculator
│   ├── cinematography.py         # Shot selector, camera moves, framing solver
│   ├── puppet_rig.py             # Skeletal kinematics, joint limits, pose library
│   ├── lipsync_engine.py         # Whisper forced-alignment viseme generator
│   ├── vfx_engine.py             # Mandalas, aura shaders, particle themes
│   ├── foley_scheduler.py        # Event-driven sound design & SFX mapper
│   ├── composer.py               # Assembles modular components into HyperFrames index.html/engine.js
│   └── qa_verifier.py            # Automated ASL, safe-zone, and audio QA suite
├── build_audio.py                # 48kHz TTS synthesis & Whisper alignment
├── render_and_qa.py              # HyperFrames Puppeteer render & FFmpeg 48kHz master
├── db_manager.py                 # SQLite database & Pydantic models
└── publish_youtube.py            # YouTube metadata & upload handler

templates/
├── composition/
│   ├── index.html.jinja2         # Clean, semantic HTML5 stage template
│   ├── styles.css.jinja2         # Golden-zone responsive CSS, puppet stylesheets
│   └── engine.js.jinja2          # Modular GSAP 3 timeline choreography engine
```

### 9.1 Data Model Evolution in `db_manager.py`
The data model will be extended to natively support micro-beats while retaining full backward compatibility with stored episodes:

```python
class BeatPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    beat_index: int = Field(..., ge=1)
    shot_type: Literal[
        "establishing_wide", "full_two_shot", "over_the_shoulder", 
        "medium_close_up", "close_up_dramatic", "extreme_close_up_eyes",
        "action_cutaway", "mandala_cosmic"
    ]
    camera_action: Literal[
        "static_lock", "cinematic_push", "pull_back", "punch_in_cut", 
        "slow_pan_horizontal", "dramatic_whip_pan", "impact_shake"
    ]
    target_duration_sec: float = Field(..., ge=1.2, le=4.0)
    primary_character_pose: str
    primary_character_emotion: str
    secondary_character_pose: Optional[str] = None
    secondary_character_emotion: Optional[str] = None
    foley_cues: list[str] = Field(default_factory=list)
    vfx_triggers: list[str] = Field(default_factory=list)

class ScenePlan(BaseModel):
    # Existing fields retained for database integrity...
    scene_index: int
    narration_text: str
    # New beat breakdown list
    beats: Optional[list[BeatPlan]] = None
```

---

## 10. Phased Implementation Roadmap & Priorities

```
[Phase 1: Foundations] ───> [Phase 2: Cinematics] ───> [Phase 3: Audio/VFX] ───> [Phase 4: QA & Verification]
  - Modular Engine Core       - Beat Decomposer           - 48kHz Master Bus       - ASL Validator
  - Puppet Sizing & Rigging   - Dynamic Camera Moves      - Foley Scheduler        - Safe-Zone Bounding Box
  - Whisper True Lip-Sync     - Two-Shot Staging          - Mythological Mandalas  - End-to-End Pilot Video
```

### Phase 1: Core Kinematics, Puppet Sizing & True Lip-Sync (Priority: P0 — Critical)
- [ ] Create `scripts/engine/` module structure and Jinja2 templates.
- [ ] Implement `scripts/engine/puppet_rig.py`: Standardize base puppet size to $480\text{px} \times 960\text{px}$ with foot transform-origin (`50% 100%`).
- [ ] Fix broken poses: Replace `humbled_braced` scarecrow angles with anatomically natural joint limits.
- [ ] Implement `ContinuousLifeEngine`: Continuous diaphragmatic breathing ($2.2\text{s}$ sine wave), natural blinks ($3.5\text{s}$), and weight shifts.
- [ ] Implement `scripts/engine/lipsync_engine.py`: Wire Whisper `aligned_words` timestamps to the 5-viseme Hindi mouth rig; ban periodic loops.

### Phase 2: Beat Decomposition & Dynamic Cinematography (Priority: P0 — Critical)
- [ ] Implement `scripts/engine/beat_planner.py`: Deconstruct narrative scenes into $1.8\text{s} - 3.5\text{s}$ micro-beats (target ASL: $2.8\text{s}$).
- [ ] Implement `scripts/engine/cinematography.py`: Implement shot library (EWS, FS, MS, MCU, CU, ECU) and 9:16 Golden Zone framing solver.
- [ ] Implement dynamic two-character staging: OTS framing, conversational spacing ($180\text{px}-240\text{px}$ gap), and automated eyeline vector solver.
- [ ] Implement kinetic camera transitions: Punch-in cuts, subtle parallax dolly, impact screen shake ($12\text{px}$ decay).

### Phase 3: Broadcast Audio & Mythological Asset Overhaul (Priority: P0 — Critical)
- [ ] Refactor `scripts/render_and_qa.py`: Eliminate 24kHz downsampling; enforce $48\text{kHz}$ $24\text{-bit}$ master audio pipeline.
- [ ] Implement `scripts/engine/foley_scheduler.py`: Schedule Foley cues on exact visual impact frames (steps, sword draws, chain tension, aura hums).
- [ ] Purge `assets/svg/diagrams/` technical schematics; catalog new Sanskrit Kundalis, astrological wheels, and divine aura shaders.
- [ ] Implement dynamic BGM sidechain ducking (-14 dB under voiceover, +8 dB swell during beat cuts).

### Phase 4: Automated Cinematic QA & Full Pipeline Pilot (Priority: P1 — High Impact)
- [ ] Implement `scripts/engine/qa_verifier.py`: Automated checks asserting $\text{ASL} \le 3.8\text{s}$, zero safe-zone violations, and frequency response up to $20\text{kHz}$.
- [ ] Update `docs/INSTRUCTIONS.md` to document the new beat-driven workflow, framing rules, and asset standards.
- [ ] Execute an end-to-end production run of a pilot episode.
- [ ] Inspect output video frame-by-frame and frequency-spectrum to verify broadcast quality.

---

## 11. Testing, Verification & Quality Assurance Protocols

Every generated video must pass an automated triple-gate QA protocol before approval:

### Gate 1: Temporal & Cinematography QA (Automated)
```python
def verify_cinematography_metrics(manifest: dict) -> None:
    shots = manifest["beats"]
    total_dur = manifest["total_duration_sec"]
    asl = total_dur / len(shots)
    assert asl <= 3.8, f"FAILED: ASL {asl:.2f}s exceeds maximum threshold of 3.8s!"
    
    for shot in shots:
        dur = shot["duration_sec"]
        assert dur <= 4.0, f"FAILED: Shot {shot['beat_id']} held for {dur:.2f}s without a visual cut!"
        assert dur >= 1.2, f"FAILED: Shot {shot['beat_id']} too short ({dur:.2f}s) for visual comprehension!"
```

### Gate 2: Geometric & Safe-Zone QA (Automated via Puppeteer Snapshot)
- **Bounding Box Collision Check:** Verify that overlay elements (title cards, Sanskrit Kundalis) never intersect the puppet head bounding box ($Y \in [300\text{px}, 750\text{px}]$).
- **Headroom Verification:** Ensure puppet crown maintains at least $150\text{px}$ clearance below the top exclusion zone ($Y \ge 288\text{px}$).
- **Puppet Width Invariant:** Assert bounding width of puppets in two-character shots is $\le 420\text{px}$.

### Gate 3: Acoustic & Synchronization QA (Automated via FFprobe/Librosa)
- **Sample Rate Verification:** Verify master file is exactly `48000 Hz` with stereo channels.
- **Spectral Energy Check:** Confirm audio spectrum contains active frequencies between $12\text{ kHz}$ and $19\text{ kHz}$ (confirming no downsampling bottleneck).
- **Lip-Sync Alignment Audit:** Verify mouth viseme state changes match Whisper word timestamps within $\pm 35\text{ms}$.

---

## 12. Deliverable Summary & Awaiting User Review

This document establishes the definitive, comprehensive architectural blueprint for the Sutradhar video-generation engine. It completely resolves the root causes of oversized characters, unnatural movement, static pacing, fake lip-sync, inappropriate diagrams, and degraded audio.

**Notice Regarding Execution:**  
In strict compliance with instructions:
- **No application code, assets, database rows, or existing documentation files have been modified.**
- All research, mathematical calculations, framing rules, and architectural modules are documented in this file (`docs/VIDEO_ENGINE_REARCHITECTURE_PLAN.md`).
- **Implementation will not begin until you have reviewed and explicitly approved this plan.**

Please review the architecture and implementation roadmap above. Once approved, we will begin the clean-slate implementation of Phase 1.
