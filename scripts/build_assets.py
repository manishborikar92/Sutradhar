"""Sutradhar Asset Generator — 48kHz Stereo BGM Beds & Acoustic Foley Library (Phase 3).

Generates:
1. 2.5-Minute (165s) Theatrical Indian Instrumental BGM Beds at 48kHz Stereo:
   - theatrical_narrative.mp3
   - tense_confrontation.mp3
   - divine_cosmic.mp3
   - melancholy_tragedy.mp3
2. Authentic 48kHz Stereo Acoustic Foley SFX:
   - metal_clang.wav
   - conch_blast.wav
   - chain_rattle.wav
   - foot_thud.wav
   - fire_crackle.wav
   - crystal_shatter.wav
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BGM_DIR = REPO_ROOT / "assets" / "bgm"
SFX_DIR = REPO_ROOT / "assets" / "sfx"


def run_ffmpeg(args: list[str]) -> None:
    """Execute FFmpeg command cleanly."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg command failed: {res.stderr}\nCommand: {' '.join(cmd)}")


def build_bgm_tracks() -> None:
    """Generate 165-second, 48kHz stereo cinematic Indian instrumental beds."""
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    duration_s = 165  # 2 minutes 45 seconds

    # 1. Theatrical Narrative (Majestic Tanpura Drone C# + Pa, Temple Gongs, Sitar Resonance)
    theatrical_path = BGM_DIR / "theatrical_narrative.mp3"
    print(f"[INFO] Generating {theatrical_path.name} ({duration_s}s, 48kHz Stereo)...")
    filter_theatrical = (
        f"anoisesrc=d={duration_s}:c=pink:r=48000:a=0.008[ambient];"
        f"sine=f=138.59:r=48000:d={duration_s}[tanpura_sa];"      # C#3 Root
        f"sine=f=207.65:r=48000:d={duration_s}[tanpura_pa];"      # G#3 Fifth
        f"sine=f=277.18:r=48000:d={duration_s}[tanpura_sa_oct];"  # C#4 Octave
        f"sine=f=554.37:r=48000:d={duration_s}[flute_harmonic];"  # C#5 Flute
        f"[tanpura_sa]volume=0.22,tremolo=f=0.4:d=0.3[t1];"
        f"[tanpura_pa]volume=0.18,tremolo=f=0.5:d=0.25[t2];"
        f"[tanpura_sa_oct]volume=0.14,tremolo=f=0.3:d=0.35[t3];"
        f"[flute_harmonic]volume=0.07,tremolo=f=0.6:d=0.4[t4];"
        f"[t1][t2][t3][t4][ambient]amix=inputs=5:normalize=0[drone];"
        f"[drone]aecho=0.8:0.88:60|120:0.4|0.3,apulsator=mode=sine:hz=0.08:width=0.6:offset_r=0.5[stereo_bed];"
        f"[stereo_bed]afade=t=in:st=0:d=2.5,afade=t=out:st={duration_s - 3}:d=3.0,aformat=sample_rates=48000:channel_layouts=stereo[out]"
    )
    run_ffmpeg([
        "-filter_complex", filter_theatrical,
        "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", str(theatrical_path)
    ])

    # 2. Tense Confrontation (Pounding Martial Drums, Aggressive Brass Drone, Dark Swell)
    confrontation_path = BGM_DIR / "tense_confrontation.mp3"
    print(f"[INFO] Generating {confrontation_path.name} ({duration_s}s, 48kHz Stereo)...")
    filter_confrontation = (
        f"anoisesrc=d={duration_s}:c=brown:r=48000:a=0.02[sub_rumble];"
        f"sine=f=73.42:r=48000:d={duration_s}[bass_d];"          # D2 Low War Drone
        f"sine=f=110.00:r=48000:d={duration_s}[brass_a];"        # A2 Fifth
        f"sine=f=146.83:r=48000:d={duration_s}[brass_d_oct];"    # D3 Octave
        f"[bass_d]volume=0.30,tremolo=f=1.2:d=0.5[w1];"
        f"[brass_a]volume=0.22,tremolo=f=1.6:d=0.4[w2];"
        f"[brass_d_oct]volume=0.18,tremolo=f=0.8:d=0.6[w3];"
        f"[w1][w2][w3][sub_rumble]amix=inputs=4:normalize=0[raw_war];"
        f"[raw_war]aecho=0.8:0.9:80|160:0.5|0.35,apulsator=mode=sine:hz=0.2:width=0.8:offset_r=0.4[stereo_war];"
        f"[stereo_war]afade=t=in:st=0:d=1.5,afade=t=out:st={duration_s - 3}:d=3.0,aformat=sample_rates=48000:channel_layouts=stereo[out]"
    )
    run_ffmpeg([
        "-filter_complex", filter_confrontation,
        "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", str(confrontation_path)
    ])

    # 3. Divine Cosmic (Celestial Tanpura, Shani Ethereal Harmonics, Astral Chimes)
    cosmic_path = BGM_DIR / "divine_cosmic.mp3"
    print(f"[INFO] Generating {cosmic_path.name} ({duration_s}s, 48kHz Stereo)...")
    filter_cosmic = (
        f"anoisesrc=d={duration_s}:c=pink:r=48000:a=0.006[ether];"
        f"sine=f=164.81:r=48000:d={duration_s}[ethereal_e];"     # E3
        f"sine=f=246.94:r=48000:d={duration_s}[ethereal_b];"     # B3
        f"sine=f=329.63:r=48000:d={duration_s}[ethereal_e_oct];" # E4
        f"sine=f=659.25:r=48000:d={duration_s}[bell_overtone];"  # E5 Bell
        f"[ethereal_e]volume=0.20,tremolo=f=0.2:d=0.3[c1];"
        f"[ethereal_b]volume=0.16,tremolo=f=0.25:d=0.3[c2];"
        f"[ethereal_e_oct]volume=0.12,tremolo=f=0.15:d=0.4[c3];"
        f"[bell_overtone]volume=0.06,tremolo=f=0.4:d=0.5[c4];"
        f"[c1][c2][c3][c4][ether]amix=inputs=5:normalize=0[raw_cosmic];"
        f"[raw_cosmic]aecho=0.85:0.92:150|300:0.5|0.4,apulsator=mode=sine:hz=0.05:width=0.7:offset_r=0.6[stereo_cosmic];"
        f"[stereo_cosmic]afade=t=in:st=0:d=2.0,afade=t=out:st={duration_s - 3}:d=3.0,aformat=sample_rates=48000:channel_layouts=stereo[out]"
    )
    run_ffmpeg([
        "-filter_complex", filter_cosmic,
        "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", str(cosmic_path)
    ])

    # 4. Melancholy Tragedy (Sorrowful Karmic Drone, Low Bowed Sarangi resonance)
    tragedy_path = BGM_DIR / "melancholy_tragedy.mp3"
    print(f"[INFO] Generating {tragedy_path.name} ({duration_s}s, 48kHz Stereo)...")
    filter_tragedy = (
        f"anoisesrc=d={duration_s}:c=brown:r=48000:a=0.012[somber_air];"
        f"sine=f=98.00:r=48000:d={duration_s}[g_root];"          # G2
        f"sine=f=116.54:r=48000:d={duration_s}[bb_minor];"       # Bb2 (Minor Third - Melancholy)
        f"sine=f=146.83:r=48000:d={duration_s}[d_fifth];"        # D3
        f"sine=f=233.08:r=48000:d={duration_s}[bb_high];"        # Bb3
        f"[g_root]volume=0.25,tremolo=f=0.3:d=0.3[s1];"
        f"[bb_minor]volume=0.20,tremolo=f=0.35:d=0.35[s2];"
        f"[d_fifth]volume=0.15,tremolo=f=0.25:d=0.3[s3];"
        f"[bb_high]volume=0.08,tremolo=f=0.4:d=0.4[s4];"
        f"[s1][s2][s3][s4][somber_air]amix=inputs=5:normalize=0[raw_tragedy];"
        f"[raw_tragedy]aecho=0.82:0.9:100|200:0.45|0.35,apulsator=mode=sine:hz=0.07:width=0.65:offset_r=0.4[stereo_tragedy];"
        f"[stereo_tragedy]afade=t=in:st=0:d=2.0,afade=t=out:st={duration_s - 3}:d=3.0,aformat=sample_rates=48000:channel_layouts=stereo[out]"
    )
    run_ffmpeg([
        "-filter_complex", filter_tragedy,
        "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", str(tragedy_path)
    ])

    # Replicate to legacy aliases with full 165s length to permanently eradicate the 56s loop problem
    aliases = {
        "dramatic_mythology.mp3": theatrical_path,
        "epic_history.mp3": theatrical_path,
        "wrath_confrontation.mp3": confrontation_path,
        "cosmic_mystery.mp3": cosmic_path,
        "serene_blessing.mp3": cosmic_path,
        "sorrow_tragedy.mp3": tragedy_path,
    }
    for alias_name, src in aliases.items():
        shutil.copy2(src, BGM_DIR / alias_name)
    print(f"[INFO] Successfully built 4 canonical BGM beds and 6 extended aliases ({duration_s}s, 48kHz stereo).")


