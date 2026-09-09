from __future__ import annotations
from typing import IO
from .._http import HttpClient
from ..models import PaginatedResponse, TranscribeResult, Transcription


class SttResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def transcribe(self, audio: IO[bytes], filename: str = "audio.mp3", language: str = "es-ES") -> TranscribeResult:
        d = self._http.request(
            "POST",
            "/stt/transcribe",
            files={"audio": (filename, audio, "audio/mpeg")},
            params={"language": language},
        )
        return TranscribeResult.from_dict(d)

    def list_transcriptions(self, page: int = 1, limit: int = 20) -> PaginatedResponse[Transcription]:
        """Transcripciones guardadas del usuario, de la más reciente a la más
        antigua."""
        d = self._http.request(
            "GET", "/stt/transcriptions", params={"page": page, "limit": limit}
        )
        return PaginatedResponse(
            items=[Transcription.from_dict(t) for t in d["items"]],
            total=d["total"],
            page=d["page"],
            limit=d["limit"],
        )

    def delete_transcription(self, transcription_id: str) -> None:
        """Borra una transcripción guardada.

        No devuelve el saldo que consumió: el trabajo ya se hizo.
        """
        self._http.request("DELETE", f"/stt/transcriptions/{transcription_id}")
