from __future__ import annotations
from ._http import HttpClient
from .resources.audios import AudiosResource
from .resources.auth import AuthResource
from .resources.balance import BalanceResource
from .resources.models import ModelsResource
from .resources.stt import SttResource
from .resources.users import UsersResource
from .resources.voices import VoicesResource


DEFAULT_BASE_URL = "https://vocea.app/api/v1"


class VoceaClient:
    """Cliente síncrono de la API de Vocea.

    Todo salvo `auth` necesita una clave de API. Si aún no tienes una, el SDK
    puede emitirla: inicia sesión con `auth.login` y crea la clave con
    `users.create_api_key`. Para usar solo `auth`, construye el cliente con una
    clave vacía.
    """

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL) -> None:
        http = HttpClient(api_key, base_url)
        self.auth = AuthResource(http)
        self.voices = VoicesResource(http)
        self.audios = AudiosResource(http)
        self.stt = SttResource(http)
        self.models = ModelsResource(http)
        self.users = UsersResource(http)
        self.balance = BalanceResource(http)
