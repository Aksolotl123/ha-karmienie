"""Config flow: logowanie osobnym kontem Firebase dla Home Assistant."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
    CONF_DATABASE_URL,
    CONF_THRESHOLD_HOURS,
    DEFAULT_THRESHOLD_HOURS,
    DOMAIN,
)
from .firebase import FirebaseAccessDenied, FirebaseAuthError, FirebaseClient, FirebaseError

_LOGGER = logging.getLogger(__name__)


class KarmienieConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, data: Mapping[str, Any]) -> tuple[str | None, dict[str, str]]:
        client = FirebaseClient(
            async_get_clientsession(self.hass),
            data[CONF_API_KEY],
            data[CONF_DATABASE_URL],
            data[CONF_EMAIL],
            data[CONF_PASSWORD],
        )
        try:
            await client.sign_in()
            await client.fetch_feedings(1)
        except FirebaseAuthError:
            return None, {"base": "invalid_auth"}
        except FirebaseAccessDenied:
            return None, {"base": "no_access"}
        except FirebaseError as err:
            _LOGGER.debug("Walidacja nieudana: %s", err)
            return None, {"base": "cannot_connect"}
        return client.uid, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            uid, errors = await self._validate(user_input)
            if not errors:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Karmienie", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                ),
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                # Bez wartości domyślnych — klucz i adres bazy wpisuje użytkownik.
                vol.Required(CONF_DATABASE_URL): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                ),
                vol.Required(CONF_API_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            _uid, errors = await self._validate(data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return KarmienieOptionsFlow()


class KarmienieOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_THRESHOLD_HOURS, DEFAULT_THRESHOLD_HOURS)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_THRESHOLD_HOURS, default=current): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.5,
                            max=12,
                            step=0.25,
                            unit_of_measurement="h",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
