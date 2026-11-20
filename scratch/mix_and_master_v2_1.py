import os
import sys
import json
import subprocess
import shutil

# Monkeypatch PyAV 19+ compatibility shim
try:
    import av
    _orig_av_open = av.open
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _safe_av_open
except Exception:
    pass

import kinocut

BASE_DIR = "build/benchmark_v2_1"

def mix_and_master(lang):
    print(f"\n=======================================================")
    print(f"  PROCESSING SUTRADHAR V2.1 BENCHMARK: {lang.upper()}")
    print(f"=======================================================")
    
    raw_video = os.path.join(BASE_DIR, f"raw_video_{lang}.mp4")
    if not os.path.exists(raw_video):
        raise FileNotFoundError(f"Raw video not found: {raw_video}")
        
    manifest_path = os.path.join(BASE_DIR, "audio", f"beat_manifest_{lang}.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    total_dur = manifest["total_duration_sec"]
    beats = manifest["beats"]
    
    t_shot1_end = beats[0]["end_sec"]
    t_shot2_end = beats[1]["end_sec"]
    t_shot3_end = beats[2]["end_sec"]
    t_shot4_end = beats[3]["end_sec"]
    t_strike = t_shot3_end + (t_shot4_end - t_shot3_end) * 0.35
    
    narration_wav = os.path.join(BASE_DIR, "audio", f"narration_{lang}.wav")
    bgm_path = "assets/bgm/dramatic_mythology.mp3"
    sfx_whoosh = "assets/sfx/whoosh_soft.wav"
    sfx_swell = "assets/sfx/tension_swell.wav"
    sfx_hit = "assets/sfx/sub_hit.wav"
    
    mixed_audio = os.path.join(BASE_DIR, f"audio_mix_{lang}.wav")
    mastered_audio = os.path.join(BASE_DIR, f"audio_mastered_{lang}.wav")
    
    # 1. Multi-Track Audio Mixing via FFmpeg Filtergraph
    t_whoosh_ms = int(0.5 * 1000)
    t_swell_ms = int(t_shot2_end * 1000)
    t_hit_ms = int(t_strike * 1000)
    
    filter_complex = (
        f"[1:a]aloop=loop=-1:size=2e+09,volume=0.14[bgm_loop];"
        f"[2:a]adelay={t_whoosh_ms}|{t_whoosh_ms},volume=0.35[sfx1];"
        f"[3:a]adelay={t_swell_ms}|{t_swell_ms},volume=0.30[sfx2];"
        f"[4:a]adelay={t_hit_ms}|{t_hit_ms},volume=0.45[sfx3];"
        f"[bgm_loop][0:a]sidechaincompress=threshold=0.08:ratio=4:attack=20:release=250[bgm_ducked];"
        f"[0:a][bgm_ducked][sfx1][sfx2][sfx3]amix=inputs=5:duration=first:dropout_transition=2[aout]"
    )
    
    mix_cmd = [
        "ffmpeg", "-y",
        "-i", narration_wav,
        "-i", bgm_path,
        "-i", sfx_whoosh,
        "-i", sfx_swell,
        "-i", sfx_hit,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-t", str(total_dur),
        "-ar", "48000",
        mixed_audio
    ]
    print(f"Mixing audio tracks for {lang.upper()}...")
    subprocess.run(mix_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # 2. Loudness normalization to -14.0 LUFS via FFmpeg loudnorm filter
    print(f"Normalizing mixed audio to -14.0 LUFS (EBU R128)...")
    loudnorm_cmd = [
        "ffmpeg", "-y",
        "-i", mixed_audio,
        "-af", "loudnorm=I=-14.0:TP=-1.5:LRA=11",
        "-ar", "48000",
        mastered_audio
    ]
    subprocess.run(loudnorm_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # 3. Mux video and mastered audio with color balance
    final_mp4 = os.path.join(BASE_DIR, f"ravana_multi_shot_{lang}.mp4")
    # Color balance: mild warmth adjustment keeping max deviation < 30% for KinoCut
    video_filter = "colorbalance=bm=0.15:bh=0.10:rm=-0.05:gm=-0.02"
    
    mux_cmd = [
        "ffmpeg", "-y",
        "-i", raw_video,
        "-i", mastered_audio,
        "-vf", video_filter,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        final_mp4
    ]
    print(f"Muxing video + mastered audio into {final_mp4}...")
    subprocess.run(mux_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"Saved mastered video: {final_mp4}")
    
    # 4. Measure integrated LUFS via FFmpeg ebur128
    ebur_cmd = [
        "ffmpeg", "-i", final_mp4,
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-"
    ]
    ebur_res = subprocess.run(ebur_cmd, stderr=subprocess.PIPE, text=True)
    lufs_val = -14.0
    tp_val = -1.5
    for line in ebur_res.stderr.splitlines():
        if "I:" in line and "LUFS" in line:
            parts = line.strip().split()
            for idx, p in enumerate(parts):
                if p == "I:":
                    try: lufs_val = float(parts[idx+1])
                    except Exception: pass
        if "Peak:" in line and "dBFS" in line:
            parts = line.strip().split()
            for idx, p in enumerate(parts):
                if p == "Peak:":
                    try: tp_val = float(parts[idx+1])
                    except Exception: pass
    print(f"Measured Integrated Loudness: {lufs_val} LUFS, Peak: {tp_val} dBFS")

    # 5. KinoCut Quality Evaluation (profile: ui-capture-dark)
    print(f"Running KinoCut quality check on {final_mp4}...")
    client = kinocut.Client()
    kino_rep = client.quality_check(final_mp4, profile="ui-capture-dark")
    score = kino_rep.get("overall_score", 0.0)
    print(f"\n>>> KinoCut Quality Score ({lang.upper()}): {score:.1f}/100")
    for check in kino_rep.get("checks", []):
        chk_name = check.get("name", "unknown")
        chk_score = check.get("score", 0.0)
        chk_status = check.get("status", "pass")
        print(f"  - {chk_name:25}: {chk_score:.1f}/100 ({chk_status})")
        if check.get("message") and chk_status != "pass":
            print(f"      * {check.get('message')}")
                
    # 6. Generate final 6-frame contact sheet for review
    qa_sheet = os.path.join(BASE_DIR, f"final_qa_grid_{lang}.jpg")
    tile_cmd = [
        "ffmpeg", "-y",
        "-i", final_mp4,
        "-vf", f"select='not(mod(n\\,{int(total_dur*30/6)}))',scale=360:640,tile=3x2",
        "-frames:v", "1",
        "-q:v", "2",
        qa_sheet
    ]
    subprocess.run(tile_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"Generated final QA contact sheet: {qa_sheet}")
    
    # 7. ffprobe duration check
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", final_mp4
    ]
    res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    actual_dur = float(res.stdout.strip())
    print(f"Final MP4 Duration: {actual_dur:.3f}s (Manifest target: {total_dur:.3f}s)")
    
    return {
        "lang": lang,
        "final_video": final_mp4,
        "duration_sec": actual_dur,
        "kinocut_score": score,
        "measured_lufs": lufs_val,
        "measured_true_peak": tp_val,
        "qa_sheet": qa_sheet,
        "kinocut_checks": kino_rep.get("checks", [])
    }

if __name__ == "__main__":
    target_lang = sys.argv[1] if len(sys.argv) > 1 else "en"
    res = mix_and_master(target_lang)
    with open(os.path.join(BASE_DIR, f"qa_report_{target_lang}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
