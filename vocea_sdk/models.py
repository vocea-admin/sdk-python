from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, Optional, TypeVar


T = TypeVar("T")
M = TypeVar("M", bound="_FromApi")


VoiceStatus = Literal["pending", "active", "failed"]
VoiceAgeRange = Literal["young", "adult", "senior"]
VoiceGender = Literal["male", "female", "neutral"]
Emotion = Literal["neutral", "happy", "sad", "angry", "fearful", "surprised", "disgusted", "whisper"]
# Los cinco tipos que emite el backend (TransactionType en
# balance-transaction.entity.ts). Son datos que viajan por el cable y viven
# en la base de datos: no se renombran.
TransactionType = Literal[
    "purchase",
    "consumption",
    "adjustment",
    "earned_public_voice",
    "welcome_bonus",
]


class _FromApi:
    """Construye modelos a partir del JSON de la API.

    Descarta las claves que el modelo no declara en vez de reventar con un
    `TypeError`. La API crece: cada campo nuevo del backend llegaría como un
    argumento inesperado a la dataclass y tumbaría al cliente entero por leer
    algo que ni siquiera usa. Los SDK de Node y de Go ya son tolerantes por
    construcción (`JSON.parse` deja pasar las claves de más y `encoding/json`
    las ignora salvo que se pida `DisallowUnknownFields`); este es el
    equivalente en Python.

    Tolerar no es ignorar: los campos que el backend emite hoy están todos
    declarados. Descartar en silencio solo cubre lo que aún no existe.
    """

    @classmethod
    def from_dict(cls: type[M], d: dict[str, Any]) -> M:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})  # type: ignore[attr-defined]


@dataclass
class Country(_FromApi):
    id: str
    name: str
    code: str


@dataclass
class Region(_FromApi):
    id: str
    name: str


@dataclass
class VoiceProvider(_FromApi):
    """Estado de la voz en un proveedor TTS.

    La API devuelve estas claves en snake_case, a diferencia del resto de la
    respuesta: se respetan tal cual para no mentir sobre el JSON que llega.
    """

    provider_id: str
    #: `inworld` (Standard), `minimax` (Premium), `elevenlabs` (Studio).
    name: str
    is_enabled: bool
    #: La voz está clonada en este proveedor y se puede usar.
    is_cloned: bool
    last_used_at: Optional[str]
    has_sample_preview: bool


@dataclass
class VoiceWarning(_FromApi):
    """Aviso del motor de clonación (calidad de la muestra, recorte…).

    Solo viaja en la respuesta de `voices.clone()`.
    """

    provider: str
    text: str


@dataclass
class Voice(_FromApi):
    """Una voz clonada, tal y como la devuelve la API.

    Los campos sin valor por defecto son los que el backend emite siempre. Los
    demás dependen del endpoint: `country` y `region` solo llegan cuando la
    consulta carga esas relaciones, `isFavorited` y `favoritesCount` solo en
    los listados, y `warnings` solo al clonar.
    """

    id: str
    name: str
    status: VoiceStatus
    failureReason: Optional[str]
    #: Duración en segundos del audio usado para clonar.
    cloneAudioDuration: Optional[float]
    #: Idioma de la muestra con la que se clonó (ej. 'es').
    languageCode: Optional[str]
    countryId: Optional[str]
    regionId: Optional[str]
    ageRange: Optional[VoiceAgeRange]
    gender: Optional[VoiceGender]
    isPublicRequest: bool
    isPublic: bool
    publicRejectReason: Optional[str]
    timesUsed: int
    #: Saldo total en USD que ha generado la voz cuando otros la usan.
    balanceEarnedTotal: float
    hasSamplePreview: bool
    #: Última vez que se usó la voz para generar audio. None si nunca.
    lastUsedAt: Optional[str]
    createdAt: str
    updatedAt: str
    #: Fecha de borrado lógico. None mientras la voz está viva.
    deletedAt: Optional[str]
    country: Optional[Country] = None
    region: Optional[Region] = None
    #: Estado de la voz en cada proveedor TTS.
    providers: list[VoiceProvider] = field(default_factory=list)
    #: Avisos de la clonación. Solo en la respuesta de `voices.clone()`.
    warnings: list[VoiceWarning] = field(default_factory=list)
    #: None cuando el endpoint no lo informa (no es lo mismo que "no favorita").
    isFavorited: Optional[bool] = None
    #: None cuando el endpoint no lo informa (no es lo mismo que "cero").
    favoritesCount: Optional[int] = None
    #: La API dejó de enviarlo (la entidad ya no tiene la columna). Se mantiene
    #: por si algún endpoint sin auditar todavía lo incluye.
    langSet: Optional[Literal["full", "lite"]] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Voice":
        return super().from_dict(
            {
                **d,
                "country": Country.from_dict(d["country"]) if d.get("country") else None,
                "region": Region.from_dict(d["region"]) if d.get("region") else None,
                "providers": [VoiceProvider.from_dict(p) for p in d.get("providers") or []],
                "warnings": [VoiceWarning.from_dict(w) for w in d.get("warnings") or []],
            }
        )


