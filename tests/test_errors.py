"""Los errores de la API llegan como VoceaError, con el cuerpo intacto."""

from __future__ import annotations

import httpx
import pytest
import respx

from vocea_sdk import VoceaError

from .conftest import BASE_URL


@respx.mock
def test_saldo_insuficiente_llega_como_vocea_error(cliente):
    respx.get(f"{BASE_URL}/voices/voz-1").mock(
        return_value=httpx.Response(
            402, json={"statusCode": 402, "message": "Insufficient balance"}
        )
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.voices.get("voz-1")

    assert excinfo.value.status_code == 402
    assert excinfo.value.body["message"] == "Insufficient balance"
    assert "Insufficient balance" in str(excinfo.value)


@respx.mock
def test_una_lista_de_mensajes_de_validacion_se_une_en_uno(cliente):
    respx.get(f"{BASE_URL}/voices/voz-1").mock(
        return_value=httpx.Response(
            400, json={"statusCode": 400, "message": ["name is required", "too short"]}
        )
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.voices.get("voz-1")

    assert "name is required, too short" in str(excinfo.value)
