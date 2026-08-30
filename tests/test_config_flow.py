"""Tests for the gPlug Energy config and options flows."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gplug_energy.const import (
    CONF_AUTO_CARD,
    CONF_AUTO_ENERGY,
    CONF_CONNECTION_TYPE,
    CONF_DEVICE_NAME,
    CONF_HTTP_HOST,
    CONF_MQTT_TOPIC,
    CONF_POLLING_INTERVAL,
    CONNECTION_HTTP,
    CONNECTION_MQTT,
    DOMAIN,
)


async def _start_flow(hass: HomeAssistant, connection_type: str):
    """Start the user flow and select a connection type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONNECTION_TYPE: connection_type}
    )


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """The initial step shows the connection type selection form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_mqtt_flow_success(hass: HomeAssistant, mock_setup_entry) -> None:
    """MQTT path creates an entry with the expected data."""
    result = await _start_flow(hass, CONNECTION_MQTT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_NAME: "Keller", CONF_MQTT_TOPIC: " tele/gplugd/SENSOR "},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "gPlug – Keller"
    assert result["data"] == {
        CONF_CONNECTION_TYPE: CONNECTION_MQTT,
        CONF_MQTT_TOPIC: "tele/gplugd/SENSOR",
        CONF_DEVICE_NAME: "Keller",
    }
    assert result["result"].unique_id == "gplug_tele/gplugd/SENSOR"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_mqtt_flow_invalid_topic_then_recover(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """A topic without a slash shows invalid_topic; a valid retry succeeds."""
    result = await _start_flow(hass, CONNECTION_MQTT)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_NAME: "gPlugD", CONF_MQTT_TOPIC: "noslash"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt"
    assert result["errors"] == {"base": "invalid_topic"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_NAME: "gPlugD", CONF_MQTT_TOPIC: "tele/gplugd/SENSOR"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_mqtt_flow_duplicate_aborts(hass: HomeAssistant) -> None:
    """A second entry with the same MQTT topic aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="gplug_tele/gplugd/SENSOR",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_MQTT,
            CONF_MQTT_TOPIC: "tele/gplugd/SENSOR",
        },
    ).add_to_hass(hass)

    result = await _start_flow(hass, CONNECTION_MQTT)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_NAME: "gPlugD", CONF_MQTT_TOPIC: "tele/gplugd/SENSOR"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_http_flow_success(hass: HomeAssistant, mock_setup_entry) -> None:
    """HTTP path creates an entry with host and polling interval."""
    result = await _start_flow(hass, CONNECTION_HTTP)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "http"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: "Garage",
            CONF_HTTP_HOST: " 192.168.1.50 ",
            CONF_POLLING_INTERVAL: 15,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "gPlug – Garage (HTTP)"
    assert result["data"] == {
        CONF_CONNECTION_TYPE: CONNECTION_HTTP,
        CONF_HTTP_HOST: "192.168.1.50",
        CONF_DEVICE_NAME: "Garage",
        CONF_POLLING_INTERVAL: 15,
    }
    assert result["result"].unique_id == "gplug_http_192.168.1.50"


async def test_http_flow_invalid_host_then_recover(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """A whitespace-only host shows invalid_host; a valid retry succeeds."""
    result = await _start_flow(hass, CONNECTION_HTTP)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_NAME: "gPlugD", CONF_HTTP_HOST: "   ", CONF_POLLING_INTERVAL: 10},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "http"
    assert result["errors"] == {"base": "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: "gPlugD",
            CONF_HTTP_HOST: "10.0.0.2",
            CONF_POLLING_INTERVAL: 10,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_http_flow_duplicate_aborts(hass: HomeAssistant) -> None:
    """A second entry with the same HTTP host aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="gplug_http_10.0.0.5",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_HTTP,
            CONF_HTTP_HOST: "10.0.0.5",
        },
    ).add_to_hass(hass)

    result = await _start_flow(hass, CONNECTION_HTTP)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: "gPlugD",
            CONF_HTTP_HOST: "10.0.0.5",
            CONF_POLLING_INTERVAL: 10,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_mqtt(hass: HomeAssistant, mock_setup_entry) -> None:
    """Options flow for an MQTT entry offers no polling interval field."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="gplug_tele/gplugd/SENSOR",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_MQTT,
            CONF_MQTT_TOPIC: "tele/gplugd/SENSOR",
            CONF_DEVICE_NAME: "gPlugD",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema_keys = [str(key) for key in result["data_schema"].schema]
    assert CONF_AUTO_ENERGY in schema_keys
    assert CONF_AUTO_CARD in schema_keys
    assert CONF_POLLING_INTERVAL not in schema_keys

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTO_ENERGY: False, CONF_AUTO_CARD: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_AUTO_ENERGY: False, CONF_AUTO_CARD: True}


async def test_options_flow_http(hass: HomeAssistant, mock_setup_entry) -> None:
    """Options flow for an HTTP entry includes the polling interval field."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="gplug_http_10.0.0.9",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_HTTP,
            CONF_HTTP_HOST: "10.0.0.9",
            CONF_DEVICE_NAME: "gPlugD",
            CONF_POLLING_INTERVAL: 10,
        },
        options={CONF_AUTO_ENERGY: True},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    schema_keys = [str(key) for key in result["data_schema"].schema]
    assert CONF_POLLING_INTERVAL in schema_keys

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_AUTO_ENERGY: True, CONF_AUTO_CARD: False, CONF_POLLING_INTERVAL: 30},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_AUTO_ENERGY: True,
        CONF_AUTO_CARD: False,
        CONF_POLLING_INTERVAL: 30,
    }
