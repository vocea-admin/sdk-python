from __future__ import annotations
from .._http import HttpClient
from ..models import TtsConfig, TtsLanguage, TtsModel, TtsModelListItem


class ModelsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self) -> list[TtsModelListItem]:
        """Lista todos los modelos TTS activos.

        Los elementos traen `providerId`, que el detalle no envía y que
        `voices.clone()` exige: este listado es de donde salen esos
        identificadores.
        """
        data = self._http.request("GET", "/tts-models")
        return [TtsModelListItem.from_dict(m) for m in data]

    def get(self, model_id: str) -> TtsModel:
        """Obtiene un modelo TTS por ID.

        El detalle NO trae `providerId` ni `maxCharacters`; para eso está
        `list()`. Son tipos distintos a propósito.
        """
        return TtsModel.from_dict(self._http.request("GET", f"/tts-models/{model_id}"))

    def languages(self) -> list[TtsLanguage]:
        """Lista idiomas del conjunto completo (Minimax + ElevenLabs)."""
        data = self._http.request("GET", "/tts-models/languages")
        return [TtsLanguage.from_dict(lang) for lang in data]

    def lite_languages(self) -> list[TtsLanguage]:
        """Lista idiomas del conjunto reducido (Inworld / standard tier)."""
        data = self._http.request("GET", "/tts-models/languages/lite")
        return [TtsLanguage.from_dict(lang) for lang in data]

    def config(self) -> TtsConfig:
        """Indica qué conjuntos de idiomas están habilitados en esta instancia."""
        data = self._http.request("GET", "/tts-models/config")
        return TtsConfig.from_dict(data)
