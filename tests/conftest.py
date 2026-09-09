"""Piezas comunes a los tests de contrato del SDK.

Los tests hablan HTTP de verdad contra un transporte simulado (respx), no
contra dobles de los recursos: así se verifica lo que de verdad viaja por el
cable —verbo, ruta, cabeceras y cuerpo— y cómo se deserializa la respuesta.

Los `fixtures` de respuesta son copias fieles de lo que emite el backend, con
todas sus claves, incluidas las internas. La versión anterior era una lista de
deseos —solo los campos que la dataclass declaraba— y por eso los tests daban
por bueno un SDK que reventaba contra la API real.
"""

from __future__ import annotations

from typing import Any

import pytest

from vocea_sdk import VoceaClient


BASE_URL = "https://api.test/v1"

# Un decimal con ocho cifras significativas: si algún punto del camino lo
# convierte a string y lo redondea, el test lo caza.
SALDO_EXACTO = 10.42544375


@pytest.fixture
def cliente() -> VoceaClient:
    return VoceaClient(api_key="vca_test", base_url=BASE_URL)


@pytest.fixture
def voz_json() -> dict[str, Any]:
    """Una voz tal y como sale de `VoicesService.toPublic()`.

    Es la entidad `Voice` entera menos cuatro campos (`providerStates`,
    `userId`, `cloneAudioKey`, `samplePreviewKey`), más `providers`,
    `hasSamplePreview` y los extras del listado. No lleva `langSet`: la
    entidad perdió esa columna y el backend ya no la envía.
    """
    return {
        "id": "voz-1",
        "name": "Mi voz",
        "status": "active",
        "failureReason": None,
        "cloneAudioDuration": 41.28,
        "languageCode": "es",
        "countryId": "co-1",
        "country": {"id": "co-1", "name": "España", "code": "ES"},
        "regionId": None,
        "region": None,
        "ageRange": "adult",
        "gender": "female",
        "isPublicRequest": False,
        "isPublic": True,
        "publicRejectReason": None,
        "timesUsed": 7,
        "balanceEarnedTotal": SALDO_EXACTO,
        "lastUsedAt": "2026-09-03T10:15:00.000Z",
        "createdAt": "2026-09-01T00:00:00.000Z",
        "updatedAt": "2026-09-02T00:00:00.000Z",
        "deletedAt": None,
        "providers": [
            {
                "provider_id": "prov-a",
                "name": "inworld",
                "is_enabled": True,
                "is_cloned": True,
                "last_used_at": None,
                "has_sample_preview": True,
            },
            {
                "provider_id": "prov-b",
                "name": "elevenlabs",
                "is_enabled": True,
                "is_cloned": False,
                "last_used_at": "2026-09-03T10:15:00.000Z",
                "has_sample_preview": False,
            },
        ],
        "hasSamplePreview": True,
        "isFavorited": False,
        "favoritesCount": 3,
    }


@pytest.fixture
def audio_json() -> dict[str, Any]:
    """Un audio tal y como sale de `AudiosService.sanitizeAudio()`.

    Es la entidad `Audio` menos `textHash`, `audioKey`, `isCached` y `userId`,
    más la `audioUrl` firmada.
    """
    return {
        "id": "aud-1",
        "voiceId": "voz-1",
        "providerVoiceId": None,
        "ttsModelId": "mod-1",
        "textContent": "Hola mundo",
        "durationSeconds": 3.5,
        "characterCount": 10,
        "languageCode": "es",
        "generationTimeMs": 1830,
        "speakingRate": 1.0,
        "temperature": 1.0,
        "emotion": "neutral",
        "createdAt": "2026-09-02T00:00:00.000Z",
        "audioUrl": "https://vocea.app/api/v1/audios/aud-1/play.mp3",
    }
