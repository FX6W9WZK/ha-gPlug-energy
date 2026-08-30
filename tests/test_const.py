"""Consistency tests for the gPlug Energy constant maps."""

from __future__ import annotations

from custom_components.gplug_energy.const import (
    MODEL_DETECT_PATTERNS,
    MODEL_INFO,
    SENSOR_KEY_ALIASES,
    SENSOR_SKIP_KEYS,
    SENSOR_TYPES_ENERGY,
)


def test_aliases_point_to_known_sensor_types() -> None:
    """Every alias must resolve to a defined canonical sensor."""
    for alias, canonical in SENSOR_KEY_ALIASES.items():
        assert canonical in SENSOR_TYPES_ENERGY, alias


def test_model_patterns_map_to_known_models() -> None:
    """Every detection pattern must map to a model with model info."""
    for pattern, model in MODEL_DETECT_PATTERNS.items():
        assert model in MODEL_INFO, pattern


def test_sensor_types_are_complete() -> None:
    """All sensor definitions carry the fields the platform relies on."""
    for key, config in SENSOR_TYPES_ENERGY.items():
        assert key not in SENSOR_SKIP_KEYS
        for field in ("name", "name_en", "unit", "device_class", "state_class", "icon"):
            assert field in config, f"{key} missing {field}"
