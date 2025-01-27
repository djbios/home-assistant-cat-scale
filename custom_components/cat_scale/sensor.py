import logging
from collections import deque
from datetime import timedelta

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

# We'll remove baseline_lookback since we're no longer averaging historical data.
DEFAULT_NAME = "Cat Litter Detected Weight"
DEFAULT_CAT_WEIGHT_THRESHOLD = 700
DEFAULT_MIN_PRESENCE_TIME = 2
DEFAULT_LEAVE_TIMEOUT = 30

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CAT_WEIGHT_THRESHOLD, default=DEFAULT_CAT_WEIGHT_THRESHOLD): cv.positive_int,
    vol.Optional(CONF_MIN_PRESENCE_TIME, default=DEFAULT_MIN_PRESENCE_TIME): cv.positive_int,
    vol.Optional(CONF_LEAVE_TIMEOUT, default=DEFAULT_LEAVE_TIMEOUT): cv.positive_int,
})


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    """Set up the cat litter detection sensor platform."""
    source_sensor = config[CONF_SOURCE_SENSOR]
    name = config[CONF_NAME]
    cat_weight_threshold = config[CONF_CAT_WEIGHT_THRESHOLD]
    min_presence_time = config[CONF_MIN_PRESENCE_TIME]
    leave_timeout = config[CONF_LEAVE_TIMEOUT]

    entity = CatLitterDetectionSensor(
        hass=hass,
        name=name,
        source_entity=source_sensor,
        cat_weight_threshold=cat_weight_threshold,
        min_presence_time=min_presence_time,
        leave_timeout=leave_timeout
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
    the cat's weight as (peak_weight - baseline_weight).
    """

    def __init__(
        self,
        hass,
        name,
        source_entity,
        cat_weight_threshold,
        min_presence_time,
        leave_timeout
    ):
        """Initialize the cat litter detection sensor."""
        self._hass = hass
        self._name = name
        self._source_entity = source_entity

        # Configurable parameters
        self._threshold = cat_weight_threshold
        self._min_presence_time = timedelta(seconds=min_presence_time)
        self._leave_timeout = timedelta(seconds=leave_timeout)

        # Keep recent readings, mostly for debugging or if you need them later
        # Format: deque of (timestamp, weight)
        self._recent_readings = deque()

        # Final reported state: last successfully detected cat weight
        self._state = None

        # Detection state machine
        self._detection_state = DetectionState.IDLE

        # Timestamps and values for detection logic
        self._cat_arrived_time = None
        self._cat_confirmed_time = None
        self._peak_weight = None

        # The main difference:
        # We store the "baseline_weight" from the first reading above threshold
        # (and update it whenever we return to IDLE).
        self._baseline_weight = None

        # Store unsubscribe function for the event listener
        self._unsub_listener = None

    async def async_added_to_hass(self):
        """When entity is added to hass, set up state listener on the source sensor."""
        _LOGGER.debug("Adding %s to hass. Subscribing to source sensor: %s", self._name, self._source_entity)

        self._unsub_listener = async_track_state_change_event(
            self._hass, [self._source_entity], self._handle_source_sensor_state_event
        )

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        _LOGGER.debug("Removing %s from hass and unsubscribing", self._name)
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    @callback
    def _handle_source_sensor_state_event(self, event):
        """Handle state changes of the source sensor."""
        new_state = event.data.get("new_state")
        if not new_state:
            _LOGGER.debug("%s: No new_state in event", self._name)
            return

        if new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
            _LOGGER.debug("%s: State is unknown/unavailable (%s). Ignoring.", self._name, new_state.state)
            return

        try:
            weight = float(new_state.state)
        except ValueError:
            _LOGGER.debug("%s: State (%s) is non-numeric. Ignoring.", self._name, new_state.state)
            return

        # Use last_changed if available; else fallback to event.time_fired
        event_time = new_state.last_changed or event.time_fired

        _LOGGER.debug("%s: New weight=%.2f at %s", self._name, weight, event_time)

        # Add the reading to our records
        self._add_reading(weight, event_time)
        # Run detection logic
        self._evaluate_detection(weight, event_time)
        # Update the entity state if needed
        self.async_write_ha_state()

    def _add_reading(self, weight: float, reading_time) -> None:
        """Add a new reading (weight) with a timestamp, and prune old data."""
        _LOGGER.debug("%s: Adding reading -> weight=%.2f, time=%s", self._name, weight, reading_time)
        self._recent_readings.append((reading_time, weight))

        # For example, keep up to 5 minutes of data for debugging
        max_keep = timedelta(minutes=2)
        oldest_allowed = reading_time - max_keep

        while self._recent_readings and self._recent_readings[0][0] < oldest_allowed:
            popped = self._recent_readings.popleft()
            _LOGGER.debug("%s: Pruning old reading -> %s", self._name, popped)

    def _evaluate_detection(self, current_weight: float, event_time) -> None:
        """Core logic to track cat presence and finalize cat weight if needed."""
        _LOGGER.debug(
            "%s: Evaluating detection. State=%s, current_weight=%.2f, baseline=%.2f",
            self._name, self._detection_state, current_weight, self._baseline_weight
        )

        if self._baseline_weight is None:
            self._baseline_weight = current_weight
            _LOGGER.debug(
                "%s: First reading above threshold. Setting baseline to %.2f",
                self._name, self._baseline_weight
            )
            return

        if self._detection_state == DetectionState.IDLE:
            # If weight is above threshold, start waiting for confirmation
            if current_weight >= self._threshold + self._baseline_weight:
                self._cat_arrived_time = event_time
                self._detection_state = DetectionState.WAITING_FOR_CONFIRMATION
                _LOGGER.debug(
                    "%s: Transition to WAITING_FOR_CONFIRMATION at %s. baseline_weight=%.2f",
                    self._name, event_time, self._baseline_weight
                )
            else:
                # Update baseline if needed
                self._baseline_weight = sum([r[1] for r in self._recent_readings]) / len(self._recent_readings)

        elif self._detection_state == DetectionState.WAITING_FOR_CONFIRMATION:
            # Check if weight is still above threshold
            if current_weight >= self._threshold:
                if (event_time - self._cat_arrived_time) >= self._min_presence_time:
                    # Confirm cat presence
                    self._cat_confirmed_time = event_time
                    self._peak_weight = current_weight
                    self._detection_state = DetectionState.CAT_PRESENT
                    _LOGGER.debug(
                        "%s: Cat presence confirmed. peak_weight=%.2f, time=%s",
                        self._name, self._peak_weight, event_time
                    )
            else:
                # Weight dropped below threshold before confirmation:
                # revert to IDLE and update baseline
                _LOGGER.debug(
                    "%s: Weight dropped below threshold (%.2f < %.2f) before confirmation. "
                    "Reset to IDLE, baseline updated to %.2f.",
                    self._name, current_weight, self._threshold, current_weight
                )
                self._detection_state = DetectionState.IDLE
                self._baseline_weight = current_weight

        elif self._detection_state == DetectionState.CAT_PRESENT:
            if current_weight >= self._threshold + self._baseline_weight:
                # Cat still present: update peak if needed
                if current_weight > self._peak_weight:
                    _LOGGER.debug(
                        "%s: Updating peak weight from %.2f to %.2f",
                        self._name, self._peak_weight, current_weight
                    )
                self._peak_weight = max(self._peak_weight, current_weight)

                # Check if we've exceeded leave_timeout
                if (event_time - self._cat_confirmed_time) > self._leave_timeout:
                    _LOGGER.debug(
                        "%s: Cat presence took too long (%s). Discarding event, baseline updated to %.2f",
                        self._name, self._leave_timeout, current_weight
                    )
                    self._detection_state = DetectionState.IDLE
                    # Update baseline here as well, since we discard
                    self._baseline_weight = current_weight
                    self._recent_readings.clear()
            else:
                # Cat left: finalize cat weight
                detected_cat_weight = self._peak_weight - self._baseline_weight
                if detected_cat_weight < 0:
                    _LOGGER.debug(
                        "%s: Negative cat weight (%.2f). Forcing to 0. Possibly sensor drift/noise.",
                        self._name, detected_cat_weight
                    )
                    detected_cat_weight = 0

                self._state = round(detected_cat_weight, 2)
                _LOGGER.debug(
                    "%s: Cat event recognized. baseline=%.2f, peak=%.2f, final=%.2f",
                    self._name, self._baseline_weight, self._peak_weight, self._state
                )

                # Return to IDLE, update baseline to the new reading
                self._detection_state = DetectionState.IDLE
                self._baseline_weight = current_weight
                _LOGGER.debug(
                    "%s: Transitioning back to IDLE after cat left. New baseline=%.2f",
                    self._name, self._baseline_weight
                )
                self._recent_readings.clear()

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
