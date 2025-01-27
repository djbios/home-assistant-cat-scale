import logging
from collections import deque
from datetime import datetime, timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

CONF_SOURCE_SENSOR = "source_sensor"
CONF_CAT_WEIGHT_THRESHOLD = "cat_weight_threshold"
CONF_MIN_PRESENCE_TIME = "min_presence_time"
CONF_LEAVE_TIMEOUT = "leave_timeout"
CONF_BASELINE_LOOKBACK = "baseline_lookback"

DEFAULT_NAME = "Cat Litter Detected Weight"
DEFAULT_CAT_WEIGHT_THRESHOLD = 1000
DEFAULT_MIN_PRESENCE_TIME = 2
DEFAULT_LEAVE_TIMEOUT = 30
DEFAULT_BASELINE_LOOKBACK = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CAT_WEIGHT_THRESHOLD, default=DEFAULT_CAT_WEIGHT_THRESHOLD): cv.positive_int,
    vol.Optional(CONF_MIN_PRESENCE_TIME, default=DEFAULT_MIN_PRESENCE_TIME): cv.positive_int,
    vol.Optional(CONF_LEAVE_TIMEOUT, default=DEFAULT_LEAVE_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_BASELINE_LOOKBACK, default=DEFAULT_BASELINE_LOOKBACK): cv.positive_int,
})


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    """Set up the cat litter detection sensor platform."""
    source_sensor = config[CONF_SOURCE_SENSOR]
    name = config[CONF_NAME]
    cat_weight_threshold = config[CONF_CAT_WEIGHT_THRESHOLD]
    min_presence_time = config[CONF_MIN_PRESENCE_TIME]
    leave_timeout = config[CONF_LEAVE_TIMEOUT]
    baseline_lookback = config[CONF_BASELINE_LOOKBACK]

    entity = CatLitterDetectionSensor(
        hass=hass,
        name=name,
        source_entity=source_sensor,
        cat_weight_threshold=cat_weight_threshold,
        min_presence_time=min_presence_time,
        leave_timeout=leave_timeout,
        baseline_lookback=baseline_lookback
    )
    async_add_entities([entity])


class DetectionState:
    """Simple state constants to keep track of the detection process."""
    IDLE = "idle"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    CAT_PRESENT = "cat_present"


