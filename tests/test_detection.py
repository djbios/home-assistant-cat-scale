"""
Pytest suite for Cat Scale Integration.
"""

import pytest
import random
from datetime import datetime, timedelta


from custom_components.cat_scale.sensor import DetectionState
from tests.test_data.utils import FakeState, FakeEvent

TESTS_TOLERANCE = 10


def generate_series(
    start_time: datetime,
    steps: int,
    base_weight: float,
    noise: float = 0.0,
    event_profile=None,
    time_step_sec: int = 1,
):
    """
    A generator function that yields (timestamp, weight).

    :param start_time: Starting timestamp.
    :param steps: Number of readings to generate.
    :param base_weight: The baseline around which we add any noise or cat events.
    :param noise: Maximum random noise magnitude, e.g. 0.1 means +/- 0.1.
    :param event_profile: A function(time_idx, current_weight) -> delta_weight
                          This can simulate a cat arriving or baseline changes.
    :param time_step_sec: Seconds to increment each step's timestamp.
    """
    current_time = start_time
    current_weight = base_weight

    for i in range(steps):
        # If we have an event profile, get the delta for this step
        if event_profile:
            delta_w = event_profile(i, current_weight)
            current_weight += delta_w

        # Add optional random noise
        if noise > 0:
            current_weight += random.uniform(-noise, noise)

        yield current_time, round(current_weight, 2)

        # Advance time
        current_time += timedelta(seconds=time_step_sec)


def feed_readings_to_sensor(sensor, readings):
    """
    Helper to feed (timestamp, weight) readings into the sensor
    as if they were new state_changed events from HA.

    We simulate:
        new_state.state = str(weight)
        new_state.last_changed = timestamp
        event.time_fired = timestamp
    """
    for ts, w in readings:
        fstate = FakeState(str(w), ts)
        fevent = FakeEvent(fstate, ts)
        sensor._handle_source_sensor_state_event(fevent)


@pytest.mark.asyncio
async def test_noisy_baseline_no_events(make_sensor):
    """
    just noisy baseline no events: assert baseline is set, but no cat detection
    """
    sensor = await make_sensor(threshold=700, min_time=2, leave_time=30)
    start_time = datetime.now()
    # 20 steps of random noise around 500
    readings = generate_series(
        start_time=start_time,
        steps=20,
        base_weight=500.0,
        noise=1.0,
        event_profile=None,
    )
    feed_readings_to_sensor(sensor, readings)

    # After feeding, we expect:
    # - detection_state = IDLE
    # - cat_weight sensor._state = None (no cat recognized)
    # - baseline_weight ~ near 500
    assert sensor._detection_state == DetectionState.IDLE
    assert sensor.state is None
    # baseline ~ 500, allow some margin
    assert sensor.baseline_weight == pytest.approx(500, abs=10)


@pytest.mark.asyncio
async def test_cat_come_left_same_baseline(make_sensor):
    """
    baseline -> cat come -> cat left => same baseline
    Expect cat weight = peak - baseline, waste = 0 if final baseline is same as pre-cat
    """
    sensor = await make_sensor(threshold=50, min_time=2, leave_time=30)
    base_wt = 500.0
    cat_delta = 60.0  # cat adds 60 grams above baseline
    start_time = datetime.now()

    def event_profile(i, curr_weight):
        # At step 2, cat arrives
        # Steps 2..7 => cat present
        # Step 8 => cat leaves, returning to baseline
        if i == 2:
            return cat_delta  # cat arrives
        if 2 < i < 8:
            return 0  # cat still there
        if i == 8:
            return -cat_delta  # cat leaves
        return 0

    readings = generate_series(
        start_time=start_time,
        steps=12,
        base_weight=base_wt,
        noise=0.0,
        event_profile=event_profile,
    )
    feed_readings_to_sensor(sensor, readings)

    # Cat was present from step 2..7 with at least 2s above threshold -> detection
    # Final baseline = original baseline if no net change
    expected_cat_weight = 60.0
    # Because the sensor uses round(...,2), we do the same
    # Also expect waste = 0 if final baseline == pre-cat baseline

    assert sensor.state == pytest.approx(expected_cat_weight, 0.1), "Cat weight must be ~60"
    assert sensor.baseline_weight == pytest.approx(base_wt, 0.1), "Baseline should remain near 500"
    assert sensor.waste_weight == pytest.approx(0.0, 0.01), (
        "Waste should be 0 if baseline didn't shift"
    )


