"""Detecção de anomalias na evolução de prescrições.

Entrada: DataFrame com ``timestamp, drug, dose_mg, frequency_per_day``.

Regras (explicáveis, adequadas a poucos dados por paciente):

* salto ou queda brusca da dose diária em relação à prescrição anterior da mesma droga;
* dose diária acima do máximo de referência;
* combinações de fármacos com risco conhecido prescritas em uma janela de dias.

As tabelas abaixo são **ilustrativas** (projeto acadêmico) e não substituem uma base de
interações medicamentosas validada.
"""

from __future__ import annotations

import pandas as pd

from hospital_monitor.alerts import Severity

MAX_DAILY_MG = {
    "paracetamol": 4000,
    "dipirona": 4000,
    "ibuprofeno": 3200,
    "tramadol": 400,
    "morfina": 200,
}

RISKY_PAIRS = [
    ("varfarina", "ibuprofeno", "risco aumentado de sangramento"),
    ("varfarina", "aspirina", "risco aumentado de sangramento"),
    ("enalapril", "espironolactona", "risco de hipercalemia"),
    ("tramadol", "fluoxetina", "risco de síndrome serotoninérgica"),
    ("sildenafila", "nitroglicerina", "risco de hipotensão grave"),
]

COLUMNS = ["timestamp", "drug", "severity", "reason"]


def detect_prescription_anomalies(df: pd.DataFrame, interaction_window_days: int = 7) -> pd.DataFrame:
    required = {"timestamp", "drug", "dose_mg", "frequency_per_day"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colunas ausentes: {sorted(missing)}")

    data = df.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data["drug"] = data["drug"].astype(str).str.strip().str.lower()
    data["daily_mg"] = data["dose_mg"].astype(float) * data["frequency_per_day"].astype(float)
    data = data.sort_values("timestamp").reset_index(drop=True)

    events: list[dict] = []

    for drug, grp in data.groupby("drug"):
        prev = None
        for _, row in grp.iterrows():
            daily = row["daily_mg"]
            limit = MAX_DAILY_MG.get(drug)
            if limit and daily > limit:
                events.append(
                    _ev(row, Severity.CRITICAL, f"dose diária de {daily:.0f} mg excede o máximo de referência ({limit} mg)")
                )
            if prev is not None and prev > 0:
                ratio = daily / prev
                if ratio >= 2.0 or ratio <= 0.25:
                    sev = Severity.CRITICAL
                elif ratio >= 1.5 or ratio <= 0.5:
                    sev = Severity.WARNING
                else:
                    sev = None
                if sev is not None:
                    verb = "aumento" if ratio > 1 else "redução"
                    events.append(
                        _ev(row, sev, f"{verb} brusco da dose diária: {prev:.0f} mg -> {daily:.0f} mg (x{ratio:.2f})")
                    )
            prev = daily

    flagged_pairs: set[tuple[str, str]] = set()
    window = pd.Timedelta(days=interaction_window_days)
    for _, row in data.iterrows():
        recent = data[(data["timestamp"] <= row["timestamp"]) & (data["timestamp"] >= row["timestamp"] - window)]
        recent_drugs = set(recent["drug"])
        for a, b, why in RISKY_PAIRS:
            if {a, b} <= recent_drugs and row["drug"] in (a, b) and (a, b) not in flagged_pairs:
                flagged_pairs.add((a, b))
                events.append(_ev(row, Severity.WARNING, f"combinação {a} + {b}: {why}"))

    if not events:
        return pd.DataFrame(columns=COLUMNS)
    return pd.DataFrame(events, columns=COLUMNS).sort_values("timestamp").reset_index(drop=True)


def _ev(row: pd.Series, severity: Severity, reason: str) -> dict:
    return {
        "timestamp": row["timestamp"],
        "drug": row["drug"],
        "severity": int(severity),
        "reason": reason,
    }
