"""Koordynator: trzyma okno ostatnich wpisów zsynchronizowane strumieniem RTDB."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_THRESHOLD_HOURS,
    DEFAULT_THRESHOLD_HOURS,
    DOMAIN,
    FEEDINGS_LIMIT,
    UNAVAILABLE_AFTER,
)
from .firebase import FirebaseAccessDenied, FirebaseAuthError, FirebaseClient, FirebaseError
from .model import Snapshot

_LOGGER = logging.getLogger(__name__)

BACKOFF_MIN = 5
BACKOFF_MAX = 300


def _set_path(root: dict[str, Any], parts: list[str], value: Any) -> None:
    """Ustawia/usuwa węzeł pod ścieżką jak RTDB (None = usunięcie)."""
    node = root
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            if value is None:
                return
            child = {}
            node[part] = child
        node = child
    if value is None:
        node.pop(parts[-1], None)
    else:
        node[parts[-1]] = value


class KarmienieCoordinator(DataUpdateCoordinator[Snapshot]):
    """Push-only: brak update_interval, dane przychodzą ze strumienia SSE."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: FirebaseClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN)
        self.client = client
        self._feedings: dict[str, Any] = {}
        self.loaded = False
        self.connected = False
        self._disconnected_since: datetime | None = dt_util.utcnow()
        self.last_error: str | None = None

    @property
    def threshold(self) -> timedelta:
        hours = self.config_entry.options.get(CONF_THRESHOLD_HOURS, DEFAULT_THRESHOLD_HOURS)
        return timedelta(hours=float(hours))

    @property
    def data_available(self) -> bool:
        """Dane uznajemy za aktualne mimo krótkiej przerwy w strumieniu."""
        if not self.loaded:
            return False
        if self.connected or self._disconnected_since is None:
            return True
        return dt_util.utcnow() - self._disconnected_since < UNAVAILABLE_AFTER

    async def _async_update_data(self) -> Snapshot:
        return Snapshot.from_raw(self._feedings)

    def start(self) -> None:
        self.config_entry.async_create_background_task(
            self.hass, self._run(), f"{DOMAIN}_stream"
        )
        # Co minutę: przeliczenie „od ostatniego karmienia”, progu i liczników „dziś”.
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._tick, timedelta(minutes=1), name=f"{DOMAIN}_tick"
            )
        )

    @callback
    def _tick(self, _now: datetime) -> None:
        self.async_update_listeners()

    async def _run(self) -> None:
        backoff = BACKOFF_MIN
        while True:
            try:
                await self.client.stream_feedings(
                    FEEDINGS_LIMIT, self._on_event, self._on_connected
                )
                backoff = BACKOFF_MIN  # planowe zamknięcie (odnowienie tokenu)
                continue
            except FirebaseAuthError as err:
                self.last_error = f"Logowanie odrzucone: {err}"
                _LOGGER.error("Karmienie: %s", self.last_error)
                self.config_entry.async_start_reauth(self.hass)
                backoff = BACKOFF_MAX
            except FirebaseAccessDenied as err:
                self.last_error = (
                    "Brak dostępu do /feedings — sprawdź users/{uid}/allowed i appVersion"
                )
                _LOGGER.error("Karmienie: %s (%s)", self.last_error, err)
                backoff = BACKOFF_MAX
            except FirebaseError as err:
                self.last_error = str(err)
                _LOGGER.debug("Karmienie: strumień przerwany: %s", err)
            self._on_disconnected()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)

    @callback
    def _on_connected(self) -> None:
        self.connected = True
        self._disconnected_since = None
        self.last_error = None

    @callback
    def _on_disconnected(self) -> None:
        if self.connected:
            self._disconnected_since = dt_util.utcnow()
        self.connected = False
        self.async_update_listeners()

    @callback
    def _on_event(self, event: str, payload: dict[str, Any]) -> None:
        path = [p for p in str(payload.get("path", "/")).split("/") if p]
        data = payload.get("data")
        if event == "put":
            if not path:
                self._feedings = data if isinstance(data, dict) else {}
            else:
                _set_path(self._feedings, path, data)
        elif event == "patch" and isinstance(data, dict):
            for key, value in data.items():
                sub = [p for p in key.split("/") if p]
                if not path and not sub:
                    continue
                _set_path(self._feedings, path + sub, value)
        self.loaded = True
        self.async_set_updated_data(Snapshot.from_raw(self._feedings))
