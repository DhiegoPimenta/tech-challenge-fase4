"""Garante que as telas chamam as funções do pacote com argumentos que existem de verdade.

Os testes de UI não enviam arquivos, então erros de nome de argumento em caminhos que dependem de
upload (como em `assess_voice`) só apareciam em produção. Esta checagem estática cobre isso.
"""

import ast
import inspect
from pathlib import Path

from hospital_monitor.audio.text_analytics import analyze_text
from hospital_monitor.audio.voice_features import assess_voice, extract_voice_features
from hospital_monitor.pipelines import (
    analyze_movement,
    analyze_prescriptions,
    analyze_vitals,
    audio_alerts,
    video_alerts,
)

VIEWS = Path(__file__).resolve().parents[1] / "app" / "views"
FUNCS = {
    f.__name__: f
    for f in (
        assess_voice, extract_voice_features, analyze_text, audio_alerts, video_alerts,
        analyze_vitals, analyze_prescriptions, analyze_movement,
    )
}


def test_view_keyword_arguments_exist():
    errors = []
    for path in VIEWS.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            func = FUNCS.get(name)
            if func is None:
                continue
            params = inspect.signature(func).parameters
            accepts_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
            for kw in node.keywords:
                if kw.arg and kw.arg not in params and not accepts_kwargs:
                    errors.append(f"{path.name}:{node.lineno} {name}(... {kw.arg}=...)")
    assert not errors, "argumentos inexistentes: " + ", ".join(errors)