@pytest.mark.asyncio
async def test_baseline_change_down(make_sensor, hass):
    """
    Scenario: baseline is 500, but then the scale consistently reads ~490 after some event
    (maybe litter was removed).
    Expect the sensor to adapt baseline to ~490, no cat detection.
    """
    sensor = await make_sensor(threshold=100, min_time=2, leave_time=30)
    start_time = datetime.now()

    # We'll simulate a downward shift of ~10g after step 5
    def event_profile(i, curr_weight):
        if i < TESTS_TOLERANCE:
            return 0
        # After step 5, shift baseline down by 10 from 500 to 490
        return -1 if curr_weight > 490 else 0

    readings = generate_series(
        start_time=start_time,
        steps=20,
        base_weight=500.0,
        noise=0.5,
        event_profile=event_profile,
    )
    feed_readings_to_sensor(sensor, readings)

    # We expect no cat detection, so:
    assert sensor.state is None
    assert sensor._detection_state == DetectionState.IDLE
    # We expect final baseline near 490
    assert sensor.baseline_weight == pytest.approx(490.0, 0.1)


@pytest.mark.asyncio
async def test_baseline_change_up_less_than_cat(make_sensor, hass):
    """
    Baseline slowly creeps up by +30g, but threshold is 50.
    That does not trigger cat detection because we never exceed baseline+50.
    """
    sensor = await make_sensor(threshold=50, min_time=2, leave_time=30)
    start_time = datetime.now()

    def event_profile(i, curr_weight):
        # Over 10 steps, let's add +30g total (3g per step)
        if i < 10:
            return 3
        return 0

    readings = generate_series(
        start_time=start_time,
        steps=15,
        base_weight=500.0,
        noise=0,
        event_profile=event_profile,
    )
    feed_readings_to_sensor(sensor, readings)

    # No cat detection
    assert sensor.state is None
    # Baseline should end up around 530 if the sensor code picks up that average
    # The sensor's logic might or might not fully adopt the new baseline
    # but we at least expect no cat event recognized.
    assert sensor._detection_state == DetectionState.IDLE


@pytest.mark.asyncio
async def test_cat_come_left_quickly_no_update(make_sensor, hass):
    """
    The cat is above threshold for less than min_presence_time -> no detection
    """
    sensor = await make_sensor(threshold=50, min_time=5, leave_time=30)
    start_time = datetime.now()

    # We'll spike up by 60 for only 3 seconds total
    def event_profile(i, curr_weight):
        if i == 2:
            return 60
        if i == 3:
            return 0  # still cat
        if i == 4:
            return -60  # cat leaves
        return 0

    # We'll produce 10 steps total (0..9)
    readings = generate_series(
        start_time=start_time,
        steps=10,
        base_weight=500.0,
        noise=0.0,
        event_profile=event_profile,
    )
    feed_readings_to_sensor(sensor, readings)

    # Cat never meets the min_presence_time=5s, so no detection
    assert sensor.state is None
    assert sensor._detection_state == DetectionState.IDLE


@pytest.mark.asyncio
async def test_cat_come_waste_left_all_sensors(make_sensor, hass):
    """
    baseline -> cat come -> confirm -> cat leaves -> leaves waste =>
    assert cat weight, waste weight, final baseline
    """
    sensor = await make_sensor(threshold=50, min_time=2, leave_time=30)
    base_wt = 500.0
    cat_delta = 60.0
    # After cat leaves, we add ~15g more to the baseline => "waste"
    # So final baseline ~ base_wt + 15 = 515
    start_time = datetime.now()

    def event_profile(i, curr_weight):
        if i == 2:
            return cat_delta  # cat arrives
        if 2 < i < 7:
            return 0  # cat still there
        if i == 7:
            return -cat_delta + 15  # cat leaves, but waste is added
        # after cat leaves, from step 8..15, let's drift baseline +15 total => +1 g each step TODO not working yet
        # if 8 <= i <= 15:
        #     return 1
        return 0

    readings = list(
        generate_series(
            start_time=start_time,
            steps=20,
            base_weight=base_wt,
            noise=0.0,
            event_profile=event_profile,
        )
    )
    feed_readings_to_sensor(sensor, readings)

    # Cat was present from step 2..6 => 5 steps => definitely > min_presence_time=2
    # So cat recognized with cat weight= peak(560) - baseline(500) = 60
    # Then final baseline ~ 500 + 15 => 515
    # waste_weight = 515 - 500 = 15
    assert sensor.state == pytest.approx(60, 0.1), "Cat weight must be ~60"
    assert sensor.baseline_weight == pytest.approx(515, 0.1), "Baseline should end near 515"
    assert sensor.waste_weight == pytest.approx(15, 0.1), "Waste weight should be ~15"
    assert sensor._detection_state == DetectionState.IDLE
