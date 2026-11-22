#!/usr/bin/env python3
"""Sutradhar — Audio Asset Synthesizer for SFX and BGM.

Generates broadcast-grade procedural SFX (WAV) and multi-mood BGM (MP3)
to expand the sound-effects and background music libraries for Phase 5.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path
import numpy as np
import soundfile as sf

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
SFX_DIR = ROOT_DIR / "assets" / "sfx"
BGM_DIR = ROOT_DIR / "assets" / "bgm"


def ensure_dirs() -> None:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    BGM_DIR.mkdir(parents=True, exist_ok=True)


def synth_wav(filepath: Path, samples: np.ndarray, sr: int = 44100) -> None:
    # Ensure stereo
    if samples.ndim == 1:
        samples = np.column_stack((samples, samples))
    # Normalize to -1.5 dBFS peak
    max_val = np.max(np.abs(samples))
    if max_val > 1e-6:
        peak_target = 10.0 ** (-1.5 / 20.0)
        samples = samples * (peak_target / max_val)
    sf.write(str(filepath), samples, sr, subtype="PCM_16")
    print(f"[SFX] Created {filepath.name} ({filepath.stat().st_size:,} bytes, {len(samples)/sr:.2f}s)")


def synth_mp3(filepath: Path, samples: np.ndarray, sr: int = 44100) -> None:
    wav_temp = filepath.with_suffix(".temp.wav")
    try:
        synth_wav(wav_temp, samples, sr)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(wav_temp),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(filepath),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg MP3 encoding failed: {res.stderr}")
        print(f"[BGM] Created {filepath.name} ({filepath.stat().st_size:,} bytes, {len(samples)/sr:.2f}s)")
    finally:
        if wav_temp.exists():
            wav_temp.unlink()


# ---------------------------------------------------------------------------
# SFX Generators (10 New Sound Effects)
# ---------------------------------------------------------------------------

def make_laser_strike(sr: int = 44100) -> np.ndarray:
    """Sharp celestial energy beam firing and impact."""
    dur = 1.2
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    # Exponential pitch sweep from 2600 Hz down to 140 Hz
    freqs = 140.0 + (2600.0 - 140.0) * np.exp(-t * 9.0)
    phase = 2 * np.pi * np.cumsum(freqs) / sr
    beam = np.sin(phase)

    # Initial transient crack (white noise burst)
    noise = np.random.normal(0, 1, n) * np.exp(-t * 22.0)

    # Low sub thump
    sub = np.sin(2 * np.pi * 75 * t) * np.exp(-t * 6.0)

    env = np.exp(-t * 3.5)
    sig = 0.55 * beam * env + 0.35 * noise + 0.30 * sub
    return sig


def make_crystal_shatter(sr: int = 44100) -> np.ndarray:
    """Crystalline / glass fracture burst with scattering shards."""
    dur = 1.6
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    # Resonant shard frequencies
    modes = [2850, 4200, 5600, 7100, 8900, 10500]
    shards = np.zeros(n)
    for i, f in enumerate(modes):
        delay = i * 0.015
        dt = np.maximum(0, t - delay)
        decay = 4.0 + (i % 3) * 2.5
        shards += np.sin(2 * np.pi * f * dt) * np.exp(-dt * decay) * (t >= delay)

    # High-passed impact transient
    noise = np.random.normal(0, 1, n) * np.exp(-t * 18.0)
    sig = 0.45 * shards + 0.45 * noise
    return sig


def make_thunder_rumble(sr: int = 44100) -> np.ndarray:
    """Low seismic rolling thunder and tectonic rumble."""
    dur = 3.5
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    # Low-frequency harmonics
    f1 = 45.0
    f2 = 68.0
    f3 = 92.0
    rumble = (
        0.5 * np.sin(2 * np.pi * f1 * t + 0.4 * np.sin(2 * np.pi * 3.5 * t))
        + 0.3 * np.sin(2 * np.pi * f2 * t)
        + 0.2 * np.sin(2 * np.pi * f3 * t)
    )

    # Filtered low noise
    noise = np.random.normal(0, 1, n)
    # Simple lowpass via moving average
    kernel_size = int(sr * 0.01)
    kernel = np.ones(kernel_size) / kernel_size
    filtered_noise = np.convolve(noise, kernel, mode="same")

    # Swelling and rolling envelope
    env = (np.sin(np.pi * np.clip(t / 0.5, 0, 1) * 0.5)) * np.exp(-t * 0.8)
    sig = (0.6 * rumble + 0.4 * filtered_noise) * env
    return sig


def make_conch_blast(sr: int = 44100) -> np.ndarray:
    """Sacred Shankha conch horn call with ceremonial resonance."""
    dur = 2.8
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    # Fundamental around Middle C (261.6 Hz) + rich natural harmonics
    f0 = 261.6
    vibrato = 1.0 + 0.012 * np.sin(2 * np.pi * 5.2 * t)
    sig = (
        0.45 * np.sin(2 * np.pi * f0 * vibrato * t)
        + 0.30 * np.sin(2 * np.pi * f0 * 2 * vibrato * t)
        + 0.18 * np.sin(2 * np.pi * f0 * 3 * vibrato * t)
        + 0.10 * np.sin(2 * np.pi * f0 * 4 * vibrato * t)
        + 0.06 * np.sin(2 * np.pi * f0 * 5 * vibrato * t)
    )

    # Ceremonial breath swell: rise in 0.4s, hold, gentle release
    attack = np.clip(t / 0.45, 0, 1)
    release = np.exp(-np.maximum(0, t - 1.8) * 2.5)
    env = attack * release
    return sig * env


def make_sword_clash(sr: int = 44100) -> np.ndarray:
    """Sharp divine weapon clash with metallic ringing."""
    dur = 1.4
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    # Metallic chime resonances
    ring = (
        0.45 * np.sin(2 * np.pi * 2100 * t) * np.exp(-t * 5.0)
        + 0.35 * np.sin(2 * np.pi * 3450 * t) * np.exp(-t * 6.5)
        + 0.25 * np.sin(2 * np.pi * 5120 * t) * np.exp(-t * 8.0)
    )
    # Sharp impact crack
    crack = np.random.normal(0, 1, n) * np.exp(-t * 40.0)
    return ring + 0.5 * crack


def make_magma_crack(sr: int = 44100) -> np.ndarray:
    """Tectonic bedrock fissure and subterranean grinding."""
    dur = 2.5
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    sub = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 1.5)
    grind = np.random.normal(0, 1, n) * np.sin(2 * np.pi * 120 * t) * np.exp(-t * 1.8)
    env = np.sin(np.pi * np.clip(t / 0.2, 0, 1) * 0.5) * np.exp(-t * 1.0)
    return (0.6 * sub + 0.4 * grind) * env


def make_cosmic_chime(sr: int = 44100) -> np.ndarray:
    """Cascading pentatonic chimes for divine revelations."""
    dur = 2.6
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    freqs = [784.0, 987.77, 1174.66, 1318.51, 1567.98]
    sig = np.zeros(n)
    for i, f in enumerate(freqs):
        delay = i * 0.08
        dt = np.maximum(0, t - delay)
        sig += np.sin(2 * np.pi * f * dt) * np.exp(-dt * 2.2) * (t >= delay)
    return sig * 0.35


def make_curtain_whoosh(sr: int = 44100) -> np.ndarray:
    """Heavy velvet fabric drape glide."""
    dur = 1.6
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    noise = np.random.normal(0, 1, n)
    # Bandpass filter approximation via windowed sin modulation
    carrier = np.sin(2 * np.pi * 650 * t)
    smooth = np.convolve(noise * carrier, np.ones(int(sr * 0.005)), mode="same")

    # Symmetric parabolic swell
    env = np.sin(np.pi * (t / dur)) ** 2
    return smooth * env * 0.7


def make_footstep_heavy(sr: int = 44100) -> np.ndarray:
    """Titan / Deity stone footstep impact."""
    dur = 1.1
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    sub = np.sin(2 * np.pi * 42 * t) * np.exp(-t * 5.0)
    thud = np.sin(2 * np.pi * 110 * t) * np.exp(-t * 12.0)
    noise = np.random.normal(0, 1, n) * np.exp(-t * 25.0)
    return 0.6 * sub + 0.3 * thud + 0.2 * noise


def make_energy_hum(sr: int = 44100) -> np.ndarray:
    """Sacred 108 Hz cosmic harmonic frequency hum."""
    dur = 3.0
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    f0 = 108.0
    breath = 1.0 + 0.15 * np.sin(2 * np.pi * 0.8 * t)
    sig = (
        0.55 * np.sin(2 * np.pi * f0 * t)
        + 0.30 * np.sin(2 * np.pi * f0 * 2 * t)
        + 0.15 * np.sin(2 * np.pi * f0 * 3 * t)
    ) * breath
    env = np.sin(np.pi * (t / dur))
    return sig * env


# ---------------------------------------------------------------------------
# BGM Generators (3 New Emotional Moods, 56s Loopable)
# ---------------------------------------------------------------------------

def make_wrath_confrontation(sr: int = 44100, dur: float = 56.0) -> np.ndarray:
    """Wrathful, intense war drums (132 BPM) and heavy minor drone."""
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    # 1. Heavy low drone in D minor (D2 73.4 Hz + F2 87.3 Hz + A2 110 Hz)
    drone = (
        0.35 * np.sin(2 * np.pi * 73.4 * t)
        + 0.20 * np.sin(2 * np.pi * 87.3 * t)
        + 0.15 * np.sin(2 * np.pi * 110.0 * t)
    )

    # 2. Percussive pulse at 132 BPM (interval ~ 0.4545s)
    beat_interval = 60.0 / 132.0
    beat_times = np.arange(0, dur, beat_interval)
    drums = np.zeros(n)
    for bt in beat_times:
        b_idx = int(bt * sr)
        hit_len = int(sr * 0.22)
        if b_idx + hit_len <= n:
            ht = np.linspace(0, 0.22, hit_len, False)
            hit = (
                0.6 * np.sin(2 * np.pi * 65.0 * ht) * np.exp(-ht * 14.0)
                + 0.4 * np.random.normal(0, 1, hit_len) * np.exp(-ht * 28.0)
            )
            drums[b_idx : b_idx + hit_len] += hit

    # 3. Dynamic crescendo swell
    swell = 0.75 + 0.25 * np.sin(2 * np.pi * (t / 14.0))
    sig = (drone * 0.6 + drums * 0.5) * swell
    return np.column_stack((sig, sig))


def make_sorrow_tragedy(sr: int = 44100, dur: float = 56.0) -> np.ndarray:
    """Somber, poignant raga drone and slow weeping strings for tragedy."""
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    # 1. Melancholic minor raga drone in C# (C#2 69.3 Hz, G#2 103.8 Hz, E3 164.8 Hz)
    drone = (
        0.40 * np.sin(2 * np.pi * 69.3 * t)
        + 0.25 * np.sin(2 * np.pi * 103.8 * t)
        + 0.20 * np.sin(2 * np.pi * 164.8 * t)
    )

    # 2. Weeping string melody (slow bowed vibrato)
    vibrato = 1.0 + 0.008 * np.sin(2 * np.pi * 4.8 * t)
    melody = (
        0.25 * np.sin(2 * np.pi * 277.2 * vibrato * t)  # C#4
        * (0.5 + 0.5 * np.sin(2 * np.pi * (t / 8.0)))
        + 0.20 * np.sin(2 * np.pi * 329.6 * vibrato * t)  # E4
        * (0.5 + 0.5 * np.cos(2 * np.pi * (t / 10.0)))
    )

    swell = 0.80 + 0.20 * np.sin(2 * np.pi * (t / 12.0))
    sig = (drone * 0.65 + melody * 0.4) * swell
    return np.column_stack((sig, sig))


def make_serene_blessing(sr: int = 44100, dur: float = 56.0) -> np.ndarray:
    """Devotional Tanpura drone and peaceful flute harmonics for resolution & outro."""
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)

    # 1. Radiant Tanpura drone (Sa-Pa: C3 130.8 Hz, G3 196 Hz, C4 261.6 Hz)
    tanpura = (
        0.35 * np.sin(2 * np.pi * 130.8 * t)
        + 0.25 * np.sin(2 * np.pi * 196.0 * t)
        + 0.20 * np.sin(2 * np.pi * 261.6 * t)
        + 0.10 * np.sin(2 * np.pi * 392.0 * t)
    )

    # 2. Gentle flute harmonics (pure pentatonic tones)
    flute = (
        0.22 * np.sin(2 * np.pi * 523.25 * t)  # C5
        * (0.6 + 0.4 * np.sin(2 * np.pi * (t / 6.0)))
        + 0.18 * np.sin(2 * np.pi * 659.25 * t)  # E5
        * (0.6 + 0.4 * np.cos(2 * np.pi * (t / 8.0)))
    )

    peace_env = 0.85 + 0.15 * np.sin(2 * np.pi * (t / 16.0))
    sig = (tanpura * 0.6 + flute * 0.4) * peace_env
    return np.column_stack((sig, sig))


def build_all_assets() -> None:
    ensure_dirs()
    print("\n--- Synthesizing 10 New Sound Effects (assets/sfx/) ---")
    sfx_map = {
        "laser_strike.wav": make_laser_strike,
        "crystal_shatter.wav": make_crystal_shatter,
        "thunder_rumble.wav": make_thunder_rumble,
        "conch_blast.wav": make_conch_blast,
        "sword_clash.wav": make_sword_clash,
        "magma_crack.wav": make_magma_crack,
        "cosmic_chime.wav": make_cosmic_chime,
        "curtain_whoosh.wav": make_curtain_whoosh,
        "footstep_heavy.wav": make_footstep_heavy,
        "energy_hum.wav": make_energy_hum,
    }
    for filename, fn in sfx_map.items():
        out_p = SFX_DIR / filename
        samples = fn()
        synth_wav(out_p, samples)

    print("\n--- Synthesizing 3 New Emotional BGM Tracks (assets/bgm/) ---")
    bgm_map = {
        "wrath_confrontation.mp3": make_wrath_confrontation,
        "sorrow_tragedy.mp3": make_sorrow_tragedy,
        "serene_blessing.mp3": make_serene_blessing,
    }
    for filename, fn in bgm_map.items():
        out_p = BGM_DIR / filename
        samples = fn()
        synth_mp3(out_p, samples)


if __name__ == "__main__":
    build_all_assets()
    print("\n[SUCCESS] Audio asset synthesis complete.")
