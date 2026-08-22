"""Auto-configure the Home Assistant Energy Dashboard for gPlug sensors."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Sensor keys → (OBIS key, default price CHF/kWh or None)
ENERGY_IMPORT_KEYS = [
    ("Ei1_1.8.1", 0.27),  # Tariff 1 (HT)
    ("Ei2_1.8.2", 0.21),  # Tariff 2 (NT)
]

ENERGY_EXPORT_KEYS = [
    ("Eo1_2.8.1", None),  # Tariff 1 (HT)
    ("Eo2_2.8.2", None),  # Tariff 2 (NT)
]


async def async_configure_energy_dashboard(
    hass: HomeAssistant,
    entry_id: str,
) -> None:
    """Auto-configure sensors in the Energy Dashboard.

    Uses the flat grid-source format (one source per tariff).
    Only runs once: if any gPlug sensor is already present, it skips entirely.
    """
    try:
        from homeassistant.components.energy import async_get_manager
    except ImportError:
        _LOGGER.debug("Energy component not available, skipping auto-config")
        return

    try:
        manager = await async_get_manager(hass)
        prefs = manager.data
    except Exception:  # noqa: BLE001 — private HA API, must never break setup
        _LOGGER.debug("Could not access energy manager, skipping auto-config")
        return

    if prefs is None:
        _LOGGER.debug("Energy preferences not initialized yet")
        return

    existing_sources = prefs.get("energy_sources", [])

    # Check if ANY gplug sensor is already configured – if so, skip entirely
    for source in existing_sources:
        for key in ("stat_energy_from", "stat_energy_to"):
            val = source.get(key, "") or ""
            if "gplug" in val:
                _LOGGER.debug(
                    "gPlug sensor already in Energy Dashboard (%s), skipping", val
                )
                return

    ent_reg = er.async_get(hass)

    # Build one grid source per tariff (flat format)
    new_sources = []
    for sensor_key, default_price in ENERGY_IMPORT_KEYS:
        entity_id = _find_entity_id(ent_reg, entry_id, sensor_key)
        if not entity_id:
            continue

        # Find matching export sensor
        export_entity = None
        for export_key, _ in ENERGY_EXPORT_KEYS:
            eid = _find_entity_id(ent_reg, entry_id, export_key)
            if eid:
                export_entity = eid
                # Only pair first import with first export, second with second
                idx_import = [k for k, _ in ENERGY_IMPORT_KEYS].index(sensor_key)
                idx_export = [k for k, _ in ENERGY_EXPORT_KEYS].index(export_key)
                if idx_import == idx_export:
                    break
                export_entity = None

        new_sources.append(
            {
                "type": "grid",
                "stat_energy_from": entity_id,
                "stat_energy_to": export_entity,
                "stat_cost": None,
                "stat_compensation": None,
                "entity_energy_price": None,
                "entity_energy_price_export": None,
                "number_energy_price": default_price,
                "number_energy_price_export": None,
                "cost_adjustment_day": 0.0,
            }
        )

    if not new_sources:
        _LOGGER.debug("No gPlug energy sensors found yet, skipping auto-config")
        return

    # Merge: keep existing sources, append gPlug sources
    merged = list(existing_sources) + new_sources

    try:
        await manager.async_update({"energy_sources": merged})
        _LOGGER.info(
            "Auto-configured Energy Dashboard with %d gPlug grid source(s): %s",
            len(new_sources),
            [s["stat_energy_from"] for s in new_sources],
        )
    except Exception as exc:  # noqa: BLE001 — private HA API, must never break setup
        _LOGGER.warning("Could not auto-configure Energy Dashboard: %s", exc)


def _find_entity_id(
    ent_reg: er.EntityRegistry,
    entry_id: str,
    sensor_key: str,
) -> str | None:
    """Find an entity_id by its unique_id pattern."""
    unique_id = f"{entry_id}_{sensor_key}"
    return ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
