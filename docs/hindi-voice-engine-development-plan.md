# Sutradhar Hindi Voice Engine Development Plan (ElevenLabs-Only Architecture)

> **Document Status:** Final Architecture Specification (Pending User Sign-Off)  
> **Language Standard:** Pure Hindi (Devanagari script only; English support discontinued)  
> **Primary TTS Model:** **Eleven v4 (`eleven_v4`)** with Native Inline Audio Tag Steering  
> **Alternative Models:** `eleven_multilingual_v2` (Legacy fallback), `eleven_turbo_v2_5` (Draft testing)  
> **Fixed Narrator Voice:** **Viraj** (`uuyFQegRan8rpIQCGu9K`)  
> **Subscription Allowance:** ElevenLabs Starter Plan (37,188 monthly character credits)  
> **Configuration Architecture:** `config/voices.yaml` + `scripts/manage_voices.py` CLI helper  
> **Audio Assembly & Subtitles:** Per-Scene Synthesis + Local Whisper Millisecond Alignment  
> **Codebase Refactoring Strategy:** Clean Complete Removal of Kokoro ONNX and Gemini TTS  

---

## 1. Executive Summary & Strategic Architecture

The Sutradhar audio engine is standardized exclusively on **ElevenLabs**, powered by **Eleven v4 (`eleven_v4`)**.

Eleven v4 was chosen over earlier generations because it functions as an **adaptive digital voice actor** rather than a flat text-to-speech synthesizer. It provides native, first-class comprehension of **inline audio tags** (e.g. `[slowly, solemn]`, `[whispers]`, `[angry]`, `[building]`), allowing us to direct the pace, emotional intensity, volume, and dramatic inflection of each Hindi scene directly through the script without extra post-processing or SSML.

```mermaid
flowchart TD
    subgraph Planning ["1. Scene & Script Generation"]
        P["Episode Plan (build/episode_plan.json)"]
        P -->|Devanagari + Inline Audio Tags| T["Tagged Narration Text"]
    end

    subgraph Config ["2. Voice & Roster Management"]
        VY["config/voices.yaml"]
        CLI["scripts/manage_voices.py"]
        CLI <-->|Sync & Preview| EL_LIB["ElevenLabs Voice Library"]
        CLI -->|Assign Characters| VY
    end

    subgraph Engine ["3. ElevenLabs v4 Engine"]
        E["scripts/elevenlabs_engine.py"]
        CACHE["build/cache/audio/ (Hash Cache)"]
        API["ElevenLabs API (eleven_v4)"]
        
        T --> E
        VY --> E
        E -->|Check Hash| CACHE
        CACHE -->|Miss| API
        API -->|Audio Stream| CACHE
        CACHE --> SCENE_AUDIO["Scene WAV Files"]
    end

    subgraph Assembly ["4. Audio Mastering & Subtitles"]
        SCENE_AUDIO --> PAUSES["Narrative Dynamic Pauses"]
        PAUSES --> MASTER["episode_audio.wav (44.1 kHz 16-bit)"]
        MASTER --> WHISPER["Local Whisper Alignment (hi)"]
        WHISPER --> MANIFEST["audio_manifest.json (Word Timestamps)"]
    end
```

### Core Decisions
1. **Single Exclusive Provider:** ElevenLabs generates 100% of speech assets across all episodes.
2. **Primary Engine:** `eleven_v4` is the default model for all characters and scenes. Both `eleven_v4` and `eleven_multilingual_v2` consume identical credits (**1 credit per character**), making v4's superior dramatic range available at zero cost premium.
3. **Fixed Narrator:** **Viraj** (`uuyFQegRan8rpIQCGu9K`) is the permanent, unalterable voice for Sutradhar (the cosmic narrator) and Mahadev.
4. **Dynamic Character Assignment:** Supporting and mythological characters are mapped in `config/voices.yaml` and managed via `scripts/manage_voices.py`. Any character can be assigned to any voice in your ElevenLabs Library without touching application code.
5. **Zero-Waste Disk Caching:** Every generated scene is hashed by `(text, voice_id, model_id, settings)` and stored in `build/cache/audio/`. Re-rendering a video or adjusting a single scene costs 0 credits for all unchanged scenes.

---

## 2. Eleven v4 Inline Audio Tags: Specification & Guidelines

