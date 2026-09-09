"""Contrato HTTP del recurso de modelos TTS.

El listado y el detalle son dos formas distintas del mismo modelo y el SDK las
representa con dos tipos distintos a propósito. `GET /tts-models` devuelve la
entidad casi entera —incluidos `providerId` y `maxCharacters`—; `GET
/tts-models/:id` se sirve con un `select` reducido que no los trae.

Que el listado conserve `providerId` no es un detalle cosmético: es el único
sitio del que el SDK puede sacar los identificadores que `voices.clone()`
exige. Mientras el listado se deserializaba como `TtsModel`, esos ids se
descartaban en silencio al construir la dataclass y `clone()` era inusable
salvo que el llamante los conociera por fuera.
"""

from __future__ import annotations

import dataclasses
import io

import httpx
import pytest
import respx

from vocea_sdk import TtsConfig, TtsLanguage, TtsModel, TtsModelListItem, VoceaError

from .conftest import BASE_URL


# Las claves exactas que emite `GET /tts-models`: la entidad `TtsModel` entera
# menos las tres que el servicio quita antes de responder (`providerModelId` y
# `provider`, que solo sirven para filtrar, y `costPerMillionUsd`, que es coste
# interno de negocio).
CLAVES_DEL_LISTADO = {
    "id",
    "name",
    "description",
    "providerId",
    "maxCharacters",
    "isActive",
    "sortOrder",
    "createdAt",
}

# Las claves de `GET /tts-models/:id`, que es el `PUBLIC_SELECT` del servicio.
CLAVES_DEL_DETALLE = {"id", "name", "description", "isActive", "sortOrder", "createdAt"}


@pytest.fixture
def listado_json() -> list[dict]:
    """Dos modelos tal y como salen de `TtsModelsService.findAll()`."""
    return [
        {
            "id": "mod-1",
            "name": "Vocea Pro",
            "description": "Máxima calidad",
            "providerId": "prov-a",
            "maxCharacters": 5000,
            "isActive": True,
            "sortOrder": 0,
            "createdAt": "2026-09-01T00:00:00.000Z",
        },
        {
            "id": "mod-2",
            "name": "Vocea Lite",
            "description": None,
            "providerId": "prov-b",
            "maxCharacters": 2000,
            "isActive": True,
            "sortOrder": 1,
            "createdAt": "2026-09-01T00:00:00.000Z",
        },
    ]


@pytest.fixture
def detalle_json() -> dict:
    """Un modelo tal y como sale de `TtsModelsService.findOne()`."""
    return {
        "id": "mod-1",
        "name": "Vocea Pro",
        "description": "Máxima calidad",
        "isActive": True,
        "sortOrder": 0,
        "createdAt": "2026-09-01T00:00:00.000Z",
    }


