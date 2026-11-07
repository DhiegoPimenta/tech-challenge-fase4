"""Roda os detectores de sinais vitais em dados reais do PhysioNet (BIDMC PPG and Respiration Dataset).

Fonte (acesso aberto, licença Open Data Commons Attribution v1.0):
https://physionet.org/content/bidmc/1.0.0/   (arquivos ``bidmc_XX_Numerics.csv``, 1 amostra/s, ~8 min)

Uso:
    python scripts/eval_physionet.py <pasta_com_os_csv> [--exportar bidmc_NN]

Os arquivos trazem ``HR`` (bpm) e ``SpO2`` (%), sem pressão arterial e sem relógio. O script monta a coluna
``timestamp`` a partir de 2025-01-01 00:00:00 + segundos e agrupa pontos vizinhos em episódios com tolerância
de 5 s (o padrão do app é 5 min, pensado para dados com 1 amostra/min).

Não há rótulos de anomalia nesses arquivos: o resultado mostra *o que o sistema marca* em dados reais, não
precisão/revocação.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hospital_monitor.alerts import Severity  # noqa: E402
from hospital_monitor.anomalies.episodes import group_episodes  # noqa: E402
from hospital_monitor.anomalies.vitals import detect_vitals_anomalies  # noqa: E402

BASE = pd.Timestamp("2025-01-01 00:00:00")


def load_bidmc(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, skipinitialspace=True)
    raw.columns = [c.strip() for c in raw.columns]
    df = pd.DataFrame(
        {
            "timestamp": BASE + pd.to_timedelta(raw["Time [s]"], unit="s"),
            "hr": raw["HR"],
            "spo2": raw["SpO2"],
        }
    )
    return df.dropna().reset_index(drop=True)


def analyze(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = detect_vitals_anomalies(df)
    episodes = group_episodes(events, pd.Timedelta(seconds=5)) if not events.empty else events
    return events, episodes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", type=Path)
    ap.add_argument("--exportar", help="ex.: bidmc_01 -> grava tests/manual/physionet_<nome>.csv no formato do app")
    args = ap.parse_args()

    files = sorted(args.pasta.glob("bidmc_*_Numerics.csv"))
    if not files:
        sys.exit(f"Nenhum bidmc_*_Numerics.csv em {args.pasta}")

    rows = []
    for f in files:
        df = load_bidmc(f)
        events, episodes = analyze(df)
        n_crit = int((episodes["severity"] == int(Severity.CRITICAL)).sum()) if not episodes.empty else 0
        rows.append(
            {
                "registro": f.stem.replace("_Numerics", ""),
                "pontos": len(df),
                "hr_min": df["hr"].min(),
                "hr_max": df["hr"].max(),
                "spo2_min": df["spo2"].min(),
                "pontos_marcados": len(events),
                "episodios": len(episodes),
                "criticos": n_crit,
            }
        )
        if args.exportar and f.stem.startswith(args.exportar):
            out = ROOT / "tests" / "manual" / f"physionet_{args.exportar}.csv"
            df.to_csv(out, index=False)
            print(f"exportado: {out}")

    res = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(res.to_string(index=False))
    print()
    print(f"registros: {len(res)} | pontos: {res['pontos'].sum()}")
    print(f"registros sem nenhum episódio: {(res['episodios'] == 0).sum()}")
    print(f"registros com episódio crítico: {(res['criticos'] > 0).sum()}")
    print(f"episódios por registro: média {res['episodios'].mean():.1f}, máx {res['episodios'].max()}")
    print(f"pontos marcados: {res['pontos_marcados'].sum()} de {res['pontos'].sum()} "
          f"({100 * res['pontos_marcados'].sum() / res['pontos'].sum():.1f}%)")


if __name__ == "__main__":
    main()