Eleven v4 treats text as a staged performance. By wrapping natural-language performance cues in square brackets `[...]`, the model dynamically modulates timbre, cadence, volume, and breathing.

### 2.1 Verified Supported Tag Categories

Based on official ElevenLabs documentation and our empirical benchmarks on Hindi speech, the following tag categories are verified and active in `eleven_v4`:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    VERIFIED ELEVEN v4 AUDIO TAG TAXONOMY                     │
├──────────────────┬──────────────────┬──────────────────┬─────────────────────┤
│ Pacing & Tempo   │ Emotions & Tone  │ Volume & Style   │ Vocal Reactions     │
├──────────────────┼──────────────────┼──────────────────┼─────────────────────┤
│ [slowly]         │ [calm]           │ [whispers]       │ [sighs]             │
│ [rushed]         │ [solemn]         │ [whispering]     │ [exhales]           │
│ [fast]           │ [serious]        │ [softly]         │ [gasp]              │
│ [pause]          │ [thoughtful]     │ [quietly]        │ [laughs]            │
│ [long pause]     │ [angry]          │ [shouts]         │ [chuckles]          │
│ [short pause]    │ [furious]        │ [shouting]       │ [clears throat]     │
│ [building]       │ [sorrowful]      │ [booming]        │ [gulps]             │
│ [building energy]│ [grief]          │ [gentle]         │ [trembling]         │
└──────────────────┴──────────────────┴──────────────────┴─────────────────────┘
```

> [!IMPORTANT]
> **No SSML Required:** Eleven v4 **does not** use XML-based SSML tags (e.g. `<break time="1s"/>`). Always use natural-language bracketed tags (e.g. `[long pause]`) or typographical markers (dashes `—`, ellipses `…`, and Devanagari full stops `।`) to manage timing.

---

### 2.2 Sutradhar Scene-to-Tag Mapping Rules

The pipeline automatically maps scene attributes to appropriate Eleven v4 tags:

| Scene Type / Character Role | Recommended Opening Tag | Inline Delivery Tag | Dramatic Purpose |
| :--- | :--- | :--- | :--- |
| **Sutradhar Narrator (Hook / Setup)** | `[slowly, solemn, deep]` | `[pause]` | Establishes ancient mythological gravitas; curbs v4's fast default speed to an unhurried ~125 wpm. |
| **Cosmic Climax / Divine Revelation** | `[building, intense, solemn]` | `[long pause]` | Builds mounting tension before a divine strike or universe-shattering event. |
| **Antagonist Dialogue (Ravana, Asuras)** | `[arrogant, booming, furious]` | `[laughs]`, `[shouts]` | Conveys hubris, defiance, and thunderous power. |
| **Sorrow / Tragedy (Mandodari, Sita)** | `[softly, sorrowful, trembling]` | `[sighs]`, `[grief]` | Infuses dialogue with genuine pathos, tears, and helplessness. |
| **Sage / Devotional (Rishi, Bhakta)** | `[calm, gentle, devotional]` | `[thoughtful]` | Conveys serene spiritual wisdom and meditative detachment. |
| **Philosophical Outro / Moral** | `[gentle, calm, peaceful]` | `[pause]` | Leaves the viewer with reflective, timeless philosophical resonance. |

---

### 2.3 Concrete Hindi Implementation Examples

#### 1. Hook & Cosmic Opening (Narrator: Viraj)
```text
[slowly, solemn, deep] सत्य केवल काल के गाल पर लिखा एक शब्द नहीं... [pause] यह सृष्टि का मूल आधार है। जब तीनों लोकों में अंधकार छा गया, तब केवल एक ही नाम गूंजा।
```
*Effect:* Viraj delivers the opening line with deep, resonant contemplation, pausing naturally at the ellipses before concluding with divine authority.

#### 2. Rising Action & Climax Beat (Narrator: Viraj)
```text
[building, intense] जब महादेव ने अपना तीसरा नेत्र खोला— [long pause] तो सम्पूर्ण ब्रह्मांड थर्रा उठा! न देव बचे, न दानव!
```
*Effect:* Cadence accelerates with mounting urgency; the `[long pause]` builds dramatic suspense before the explosion of divine fury.

#### 3. Wrathful Confrontation Dialogue (Ravana: Niraj)
```text
[arrogant, booming, furious] कौन है जो दशानन के मार्ग में खड़ा हो सके? [laughs] तीनों लोकों का स्वामी केवल मैं हूँ!
```
*Effect:* Niraj opens with aggressive, resonant dominance, delivers an authentic dark chuckle, and ends with thunderous vocal power.

#### 4. Emotional Tragedy Dialogue (Mandodari: Kanika)
```text
[softly, sorrowful, trembling] हे स्वामी... धर्म का मार्ग मत त्यागिए... [sighs] यह हठ लंका का सर्वनाश कर देगा...
```
*Effect:* Kanika's voice trembles softly with sorrow, sighs before the warning, and captures the tragic inevitability of Lanka's fall.

#### 5. Philosophical Outro (Narrator: Viraj)
```text
[gentle, calm, peaceful] कर्म ही नियति है, और धर्म ही शाश्वत सत्य। [pause] कथा अनन्ता... सूत्रधार।
```
*Effect:* Soft, meditative closure that gently dissolves into the final marquee and closing curtains.

---

### 2.4 Tag Implementation & Preprocessing Rules

To ensure tags direct the performance without interfering with subtitle synchronization or audio quality, the `ElevenLabsEngine` enforces these strict rules:

1. **Tag Placement:** Tags must be placed **immediately before** the clause or phrase they affect.
2. **Subtitles vs. Audio Disconnection:**
   - **TTS Payload:** Receives the **full tagged text** (e.g. `[slowly, solemn] सत्य केवल...`). Eleven v4 interprets the tag and synthesizes only the spoken words.
   - **Local Whisper Alignment:** Whisper listens to the synthesized audio directly. Because Eleven v4 does **not** speak bracketed tags aloud, Whisper's generated word timestamps in `audio_manifest.json` contain **only the clean spoken Devanagari words**, with zero tag leakage into video captions.
3. **Compound Tag Limit:** Use at most 3 descriptors per tag (e.g. `[slowly, solemn, deep]`). Combining more than 3 tags can dilute the model's focus.
4. **Devanagari Punctuation Synergy:** Combine tags with native punctuation:
   - `।` (Purna Viram) = Standard sentence pause (~300ms).
   - `...` (Ellipsis) = Trailing contemplative pause (~400ms).
   - `—` (Em-dash) = Dramatic breathless pause before revelation (~250ms).
   - `[pause]` = Explicit dramatic pause (~500ms).
   - `[long pause]` = Heavy theatrical pause (~800ms).

---

## 3. ElevenLabs Model Evaluation & Subscription Economics

### Empirical Model Comparison (Hindi Mythology Benchmark)

We tested our candidate models by synthesizing a 76-character passage (*"सत्य केवल काल के गाल पर लिखा एक शब्द नहीं, यह सृष्टि का मूल आधार है।"*) with **Viraj** (`uuyFQegRan8rpIQCGu9K`):

| Model ID | Latency | Untagged Duration | Tagged Duration (`[slowly, solemn]`) | Credit Cost | Verdict for Sutradhar |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`eleven_v4`** | **3.20s** | 5.88s | **7.24s (~135 wpm)** | **1 credit / char** | **SELECTED PRIMARY MODEL:** Native inline audio tags, superior dynamic acting, ultra-crisp audio mastering, and perfect Hindi phonetics. |
| **`eleven_multilingual_v2`** | 3.30s | 8.96s | 8.96s (Tags ignored) | 1 credit / char | **LEGACY FALLBACK:** Stately default pacing, but completely lacks inline tag support and dynamic emotional acting. |
| **`eleven_turbo_v2_5`** | 1.49s | 6.53s | 6.53s (Limited tags) | **0.5 credits / char** | **DRAFT / RETRY ENGINE:** 2.2x faster generation and 50% credit discount. Ideal for rapid pipeline drafts and layout testing. |

---

### Subscription Capacity on ElevenLabs Starter Plan (37,188 Monthly Credits)

A standard 60-second Sutradhar YouTube Short script contains ~550 Devanagari characters across 6 scenes:

$$\text{Credits per Short (Eleven v4)} = 550 \text{ characters} \times 1.0 = \mathbf{550 \text{ credits}}$$

| Production Cadence | Model | Monthly Shorts | Audio Duration | Monthly Credits Used | Quota Consumed | Remaining Buffer |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Daily Shorts (1/day)** | `eleven_v4` | **30 Shorts** | ~30.0 minutes | **16,500 credits** | **44.4%** | **20,688 credits** |
| **Daily Shorts (1/day)** | `eleven_turbo_v2_5` | **30 Shorts** | ~30.0 minutes | **8,250 credits** | **22.2%** | **28,938 credits** |
| **Maximum Monthly Limit** | `eleven_v4` | **67 Shorts** | ~67.0 minutes | **36,850 credits** | **99.1%** | 338 credits |

> **Key Finding:** Producing 1 Short every day on `eleven_v4` consumes **less than 45% of your monthly credit pool**. You have over **20,000 spare credits every month** to accommodate scene retries, script variations, and voice previews.

---

## 4. Voice Roster & Dynamic Configuration Architecture

### 4.1 Schema Definition: `config/voices.yaml`

A dedicated configuration file cleanly decouples character assignments from Python code:

```yaml
version: "2.0"
default_model: "eleven_v4"
output_format: "mp3_44100_128"

