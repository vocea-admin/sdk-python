"""Contrato de los constructores de `advanced_params`.

Son funciones puras, así que aquí no hay respx salvo en el último test: lo que
se fija es qué claves emite cada calidad y, sobre todo, que la validación
rechaza lo que la API rechazaría. Enviar una clave de otra calidad devuelve 400
INVALID_ADVANCED_PARAMS y un `pitch` fuera de rango falla la generación entera,
de modo que cada `ValueError` de aquí es una llamada de red que no se gasta.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from vocea_sdk import premium_params, standard_params, studio_params
from vocea_sdk.params import EMOCIONES

from .conftest import BASE_URL


# --------------------------------------------------------------------------
# Claves y valores por defecto de cada calidad
# --------------------------------------------------------------------------


def test_standard_params_solo_emite_expressiveness_a_50():
    """Standard (Inworld) admite un único parámetro: colar cualquier otra clave
    haría fallar la llamada con INVALID_ADVANCED_PARAMS."""
    assert standard_params() == {"expressiveness": 50}


def test_premium_params_emite_sus_tres_claves_con_los_defectos_de_la_api():
    """Los valores por defecto tienen que ser los neutros de Minimax: 0
    semitonos, volumen medio y emoción `neutral`, que es dejar la voz como está."""
    assert premium_params() == {"pitch": 0, "volume": 50, "emotion": "neutral"}


def test_studio_params_emite_sus_tres_claves_con_los_defectos_de_la_api():
    """`clarity` por defecto es 75, no 50: es el punto en el que ElevenLabs se
    ciñe a la voz clonada sin sonar metálico, y no coincide con el resto."""
    assert studio_params() == {"stability": 50, "clarity": 75, "style": 0}


def test_las_tres_calidades_no_comparten_ninguna_clave():
    """Cada calidad tiene su juego de claves y no se solapan; si una empezara a
    emitir la de otra, la mezcla llegaría al backend y este la rechazaría."""
    estandar = set(standard_params())
    premium = set(premium_params())
    estudio = set(studio_params())

    assert estandar & premium == set()
    assert estandar & estudio == set()
    assert premium & estudio == set()


# --------------------------------------------------------------------------
# pitch: semitonos, no porcentaje
# --------------------------------------------------------------------------


@pytest.mark.parametrize("semitonos", [-12, -1, 0, 1, 12])
def test_premium_params_acepta_todo_el_rango_de_semitonos(semitonos):
    """El rango real es -12 a 12 semitonos —una octava arriba y otra abajo— y
    los dos extremos son valores válidos, no el primer error."""
    assert premium_params(pitch=semitonos)["pitch"] == semitonos


@pytest.mark.parametrize("fuera_de_rango", [13, -13, 50, -100, 100])
def test_premium_params_rechaza_el_pitch_fuera_de_los_doce_semitonos(fuera_de_rango):
    """El rango estuvo documentado como -100 a 100 y quien mandaba 50 creyendo
    que era un porcentaje se comía un 400: el SDK lo corta antes de la red."""
    with pytest.raises(ValueError, match="pitch"):
        premium_params(pitch=fuera_de_rango)


@pytest.mark.parametrize("decimal", [1.5, -0.5, 0.0, 12.0])
def test_premium_params_rechaza_un_pitch_decimal(decimal):
    """Son semitonos enteros: medio tono no existe en esta escala y un float
    llega al backend como valor inválido aunque su valor esté dentro del rango."""
    with pytest.raises(ValueError, match="entero"):
        premium_params(pitch=decimal)


def test_premium_params_rechaza_un_booleano_como_pitch():
    """En Python `True == 1`, así que un booleano pasaría por entero si solo se
    mirara el rango; se comprueba el tipo aparte para que no cuele."""
    with pytest.raises(ValueError, match="entero"):
        premium_params(pitch=True)


def test_premium_params_rechaza_un_booleano_como_volume():
    """Mismo agujero que en `pitch`: `False` valdría como 0 dentro de la escala
    0–100 si el tipo no se comprobara."""
    with pytest.raises(ValueError, match="entero"):
        premium_params(volume=False)


# --------------------------------------------------------------------------
# Escalas 0–100
# --------------------------------------------------------------------------


@pytest.mark.parametrize("extremo", [0, 100])
def test_las_escalas_de_cero_a_cien_aceptan_sus_extremos(extremo):
    """0 y 100 son valores legales de la escala, no el borde prohibido: la
    comparación tiene que ser inclusiva en los dos lados."""
    assert standard_params(expressiveness=extremo)["expressiveness"] == extremo
    assert premium_params(volume=extremo)["volume"] == extremo
    assert studio_params(stability=extremo)["stability"] == extremo
    assert studio_params(clarity=extremo)["clarity"] == extremo
    assert studio_params(style=extremo)["style"] == extremo


@pytest.mark.parametrize("fuera_de_rango", [-1, 101])
def test_las_escalas_de_cero_a_cien_rechazan_lo_que_se_sale(fuera_de_rango):
    """Un valor pasado de 100 o negativo se rechaza en cada parámetro por
    separado: la validación no puede quedarse solo en el primero."""
    with pytest.raises(ValueError, match="expressiveness"):
        standard_params(expressiveness=fuera_de_rango)
    with pytest.raises(ValueError, match="volume"):
        premium_params(volume=fuera_de_rango)
    with pytest.raises(ValueError, match="stability"):
        studio_params(stability=fuera_de_rango)
    with pytest.raises(ValueError, match="clarity"):
        studio_params(clarity=fuera_de_rango)
    with pytest.raises(ValueError, match="style"):
        studio_params(style=fuera_de_rango)


@pytest.mark.parametrize("no_entero", [50.5, "50", None])
def test_las_escalas_de_cero_a_cien_rechazan_lo_que_no_es_entero(no_entero):
    """Un string o un float llegarían al backend con el tipo cambiado; el
    mensaje del error nombra el tipo recibido para que se vea de dónde sale."""
    with pytest.raises(ValueError, match="entero"):
        studio_params(clarity=no_entero)


# --------------------------------------------------------------------------
# emotion
# --------------------------------------------------------------------------


@pytest.mark.parametrize("emocion", EMOCIONES)
def test_premium_params_acepta_todas_las_emociones_de_la_api(emocion):
    """La lista de emociones es la que reconoce el proveedor; si el SDK dejara
    fuera una válida, el usuario no tendría forma de pedirla."""
    assert premium_params(emotion=emocion)["emotion"] == emocion


@pytest.mark.parametrize("invalida", ["excited", "NEUTRAL", "", None])
def test_premium_params_rechaza_una_emocion_que_no_esta_en_la_lista(invalida):
    """La API compara la cadena exacta: ni un sinónimo ni un cambio de
    mayúsculas valen, y el fallo se ve mejor aquí que en un 400."""
    with pytest.raises(ValueError, match="emotion"):
        premium_params(emotion=invalida)


# --------------------------------------------------------------------------
# Integración: lo construido aquí es lo que viaja por el cable
# --------------------------------------------------------------------------


@respx.mock
def test_lo_que_produce_premium_params_llega_intacto_en_advanced_params(
    cliente, audio_json
):
    """El diccionario viaja tal cual dentro de `advanced_params`, sin reescalar
    el `pitch` ni sacarlo al nivel superior del cuerpo: -3 son -3 semitonos."""
    ruta = respx.post(f"{BASE_URL}/audios/generate").mock(
        return_value=httpx.Response(201, json=audio_json)
    )

    cliente.audios.generate(
        voice_id="voz-1",
        text="Hola mundo",
        advanced_params=premium_params(pitch=-3, volume=80, emotion="happy"),
    )

    cuerpo = json.loads(ruta.calls.last.request.read())
    assert cuerpo["advanced_params"] == {
        "pitch": -3,
        "volume": 80,
        "emotion": "happy",
    }
    # El pitch va dentro de advanced_params y en semitonos, no suelto ni escalado.
    assert "pitch" not in cuerpo
    assert cuerpo["speed"] == 1.0
