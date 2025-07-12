import csv
from datetime import datetime
import pathlib

import pytest

from custom_components.cat_scale.sensor import DetectionState
from tests.test_data.utils import FakeState, FakeEvent


def readings(filename):
    base = pathlib.Path(__file__).parent / "test_data" / filename
    with base.open() as f:
        for row in csv.DictReader(f):
            yield datetime.fromisoformat(row["last_changed"]), int(row["state"])


@pytest.mark.asyncio
async def test1_csv(make_sensor):
    # Normal full cycle: cat comes, left about 30g, leave
    sensor = await make_sensor(threshold=1000, min_time=30, leave_time=600)
    for dt, value in readings("test1.csv"):
        state = FakeState(value, dt)
        event = FakeEvent(state, dt)
        sensor._handle_source_sensor_state_event(event)

        assert sensor.baseline_weight < 5000, (
            f"In this sample baseline not changed, so should stay around 5000g {value}"
        )

    assert sensor._detection_state == DetectionState.IDLE
    assert sensor.state == pytest.approx(2800, abs=100), "Cat weight should be around 3000g"
    assert sensor.waste_weight == pytest.approx(30, abs=10), "Waste weight should be around 500g"


@pytest.mark.asyncio
async def test2_csv(make_sensor):
    # A bit weird example: cat does it business, but the baseline is actually becomes lower
    sensor = await make_sensor(threshold=1000, min_time=30, leave_time=600)
    for dt, value in readings("test2.csv"):
        state = FakeState(value, dt)
        event = FakeEvent(state, dt)
        sensor._handle_source_sensor_state_event(event)

        assert sensor.baseline_weight < 5000, (
            f"In this sample baseline not changed, so should stay around 5000g {value}"
        )

    assert sensor._detection_state == DetectionState.IDLE
    assert sensor.state == pytest.approx(2800, abs=100), "Cat weight should be around 3000g"
    assert sensor.waste_weight == 0
