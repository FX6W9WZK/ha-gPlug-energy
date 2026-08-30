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


def test_detect_obis_key_maps_fragments() -> None:
    """Keys embedding OBIS codes map to canonical sensor keys."""
    from custom_components.gplug_energy.const import detect_obis_key

    assert detect_obis_key("Bezug_1.8.0") == "Ei_1.8"
    assert detect_obis_key("1-0:1.8.1") == "Ei1_1.8.1"
    assert detect_obis_key("zaehler_1.8.2") == "Ei2_1.8.2"
    assert detect_obis_key("Einspeisung_2.8") == "Eo_2.8"
    assert detect_obis_key("ruecklauf_2.8.1") == "Eo1_2.8.1"
    assert detect_obis_key("export_t2_2.8.2") == "Eo2_2.8.2"
    assert detect_obis_key("Leistung_1.7.0") == "Pi_1.7"
    assert detect_obis_key("abgabe_2.7") == "Po_2.7"
    assert detect_obis_key("spannung_32.7") == "V1_32.7"
    assert detect_obis_key("u2_52.7.0") == "V2_52.7"
    assert detect_obis_key("u3_72.7") == "V3_72.7"
    assert detect_obis_key("strom_31.7") == "I1_31.7"
    assert detect_obis_key("i2_51.7") == "I2_51.7"
    assert detect_obis_key("i3_71.7.0") == "I3_71.7"


def test_detect_obis_key_negative_cases() -> None:
    """Keys without OBIS fragments stay unmapped."""
    from custom_components.gplug_energy.const import detect_obis_key

    assert detect_obis_key("Custom_value") is None
    assert detect_obis_key("E_in") is None
    assert detect_obis_key("Meter_18") is None
    assert detect_obis_key("v11.8.9") is None
    assert detect_obis_key("21.8") is None
