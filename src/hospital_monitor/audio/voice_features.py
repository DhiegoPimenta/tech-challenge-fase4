"""Características vocais calculadas com NumPy (sem depender de librosa).

O objetivo é gerar **indicadores** relacionados a fadiga, dificuldade respiratória e fala
alterada (disartria), não um diagnóstico:

* proporção de silêncio, nº e duração de pausas  -> fala fragmentada / respiração entrecortada;
* variabilidade de energia (dB)                  -> fala monótona e fraca (fadiga);
* f0 médio, desvio de f0 e jitter aproximado     -> instabilidade vocal (rouquidão, disartria);
* palavras por minuto (usa a transcrição)        -> lentificação da fala.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hospital_monitor.alerts import Severity
from hospital_monitor.utils import find_runs

FRAME_S = 0.030
HOP_S = 0.015
MIN_PAUSE_S = 0.25
F0_MIN, F0_MAX = 75.0, 400.0


@dataclass
class VoiceFeatures:
    duration_s: float
    rms_mean_db: float
    rms_std_db: float
    silence_ratio: float
    n_pauses: int
    longest_pause_s: float
    pauses_per_min: float
    f0_mean_hz: float
    f0_std_hz: float
    jitter_pct: float
    voiced_ratio: float


@dataclass
class VoiceFinding:
    kind: str
    severity: Severity
    message: str


DEFAULT_THRESHOLDS = {
    "silence_ratio": 0.45,
    "longest_pause_s": 3.0,
    "pauses_per_min": 20.0,
    "rms_std_db": 3.0,
    "f0_std_hz": 15.0,
    "jitter_pct": 2.0,
    "wpm_low": 90.0,
}


def extract_voice_features(y: np.ndarray, sr: int, max_seconds: float = 180.0) -> VoiceFeatures:
    y = np.asarray(y, dtype=np.float32)[: int(max_seconds * sr)]
    duration = len(y) / sr
    flen, hop = int(FRAME_S * sr), int(HOP_S * sr)
    if len(y) < flen * 3:
        raise ValueError("Áudio muito curto para análise (mínimo ~0,1 s).")

    frames = np.lib.stride_tricks.sliding_window_view(y, flen)[::hop]
    energy = (frames.astype(np.float64) ** 2).mean(axis=1)
    rms_db = 10 * np.log10(energy + 1e-12)

    ref = np.percentile(rms_db, 95)
    silent = rms_db < (ref - 30.0)  # silêncio = 30 dB abaixo do nível típico de fala
    min_frames = int(MIN_PAUSE_S / HOP_S)
    pauses = [(a, b) for a, b in find_runs(silent) if (b - a + 1) >= min_frames]
    pause_lengths = [(b - a + 1) * HOP_S for a, b in pauses]

    voiced_frames = frames[~silent]
    f0 = _estimate_f0(voiced_frames, sr)
    if len(f0) >= 3:
        periods = 1.0 / f0
        jitter = float(np.mean(np.abs(np.diff(periods))) / np.mean(periods) * 100)
        f0_mean, f0_std = float(f0.mean()), float(f0.std())
    else:
        jitter, f0_mean, f0_std = float("nan"), float("nan"), float("nan")

    speech_db = rms_db[~silent]
    return VoiceFeatures(
        duration_s=duration,
        rms_mean_db=float(speech_db.mean()) if len(speech_db) else float("nan"),
        rms_std_db=float(speech_db.std()) if len(speech_db) else float("nan"),
        silence_ratio=float(silent.mean()),
        n_pauses=len(pauses),
        longest_pause_s=float(max(pause_lengths)) if pause_lengths else 0.0,
        pauses_per_min=len(pauses) / (duration / 60.0) if duration > 0 else 0.0,
        f0_mean_hz=f0_mean,
        f0_std_hz=f0_std,
        jitter_pct=jitter,
        voiced_ratio=float(len(f0) / max(len(voiced_frames), 1)) if len(voiced_frames) else 0.0,
    )


def _estimate_f0(frames: np.ndarray, sr: int) -> np.ndarray:
    """f0 por autocorrelação (via FFT) em frames de fala. Descarta frames sem periodicidade."""
    if len(frames) == 0:
        return np.array([])
    n = frames.shape[1]
    x = frames.astype(np.float64)
    x = (x - x.mean(axis=1, keepdims=True)) * np.hanning(n)
    spec = np.fft.rfft(x, n=2 * n, axis=1)
    ac = np.fft.irfft(np.abs(spec) ** 2, axis=1)[:, :n]
    ac = ac / (ac[:, [0]] + 1e-12)
    lo, hi = int(sr / F0_MAX), min(int(sr / F0_MIN), n - 1)
    seg = ac[:, lo:hi]
    lag = seg.argmax(axis=1) + lo
    peak = seg.max(axis=1)
    return sr / lag[peak > 0.3]


def assess_voice(
    feat: VoiceFeatures, words_per_min: float | None = None, thresholds: dict | None = None
) -> list[VoiceFinding]:
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    out: list[VoiceFinding] = []

    if feat.silence_ratio > th["silence_ratio"]:
        out.append(VoiceFinding("silencio", Severity.WARNING,
                                f"Alta proporção de silêncio ({feat.silence_ratio:.0%}): fala escassa ou lenta, possível fadiga."))
    if feat.longest_pause_s > th["longest_pause_s"]:
        out.append(VoiceFinding("pausa_longa", Severity.WARNING,
                                f"Pausa longa de {feat.longest_pause_s:.1f} s durante a fala."))
    if feat.pauses_per_min > th["pauses_per_min"]:
        out.append(VoiceFinding("fala_fragmentada", Severity.WARNING,
                                f"{feat.pauses_per_min:.0f} pausas/min: fala entrecortada, possível dificuldade respiratória."))
    if not np.isnan(feat.rms_std_db) and feat.rms_std_db < th["rms_std_db"]:
        out.append(VoiceFinding("energia_monotona", Severity.INFO,
                                f"Pouca variação de intensidade ({feat.rms_std_db:.1f} dB): fala monótona/fraca."))
    if not np.isnan(feat.f0_std_hz) and feat.f0_std_hz < th["f0_std_hz"]:
        out.append(VoiceFinding("pitch_monotono", Severity.INFO,
                                f"Pouca variação de tom (desvio de f0 {feat.f0_std_hz:.1f} Hz): voz monótona, possível fadiga."))
    if not np.isnan(feat.jitter_pct) and feat.jitter_pct > th["jitter_pct"]:
        out.append(VoiceFinding("jitter", Severity.WARNING,
                                f"Instabilidade vocal elevada (jitter ~{feat.jitter_pct:.1f}%): possível rouquidão/disartria."))
    if words_per_min is not None and words_per_min < th["wpm_low"]:
        out.append(VoiceFinding("fala_lenta", Severity.WARNING,
                                f"Fala lenta ({words_per_min:.0f} palavras/min)."))
    return out
