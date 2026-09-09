"""Contrato HTTP del recurso de usuario."""

from __future__ import annotations

import httpx
import respx

from .conftest import BASE_URL, SALDO_EXACTO


@respx.mock
def test_balance_pide_users_me_balance_y_deserializa_el_decimal(cliente):
    ruta = respx.get(f"{BASE_URL}/users/me/balance").mock(
        return_value=httpx.Response(200, json={"balance": SALDO_EXACTO})
    )

    saldo = cliente.users.balance()

    assert ruta.called
    assert ruta.calls.last.request.method == "GET"
    assert ruta.calls.last.request.url.path == "/v1/users/me/balance"
    assert ruta.calls.last.request.headers["authorization"] == "Bearer vca_test"
    # Llega como número y no pierde ninguna de las ocho cifras decimales.
    assert saldo.balance == SALDO_EXACTO
    assert isinstance(saldo.balance, float)
