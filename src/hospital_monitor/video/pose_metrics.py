"""Métricas posturais a partir de keypoints COCO-17 e detecção de eventos fora do padrão.

Este módulo é **puro NumPy/pandas** (sem modelos), então é testável sem GPU e sem vídeo:
o ``detector`` extrai os keypoints com YOLOv8-pose e entrega a sequência para cá.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from hospital_monitor.alerts import Severity
from hospital_monitor.utils import find_runs

# índices COCO-17
KP = {
    "l_shoulder": 5, "r_shoulder": 6,
    "l_elbow": 7, "r_elbow": 8,
    "l_wrist": 9, "r_wrist": 10,
    "l_hip": 11, "r_hip": 12,
    "l_knee": 13, "r_knee": 14,
    "l_ankle": 15, "r_ankle": 16,
}

ANGLE_COLS = ["knee_l", "knee_r", "elbow_l", "elbow_r", "hip_l", "hip_r"]


@dataclass
class VideoEvent:
    t_start: float
    t_end: float
    kind: str
    severity: Severity
    message: str
    value: float | None = None


@dataclass
class ExerciseProfile:
    name: str
    description: str
    limits: dict[str, tuple[float, float]]  # métrica -> (mínimo, máximo) aceitáveis
    asymmetry_pairs: list[tuple[str, str]] = field(default_factory=list)
    max_asymmetry_deg: float = 25.0
    velocity_cols: list[str] = field(default_factory=list)
    max_velocity_deg_s: float = 400.0


PROFILES: dict[str, ExerciseProfile] = {
    "Agachamento (fisioterapia)": ExerciseProfile(
        name="Agachamento (fisioterapia)",
        description="Flexão de joelho limitada, tronco relativamente ereto e movimento simétrico.",
        limits={"knee_l": (55, 180), "knee_r": (55, 180), "trunk_tilt": (0, 40)},
        asymmetry_pairs=[("knee_l", "knee_r")],
        max_asymmetry_deg=25.0,
        velocity_cols=["knee_l", "knee_r"],
        max_velocity_deg_s=350.0,
    ),
    "Marcha / caminhada": ExerciseProfile(
        name="Marcha / caminhada",
        description="Tronco ereto; assimetria entre pernas é esperada, então só limites e velocidade.",
        limits={"knee_l": (90, 180), "knee_r": (90, 180), "trunk_tilt": (0, 20)},
        velocity_cols=["knee_l", "knee_r"],
        max_velocity_deg_s=700.0,
    ),
    "Livre (tronco e velocidade)": ExerciseProfile(
        name="Livre (tronco e velocidade)",
        description="Perfil genérico: inclinação de tronco e movimentos bruscos.",
        limits={"trunk_tilt": (0, 60)},
        velocity_cols=["knee_l", "knee_r", "elbow_l", "elbow_r"],
        max_velocity_deg_s=600.0,
    ),
}


# ---------------------------------------------------------------- geometria


def joint_angle(a, b, c) -> float:
    """Ângulo (graus) no ponto ``b`` formado por a-b-c. NaN se algum ponto for inválido."""
    a, b, c = (np.asarray(p, dtype=float) for p in (a, b, c))
    v1, v2 = a - b, c - b
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if not np.isfinite(denom) or denom < 1e-6:
        return float("nan")
    cos = np.clip(np.dot(v1, v2) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos)))


def trunk_tilt(l_shoulder, r_shoulder, l_hip, r_hip) -> float:
    """Inclinação do tronco em relação à vertical (0° = ereto). Eixo y da imagem aponta para baixo."""
    mid_sh = (np.asarray(l_shoulder, float) + np.asarray(r_shoulder, float)) / 2
    mid_hip = (np.asarray(l_hip, float) + np.asarray(r_hip, float)) / 2
    v = mid_sh - mid_hip
    norm = np.linalg.norm(v)
    if not np.isfinite(norm) or norm < 1e-6:
        return float("nan")
    cos = np.clip(np.dot(v, np.array([0.0, -1.0])) / norm, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos)))


def frame_metrics(kpts: np.ndarray, conf: np.ndarray, min_conf: float = 0.4) -> dict[str, float]:
    """``kpts`` (17,2) em pixels e ``conf`` (17,). Keypoints abaixo de ``min_conf`` viram NaN."""
    nan = np.array([np.nan, np.nan])

    def p(name: str) -> np.ndarray:
        i = KP[name]
        return kpts[i] if conf[i] >= min_conf else nan

    return {
        "knee_l": joint_angle(p("l_hip"), p("l_knee"), p("l_ankle")),
        "knee_r": joint_angle(p("r_hip"), p("r_knee"), p("r_ankle")),
        "elbow_l": joint_angle(p("l_shoulder"), p("l_elbow"), p("l_wrist")),
        "elbow_r": joint_angle(p("r_shoulder"), p("r_elbow"), p("r_wrist")),
        "hip_l": joint_angle(p("l_shoulder"), p("l_hip"), p("l_knee")),
        "hip_r": joint_angle(p("r_shoulder"), p("r_hip"), p("r_knee")),
        "trunk_tilt": trunk_tilt(p("l_shoulder"), p("r_shoulder"), p("l_hip"), p("r_hip")),
    }


def sequence_metrics(
    kpts: np.ndarray, conf: np.ndarray, times: np.ndarray, min_conf: float = 0.4
) -> pd.DataFrame:
    """``kpts`` (T,17,2), ``conf`` (T,17), ``times`` (T,) em segundos."""
    rows = [frame_metrics(kpts[i], conf[i], min_conf) for i in range(len(times))]
    df = pd.DataFrame(rows)
    df.insert(0, "time_s", np.asarray(times, dtype=float))
    df["detected"] = df[ANGLE_COLS + ["trunk_tilt"]].notna().any(axis=1)
    return df


# ---------------------------------------------------------------- eventos


def _frame_dt(times: np.ndarray) -> float:
    return float(np.median(np.diff(times))) if len(times) > 1 else 0.0


def detect_pose_events(
    metrics: pd.DataFrame,
    profile: ExerciseProfile,
    min_duration_s: float = 0.4,
    max_absent_s: float = 2.0,
) -> list[VideoEvent]:
    times = metrics["time_s"].to_numpy()
    dt = _frame_dt(times)
    events: list[VideoEvent] = []

    # 1) fora dos limites articulares / de tronco
    for col, (lo, hi) in profile.limits.items():
        if col not in metrics:
            continue
        x = metrics[col].to_numpy()
        with np.errstate(invalid="ignore"):
            bad = (x < lo) | (x > hi)
        for a, b in find_runs(bad):
            dur = times[b] - times[a] + dt
            if dur < min_duration_s:
                continue
            seg = x[a : b + 1]
            dev = max(lo - np.nanmin(seg), np.nanmax(seg) - hi)
            sev = Severity.CRITICAL if dev > 25 else Severity.WARNING
            events.append(
                VideoEvent(times[a], times[b] + dt, "limite_articular", sev,
                           f"{col} fora do intervalo seguro [{lo:.0f}°, {hi:.0f}°] (desvio de {dev:.0f}°)", float(dev))
            )

    # 2) assimetria entre lados
    for left, right in profile.asymmetry_pairs:
        if left in metrics and right in metrics:
            diff = (metrics[left] - metrics[right]).abs().to_numpy()
            with np.errstate(invalid="ignore"):
                bad = diff > profile.max_asymmetry_deg
            for a, b in find_runs(bad):
                dur = times[b] - times[a] + dt
                if dur >= min_duration_s:
                    events.append(
                        VideoEvent(times[a], times[b] + dt, "assimetria", Severity.WARNING,
                                   f"Assimetria {left}/{right} de até {np.nanmax(diff[a:b+1]):.0f}° "
                                   f"(limite {profile.max_asymmetry_deg:.0f}°)", float(np.nanmax(diff[a:b+1])))
                    )

    # 3) movimentos bruscos (velocidade angular)
    if dt > 0:
        for col in profile.velocity_cols:
            if col not in metrics:
                continue
            vel = np.abs(np.diff(metrics[col].to_numpy())) / dt
            with np.errstate(invalid="ignore"):
                bad = vel > profile.max_velocity_deg_s
            for a, b in find_runs(bad):
                if (b - a + 1) >= 2:  # exige 2+ amostras para ignorar ruído do keypoint
                    events.append(
                        VideoEvent(times[a], times[b + 1], "movimento_brusco", Severity.WARNING,
                                   f"Velocidade angular de {col} até {np.nanmax(vel[a:b+1]):.0f}°/s "
                                   f"(limite {profile.max_velocity_deg_s:.0f}°/s)", float(np.nanmax(vel[a:b+1])))
                    )

    # 4) paciente fora de quadro
    absent = ~metrics["detected"].to_numpy()
    for a, b in find_runs(absent):
        dur = times[b] - times[a] + dt
        if dur >= max_absent_s:
            events.append(VideoEvent(times[a], times[b] + dt, "fora_de_quadro", Severity.WARNING,
                                     f"Paciente não detectado por {dur:.1f} s", float(dur)))

    return sorted(events, key=lambda e: e.t_start)


def detect_fall(
    boxes: np.ndarray, times: np.ndarray, window_s: float = 1.5, cooldown_s: float = 3.0
) -> list[VideoEvent]:
    """Queda suspeita: caixa da pessoa passa de 'em pé' (largura/altura < 0.8) para 'deitado' (> 1.2)."""
    boxes = np.asarray(boxes, dtype=float)
    w = boxes[:, 2] - boxes[:, 0]
    h = boxes[:, 3] - boxes[:, 1]
    with np.errstate(invalid="ignore", divide="ignore"):
        aspect = w / h
    events: list[VideoEvent] = []
    last = -1e9
    for i in range(len(times)):
        if not np.isfinite(aspect[i]) or aspect[i] < 1.2 or times[i] - last < cooldown_s:
            continue
        recent = (times >= times[i] - window_s) & (times <= times[i])
        with np.errstate(invalid="ignore"):
            was_upright = np.nanmin(aspect[recent]) < 0.8 if np.isfinite(aspect[recent]).any() else False
        if was_upright:
            events.append(VideoEvent(times[i], times[i], "queda_suspeita", Severity.CRITICAL,
                                     "Queda suspeita: pessoa passou da vertical para a horizontal em poucos instantes",
                                     float(aspect[i])))
            last = times[i]
    return events
