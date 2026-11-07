"""Leitura e conversão de áudio (o Azure Speech espera WAV PCM 16 kHz mono)."""

from __future__ import annotations

import io
from math import gcd

import numpy as np


def load_audio(data: bytes) -> tuple[np.ndarray, int]:
    """Decodifica WAV/FLAC/OGG em um vetor mono float32 e a taxa de amostragem."""
    import soundfile as sf

    y, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    return y.mean(axis=1), int(sr)


def resample(y: np.ndarray, sr: int, target: int = 16000) -> np.ndarray:
    if sr == target:
        return y
    from scipy.signal import resample_poly

    g = gcd(sr, target)
    return resample_poly(y, target // g, sr // g).astype(np.float32)


def to_wav_16k_mono(y: np.ndarray, sr: int) -> bytes:
    """Serializa o áudio como WAV PCM16 16 kHz mono."""
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, resample(y, sr, 16000), 16000, format="WAV", subtype="PCM_16")
    return buf.getvalue()
