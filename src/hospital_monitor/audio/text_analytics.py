"""Análise do texto transcrito: Azure AI Language (sentimento, frases-chave, entidades) + termos críticos."""

from __future__ import annotations

from dataclasses import dataclass, field

from .clinical_terms import find_critical_terms, local_sentiment

MAX_CHARS = 4500  # limite do serviço é 5120 caracteres por documento


@dataclass
class TextInsights:
    sentiment: str
    scores: dict[str, float]
    key_phrases: list[str] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    critical_terms: list[dict] = field(default_factory=list)
    source: str = "local"  # "azure" ou "local"


def _chunks(text: str, size: int = MAX_CHARS) -> list[str]:
    text = text.strip()
    out: list[str] = []
    while len(text) > size:
        cut = text.rfind(" ", 0, size)
        cut = cut if cut > 0 else size
        out.append(text[:cut])
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out


def analyze_text(text: str, endpoint: str = "", key: str = "", language: str = "pt") -> TextInsights:
    """Usa o Azure AI Language se endpoint/chave existirem; senão cai no léxico local."""
    critical = find_critical_terms(text)
    if not (endpoint and key):
        scores = local_sentiment(text)
        return TextInsights(max(scores, key=scores.get), scores, critical_terms=critical, source="local")

    from azure.ai.textanalytics import TextAnalyticsClient
    from azure.core.credentials import AzureKeyCredential

    client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    docs = _chunks(text)

    sent = [r for r in client.analyze_sentiment(docs, language=language) if not r.is_error]
    if not sent:
        raise RuntimeError("Azure AI Language não retornou sentimento para o texto.")
    scores = {
        k: round(sum(getattr(r.confidence_scores, k) for r in sent) / len(sent), 3)
        for k in ("positive", "neutral", "negative")
    }

    phrases: list[str] = []
    for r in client.extract_key_phrases(docs, language=language):
        if not r.is_error:
            phrases.extend(r.key_phrases)

    entities: list[dict] = []
    for r in client.recognize_entities(docs, language=language):
        if not r.is_error:
            entities.extend(
                {"text": e.text, "category": e.category, "confidence": round(e.confidence_score, 2)}
                for e in r.entities
            )

    return TextInsights(
        sentiment=max(scores, key=scores.get),
        scores=scores,
        key_phrases=list(dict.fromkeys(phrases)),
        entities=entities,
        critical_terms=critical,
        source="azure",
    )
