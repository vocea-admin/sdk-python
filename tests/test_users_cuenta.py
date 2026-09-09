"""Contrato HTTP del perfil, la clave de API y el borrado de cuenta.

El saldo vive en `test_users.py`; aquí está todo lo demás de `users`.
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
def usuario_json() -> dict[str, Any]:
    """El perfil tal y como sale de `UsersService.sanitize()`.

    `sanitize()` no elige campos: copia la entidad `User` entera y borra sus
    ocho secretos (`passwordHash`, los cuatro tokens de verificación y de
    reseteo, `refreshTokenHash`, `birthYear` y `apiKey`). Todo lo demás viaja,
    incluidas siete columnas internas que la dataclass no declara y que
    `from_dict` tiene que descartar en vez de reventar.
    """
    return {
        "id": "usr-1",
        "email": "ana@vocea.app",
        "fullName": "Ana Pérez",
        "isVerified": True,
        "role": "user",
        "balance": SALDO_EXACTO,
        "preferredLanguage": "es",
        "providerAccountId": None,
        "verificationLastSentAt": "2026-09-01T00:00:03.000Z",
        "affiliateCode": "ANA2026",
        "referredByCode": None,
        "welcomeBonusGrantedAt": "2026-09-01T00:00:05.000Z",
        "normalizedEmail": "ana@vocea.app",
        "registrationIp": "203.0.113.7",
        "createdAt": "2026-09-01T00:00:00.000Z",
        "updatedAt": "2026-09-02T00:00:00.000Z",
    }


@respx.mock
def test_me_deserializa_el_perfil_entero_que_manda_el_backend(cliente, usuario_json):
    """Contra la respuesta real, con sus siete columnas internas incluidas.

    Si `from_dict` dejara de descartarlas, `me()` moriría con un `TypeError`
    por leer campos que el SDK ni siquiera expone.
    """
    ruta = respx.get(f"{BASE_URL}/users/me").mock(
        return_value=httpx.Response(200, json=usuario_json)
    )

    perfil = cliente.users.me()

    assert ruta.called
    assert ruta.calls.last.request.method == "GET"
    assert ruta.calls.last.request.url.path == "/v1/users/me"
    assert ruta.calls.last.request.headers["authorization"] == "Bearer vca_test"
    assert perfil.id == "usr-1"
    assert perfil.email == "ana@vocea.app"
    assert perfil.fullName == "Ana Pérez"
    assert perfil.preferredLanguage == "es"
    assert perfil.role == "user"
    assert perfil.isVerified is True
    # El saldo del perfil es el mismo decimal de ocho cifras que `balance()`:
    # llega como número y no se redondea por el camino.
    assert perfil.balance == SALDO_EXACTO
    assert isinstance(perfil.balance, float)
    # Lo interno se queda fuera: el afiliado y la IP de registro no son parte
    # del modelo público aunque el backend los mande.
    assert not hasattr(perfil, "affiliateCode")
    assert not hasattr(perfil, "registrationIp")


@respx.mock
def test_me_con_una_clave_invalida_lanza_vocea_error(cliente):
    """Un 401 no puede llegar al usuario como un `User` a medio construir."""
    respx.get(f"{BASE_URL}/users/me").mock(
        return_value=httpx.Response(
            401, json={"statusCode": 401, "message": "Invalid API key"}
        )
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.users.me()

    assert excinfo.value.status_code == 401
    assert "Invalid API key" in str(excinfo.value)


@respx.mock
def test_update_solo_del_nombre_manda_una_unica_clave(cliente, usuario_json):
    """Un campo que no se indica no puede viajar.

    `preferred_language` a `None` en el cuerpo sería una orden de borrar el
    idioma del usuario, no un "déjalo como está".
    """
    ruta = respx.patch(f"{BASE_URL}/users/me").mock(
        return_value=httpx.Response(200, json={**usuario_json, "fullName": "Ana Gil"})
    )

    perfil = cliente.users.update(full_name="Ana Gil")

    peticion = ruta.calls.last.request
    assert peticion.method == "PATCH"
    assert peticion.url.path == "/v1/users/me"
    assert json.loads(peticion.read()) == {"full_name": "Ana Gil"}
    # La respuesta vuelve en camelCase aunque la petición fuese snake_case:
    # es la asimetría del contrato, no una errata.
    assert perfil.fullName == "Ana Gil"
    assert perfil.preferredLanguage == "es"


@respx.mock
def test_update_manda_los_dos_campos_en_snake_case(cliente, usuario_json):
    """Los nombres del cuerpo son los del DTO del backend; en camelCase el
    `ValidationPipe` los rechazaría por desconocidos."""
    ruta = respx.patch(f"{BASE_URL}/users/me").mock(
        return_value=httpx.Response(
            200, json={**usuario_json, "fullName": "Ana Gil", "preferredLanguage": "en"}
        )
    )

    perfil = cliente.users.update(full_name="Ana Gil", preferred_language="en")

    assert json.loads(ruta.calls.last.request.read()) == {
        "full_name": "Ana Gil",
        "preferred_language": "en",
    }
    assert perfil.preferredLanguage == "en"


@respx.mock
def test_update_sin_ningun_campo_no_llega_a_pedir_nada(cliente):
    """Un PATCH vacío gastaría una petición para no cambiar nada; el SDK lo
    corta antes de salir a la red."""
    ruta = respx.patch(f"{BASE_URL}/users/me")

    with pytest.raises(ValueError, match="al menos un campo"):
        cliente.users.update()

    assert not ruta.called


@respx.mock
def test_update_propaga_los_errores_de_validacion_del_backend(cliente):
    """El nombre tiene un mínimo de dos caracteres que solo valida el servidor:
    su 400 tiene que llegar como `VoceaError`, no como un perfil falso."""
    respx.patch(f"{BASE_URL}/users/me").mock(
        return_value=httpx.Response(
            400,
            json={
                "statusCode": 400,
                "message": ["full_name must be longer than or equal to 2 characters"],
                "error": "Bad Request",
            },
        )
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.users.update(full_name="A")

    assert excinfo.value.status_code == 400
    assert "longer than or equal to 2" in str(excinfo.value)


@respx.mock
def test_api_key_status_consulta_la_ruta_de_estado_y_no_la_clave(cliente):
    """El estado vive en `/api-key/status`, una ruta distinta de la que emite
    la clave: confundirlas crearía una clave nueva al preguntar por ella."""
    ruta = respx.get(f"{BASE_URL}/users/me/api-key/status").mock(
        return_value=httpx.Response(200, json={"hasApiKey": True})
    )

    estado = cliente.users.api_key_status()

    assert ruta.calls.last.request.method == "GET"
    assert ruta.calls.last.request.url.path == "/v1/users/me/api-key/status"
    assert estado.hasApiKey is True


@respx.mock
def test_create_api_key_va_por_post_y_devuelve_la_clave_en_claro(cliente):
    """Es la única respuesta que trae la clave legible: el backend solo guarda
    su hash, así que perderla aquí es perderla del todo."""
    ruta = respx.post(f"{BASE_URL}/users/me/api-key").mock(
        return_value=httpx.Response(201, json={"apiKey": "vca_" + "ab12" * 16})
    )

    creada = cliente.users.create_api_key()

    assert ruta.calls.last.request.method == "POST"
    assert ruta.calls.last.request.url.path == "/v1/users/me/api-key"
    assert creada.apiKey == "vca_" + "ab12" * 16


@respx.mock
def test_delete_api_key_revoca_con_delete_en_la_misma_ruta(cliente):
    """Emitir y revocar comparten ruta y solo se distinguen por el verbo: un
    POST donde tocaba DELETE dejaría al usuario con una clave nueva y viva."""
    ruta = respx.delete(f"{BASE_URL}/users/me/api-key").mock(
        return_value=httpx.Response(200, json={"message": "API key revocada correctamente"})
    )

    mensaje = cliente.users.delete_api_key()

    assert ruta.calls.last.request.method == "DELETE"
    assert ruta.calls.last.request.url.path == "/v1/users/me/api-key"
    assert mensaje == "API key revocada correctamente"


@respx.mock
def test_delete_api_key_sin_cuerpo_devuelve_cadena_vacia(cliente):
    """La revocación ya surtió efecto aunque la respuesta venga vacía: el SDK
    devuelve un texto vacío en vez de estallar contra un `None`."""
    respx.delete(f"{BASE_URL}/users/me/api-key").mock(
        return_value=httpx.Response(204)
    )

    assert cliente.users.delete_api_key() == ""


@respx.mock
def test_delete_account_borra_con_delete_y_tolera_un_204_sin_cuerpo(cliente):
    """El borrado responde 204 y no manda JSON; intentar deserializarlo
    convertiría una cuenta ya borrada en una excepción."""
    ruta = respx.delete(f"{BASE_URL}/users/me").mock(
        return_value=httpx.Response(204)
    )

    assert cliente.users.delete_account() is None

    peticion = ruta.calls.last.request
    assert peticion.method == "DELETE"
    assert peticion.url.path == "/v1/users/me"
    assert peticion.headers["authorization"] == "Bearer vca_test"
