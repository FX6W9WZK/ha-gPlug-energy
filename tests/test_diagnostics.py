"""Tests for gPlug Energy diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gplug_energy.const import (
    CONF_AUTO_ENERGY,
    CONF_CONNECTION_TYPE,
    CONF_DEVICE_NAME,
    CONF_HTTP_HOST,
    CONNECTION_HTTP,
    DOMAIN,
)
from custom_components.gplug_energy.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_passwords(hass: HomeAssistant) -> None:
    """Password-like keys are redacted; everything else passes through."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: CONNECTION_HTTP,
            CONF_HTTP_HOST: "10.0.0.7",
            CONF_DEVICE_NAME: "gPlugD",
            "http_password": "geheim",
            "MQTT_Password": "auch-geheim",
        },
        options={CONF_AUTO_ENERGY: False},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["config_entry_data"] == {
        CONF_CONNECTION_TYPE: CONNECTION_HTTP,
        CONF_HTTP_HOST: "10.0.0.7",
        CONF_DEVICE_NAME: "gPlugD",
        "http_password": "**REDACTED**",
        "MQTT_Password": "**REDACTED**",
    }
    assert diagnostics["config_entry_options"] == {CONF_AUTO_ENERGY: False}