def build_sfx_library() -> None:
    """Generate authentic 48kHz stereo Foley sound effects."""
    SFX_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Metal Clang (Gada impact / armor strike)
    metal_path = SFX_DIR / "metal_clang.wav"
    print(f"[INFO] Generating {metal_path.name} (48kHz Stereo)...")
    run_ffmpeg([
        "-filter_complex",
        "sine=f=440:d=1.5[h1];sine=f=880:d=1.5[h2];sine=f=1320:d=1.5[h3];anoisesrc=d=0.08:c=white:r=48000:a=0.3[transient];"
        "[h1]volume=0.4,afade=t=out:st=0.05:d=1.4[s1];"
        "[h2]volume=0.25,afade=t=out:st=0.03:d=1.2[s2];"
        "[h3]volume=0.15,afade=t=out:st=0.02:d=0.8[s3];"
        "[s1][s2][s3][transient]amix=inputs=4:normalize=0[mix];"
        "[mix]aecho=0.8:0.7:40|80:0.5|0.3,aformat=sample_rates=48000:channel_layouts=stereo[out]",
        "-map", "[out]", "-c:a", "pcm_s24le", str(metal_path)
    ])

    # 2. Foot Thud (Heavy royal boot / planetary step)
    foot_path = SFX_DIR / "foot_thud.wav"
    print(f"[INFO] Generating {foot_path.name} (48kHz Stereo)...")
    run_ffmpeg([
        "-filter_complex",
        "sine=f=65:d=0.9[sub];anoisesrc=d=0.06:c=brown:r=48000:a=0.4[thud_impact];"
        "[sub]volume=0.5,afade=t=out:st=0.05:d=0.8[s1];"
        "[s1][thud_impact]amix=inputs=2:normalize=0[mix];"
        "[mix]aecho=0.8:0.6:30|60:0.4|0.2,aformat=sample_rates=48000:channel_layouts=stereo[out]",
        "-map", "[out]", "-c:a", "pcm_s24le", str(foot_path)
    ])

    # 3. Chain Rattle (Metallic link jingle & drag)
    chain_path = SFX_DIR / "chain_rattle.wav"
    print(f"[INFO] Generating {chain_path.name} (48kHz Stereo)...")
    run_ffmpeg([
        "-filter_complex",
        "anoisesrc=d=1.8:c=white:r=48000:a=0.15[metal_scrape];"
        "sine=f=1200:d=1.8[jingle1];sine=f=1750:d=1.8[jingle2];"
        "[jingle1]volume=0.12,tremolo=f=8.0:d=0.8[j1];"
        "[jingle2]volume=0.08,tremolo=f=12.0:d=0.9[j2];"
        "[metal_scrape]highpass=f=2000,volume=0.18,tremolo=f=6.0:d=0.6[j3];"
        "[j1][j2][j3]amix=inputs=3:normalize=0[mix];"
        "[mix]afade=t=out:st=1.0:d=0.8,aecho=0.8:0.7:50|100:0.3|0.2,aformat=sample_rates=48000:channel_layouts=stereo[out]",
        "-map", "[out]", "-c:a", "pcm_s24le", str(chain_path)
    ])

    # 4. Fire Crackle (Temple havan brazier flames & sparks)
    fire_path = SFX_DIR / "fire_crackle.wav"
    print(f"[INFO] Generating {fire_path.name} (48kHz Stereo)...")
    run_ffmpeg([
        "-filter_complex",
        "anoisesrc=d=2.5:c=brown:r=48000:a=0.2[flame_body];"
        "anoisesrc=d=2.5:c=white:r=48000:a=0.08[sparks];"
        "[flame_body]lowpass=f=400,volume=0.25,tremolo=f=3.5:d=0.5[f1];"
        "[sparks]highpass=f=3500,volume=0.15,tremolo=f=15.0:d=0.9[f2];"
        "[f1][f2]amix=inputs=2:normalize=0[mix];"
        "[mix]afade=t=in:st=0:d=0.3,afade=t=out:st=2.0:d=0.5,aformat=sample_rates=48000:channel_layouts=stereo[out]",
        "-map", "[out]", "-c:a", "pcm_s24le", str(fire_path)
    ])

    # 5. Conch Blast (Sacred Shankha Prologue Call)
    conch_path = SFX_DIR / "conch_blast.wav"
    print(f"[INFO] Generating {conch_path.name} (48kHz Stereo)...")
    run_ffmpeg([
        "-filter_complex",
        "sine=f=261.63:d=3.0[c_root];sine=f=523.25:d=3.0[c_octave];sine=f=784.88:d=3.0[c_fifth];"
        "[c_root]volume=0.35,afade=t=in:st=0:d=0.4,afade=t=out:st=2.2:d=0.8[c1];"
        "[c_octave]volume=0.25,afade=t=in:st=0:d=0.4,afade=t=out:st=2.2:d=0.8[c2];"
        "[c_fifth]volume=0.15,afade=t=in:st=0:d=0.5,afade=t=out:st=2.0:d=1.0[c3];"
        "[c1][c2][c3]amix=inputs=3:normalize=0[mix];"
        "[mix]aecho=0.85:0.8:100|200:0.5|0.35,aformat=sample_rates=48000:channel_layouts=stereo[out]",
        "-map", "[out]", "-c:a", "pcm_s24le", str(conch_path)
    ])

    print("[INFO] Successfully built 48kHz stereo authentic Foley SFX library.")


if __name__ == "__main__":
    build_bgm_tracks()
    build_sfx_library()
