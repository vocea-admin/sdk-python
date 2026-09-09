"""Contrato HTTP del panel de referidos: `referrals` y `referral_history`."""

from __future__ import annotations

import httpx
import pytest
import respx

from vocea_sdk import VoceaError

from .conftest import BASE_URL, SALDO_EXACTO


# Un referido que ya ha comprado: `findReferralStats()` le rellena los cuatro
# campos que salen de la tabla de comisiones.
REFERIDO_CON_COMPRA = {
    "refereeId": "usr-2",
    "refereeEmail": "comprador@ejemplo.com",
    "refereeName": "Ana Comprador",
    "totalUsd": SALDO_EXACTO,
    "latestStatus": "active",
    "latestDate": "2026-09-03T10:15:00.000Z",
    "hasPurchased": True,
}

# Un referido recién registrado: no hay ninguna fila de comisión suya, así que
# el backend manda `latestStatus` nulo, `totalUsd` a cero y, hoy por hoy, cae
# de vuelta a su fecha de alta en `latestDate`.
REFERIDO_SIN_COMPRA = {
    "refereeId": "usr-3",
    "refereeEmail": "recien@ejemplo.com",
    "refereeName": "Beto Recién",
    "totalUsd": 0,
    "latestStatus": None,
    "latestDate": "2026-09-08T18:00:00.000Z",
    "hasPurchased": False,
}


# ─── Panel de referidos ────────────────────────────────────────────────────


@respx.mock
def test_referrals_pide_balance_referrals_y_deserializa_el_panel_entero(cliente):
    """Fija la ruta y las tres claves del panel: si `totalEarned` o
    `referralPercentage` se perdieran, el usuario vería cero comisión ganada."""
    ruta = respx.get(f"{BASE_URL}/balance/referrals").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [REFERIDO_CON_COMPRA, REFERIDO_SIN_COMPRA],
                "totalEarned": SALDO_EXACTO,
                "referralPercentage": 5,
            },
        )
    )

    panel = cliente.balance.referrals()

    peticion = ruta.calls.last.request
    assert peticion.method == "GET"
    assert peticion.url.path == "/v1/balance/referrals"
    # El endpoint está tras el guard: sin cabecera no habría panel que leer.
    assert peticion.headers["authorization"] == "Bearer vca_test"
    # Sin query: el panel no se pagina ni se filtra.
    assert not peticion.url.params

    assert len(panel.items) == 2
    assert panel.totalEarned == SALDO_EXACTO
    assert panel.referralPercentage == 5

    comprador = panel.items[0]
    assert comprador.refereeId == "usr-2"
    assert comprador.refereeEmail == "comprador@ejemplo.com"
    assert comprador.refereeName == "Ana Comprador"
    assert comprador.latestStatus == "active"
    assert comprador.latestDate == "2026-09-03T10:15:00.000Z"
    assert comprador.hasPurchased is True
    # La comisión viene de una columna decimal(15,8): llega como número y
    # conserva las ocho cifras, no como cadena redondeada.
    assert comprador.totalUsd == SALDO_EXACTO
    assert isinstance(comprador.totalUsd, float)


@respx.mock
def test_referrals_acepta_un_referido_recien_registrado_sin_compras(cliente):
    """Un referido que aún no ha comprado llega con `latestStatus` nulo: el SDK
    debe deserializarlo como None en vez de reventar al construir el modelo."""
    respx.get(f"{BASE_URL}/balance/referrals").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [REFERIDO_SIN_COMPRA],
                "totalEarned": 0,
                "referralPercentage": 5,
            },
        )
    )

    panel = cliente.balance.referrals()

    recien = panel.items[0]
    assert recien.latestStatus is None
    assert recien.hasPurchased is False
    assert recien.totalUsd == 0
    # El resto de campos sí están: el referido existe aunque no haya gastado.
    assert recien.refereeEmail == "recien@ejemplo.com"


@respx.mock
def test_referrals_tolera_que_latest_date_llegue_nula(cliente):
    """`latestDate` está declarada opcional: una fila sin fecha —o un backend
    que deje de rellenarla— no puede tumbar la lectura del panel entero."""
    respx.get(f"{BASE_URL}/balance/referrals").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [{**REFERIDO_SIN_COMPRA, "latestDate": None}],
                "totalEarned": 0,
                "referralPercentage": 5,
            },
        )
    )

    panel = cliente.balance.referrals()

    assert panel.items[0].latestDate is None
    assert panel.items[0].latestStatus is None


@respx.mock
def test_referrals_sin_referidos_devuelve_lista_vacia_y_no_none(cliente):
    """Un usuario sin código de afiliado recibe `items: []`; quien recorra el
    panel debe encontrar una lista, no un None que rompa el bucle."""
    respx.get(f"{BASE_URL}/balance/referrals").mock(
        return_value=httpx.Response(
            200,
            json={"items": [], "totalEarned": 0, "referralPercentage": 5},
        )
    )

    panel = cliente.balance.referrals()

    assert panel.items == []
    assert panel.totalEarned == 0