# ==============================================================================
# FIXED NARRATOR (Permanent - do not modify)
# ==============================================================================
narrator:
  name: "Viraj"
  voice_id: "uuyFQegRan8rpIQCGu9K"
  category: "professional"
  model_id: "eleven_v4"
  default_tags: "[slowly, solemn, deep]"
  settings:
    stability: 0.60
    similarity_boost: 0.80
    style: 0.05
    use_speaker_boost: true

# ==============================================================================
# CHARACTER VOICES (Populated from your ElevenLabs Library)
# ==============================================================================
characters:
  mahadev:
    name: "Viraj"
    voice_id: "uuyFQegRan8rpIQCGu9K"
    model_id: "eleven_v4"
    default_tags: "[calm, solemn, deep]"
    settings:
      stability: 0.65
      similarity_boost: 0.85
      style: 0.00
      use_speaker_boost: true

  ravana:
    name: "Niraj"
    voice_id: "k0gtD0Bbpi6hL40jfHfm"
    model_id: "eleven_v4"
    default_tags: "[arrogant, booming, furious]"
    settings:
      stability: 0.50
      similarity_boost: 0.85
      style: 0.10
      use_speaker_boost: true

  mandodari:
    name: "Kanika"
    voice_id: "xccfcojYYGnqTTxwZEDU"
    model_id: "eleven_v4"
    default_tags: "[softly, sorrowful, trembling]"
    settings:
      stability: 0.65
      similarity_boost: 0.80
      style: 0.05
      use_speaker_boost: true

  sage_narrator:
    name: "Shivank S"
    voice_id: "3zfVMgyQmfzZpm8pYvD2"
    model_id: "eleven_v4"
    default_tags: "[calm, gentle, devotional]"
    settings:
      stability: 0.60
      similarity_boost: 0.80
      style: 0.05
      use_speaker_boost: true

