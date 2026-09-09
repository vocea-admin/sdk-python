"""Contrato HTTP del recurso de saldo: paquetes, checkout y transacciones."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from vocea_sdk import VoceaError

from .conftest import BASE_URL


PAQUETE_JSON = {
    "id": "paq-1",
    "name": "Starter",
    "priceUsd": 9.99,
    "isActive": True,
    "lemonsqueezyVariantId": "123456",
    "createdAt": "2026-09-01T00:00:00.000Z",
}

# Tal y como sale del backend: además de los campos publicados, el movimiento
# arrastra columnas internas de la entidad.
MOVIMIENTO_JSON = {
    "id": "mov-1",
    "userId": "usr-1",
    "audioId": None,
    "transcriptionId": None,
    "packageId": "paq-1",
    "type": "purchase",
    "amount": 9.99,
    "balanceAfter": 19.98,
    "description": "Compra del paquete Starter",
    "lemonsqueezyOrderId": "ord-1",
    "createdAt": "2026-09-02T00:00:00.000Z",
}


# ─── Paquetes ──────────────────────────────────────────────────────────────


@respx.mock
def test_list_packages_pide_balance_packages(cliente):
    ruta = respx.get(f"{BASE_URL}/balance/packages").mock(
        return_value=httpx.Response(200, json=[PAQUETE_JSON])
    )

    paquetes = cliente.balance.list_packages()

    assert ruta.called
    assert ruta.calls.last.request.method == "GET"
    assert ruta.calls.last.request.url.path == "/v1/balance/packages"
    assert len(paquetes) == 1
    assert paquetes[0].id == "paq-1"
    assert paquetes[0].name == "Starter"
    # El precio llega como número, no como cadena.
    assert paquetes[0].priceUsd == 9.99
    assert isinstance(paquetes[0].priceUsd, float)
    assert paquetes[0].isActive is True
    assert paquetes[0].lemonsqueezyVariantId == "123456"
    assert paquetes[0].createdAt == "2026-09-01T00:00:00.000Z"


# ─── Checkout ──────────────────────────────────────────────────────────────


@respx.mock
def test_checkout_hace_post_con_package_id_en_el_cuerpo(cliente):
    ruta = respx.post(f"{BASE_URL}/balance/checkout").mock(
        return_value=httpx.Response(201, json={"checkoutUrl": "https://pago/xyz"})
    )

    respuesta = cliente.balance.checkout("paq-1")

    peticion = ruta.calls.last.request
    assert peticion.method == "POST"
    assert peticion.url.path == "/v1/balance/checkout"
    # El nombre del campo es el del DTO del backend: package_id, no packageId.
    assert json.loads(peticion.read()) == {"package_id": "paq-1"}
    # Sin success_url no viaja la query: la API pone su destino por defecto.
    assert "success_url" not in peticion.url.params
    assert respuesta.checkoutUrl == "https://pago/xyz"


@respx.mock
def test_checkout_pasa_success_url_como_query(cliente):
    ruta = respx.post(f"{BASE_URL}/balance/checkout").mock(
        return_value=httpx.Response(201, json={"checkoutUrl": "https://pago/xyz"})
    )

    cliente.balance.checkout("paq-1", success_url="https://mi-app/gracias")

    peticion = ruta.calls.last.request
    assert peticion.url.params["success_url"] == "https://mi-app/gracias"
    assert json.loads(peticion.read()) == {"package_id": "paq-1"}


@respx.mock
def test_checkout_de_un_paquete_inexistente_llega_como_vocea_error(cliente):
    respx.post(f"{BASE_URL}/balance/checkout").mock(
        return_value=httpx.Response(
            404, json={"statusCode": 404, "message": "Paquete de saldo no encontrado"}
        )
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.balance.checkout("paq-fantasma")

    assert excinfo.value.status_code == 404


# ─── Transacciones ─────────────────────────────────────────────────────────


@respx.mock
def test_list_transactions_pide_balance_transactions_paginado(cliente):
    ruta = respx.get(f"{BASE_URL}/balance/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [MOVIMIENTO_JSON],
                "total": 1,
                "page": 2,
                "limit": 5,
                "totalPages": 1,
            },
        )
    )

    pagina = cliente.balance.list_transactions(page=2, limit=5)

    peticion = ruta.calls.last.request
    assert peticion.method == "GET"
    assert peticion.url.path == "/v1/balance/transactions"
    assert peticion.url.params["page"] == "2"
    assert peticion.url.params["limit"] == "5"
    # Sin filtro, el tipo no viaja: la API devolvería solo ese tipo si viajara.
    assert "type" not in peticion.url.params
    assert peticion.headers["authorization"] == "Bearer vca_test"

    assert (pagina.total, pagina.page, pagina.limit) == (1, 2, 5)
    movimiento = pagina.items[0]
    assert movimiento.id == "mov-1"
    assert movimiento.type == "purchase"
    assert movimiento.amount == 9.99
    assert isinstance(movimiento.amount, float)
    assert movimiento.description == "Compra del paquete Starter"
    assert movimiento.createdAt == "2026-09-02T00:00:00.000Z"


@respx.mock
def test_list_transactions_filtra_por_tipo(cliente):
    consumo = {
        **MOVIMIENTO_JSON,
        "id": "mov-2",
        "type": "consumption",
        "amount": -0.00031250,
        "description": "Generación de audio",
    }
    ruta = respx.get(f"{BASE_URL}/balance/transactions").mock(
        return_value=httpx.Response(
            200,
            json={"items": [consumo], "total": 1, "page": 1, "limit": 20, "totalPages": 1},
        )
    )

    pagina = cliente.balance.list_transactions(type="consumption")

    assert ruta.calls.last.request.url.params["type"] == "consumption"
    # El consumo llega en negativo y con los ocho decimales intactos.
    assert pagina.items[0].amount == -0.00031250
    assert pagina.items[0].type == "consumption"
