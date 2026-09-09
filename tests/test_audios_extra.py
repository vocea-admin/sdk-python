"""Contrato del cuerpo que `audios.generate` manda, y de `play_url`.

`test_audios.py` mira lo que vuelve; aquí se mira lo que sale. El backend
decide por presencia de claves —`voice_id` y `provider_voice_id` son
excluyentes, y `advanced_params` se valida contra la calidad del modelo—, así
que una clave de más o un campo colocado en el nivel equivocado rompe la
llamada aunque el SDK compile.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from vocea_sdk import VoceaClient, VoceaError, premium_params

from .conftest import BASE_URL


def cuerpo(ruta) -> dict:
    """El JSON que viajó en la última petición de la ruta."""
    return json.loads(ruta.calls.last.request.content)


@pytest.fixture
def cliente_otra_base() -> VoceaClient:
    """Cliente contra otro host y con barra final, que `HttpClient` normaliza."""
    return VoceaClient(api_key="vca_test", base_url="https://otra.test/api/v1/")


@respx.mock
def test_generate_con_provider_voice_id_no_manda_voice_id(cliente, audio_json):
    """Mandar las dos claves es un 400: la voz del catálogo viaja sola."""
    ruta = respx.post(f"{BASE_URL}/audios/generate").mock(
        return_value=httpx.Response(201, json=audio_json)
    )

    cliente.audios.generate(
        provider_voice_id="Ashley", text="Hola mundo", language_code="en"
    )

    enviado = cuerpo(ruta)
    assert enviado["provider_voice_id"] == "Ashley"
    assert "voice_id" not in enviado
    assert enviado["text"] == "Hola mundo"
    assert enviado["language_code"] == "en"


@respx.mock
def test_generate_con_voice_id_no_manda_provider_voice_id(cliente, audio_json):
    """Simétrico del anterior: la voz clonada tampoco arrastra la del catálogo."""
    ruta = respx.post(f"{BASE_URL}/audios/generate").mock(
        return_value=httpx.Response(201, json=audio_json)
    )

    cliente.audios.generate(voice_id="voz-1", text="Hola mundo")

    enviado = cuerpo(ruta)
    assert enviado["voice_id"] == "voz-1"
    assert "provider_voice_id" not in enviado
    # El idioma por defecto es el español, y no se deduce del texto.
    assert enviado["language_code"] == "es"


@respx.mock
def test_generate_sin_ninguna_voz_falla_sin_gastar_la_peticion(cliente):
    """Sin voz la API cobraría un 400: mejor romper aquí y no gastar la llamada."""
    ruta = respx.post(f"{BASE_URL}/audios/generate")

    with pytest.raises(ValueError, match="voice_id o provider_voice_id"):
        cliente.audios.generate(text="Hola mundo")

    assert not ruta.called


@respx.mock
def test_generate_con_las_dos_voces_falla_sin_gastar_la_peticion(cliente):
    """Son excluyentes: pedir las dos es ambiguo y se corta antes del cable."""
    ruta = respx.post(f"{BASE_URL}/audios/generate")

    with pytest.raises(ValueError, match="pero no ambos"):
        cliente.audios.generate(
            voice_id="voz-1", provider_voice_id="Ashley", text="Hola mundo"
        )

    assert not ruta.called


@respx.mock
def test_generate_manda_speed_fuera_de_advanced_params(cliente, audio_json):
    """`speed` vale para todas las calidades; dentro de `advanced_params` sería
    un parámetro ajeno a la calidad y la API lo rechazaría."""
    ruta = respx.post(f"{BASE_URL}/audios/generate").mock(
        return_value=httpx.Response(201, json=audio_json)
    )

    cliente.audios.generate(
        voice_id="voz-1",
        text="Hola mundo",
        tts_model_id="mod-1",
        speed=1.25,
        advanced_params=premium_params(pitch=-3, volume=80, emotion="happy"),
    )

    enviado = cuerpo(ruta)
    assert enviado["speed"] == 1.25
    assert "speed" not in enviado["advanced_params"]
    assert enviado["advanced_params"] == {
        "pitch": -3,
        "volume": 80,
        "emotion": "happy",
    }
    assert enviado["tts_model_id"] == "mod-1"


@respx.mock
def test_generate_omite_los_opcionales_que_no_se_indican(cliente, audio_json):
    """El backend valida por presencia: una clave a null no es lo mismo que
    una clave ausente, así que lo que no se pide no puede viajar."""
    ruta = respx.post(f"{BASE_URL}/audios/generate").mock(
        return_value=httpx.Response(201, json=audio_json)
    )

    cliente.audios.generate(voice_id="voz-1", text="Hola mundo")

    enviado = cuerpo(ruta)
    assert set(enviado) == {"text", "language_code", "speed", "voice_id"}
    # `speed` sí viaja siempre, con su valor neutro.
    assert enviado["speed"] == 1.0


@respx.mock
def test_los_parametros_legacy_viajan_agrupados_en_voice_setting(cliente, audio_json):
    """La interfaz vieja sigue funcionando: sus tres campos se agrupan en
    `voice_setting` y en camelCase, que es lo que entiende la API."""
    ruta = respx.post(f"{BASE_URL}/audios/generate").mock(
        return_value=httpx.Response(201, json=audio_json)
    )

    cliente.audios.generate(
        voice_id="voz-1", text="Hola mundo", speaking_rate=0.9, emotion="sad"
    )

    enviado = cuerpo(ruta)
    assert enviado["voice_setting"] == {"speakingRate": 0.9, "emotion": "sad"}
    # `temperature` no se indicó: no aparece ni siquiera a null.
    assert "temperature" not in enviado["voice_setting"]


@respx.mock
def test_play_url_compone_la_url_sin_llamar_a_la_api(cliente):
    """Es una URL pública para un <audio> o para compartir: si hiciera una
    petición costaría una llamada y exigiría clave. Sin rutas montadas, respx
    haría fallar cualquier tráfico."""
    assert (
        cliente.audios.play_url("aud-1") == f"{BASE_URL}/audios/aud-1/play.mp3"
    )
    assert len(respx.calls) == 0


def test_play_url_respeta_el_base_url_del_cliente(cliente_otra_base):
    """Apuntar a otro entorno tiene que cambiar también la URL de reproducción,
    y la barra final del `base_url` no puede acabar duplicada."""
    assert (
        cliente_otra_base.audios.play_url("aud-1")
        == "https://otra.test/api/v1/audios/aud-1/play.mp3"
    )


@respx.mock
def test_advanced_params_de_otra_calidad_llega_como_vocea_error(cliente):
    """El 400 por parámetros de otra calidad hay que distinguirlo por
    `error_code`: el mensaje cambia con el idioma y con la versión."""
    respx.post(f"{BASE_URL}/audios/generate").mock(
        return_value=httpx.Response(
            400,
            json={
                "statusCode": 400,
                "errorCode": "INVALID_ADVANCED_PARAMS",
                "message": "Invalid advanced params for model quality 'standard'",
            },
        )
    )

    with pytest.raises(VoceaError) as excinfo:
        cliente.audios.generate(
            voice_id="voz-1",
            text="Hola mundo",
            advanced_params={"stability": 50},
        )

    assert excinfo.value.status_code == 400
    assert excinfo.value.error_code == "INVALID_ADVANCED_PARAMS"
