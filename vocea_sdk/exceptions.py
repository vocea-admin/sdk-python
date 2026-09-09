from __future__ import annotations
from typing import Any, Optional


class VoceaError(Exception):
    """Error devuelto por la API.

    La API sanea sus errores y a menudo no manda `message`: responde
    `{"statusCode": 402, "errorCode": "INSUFFICIENT_BALANCE"}`. Por eso lo que
    hay que mirar es `error_code`, que es estable, y no el texto del mensaje,
    que cambia con el idioma y con la versión.

        try:
            client.audios.generate(...)
        except VoceaError as e:
            if e.error_code == "INSUFFICIENT_BALANCE":
                ...
    """

    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Vocea API error {status_code}: {self._describir()}")

    @property
    def error_code(self) -> Optional[str]:
        """Código estable del error, o None si la respuesta no traía ninguno.

        Los que emite la API hoy: INSUFFICIENT_BALANCE, PROVIDERS_REQUIRED,
        PROVIDER_NOT_AVAILABLE, INVALID_ADVANCED_PARAMS, CLONE_FAILED,
        CLONE_REQUIRES_PURCHASE, VOICE_NOT_FOUND, VOICE_NAME_ALREADY_EXISTS,
        VOICE_METADATA_INCOMPLETE, TRIAL_VOICE_LIMIT_REACHED, AUDIO_NO_FILES,
        AUDIO_INVALID_FORMAT y AUDIO_TOO_LARGE.
        """
        codigo = self.body.get("errorCode")
        return codigo if isinstance(codigo, str) else None

    def _describir(self) -> str:
        """El texto más útil que traiga el cuerpo, en orden de preferencia."""
        mensaje: Any = self.body.get("message")
        if isinstance(mensaje, list):
            # Los errores de validación llegan como lista de cadenas.
            return ", ".join(str(m) for m in mensaje)
        if isinstance(mensaje, str) and mensaje:
            return mensaje
        if self.error_code:
            return self.error_code
        return str(self.body)