# ─── Historial de un referido ──────────────────────────────────────────────


@respx.mock
def test_referral_history_pide_la_ruta_con_el_id_del_referido(cliente):
    """El id viaja en la ruta, no en query: fijarlo evita que un refactor lo
    mande como parámetro y la API responda con el historial equivocado."""
    ruta = respx.get(f"{BASE_URL}/balance/referrals/usr-2").mock(
        return_value=httpx.Response(
            200,
            json={
                "refereeId": "usr-2",
                "refereeEmail": "comprador@ejemplo.com",
                "refereeName": "Ana Comprador",
                "transactions": [
                    {
                        "id": "ref-1",
                        "date": "2026-09-03T10:15:00.000Z",
                        "commissionUsd": 0.49950000,
                        "status": "active",
                        "orderId": "ord-991",
                    },
                    {
                        "id": "ref-2",
                        "date": "2026-09-01T09:00:00.000Z",
                        "commissionUsd": 9.92544375,
                        "status": "reversed",
                        "orderId": "ord-990",
                    },
                ],
            },
        )
    )

    historial = cliente.balance.referral_history("usr-2")

    peticion = ruta.calls.last.request
    assert peticion.method == "GET"
    assert peticion.url.path == "/v1/balance/referrals/usr-2"
    assert peticion.headers["authorization"] == "Bearer vca_test"

    assert historial.refereeId == "usr-2"
    assert historial.refereeEmail == "comprador@ejemplo.com"
    assert historial.refereeName == "Ana Comprador"
    assert len(historial.transactions) == 2

    primera = historial.transactions[0]
    assert primera.id == "ref-1"
    assert primera.date == "2026-09-03T10:15:00.000Z"
    assert primera.status == "active"
    assert primera.orderId == "ord-991"
    # La comisión es el 5% de una recarga: son céntimos con ocho decimales y
    # cualquier redondeo por el camino descuadraría el total del panel.
    assert primera.commissionUsd == 0.49950000
    assert isinstance(primera.commissionUsd, float)

    # Una compra reembolsada no desaparece del historial: cambia de estado.
    segunda = historial.transactions[1]
    assert segunda.status == "reversed"
    assert segunda.commissionUsd == 9.92544375


@respx.mock
def test_referral_history_acepta_una_comision_sin_order_id(cliente):
    """`orderId` está declarado opcional: un ajuste manual sin pedido asociado
    debe leerse como None y no impedir ver el resto de comisiones."""
    respx.get(f"{BASE_URL}/balance/referrals/usr-2").mock(
        return_value=httpx.Response(
            200,
            json={
                "refereeId": "usr-2",
                "refereeEmail": "comprador@ejemplo.com",
                "refereeName": "Ana Comprador",
                "transactions": [
                    {
                        "id": "ref-3",
                        "date": "2026-09-04T12:00:00.000Z",
                        "commissionUsd": 0.00031250,
                        "status": "active",
                        "orderId": None,
                    }
                ],
            },
        )
    )

    historial = cliente.balance.referral_history("usr-2")

    comision = historial.transactions[0]
    assert comision.orderId is None
    assert comision.commissionUsd == 0.00031250


@respx.mock
def test_referral_history_sin_movimientos_devuelve_lista_vacia(cliente):
    """Un referido registrado que aún no ha comprado tiene ficha pero ninguna
    comisión: el historial llega vacío, no ausente."""
    respx.get(f"{BASE_URL}/balance/referrals/usr-3").mock(
        return_value=httpx.Response(
            200,
            json={
                "refereeId": "usr-3",
                "refereeEmail": "recien@ejemplo.com",
                "refereeName": "Beto Recién",
                "transactions": [],
            },
        )
    )

    historial = cliente.balance.referral_history("usr-3")

    assert historial.transactions == []
    assert historial.refereeName == "Beto Recién"


@respx.mock
def test_referral_history_de_un_referido_ajeno_llega_como_vocea_error(cliente):
    """El backend responde 404 cuando el id no es un referido de quien pregunta:
    el SDK debe propagarlo como VoceaError y no como un historial vacío."""
    respx.get(f"{BASE_URL}/balance/referrals/usr-ajeno").mock(
        return_value=httpx.Response(
            404,
            json={
                "message": "Referido no encontrado",
                "error": "Not Found",
                "statusCode": 404,
            },
        )
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.balance.referral_history("usr-ajeno")

    assert excinfo.value.status_code == 404
    assert "Referido no encontrado" in str(excinfo.value)
    # La API no manda `errorCode` en este error: quien lo mire encontrará None.
    assert excinfo.value.error_code is None
