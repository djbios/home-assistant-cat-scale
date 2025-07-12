"""Configure pytest for Home Assistant tests."""

import os
import sys
from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow

# Add the custom_components directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from custom_components.cat_scale.sensor import CatLitterDetectionSensor
from custom_components.cat_scale.const import (
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield


@pytest.fixture(autouse=True)
async def setup_comp(hass):
    """Set up the component for testing."""
    # Create a mock for the async_setup_entry function
    with patch("custom_components.cat_scale.async_setup_entry", return_value=True):
        # Set up the component
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        await hass.async_block_till_done()
        yield


@pytest.fixture
def mock_flow_handler():
    """Mock the flow handler."""
    with patch("custom_components.cat_scale.config_flow.CatScaleConfigFlow") as mock_handler:
        mock_handler.return_value.async_step_user.return_value = {
            "type": data_entry_flow.FlowResultType.FORM,
            "step_id": "user",
        }
        yield mock_handler.return_value


@pytest.fixture
def make_sensor(hass):
    """
    A Pytest fixture that creates a CatLitterDetectionSensor instance.
    We pass in a "hass" fixture to mimic HA environment if needed,
    or you can just pass None if you're not using real HA objects in your tests.
    """

    async def _make(
        name="Test Cat Sensor",
        threshold=700,
        min_time=2,
        leave_time=30,
        after_cat_standard_deviation=50,
    ):
        sensor = CatLitterDetectionSensor(
            hass=hass,
            name=name,
            source_entity="sensor.test_scale",
            cat_weight_threshold=threshold,
            min_presence_time=min_time,
            leave_timeout=leave_time,
            after_cat_standard_deviation=after_cat_standard_deviation,
        )
        sensor.hass = hass
        sensor.entity_id = "sensor.test_cat"
        sensor._no_platform_reported = True
        sensor.translation_key = None
        await sensor.async_added_to_hass()
        return sensor

    return _make
