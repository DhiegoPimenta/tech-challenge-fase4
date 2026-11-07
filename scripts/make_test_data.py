"""Gera os CSVs (e um vídeo sintético) usados no mapa de testes manuais.

Uso:  python scripts/make_test_data.py   ->  grava em tests/manual/
Os áudios falados são gerados por scripts/make_test_audio.ps1 (voz pt-BR do Windows).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hospital_monitor.synthetic import make_movement, make_prescriptions, make_vitals  # noqa: E402

OUT = ROOT / "tests" / "manual"
OUT.mkdir(parents=True, exist_ok=True)

# --- séries temporais -------------------------------------------------------
make_vitals().to_csv(OUT / "vitais_com_anomalias.csv", index=False)
make_vitals(inject=False).to_csv(OUT / "vitais_normais.csv", index=False)
make_prescriptions().to_csv(OUT / "prescricoes_com_anomalias.csv", index=False)
pd.DataFrame(
    [
        ("2025-01-01 08:00", "paracetamol", 500, 3),
        ("2025-01-02 08:00", "paracetamol", 500, 3),
        ("2025-01-03 08:00", "paracetamol", 500, 3),
        ("2025-01-01 09:00", "enalapril", 10, 1),
        ("2025-01-02 09:00", "enalapril", 10, 1),
    ],
    columns=["timestamp", "drug", "dose_mg", "frequency_per_day"],
).to_csv(OUT / "prescricoes_normais.csv", index=False)
make_movement().to_csv(OUT / "movimento_com_anomalias.csv", index=False)
make_movement(inject=False).to_csv(OUT / "movimento_normal.csv", index=False)

# CSV inválido (sem a coluna timestamp) para testar o tratamento de erro
pd.DataFrame({"hr": [70, 72, 71], "spo2": [98, 97, 98]}).to_csv(OUT / "invalido_sem_timestamp.csv", index=False)

# --- vídeo sintético --------------------------------------------------------
# Quadrados coloridos em movimento: NÃO contém pessoa, então o esperado é "paciente fora de quadro".
try:
    import cv2

    w, h, fps, seconds = 640, 480, 15, 8
    writer = cv2.VideoWriter(str(OUT / "video_sem_pessoa.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for i in range(fps * seconds):
        frame = np.full((h, w, 3), 235, dtype=np.uint8)
        x = int(50 + (w - 150) * (i / (fps * seconds)))
        cv2.rectangle(frame, (x, 200), (x + 80, 280), (200, 90, 30), -1)
        writer.write(frame)
    writer.release()
    print("vídeo sintético gerado")
except ImportError:
    print("opencv não instalado: vídeo sintético não gerado")

print("arquivos em", OUT)
for p in sorted(OUT.iterdir()):
    print(f"  {p.name:36s} {p.stat().st_size/1024:8.1f} KB")
