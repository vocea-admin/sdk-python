from __future__ import annotations
from typing import Any
import httpx
from .exceptions import VoceaError


class HttpClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    @property
    def base_url(self) -> str:
        """URL base ya normalizada, sin barra final.

        La expone `audios.play_url`, que compone una URL en vez de pedirla.
        """
        return self._base

    def _raise(self, r: httpx.Response) -> None:
        try:
            body = r.json()
        except Exception:
            body = {"statusCode": r.status_code, "message": r.text}
        raise VoceaError(r.status_code, body)

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        data: dict | None = None,
        files: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        url = f"{self._base}{path}"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None} or None
        r = httpx.request(
            method,
            url,
            headers=self._headers,
            json=json,
            data=data,
            files=files,
            params=clean_params,
        )
        if not r.is_success:
            self._raise(r)
        if r.status_code == 204 or not r.content:
            return None
        return r.json()

    def stream(self, method: str, path: str) -> httpx.Response:
        url = f"{self._base}{path}"
        r = httpx.request(method, url, headers=self._headers)
        if not r.is_success:
            self._raise(r)
        return r


class AsyncHttpClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def _raise(self, r: httpx.Response) -> None:
        try:
            body = r.json()
        except Exception:
            body = {"statusCode": r.status_code, "message": r.text}
        raise VoceaError(r.status_code, body)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        data: dict | None = None,
        files: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        url = f"{self._base}{path}"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None} or None
        async with httpx.AsyncClient() as client:
            r = await client.request(
                method,
                url,
                headers=self._headers,
                json=json,
                data=data,
                files=files,
                params=clean_params,
            )
        if not r.is_success:
            self._raise(r)
        if r.status_code == 204 or not r.content:
            return None
        return r.json()
