# Sutradhar Audio Library Manifest & Sourcing Guide

This document defines the strict audio asset contracts, technical specifications, and recommended CC0 / YouTube Audio Library search keywords for all background music (BGM) and sound effects (SFX) used in Sutradhar's Kathputli shorts.

---

## 1. Technical Audio Specifications

| Parameter | Specification | Notes |
| :--- | :--- | :--- |
| **BGM Format** | MP3 (`.mp3`) or WAV (`.wav`) | 320 kbps CBR (MP3) or 24-bit PCM (WAV) |
| **SFX Format** | Broadcast WAV (`.wav`) | 24-bit PCM, uncompressed |
| **Sample Rate** | 44,100 Hz or 48,000 Hz | Resampled to 24,000 Hz master rate during final render |
| **Channels** | Stereo (2.0) | Symmetrical left/right panning |
| **Master Loudness Target** | **-14.0 LUFS ± 0.5** | Conforms to 2026 YouTube Shorts loudness standard |
| **True Peak Max** | **-1.0 dBFS** | Strictly prevents clipping on mobile DACs |
| **Integrated Dialogue Gate** | Sidechain ducking active | BGM ducks by 6:1 ratio under narration |
| **Tail Fade-Out** | 1.20s smooth exponential fade | `afade=t=out:st={duration-1.2}:d=1.2` |

---

## 2. Required Core Audio Assets

### A. Background Music (`assets/bgm/`)
Each editorial pillar maps directly to a primary BGM track in `config.yaml`:

| Filename | Editorial Pillar | Aesthetic Character | Target Mood |
| :--- | :--- | :--- | :--- |
| `dramatic_mythology.mp3` | **Ancient Epics & Lore** | Classical Indian instrumentation (Rudra Veena, Pakhawaj, Sitar, low cinematic drones). Epic, grand, solemn. | Sovereign defiance, divine confrontation, mythical grandeur. |
| `epic_history.mp3` | **Hidden History** | War drums, Nagara, Bansuri, ancient bronze gongs, low cello strings. Driving, narrative, investigative. | Lost civilizations, archaeological discoveries, ancient tactical warfare. |
| `cosmic_mystery.mp3` | **Cosmic & Scientific Paradoxes** | Deep analog synthesizer drones, tanpura overtone drones, bowed glass, subtle celestial pulses. Wonder, tension, paradox. | Event horizons, cosmic geometry, time dilation, Vedic astronomy. |

### B. Sound Effects (`assets/sfx/`)
Synchronized with shot cuts, character kinetic gestures, and narrative climax impacts:

| Filename | Type | Typical Duration | Usage Cue |
| :--- | :--- | :--- | :--- |
| `whoosh_soft.wav` | Transition / Motion | 0.60s – 0.90s | Theatrical curtain opening, rapid camera whip pan, sudden shot transition. |
| `sub_hit.wav` | Impact / Climax | 1.20s – 1.80s | Cosmic strike, weapon impact, sudden realization, climax reveal. |
| `tension_swell.wav` | Riser / Atmosphere | 2.50s – 4.00s | Building tension before dialogue shout, climax anticipation. |

---

## 3. Royalty-Free & CC0 Sourcing Guidelines

When sourcing or replacing audio tracks, select only **100% royalty-free, commercial-safe (CC0 or YouTube Audio Library)** assets.

### Recommended YouTube Audio Library Search Keywords:
- **For `dramatic_mythology.mp3`:**
  - Keywords: `"Indian cinematic"`, `"Epic Sitar"`, `"Veena drone"`, `"Pakhawaj battle"`, `"Ancient temple ambient"`.
  - Filter: *Genre: Cinematic / World | Mood: Dramatic, Dark, Epic*.
- **For `epic_history.mp3`:**
  - Keywords: `"Historical drama"`, `"War drums tribal"`, `"Ancient empire"`, `"Battle of Ten Kings"`, `"Caravan mystery"`.
  - Filter: *Genre: Cinematic | Mood: Suspenseful, Driving*.
- **For `cosmic_mystery.mp3`:**
  - Keywords: `"Cosmic drone"`, `"Space ambient"`, `"Deep abyss synth"`, `"Quantum dark"`, `"Astronomical void"`.
  - Filter: *Genre: Ambient / Cinematic | Mood: Mysterious, Atmospheric*.
- **For SFX (`assets/sfx/`):**
  - Keywords: `"Cinematic sub bass drop"`, `"Deep boom impact"`, `"Velvet whoosh"`, `"Dark braam riser"`.

---

## 4. Procedural Fallback Engine Guarantee
If any BGM track is temporarily absent from `assets/bgm/`, Sutradhar's hardened rendering engine automatically falls back to an internal procedural harmonic drone bed (`aevalsrc` acoustic sine drone) so renders never crash or abort unexpectedly during testing.
