from __future__ import annotations
from typing import Any, Optional
from .._http import HttpClient
from ..models import LoginResponse


class AuthResource:
    """Ciclo de vida de la cuenta: alta, acceso y recuperación.

    Son las únicas llamadas que funcionan sin clave de API, y ese es el punto:
    `register` y `login` son la forma de llegar a las credenciales que necesita
    el resto del SDK. Para usar solo este recurso, construye el cliente con una
    clave vacía.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def register(
        self,
        full_name: str,
        email: str,
        password: str,
        birth_year: int,
        referral_code: Optional[str] = None,
    ) -> str:
        """Crea una cuenta y devuelve el mensaje de confirmación.

        No devuelve una sesión: hay que verificar el correo antes de entrar.
        `birth_year` es obligatorio porque la plataforma no admite menores.
        """
        body: dict[str, Any] = {
            "full_name": full_name,
            "email": email,
            "password": password,
            "birth_year": birth_year,
        }
        if referral_code:
            body["referral_code"] = referral_code
        d = self._http.request("POST", "/auth/register", json=body)
        return (d or {}).get("message", "")

    def login(self, email: str, password: str) -> LoginResponse:
        """Cambia credenciales por un token de acceso y el perfil del usuario."""
        d = self._http.request(
            "POST", "/auth/login", json={"email": email, "password": password}
        )
        return LoginResponse.from_dict(d)

    def verify_email(self, token: str) -> None:
        """Confirma una dirección con el token del correo de verificación."""
        self._http.request("POST", "/auth/verify-email", json={"token": token})

    def resend_verification(self, email: str) -> None:
        """Reenvía el correo de verificación."""
        self._http.request("POST", "/auth/resend-verification", json={"email": email})

    def forgot_password(self, email: str) -> None:
        """Inicia el restablecimiento de contraseña.

        Responde igual exista o no la dirección: distinguirlas convertiría el
        formulario en un comprobador de qué correos están registrados.
        """
        self._http.request("POST", "/auth/forgot-password", json={"email": email})

    def reset_password(self, token: str, new_password: str) -> None:
        """Fija una contraseña nueva con el token del correo de recuperación."""
        self._http.request(
            "POST",
            "/auth/reset-password",
            json={"token": token, "new_password": new_password},
        )

    def logout(self) -> None:
        """Invalida la sesión actual en el servidor."""
        self._http.request("POST", "/auth/logout")
