from __future__ import annotations
from typing import IO, Any
from .._http import HttpClient
from ..models import PaginatedResponse, Voice, VoiceEarnings


class VoicesResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, page: int = 1, limit: int = 20) -> PaginatedResponse[Voice]:
        d = self._http.request("GET", "/voices", params={"page": page, "limit": limit})
        return PaginatedResponse(items=[Voice.from_dict(v) for v in d["items"]], total=d["total"], page=d["page"], limit=d["limit"])

    def list_public(self, page: int = 1, limit: int = 20, country_id: str | None = None, region_id: str | None = None, age_range: str | None = None) -> PaginatedResponse[Voice]:
        d = self._http.request("GET", "/voices/public", params={"page": page, "limit": limit, "countryId": country_id, "regionId": region_id, "ageRange": age_range})
        return PaginatedResponse(items=[Voice.from_dict(v) for v in d["items"]], total=d["total"], page=d["page"], limit=d["limit"])

    def get(self, voice_id: str) -> Voice:
        return Voice.from_dict(self._http.request("GET", f"/voices/{voice_id}"))

    def clone(self, name: str, audio_samples: list[tuple[str, IO[bytes], str]], provider_ids: list[str], sample_text: str | None = None, language_code: str | None = None) -> Voice:
        """
        Clona una voz a partir de una o varias muestras de audio.

        Args:
            name: Nombre de la voz.
            audio_samples: Muestras como (nombre de fichero, binario, tipo MIME).
                La API acepta hasta 20.
            provider_ids: Proveedores en los que clonar la voz. Obligatorio:
                al menos uno. La API rechaza la lista vacía con
                PROVIDERS_REQUIRED. Con varios, la voz queda disponible en
                varias calidades.
            sample_text: Texto de muestra para la previsualización.
            language_code: Idioma de la muestra (ej: 'es').
        """
        if not provider_ids:
            raise ValueError("clone requiere al menos un provider_id")
        data: dict[str, Any] = {"name": name}
        if provider_ids:
            # Viajan como partes repetidas del multipart: así recibe listas la API.
            data["providerIds"] = provider_ids
        if sample_text:
            data["sample_text"] = sample_text
        if language_code:
            data["language_code"] = language_code
        files = [("audio_sample", s) for s in audio_samples]
        return Voice.from_dict(self._http.request("POST", "/voices/clone", data=data, files=files))

    def update(self, voice_id: str, name: str) -> Voice:
        return Voice.from_dict(self._http.request("PATCH", f"/voices/{voice_id}", json={"name": name}))

    def delete(self, voice_id: str) -> None:
        self._http.request("DELETE", f"/voices/{voice_id}")

    def favorite(self, voice_id: str) -> bool:
        d = self._http.request("POST", f"/voices/{voice_id}/favorite")
        return d["isFavorited"]

    def request_public(self, voice_id: str) -> None:
        self._http.request("POST", f"/voices/{voice_id}/request-public")

    def sample(self, voice_id: str) -> bytes:
        return self._http.stream("GET", f"/voices/{voice_id}/sample").content

    def update_metadata(
        self,
        voice_id: str,
        *,
        country_id: str | None = None,
        region_id: str | None = None,
        age_range: str | None = None,
        new_country_name: str | None = None,
        new_region_name: str | None = None,
    ) -> Voice:
        """Fija el origen y el rango de edad de una voz.

        El catálogo público exige los tres rellenos, así que este es el paso
        previo a `request_public`. `new_country_name` y `new_region_name` crean
        la entrada cuando todavía no existe, en vez de fallar.
        """
        body: dict[str, Any] = {}
        for clave, valor in (
            ("countryId", country_id),
            ("regionId", region_id),
            ("ageRange", age_range),
            ("newCountryName", new_country_name),
            ("newRegionName", new_region_name),
        ):
            if valor is not None:
                body[clave] = valor
        if not body:
            raise ValueError("update_metadata requiere al menos un campo")
        return Voice.from_dict(
            self._http.request("PATCH", f"/voices/{voice_id}/metadata", json=body)
        )

    def earnings(self, voice_id: str) -> VoiceEarnings:
        """Historial mensual de saldo generado por una voz pública."""
        return VoiceEarnings.from_dict(
            self._http.request("GET", f"/voices/{voice_id}/earnings")
        )
