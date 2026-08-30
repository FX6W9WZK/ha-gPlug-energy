"""Tests for the Energy Dashboard auto-configuration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gplug_energy.const import DOMAIN
from custom_components.gplug_energy.energy import (
    _find_entity_id,
    async_configure_energy_dashboard,
)

PATCH_TARGET = "homeassistant.components.energy.async_get_manager"


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """A config entry added to hass for registry operations."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="gplug_test")
    config_entry.add_to_hass(hass)
    return config_entry


def _make_manager(prefs) -> MagicMock:
    manager = MagicMock()
    manager.data = prefs
    manager.async_update = AsyncMock()
    return manager


def _register(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    """Register a sensor entity with the integration's unique_id scheme."""
    ent_reg = er.async_get(hass)
    reg_entry = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_{key}",
        config_entry=entry,
    )
    return reg_entry.entity_id


async def test_energy_component_not_available(hass: HomeAssistant, entry) -> None:
    """A missing energy component (ImportError) is handled gracefully."""
    import sys

    with patch.dict(sys.modules, {"homeassistant.components.energy": None}):
        await async_configure_energy_dashboard(hass, entry.entry_id)


async def test_manager_unavailable(hass: HomeAssistant, entry) -> None:
    """Failure to access the energy manager is swallowed."""
    with patch(PATCH_TARGET, new=AsyncMock(side_effect=RuntimeError("boom"))):
        await async_configure_energy_dashboard(hass, entry.entry_id)


async def test_prefs_not_initialized(hass: HomeAssistant, entry) -> None:
    """Uninitialized energy preferences skip the auto-config."""
    manager = _make_manager(None)
    with patch(PATCH_TARGET, new=AsyncMock(return_value=manager)):
        await async_configure_energy_dashboard(hass, entry.entry_id)
    manager.async_update.assert_not_awaited()


async def test_existing_gplug_source_skips(hass: HomeAssistant, entry) -> None:
    """An already configured gPlug source prevents duplicates."""
    _register(hass, entry, "Ei1_1.8.1")
    manager = _make_manager(
        {
            "energy_sources": [
                {"type": "grid", "stat_energy_from": "sensor.gplug_energy_import"}
            ]
        }
    )
    with patch(PATCH_TARGET, new=AsyncMock(return_value=manager)):
        await async_configure_energy_dashboard(hass, entry.entry_id)
    manager.async_update.assert_not_awaited()


async def test_existing_gplug_export_source_skips(hass: HomeAssistant, entry) -> None:
    """A gPlug sensor in stat_energy_to also prevents duplicates."""
    manager = _make_manager(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "stat_energy_from": "sensor.other",
                    "stat_energy_to": "sensor.gplug_energy_export",
                }
            ]
        }
    )
    with patch(PATCH_TARGET, new=AsyncMock(return_value=manager)):
        await async_configure_energy_dashboard(hass, entry.entry_id)
    manager.async_update.assert_not_awaited()


async def test_no_sensors_found(hass: HomeAssistant, entry) -> None:
    """Without registered gPlug sensors nothing is written."""
    manager = _make_manager({"energy_sources": []})
    with patch(PATCH_TARGET, new=AsyncMock(return_value=manager)):
        await async_configure_energy_dashboard(hass, entry.entry_id)
    manager.async_update.assert_not_awaited()


async def test_full_tariff_configuration(hass: HomeAssistant, entry) -> None:
    """Both tariffs get grid sources with paired export sensors and prices."""
    import_1 = _register(hass, entry, "Ei1_1.8.1")
    import_2 = _register(hass, entry, "Ei2_1.8.2")
    export_1 = _register(hass, entry, "Eo1_2.8.1")
    export_2 = _register(hass, entry, "Eo2_2.8.2")

    existing = {"type": "solar", "stat_energy_from": "sensor.pv"}
    manager = _make_manager({"energy_sources": [existing]})

    with patch(PATCH_TARGET, new=AsyncMock(return_value=manager)):
        await async_configure_energy_dashboard(hass, entry.entry_id)

    manager.async_update.assert_awaited_once()
    sources = manager.async_update.await_args.args[0]["energy_sources"]
    assert sources[0] == existing  # existing sources are preserved
    assert len(sources) == 3

    tariff_1, tariff_2 = sources[1], sources[2]
    assert tariff_1["type"] == "grid"
    assert tariff_1["stat_energy_from"] == import_1
    assert tariff_1["stat_energy_to"] == export_1
    assert tariff_1["number_energy_price"] == 0.27
    assert tariff_2["stat_energy_from"] == import_2
    assert tariff_2["stat_energy_to"] == export_2
    assert tariff_2["number_energy_price"] == 0.21


async def test_mismatched_export_tariff_not_paired(hass: HomeAssistant, entry) -> None:
    """An export sensor of a different tariff index is not paired."""
    import_1 = _register(hass, entry, "Ei1_1.8.1")
    _register(hass, entry, "Eo2_2.8.2")  # only tariff-2 export exists

    manager = _make_manager({"energy_sources": []})
    with patch(PATCH_TARGET, new=AsyncMock(return_value=manager)):
        await async_configure_energy_dashboard(hass, entry.entry_id)

    sources = manager.async_update.await_args.args[0]["energy_sources"]
    assert len(sources) == 1
    assert sources[0]["stat_energy_from"] == import_1
    assert sources[0]["stat_energy_to"] is None


async def test_update_failure_is_swallowed(
    hass: HomeAssistant, entry, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing manager.async_update logs a warning but never raises."""
    _register(hass, entry, "Ei1_1.8.1")
    manager = _make_manager({"energy_sources": []})
    manager.async_update = AsyncMock(side_effect=RuntimeError("save failed"))

    with patch(PATCH_TARGET, new=AsyncMock(return_value=manager)):
        await async_configure_energy_dashboard(hass, entry.entry_id)

    assert "Could not auto-configure Energy Dashboard" in caplog.text


def test_find_entity_id(hass: HomeAssistant, entry) -> None:
    """_find_entity_id resolves registered keys and returns None otherwise."""
    ent_reg = er.async_get(hass)
    assert _find_entity_id(ent_reg, entry.entry_id, "Ei1_1.8.1") is None

    entity_id = _register(hass, entry, "Ei1_1.8.1")
    assert _find_entity_id(ent_reg, entry.entry_id, "Ei1_1.8.1") == entity_id
