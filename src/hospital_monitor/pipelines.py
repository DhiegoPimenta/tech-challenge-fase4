"""Cola entre os detectores e a central de alertas (usada pela UI e pelos testes)."""

from __future__ import annotations

import pandas as pd

from .alerts import Alert, Severity
from .anomalies.movement import detect_movement_anomalies
from .anomalies.prescriptions import detect_prescription_anomalies
from .anomalies.vitals import VITAL_LIMITS, detect_vitals_anomalies, vitals_episodes
from .audio.text_analytics import TextInsights
from .audio.voice_features import VoiceFinding
from .video.pose_metrics import VideoEvent

SRC_VIDEO = "Vídeo"
SRC_AUDIO = "Áudio"
SRC_VITALS = "Sinais vitais"
SRC_RX = "Prescrições"
SRC_MOVE = "Movimentação"


def analyze_vitals(df: pd.DataFrame, **kwargs) -> tuple[pd.DataFrame, pd.DataFrame, list[Alert]]:
    events = detect_vitals_anomalies(df, **kwargs)
    episodes = vitals_episodes(events)
    alerts = []
    for _, ep in episodes.iterrows():
        label = VITAL_LIMITS.get(ep["signal"], {}).get("label", ep["signal"])
        alerts.append(
            Alert(
                source=SRC_VITALS,
                severity=Severity(int(ep["severity"])),
                title=label,
                message=f"{ep['reasons']}; {ep['n_points']} medição(ões), valor de pico {ep['peak_value']:.1f}",
                when=f"{ep['start']:%d/%m %H:%M} - {ep['end']:%H:%M}",
                details={"signal": ep["signal"]},
            )
        )
    return events, episodes, alerts


def analyze_prescriptions(df: pd.DataFrame) -> tuple[pd.DataFrame, list[Alert]]:
    events = detect_prescription_anomalies(df)
    alerts = [
        Alert(
            source=SRC_RX,
            severity=Severity(int(r["severity"])),
            title=f"Prescrição de {r['drug']}",
            message=r["reason"],
            when=f"{r['timestamp']:%d/%m/%Y %H:%M}",
        )
        for _, r in events.iterrows()
    ]
    return events, alerts


def analyze_movement(df: pd.DataFrame, **kwargs) -> tuple[pd.DataFrame, list[Alert]]:
    events = detect_movement_anomalies(df, **kwargs)
    titles = {"imobilidade": "Imobilidade prolongada", "queda_suspeita": "Possível queda", "pico_atipico": "Pico de movimento"}
    alerts = [
        Alert(
            source=SRC_MOVE,
            severity=Severity(int(r["severity"])),
            title=titles.get(r["kind"], r["kind"]),
            message=r["reason"],
            when=f"{r['start']:%d/%m %H:%M} - {r['end']:%H:%M}",
        )
        for _, r in events.iterrows()
    ]
    return events, alerts


def video_alerts(events: list[VideoEvent]) -> list[Alert]:
    return [
        Alert(
            source=SRC_VIDEO,
            severity=e.severity,
            title=e.kind.replace("_", " ").capitalize(),
            message=e.message,
            when=f"{e.t_start:.1f}s - {e.t_end:.1f}s",
            details={"kind": e.kind, "value": e.value},
        )
        for e in events
    ]


def audio_alerts(findings: list[VoiceFinding], insights: TextInsights | None) -> list[Alert]:
    alerts = [
        Alert(source=SRC_AUDIO, severity=f.severity, title="Voz: " + f.kind.replace("_", " "), message=f.message)
        for f in findings
    ]
    if insights:
        for t in insights.critical_terms:
            alerts.append(
                Alert(
                    source=SRC_AUDIO,
                    severity=t["severity"],
                    title=f"Termo crítico ({t['category']})",
                    message=f"O paciente mencionou \"{t['term']}\" ({t['count']}x) na consulta.",
                )
            )
        if insights.scores.get("negative", 0) >= 0.6:
            alerts.append(
                Alert(
                    source=SRC_AUDIO,
                    severity=Severity.WARNING,
                    title="Sentimento negativo",
                    message=f"Fala predominantemente negativa ({insights.scores['negative']:.0%}), análise: {insights.source}.",
                )
            )
    return alerts
