"""La URL por defecto del cliente.

Este fichero nace de un fallo real: `DEFAULT_BASE_URL` se publicó como
`https://vocea.app/api/api/v1`, con el segmento `/api` repetido. Quien
instanciaba `VoceaClient(api_key=...)` sin pasar `base_url` hablaba con una
dirección que no existe, así que el SDK no servía recién instalado. No había
ningún test sobre la URL por defecto y por eso el fallo sobrevivió.
"""

from __future__ import annotations

import httpx
import respx

from vocea_sdk import VoceaClient
from vocea_sdk.client import DEFAULT_BASE_URL


URL_PUBLICA = "https://vocea.app/api/v1"


def test_la_url_por_defecto_es_la_publica_de_la_api():
    """Misma base que los SDK de Node y Go: un solo `/api`."""
    assert DEFAULT_BASE_URL == URL_PUBLICA


@respx.mock
def test_un_cliente_sin_base_url_llama_a_la_url_publica():
    """La constante no basta: hay que ver que es la que acaba en la petición."""
    ruta = respx.get(f"{URL_PUBLICA}/users/me/balance").mock(
        return_value=httpx.Response(200, json={"balance": 1.5})
    )

    VoceaClient(api_key="vca_test").users.balance()

    assert ruta.called
    peticion = ruta.calls.last.request
    assert peticion.url.host == "vocea.app"
    # El path completo, para que un `/api` de más no pase desapercibido.
    assert peticion.url.path == "/api/v1/users/me/balance"


@respx.mock
def test_una_base_url_explicita_sustituye_a_la_por_defecto():
    """Instancias propias: lo que se pasa manda sobre la constante."""
    ruta = respx.get("http://localhost:3000/api/v1/users/me/balance").mock(
        return_value=httpx.Response(200, json={"balance": 1.5})
    )

    cliente = VoceaClient(api_key="vca_test", base_url="http://localhost:3000/api/v1")
    cliente.users.balance()

    assert ruta.called
    assert ruta.calls.last.request.url.host == "localhost"
