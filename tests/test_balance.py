"""Los modelos de saldo se construyen con las claves que envía la API.

Los dataclasses se rellenan por desempaquetado (`Modelo(**json)`), así que el
nombre del campo *es* la clave del JSON: si una se renombra y la otra no, esto
revienta con un TypeError en vez de fallar en silencio.
"""

from __future__ import annotations

from typing import get_args

import vocea_sdk
from vocea_sdk import (
    BalancePackage,
    MonthlyEarning,
    TransactionType,
    UsdBalance,
    VoiceEarnings,
)

from .conftest import SALDO_EXACTO


def test_usd_balance_lee_la_clave_balance():
    saldo = UsdBalance(**{"balance": SALDO_EXACTO})

    assert saldo.balance == SALDO_EXACTO


def test_balance_package_recibe_el_precio_como_numero():
    paquete = BalancePackage(
        **{
            "id": "paq-1",
            "name": "Starter",
            "priceUsd": 9.99,
            "isActive": True,
            "lemonsqueezyVariantId": "123456",
        }
    )

    assert paquete.priceUsd == 9.99
    assert isinstance(paquete.priceUsd, float)


def test_voice_earnings_se_construye_desde_el_json_de_la_api():
    payload = {
        "earnings": [
            {"month": "2026-08", "balanceEarned": 1.25},
            {"month": "2026-09", "balanceEarned": 2.25},
        ],
        "balanceEarnedTotal": 3.50,
        "timesUsed": 12,
    }

    ganancias = VoiceEarnings(
        **{**payload, "earnings": [MonthlyEarning(**m) for m in payload["earnings"]]}
    )

    assert ganancias.balanceEarnedTotal == 3.50
    assert ganancias.earnings[0].balanceEarned == 1.25


def test_transaction_type_declara_los_cinco_tipos_del_backend():
    """Los cinco valores del enum TransactionType de la entidad del backend.

    La pista de tipo llegó a declarar solo tres, así que quien la leía no se
    enteraba de que un movimiento puede venir de una voz pública o del regalo
    de bienvenida. Los valores son datos que viajan por el cable: se copian
    tal cual del backend, no se traducen.
    """
    assert set(get_args(TransactionType)) == {
        "purchase",
        "consumption",
        "adjustment",
        "earned_public_voice",
        "welcome_bonus",
    }


def test_la_superficie_publica_es_la_esperada():
    """Centinela: exportar o dejar de exportar un símbolo es un cambio de API.

    La lista creció al nivelar el SDK con el de Node: `auth`, el perfil
    completo, las transcripciones, los referidos y los constructores de
    parámetros avanzados. Si algo desaparece de aquí, alguien rompió a un
    usuario que lo importaba.
    """
    assert sorted(vocea_sdk.__all__) == [
        "ApiKeyCreated",
        "ApiKeyStatus",
        "Audio",
        "BalancePackage",
        "BalanceTransaction",
        "CheckoutResponse",
        "Country",
        "LoginResponse",
        "MonthlyEarning",
        "PaginatedResponse",
        "Referral",
        "ReferralCommission",
        "ReferralHistory",
        "ReferralStats",
        "Region",
        "TransactionType",
        "TranscribeResult",
        "Transcription",
        "TtsConfig",
        "TtsLanguage",
        "TtsModel",
        "TtsModelListItem",
        "UsdBalance",
        "User",
        "VoceaClient",
        "VoceaError",
        "Voice",
        "VoiceEarnings",
        "VoiceProvider",
        "VoiceWarning",
        "premium_params",
        "standard_params",
        "studio_params",
    ]
