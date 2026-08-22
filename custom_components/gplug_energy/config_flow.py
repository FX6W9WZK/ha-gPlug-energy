"""Config flow for gPlug Energy integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AUTO_CARD,
    CONF_AUTO_ENERGY,
    CONF_CONNECTION_TYPE,
    CONF_DEVICE_NAME,
    CONF_HTTP_HOST,
    CONF_MQTT_TOPIC,
    CONF_POLLING_INTERVAL,
    CONNECTION_HTTP,
    CONNECTION_MQTT,
    DEFAULT_AUTO_CARD,
    DEFAULT_AUTO_ENERGY,
    DEFAULT_DEVICE_NAME,
    DEFAULT_MQTT_TOPIC,
    DEFAULT_POLLING_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GPlugEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for gPlug Energy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step – connection type selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            connection_type = user_input.get(CONF_CONNECTION_TYPE, CONNECTION_MQTT)

            if connection_type == CONNECTION_MQTT:
                return await self.async_step_mqtt(None)
            return await self.async_step_http(None)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONNECTION_TYPE, default=CONNECTION_MQTT
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=CONNECTION_MQTT,
                                    label="MQTT (empfohlen / recommended)",
                                ),
                                selector.SelectOptionDict(
                                    value=CONNECTION_HTTP,
                                    label="HTTP Polling",
                                ),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle MQTT configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mqtt_topic = user_input[CONF_MQTT_TOPIC].strip()
            device_name = user_input.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)

            # Validate topic format
            if not mqtt_topic or "/" not in mqtt_topic:
                errors["base"] = "invalid_topic"
            else:
                # Check for duplicate
                await self.async_set_unique_id(f"gplug_{mqtt_topic}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"gPlug – {device_name}",
                    data={
                        CONF_CONNECTION_TYPE: CONNECTION_MQTT,
                        CONF_MQTT_TOPIC: mqtt_topic,
                        CONF_DEVICE_NAME: device_name,
                    },
                )

        return self.async_show_form(
            step_id="mqtt",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_NAME, default=DEFAULT_DEVICE_NAME): str,
                    vol.Required(CONF_MQTT_TOPIC, default=DEFAULT_MQTT_TOPIC): str,
                }
            ),
            errors=errors,
        )

    async def async_step_http(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle HTTP polling configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HTTP_HOST].strip()
            device_name = user_input.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
            interval = user_input.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)

            if not host:
                errors["base"] = "invalid_host"
            else:
                await self.async_set_unique_id(f"gplug_http_{host}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"gPlug – {device_name} (HTTP)",
                    data={
                        CONF_CONNECTION_TYPE: CONNECTION_HTTP,
                        CONF_HTTP_HOST: host,
                        CONF_DEVICE_NAME: device_name,
                        CONF_POLLING_INTERVAL: interval,
                    },
                )

        return self.async_show_form(
            step_id="http",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_NAME, default=DEFAULT_DEVICE_NAME): str,
                    vol.Required(CONF_HTTP_HOST): str,
                    vol.Optional(
                        CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5,
                            max=300,
                            step=5,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return GPlugOptionsFlowHandler()


class GPlugOptionsFlowHandler(OptionsFlow):
    """Handle gPlug options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        connection_type = self.config_entry.data.get(
            CONF_CONNECTION_TYPE, CONNECTION_MQTT
        )

        # Current values (from options first, then data, then defaults)
        auto_energy = self.config_entry.options.get(
            CONF_AUTO_ENERGY,
            self.config_entry.data.get(CONF_AUTO_ENERGY, DEFAULT_AUTO_ENERGY),
        )
        auto_card = self.config_entry.options.get(
            CONF_AUTO_CARD,
            self.config_entry.data.get(CONF_AUTO_CARD, DEFAULT_AUTO_CARD),
        )

        schema_dict: dict = {
            vol.Optional(CONF_AUTO_ENERGY, default=auto_energy): bool,
            vol.Optional(CONF_AUTO_CARD, default=auto_card): bool,
        }

        if connection_type == CONNECTION_HTTP:
            polling = self.config_entry.options.get(
                CONF_POLLING_INTERVAL,
                self.config_entry.data.get(
                    CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL
                ),
            )
            schema_dict[vol.Optional(CONF_POLLING_INTERVAL, default=polling)] = (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5,
                        max=300,
                        step=5,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                )
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
