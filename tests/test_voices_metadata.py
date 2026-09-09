"""Contrato HTTP de la metadata y de las ganancias de una voz.

Son los dos pasos del camino de una voz al catálogo público: primero se le
rellenan país, región y edad (`update_metadata`), y una vez publicada se
consulta lo que factura (`earnings`).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from vocea_sdk import VoceaError

from .conftest import BASE_URL, SALDO_EXACTO


@pytest.fixture
def voz_con_metadata_json() -> dict[str, Any]:
    """La voz que devuelve `PATCH /voices/:id/metadata`.

    Es `toPublic()` sin los extras del listado: no trae `isFavorited` ni
    `favoritesCount`, y `country`/`region` llegan como entidades completas
    —con su `isActive`— porque el backend recarga esas relaciones.
    """
    return {
        "id": "voz-1",
        "name": "Mi voz",
        "status": "active",
        "failureReason": None,
        "cloneAudioDuration": 41.28,
        "languageCode": "es",
        "countryId": "co-1",
        "country": {"id": "co-1", "name": "España", "code": "ES", "isActive": True},
        "regionId": "re-1",
        "region": {"id": "re-1", "countryId": "co-1", "name": "Andalucía", "isActive": True},
        "ageRange": "adult",
        "gender": "female",
        "isPublicRequest": False,
        "isPublic": False,
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
            }
        ],
        "hasSamplePreview": True,
    }


@pytest.fixture
def ganancias_json() -> dict[str, Any]:
    """Lo que emite `VoicesService.getEarnings()`.

    `month` es una columna `date`, así que viaja como 'YYYY-MM-DD' y no como
    fecha ISO completa, y los importes salen del transformador de decimales
    con sus ocho cifras. Los meses vienen en orden descendente.
    """
    return {
        "earnings": [
            {"month": "2026-09-01", "balanceEarned": 7.125},
            {"month": "2026-08-01", "balanceEarned": 3.30044375},
        ],
        "balanceEarnedTotal": SALDO_EXACTO,
        "timesUsed": 47,
    }


def _cuerpo(peticion: httpx.Request) -> dict[str, Any]:
    return json.loads(peticion.content)


@respx.mock
def test_update_metadata_manda_solo_los_campos_indicados(cliente, voz_con_metadata_json):
    """Un campo omitido no puede viajar como null: el PATCH lo interpretaría
    como "bórralo" y dejaría la voz fuera del catálogo público.
    """
    ruta = respx.patch(f"{BASE_URL}/voices/voz-1/metadata").mock(
        return_value=httpx.Response(200, json=voz_con_metadata_json)
    )

    voz = cliente.voices.update_metadata("voz-1", country_id="co-1", age_range="adult")

    peticion = ruta.calls.last.request
    assert peticion.method == "PATCH"
    assert peticion.url.path == "/v1/voices/voz-1/metadata"
    assert peticion.headers["authorization"] == "Bearer vca_test"
    assert _cuerpo(peticion) == {"countryId": "co-1", "ageRange": "adult"}
    # La respuesta es la voz entera, con las relaciones ya recargadas.
    assert voz.region is not None and voz.region.name == "Andalucía"
    assert voz.country is not None and voz.country.code == "ES"
    assert voz.ageRange == "adult"
    # El endpoint no informa los extras del listado: quedan en None, que no es
    # lo mismo que "no favorita" ni que "cero favoritos".
    assert voz.isFavorited is None
    assert voz.favoritesCount is None


@respx.mock
def test_update_metadata_no_arrastra_los_campos_que_no_se_pasan(cliente, voz_con_metadata_json):
    """Fijar solo la región deja intactos país y edad: el cuerpo lleva una
    única clave, no las cinco con cuatro nulos.
    """
    ruta = respx.patch(f"{BASE_URL}/voices/voz-1/metadata").mock(
        return_value=httpx.Response(200, json=voz_con_metadata_json)
    )

    cliente.voices.update_metadata("voz-1", region_id="re-1")

    cuerpo = _cuerpo(ruta.calls.last.request)
    assert cuerpo == {"regionId": "re-1"}
    assert "countryId" not in cuerpo
    assert "ageRange" not in cuerpo
    assert "newCountryName" not in cuerpo
    assert "newRegionName" not in cuerpo


@respx.mock
def test_update_metadata_propone_pais_y_region_nuevos(cliente, voz_con_metadata_json):
    """Los nombres nuevos son la vía para un origen que aún no está en el
    catálogo: si no viajaran, el backend nunca crearía la entrada.
    """
    ruta = respx.patch(f"{BASE_URL}/voices/voz-1/metadata").mock(
        return_value=httpx.Response(200, json=voz_con_metadata_json)
    )

    cliente.voices.update_metadata(
        "voz-1",
        new_country_name="España",
        new_region_name="Andalucía",
        age_range="adult",
    )

    assert _cuerpo(ruta.calls.last.request) == {
        "newCountryName": "España",
        "newRegionName": "Andalucía",
        "ageRange": "adult",
    }


@respx.mock
def test_update_metadata_sin_ningun_campo_no_gasta_la_peticion(cliente):
    """Un PATCH con el cuerpo vacío devolvería la voz sin tocar nada y el
    usuario creería haberla actualizado: el error se detecta antes de salir.
    """
    ruta = respx.patch(f"{BASE_URL}/voices/voz-1/metadata")

    with pytest.raises(ValueError, match="al menos un campo"):
        cliente.voices.update_metadata("voz-1")

    assert not ruta.called


@respx.mock
def test_earnings_deserializa_el_historial_mensual(cliente, ganancias_json):
    """Es dinero: si algún punto del camino redondea un importe o se come un
    mes, el propietario de la voz ve una cifra que no es la suya.
    """
    ruta = respx.get(f"{BASE_URL}/voices/voz-1/earnings").mock(
        return_value=httpx.Response(200, json=ganancias_json)
    )

    ganancias = cliente.voices.earnings("voz-1")

    peticion = ruta.calls.last.request
    assert peticion.method == "GET"
    assert peticion.url.path == "/v1/voices/voz-1/earnings"
    assert peticion.headers["authorization"] == "Bearer vca_test"
    assert [m.month for m in ganancias.earnings] == ["2026-09-01", "2026-08-01"]
    # Los decimales llegan como números y con las ocho cifras intactas.
    assert ganancias.earnings[0].balanceEarned == 7.125
    assert ganancias.earnings[1].balanceEarned == 3.30044375
    assert ganancias.balanceEarnedTotal == SALDO_EXACTO
    assert isinstance(ganancias.balanceEarnedTotal, float)
    assert ganancias.timesUsed == 47


@respx.mock
def test_earnings_de_una_voz_sin_historial_devuelve_lista_vacia(cliente):
    """Una voz recién publicada no tiene meses todavía: eso es una lista
    vacía, no un fallo ni un None que reviente al iterar.
    """
    respx.get(f"{BASE_URL}/voices/voz-2/earnings").mock(
        return_value=httpx.Response(
            200, json={"earnings": [], "balanceEarnedTotal": 0, "timesUsed": 0}
        )
    )

    ganancias = cliente.voices.earnings("voz-2")

    assert ganancias.earnings == []
    assert ganancias.balanceEarnedTotal == 0


@respx.mock
def test_una_metadata_incompleta_estalla_al_pedir_publicar(cliente, voz_con_metadata_json):
    """Rellenar solo el país deja la voz a medias y el backend la rechaza al
    publicarla. El motivo se lee en `error_code`, que es estable; el mensaje
    cambia con el idioma y con la versión, y aquí ni siquiera viene.
    """
    respx.patch(f"{BASE_URL}/voices/voz-1/metadata").mock(
        return_value=httpx.Response(
            200, json={**voz_con_metadata_json, "regionId": None, "region": None}
        )
    )
    respx.post(f"{BASE_URL}/voices/voz-1/request-public").mock(
        return_value=httpx.Response(
            400, json={"statusCode": 400, "errorCode": "VOICE_METADATA_INCOMPLETE"}
        )
    )

    voz = cliente.voices.update_metadata("voz-1", country_id="co-1")
    assert voz.regionId is None

    with pytest.raises(VoceaError) as excinfo:
        cliente.voices.request_public("voz-1")

    assert excinfo.value.status_code == 400
    assert excinfo.value.error_code == "VOICE_METADATA_INCOMPLETE"
    # Sin `message`, el texto del error cae al código en vez de a un dict crudo.
    assert "VOICE_METADATA_INCOMPLETE" in str(excinfo.value)
