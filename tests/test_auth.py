"""Contrato HTTP del recurso de autenticación.

Es el único recurso que se usa sin clave de API, así que su contrato es la
puerta de entrada al resto del SDK: si `login` deserializa mal, nadie llega a
emitir una clave.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from vocea_sdk import VoceaError
from vocea_sdk.models import User

from .conftest import BASE_URL, SALDO_EXACTO


@pytest.fixture
def usuario_json() -> dict[str, Any]:
    """El usuario anidado en un login, tal y como sale de `sanitizeUser()`.

    Es la entidad `User` entera menos sus secretos (`passwordHash`, los tokens
    de verificación y de recuperación, `refreshTokenHash`, `birthYear` y
    `apiKey`). Las claves internas que sí viajan —`normalizedEmail`,
    `registrationIp`, `providerAccountId`…— están aquí a propósito: el SDK no
    las declara y tiene que saber descartarlas sin romperse.
    """
    return {
        "id": "usr-1",
        "email": "juan@example.com",
        "fullName": "Juan Pérez",
        "isVerified": True,
        "role": "user",
        "balance": SALDO_EXACTO,
        "preferredLanguage": "es",
        "providerAccountId": None,
        "verificationLastSentAt": "2026-09-01T00:00:00.000Z",
        "affiliateCode": None,
        "referredByCode": "AFIL123",
        "welcomeBonusGrantedAt": "2026-09-01T00:00:05.000Z",
        "normalizedEmail": "juan@example.com",
        "registrationIp": "203.0.113.7",
        "createdAt": "2026-09-01T00:00:00.000Z",
        "updatedAt": "2026-09-02T00:00:00.000Z",
    }


def cuerpo(peticion: httpx.Request) -> Any:
    """El JSON que de verdad viajó en la petición."""
    return json.loads(peticion.read())


# ─── Alta de cuenta ─────────────────────────────────────────────────────────


@respx.mock
def test_register_manda_los_campos_en_snake_case(cliente):
    """El DTO del backend valida en snake_case: mandar `fullName` sería un 400
    de validación, no un alta."""
    ruta = respx.post(f"{BASE_URL}/auth/register").mock(
        return_value=httpx.Response(
            201, json={"message": "Cuenta creada. Revisa tu correo para verificarla."}
        )
    )

    mensaje = cliente.auth.register(
        full_name="Juan Pérez",
        email="juan@example.com",
        password="Contraseña123!",
        birth_year=1990,
    )

    peticion = ruta.calls.last.request
    assert peticion.method == "POST"
    assert peticion.url.path == "/v1/auth/register"
    assert cuerpo(peticion) == {
        "full_name": "Juan Pérez",
        "email": "juan@example.com",
        "password": "Contraseña123!",
        "birth_year": 1990,
    }
    assert mensaje == "Cuenta creada. Revisa tu correo para verificarla."


@respx.mock
def test_register_omite_referral_code_cuando_no_se_pasa(cliente):
    """Mandar `referral_code: null` no es lo mismo que no mandarlo: el backend
    atribuiría el alta a un afiliado inexistente en vez de a ninguno."""
    ruta = respx.post(f"{BASE_URL}/auth/register").mock(
        return_value=httpx.Response(201, json={"message": "Cuenta creada."})
    )

    cliente.auth.register(
        full_name="Juan Pérez",
        email="juan@example.com",
        password="Contraseña123!",
        birth_year=1990,
    )

    assert "referral_code" not in cuerpo(ruta.calls.last.request)


@respx.mock
def test_register_incluye_referral_code_cuando_se_pasa(cliente):
    """Con código de afiliado el alta acredita el bono de referido: si el SDK
    lo perdiera por el camino, el afiliado no cobraría y nadie se enteraría."""
    ruta = respx.post(f"{BASE_URL}/auth/register").mock(
        return_value=httpx.Response(201, json={"message": "Cuenta creada."})
    )

    cliente.auth.register(
        full_name="Juan Pérez",
        email="juan@example.com",
        password="Contraseña123!",
        birth_year=1990,
        referral_code="AFIL123",
    )

    assert cuerpo(ruta.calls.last.request)["referral_code"] == "AFIL123"


@respx.mock
def test_register_devuelve_cadena_vacia_si_la_respuesta_no_trae_message(cliente):
    """El alta se completó aunque el cuerpo venga vacío: devolver `None` haría
    reventar a quien imprima el mensaje, y el error no sería del SDK."""
    respx.post(f"{BASE_URL}/auth/register").mock(return_value=httpx.Response(204))

    assert (
        cliente.auth.register(
            full_name="Juan Pérez",
            email="juan@example.com",
            password="Contraseña123!",
            birth_year=1990,
        )
        == ""
    )


# ─── Inicio y cierre de sesión ──────────────────────────────────────────────


@respx.mock
def test_login_construye_un_user_de_verdad_y_no_un_diccionario(cliente, usuario_json):
    """`LoginResponse` tiene un `from_dict` a medida solo por este anidamiento:
    la copia genérica dejaría un `dict` donde el tipo promete un `User`."""
    ruta = respx.post(f"{BASE_URL}/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c3ItMSJ9.firma",
                "user": usuario_json,
            },
        )
    )

    sesion = cliente.auth.login("juan@example.com", "Contraseña123!")

    peticion = ruta.calls.last.request
    assert peticion.url.path == "/v1/auth/login"
    assert cuerpo(peticion) == {
        "email": "juan@example.com",
        "password": "Contraseña123!",
    }
    assert sesion.access_token.startswith("eyJ")
    assert isinstance(sesion.user, User)
    assert sesion.user.fullName == "Juan Pérez"
    assert sesion.user.isVerified is True


@respx.mock
def test_login_conserva_el_decimal_del_saldo_del_usuario_anidado(cliente, usuario_json):
    """El saldo cruza dos deserializaciones —la del login y la del `User`— y es
    dinero: cualquier redondeo por el camino se ve aquí."""
    respx.post(f"{BASE_URL}/auth/login").mock(
        return_value=httpx.Response(
            200, json={"access_token": "eyJ.token", "user": usuario_json}
        )
    )

    sesion = cliente.auth.login("juan@example.com", "Contraseña123!")

    assert sesion.user.balance == SALDO_EXACTO
    assert isinstance(sesion.user.balance, float)


@respx.mock
def test_login_no_revienta_si_la_respuesta_trae_claves_que_el_sdk_no_declara(
    cliente, usuario_json
):
    """El usuario saneado viaja con campos internos (`normalizedEmail`,
    `registrationIp`…) que el modelo no declara: se descartan, no tumban al
    cliente."""
    respx.post(f"{BASE_URL}/auth/login").mock(
        return_value=httpx.Response(
            200, json={"access_token": "eyJ.token", "user": usuario_json}
        )
    )

    sesion = cliente.auth.login("juan@example.com", "Contraseña123!")

    assert sesion.user.id == "usr-1"
    assert not hasattr(sesion.user, "registrationIp")


@respx.mock
def test_logout_va_a_auth_logout_con_la_clave_y_sin_cuerpo(cliente):
    """Cerrar sesión invalida el refresh token del servidor: sin la cabecera de
    autorización el backend no sabría cuál."""
    ruta = respx.post(f"{BASE_URL}/auth/logout").mock(
        return_value=httpx.Response(200, json={"message": "Sesión cerrada"})
    )

    assert cliente.auth.logout() is None

    peticion = ruta.calls.last.request
    assert peticion.method == "POST"
    assert peticion.url.path == "/v1/auth/logout"
    assert peticion.headers["authorization"] == "Bearer vca_test"
    assert peticion.read() == b""


# ─── Verificación de correo ─────────────────────────────────────────────────


@respx.mock
def test_verify_email_manda_el_token_del_correo(cliente):
    """El token del enlace es lo único que activa la cuenta: viaja en el cuerpo,
    no en la ruta ni en la query."""
    ruta = respx.post(f"{BASE_URL}/auth/verify-email").mock(
        return_value=httpx.Response(200, json={"message": "Cuenta verificada exitosamente"})
    )

    assert cliente.auth.verify_email("tok-verificacion") is None
    assert cuerpo(ruta.calls.last.request) == {"token": "tok-verificacion"}


@respx.mock
def test_verify_email_soporta_un_204_sin_cuerpo(cliente):
    """Un 204 no trae JSON que deserializar: intentar leerlo convertiría un
    éxito en una excepción."""
    respx.post(f"{BASE_URL}/auth/verify-email").mock(return_value=httpx.Response(204))

    assert cliente.auth.verify_email("tok-verificacion") is None


@respx.mock
def test_resend_verification_manda_solo_el_correo(cliente):
    """Reenviar el enlace se pide sin sesión: la dirección es el único dato con
    el que cuenta el backend."""
    ruta = respx.post(f"{BASE_URL}/auth/resend-verification").mock(
        return_value=httpx.Response(
            200, json={"message": "Si el correo existe, recibirás un nuevo enlace"}
        )
    )

    assert cliente.auth.resend_verification("juan@example.com") is None

    peticion = ruta.calls.last.request
    assert peticion.url.path == "/v1/auth/resend-verification"
    assert cuerpo(peticion) == {"email": "juan@example.com"}


# ─── Recuperación de contraseña ─────────────────────────────────────────────


@respx.mock
def test_forgot_password_responde_igual_exista_o_no_la_cuenta(cliente):
    """Con una dirección no registrada el backend devuelve el MISMO 200 y el
    mismo texto. Es deliberado: distinguir el caso convertiría el formulario en
    un comprobador de qué correos están dados de alta. Que nadie lo "arregle"
    propagando un 404 aquí."""
    respx.post(f"{BASE_URL}/auth/forgot-password").mock(
        return_value=httpx.Response(
            200, json={"message": "Si el correo existe, recibirás instrucciones"}
        )
    )

    assert cliente.auth.forgot_password("no-existe@example.com") is None


@respx.mock
def test_forgot_password_manda_el_correo_en_el_cuerpo(cliente):
    """La dirección va en el cuerpo y no en la query: en la query acabaría en
    los logs de acceso del proxy."""
    ruta = respx.post(f"{BASE_URL}/auth/forgot-password").mock(
        return_value=httpx.Response(
            200, json={"message": "Si el correo existe, recibirás instrucciones"}
        )
    )

    cliente.auth.forgot_password("juan@example.com")

    peticion = ruta.calls.last.request
    assert peticion.url.path == "/v1/auth/forgot-password"
    assert not peticion.url.params
    assert cuerpo(peticion) == {"email": "juan@example.com"}


@respx.mock
def test_reset_password_manda_token_y_new_password(cliente):
    """El DTO espera `new_password` en snake_case; `newPassword` o `password`
    pasarían la validación por alto y dejarían la contraseña sin cambiar."""
    ruta = respx.post(f"{BASE_URL}/auth/reset-password").mock(
        return_value=httpx.Response(
            200, json={"message": "Contraseña actualizada exitosamente"}
        )
    )

    assert cliente.auth.reset_password("tok-reset", "NuevaClave123!") is None
    assert cuerpo(ruta.calls.last.request) == {
        "token": "tok-reset",
        "new_password": "NuevaClave123!",
    }


@respx.mock
def test_reset_password_con_token_caducado_llega_como_vocea_error(cliente):
    """El token de recuperación expira en una hora: el 400 tiene que llegar como
    excepción y no como un `None` que se confunda con un éxito."""
    respx.post(f"{BASE_URL}/auth/reset-password").mock(
        return_value=httpx.Response(400, json={"statusCode": 400})
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.auth.reset_password("tok-caducado", "NuevaClave123!")

    assert excinfo.value.status_code == 400


# ─── Errores ────────────────────────────────────────────────────────────────


@respx.mock
def test_login_con_credenciales_invalidas_llega_como_vocea_error(cliente):
    """El filtro del backend borra el mensaje de los 401 para no revelar si
    falló el correo o la contraseña: `error_code` se consulta igual y devuelve
    `None` en vez de reventar."""
    respx.post(f"{BASE_URL}/auth/login").mock(
        return_value=httpx.Response(401, json={"statusCode": 401})
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.auth.login("juan@example.com", "mala")

    assert excinfo.value.status_code == 401
    assert excinfo.value.error_code is None
    assert "401" in str(excinfo.value)


@respx.mock
def test_login_sin_correo_verificado_expone_su_error_code(cliente):
    """Es el caso que se distingue de una credencial mala: quien integra decide
    entre "reenviar verificación" y "reintentar" mirando `error_code`, que es
    estable, y no el texto del mensaje."""
    respx.post(f"{BASE_URL}/auth/login").mock(
        return_value=httpx.Response(
            403, json={"statusCode": 403, "errorCode": "EMAIL_NOT_VERIFIED"}
        )
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.auth.login("juan@example.com", "Contraseña123!")

    assert excinfo.value.status_code == 403
    assert excinfo.value.error_code == "EMAIL_NOT_VERIFIED"
    assert "EMAIL_NOT_VERIFIED" in str(excinfo.value)
