"""Los modelos aguantan el JSON real de la API, entero.

Dos fallos vivían aquí y hacían el paquete inservible contra el backend de
verdad:

1. `Voice.from_dict` hacía `cls(**{**d, ...})` y `Audio(**d)` desempaquetaba el
   diccionario completo, así que *cualquier* clave que el backend emitiera y la
   dataclass no declarase reventaba con `TypeError`. El backend manda seis
   campos que la dataclass no tenía (`cloneAudioDuration`, `languageCode`,
   `gender`, `lastUsedAt`, `deletedAt`, `providers`) y encima ya no manda
   `langSet`, que era obligatorio: dos de los tres recursos principales del SDK
   no funcionaban.

2. Los fixtures eran más pobres que la API —solo los campos que la dataclass
   declaraba— y por eso ningún test lo detectó. Ahora los fixtures son copias
   fieles de lo que emite el backend (ver `conftest.py`).
"""

from __future__ import annotations

import dataclasses

import pytest

from vocea_sdk import Audio, Country, Voice, VoiceProvider, VoiceWarning
from vocea_sdk.models import _FromApi

from .conftest import SALDO_EXACTO


# Las claves exactas que emite `VoicesService.toPublic()` para una voz de un
# listado. Si el backend añade una, este test no falla (el SDK la descarta);
# el que falla es el de abajo, que exige que estén declaradas.
CLAVES_VOZ_DEL_BACKEND = {
    "id",
    "name",
    "status",
    "failureReason",
    "cloneAudioDuration",
    "languageCode",
    "countryId",
    "country",
    "regionId",
    "region",
    "ageRange",
    "gender",
    "isPublicRequest",
    "isPublic",
    "publicRejectReason",
    "timesUsed",
    "balanceEarnedTotal",
    "lastUsedAt",
    "createdAt",
    "updatedAt",
    "deletedAt",
    "providers",
    "hasSamplePreview",
    "isFavorited",
    "favoritesCount",
}

CLAVES_AUDIO_DEL_BACKEND = {
    "id",
    "voiceId",
    "providerVoiceId",
    "ttsModelId",
    "textContent",
    "durationSeconds",
    "characterCount",
    "languageCode",
    "generationTimeMs",
    "speakingRate",
    "temperature",
    "emotion",
    "createdAt",
    "audioUrl",
}


