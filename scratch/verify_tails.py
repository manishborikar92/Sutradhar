import wave
import numpy as np
from pathlib import Path

for name in ["sample_01_cosmos", "sample_02_epics"]:
    wav_path = Path(f"build/samples/{name}/narration_full.wav")
    with wave.open(str(wav_path), "rb") as wf:
        n_channels = wf.getnchannels()
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        dur = n_frames / sr
        data = wf.readframes(n_frames)
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        if n_channels > 1:
            samples = samples[::n_channels]
        # Inspect final 0.40s
        final_pad_samples = int(sr * 0.40)
        final_pad_max = float(np.max(np.abs(samples[-final_pad_samples:])))
        final_100ms_max = float(np.max(np.abs(samples[-int(sr * 0.10):])))
        print(f"{name}: total narration={dur:.2f}s, last 400ms peak={final_pad_max:.5f}, last 100ms peak={final_100ms_max:.5f}")
