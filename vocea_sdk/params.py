"""Constructores de `advanced_params`, uno por calidad de voz.

Cada calidad admite sus propios parámetros y enviar uno que pertenece a otra
falla la llamada con `INVALID_ADVANCED_PARAMS`. Estas funciones ponen las
claves correctas para que no haya que recordarlas.

Casi todo es una escala de 0 a 100 que la API reconvierte al rango nativo de
cada proveedor. La excepción es `pitch`: son semitonos de verdad, así que va de
-12 a 12 y tiene que ser entero. Ese dato estuvo mal documentado durante mucho
tiempo —se anunciaba de -100 a 100— y quien enviaba 50 creyendo que era un
porcentaje mandaba un valor fuera de rango.
"""

from __future__ import annotations
from typing import Any

# Las emociones que acepta la API. Cualquier otra se rechaza.
EMOCIONES = (
    "neutral",
    "happy",
    "sad",
    "angry",
    "fearful",
    "surprised",
    "disgusted",
    "whisper",
)


def _en_rango(nombre: str, valor: int, minimo: int, maximo: int) -> int:
    if not isinstance(valor, int) or isinstance(valor, bool):
        raise ValueError(f"{nombre} tiene que ser un entero, no {type(valor).__name__}")
    if valor < minimo or valor > maximo:
        raise ValueError(f"{nombre} tiene que estar entre {minimo} y {maximo}: {valor}")
    return valor


def standard_params(expressiveness: int = 50) -> dict[str, Any]:
    """Parámetros de la calidad `standard` (Inworld).

    `expressiveness` va de 0 a 100 y por defecto es 50. Valores bajos leen de
    forma estable y repetible; altos, más expresiva pero menos predecible.
    """
    return {"expressiveness": _en_rango("expressiveness", expressiveness, 0, 100)}


def premium_params(
    pitch: int = 0, volume: int = 50, emotion: str = "neutral"
) -> dict[str, Any]:
    """Parámetros de la calidad `premium` (Minimax).

    `pitch` es el único que no es una escala 0–100: son semitonos enteros de
    -12 a 12, y 0 deja la voz como está. `volume` va de 0 a 100.
    """
    if emotion not in EMOCIONES:
        raise ValueError(f"emotion tiene que ser una de {EMOCIONES}: {emotion!r}")
    return {
        "pitch": _en_rango("pitch", pitch, -12, 12),
        "volume": _en_rango("volume", volume, 0, 100),
        "emotion": emotion,
    }


def studio_params(
    stability: int = 50, clarity: int = 75, style: int = 0
) -> dict[str, Any]:
    """Parámetros de la calidad `studio` (ElevenLabs).

    Los tres van de 0 a 100. `stability` alto suena uniforme entre tomas y bajo
    varía más; `clarity` es cuánto se ciñe el resultado a la voz clonada; subir
    `style` aumenta la latencia de generación.
    """
    return {
        "stability": _en_rango("stability", stability, 0, 100),
        "clarity": _en_rango("clarity", clarity, 0, 100),
        "style": _en_rango("style", style, 0, 100),
    }
