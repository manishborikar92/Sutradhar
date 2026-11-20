import os
import json
import subprocess
import soundfile as sf
import numpy as np
import kokoro_onnx

AUDITION_DIR = "build/audition/hindi_v2"
OUTPUT_DIR = "build/benchmark_v2_1/audio"
os.makedirs(AUDITION_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_PATH = "models/kokoro/kokoro-v1.0.onnx"
VOICES_PATH = "models/kokoro/voices-v1.0.bin"

kokoro = kokoro_onnx.Kokoro(MODEL_PATH, VOICES_PATH)

# Helper to get blended voice style
def get_voice(spec):
    if isinstance(spec, str):
        return kokoro.get_voice_style(spec)
    elif isinstance(spec, dict):
        blend = None
        for vname, weight in spec.items():
            vec = kokoro.get_voice_style(vname)
            if blend is None:
                blend = weight * vec
            else:
                blend += weight * vec
        return blend
    raise ValueError(f"Unknown voice spec: {spec}")

# 1. Audition candidate voices and blends
test_sentence = "लंका के स्वर्ण दरबार में, दशानन रावण क्रोध से उठ खड़ा हुआ।"

candidates = {
    "hm_omega": "hm_omega",
    "hm_psi": "hm_psi",
    "hf_alpha": "hf_alpha",
    "hf_beta": "hf_beta",
    "blend_narrator_male_A": {"hm_omega": 0.65, "hm_psi": 0.35},
    "blend_narrator_male_B": {"hm_psi": 0.60, "hm_omega": 0.40},
    "blend_narrator_female": {"hf_alpha": 0.60, "hf_beta": 0.40},
    "blend_ravana_deep": {"hm_omega": 0.85, "hm_psi": 0.15}
}

print("=== Auditioning Hindi Voices and Blends ===")
for cname, cspec in candidates.items():
    vstyle = get_voice(cspec)
    samples, sr = kokoro.create(test_sentence, voice=vstyle, speed=0.92, lang="hi")
    out_path = os.path.join(AUDITION_DIR, f"audition_{cname}.wav")
    sf.write(out_path, samples, sr)
    dur = len(samples) / sr
    print(f"Saved candidate {cname:25} -> {out_path} ({dur:.2f}s)")

# 2. Production 5-beat Hindi script
# Beat definition:
# B1: Lanka court (Narrator)
# B2: Defying gods (Narrator)
# B3: Boast (Ravana dialogue)
# B4: Shiva toe press (Narrator)
# B5: Crushed submission (Narrator)

narrator_voice = get_voice({"hm_omega": 0.65, "hm_psi": 0.35})
ravana_voice = get_voice({"hm_omega": 0.85, "hm_psi": 0.15})

beats = [
    {
        "id": "beat_1",
        "shot": "shot_1_lanka_court",
        "speaker": "narrator",
        "text": "लंका के स्वर्ण दरबार में, दशानन रावण क्रोध से उठ खड़ा हुआ।",
        "voice": narrator_voice,
        "speed": 0.94,
        "pause_after_ms": 280,
        "dsp": None
    },
    {
        "id": "beat_2",
        "shot": "shot_2_throne_advance",
        "speaker": "narrator",
        "text": "देवताओं को ललकारते हुए, उसने अपनी दृष्टि कैलाश पर टिका दी।",
        "voice": narrator_voice,
        "speed": 0.90,
        "pause_after_ms": 350,
        "dsp": None
    },
    {
        "id": "beat_3",
        "shot": "shot_3_ravana_dialogue",
        "speaker": "ravana",
        "text": "मैं इस पर्वत को जड़ से उखाड़ फेंकूँगा!",
        "voice": ravana_voice,
        "speed": 0.84,
        "pause_after_ms": 450,
        "dsp": "ravana_dialogue"
    },
    {
        "id": "beat_4",
        "shot": "shot_4_kailash_quake",
        "speaker": "narrator",
        "text": "महादेव ने केवल अपने पैर का अंगूठा दबाया, और पूरा पर्वत कांप उठा।",
        "voice": narrator_voice,
        "speed": 0.96,
        "pause_after_ms": 320,
        "dsp": None
    },
    {
        "id": "beat_5",
        "shot": "shot_5_crushed_submission",
        "speaker": "narrator",
        "text": "उस असीम भार के नीचे दबा लंकापति, शिव की स्तुति में लीन हो गया।",
        "voice": narrator_voice,
        "speed": 0.88,
        "pause_after_ms": 750,  # Verified >= 0.70s trailing silence
        "dsp": None
    }
]

print("\n=== Synthesizing 5 Hindi Beats ===")
raw_beat_files = []
processed_beat_files = []

for i, b in enumerate(beats, 1):
    raw_path = os.path.join(AUDITION_DIR, f"hi_beat_{i}_raw.wav")
    samples, sr = kokoro.create(b["text"], voice=b["voice"], speed=b["speed"], lang="hi")
    sf.write(raw_path, samples, sr)
    raw_beat_files.append((raw_path, len(samples)/sr))
    
    # Process beat with DSP if requested
    proc_path = os.path.join(AUDITION_DIR, f"hi_beat_{i}_proc.wav")
    if b["dsp"] == "ravana_dialogue":
        # Apply bass boost (+3.5dB @ 120Hz) + subtle stone hall resonance
        # aecho=0.8:0.88:35:0.25 gives theatrical depth without mud
        cmd = [
            "ffmpeg", "-y", "-i", raw_path,
            "-af", "equalizer=f=120:width_type=o:w=1.2:g=3.5,equalizer=f=250:width_type=o:w=1.0:g=1.5,aecho=0.8:0.88:35:0.25",
            proc_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        # Straight copy
        sf.write(proc_path, samples, sr)
        
    proc_data, proc_sr = sf.read(proc_path)
    proc_dur = len(proc_data) / proc_sr
    processed_beat_files.append((proc_path, proc_dur, b["pause_after_ms"]))
    print(f"Beat {i} ({b['speaker']}): core {proc_dur:.2f}s, pause {b['pause_after_ms']}ms")

# 3. Concatenate beats with exact silence gaps
print("\n=== Concatenating Beats with Controlled Pauses ===")
combined_audio = []
sr = 24000
beat_manifest_items = []
current_time = 0.0

for i, (bpath, bdur, pause_ms) in enumerate(processed_beat_files, 1):
    bdata, bsr = sf.read(bpath)
    if bsr != sr:
        raise ValueError(f"Sample rate mismatch: {bsr} vs {sr}")
    
    start_time = current_time
    combined_audio.append(bdata)
    current_time += bdur
    speech_end_time = current_time
    
    # Add silence
    pause_samples = int(sr * (pause_ms / 1000.0))
    if pause_samples > 0:
        combined_audio.append(np.zeros(pause_samples, dtype=np.float32))
        current_time += (pause_ms / 1000.0)
    
    beat_info = beats[i-1]
    beat_manifest_items.append({
        "beat_index": i,
        "beat_id": beat_info["id"],
        "shot_id": beat_info["shot"],
        "speaker": beat_info["speaker"],
        "text": beat_info["text"],
        "start_sec": round(start_time, 3),
        "speech_end_sec": round(speech_end_time, 3),
        "end_sec": round(current_time, 3),
        "duration_sec": round(current_time - start_time, 3),
        "trailing_pause_sec": round(pause_ms / 1000.0, 3)
    })

concat_array = np.concatenate(combined_audio)
raw_concat_path = os.path.join(AUDITION_DIR, "hi_concat_raw.wav")
sf.write(raw_concat_path, concat_array, sr)

# 4. Broadcast vocal mastering chain via FFmpeg
print("\n=== Applying Broadcast Vocal Mastering Chain ===")
mastered_path = os.path.join(OUTPUT_DIR, "narration_hi.wav")
# Chain:
# 1. highpass=f=80 (remove subsonic rumble)
# 2. equalizer=f=175:width_type=o:w=1.0:g=2.0 (vocal chest warmth)
# 3. equalizer=f=5000:width_type=o:w=1.5:g=-2.0 (tame harshness/sibilance)
# 4. equalizer=f=10000:width_type=o:w=1.5:g=1.5 (air)
# 5. acompressor=threshold=-18dB:ratio=2.5:attack=15:release=120
# 6. volume=0.92 (headroom)
vocal_chain = (
    "highpass=f=80,"
    "equalizer=f=175:width_type=o:w=1.0:g=2.0,"
    "equalizer=f=5000:width_type=o:w=1.5:g=-2.0,"
    "equalizer=f=10000:width_type=o:w=1.5:g=1.5,"
    "acompressor=threshold=-18dB:ratio=2.5:attack=15:release=120,"
    "volume=0.92"
)

cmd = [
    "ffmpeg", "-y", "-i", raw_concat_path,
    "-af", vocal_chain,
    "-ar", "24000",
    mastered_path
]
subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Verify final mastered audio with ffprobe
ffprobe_cmd = [
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1", mastered_path
]
res = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
mastered_duration = float(res.stdout.strip())

# Check trailing silence
final_beat = beat_manifest_items[-1]
actual_trailing_silence = mastered_duration - final_beat["speech_end_sec"]
print(f"Mastered narration_hi.wav duration: {mastered_duration:.3f}s")
print(f"Trailing silence after final spoken word: {actual_trailing_silence:.3f}s (required: >= 0.70s)")

manifest = {
    "language": "hi",
    "total_duration_sec": round(mastered_duration, 3),
    "trailing_silence_sec": round(actual_trailing_silence, 3),
    "sample_rate": 24000,
    "beats": beat_manifest_items,
    "mastering_chain": vocal_chain
}

manifest_path = os.path.join(OUTPUT_DIR, "beat_manifest_hi.json")
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f"Saved beat manifest to {manifest_path}")
