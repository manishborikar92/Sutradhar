import os
import json
import soundfile as sf
import numpy as np

# PyAV 19+ compatibility shim
try:
    import av
    _orig_av_open = av.open
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _safe_av_open
except Exception:
    pass

import kokoro_onnx
from faster_whisper import WhisperModel

HINDI_DIR = "build/audition/hindi_test"
os.makedirs(HINDI_DIR, exist_ok=True)

kokoro = kokoro_onnx.Kokoro("models/kokoro/kokoro-v1.0.onnx", "models/kokoro/voices-v1.0.bin")

hindi_script = (
    "रावण ने जब अपने अहंकार में आकर कैलाश पर्वत को हिलाने का दुस्साहस किया, "
    "तब महादेव शिव ने केवल अपने पैर का अंगूठा दबाया। "
    "उस असीम भार के नीचे रावण का हाथ दब गया, "
    "और उसकी भयंकर गर्जना तीनों लोकों में गूंज उठी।"
)

voices = ["hm_omega", "hm_psi", "hf_alpha", "hf_beta"]
results = {}

print("Initializing Faster-Whisper base model for evaluation...")
whisper = WhisperModel("base", device="cpu", compute_type="int8")

for voice in voices:
    print(f"\n--- Testing Hindi voice: {voice} ---")
    wav_path = os.path.join(HINDI_DIR, f"hindi_story_{voice}.wav")
    
    # Synthesize with speed=0.92
    samples, sr = kokoro.create(hindi_script, voice=voice, speed=0.92, lang="hi")
    
    # Add 450ms trailing silence to guarantee zero clipping
    tail_samples = int(sr * 0.45)
    padded = np.concatenate([samples, np.zeros(tail_samples, dtype=np.float32)])
    sf.write(wav_path, padded, sr)
    
    duration_sec = len(padded) / sr
    audio_dur_no_tail = len(samples) / sr
    print(f"Saved {wav_path} (duration: {duration_sec:.2f}s, core: {audio_dur_no_tail:.2f}s)")
    
    # Evaluate with Whisper
    segments, info = whisper.transcribe(wav_path, language="hi", beam_size=5, word_timestamps=True)
    segments_list = list(segments)
    
    transcribed_text = " ".join([seg.text.strip() for seg in segments_list])
    all_words = []
    for seg in segments_list:
        if seg.words:
            for w in seg.words:
                all_words.append({
                    "word": w.word,
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "probability": round(w.probability, 3)
                })
                
    avg_word_prob = float(np.mean([w["probability"] for w in all_words])) if all_words else 0.0
    
    results[voice] = {
        "file": wav_path,
        "duration_sec": round(duration_sec, 2),
        "core_duration_sec": round(audio_dur_no_tail, 2),
        "transcribed_text": transcribed_text,
        "whisper_language_detected": info.language,
        "whisper_language_prob": round(info.language_probability, 3),
        "word_count": len(all_words),
        "avg_word_confidence": round(avg_word_prob, 3),
        "words": all_words[:10]  # sample of first 10 words
    }
    print(f"Transcribed: '{transcribed_text}'")
    print(f"Detected lang: {info.language} ({info.language_probability:.2f}), Avg word confidence: {avg_word_prob:.3f}")

report_data = {
    "engine": "kokoro-onnx==0.6.1",
    "model_onnx": "models/kokoro/kokoro-v1.0.onnx",
    "voices_bin": "models/kokoro/voices-v1.0.bin",
    "target_script": hindi_script,
    "voices_tested": voices,
    "results": results,
    "findings": {
        "local_g2p_supported": True,
        "espeak_backend": "espeakng_loader bundled with kokoro-onnx",
        "audio_sample_rate": 24000
    }
}

report_path = os.path.join(HINDI_DIR, "hindi_feasibility_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report_data, f, indent=2, ensure_ascii=False)

print(f"\nFeasibility report written to {report_path}")
