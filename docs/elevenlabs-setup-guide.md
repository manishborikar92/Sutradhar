# ElevenLabs Setup & Best Practices Guide for Sutradhar

> **Project:** Sutradhar Hindi-Only Voice Engine  
> **Provider:** ElevenLabs (Exclusive TTS Engine)  
> **Fixed Narrator:** Viraj (`uuyFQegRan8rpIQCGu9K`)  
> **Target Language:** Pure Hindi (Devanagari script)  
> **Authoritative Documentation:**
> - [ElevenLabs Official API Documentation](https://elevenlabs.io/docs/api-reference)
> - [ElevenLabs Multilingual v2 Model Guide](https://elevenlabs.io/docs/models#multilingual-v2)
> - [ElevenLabs Voice Settings & Parameters](https://elevenlabs.io/docs/speech-synthesis/voice-settings)
> - [ElevenLabs Python SDK](https://github.com/elevenlabs/elevenlabs-python)

---

## 1. Overview & Subscription Economics

With an active **ElevenLabs Starter Subscription** (30,000–37,188 characters/month), your account has full access to the **ElevenLabs Voice Library**, allowing you to synthesize custom community voices like **Viraj** (`uuyFQegRan8rpIQCGu9K`), **Niraj**, **Kanika**, and others via the official API without HTTP 402 restrictions.

### Production Economics for Sutradhar Shorts

| Metric | Per YouTube Short | Monthly Cadence (30 Shorts) | Starter Plan Capacity (37,188 Credits) |
| :--- | :--- | :--- | :--- |
| **Script Length** | ~550 Devanagari characters | ~16,500 characters | Up to **67 complete Shorts** |
| **Credit Consumption** | ~550 credits | ~16,500 credits | ~44% of monthly quota |
| **Remaining Buffer** | — | — | **~20,688 credits buffer** for retries/QA |

> **Key Takeaway:** Your Starter plan comfortably covers a daily YouTube Short every single day with ample margin for retries and voice testing.

---

## 2. API Key Setup & Security

1. Log in to [ElevenLabs](https://elevenlabs.io/).
2. Click your profile avatar in the bottom-left corner $\rightarrow$ Select **Profile + API key**.
3. Under **API Keys**, click **Create API Key**.
4. Set permissions to standard Text-to-Speech access (read voices, generate speech).
5. Copy the API key and update your local `.env` file in the Sutradhar workspace:
   ```env
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
   ```
6. **Security Rules:**
   - Never commit `.env` to Git (it is already ignored by `.gitignore`).
   - Keep `.env.local.example` preserved and sanitized.

---

## 3. Recommended Speech Synthesis Models for Hindi

ElevenLabs offers multiple speech models. For Sutradhar's epic, mythological storytelling, choose according to your priority:

| Model ID | Recommended Use Case | Character Credit Multiplier | Hindi Audio Quality & Timbre |
| :--- | :--- | :---: | :--- |
| **`eleven_multilingual_v2`** *(Recommended Primary)* | **Production Episodes & Narration** | **1 credit / character** | **Superior:** Richest emotional depth, resonant low frequencies, accurate Devanagari pronunciation, and natural breathing cadence. |
| **`eleven_turbo_v2_5`** | **Fast Prototyping / Drafts** | **0.5 credits / character** | **Good:** Low-latency generation with 50% credit savings; slightly less dramatic weight in deep mythological dialogue. |
| **`eleven_flash_v2_5`** | **Ultra-low latency real-time** | **0.5 credits / character** | **Moderate:** Optimized for interactive agents; less suited for cinematic voiceover. |

> **Recommendation:** Standardize on **`eleven_multilingual_v2`** for all production Short renders. Its tonal gravitas for Sutradhar (Viraj) is unmatched.

---

## 4. Calibrated Voice Settings for Hindi Mythological Narration

When generating speech via the API, fine-tune the `voice_settings` payload for optimal emotional delivery:

```json
{
  "stability": 0.60,
  "similarity_boost": 0.80,
  "style": 0.05,
  "use_speaker_boost": true
}
```

### Parameter Breakdown

- **`stability` (`0.60`):**
  - Range: `0.0` (wildly expressive / variable) to `1.0` (monotone / rigid).
  - Setting this to `0.55`–`0.65` strikes the ideal balance for Hindi storytelling: it preserves Viraj’s steady, authoritative cadence while allowing natural dramatic inflection on dramatic words (e.g. *क्रोध*, *तपस्या*, *महादेव*).
- **`similarity_boost` (`0.80`):**
  - Range: `0.0` to `1.0`.
  - A value of `0.75`–`0.85` strictly preserves Viraj’s deep, resonant vocal identity and bass timbre without introducing high-frequency clipping.
- **`style` (`0.05`):**
  - Range: `0.0` to `1.0`.
  - Keep low (`0.00`–`0.10`). Setting this too high can cause unnatural breathiness or theatrical over-acting in Devanagari phonemes.
- **`use_speaker_boost` (`true`):**
  - Boosts the clarity and acoustic volume of the voice, ensuring clear separation when mixed with Sutradhar’s background music (BGM).

---

## 5. Output Audio Format

When calling `/v1/text-to-speech/{voice_id}`, specify the `output_format` query parameter:

- **`mp3_44100_128` (Default & Recommended):** High-fidelity 44.1 kHz, 128 kbps MP3. Fast network transfer, crystal-clear dialogue, seamlessly accepted by FFmpeg and MoviePy.
- **`pcm_24000` / `pcm_44100`:** Raw uncompressed PCM (16-bit little-endian). Useful for zero-compression studio mixing, but transfers larger file sizes.

---

## 6. Managing Voices in Your Library

To use any voice in Sutradhar via the API, the voice **must be present in your ElevenLabs Voice Library**.

### How to Add a Community Voice:
1. Go to [ElevenLabs Voice Library](https://elevenlabs.io/app/voice-library).
2. Search for the voice name (e.g., *Viraj*, *Kanika*, *Niraj*, *Shivank S*).
3. Click **Add to Voice Lab** / **Add to Library**.
4. The voice is now instantly accessible to your API key via its `voice_id`.

### Curated Shortlist in Your Library:
- **Viraj (Fixed Narrator):** `uuyFQegRan8rpIQCGu9K`
- **Niraj (Antagonist / Gritty Male):** `k0gtD0Bbpi6hL40jfHfm`
- **Kanika (Expressive / Regal Female):** `xccfcojYYGnqTTxwZEDU`
- **Shivank S (Ancient Chronicle / Sage):** `3zfVMgyQmfzZpm8pYvD2`
- **Raghav (Spiritual / Devotional Male):** `jwSK1od8qQ3xXXgaU8zX`
- **Kuber (Epic Historical Narrator):** `sZk20flPPGUa0sDxsZ8t`
- **Monika Sogam (Modulated Female):** `1qEiC6qsybMkmnNdVMbK`
- **Aarohi (Warm Female Companion):** `q0ZHKnI2h9hEY2Xmr7jl`

---

## 7. Account Monitoring & Quota Verification

You can check your live credit consumption at any time via the API or dashboard:

- **Web Dashboard:** [ElevenLabs Subscription Settings](https://elevenlabs.io/app/subscription)
- **API Ping (cURL):**
  ```bash
  curl -X GET "https://api.elevenlabs.io/v1/user/subscription" \
       -H "xi-api-key: YOUR_API_KEY"
  ```
  Returns:
  ```json
  {
    "tier": "starter",
    "status": "active",
    "character_count": 0,
    "character_limit": 37188
  }
  ```