@dataclass
class TtsModel(_FromApi):
    """Modelo TTS tal y como lo devuelve `GET /tts-models/:id`.

    El detalle se sirve con una selección reducida, así que NO trae
    `providerId` ni `maxCharacters`. El listado sí: ver `TtsModelListItem`.
    """
    id: str
    name: str
    description: Optional[str]
    isActive: bool
    sortOrder: int
    createdAt: str


@dataclass
class TtsModelListItem(TtsModel):
    """Modelo TTS del listado `GET /tts-models`, con dos campos que el detalle
    no envía.

    `providerId` importa más de lo que parece: es el identificador que
    `voices.clone()` exige, y este listado es el único sitio del que el SDK
    puede sacarlo.
    """
    providerId: str = ""
    maxCharacters: int = 0


@dataclass
class TtsLanguage(_FromApi):
    code: str
    name: str


@dataclass
class TtsConfig(_FromApi):
    """Indica qué conjuntos de idiomas están habilitados en esta instancia."""
    full: bool
    lite: bool


@dataclass
class Audio(_FromApi):
    """Un audio generado.

    `voiceId` y `providerVoiceId` son excluyentes: el audio se generó con una
    voz clonada del usuario o con una del catálogo del proveedor.
    """

    id: str
    voiceId: Optional[str]
    #: Voz del catálogo del proveedor. None si se usó una voz clonada.
    providerVoiceId: Optional[str]
    ttsModelId: str
    textContent: str
    characterCount: int
    languageCode: str
    durationSeconds: Optional[float]
    #: Tiempo que tardó el proveedor en sintetizar, en milisegundos.
    generationTimeMs: Optional[int]
    speakingRate: Optional[float]
    temperature: Optional[float]
    emotion: Optional[Emotion]
    audioUrl: str
    createdAt: str


@dataclass
class TranscribeResult(_FromApi):
    transcript: str
    characterCount: int
    balanceConsumed: float
    durationMs: Optional[int]


@dataclass
class UsdBalance(_FromApi):
    """Saldo del usuario, en dólares."""
    balance: float


@dataclass
class BalancePackage(_FromApi):
    """Paquete de recarga. `priceUsd` es también el saldo que suma la compra."""
    id: str
    name: str
    priceUsd: float
    isActive: bool
    lemonsqueezyVariantId: Optional[str] = None
    createdAt: Optional[str] = None


@dataclass
class CheckoutResponse(_FromApi):
    """URL de pago a la que redirigir al usuario."""
    checkoutUrl: str


@dataclass
class BalanceTransaction(_FromApi):
    """Un movimiento del historial de saldo.

    `amount` va en dólares: positivo cuando suma saldo, negativo cuando lo
    descuenta. La API adjunta además campos internos al movimiento
    (balanceAfter, userId, el pedido de Lemon Squeezy…) que `from_dict`
    descarta.
    """
    id: str
    type: TransactionType
    amount: float
    description: str
    createdAt: str


@dataclass
class MonthlyEarning(_FromApi):
    month: str
    balanceEarned: float