def _campos(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


# ─── El listado conserva los identificadores que clone() necesita ──────────


@respx.mock
def test_list_puebla_provider_id_y_max_characters_desde_el_json(cliente, listado_json):
    """Son los dos campos que el listado añade y que antes se perdían.

    Deserializar el listado como `TtsModel` los descartaba sin aviso: la
    llamada devolvía objetos aparentemente correctos a los que les faltaba
    justo lo único que el detalle no puede dar.
    """
    ruta = respx.get(f"{BASE_URL}/tts-models").mock(
        return_value=httpx.Response(200, json=listado_json)
    )

    modelos = cliente.models.list()

    assert ruta.called
    assert ruta.calls.last.request.method == "GET"
    assert ruta.calls.last.request.url.path == "/v1/tts-models"
    assert ruta.calls.last.request.headers["authorization"] == "Bearer vca_test"
    assert [m.providerId for m in modelos] == ["prov-a", "prov-b"]
    assert [m.maxCharacters for m in modelos] == [5000, 2000]
    # Y el resto del modelo sigue llegando entero, no solo los dos campos nuevos.
    assert [m.id for m in modelos] == ["mod-1", "mod-2"]
    assert modelos[0].name == "Vocea Pro"
    assert modelos[1].description is None
    assert modelos[0].sortOrder == 0
    assert modelos[0].createdAt == "2026-09-01T00:00:00.000Z"


@respx.mock
def test_list_devuelve_tts_model_list_item_y_el_detalle_no(
    cliente, listado_json, detalle_json
):
    """Listado y detalle son tipos distintos porque las respuestas lo son.

    `TtsModel` no declara `providerId` ni `maxCharacters` a conciencia: el
    detalle no los envía, y fingir que sí llevaría a leer un valor inventado.
    """
    respx.get(f"{BASE_URL}/tts-models").mock(
        return_value=httpx.Response(200, json=listado_json)
    )
    respx.get(f"{BASE_URL}/tts-models/mod-1").mock(
        return_value=httpx.Response(200, json=detalle_json)
    )

    del_listado = cliente.models.list()[0]
    del_detalle = cliente.models.get("mod-1")

    assert type(del_listado) is TtsModelListItem
    assert type(del_detalle) is TtsModel
    # El elemento del listado es un `TtsModel`; al revés, no.
    assert isinstance(del_listado, TtsModel)
    assert not isinstance(del_detalle, TtsModelListItem)
    assert not hasattr(del_detalle, "providerId")
    assert not hasattr(del_detalle, "maxCharacters")


def test_los_dos_tipos_declaran_lo_que_emite_cada_endpoint(listado_json, detalle_json):
    """Los fixtures son la respuesta real, no un subconjunto cómodo.

    Si el listado y el detalle dejaran de diferenciarse en los mismos dos
    campos, el motivo para tener dos tipos habría desaparecido y este test
    tiene que enterarse.
    """
    assert set(listado_json[0]) == CLAVES_DEL_LISTADO
    assert set(detalle_json) == CLAVES_DEL_DETALLE
    assert CLAVES_DEL_LISTADO <= _campos(TtsModelListItem)
    assert CLAVES_DEL_DETALLE <= _campos(TtsModel)
    assert _campos(TtsModelListItem) - _campos(TtsModel) == {"providerId", "maxCharacters"}


@respx.mock
def test_el_provider_id_del_listado_alimenta_a_voices_clone(
    cliente, listado_json, voz_json
):
    """Este es el recorrido completo que justifica el tipo del listado.

    `clone()` rechaza una lista vacía de proveedores, así que sin el
    `providerId` del listado el SDK no podía clonar por sí solo.
    """
    respx.get(f"{BASE_URL}/tts-models").mock(
        return_value=httpx.Response(200, json=listado_json)
    )
    clonar = respx.post(f"{BASE_URL}/voices/clone").mock(
        return_value=httpx.Response(201, json=voz_json)
    )

    proveedores = [m.providerId for m in cliente.models.list()]
    cliente.voices.clone(
        name="Mi voz",
        audio_samples=[("muestra.mp3", io.BytesIO(b"ID3"), "audio/mpeg")],
        provider_ids=proveedores,
    )

    cuerpo = clonar.calls.last.request.content
    assert b'name="providerIds"' in cuerpo
    assert b"prov-a" in cuerpo and b"prov-b" in cuerpo


@respx.mock
def test_un_elemento_sin_provider_id_no_finge_tener_uno(cliente, listado_json):
    """Los valores por defecto son un requisito de la herencia, no un dato.

    `TtsModelListItem` hereda campos sin defecto, así que los suyos obligan a
    tenerlo. Que sean `""` y `0` —falsos ambos— permite al llamante detectar
    un modelo mal configurado con un simple `if not m.providerId`.
    """
    sin_proveedor = {k: v for k, v in listado_json[0].items() if k != "providerId"}
    respx.get(f"{BASE_URL}/tts-models").mock(
        return_value=httpx.Response(200, json=[sin_proveedor])
    )

    modelo = cliente.models.list()[0]

    assert modelo.providerId == ""
    assert not modelo.providerId


# ─── Idiomas y configuración: from_dict en vez de desempaquetar ────────────


@respx.mock
def test_languages_deserializa_y_aguanta_una_clave_nueva(cliente):
    """`TtsLanguage(**lang)` reventaba con `TypeError` en cuanto el backend
    añadiera un campo al catálogo de idiomas; `from_dict` lo descarta."""
    ruta = respx.get(f"{BASE_URL}/tts-models/languages").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"code": "en", "name": "English"},
                {"code": "es", "name": "Spanish", "flag": "🇪🇸", "rtl": False},
            ],
        )
    )

    idiomas = cliente.models.languages()

    assert ruta.calls.last.request.url.path == "/v1/tts-models/languages"
    assert idiomas == [
        TtsLanguage(code="en", name="English"),
        TtsLanguage(code="es", name="Spanish"),
    ]
    assert not hasattr(idiomas[1], "flag")


@respx.mock
def test_lite_languages_usa_su_propia_ruta_y_tambien_es_tolerante(cliente):
    """El conjunto reducido cuelga de `/languages/lite`: no es el mismo
    endpoint filtrado en cliente, y comparte la tolerancia del completo."""
    ruta = respx.get(f"{BASE_URL}/tts-models/languages/lite").mock(
        return_value=httpx.Response(
            200, json=[{"code": "es", "name": "Spanish", "tier": "standard"}]
        )
    )

    idiomas = cliente.models.lite_languages()

    assert ruta.calls.last.request.url.path == "/v1/tts-models/languages/lite"
    assert idiomas == [TtsLanguage(code="es", name="Spanish")]


@respx.mock
def test_config_deserializa_los_dos_conjuntos_y_aguanta_una_clave_nueva(cliente):
    """`config()` decide qué catálogo de idiomas ofrecer, así que una bandera
    nueva en la respuesta no puede dejar al cliente sin saberlo."""
    ruta = respx.get(f"{BASE_URL}/tts-models/config").mock(
        return_value=httpx.Response(200, json={"full": False, "lite": True, "beta": True})
    )

    config = cliente.models.config()

    assert ruta.calls.last.request.url.path == "/v1/tts-models/config"
    assert config == TtsConfig(full=False, lite=True)
    assert isinstance(config, TtsConfig)


# ─── Errores ───────────────────────────────────────────────────────────────


@respx.mock
def test_get_de_un_modelo_inexistente_lanza_vocea_error(cliente):
    """El 404 del catálogo no trae `errorCode`: el mensaje es lo único que hay.

    Fijarlo evita que un cambio en `VoceaError` deje este caso describiéndose
    como el diccionario crudo.
    """
    respx.get(f"{BASE_URL}/tts-models/no-existe").mock(
        return_value=httpx.Response(
            404,
            json={
                "message": "Modelo Vocea con ID no-existe no encontrado",
                "error": "Not Found",
                "statusCode": 404,
            },
        )
    )

    with pytest.raises(VoceaError) as exc:
        cliente.models.get("no-existe")

    assert exc.value.status_code == 404
    assert exc.value.error_code is None
    assert "Modelo Vocea con ID no-existe no encontrado" in str(exc.value)
