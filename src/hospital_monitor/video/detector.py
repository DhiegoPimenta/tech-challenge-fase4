"""Processa um vídeo com YOLOv8-pose (keypoints) e YOLOv8 (objetos) e devolve métricas e eventos.

* **Postura**: ``yolov8n-pose.pt`` fornece 17 keypoints por pessoa (mesma família de saída do
  OpenPose/COCO). Usamos a maior pessoa do quadro como paciente.
* **Objetos / áreas críticas**: ``yolov8n.pt`` (COCO) detecta objetos; se uma região crítica (ROI)
  for definida, objetos da lista de observação dentro dela geram alerta.

Importações pesadas (cv2, ultralytics) são feitas dentro das funções para manter o restante do
pacote leve e testável.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from hospital_monitor.alerts import Severity
from hospital_monitor.utils import find_runs

from .pose_metrics import (
    ExerciseProfile,
    VideoEvent,
    detect_fall,
    detect_pose_events,
    sequence_metrics,
)

ROI = tuple[float, float, float, float]  # (x1, y1, x2, y2) em frações da imagem (0-1)


@dataclass
class VideoAnalysis:
    fps: float
    duration_s: float
    frames_analyzed: int
    width: int
    height: int
    metrics: pd.DataFrame
    events: list[VideoEvent]
    object_frames: dict[str, int] = field(default_factory=dict)  # classe -> nº de quadros analisados com ela
    snapshots: dict[float, np.ndarray] = field(default_factory=dict)  # tempo(s) -> imagem BGR anotada

    def nearest_snapshot(self, t: float) -> tuple[float, np.ndarray] | None:
        if not self.snapshots:
            return None
        key = min(self.snapshots, key=lambda k: abs(k - t))
        return key, self.snapshots[key]


def load_models(models_dir: str = "models"):
    """Carrega os modelos (baixa os pesos automaticamente na 1ª execução se não existirem)."""
    from ultralytics import YOLO

    def path(name: str) -> str:
        local = os.path.join(models_dir, name)
        return local if os.path.exists(local) else name

    return YOLO(path("yolov8n-pose.pt")), YOLO(path("yolov8n.pt"))


def analyze_video(
    video_path: str,
    profile: ExerciseProfile,
    models,
    stride: int = 3,
    max_seconds: float = 120.0,
    roi: ROI | None = None,
    watch_classes: tuple[str, ...] = ("scissors", "knife"),
    snapshot_every_s: float = 1.0,
    progress_cb: Callable[[float], None] | None = None,
) -> VideoAnalysis:
    import cv2

    pose_model, obj_model = models
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Não foi possível abrir o vídeo (formato não suportado?).")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    max_frames = int(max_seconds * fps)
    limit = min(total, max_frames) if total else max_frames

    times: list[float] = []
    kpts_all: list[np.ndarray] = []
    conf_all: list[np.ndarray] = []
    boxes_all: list[np.ndarray] = []
    roi_hits: list[str | None] = []
    obj_frames: Counter = Counter()
    snapshots: dict[float, np.ndarray] = {}
    last_snap = -1e9

    idx = 0
    while idx < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % stride == 0:
            t = idx / fps
            pres = pose_model(frame, verbose=False)[0]
            kp = np.full((17, 2), np.nan)
            cf = np.zeros(17)
            box = np.full(4, np.nan)
            if pres.boxes is not None and len(pres.boxes) > 0 and pres.keypoints is not None:
                xyxy = pres.boxes.xyxy.cpu().numpy()
                areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
                k = int(np.argmax(areas))
                kp = pres.keypoints.xy[k].cpu().numpy()
                if pres.keypoints.conf is not None:
                    cf = pres.keypoints.conf[k].cpu().numpy()
                else:
                    cf = np.ones(17)
                box = xyxy[k]

            ores = obj_model(frame, verbose=False, conf=0.35)[0]
            seen: set[str] = set()
            hit: str | None = None
            for b in ores.boxes:
                name = ores.names[int(b.cls)]
                seen.add(name)
                if roi and name in watch_classes:
                    x1, y1, x2, y2 = b.xyxy[0].cpu().numpy()
                    cx, cy = (x1 + x2) / 2 / width, (y1 + y2) / 2 / height
                    if roi[0] <= cx <= roi[2] and roi[1] <= cy <= roi[3]:
                        hit = name
            obj_frames.update(seen)

            times.append(t)
            kpts_all.append(kp)
            conf_all.append(cf)
            boxes_all.append(box)
            roi_hits.append(hit)

            if t - last_snap >= snapshot_every_s:
                img = pres.plot()
                if roi:
                    cv2.rectangle(
                        img,
                        (int(roi[0] * width), int(roi[1] * height)),
                        (int(roi[2] * width), int(roi[3] * height)),
                        (0, 0, 255), 2,
                    )
                scale = 640 / max(img.shape[1], 1)
                snapshots[t] = cv2.resize(img, None, fx=scale, fy=scale) if scale < 1 else img
                last_snap = t

            if progress_cb and limit:
                progress_cb(min(idx / limit, 1.0))
        idx += 1
    cap.release()

    if not times:
        raise ValueError("Nenhum quadro foi processado.")

    t_arr = np.asarray(times)
    metrics = sequence_metrics(np.stack(kpts_all), np.stack(conf_all), t_arr)
    events = detect_pose_events(metrics, profile)
    events += detect_fall(np.stack(boxes_all), t_arr)

    dt = float(np.median(np.diff(t_arr))) if len(t_arr) > 1 else 0.0
    hits = np.array([h is not None for h in roi_hits])
    for a, b in find_runs(hits):
        name = roi_hits[a]
        events.append(
            VideoEvent(t_arr[a], t_arr[b] + dt, "objeto_em_area_critica", Severity.CRITICAL,
                       f"Objeto '{name}' dentro da área crítica", float(b - a + 1))
        )

    if progress_cb:
        progress_cb(1.0)
    return VideoAnalysis(
        fps=fps,
        duration_s=idx / fps,
        frames_analyzed=len(times),
        width=width,
        height=height,
        metrics=metrics,
        events=sorted(events, key=lambda e: e.t_start),
        object_frames=dict(obj_frames),
        snapshots=snapshots,
    )
