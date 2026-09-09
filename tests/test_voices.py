"""Contrato HTTP del recurso de voces."""

from __future__ import annotations

import io

import httpx
import pytest
import respx

from .conftest import BASE_URL, SALDO_EXACTO


def _muestra(nombre: str, contenido: bytes) -> tuple[str, io.BytesIO, str]:
    return (nombre, io.BytesIO(contenido), "audio/mpeg")


@respx.mock
def test_get_deserializa_la_respuesta_real_de_la_api(cliente, voz_json):
    """Contra el JSON entero del backend, no contra un subconjunto cómodo.

    Con la voz completa este `get()` moría con un `TypeError`: seis campos que
    el backend manda no estaban declarados en la dataclass.
    """
    ruta = respx.get(f"{BASE_URL}/voices/voz-1").mock(
        return_value=httpx.Response(200, json=voz_json)
    )

    voz = cliente.voices.get("voz-1")

    assert ruta.called
    # El decimal llega como número y no pierde precisión al deserializarse.
    assert voz.balanceEarnedTotal == SALDO_EXACTO
    assert voz.country is not None and voz.country.code == "ES"
    assert voz.gender == "female"
    assert voz.cloneAudioDuration == 41.28
    assert [p.name for p in voz.providers] == ["inworld", "elevenlabs"]


@respx.mock
def test_list_pagina_y_autentica(cliente, voz_json):
    ruta = respx.get(f"{BASE_URL}/voices").mock(
        return_value=httpx.Response(
            200, json={"items": [voz_json], "total": 1, "page": 2, "limit": 5}
        )
    )

    pagina = cliente.voices.list(page=2, limit=5)

    peticion = ruta.calls.last.request
    assert peticion.url.params["page"] == "2"
    assert peticion.url.params["limit"] == "5"
    assert peticion.headers["authorization"] == "Bearer vca_test"
    assert pagina.items[0].balanceEarnedTotal == SALDO_EXACTO


@respx.mock
def test_list_public_filtra_sin_arrastrar_los_nulos(cliente, voz_json):
    ruta = respx.get(f"{BASE_URL}/voices/public").mock(
        return_value=httpx.Response(
            200, json={"items": [voz_json], "total": 1, "page": 1, "limit": 20}
        )
    )

    cliente.voices.list_public(country_id="co-1")

    params = ruta.calls.last.request.url.params
    assert params["countryId"] == "co-1"
    assert "regionId" not in params
    assert "ageRange" not in params


@respx.mock
def test_clone_envia_provider_ids_y_todas_las_muestras(cliente, voz_json):
    ruta = respx.post(f"{BASE_URL}/voices/clone").mock(
        return_value=httpx.Response(201, json=voz_json)
    )

    cliente.voices.clone(
        name="Mi voz",
        audio_samples=[_muestra("a.mp3", b"uno"), _muestra("b.mp3", b"dos")],
        provider_ids=["prov-a", "prov-b"],
        sample_text="Hola",
        language_code="es",
    )

    cuerpo = ruta.calls.last.request.read().decode("utf-8", "replace")
    # Los proveedores viajan como partes repetidas, que es como la API recibe
    # las listas de un multipart.
    assert cuerpo.count('name="providerIds"') == 2
    assert "prov-a" in cuerpo
    assert "prov-b" in cuerpo
    assert cuerpo.count('name="audio_sample"') == 2
    assert 'name="sample_text"' in cuerpo
    assert 'name="language_code"' in cuerpo


@respx.mock
def test_clone_exige_al_menos_un_proveedor(cliente):
    # Antes, una lista vacía hacía que la API clonara en todos los proveedores
    # activos: el usuario ocupaba plazas del pool que no había pedido. Ahora es
    # obligatorio elegir, y el error se detecta aquí sin gastar una petición.
    ruta = respx.post(f"{BASE_URL}/voices/clone")

    with pytest.raises(ValueError, match="provider_id"):
        cliente.voices.clone(
            name="Mi voz", audio_samples=[_muestra("a.mp3", b"uno")], provider_ids=[]
        )

    assert not ruta.called


@respx.mock
def test_sample_devuelve_los_bytes_del_audio(cliente):
    respx.get(f"{BASE_URL}/voices/voz-1/sample").mock(
        return_value=httpx.Response(200, content=b"ID3-audio")
    )

    assert cliente.voices.sample("voz-1") == b"ID3-audio"
