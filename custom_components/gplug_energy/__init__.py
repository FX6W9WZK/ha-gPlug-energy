"""
gPlug Energy – HACS Integration for gPlug Smart Meter Sensors.

Reads energy data from all gPlug devices (gPlugD, gPlugD-E, gPlugK, gPlugM)
via MQTT and creates properly configured sensor entities for the
Home Assistant Energy Dashboard. Device model is auto-detected from the
MQTT topic name.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_AUTO_CARD,
    CONF_AUTO_ENERGY,
    DEFAULT_AUTO_CARD,
    DEFAULT_AUTO_ENERGY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

_MANIFEST_PATH = Path(__file__).parent / "manifest.json"
_VERSION = json.loads(_MANIFEST_PATH.read_text()).get("version", "0.0.0")

CARD_STATIC_URL = "/gplug_energy/gplug-energy-card.js"
CARD_URL = f"{CARD_STATIC_URL}?v={_VERSION}"
CARD_PATH = Path(__file__).parent / "www" / "gplug-energy-card.js"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up gPlug Energy from a config entry."""
    # Check options (options override data)
    auto_card = entry.options.get(
        CONF_AUTO_CARD, entry.data.get(CONF_AUTO_CARD, DEFAULT_AUTO_CARD)
    )
    auto_energy = entry.options.get(
        CONF_AUTO_ENERGY, entry.data.get(CONF_AUTO_ENERGY, DEFAULT_AUTO_ENERGY)
    )

    # Register custom Lovelace card (if enabled)
    if auto_card:
        await _register_card(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Auto-configure Energy Dashboard (if enabled)
    if auto_energy:

        async def _delayed_energy_config(_now=None):
            from .energy import async_configure_energy_dashboard

            await async_configure_energy_dashboard(hass, entry.entry_id)

        async_call_later(hass, 30, _delayed_energy_config)

    _LOGGER.info(
        "gPlug Energy loaded (topic=%s, auto_energy=%s, auto_card=%s)",
        entry.data.get("mqtt_topic", "n/a"),
        auto_energy,
        auto_card,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _register_card(hass: HomeAssistant) -> None:
    """Register the gPlug Energy Lovelace card as a frontend resource."""
    # Step 1: Serve the JS file via HTTP (static path without query string)
    try:
        if hasattr(hass.http, "async_register_static_paths"):
            from homeassistant.components.http import StaticPathConfig

            await hass.http.async_register_static_paths(
                [StaticPathConfig(CARD_STATIC_URL, str(CARD_PATH), True)]
            )
        else:
            hass.http.register_static_path(
                CARD_STATIC_URL, str(CARD_PATH), cache_headers=True
            )
        _LOGGER.info("gPlug card served at %s", CARD_STATIC_URL)
    except Exception as exc:  # noqa: BLE001 — private HA API, must never break setup
        _LOGGER.warning("Could not serve card file: %s", exc)
        return

    # Step 2: Register in Lovelace resources with version for cache busting
    await _add_lovelace_resource(hass, CARD_URL)


async def _add_lovelace_resource(hass: HomeAssistant, url: str) -> None:
    """Add or update a JS module in Lovelace resources via HA API."""
    try:
        ll_data = hass.data.get("lovelace")
        if ll_data is None or not hasattr(ll_data, "resources"):
            _LOGGER.debug(
                "Lovelace resources not available (YAML mode?). Add manually: %s",
                url,
            )
            return

        resources = ll_data.resources
        if not resources.loaded:
            return

        for item in resources.async_items():
            existing_url = item.get("url", "")
            if CARD_STATIC_URL in existing_url:
                if existing_url == url:
                    _LOGGER.debug("gPlug card already registered with current version")
                    return
                await resources.async_update_item(item["id"], {"url": url})
                _LOGGER.info("gPlug card updated to %s", url)
                return

        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.info("gPlug card registered in lovelace_resources: %s", url)

    except Exception:  # noqa: BLE001 — private HA API, must never break setup
        _LOGGER.debug(
            "Could not auto-register Lovelace resource. "
            "Add manually: Settings > Dashboards > Resources > "
            "Add Resource > URL: %s > Type: JavaScript Module",
            url,
        )