@dataclass
class VoiceEarnings(_FromApi):
    earnings: list[MonthlyEarning]
    balanceEarnedTotal: float
    timesUsed: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VoiceEarnings":
        return super().from_dict(
            {**d, "earnings": [MonthlyEarning.from_dict(m) for m in d.get("earnings") or []]}
        )


@dataclass
class PaginatedResponse(Generic[T]):
    # Genérico con TypeVar y no con la sintaxis `class PaginatedResponse[T]`
    # (PEP 695): esa forma exige Python 3.12 y el paquete se publica para
    # 3.10+, donde ni siquiera se importaría.
    items: list[T]
    total: int
    page: int
    limit: int


# ─── Auth y perfil ──────────────────────────────────────────────────────────


@dataclass
class User(_FromApi):
    """Perfil que devuelven `GET /users/me`, `PATCH /users/me` y el campo
    `user` de un inicio de sesión: la entidad del backend sin sus secretos.

    Los nombres llegan en camelCase aunque la petición de actualización los
    mande en snake_case. Es la asimetría del contrato, no una errata.
    """
    id: str
    email: str
    fullName: str
    preferredLanguage: str
    role: str
    isVerified: bool
    balance: float
    createdAt: str
    updatedAt: str


@dataclass
class LoginResponse(_FromApi):
    """Token de acceso y el mismo perfil saneado que devuelve `/users/me`."""
    access_token: str
    user: User

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LoginResponse":
        # `user` llega anidado y hay que construirlo aparte: `_FromApi` copia
        # los valores tal cual y dejaría un diccionario donde se espera un User.
        datos = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        datos["user"] = User.from_dict(datos.get("user") or {})
        return cls(**datos)


@dataclass
class ApiKeyStatus(_FromApi):
    """Si la cuenta tiene ya una clave emitida. No dice cuál: el backend
    guarda solo su hash."""
    hasApiKey: bool


@dataclass
class ApiKeyCreated(_FromApi):
    """Clave recién emitida. Es la única vez que se puede leer."""
    apiKey: str


# ─── Transcripciones ────────────────────────────────────────────────────────


@dataclass
class Transcription(_FromApi):
    """Una transcripción guardada, tal como la lista `GET /stt/transcriptions`."""
    id: str
    transcript: str
    characterCount: int
    durationMs: Optional[int]
    createdAt: str


# ─── Referidos ──────────────────────────────────────────────────────────────


@dataclass
class Referral(_FromApi):
    """Una persona que el usuario trajo, con lo que ha generado.

    `latestStatus` es None mientras el referido no haya comprado nada.
    """
    refereeId: str
    refereeEmail: str
    refereeName: str
    totalUsd: float
    latestStatus: Optional[str]
    latestDate: Optional[str]
    hasPurchased: bool


@dataclass
class ReferralStats(_FromApi):
    """Respuesta de `GET /balance/referrals`."""
    items: list[Referral]
    totalEarned: float
    referralPercentage: float

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReferralStats":
        # Sin valores por defecto a propósito. Un `.get(..., 0.0)` convertiría
        # un renombrado del backend en «0 USD ganados» en pantalla, sin ningún
        # error: el usuario creería que no ha ganado nada. Es dinero; que
        # reviente y se vea.
        return cls(
            items=[Referral.from_dict(x) for x in (d.get("items") or [])],
            totalEarned=d["totalEarned"],
            referralPercentage=d["referralPercentage"],
        )


@dataclass
class ReferralCommission(_FromApi):
    """Un movimiento de comisión de un referido concreto."""
    id: str
    date: str
    commissionUsd: float
    status: str
    orderId: Optional[str]


@dataclass
class ReferralHistory(_FromApi):
    """Respuesta de `GET /balance/referrals/:refereeId`."""
    refereeId: str
    refereeEmail: str
    refereeName: str
    transactions: list[ReferralCommission]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReferralHistory":
        return cls(
            refereeId=d["refereeId"],
            refereeEmail=d["refereeEmail"],
            refereeName=d["refereeName"],
            transactions=[
                ReferralCommission.from_dict(x) for x in (d.get("transactions") or [])
            ],
        )