# Automatic Fallback: Any character not defined above defaults to Viraj
fallback_to_narrator: true
```

---

### 4.2 Interactive CLI Tool: `scripts/manage_voices.py`

This CLI tool allows you to inspect, audition, and reassign voices without manually editing files:

```bash
# 1. List all 33 voices currently in your ElevenLabs Library
python scripts/manage_voices.py list

# 2. Check current account subscription tier & remaining character balance
python scripts/manage_voices.py status

# 3. Preview/audition any voice with a tagged Hindi sentence
python scripts/manage_voices.py preview --voice-id uuyFQegRan8rpIQCGu9K --tag "[slowly, solemn, deep]"

# 4. Assign a voice from your library to a character in config/voices.yaml
python scripts/manage_voices.py assign --character ravana --voice-id k0gtD0Bbpi6hL40jfHfm

# 5. Display the active character-to-voice mapping table
python scripts/manage_voices.py show-roster
```

---

## 5. Pipeline Integration & Subtitle Synchronization

### 5.1 Per-Scene Synthesis Architecture

Each scene in `episode_plan.json` is synthesized independently:
1. **Voice Resolution:** Look up `scene.speaker_role` and `scene.character_name` in `config/voices.yaml`.
2. **Tag Injection:** If `scene.narration_text` does not already contain an opening audio tag, prepend the character's `default_tags` based on scene emotion.
3. **Smart Cache Check:** Compute MD5 hash: `hash(text + voice_id + model_id + json(settings))`.
   - If cached at `build/cache/audio/{hash}.mp3`, return immediately (0 API calls, 0 credits spent).
   - If miss, call ElevenLabs `/v1/text-to-speech/{voice_id}` with timeout (30s) and exponential backoff retry.
4. **Master Concatenation:** Concatenate all scene audio segments with dynamic narrative pauses into `build/audio/episode_audio.wav` (44.1 kHz, 16-bit PCM).
5. **Whisper Subtitle Alignment:** Pass `episode_audio.wav` to local Whisper with `language="hi"`. Whisper generates precise word-level start and end timestamps into `audio_manifest.json` for video rendering.

---

## 6. Codebase Refactoring & Cleanup Plan

### 6.1 Legacy Code to Purge

| File / Module | Action | Impact |
| :--- | :---: | :--- |
| `models/kokoro/*` | **DELETE** | Purges legacy Kokoro ONNX model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`). Frees ~350 MB disk space. |
| `scripts/audition/gemini_audition.py` | **DELETE** | Purges Google Gemini TTS audition scripts. |
| `scripts/audition/analyze_acoustic_matching.py` | **DELETE** | Purges Gemini DSP matching scripts. |
| `docs/google-ai-studio-billing-setup.md` | **ARCHIVE** | Retained for reference, removed from active build pipeline. |
| Kokoro ONNX loaders in `scripts/build_audio.py` | **PURGE** | Removes ONNX sessions, voice vector mixing, tokenizer phonemization, and SHA-256 validation. |
| `kokoro-onnx` in `requirements.txt` | **PURGE** | Removes unused runtime dependencies. |

---

### 6.2 New & Updated Modules

| Module Path | Role in Architecture |
| :--- | :--- |
| `config/voices.yaml` | Master character-to-voice registry with default Eleven v4 audio tags. |
| `scripts/manage_voices.py` | Interactive CLI tool for voice library sync, audition, and assignment. |
| `scripts/elevenlabs_engine.py` | Production ElevenLabs API client with hash caching, retry logic, and audio tag support. |
| `scripts/build_audio.py` | Refactored audio builder calling `ElevenLabsEngine` with per-scene synthesis and Whisper alignment. |
| `tests/test_build_audio.py` | Updated unit test suite replacing Kokoro test doubles with ElevenLabs mock fixtures. |
| `docs/elevenlabs-setup-guide.md` | Official setup, settings, and subscription guide. |
| `docs/MASTER_AUTOMATION_PROMPT.md` | Updated master episode production prompt enforcing Hindi-only and Eleven v4 audio tags. |

---

## 7. Phased Implementation Roadmap

```mermaid
flowchart LR
    P1["Phase 1: Config & CLI Tooling"] --> P2["Phase 2: ElevenLabs Engine & Caching"]
    P2 --> P3["Phase 3: Pipeline Integration"]
    P3 --> P4["Phase 4: Purge Legacy Kokoro/Gemini"]
    P4 --> P5["Phase 5: Full E2E Verification"]
```

- **Phase 1: Configuration & Voice Management Tooling**  
  Create `config/voices.yaml` and `scripts/manage_voices.py`. Verify API connection and print voice roster.
- **Phase 2: Core ElevenLabs Synthesis Engine**  
  Implement `scripts/elevenlabs_engine.py` with hash caching, tag handling, retry logic, and pre-flight credit checks.
- **Phase 3: Pipeline Integration in `scripts/build_audio.py`**  
  Wire `ElevenLabsEngine` into `build_episode_audio()`. Preserve dynamic pacing, pauses, BGM ducking, and Whisper subtitle alignment.
- **Phase 4: Clean Complete Removal of Legacy Code**  
  Delete `models/kokoro/` and Gemini audition files. Strip Kokoro ONNX code from `build_audio.py` and update unit tests.
- **Phase 5: End-to-End Verification & Acceptance Testing**  
  Run test suite (`pytest tests/`), synthesize a complete test episode using Viraj with audio tags, and verify Whisper subtitle alignment.
