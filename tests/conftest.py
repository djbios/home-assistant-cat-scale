import pytest

from custom_components.cat_scale.sensor import CatLitterDetectionSensor


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
