"""Agrupa pontos anômalos consecutivos em episódios (evita um alerta por medição)."""

from __future__ import annotations

import pandas as pd

EPISODE_COLUMNS = ["signal", "start", "end", "n_points", "severity", "peak_value", "reasons"]


def group_episodes(events: pd.DataFrame, gap: pd.Timedelta, key: str = "signal") -> pd.DataFrame:
    """Une eventos do mesmo ``key`` separados por no máximo ``gap``.

    ``events`` precisa ter: timestamp, ``key``, value, severity (int), reason.
    """
    if events.empty:
        return pd.DataFrame(columns=EPISODE_COLUMNS)

    rows: list[dict] = []
    for name, grp in events.sort_values("timestamp").groupby(key):
        current: list[pd.Series] = []
        for _, row in grp.iterrows():
            if current and row["timestamp"] - current[-1]["timestamp"] > gap:
                rows.append(_summarize(name, current))
                current = []
            current.append(row)
        if current:
            rows.append(_summarize(name, current))

    return pd.DataFrame(rows, columns=EPISODE_COLUMNS).sort_values("start").reset_index(drop=True)


def _summarize(name: str, rows: list[pd.Series]) -> dict:
    severity = max(int(r["severity"]) for r in rows)
    # valor de pico = primeira medição com a maior severidade do episódio
    worst = max(rows, key=lambda r: int(r["severity"]))
    # cada ponto pode trazer várias razões já concatenadas ("a; b"): separa antes de deduplicar
    reasons = sorted({part for r in rows for part in str(r["reason"]).split("; ")})
    return {
        "signal": name,
        "start": rows[0]["timestamp"],
        "end": rows[-1]["timestamp"],
        "n_points": len(rows),
        "severity": severity,
        "peak_value": float(worst["value"]),
        "reasons": "; ".join(reasons),
    }
