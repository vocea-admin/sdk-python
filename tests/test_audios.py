"""Contrato HTTP del recurso de audios.

El recurso no tenía ningún test y era el otro que no funcionaba contra la API
real: `Audio(**d)` desempaquetaba la respuesta entera y `providerVoiceId` y
`generationTimeMs`, que el backend manda siempre, no estaban declarados.

Estos tests miran la respuesta, no el cuerpo de la petición: los parámetros de
generación (modelo, velocidad, `advanced_params`) son otra historia y se
prueban con su propia feature.
"""

from __future__ import annotations

import httpx
import respx

from .conftest import BASE_URL


@respx.mock
def test_generate_deserializa_la_respuesta_real(cliente, audio_json):
    ruta = respx.post(f"{BASE_URL}/audios/generate").mock(
        return_value=httpx.Response(201, json=audio_json)
    )

    audio = cliente.audios.generate(
        voice_id="voz-1", text="Hola mundo", language_code="es"
    )

    assert ruta.called
    assert ruta.calls.last.request.url.path == "/v1/audios/generate"
    assert ruta.calls.last.request.headers["authorization"] == "Bearer vca_test"
    assert audio.id == "aud-1"
    assert audio.providerVoiceId is None
    assert audio.generationTimeMs == 1830
    assert audio.durationSeconds == 3.5
    assert audio.emotion == "neutral"


@respx.mock
def test_list_pagina_y_deserializa_cada_audio(cliente, audio_json):
    ruta = respx.get(f"{BASE_URL}/audios").mock(
        return_value=httpx.Response(
            200,
            json={"items": [audio_json], "total": 1, "page": 3, "limit": 5},
        )
    )

    pagina = cliente.audios.list(page=3, limit=5)

    peticion = ruta.calls.last.request
    assert peticion.url.params["page"] == "3"
    assert peticion.url.params["limit"] == "5"
    assert (pagina.total, pagina.page, pagina.limit) == (1, 3, 5)
    assert pagina.items[0].characterCount == 10
    assert pagina.items[0].providerVoiceId is None


@respx.mock
def test_get_deserializa_la_respuesta_real(cliente, audio_json):
    ruta = respx.get(f"{BASE_URL}/audios/aud-1").mock(
        return_value=httpx.Response(200, json=audio_json)
    )

    audio = cliente.audios.get("aud-1")

    assert ruta.calls.last.request.url.path == "/v1/audios/aud-1"
    assert audio.textContent == "Hola mundo"
    assert audio.generationTimeMs == 1830


@respx.mock
def test_download_devuelve_los_bytes_del_audio(cliente):
    respx.get(f"{BASE_URL}/audios/aud-1/download").mock(
        return_value=httpx.Response(200, content=b"ID3-audio")
    )

    assert cliente.audios.download("aud-1") == b"ID3-audio"


@respx.mock
def test_delete_no_devuelve_nada_ante_un_204(cliente):
    ruta = respx.delete(f"{BASE_URL}/audios/aud-1").mock(
        return_value=httpx.Response(204)
    )

    assert cliente.audios.delete("aud-1") is None
    assert ruta.calls.last.request.method == "DELETE"
