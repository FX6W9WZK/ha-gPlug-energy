"""Sensor platform for gPlug Energy integration."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_DEVICE_NAME,
    CONF_HTTP_HOST,
    CONF_MQTT_TOPIC,
    CONF_POLLING_INTERVAL,
    CONNECTION_MQTT,
    DEFAULT_MODEL,
    DEFAULT_POLLING_INTERVAL,
    DOMAIN,
    KNOWN_JSON_PREFIXES,
    MANUFACTURER,
    MODEL_DETECT_PATTERNS,
    SENSOR_KEY_ALIASES,
    detect_obis_key,
    SENSOR_SKIP_KEYS,
    SENSOR_TYPES_ENERGY,
)

_LOGGER = logging.getLogger(__name__)

# Read-only integration: MQTT push / coordinator-style HTTP polling.
PARALLEL_UPDATES = 0

# Map string device_class to HA enum
DEVICE_CLASS_MAP = {
    "energy": SensorDeviceClass.ENERGY,
    "power": SensorDeviceClass.POWER,
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
}

STATE_CLASS_MAP = {
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
    "measurement": SensorStateClass.MEASUREMENT,
    "total": SensorStateClass.TOTAL,
}

UNIT_MAP = {
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "Wh": UnitOfEnergy.WATT_HOUR,
    "kW": UnitOfPower.KILO_WATT,
    "W": UnitOfPower.WATT,
    "V": UnitOfElectricPotential.VOLT,
    "A": UnitOfElectricCurrent.AMPERE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up gPlug sensors from a config entry."""
    connection_type = config_entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_MQTT)
    device_name = config_entry.data.get(CONF_DEVICE_NAME, "gPlugD")

    if connection_type == CONNECTION_MQTT:
        await _setup_mqtt_sensors(hass, config_entry, async_add_entities, device_name)
    else:
        await _setup_http_sensors(hass, config_entry, async_add_entities, device_name)


async def _setup_mqtt_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    device_name: str,
) -> None:
    """Set up MQTT-based sensors with auto-discovery of available keys."""
    topic = config_entry.data[CONF_MQTT_TOPIC]
    entities: dict[str, GPlugSensor] = {}

    device_info = _build_device_info(config_entry, device_name)

    @callback
    def _message_received(msg):
        """Handle incoming MQTT messages and auto-create sensors."""
        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, TypeError):
            _LOGGER.warning("Invalid JSON payload on topic %s", msg.topic)
            return

        # Extract sensor data from known JSON prefixes
        sensor_data = _extract_sensor_data(payload)

        if not sensor_data:
            _LOGGER.debug(
                "No recognized sensor data in payload: %s", list(payload.keys())
            )
            return

        new_entities = []
        for key, value in sensor_data.items():
            # Skip non-sensor keys
            if key in SENSOR_SKIP_KEYS:
                continue

            # Resolve alias to canonical key
            canonical_key = SENSOR_KEY_ALIASES.get(key, key)
            sensor_config = SENSOR_TYPES_ENERGY.get(canonical_key)

            if sensor_config is None and (obis := detect_obis_key(key)):
                # Key from an unknown meter script, but it embeds an OBIS code
                canonical_key = obis
                sensor_config = SENSOR_TYPES_ENERGY[obis]

            if sensor_config is None:
                # Unknown key – create a generic sensor
                sensor_config = _make_generic_sensor_config(key, value)
                canonical_key = key

            entity_key = f"{config_entry.entry_id}_{canonical_key}"

            if entity_key not in entities:
                entity = GPlugSensor(
                    config_entry=config_entry,
                    key=canonical_key,
                    original_key=key,
                    sensor_config=sensor_config,
                    device_info=device_info,
                    device_name=device_name,
                )
                entities[entity_key] = entity
                new_entities.append(entity)
                _LOGGER.info("Discovered gPlug sensor: %s → %s", key, canonical_key)

            # Update existing entity value
            entities[entity_key].update_value(value)

        if new_entities:
            async_add_entities(new_entities)

    unsub = await mqtt.async_subscribe(hass, topic, _message_received, qos=0)
    config_entry.async_on_unload(unsub)

    stat_topic = topic.replace("tele/", "stat/").replace("/SENSOR", "/STATUS10")
    if stat_topic != topic:
        unsub_stat = await mqtt.async_subscribe(
            hass, stat_topic, _message_received, qos=0
        )
        config_entry.async_on_unload(unsub_stat)

    _LOGGER.info("gPlug MQTT subscribed to: %s", topic)


