"""Detecção de anomalias nos padrões de movimentação do paciente durante a internação.

Entrada: DataFrame com ``timestamp`` e ``activity`` (intensidade de movimento por intervalo,
ex.: magnitude de acelerômetro de pulseira ou saída do vídeo; escala arbitrária >= 0).

Eventos:

* **imobilidade prolongada** fora do período noturno (risco de lesão por pressão, trombose);
* **pico atípico** de movimento (z-score robusto);
* **possível queda**: pico seguido de imobilidade logo em seguida.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from hospital_monitor.alerts import Severity
from hospital_monitor.utils import find_runs

COLUMNS = ["start", "end", "kind", "severity", "reason", "peak"]


def detect_movement_anomalies(
    df: pd.DataFrame,
    inactivity_threshold: float = 0.05,
    inactivity_min_hours: float = 3.0,
    spike_z: float = 5.0,
    night_start: int = 22,
    night_end: int = 6,
    post_spike_samples: int = 4,
) -> pd.DataFrame:
    if not {"timestamp", "activity"} <= set(df.columns):
        raise ValueError("Colunas esperadas: timestamp, activity")

    data = df.sort_values("timestamp").reset_index(drop=True).copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    act = data["activity"].astype(float).to_numpy()
    ts = data["timestamp"]
    if len(data) < 5:
        return pd.DataFrame(columns=COLUMNS)

    step = ts.diff().median()
    hours = ts.dt.hour.to_numpy()
    night = (hours >= night_start) | (hours < night_end)

    events: list[dict] = []

    # 1) imobilidade prolongada fora do período noturno
    still = (act < inactivity_threshold) & ~night
    for a, b in find_runs(still):
        duration_h = (b - a + 1) * step / pd.Timedelta(hours=1)
        if duration_h >= inactivity_min_hours:
            sev = Severity.CRITICAL if duration_h >= 2 * inactivity_min_hours else Severity.WARNING
            events.append(
                {
                    "start": ts.iloc[a],
                    "end": ts.iloc[b],
                    "kind": "imobilidade",
                    "severity": int(sev),
                    "reason": f"imobilidade por {duration_h:.1f} h em período diurno",
                    "peak": float(act[a : b + 1].mean()),
                }
            )

    # 2) picos atípicos e possíveis quedas
    med = np.median(act)
    mad = max(np.median(np.abs(act - med)), 1e-3)
    z = 0.6745 * (act - med) / mad
    spike_idx = np.where(z > spike_z)[0]
    last_spike = -10
    for i in spike_idx:
        if i - last_spike <= post_spike_samples:  # mesmo evento
            continue
        last_spike = i
        after = act[i + 1 : i + 1 + post_spike_samples]
        fall = len(after) == post_spike_samples and after.mean() < inactivity_threshold * 2
        events.append(
            {
                "start": ts.iloc[i],
                "end": ts.iloc[min(i + post_spike_samples, len(ts) - 1)],
                "kind": "queda_suspeita" if fall else "pico_atipico",
                "severity": int(Severity.CRITICAL if fall else Severity.WARNING),
                "reason": (
                    "pico de movimento seguido de imobilidade (possível queda)"
                    if fall
                    else "pico de movimento atípico"
                ),
                "peak": float(act[i]),
            }
        )

    if not events:
        return pd.DataFrame(columns=COLUMNS)
    return pd.DataFrame(events, columns=COLUMNS).sort_values("start").reset_index(drop=True)
