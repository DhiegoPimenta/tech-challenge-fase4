"""Gera vídeos de teste com PESSOAS REAIS a partir de uma foto (para o YOLOv8 detectar de verdade).

Não há filmagem de movimento: são simulações feitas girando/deslocando uma foto estática. Servem para
exercitar a cadeia detector -> keypoints -> ângulos -> eventos com detecções reais, não para medir
precisão clínica.

A foto vem do pacote `ultralytics` (ultralytics/assets/bus.jpg, licença AGPL-3.0 do projeto). Por isso os
vídeos gerados NÃO são versionados (ver .gitignore); gere localmente:

    python scripts/make_test_video.py                    # usa a foto do pacote ultralytics instalado
    python scripts/make_test_video.py --image bus.jpg    # ou informe o caminho da foto

Saída em tests/manual/:
  pessoa_em_pe.mp4        6 s, pessoa parada em pé             -> esperado: detectada, sem eventos
  pessoa_inclinada.mp4    6 s, imagem girada 30°               -> esperado (perfil Marcha): tronco inclinado
  queda_simulada.mp4      3 s em pé + 3 s imagem girada 90°    -> esperado: "queda suspeita"
"""

import argparse
from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "tests" / "manual"
SIZE = 720  # quadro quadrado; a foto entra com margens (letterbox)
FPS = 10


def find_image(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    import ultralytics  # noqa: PLC0415

    return Path(ultralytics.__file__).parent / "assets" / "bus.jpg"


def letterbox(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    scale = min(SIZE / w, SIZE / h)
    resized = cv2.resize(img, (int(w * scale), int(h * scale)))
    canvas = np.full((SIZE, SIZE, 3), 40, dtype=np.uint8)
    y0, x0 = (SIZE - resized.shape[0]) // 2, (SIZE - resized.shape[1]) // 2
    canvas[y0 : y0 + resized.shape[0], x0 : x0 + resized.shape[1]] = resized
    return canvas


def rotate(img: np.ndarray, angle: float) -> np.ndarray:
    if angle == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), borderValue=(40, 40, 40))


def write(name: str, frames: list[np.ndarray]) -> None:
    path = OUT / name
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (SIZE, SIZE))
    for f in frames:
        vw.write(f)
    vw.release()
    print(f"{name:24s} {path.stat().st_size / 1024:7.0f} KB  {len(frames) / FPS:.0f} s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="foto com pessoas em pé de corpo inteiro")
    args = ap.parse_args()
    src = cv2.imread(str(find_image(args.image)))
    if src is None:
        raise SystemExit("Não consegui ler a imagem.")

    OUT.mkdir(parents=True, exist_ok=True)
    upright = letterbox(src)
    tilted = letterbox(rotate(src, 30))
    lying = letterbox(rotate(src, 90))

    write("pessoa_em_pe.mp4", [upright] * (6 * FPS))
    write("pessoa_inclinada.mp4", [tilted] * (6 * FPS))
    write("queda_simulada.mp4", [upright] * (3 * FPS) + [lying] * (3 * FPS))


if __name__ == "__main__":
    main()