def _campos(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


# ─── Nada de lo que manda el backend se pierde ─────────────────────────────


def test_voice_declara_todo_lo_que_emite_el_backend(voz_json):
    """Descartar claves desconocidas no es excusa para no declararlas.

    Filtrar protege de los campos que el backend añada mañana; los que emite
    hoy tienen que estar en el tipo o el SDK estaría escondiendo datos útiles
    (`providers`, `gender`, `cloneAudioDuration`…).
    """
    assert CLAVES_VOZ_DEL_BACKEND <= _campos(Voice)
    # Y el fixture es de verdad el JSON del backend, no un subconjunto cómodo.
    assert set(voz_json) == CLAVES_VOZ_DEL_BACKEND


def test_audio_declara_todo_lo_que_emite_el_backend(audio_json):
    assert CLAVES_AUDIO_DEL_BACKEND <= _campos(Audio)
    assert set(audio_json) == CLAVES_AUDIO_DEL_BACKEND


def test_voice_from_dict_deserializa_la_respuesta_real_entera(voz_json):
    voz = Voice.from_dict(voz_json)

    assert voz.id == "voz-1"
    assert voz.cloneAudioDuration == 41.28
    assert voz.languageCode == "es"
    assert voz.gender == "female"
    assert voz.lastUsedAt == "2026-09-03T10:15:00.000Z"
    assert voz.deletedAt is None
    assert voz.balanceEarnedTotal == SALDO_EXACTO
    assert voz.isFavorited is False
    assert voz.favoritesCount == 3


def test_voice_from_dict_convierte_los_providers_en_objetos(voz_json):
    """`providers` llega en snake_case: se respeta tal cual, no se traduce."""
    voz = Voice.from_dict(voz_json)

    assert [type(p) for p in voz.providers] == [VoiceProvider, VoiceProvider]
    inworld, eleven = voz.providers
    assert inworld.provider_id == "prov-a"
    assert inworld.name == "inworld"
    assert inworld.is_cloned is True
    assert inworld.last_used_at is None
    assert eleven.is_cloned is False
    assert eleven.last_used_at == "2026-09-03T10:15:00.000Z"


def test_voice_from_dict_anida_country_y_region(voz_json):
    voz = Voice.from_dict(voz_json)

    assert isinstance(voz.country, Country)
    assert voz.country.code == "ES"
    # `region` viaja a null cuando la voz no tiene región asignada.
    assert voz.region is None


def test_audio_from_dict_deserializa_la_respuesta_real_entera(audio_json):
    audio = Audio.from_dict(audio_json)

    assert audio.id == "aud-1"
    assert audio.voiceId == "voz-1"
    assert audio.providerVoiceId is None
    assert audio.generationTimeMs == 1830
    assert audio.durationSeconds == 3.5
    assert audio.audioUrl.endswith("/audios/aud-1/play.mp3")


def test_audio_de_una_voz_del_catalogo_no_trae_voice_id(audio_json):
    """`voiceId` y `providerVoiceId` son excluyentes y ambos son anulables."""
    audio = Audio.from_dict({**audio_json, "voiceId": None, "providerVoiceId": "pv-9"})

    assert audio.voiceId is None
    assert audio.providerVoiceId == "pv-9"


# ─── Lo que el backend deja de mandar, o manda de más ──────────────────────


def test_voice_from_dict_no_exige_lang_set(voz_json):
    """La entidad perdió la columna `lang_set` y el backend dejó de enviarla.

    Era un campo obligatorio de la dataclass: sin él, `from_dict` fallaba con
    un argumento que faltaba incluso antes de llegar a los campos de más.
    """
    assert "langSet" not in voz_json

    assert Voice.from_dict(voz_json).langSet is None


def test_voice_from_dict_sobrevive_a_un_campo_nuevo_del_backend(voz_json):
    """El contrato con el backend es de solo-añadir: el SDK no puede caerse.

    Es la razón de filtrar en vez de limitarse a declarar los campos de hoy:
    un despliegue del backend con un campo nuevo no puede tumbar a quien tenga
    instalada una versión anterior del SDK.
    """
    voz = Voice.from_dict({**voz_json, "campoQueAunNoExiste": "sorpresa"})

    assert voz.id == "voz-1"
    assert not hasattr(voz, "campoQueAunNoExiste")


def test_audio_from_dict_sobrevive_a_un_campo_nuevo_del_backend(audio_json):
    audio = Audio.from_dict({**audio_json, "campoQueAunNoExiste": 42})

    assert audio.id == "aud-1"


def test_los_extras_del_listado_faltan_en_los_endpoints_de_una_sola_voz(voz_json):
    """`toPublic()` solo añade favoritos en los listados.

    En `GET /voices/{id}`, al clonar o al renombrar no viajan, y tampoco
    `country`/`region` si la consulta no cargó las relaciones. `None` dice
    «el endpoint no lo informa», que no es lo mismo que «no es favorita» ni
    que «cero favoritos».
    """
    sin_extras = {
        k: v
        for k, v in voz_json.items()
        if k not in {"isFavorited", "favoritesCount", "country", "region"}
    }

    voz = Voice.from_dict(sin_extras)

    assert voz.isFavorited is None
    assert voz.favoritesCount is None
    assert voz.country is None
    assert voz.region is None
    assert voz.providers != []


def test_from_dict_no_inventa_campos_obligatorios(voz_json):
    """Filtrar no es tragar con todo: si falta algo obligatorio, revienta.

    Descartar claves desconocidas evita que la API rompa al cliente; rellenar
    con `None` los campos que la API tiene que mandar solo trasladaría el
    fallo a la primera vez que alguien lee `voz.id`.
    """
    sin_id = {k: v for k, v in voz_json.items() if k != "id"}

    with pytest.raises(TypeError, match="id"):
        Voice.from_dict(sin_id)


def test_todos_los_modelos_comparten_el_mismo_from_dict():
    """Centinela: un modelo nuevo que no herede de `_FromApi` repite el bug.

    `PaginatedResponse` queda fuera a propósito: no se construye desde una
    respuesta cruda, sino a mano en cada recurso con los ítems ya deserializados.
    """
    from vocea_sdk import models

    modelos = [
        v
        for v in vars(models).values()
        if dataclasses.is_dataclass(v) and v is not models.PaginatedResponse
    ]
    assert modelos, "no se encontró ningún modelo: ¿cambió el módulo de sitio?"
    assert [m for m in modelos if not issubclass(m, _FromApi)] == []


def test_voice_from_dict_deserializa_los_avisos_de_la_clonacion(voz_json):
    """`POST /voices/clone` añade `warnings` a la voz: son útiles para la UI."""
    voz = Voice.from_dict(
        {
            **voz_json,
            "warnings": [{"provider": "inworld", "text": "Audio con ruido"}],
            # El mismo endpoint devuelve la muestra en base64. Es un blob que el
            # SDK no modela: se descarta, y `voices.sample()` la sirve aparte.
            "sampleAudioBase64": "SUQzB...",
        }
    )

    assert voz.warnings == [VoiceWarning(provider="inworld", text="Audio con ruido")]
