"""Tests for the gPlug Energy sensor platform (MQTT and HTTP)."""

from __future__ import annotations

import json
from datetime import timedelta

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
)

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
from custom_components.gplug_energy.sensor import _detect_model

@pytest.fixture
def expected_lingering_timers() -> bool:
    """Tolerate the MQTT mock's periodic keepalive timer after teardown."""
    return True


TOPIC = "tele/gplugd/SENSOR"
HTTP_URL = "http://192.168.1.50/cm?cmnd=Status+10"


async def _setup_mqtt_entry(hass: HomeAssistant, topic: str = TOPIC) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"gplug_{topic}",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_MQTT,
            CONF_MQTT_TOPIC: topic,
            CONF_DEVICE_NAME: "gPlugD",
        },
        options={CONF_AUTO_CARD: False, CONF_AUTO_ENERGY: False},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str | None:
    ent_reg = er.async_get(hass)
    return ent_reg.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")


# ── MQTT path ─────────────────────────────────────────────────────────────


async def test_mqtt_energy_payload_creates_sensors(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """A Tasmota ENERGY payload creates properly configured sensors."""
    entry = await _setup_mqtt_entry(hass)

    payload = {
        "Time": "2026-08-30T12:00:00",
        "ENERGY": {
            "Ei_1.8": 1234.5678,
            "Pi_1.7": 1.234,
            "V1_32.7": 231.2,
            "I1_31.7": 2.5,
        },
    }
    async_fire_mqtt_message(hass, TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    energy_id = _entity_id(hass, entry, "Ei_1.8")
    assert energy_id is not None
    state = hass.states.get(energy_id)
    assert state.state == "1234.5678"
    assert state.attributes["device_class"] == "energy"
    assert state.attributes["state_class"] == "total_increasing"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["obis_key"] == "Ei_1.8"
    assert state.attributes["integration"] == DOMAIN

    power = hass.states.get(_entity_id(hass, entry, "Pi_1.7"))
    assert power.state == "1.234"
    assert power.attributes["device_class"] == "power"
    assert power.attributes["unit_of_measurement"] == "kW"

    voltage = hass.states.get(_entity_id(hass, entry, "V1_32.7"))
    assert voltage.attributes["device_class"] == "voltage"
    current = hass.states.get(_entity_id(hass, entry, "I1_31.7"))
    assert current.attributes["device_class"] == "current"


async def test_mqtt_alias_keys_resolve_to_canonical(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """SML alias keys map to canonical OBIS sensors and keep the raw key."""
    entry = await _setup_mqtt_entry(hass)

    payload = {"SML": {"Total_in": 100.5, "Power_in": 0.75}}
    async_fire_mqtt_message(hass, TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    energy_id = _entity_id(hass, entry, "Ei_1.8")
    assert energy_id is not None
    state = hass.states.get(energy_id)
    assert state.state == "100.5"
    assert state.attributes["obis_key"] == "Total_in"

    assert _entity_id(hass, entry, "Pi_1.7") is not None


async def test_mqtt_flat_payload_and_generic_sensor(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """Flat payloads without a known prefix work; unknown keys get generic sensors."""
    entry = await _setup_mqtt_entry(hass)

    payload = {"Time": "2026-08-30T12:00:00", "Ei": 55.5, "Custom_value": 7}
    async_fire_mqtt_message(hass, TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, entry, "Ei_1.8")).state == "55.5"

    generic_id = _entity_id(hass, entry, "Custom_value")
    assert generic_id is not None
    state = hass.states.get(generic_id)
    assert state.state == "7.0"
    assert state.attributes["icon"] == "mdi:gauge"
    assert state.attributes["state_class"] == "measurement"
    assert "device_class" not in state.attributes


async def test_mqtt_unknown_nested_dict_is_flattened(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """Nested dicts under unknown prefixes are flattened to numeric leaves."""
    entry = await _setup_mqtt_entry(hass)

    payload = {"MT175": {"E_in": 3.0, "Meter_id": "abc"}}
    async_fire_mqtt_message(hass, TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    generic_id = _entity_id(hass, entry, "E_in")
    assert generic_id is not None
    assert hass.states.get(generic_id).state == "3.0"
    assert _entity_id(hass, entry, "Meter_id") is None


async def test_mqtt_invalid_json_is_ignored(
    hass: HomeAssistant, mqtt_mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Broken JSON payloads log a warning and create nothing."""
    await _setup_mqtt_entry(hass)

    async_fire_mqtt_message(hass, TOPIC, "this is not json")
    await hass.async_block_till_done()

    assert "Invalid JSON payload" in caplog.text
    assert hass.states.async_entity_ids("sensor") == []


async def test_mqtt_payload_without_sensor_data(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """Payloads without any numeric data create no entities."""
    await _setup_mqtt_entry(hass)

    async_fire_mqtt_message(
        hass, TOPIC, json.dumps({"Time": "2026-08-30T12:00:00", "Status": "ok"})
    )
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids("sensor") == []


async def test_mqtt_skip_keys_are_ignored(hass: HomeAssistant, mqtt_mock) -> None:
    """SMid and Time inside the prefix dict never become sensors."""
    entry = await _setup_mqtt_entry(hass)

    payload = {"ENERGY": {"SMid": 12345, "Time": "x", "Ei": 1.0}}
    async_fire_mqtt_message(hass, TOPIC, json.dumps(payload))
    await hass.async_block_till_done()

    assert _entity_id(hass, entry, "Ei_1.8") is not None
    assert _entity_id(hass, entry, "SMid") is None
    assert _entity_id(hass, entry, "Time") is None


async def test_mqtt_second_message_updates_existing(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """A second message updates values without duplicating entities."""
    entry = await _setup_mqtt_entry(hass)

    async_fire_mqtt_message(hass, TOPIC, json.dumps({"ENERGY": {"Ei": 1.0}}))
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TOPIC, json.dumps({"ENERGY": {"Ei": 2.0}}))
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, entry, "Ei_1.8")).state == "2.0"
    assert len(hass.states.async_entity_ids("sensor")) == 1


def test_update_value_non_numeric_becomes_unknown() -> None:
    """Non-numeric meter values are reported as unknown, numeric ones rounded."""
    from custom_components.gplug_energy.sensor import (
        GPlugSensor,
        _make_generic_sensor_config,
    )

    entry = MockConfigEntry(domain=DOMAIN, data={})
    sensor = GPlugSensor(
        config_entry=entry,
        key="Custom",
        original_key="Custom",
        sensor_config=_make_generic_sensor_config("Custom", "n/a"),
        device_info=None,
        device_name="gPlugD",
    )

    sensor.update_value("n/a")
    assert sensor.native_value is None

    sensor.update_value("1.23456789")
    assert sensor.native_value == 1.2346


def test_sensor_unknown_unit_passes_through() -> None:
    """A unit outside the UNIT_MAP is used verbatim."""
    from custom_components.gplug_energy.sensor import GPlugSensor

    entry = MockConfigEntry(domain=DOMAIN, data={})
    sensor = GPlugSensor(
        config_entry=entry,
        key="Gas",
        original_key="Gas",
        sensor_config={
            "name": "Gas",
            "name_en": "Gas",
            "unit": "m³",
            "device_class": None,
            "state_class": "total",
            "icon": "mdi:gas-burner",
        },
        device_info=None,
        device_name="gPlugD",
    )
    assert sensor.native_unit_of_measurement == "m³"


async def test_mqtt_status10_topic_is_subscribed(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """The derived stat/.../STATUS10 topic feeds the same sensors."""
    entry = await _setup_mqtt_entry(hass)

    async_fire_mqtt_message(
        hass, "stat/gplugd/STATUS10", json.dumps({"ENERGY": {"Ei": 42.0}})
    )
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, entry, "Ei_1.8")).state == "42.0"


async def test_mqtt_custom_topic_without_stat_variant(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """A topic that yields no distinct STATUS10 variant still works."""
    entry = await _setup_mqtt_entry(hass, topic="custom/topic")

    async_fire_mqtt_message(hass, "custom/topic", json.dumps({"ENERGY": {"Ei": 9.0}}))
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, entry, "Ei_1.8")).state == "9.0"


# ── HTTP path ─────────────────────────────────────────────────────────────


async def _setup_http_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="gplug_http_192.168.1.50",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_HTTP,
            CONF_HTTP_HOST: "192.168.1.50",
            CONF_DEVICE_NAME: "gPlugD HTTP",
            CONF_POLLING_INTERVAL: 10,
        },
        options={CONF_AUTO_CARD: False, CONF_AUTO_ENERGY: False},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_http_polling_creates_and_updates_sensors(
    hass: HomeAssistant, mqtt_mock, aioclient_mock
) -> None:
    """HTTP polling parses the StatusSNS wrapper and polls on the interval."""
    aioclient_mock.get(
        HTTP_URL,
        json={
            "StatusSNS": {
                "Time": "2026-08-30T12:00:00",
                "ENERGY": {"Ei_1.8": 500.25, "Pi_1.7": 0.8},
            }
        },
    )
    entry = await _setup_http_entry(hass)

    energy_id = _entity_id(hass, entry, "Ei_1.8")
    assert energy_id is not None
    assert hass.states.get(energy_id).state == "500.25"
    assert hass.states.get(_entity_id(hass, entry, "Pi_1.7")).state == "0.8"
    assert aioclient_mock.call_count == 1

    # Device info includes the configuration URL for HTTP devices
    from homeassistant.helpers import device_registry as dr

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None
    assert device.configuration_url == "http://192.168.1.50"
    assert device.name == "gPlugD HTTP"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


async def test_http_payload_without_wrapper(
    hass: HomeAssistant, mqtt_mock, aioclient_mock
) -> None:
    """A response without the StatusSNS wrapper is parsed directly."""
    aioclient_mock.get(HTTP_URL, json={"ENERGY": {"Ei_1.8": 7.0}})
    entry = await _setup_http_entry(hass)

    assert hass.states.get(_entity_id(hass, entry, "Ei_1.8")).state == "7.0"


async def test_http_non_200_response(
    hass: HomeAssistant, mqtt_mock, aioclient_mock, caplog: pytest.LogCaptureFixture
) -> None:
    """A non-200 response logs a warning and creates no entities."""
    aioclient_mock.get(HTTP_URL, status=500)
    await _setup_http_entry(hass)

    assert "HTTP 500" in caplog.text
    assert hass.states.async_entity_ids("sensor") == []


async def test_http_client_error(
    hass: HomeAssistant, mqtt_mock, aioclient_mock, caplog: pytest.LogCaptureFixture
) -> None:
    """A connection error logs an error and creates no entities."""
    aioclient_mock.get(HTTP_URL, exc=aiohttp.ClientError("no route"))
    await _setup_http_entry(hass)

    assert "Error polling gPlug" in caplog.text
    assert hass.states.async_entity_ids("sensor") == []


async def test_http_invalid_json(
    hass: HomeAssistant, mqtt_mock, aioclient_mock, caplog: pytest.LogCaptureFixture
) -> None:
    """A non-JSON body hits the ValueError branch and creates no entities."""
    aioclient_mock.get(HTTP_URL, text="<html>not json</html>")
    await _setup_http_entry(hass)

    assert "Error polling gPlug" in caplog.text
    assert hass.states.async_entity_ids("sensor") == []


async def test_http_skip_keys_and_generic_sensor(
    hass: HomeAssistant, mqtt_mock, aioclient_mock
) -> None:
    """HTTP path skips SMid/Time and creates generic sensors for unknown keys."""
    aioclient_mock.get(
        HTTP_URL,
        json={
            "StatusSNS": {
                "ENERGY": {"SMid": 999, "Time": "x", "Ei": 3.5, "Custom_value": 4}
            }
        },
    )
    entry = await _setup_http_entry(hass)

    assert hass.states.get(_entity_id(hass, entry, "Ei_1.8")).state == "3.5"
    generic = hass.states.get(_entity_id(hass, entry, "Custom_value"))
    assert generic.state == "4.0"
    assert generic.attributes["icon"] == "mdi:gauge"
    assert _entity_id(hass, entry, "SMid") is None
    assert _entity_id(hass, entry, "Time") is None


async def test_http_empty_sensor_data(
    hass: HomeAssistant, mqtt_mock, aioclient_mock
) -> None:
    """A payload without numeric data creates no entities."""
    aioclient_mock.get(HTTP_URL, json={"StatusSNS": {"Time": "x", "Status": "ok"}})
    await _setup_http_entry(hass)

    assert hass.states.async_entity_ids("sensor") == []


# ── Model detection ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("topic", "name", "model"),
    [
        ("tele/gplugd/SENSOR", "", "gPlugD"),
        ("tele/gplugd-e/SENSOR", "", "gPlugD-E"),
        ("tele/gPlugD_E/SENSOR", "", "gPlugD-E"),
        ("tele/gplugde/SENSOR", "", "gPlugD-E"),
        ("tele/gpluge/SENSOR", "", "gPlugE"),
        ("tele/gplugk/SENSOR", "", "gPlugK"),
        ("tele/gplugm/SENSOR", "", "gPlugM"),
        ("tele/meter/SENSOR", "gPlugK Keller", "gPlugK"),
        ("tele/meter/SENSOR", "Smart Meter", "gPlugD"),  # default
    ],
)
def test_detect_model(topic: str, name: str, model: str) -> None:
    """Model detection prefers longer patterns and falls back to the default."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MQTT_TOPIC: topic, CONF_DEVICE_NAME: name},
    )
    assert _detect_model(entry) == model
