# -*- coding: utf-8 -*-
"""Export one 30 s mono mixture magnitude spectrogram for Octave IALM cross-check."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

import librosa  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

OUT = Path(r"D:\FYP_HKBU_runs\rerun_20261030_2358\rpca_octave")
SONG = "Al James - Schoolboy Facination"
DUR = 30
SR = 44100
N_FFT = 2048
HOP = 512


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wav = _paths.MUSDB18_ROOT / "test" / SONG / "mixture.wav"
    y, sr = sf.read(str(wav), frames=DUR * SR, dtype="float32", always_2d=True)
    x = y.mean(axis=1)
    assert sr == SR, sr
    X = librosa.stft(x, n_fft=N_FFT, hop_length=HOP)
    mag = np.abs(X).astype(np.float32)
    m, t = mag.shape
    np.save(OUT / "mag.npy", mag)
    mag.tofile(OUT / "mag_f32.bin")
    np.save(OUT / "mix.npy", x)
    meta = {"song": SONG, "sr": SR, "n_fft": N_FFT, "hop": HOP,
            "shape": [m, t], "frames": t, "dur_s": len(x) / SR,
            "wav": str(wav), "wav_bytes": wav.stat().st_size}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("exported", m, "x", t, "->", OUT)


if __name__ == "__main__":
    main()