async def _setup_http_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    device_name: str,
) -> None:
    """Set up HTTP polling sensors."""
    host = config_entry.data[CONF_HTTP_HOST]
    interval = config_entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
    device_info = _build_device_info(config_entry, device_name)

    entities: dict[str, GPlugSensor] = {}
    url = f"http://{host}/cm?cmnd=Status+10"
    session = async_get_clientsession(hass, verify_ssl=False)

    async def _poll_data(_now=None):
        """Fetch sensor data via HTTP."""
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("HTTP %s from gPlug at %s", resp.status, host)
                    return
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            _LOGGER.error("Error polling gPlug at %s: %s", host, exc)
            return

        # Status 10 response wraps in StatusSNS
        payload = data.get("StatusSNS", data)
        sensor_data = _extract_sensor_data(payload)

        if not sensor_data:
            return

        new_entities = []
        for key, value in sensor_data.items():
            if key in SENSOR_SKIP_KEYS:
                continue

            canonical_key = SENSOR_KEY_ALIASES.get(key, key)
            sensor_config = SENSOR_TYPES_ENERGY.get(canonical_key)

            if sensor_config is None and (obis := detect_obis_key(key)):
                # Key from an unknown meter script, but it embeds an OBIS code
                canonical_key = obis
                sensor_config = SENSOR_TYPES_ENERGY[obis]

            if sensor_config is None:
                sensor_config = _make_generic_sensor_config(key, value)
                canonical_key = key

            entity_key = f"{config_entry.entry_id}_{canonical_key}"

            if entity_key not in entities:
                entity = GPlugSensor(
                    config_entry=config_entry,
                    key=canonical_key,
                    original_key=key,
                    sensor_config=sensor_config,
                    device_info=device_info,
                    device_name=device_name,
                )
                entities[entity_key] = entity
                new_entities.append(entity)

            entities[entity_key].update_value(value)

        if new_entities:
            async_add_entities(new_entities)

    await _poll_data()

    unsub_poll = async_track_time_interval(
        hass, _poll_data, timedelta(seconds=interval)
    )
    config_entry.async_on_unload(unsub_poll)


def _extract_sensor_data(payload: dict) -> dict[str, Any]:
    """
    Extract flat sensor key-value pairs from a Tasmota MQTT payload.

    Handles various JSON structures:
      {"ENERGY": {"Total": 123, ...}}
      {"SML": {"Total_in": 123, ...}}
      {"P1": {"enrg_imp": 123, ...}}
      or flat: {"Total_in": 123, ...}
    """
    result = {}

    for prefix in KNOWN_JSON_PREFIXES:
        if prefix in payload and isinstance(payload[prefix], dict):
            result.update(payload[prefix])
            return result

    # Fallback: check for flat keys (no prefix wrapper)
    for key, value in payload.items():
        if key == "Time":
            continue
        if isinstance(value, (int, float)):
            result[key] = value
        elif isinstance(value, dict):
            # Nested dict we haven't handled – flatten it
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, (int, float)):
                    result[sub_key] = sub_val

    return result


def _make_generic_sensor_config(key: str, value: Any) -> dict:
    """Create a generic sensor config for unrecognized keys."""
    return {
        "name": key.replace("_", " ").title(),
        "name_en": key.replace("_", " ").title(),
        "unit": None,
        "device_class": None,
        "state_class": "measurement",
        "icon": "mdi:gauge",
    }


def _detect_model(config_entry: ConfigEntry) -> str:
    """Auto-detect the gPlug model from the MQTT topic or device name."""
    topic = config_entry.data.get(CONF_MQTT_TOPIC, "")
    name = config_entry.data.get(CONF_DEVICE_NAME, "")
    search_str = f"{topic} {name}"

    # Check longest patterns first (gPlugD-E before gPlugD)
    for pattern, model in sorted(
        MODEL_DETECT_PATTERNS.items(), key=lambda x: -len(x[0])
    ):
        if pattern in search_str:
            return model

    return DEFAULT_MODEL


def _build_device_info(config_entry: ConfigEntry, device_name: str) -> DeviceInfo:
    """Build the device info dict with auto-detected model."""
    model = _detect_model(config_entry)
    info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=device_name,
        manufacturer=MANUFACTURER,
        model=model,
        sw_version="Tasmota",
    )
    http_host = config_entry.data.get(CONF_HTTP_HOST)
    if http_host:
        info["configuration_url"] = f"http://{http_host}"
    return info


class GPlugSensor(SensorEntity):
    """Representation of a gPlug energy sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        key: str,
        original_key: str,
        sensor_config: dict,
        device_info: DeviceInfo,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        self._config_entry = config_entry
        self._key = key
        self._original_key = original_key
        self._sensor_config = sensor_config
        self._attr_device_info = device_info

        # Entity attributes
        self._attr_unique_id = f"{config_entry.entry_id}_{key}"
        self._attr_name = sensor_config.get("name_en", sensor_config["name"])
        self._attr_icon = sensor_config.get("icon")

        # Device class
        dc = sensor_config.get("device_class")
        if dc and dc in DEVICE_CLASS_MAP:
            self._attr_device_class = DEVICE_CLASS_MAP[dc]

        # State class – critical for Energy Dashboard
        sc = sensor_config.get("state_class")
        if sc and sc in STATE_CLASS_MAP:
            self._attr_state_class = STATE_CLASS_MAP[sc]

        # Unit of measurement
        unit = sensor_config.get("unit")
        if unit and unit in UNIT_MAP:
            self._attr_native_unit_of_measurement = UNIT_MAP[unit]
        elif unit:
            self._attr_native_unit_of_measurement = unit

        # Suggested display precision
        if dc == "energy" or dc == "power":
            self._attr_suggested_display_precision = 3
        elif dc in ("voltage", "current"):
            self._attr_suggested_display_precision = 1

        self._attr_native_value = None

    @callback
    def update_value(self, value: Any) -> None:
        """Update the sensor value."""
        try:
            self._attr_native_value = round(float(value), 4)
        except (ValueError, TypeError):
            # Meters occasionally report non-numeric placeholders such as
            # "n/a". Writing those to a sensor with a numeric device class
            # raises in HA, so report the value as unknown instead.
            self._attr_native_value = None

        if self.hass and self.entity_id:
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "obis_key": self._original_key,
            "integration": DOMAIN,
        }
