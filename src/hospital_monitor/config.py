"""Configuração da aplicação, lida de variáveis de ambiente (ou de um arquivo .env local).

Nenhum segredo fica no código. Em produção (Azure Container Apps) as chaves chegam como
secrets do Container App, provisionados pelo Bicep em ``infra/main.bicep``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # python-dotenv é opcional: só ajuda no desenvolvimento local.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Settings:
    speech_key: str = ""
    speech_region: str = ""
    speech_language: str = "pt-BR"
    language_endpoint: str = ""
    language_key: str = ""
    alert_webhook_url: str = ""
    models_dir: str = "models"

    @property
    def speech_enabled(self) -> bool:
        return bool(self.speech_key and self.speech_region)

    @property
    def language_enabled(self) -> bool:
        return bool(self.language_key and self.language_endpoint)

    @property
    def webhook_enabled(self) -> bool:
        return bool(self.alert_webhook_url)


def load_settings() -> Settings:
    get = os.environ.get
    return Settings(
        speech_key=get("AZURE_SPEECH_KEY", ""),
        speech_region=get("AZURE_SPEECH_REGION", ""),
        speech_language=get("AZURE_SPEECH_LANGUAGE", "pt-BR"),
        language_endpoint=get("AZURE_LANGUAGE_ENDPOINT", ""),
        language_key=get("AZURE_LANGUAGE_KEY", ""),
        alert_webhook_url=get("ALERT_WEBHOOK_URL", ""),
        models_dir=get("MODELS_DIR", "models"),
    )
