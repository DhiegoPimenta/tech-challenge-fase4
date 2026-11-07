"""Dicionário de termos clínicos críticos (pt-BR) e busca insensível a acentos/caixa.

Complementa o Azure AI Language: o serviço dá sentimento, frases-chave e entidades; este
dicionário garante que sintomas de alerta sejam sempre marcados, mesmo offline.
Lista ilustrativa - deve ser validada por profissionais de saúde.
"""

from __future__ import annotations

import re
import unicodedata

from hospital_monitor.alerts import Severity

CRITICAL_TERMS: dict[str, tuple[Severity, list[str]]] = {
    "Respiratório": (
        Severity.CRITICAL,
        ["falta de ar", "dificuldade para respirar", "dificuldade de respirar", "nao consigo respirar", "chiado", "sufocando"],
    ),
    "Cardiovascular": (
        Severity.CRITICAL,
        ["dor no peito", "aperto no peito", "palpitacao", "palpitacoes", "batedeira", "desmaio", "desmaiei"],
    ),
    "Neurológico": (
        Severity.CRITICAL,
        ["confusao", "confuso", "fala enrolada", "dificuldade para falar", "formigamento", "dormencia", "tontura", "visao turva"],
    ),
    "Sangramento": (Severity.CRITICAL, ["sangramento", "sangrando", "sangue nas fezes", "vomito com sangue"]),
    "Sintomas gerais": (
        Severity.WARNING,
        ["cansaco", "cansado", "cansada", "fadiga", "fraqueza", "fraco", "fraca", "febre", "calafrio", "vomito", "nausea", "dor de cabeca", "sem apetite"],
    ),
    "Dor": (Severity.WARNING, ["muita dor", "dor forte", "dor insuportavel", "dor intensa"]),
}

NEGATIVE_WORDS = [
    "dor", "mal", "pior", "ruim", "cansado", "cansada", "fraco", "fraca", "medo", "preocupado",
    "preocupada", "angustia", "ansiedade", "nao consigo", "piorou", "sofrendo",
]


def normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def find_critical_terms(text: str) -> list[dict]:
    """Retorna [{'term', 'category', 'severity', 'count'}] para cada termo encontrado."""
    norm = normalize(text)
    found = []
    for category, (severity, terms) in CRITICAL_TERMS.items():
        for term in terms:
            count = len(re.findall(rf"\b{re.escape(term)}\b", norm))
            if count:
                found.append({"term": term, "category": category, "severity": severity, "count": count})
    return sorted(found, key=lambda d: (-int(d["severity"]), d["term"]))


def local_sentiment(text: str) -> dict[str, float]:
    """Fallback simples por léxico, usado quando o Azure AI Language não está configurado."""
    norm = normalize(text)
    words = max(len(norm.split()), 1)
    neg = sum(len(re.findall(rf"\b{re.escape(w)}\b", norm)) for w in NEGATIVE_WORDS)
    neg_score = min(1.0, 4.0 * neg / words)
    return {"positive": 0.0, "neutral": round(1 - neg_score, 3), "negative": round(neg_score, 3)}
