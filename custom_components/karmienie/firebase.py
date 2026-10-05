"""Minimalny klient Firebase: logowanie e-mail/hasło + strumień REST (SSE) z RTDB."""

from __future__ import annotations

import asyncio
import codecs
from collections.abc import Awaitable, Callable
import json
import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

SIGN_IN_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
REFRESH_URL = "https://securetoken.googleapis.com/v1/token"

# Firebase wysyła keep-alive co ~30 s; dłuższa cisza = martwe połączenie.
STREAM_READ_TIMEOUT = 90
# Zamykamy strumień chwilę przed wygaśnięciem tokenu i otwieramy z nowym,
# zamiast czekać na zdarzenie auth_revoked.
TOKEN_MARGIN = 120


class FirebaseError(Exception):
    """Błąd komunikacji z Firebase."""


class FirebaseAuthError(FirebaseError):
    """Złe dane logowania albo konto zablokowane."""


class FirebaseAccessDenied(FirebaseError):
    """Reguły RTDB odmówiły dostępu (brak allowed/appVersion w users/{uid})."""


class FirebaseClient:
    """Loguje się kontem e-mail/hasło i odświeża token ID."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        database_url: str,
        email: str,
        password: str,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._db = database_url.rstrip("/")
        self._email = email
        self._password = password
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at = 0.0
        self.uid: str | None = None

    async def _post(self, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with self._session.post(
                url,
                params={"key": self._api_key},
                timeout=aiohttp.ClientTimeout(total=20),
                **kwargs,
            ) as resp:
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise FirebaseError(f"Błąd połączenia z Firebase Auth: {err}") from err
        if resp.status != 200:
            message = (body or {}).get("error", {}).get("message", str(resp.status))
            if resp.status in (400, 401, 403):
                raise FirebaseAuthError(message)
            raise FirebaseError(message)
        return body

    async def sign_in(self) -> None:
        body = await self._post(
            SIGN_IN_URL,
            json={
                "email": self._email,
                "password": self._password,
                "returnSecureToken": True,
            },
        )
        self._id_token = body["idToken"]
        self._refresh_token = body["refreshToken"]
        self._expires_at = time.monotonic() + int(body.get("expiresIn", 3600))
        self.uid = body.get("localId")

    async def _refresh(self) -> None:
        body = await self._post(
            REFRESH_URL,
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
        )
        self._id_token = body["id_token"]
        self._refresh_token = body["refresh_token"]
        self._expires_at = time.monotonic() + int(body.get("expires_in", 3600))

    async def get_token(self) -> str:
        """Ważny token ID (odświeżany z zapasem, w razie problemu pełne logowanie)."""
        if self._id_token and time.monotonic() < self._expires_at - TOKEN_MARGIN * 2:
            return self._id_token
        if self._refresh_token:
            try:
                await self._refresh()
                return self._id_token  # type: ignore[return-value]
            except FirebaseAuthError:
                _LOGGER.debug("Refresh token odrzucony, loguję ponownie")
        await self.sign_in()
        return self._id_token  # type: ignore[return-value]

    def seconds_until_expiry(self) -> float:
        return self._expires_at - time.monotonic()

    def _feedings_url(self) -> str:
        return f"{self._db}/feedings.json"

    @staticmethod
    def _query(limit: int) -> dict[str, str]:
        return {"orderBy": '"$key"', "limitToLast": str(limit)}

    async def fetch_feedings(self, limit: int) -> dict[str, Any]:
        """Jednorazowy odczyt — używany do walidacji w config flow."""
        token = await self.get_token()
        try:
            async with self._session.get(
                self._feedings_url(),
                params={**self._query(limit), "auth": token},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise FirebaseAccessDenied(await resp.text())
                if resp.status != 200:
                    raise FirebaseError(f"RTDB HTTP {resp.status}")
                return await resp.json(content_type=None) or {}
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise FirebaseError(f"Błąd połączenia z RTDB: {err}") from err

    async def stream_feedings(
        self,
        limit: int,
        on_event: Callable[[str, dict[str, Any]], None],
        on_connected: Callable[[], Awaitable[None] | None],
    ) -> None:
        """Jedno połączenie SSE; kończy się przed wygaśnięciem tokenu albo przy błędzie.

        Wywołujący odpowiada za pętlę ponownych połączeń.
        """
        token = await self.get_token()
        lifetime = max(self.seconds_until_expiry() - TOKEN_MARGIN, 60)
        deadline = asyncio.timeout(lifetime)
        try:
            async with deadline:
                async with self._session.get(
                    self._feedings_url(),
                    params={**self._query(limit), "auth": token},
                    headers={"Accept": "text/event-stream"},
                    timeout=aiohttp.ClientTimeout(
                        total=None, sock_connect=20, sock_read=STREAM_READ_TIMEOUT
                    ),
                ) as resp:
                    if resp.status in (401, 403):
                        raise FirebaseAccessDenied(await resp.text())
                    if resp.status != 200:
                        raise FirebaseError(f"RTDB stream HTTP {resp.status}")
                    result = on_connected()
                    if asyncio.iscoroutine(result):
                        await result
                    await self._read_sse(resp, on_event)
        except TimeoutError as err:
            if not deadline.expired():
                # sock_read: brak keep-alive — martwe połączenie.
                raise FirebaseError("Brak danych ze strumienia RTDB") from err
            _LOGGER.debug("Zamykam strumień RTDB przed wygaśnięciem tokenu")
        except aiohttp.ClientError as err:
            raise FirebaseError(f"Strumień RTDB przerwany: {err}") from err

    async def _read_sse(
        self,
        resp: aiohttp.ClientResponse,
        on_event: Callable[[str, dict[str, Any]], None],
    ) -> None:
        # Czytamy kawałkami zamiast readline(): pierwsze zdarzenie „put” z całym
        # oknem 200 wpisów potrafi przekroczyć limit długości linii aiohttp (64 KB).
        # Dekoder przyrostowy: granica kawałka może przeciąć wielobajtowy znak (ą, ł…).
        decoder = codecs.getincrementaldecoder("utf-8")()
        buffer = ""
        event: str | None = None
        data_lines: list[str] = []
        async for chunk in resp.content.iter_any():
            buffer += decoder.decode(chunk)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.rstrip("\r")
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())
                elif line == "" and event is not None:
                    self._dispatch(event, "\n".join(data_lines), on_event)
                    event, data_lines = None, []
        raise FirebaseError("Serwer zamknął strumień RTDB")

    @staticmethod
    def _dispatch(
        event: str,
        raw: str,
        on_event: Callable[[str, dict[str, Any]], None],
    ) -> None:
        if event == "keep-alive":
            return
        if event == "cancel":
            raise FirebaseAccessDenied(raw or "cancel")
        if event == "auth_revoked":
            raise FirebaseError("Token wygasł (auth_revoked)")
        if event in ("put", "patch"):
            try:
                payload = json.loads(raw)
            except ValueError as err:
                # Bez treści — to dane o karmieniu; wystarczy długość i typ błędu.
                _LOGGER.warning(
                    "Nieczytelne zdarzenie RTDB %s (%d znaków, %s)",
                    event,
                    len(raw),
                    type(err).__name__,
                )
                return
            on_event(event, payload)
