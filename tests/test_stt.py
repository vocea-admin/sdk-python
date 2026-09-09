"""Contrato HTTP del recurso de transcripción."""

from __future__ import annotations

import io

import httpx
import respx

from .conftest import BASE_URL


@respx.mock
def test_transcribe_sube_el_audio_y_deserializa_el_saldo_consumido(cliente):
    ruta = respx.post(f"{BASE_URL}/stt/transcribe").mock(
        return_value=httpx.Response(
            200,
            json={
                "transcript": "hola mundo",
                "characterCount": 10,
                "balanceConsumed": 0.00031250,
                "durationMs": 1200,
            },
        )
    )

    resultado = cliente.stt.transcribe(io.BytesIO(b"audio"), language="es-ES")

    peticion = ruta.calls.last.request
    assert peticion.url.params["language"] == "es-ES"
    assert 'name="audio"' in peticion.read().decode("utf-8", "replace")
    assert resultado.balanceConsumed == 0.00031250
    assert resultado.transcript == "hola mundo"
