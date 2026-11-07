"""Utilidades pequenas compartilhadas entre os módulos."""

from __future__ import annotations

import numpy as np


def find_runs(mask) -> list[tuple[int, int]]:
    """Retorna os trechos contíguos True de uma máscara como pares (início, fim) inclusivos."""
    arr = np.asarray(mask, dtype=bool)
    if arr.size == 0:
        return []
    padded = np.concatenate([[False], arr, [False]]).astype(np.int8)
    diff = np.diff(padded)
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0] - 1
    return list(zip(starts.tolist(), ends.tolist(), strict=True))
