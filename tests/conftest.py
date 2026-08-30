"""Shared fixtures for the gPlug Energy test suite."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components from this repository."""
    yield


@pytest.fixture
def mock_setup_entry():
    """Prevent the integration from actually being set up."""
    with patch(
        "custom_components.gplug_energy.async_setup_entry", return_value=True
    ) as mock:
        yield mock
