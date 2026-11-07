"""Geradores de dados sintéticos com anomalias injetadas (para demonstração e testes).

Para dados reais de sinais vitais use o PhysioNet (https://physionet.org/): exporte para CSV
com as colunas ``timestamp, hr, sbp, dbp, spo2`` e envie pela interface.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_vitals(minutes: int = 480, seed: int = 7, inject: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2025-01-01 08:00", periods=minutes, freq="min")
    t = np.arange(minutes)
    hr = 74 + 4 * np.sin(t / 60) + rng.normal(0, 1.5, minutes)
    sbp = 121 + 3 * np.sin(t / 90) + rng.normal(0, 2.0, minutes)
    dbp = 79 + 2 * np.sin(t / 90) + rng.normal(0, 1.5, minutes)
    spo2 = 97.5 + rng.normal(0, 0.5, minutes)

    if inject and minutes >= 400:
        hr[200:215] = rng.normal(135, 3, 15)  # taquicardia sustentada
        spo2[300:312] = rng.normal(88, 1.0, 12)  # dessaturação
        sbp[380:386] = rng.normal(185, 3, 6)  # pico hipertensivo
        hr[120] = 160  # artefato / pico isolado
    spo2 = np.clip(spo2, 0, 100)
    return pd.DataFrame({"timestamp": ts, "hr": hr, "sbp": sbp, "dbp": dbp, "spo2": spo2})


def make_prescriptions() -> pd.DataFrame:
    rows = [
        ("2025-01-01 08:00", "dipirona", 500, 4),
        ("2025-01-02 08:00", "dipirona", 500, 4),
        ("2025-01-03 08:00", "dipirona", 1000, 4),  # dose diária dobra
        ("2025-01-04 08:00", "dipirona", 1500, 4),  # passa do máximo de referência
        ("2025-01-01 09:00", "tramadol", 50, 2),
        ("2025-01-03 09:00", "tramadol", 100, 4),  # x4
        ("2025-01-01 10:00", "enalapril", 10, 1),
        ("2025-01-02 10:00", "enalapril", 10, 1),
        ("2025-01-03 10:00", "enalapril", 10, 1),
        ("2025-01-02 11:00", "varfarina", 5, 1),
        ("2025-01-03 11:00", "ibuprofeno", 400, 3),  # interação com varfarina
    ]
    return pd.DataFrame(rows, columns=["timestamp", "drug", "dose_mg", "frequency_per_day"])


def make_movement(days: int = 2, seed: int = 11, inject: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = days * 96  # 15 em 15 minutos
    ts = pd.date_range("2025-01-01 00:00", periods=n, freq="15min")
    hours = ts.hour.to_numpy()
    night = (hours >= 22) | (hours < 6)
    base = np.where(night, 0.05, 0.45 + 0.1 * np.sin(np.arange(n) / 8))
    act = np.clip(base + rng.normal(0, 0.03, n), 0, None)
    # noites ficam acima de 0 mas abaixo do limiar de imobilidade apenas à noite (ignorado pelo detector)

    if inject and days >= 2:
        mask = (ts >= "2025-01-01 13:00") & (ts < "2025-01-01 17:00")
        act[mask] = 0.01 + np.abs(rng.normal(0, 0.005, mask.sum()))  # 4 h de imobilidade
        i = int(np.where(ts == pd.Timestamp("2025-01-02 10:00"))[0][0])
        act[i] = 3.0  # pico (queda)
        act[i + 1 : i + 9] = 0.01  # 2 h imóvel depois
    return pd.DataFrame({"timestamp": ts, "activity": act})
