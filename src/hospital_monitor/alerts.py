"""Modelo de alertas e central que consolida o que vem de todas as modalidades."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum

import pandas as pd


class Severity(IntEnum):
    INFO = 1
    WARNING = 2
    CRITICAL = 3

    @property
    def label(self) -> str:
        return {1: "INFO", 2: "ALERTA", 3: "CRÍTICO"}[int(self)]


@dataclass
class Alert:
    source: str  # "Vídeo", "Áudio", "Sinais vitais", "Prescrições", "Movimentação"
    severity: Severity
    title: str
    message: str
    when: str = ""  # texto livre: timestamp, intervalo ou segundo do vídeo
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.label
        return d


class AlertCenter:
    """Guarda os alertas da sessão. Reanalisar uma fonte substitui os alertas antigos dela."""

    def __init__(self) -> None:
        self._alerts: list[Alert] = []

    def add(self, alert: Alert) -> None:
        self._alerts.append(alert)

    def replace_source(self, source: str, alerts: list[Alert]) -> None:
        self._alerts = [a for a in self._alerts if a.source != source] + list(alerts)

    def clear(self) -> None:
        self._alerts = []

    @property
    def alerts(self) -> list[Alert]:
        return sorted(self._alerts, key=lambda a: (-int(a.severity), a.source, a.when))

    def __len__(self) -> int:
        return len(self._alerts)

    def counts(self) -> dict[str, int]:
        return {
            s.label: sum(1 for a in self._alerts if a.severity == s)
            for s in (Severity.CRITICAL, Severity.WARNING, Severity.INFO)
        }

    def to_dataframe(self) -> pd.DataFrame:
        cols = ["severity", "source", "title", "message", "when"]
        if not self._alerts:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame([a.to_dict() for a in self.alerts])[cols]

    def format_text(self, min_severity: Severity = Severity.WARNING, limit: int = 20) -> str:
        selected = [a for a in self.alerts if a.severity >= min_severity][:limit]
        if not selected:
            return "Nenhum alerta acima do nível mínimo."
        lines = [f"**{len(selected)} alerta(s) clínico(s)**"]
        for a in selected:
            lines.append(f"- [{a.severity.label}] {a.source} - {a.title}: {a.message} ({a.when})")
        return "\n".join(lines)

    def dispatch_webhook(
        self, url: str, min_severity: Severity = Severity.WARNING, timeout: int = 10
    ) -> int:
        """Envia um resumo para um webhook (Teams/Slack/Logic App). Retorna o nº de alertas enviados."""
        import requests

        selected = [a for a in self.alerts if a.severity >= min_severity]
        if not selected:
            return 0
        resp = requests.post(
            url,
            json={"text": self.format_text(min_severity), "alerts": [a.to_dict() for a in selected]},
            timeout=timeout,
        )
        resp.raise_for_status()
        return len(selected)
