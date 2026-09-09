from __future__ import annotations
from typing import Any, Optional
from .._http import HttpClient
from ..models import ApiKeyCreated, ApiKeyStatus, UsdBalance, User


class UsersResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def me(self) -> User:
        """Perfil del usuario autenticado."""
        return User.from_dict(self._http.request("GET", "/users/me"))

    def update(
        self,
        full_name: Optional[str] = None,
        preferred_language: Optional[str] = None,
    ) -> User:
        """Actualiza el perfil.

        Solo viajan los campos que indiques, así que cambiar el nombre no toca
        el idioma. La petición usa snake_case y la respuesta vuelve en
        camelCase: son formas distintas del mismo dato, no una errata.
        """
        body: dict[str, Any] = {}
        if full_name is not None:
            body["full_name"] = full_name
        if preferred_language is not None:
            body["preferred_language"] = preferred_language
        if not body:
            raise ValueError("update requiere al menos un campo que cambiar")
        return User.from_dict(self._http.request("PATCH", "/users/me", json=body))

    def balance(self) -> UsdBalance:
        """Saldo disponible del usuario autenticado.

        `balance` es el valor decimal en dólares, con ocho decimales de
        precisión, y llega como número.
        """
        return UsdBalance.from_dict(self._http.request("GET", "/users/me/balance"))

    def api_key_status(self) -> ApiKeyStatus:
        """Indica si la cuenta tiene ya una clave emitida.

        No dice cuál: el backend guarda solo su hash.
        """
        return ApiKeyStatus.from_dict(
            self._http.request("GET", "/users/me/api-key/status")
        )

    def create_api_key(self) -> ApiKeyCreated:
        """Emite una clave de API nueva y la devuelve.

        Es la única vez que la clave es legible: solo se almacena su hash, así
        que una clave perdida no se recupera, se reemplaza. Crear una sustituye
        a la anterior.
        """
        return ApiKeyCreated.from_dict(
            self._http.request("POST", "/users/me/api-key")
        )

    def delete_api_key(self) -> str:
        """Revoca la clave de API actual y devuelve el mensaje de la API."""
        d = self._http.request("DELETE", "/users/me/api-key")
        return (d or {}).get("message", "")

    def delete_account(self) -> None:
        """Borra la cuenta. El saldo restante se pierde y no se recupera."""
        self._http.request("DELETE", "/users/me")
