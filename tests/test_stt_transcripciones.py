"""Contrato HTTP del historial de transcripciones (`stt.list_transcriptions`
y `stt.delete_transcription`).

Estos dos endpoints no pasan por ningún `toPublic()`: `SttService.findAll()`
devuelve las entidades `Transcription` tal cual salen del repositorio, así que
por el cable viaja la fila entera —`userId`, `balanceConsumed`,
`languageCode`, `audioSizeBytes`— y no solo los cinco campos que declara la
dataclass. El fixture de este fichero copia esa fila completa a propósito.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from vocea_sdk import VoceaError
from vocea_sdk.models import Transcription

from .conftest import BASE_URL


@pytest.fixture
def transcripcion_json() -> dict[str, Any]:
    """Una transcripción tal y como la emite `GET /stt/transcriptions`.

    Es la entidad `Transcription` completa: el listado no filtra columnas. El
    `balanceConsumed` lleva las ocho cifras del DECIMAL(15,8) que el
    `decimalTransformer` del backend normaliza a número antes de serializar.
    """
    return {
        "id": "tr-1",
        "userId": "usr-1",
        "transcript": "hola mundo",
        "characterCount": 10,
        "balanceConsumed": 0.00031250,
        "languageCode": "es-ES",
        "audioSizeBytes": 48211,
        "durationMs": 1200,
        "createdAt": "2026-09-03T10:15:00.000Z",
    }


@respx.mock
def test_list_transcriptions_pagina_por_query_y_no_por_ruta(cliente, transcripcion_json):
    """`page` y `limit` viajan como query sobre `/stt/transcriptions`: si el SDK
    los metiera en la ruta o los omitiera, el backend serviría siempre la
    primera página de veinte y el usuario no vería el resto del historial."""
    ruta = respx.get(f"{BASE_URL}/stt/transcriptions").mock(
        return_value=httpx.Response(
            200,
            json={"items": [transcripcion_json], "total": 41, "page": 3, "limit": 5},
        )
    )

    pagina = cliente.stt.list_transcriptions(page=3, limit=5)

    peticion = ruta.calls.last.request
    assert peticion.method == "GET"
    assert peticion.url.path == "/v1/stt/transcriptions"
    assert peticion.url.params["page"] == "3"
    assert peticion.url.params["limit"] == "5"
    assert peticion.headers["authorization"] == "Bearer vca_test"
    assert (pagina.total, pagina.page, pagina.limit) == (41, 3, 5)


@respx.mock
def test_list_transcriptions_manda_la_primera_pagina_cuando_no_se_pide_nada(cliente):
    """Los valores por defecto tienen que viajar de verdad: `HttpClient` descarta
    los parámetros a None, y un `page`/`limit` ausente dejaría que el backend
    decidiera el tamaño de página a espaldas de quien lee `limit` en la
    respuesta."""
    ruta = respx.get(f"{BASE_URL}/stt/transcriptions").mock(
        return_value=httpx.Response(
            200, json={"items": [], "total": 0, "page": 1, "limit": 20}
        )
    )

    pagina = cliente.stt.list_transcriptions()

    peticion = ruta.calls.last.request
    assert peticion.url.params["page"] == "1"
    assert peticion.url.params["limit"] == "20"
    assert pagina.items == []


@respx.mock
def test_list_transcriptions_deserializa_la_fila_entera_sin_atragantarse(
    cliente, transcripcion_json
):
    """El listado devuelve la entidad completa, con columnas que la dataclass no
    declara (`userId`, `audioSizeBytes`, `languageCode`): tienen que caer sin
    romper el modelo, y los campos declarados llegar tipados."""
    respx.get(f"{BASE_URL}/stt/transcriptions").mock(
        return_value=httpx.Response(
            200,
            json={"items": [transcripcion_json], "total": 1, "page": 1, "limit": 20},
        )
    )

    pagina = cliente.stt.list_transcriptions()

    transcripcion = pagina.items[0]
    assert isinstance(transcripcion, Transcription)
    assert transcripcion.id == "tr-1"
    assert transcripcion.transcript == "hola mundo"
    assert transcripcion.characterCount == 10
    assert transcripcion.durationMs == 1200
    assert transcripcion.createdAt == "2026-09-03T10:15:00.000Z"
    # Las columnas de más se descartan, no se cuelan como atributos.
    assert not hasattr(transcripcion, "userId")
    assert not hasattr(transcripcion, "audioSizeBytes")


@respx.mock
def test_una_transcripcion_sin_duracion_se_deserializa_como_none(
    cliente, transcripcion_json
):
    """`duration_ms` es nullable en la tabla: las transcripciones antiguas y las
    de audios cuya duración no se pudo medir llegan con `durationMs: null` y no
    pueden tumbar el listado entero."""
    sin_duracion = {**transcripcion_json, "id": "tr-2", "durationMs": None}
    respx.get(f"{BASE_URL}/stt/transcriptions").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [transcripcion_json, sin_duracion],
                "total": 2,
                "page": 1,
                "limit": 20,
            },
        )
    )

    pagina = cliente.stt.list_transcriptions()

    assert [t.id for t in pagina.items] == ["tr-1", "tr-2"]
    assert pagina.items[1].durationMs is None
    # La que sí trae duración no se contagia.
    assert pagina.items[0].durationMs == 1200


@respx.mock
def test_delete_transcription_va_por_delete_a_la_ruta_del_id(cliente):
    """El borrado es un DELETE contra `/stt/transcriptions/{id}` sin cuerpo, y el
    204 del backend se traduce a None en vez de intentar parsear un JSON vacío."""
    ruta = respx.delete(f"{BASE_URL}/stt/transcriptions/tr-1").mock(
        return_value=httpx.Response(204)
    )

    assert cliente.stt.delete_transcription("tr-1") is None

    peticion = ruta.calls.last.request
    assert peticion.method == "DELETE"
    assert peticion.url.path == "/v1/stt/transcriptions/tr-1"
    assert peticion.url.params == httpx.QueryParams()
    assert peticion.read() == b""
    assert peticion.headers["authorization"] == "Bearer vca_test"


@respx.mock
def test_borrar_una_transcripcion_ajena_o_inexistente_llega_como_vocea_error(cliente):
    """`SttService.remove()` responde 404 tanto si la transcripción no existe como
    si es de otro usuario, y lo hace solo con `errorCode`: el SDK tiene que
    conservar el estado y el código, que es lo estable, sin inventarse mensaje."""
    respx.delete(f"{BASE_URL}/stt/transcriptions/tr-fantasma").mock(
        return_value=httpx.Response(404, json={"errorCode": "TRANSCRIPTION_NOT_FOUND"})
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.stt.delete_transcription("tr-fantasma")

    assert excinfo.value.status_code == 404
    assert excinfo.value.error_code == "TRANSCRIPTION_NOT_FOUND"
    assert "TRANSCRIPTION_NOT_FOUND" in str(excinfo.value)
