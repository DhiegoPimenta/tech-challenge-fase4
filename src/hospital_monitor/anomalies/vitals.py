"""Detecção de anomalias em séries temporais de sinais vitais.

Três detectores complementares, combinados por (timestamp, sinal):

1. **Regras clínicas** - limites de referência (aviso e crítico) por sinal.
2. **Z-score robusto em janela móvel** (mediana/MAD) - pega variações abruptas em relação ao
   padrão recente do próprio paciente, mesmo dentro da faixa "normal" da população.
3. **Isolation Forest multivariado** - pega combinações incomuns (ex.: FC alta com SpO2 caindo),
   usando os valores e suas variações (derivada).

Os limites são ilustrativos para fins acadêmicos; não substituem protocolos clínicos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from hospital_monitor.alerts import Severity

from .episodes import group_episodes

VITAL_LIMITS: dict[str, dict] = {
    "hr": {"label": "Frequência cardíaca (bpm)", "warn": (50, 110), "crit": (40, 130)},
    "sbp": {"label": "Pressão sistólica (mmHg)", "warn": (90, 160), "crit": (80, 180)},
    "dbp": {"label": "Pressão diastólica (mmHg)", "warn": (55, 100), "crit": (45, 120)},
    "spo2": {"label": "Saturação de O2 (%)", "warn": (94, 101), "crit": (90, 101)},
}

EVENT_COLUMNS = ["timestamp", "signal", "value", "severity", "method", "reason"]


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def rule_based_events(df: pd.DataFrame, signals: list[str]) -> pd.DataFrame:
    frames = []
    for s in signals:
        x = df[s]
        lim = VITAL_LIMITS[s]
        crit = (x < lim["crit"][0]) | (x > lim["crit"][1])
        warn = ((x < lim["warn"][0]) | (x > lim["warn"][1])) & ~crit
        for mask, sev, text in (
            (crit, Severity.CRITICAL, "fora do limite crítico"),
            (warn, Severity.WARNING, "fora da faixa de referência"),
        ):
            sub = df.loc[mask, ["timestamp", s]]
            if sub.empty:
                continue
            frames.append(
                pd.DataFrame(
                    {
                        "timestamp": sub["timestamp"].to_numpy(),
                        "signal": s,
                        "value": sub[s].to_numpy(),
                        "severity": int(sev),
                        "method": "regra clínica",
                        "reason": f"{lim['label']} {text}",
                    }
                )
            )
    return pd.concat(frames, ignore_index=True) if frames else _empty()


def rolling_robust_z(series: pd.Series, window: int) -> pd.Series:
    """Z-score robusto (0.6745 * (x - mediana) / MAD) em janela móvel."""
    minp = max(5, window // 3)
    med = series.rolling(window, min_periods=minp).median()
    mad = (series - med).abs().rolling(window, min_periods=minp).median()
    # O MAD de uma janela curta é instável (subestima o ruído e gera falsos positivos).
    # Usa-se como piso metade do MAD global da série.
    global_mad = float((series - series.median()).abs().median())
    floor = max(0.5 * global_mad, float(series.std(ddof=0)) * 0.1, 1e-6)
    mad = mad.where(mad > floor, floor)
    return 0.6745 * (series - med) / mad


def zscore_events(df: pd.DataFrame, signals: list[str], window: int, threshold: float) -> pd.DataFrame:
    frames = []
    for s in signals:
        z = rolling_robust_z(df[s].astype(float), window)
        mask = z.abs() > threshold
        sub = df.loc[mask.fillna(False), ["timestamp", s]]
        if sub.empty:
            continue
        frames.append(
            pd.DataFrame(
                {
                    "timestamp": sub["timestamp"].to_numpy(),
                    "signal": s,
                    "value": sub[s].to_numpy(),
                    "severity": int(Severity.WARNING),
                    "method": "z-score robusto",
                    "reason": f"{VITAL_LIMITS[s]['label']}: variação abrupta vs. padrão recente",
                }
            )
        )
    return pd.concat(frames, ignore_index=True) if frames else _empty()


def isolation_forest_events(
    df: pd.DataFrame, signals: list[str], contamination: float
) -> pd.DataFrame:
    if len(df) < 30 or not signals:
        return _empty()
    from sklearn.ensemble import IsolationForest

    x = df[signals].astype(float).interpolate().bfill().ffill()
    feats = pd.concat([x, x.diff().fillna(0.0).add_suffix("_d")], axis=1)
    std = feats.std(ddof=0).replace(0, 1.0)
    xs = (feats - feats.mean()) / std

    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
    outlier = model.fit_predict(xs) == -1
    if not outlier.any():
        return _empty()

    # atribui a anomalia ao sinal que mais se desviou naquele instante
    worst = xs[signals].abs().idxmax(axis=1)
    idx = np.where(outlier)[0]
    rows = []
    for i in idx:
        s = worst.iloc[i]
        rows.append(
            {
                "timestamp": df["timestamp"].iloc[i],
                "signal": s,
                "value": float(df[s].iloc[i]),
                "severity": int(Severity.WARNING),
                "method": "isolation forest",
                "reason": "padrão multivariado atípico",
            }
        )
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def detect_vitals_anomalies(
    df: pd.DataFrame,
    signals: list[str] | None = None,
    window: int = 30,
    z_threshold: float = 4.0,
    contamination: float = 0.02,
    use_isolation_forest: bool = True,
) -> pd.DataFrame:
    """Retorna um evento por (timestamp, sinal) anômalo, com a maior severidade encontrada."""
    if "timestamp" not in df.columns:
        raise ValueError("O DataFrame precisa da coluna 'timestamp'.")
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    signals = signals or [s for s in VITAL_LIMITS if s in df.columns]
    if not signals:
        raise ValueError(f"Nenhum sinal conhecido encontrado. Esperado: {list(VITAL_LIMITS)}")

    parts = [
        rule_based_events(df, signals),
        zscore_events(df, signals, window, z_threshold),
    ]
    if use_isolation_forest:
        parts.append(isolation_forest_events(df, signals, contamination))
    parts = [p for p in parts if not p.empty]
    if not parts:
        return _empty()

    allv = pd.concat(parts, ignore_index=True)
    merged = (
        allv.groupby(["timestamp", "signal"], as_index=False)
        .agg(
            value=("value", "first"),
            severity=("severity", "max"),
            method=("method", lambda m: " + ".join(sorted(set(m)))),
            reason=("reason", lambda r: "; ".join(sorted(set(r)))),
        )
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return merged[EVENT_COLUMNS]


def vitals_episodes(events: pd.DataFrame, gap_minutes: int = 5) -> pd.DataFrame:
    return group_episodes(events, pd.Timedelta(minutes=gap_minutes))
