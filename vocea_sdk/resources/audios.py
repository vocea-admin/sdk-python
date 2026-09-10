from __future__ import annotations
from typing import Any, Optional
from .._http import HttpClient
from ..models import Audio, Emotion, PaginatedResponse


class AudiosResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def generate(
        self,
        voice_id: str | None = None,
        text: str = "",
        language_code: str = "es",
        *,
        provider_voice_id: str | None = None,
        tts_model_id: Optional[str] = None,
        speed: float = 1.0,
        advanced_params: Optional[dict[str, Any]] = None,
        # Parámetros legacy (retrocompatibilidad)
        speaking_rate: Optional[float] = None,
        temperature: Optional[float] = None,
        emotion: Optional[Emotion] = None,
    ) -> Audio:
        """
        Genera un audio TTS.

        Args:
            voice_id: ID de una voz clonada del usuario. Excluyente con
                `provider_voice_id`.
            provider_voice_id: ID de una voz del catálogo del proveedor.
                Excluyente con `voice_id`.
            text: Texto a sintetizar (máx. 10 000 caracteres).
            language_code: Código de idioma (ej: 'es', 'en', 'zh').
            tts_model_id: ID del modelo TTS. Obtén la lista con `client.models.list()`.
            speed: Velocidad del habla (0.5–1.5). Por defecto 1.0. Se aplica a
                todas las calidades y va FUERA de `advanced_params`.
            advanced_params: Parámetros de la calidad de la voz. Enviar uno que
                pertenece a otra calidad devuelve 400 INVALID_ADVANCED_PARAMS,
                así que conviene construirlos con `standard_params`,
                `premium_params` o `studio_params` en vez de a mano.

        Raises:
            ValueError: si no se indica ni `voice_id` ni `provider_voice_id`, o
                si se indican los dos.
        """
        # `is None` y no truthiness: una cadena vacía es un error del llamante,
        # no una ausencia, y merece un mensaje que lo diga en vez del genérico.
        if voice_id == "" or provider_voice_id == "":
            raise ValueError(
                "voice_id y provider_voice_id no pueden ser una cadena vacía; "
                "omite el que no uses"
            )
        if (voice_id is None) == (provider_voice_id is None):
            raise ValueError(
                "generate requiere voice_id o provider_voice_id, pero no ambos"
            )
        # El rango lo impone la API y el docstring lo prometía, pero nadie lo
        # comprobaba: un 3.0 gastaba la petición para acabar en un 400.
        # params.py sí valida sus rangos; esto lo deja coherente.
        if not 0.5 <= speed <= 1.5:
            raise ValueError(f"speed tiene que estar entre 0.5 y 1.5: {speed}")
        body: dict[str, Any] = {
            "text": text,
            "language_code": language_code,
            "speed": speed,
        }
        if voice_id:
            body["voice_id"] = voice_id
        if provider_voice_id:
            body["provider_voice_id"] = provider_voice_id
        if tts_model_id:
            body["tts_model_id"] = tts_model_id
        if advanced_params:
            body["advanced_params"] = advanced_params
        # Retrocompatibilidad con la interfaz anterior
        if speaking_rate is not None or temperature is not None or emotion is not None:
            body["voice_setting"] = {
                k: v for k, v in {
                    "speakingRate": speaking_rate,
                    "temperature": temperature,
                    "emotion": emotion,
                }.items() if v is not None
            }
        d = self._http.request("POST", "/audios/generate", json=body)
        return Audio.from_dict(d)

    def list(self, page: int = 1, limit: int = 20) -> PaginatedResponse[Audio]:
        d = self._http.request("GET", "/audios", params={"page": page, "limit": limit})
        return PaginatedResponse(items=[Audio.from_dict(a) for a in d["items"]], total=d["total"], page=d["page"], limit=d["limit"])

    def get(self, audio_id: str) -> Audio:
        return Audio.from_dict(self._http.request("GET", f"/audios/{audio_id}"))

    def download(self, audio_id: str) -> bytes:
        return self._http.stream("GET", f"/audios/{audio_id}/download").content

    def delete(self, audio_id: str) -> None:
        self._http.request("DELETE", f"/audios/{audio_id}")

    def play_url(self, audio_id: str) -> str:
        """URL pública de reproducción de un audio.

        No necesita autenticación, que es lo que la hace utilizable en una
        etiqueta <audio> o para compartir con quien no tiene cuenta. Para
        obtener los bytes, usa `download`.
        """
        return f"{self._http.base_url}/audios/{audio_id}/play.mp3"
