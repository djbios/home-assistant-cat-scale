import pytest
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cat_scale.sensor import CatLitterDetectionSensor

from custom_components.cat_scale.const import (
    DOMAIN,
    CONF_SOURCE_SENSOR,
    CONF_CAT_WEIGHT_THRESHOLD,
    CONF_MIN_PRESENCE_TIME,
    CONF_LEAVE_TIMEOUT,
    CONF_AFTER_CAT_STANDARD_DEVIATION,
)


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return snapshot assertion fixture with the Home Assistant extension."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_config_entry():
    """Return a mocked config entry for integration tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOURCE_SENSOR: "sensor.test_scale",
            CONF_CAT_WEIGHT_THRESHOLD: 700,
            CONF_MIN_PRESENCE_TIME: 2,
            CONF_LEAVE_TIMEOUT: 30,
            CONF_AFTER_CAT_STANDARD_DEVIATION: 50,
        },
        options={},
        unique_id="test_scale_123",
        entry_id="test_entry_id",
    )


@pytest.fixture
async def init_integration(hass, mock_config_entry):
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


# For pure logic/unit tests only (not Silver+ integration tests)
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
        sensor._attr_translation_key = None
        await sensor.async_added_to_hass()
        return sensor

    return _make
