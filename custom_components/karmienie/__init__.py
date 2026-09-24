"""Karmienie Dziecka — dane z aplikacji (Firebase RTDB) w Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_KEY, CONF_DATABASE_URL
from .coordinator import KarmienieCoordinator
from .firebase import FirebaseAuthError, FirebaseClient, FirebaseError

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type KarmienieConfigEntry = ConfigEntry[KarmienieCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KarmienieConfigEntry) -> bool:
    client = FirebaseClient(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
        entry.data[CONF_DATABASE_URL],
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    try:
        await client.sign_in()
    except FirebaseAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except FirebaseError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = KarmienieCoordinator(hass, entry, client)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.start()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: KarmienieConfigEntry) -> None:
    # Zmiana progu tylko przelicza encje — bez restartu strumienia.
    entry.runtime_data.async_update_listeners()


async def async_unload_entry(hass: HomeAssistant, entry: KarmienieConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