class CatLitterDetectionSensor(SensorEntity):
    """
    Sensor that detects the presence of a cat on a litter scale and computes
    the cat's weight as (peak - baseline).
    """

    def __init__(
        self,
        hass,
        name,
        source_entity,
        cat_weight_threshold,
        min_presence_time,
        leave_timeout,
        baseline_lookback
    ):
        """Initialize the cat litter detection sensor."""
        self._hass = hass
        self._name = name
        self._source_entity = source_entity

        # Configurable parameters
        self._threshold = cat_weight_threshold
        self._min_presence_time = timedelta(seconds=min_presence_time)
        self._leave_timeout = timedelta(seconds=leave_timeout)
        self._baseline_lookback = timedelta(seconds=baseline_lookback)

        # For storing scale readings: we keep (timestamp, weight)
        self._recent_readings = deque()

        # Final state we report: last successfully detected cat weight
        self._state = None

        # Detection state machine
        self._detection_state = DetectionState.IDLE

        # Timestamps and values for detection logic
        self._cat_arrived_time = None
        self._cat_confirmed_time = None
        self._peak_weight = None

        # Store unsubscribe function for the event listener
        self._unsub_listener = None

    async def async_added_to_hass(self):
        """When entity is added to hass, set up state listener on the source sensor."""
        self._unsub_listener = async_track_state_change_event(
            self._hass, [self._source_entity], self._handle_source_sensor_state_event
        )

        # Initialize from current state if available
        init_state = self._hass.states.get(self._source_entity)
        if init_state and init_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
            try:
                initial_value = float(init_state.state)
                self._add_reading(initial_value)
            except ValueError:
                pass

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    @callback
    def _handle_source_sensor_state_event(self, event):
        """Handle state changes of the source sensor."""
        new_state = event.data.get("new_state")
        if not new_state:
            return

        # Skip if unknown or unavailable
        if new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
            return

        try:
            weight = float(new_state.state)
        except ValueError:
            # Not a float, ignore
            return

        # Add the reading to our records
        self._add_reading(weight)
        # Run detection logic
        self._evaluate_detection(weight)
        # Update the entity state if needed
        self.async_write_ha_state()

    def _add_reading(self, weight: float):
        """Add a new reading (weight) with current timestamp, and prune old data."""
        now = datetime.now()
        self._recent_readings.append((now, weight))

        # Prune anything older than the maximum we ever need (baseline lookback + a bit extra)
        oldest_allowed = now - (self._baseline_lookback + timedelta(minutes=1))
        while self._recent_readings and self._recent_readings[0][0] < oldest_allowed:
            self._recent_readings.popleft()

    def _evaluate_detection(self, current_weight: float):
        """Core logic to track cat presence and finalize cat weight if needed."""
        now = datetime.now()

        if self._detection_state == DetectionState.IDLE:
            # If weight is above threshold, start waiting for confirmation
            if current_weight >= self._threshold:
                self._cat_arrived_time = now
                self._detection_state = DetectionState.WAITING_FOR_CONFIRMATION

        elif self._detection_state == DetectionState.WAITING_FOR_CONFIRMATION:
            # If still above threshold and we've exceeded min_presence_time,
            # confirm cat presence
            if current_weight >= self._threshold:
                if (now - self._cat_arrived_time) >= self._min_presence_time:
                    self._cat_confirmed_time = now
                    self._peak_weight = current_weight
                    self._detection_state = DetectionState.CAT_PRESENT
            else:
                # Weight dropped below threshold before confirming
                # -> revert to idle
                self._detection_state = DetectionState.IDLE

        elif self._detection_state == DetectionState.CAT_PRESENT:
            # If cat is present, update peak if needed
            if current_weight >= self._threshold:
                self._peak_weight = max(self._peak_weight, current_weight)

                # Check if we've exceeded leave_timeout
                if (now - self._cat_confirmed_time) > self._leave_timeout:
                    # Discard event - possibly wasn't a cat
                    self._detection_state = DetectionState.IDLE
            else:
                # Cat has left: finalize cat weight
                baseline_val = self._compute_baseline(self._cat_arrived_time)
                if baseline_val is not None and self._peak_weight is not None:
                    detected_cat_weight = self._peak_weight - baseline_val
                    if detected_cat_weight < 0:
                        # If negative, might be sensor noise or scale quirk
                        _LOGGER.debug("Detected cat weight was negative. Setting to 0.")
                        detected_cat_weight = 0

                    self._state = round(detected_cat_weight, 2)
                    _LOGGER.debug("Cat event recognized: baseline=%.2f, peak=%.2f, final=%.2f",
                                  baseline_val, self._peak_weight, self._state)
                # Reset
                self._detection_state = DetectionState.IDLE

    def _compute_baseline(self, arrival_time: datetime) -> float | None:
        """
        Compute baseline as the average of readings in the period
        [arrival_time - baseline_lookback, arrival_time).
        """
        start_time = arrival_time - self._baseline_lookback
        relevant_readings = [
            w for (t, w) in self._recent_readings
            if start_time <= t < arrival_time
        ]
        if not relevant_readings:
            return None
        return sum(relevant_readings) / len(relevant_readings)

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def state(self):
        """
        Return the current cat weight detection result.
        This remains None until an event is recognized for the first time,
        and updates whenever a new cat event is finalized.
        """
        return self._state

    @property
    def icon(self):
        """Return a suitable icon."""
        return "mdi:cat"

    @property
    def unit_of_measurement(self):
        """Grams for cat weight."""
        return "g"
