"""Tests for gPlug Energy setup, unload, card registration and options reload."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.gplug_energy import (
    CARD_STATIC_URL,
    CARD_URL,
    _add_lovelace_resource,
    _register_card,
    async_update_options,
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


import pytest


@pytest.fixture
def expected_lingering_timers() -> bool:
    """Tolerate the MQTT mock's periodic keepalive timer after teardown."""
    return True


def _mqtt_entry(**options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="gplug_tele/gplugd/SENSOR",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_MQTT,
            CONF_MQTT_TOPIC: "tele/gplugd/SENSOR",
            CONF_DEVICE_NAME: "gPlugD",
        },
        options={CONF_AUTO_CARD: False, CONF_AUTO_ENERGY: False, **options},
    )


async def test_setup_and_unload_mqtt_entry(hass: HomeAssistant, mqtt_mock) -> None:
    """An MQTT entry sets up the sensor platform and unloads cleanly."""
    entry = _mqtt_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_and_unload_http_entry(
    hass: HomeAssistant, mqtt_mock, aioclient_mock
) -> None:
    """An HTTP entry sets up polling and unloads cleanly."""
    aioclient_mock.get(
        "http://10.0.0.3/cm?cmnd=Status+10",
        json={"StatusSNS": {"ENERGY": {"Ei_1.8": 100.0}}},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="gplug_http_10.0.0.3",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_HTTP,
            CONF_HTTP_HOST: "10.0.0.3",
            CONF_DEVICE_NAME: "gPlugD",
            CONF_POLLING_INTERVAL: 10,
        },
        options={CONF_AUTO_CARD: False, CONF_AUTO_ENERGY: False},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_with_auto_card_calls_register(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """auto_card=True triggers the card registration helper."""
    entry = _mqtt_entry(**{CONF_AUTO_CARD: True})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.gplug_energy._register_card", new=AsyncMock()
    ) as register_mock:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    register_mock.assert_awaited_once()


async def test_setup_auto_card_survives_missing_http(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """Card registration failure (no hass.http in tests) never breaks setup."""
    entry = _mqtt_entry(**{CONF_AUTO_CARD: True})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_with_auto_energy_schedules_config(
    hass: HomeAssistant, mqtt_mock
) -> None:
    """auto_energy=True schedules the delayed energy dashboard configuration."""
    entry = _mqtt_entry(**{CONF_AUTO_ENERGY: True})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.gplug_energy.energy.async_configure_energy_dashboard",
        new=AsyncMock(),
    ) as energy_mock:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        energy_mock.assert_not_awaited()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done()

    energy_mock.assert_awaited_once_with(hass, entry.entry_id)


async def test_update_options_triggers_reload(hass: HomeAssistant, mqtt_mock) -> None:
    """Changing options reloads the entry via the update listener."""
    entry = _mqtt_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock()
    ) as reload_mock:
        await async_update_options(hass, entry)

    reload_mock.assert_awaited_once_with(entry.entry_id)


# ── _register_card ────────────────────────────────────────────────────────


async def test_register_card_modern_api(hass: HomeAssistant) -> None:
    """New-style async_register_static_paths API is used when available."""
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    await _register_card(hass)

    hass.http.async_register_static_paths.assert_awaited_once()
    config = hass.http.async_register_static_paths.await_args.args[0][0]
    assert config.url_path == CARD_STATIC_URL


async def test_register_card_legacy_api(hass: HomeAssistant) -> None:
    """Legacy register_static_path is used when the new API is missing."""
    legacy_mock = MagicMock()
    hass.http = SimpleNamespace(register_static_path=legacy_mock)

    await _register_card(hass)

    legacy_mock.assert_called_once_with(
        CARD_STATIC_URL, str(legacy_mock.call_args.args[1]), cache_headers=True
    )


async def test_register_card_static_path_error(hass: HomeAssistant) -> None:
    """A failure while serving the file aborts before the Lovelace step."""
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock(side_effect=RuntimeError("boom"))
    resources = MagicMock()
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    await _register_card(hass)

    resources.async_items.assert_not_called()


# ── _add_lovelace_resource ────────────────────────────────────────────────


def _lovelace(hass, items, loaded=True):
    resources = MagicMock()
    resources.loaded = loaded
    resources.async_items = MagicMock(return_value=items)
    resources.async_update_item = AsyncMock()
    resources.async_create_item = AsyncMock()
    hass.data["lovelace"] = SimpleNamespace(resources=resources)
    return resources


async def test_add_resource_no_lovelace(hass: HomeAssistant) -> None:
    """No lovelace data (YAML mode) is handled gracefully."""
    await _add_lovelace_resource(hass, CARD_URL)


async def test_add_resource_lovelace_without_resources(hass: HomeAssistant) -> None:
    """Lovelace data without a resources attribute is handled gracefully."""
    hass.data["lovelace"] = object()
    await _add_lovelace_resource(hass, CARD_URL)


async def test_add_resource_not_loaded(hass: HomeAssistant) -> None:
    """Unloaded resources are left alone."""
    resources = _lovelace(hass, [], loaded=False)
    await _add_lovelace_resource(hass, CARD_URL)
    resources.async_create_item.assert_not_awaited()


async def test_add_resource_creates_new(hass: HomeAssistant) -> None:
    """The card is created when no matching resource exists."""
    resources = _lovelace(hass, [{"id": "1", "url": "/other/card.js"}])
    await _add_lovelace_resource(hass, CARD_URL)
    resources.async_create_item.assert_awaited_once_with(
        {"res_type": "module", "url": CARD_URL}
    )


async def test_add_resource_already_current(hass: HomeAssistant) -> None:
    """A resource with the current version is not touched."""
    resources = _lovelace(hass, [{"id": "1", "url": CARD_URL}])
    await _add_lovelace_resource(hass, CARD_URL)
    resources.async_update_item.assert_not_awaited()
    resources.async_create_item.assert_not_awaited()


async def test_add_resource_updates_old_version(hass: HomeAssistant) -> None:
    """A resource with an outdated version gets updated."""
    resources = _lovelace(hass, [{"id": "42", "url": f"{CARD_STATIC_URL}?v=0.0.1"}])
    await _add_lovelace_resource(hass, CARD_URL)
    resources.async_update_item.assert_awaited_once_with("42", {"url": CARD_URL})
    resources.async_create_item.assert_not_awaited()


async def test_add_resource_swallows_errors(hass: HomeAssistant) -> None:
    """Exceptions from the private Lovelace API never propagate."""
    resources = _lovelace(hass, [])
    resources.async_items.side_effect = RuntimeError("boom")
    await _add_lovelace_resource(hass, CARD_URL)
