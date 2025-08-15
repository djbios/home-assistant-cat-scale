from collections import deque
from datetime import timedelta, datetime
import logging
import statistics


from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_AFTER_CAT_STANDARD_DEVIATION,
    CONF_CAT_WEIGHT_THRESHOLD,
    CONF_LEAVE_TIMEOUT,
    CONF_MIN_PRESENCE_TIME,
    CONF_SOURCE_SENSOR,
    DEFAULT_AFTER_CAT_STANDARD_DEVIATION,
    DEFAULT_CAT_WEIGHT_THRESHOLD,
    DEFAULT_LEAVE_TIMEOUT,
    DEFAULT_MIN_PRESENCE_TIME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up sensor(s) from a config entry."""
    # Extract config from entry.options with fallbacks
    # this should be in your initial config flow
    source_sensor = entry.data[CONF_SOURCE_SENSOR]

    cat_weight_threshold = entry.options.get(
        CONF_CAT_WEIGHT_THRESHOLD,
        entry.data.get(CONF_CAT_WEIGHT_THRESHOLD, DEFAULT_CAT_WEIGHT_THRESHOLD),
    )
    min_presence_time = entry.options.get(
        CONF_MIN_PRESENCE_TIME,
        entry.data.get(CONF_MIN_PRESENCE_TIME, DEFAULT_MIN_PRESENCE_TIME),
    )
    leave_timeout = entry.options.get(
        CONF_LEAVE_TIMEOUT, entry.data.get(CONF_LEAVE_TIMEOUT, DEFAULT_LEAVE_TIMEOUT)
    )
    after_cat_standard_deviation = entry.options.get(
        CONF_AFTER_CAT_STANDARD_DEVIATION,
        entry.data.get(CONF_AFTER_CAT_STANDARD_DEVIATION, DEFAULT_AFTER_CAT_STANDARD_DEVIATION),
    )

    # Create the main and sub sensors as before
    main_sensor = CatLitterDetectionSensor(
        hass=hass,
        name=None,
        source_entity=source_sensor,
        cat_weight_threshold=cat_weight_threshold,
        min_presence_time=min_presence_time,
        leave_timeout=leave_timeout,
        after_cat_standard_deviation=after_cat_standard_deviation,
    )
    baseline_sensor = CatLitterBaselineSensor(main_sensor)
    detection_state_sensor = CatLitterDetectionStateSensor(main_sensor)
    waste_sensor = CatLitterWasteSensor(main_sensor)

    main_sensor.register_sub_sensor(baseline_sensor)
    main_sensor.register_sub_sensor(detection_state_sensor)
    main_sensor.register_sub_sensor(waste_sensor)

    async_add_entities([main_sensor, baseline_sensor, detection_state_sensor, waste_sensor])


class DetectionState:
    """Simple state constants to keep track of the detection process."""

    IDLE = "idle"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    CAT_PRESENT = "cat_present"
    AFTER_CAT = "after_cat"


class CatLitterDetectionSensor(RestoreSensor):
    """Main sensor that detects the presence of a cat on a litter scale
    and computes the cat's weight as (peak_weight - baseline_weight).

    Also tracks 'waste weight' by comparing new baseline after cat leaves
    to the baseline before the cat arrived.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_translation_key = "cat_weight"

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        source_entity: str,
        cat_weight_threshold: int,
        min_presence_time: int,
        leave_timeout: int,
        after_cat_standard_deviation: int,
    ) -> None:
        """Initialize the cat litter detection sensor."""
        self._hass = hass
        self._name = name
        self._source_entity = source_entity
        self._attr_unique_id = f"{source_entity}_cat_detection"
        self.device_entry = async_entity_id_to_device(hass, source_entity)

        # Configurable parameters
        self._threshold = cat_weight_threshold
        self._min_presence_time = timedelta(seconds=min_presence_time)
        self._leave_timeout = timedelta(seconds=leave_timeout)
        self._after_cat_standard_deviation = after_cat_standard_deviation

        # Keep recent readings, mostly for debugging or if you need them later
        # Format: deque of (timestamp, weight)
        self._recent_readings: deque[tuple[datetime, float]] = deque()

        # Max pollingrate of hx711 is 10hz, with an hour of cat presence
        self._recent_presence_readings: deque[float] = deque(maxlen=3600 * 10)

        # Final reported state: last successfully detected cat weight
        self._state = None

        # Detection state machine
        self._detection_state = DetectionState.IDLE

        # Timestamps and values for detection logic
        self._cat_arrived_time = None
        self._cat_confirmed_time = None

        # Baseline weight. Updated when returning to IDLE or first above threshold, etc.
        self._baseline_weight = None
        self._waste_weight = 0.0

        # Store unsubscribe function for the event listener
        self._unsub_listener = None

        # Sub-sensors for baseline, detection state, waste, etc.
        self._sub_sensors = []

    def register_sub_sensor(self, sensor_entity: SensorEntity):
        """Register a sub-sensor so we can update it after our own state changes."""
        self._sub_sensors.append(sensor_entity)

    def _update_sub_sensors(self):
        """Trigger update of all sub-sensors after our state changes."""
        for sensor in self._sub_sensors:
            sensor.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass, set up state listener on the source sensor."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Adding %s to hass. Subscribing to source sensor: %s",
            self._name,
            self._source_entity,
        )

        # Restore previous native value if available
        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            try:
                self._state = float(last_sensor_data.native_value)
                _LOGGER.debug("%s: Restored native_value to %.2f", self._name, self._state)
            except (ValueError, TypeError):
                _LOGGER.debug(
                    "%s: Could not restore native_value from %s",
                    self._name,
                    last_sensor_data.native_value,
                )

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
            _LOGGER.debug(
                "%s: State is unknown/unavailable (%s) Ignoring",
                self._name,
                new_state.state,
            )
            return

        try:
            weight = float(new_state.state)
        except ValueError:
            _LOGGER.debug("%s: State (%s) is non-numeric. Ignoring", self._name, new_state.state)
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
        # Also update sub-sensors
        self._update_sub_sensors()

    def _add_reading(self, weight: float, reading_time) -> None:
        """Add a new reading (weight) with a timestamp, and prune old data."""
        _LOGGER.debug(
            "%s: Adding reading -> weight=%.2f, time=%s",
            self._name,
            weight,
            reading_time,
        )
        self._recent_readings.append((reading_time, weight))
        max_keep = timedelta(minutes=5)
        oldest_allowed = reading_time - max_keep

        while self._recent_readings and self._recent_readings[0][0] < oldest_allowed:
            popped = self._recent_readings.popleft()
            _LOGGER.debug("%s: Pruning old reading -> %s", self._name, popped)

    def _evaluate_detection(self, current_weight: float, event_time) -> None:
        """Core logic to track cat presence and finalize cat weight if needed."""
        if self._baseline_weight is None:
            # On very first run, set an initial baseline
            self._baseline_weight = current_weight
            _LOGGER.debug(
                "%s: First reading seen. Setting baseline to %.2f",
                self._name,
                self._baseline_weight,
            )
            return

        # Threshold is baseline + cat_weight_threshold
        trigger_level = self._baseline_weight + self._threshold
        _LOGGER.debug(
            "%s: Evaluate detection. State=%s, curr=%.2f, baseline=%.2f, threshold=%.2f",
            self._name,
            self._detection_state,
            current_weight,
            self._baseline_weight,
            trigger_level,
        )

        if self._detection_state == DetectionState.IDLE:
            # If weight is above (baseline + threshold), start waiting
            if current_weight >= trigger_level:
                self._cat_arrived_time = event_time
                self._detection_state = DetectionState.WAITING_FOR_CONFIRMATION
                _LOGGER.debug(
                    "%s: -> WAITING_FOR_CONFIRMATION at %s. baseline=%.2f",
                    self._name,
                    event_time,
                    self._baseline_weight,
                )
                if len(self._recent_presence_readings) > 0:
                    _LOGGER.error(
                        "Presence readings were not cleared as expected. This may indicate a bug in the cat scale integration. Please report this issue at https://github.com/djbios/home-assistant-cat-scale/issues and include relevant logs."
                    )
                    self._recent_presence_readings.clear()
                self._recent_presence_readings.append(current_weight)
            elif self._recent_readings:
                # If presumably empty, we can adjust the baseline slowly or with a simple average
                median = statistics.median(r[1] for r in self._recent_readings)
                self._baseline_weight = median
                _LOGGER.debug(
                    "%s: Updated baseline to average of recent: %.2f",
                    self._name,
                    self._baseline_weight,
                )

        elif self._detection_state == DetectionState.WAITING_FOR_CONFIRMATION:
            if current_weight >= trigger_level:
                self._recent_presence_readings.append(current_weight)
                # If we have stayed above threshold long enough, confirm cat
                if (event_time - self._cat_arrived_time) >= self._min_presence_time:
                    self._cat_confirmed_time = event_time
                    self._detection_state = DetectionState.CAT_PRESENT
                    _LOGGER.debug(
                        "%s: Cat presence confirmed. time=%s",
                        self._name,
                        event_time,
                    )
            else:
                # Weight fell back below threshold, so reset
                _LOGGER.debug(
                    "%s: Weight dropped below trigger (%.2f < %.2f) before confirmation. Reset to IDLE. "
                    "baseline -> %.2f",
                    self._name,
                    current_weight,
                    trigger_level,
                    current_weight,
                )
                self._detection_state = DetectionState.IDLE
                self._baseline_weight = current_weight
                self._recent_readings.clear()
                self._recent_presence_readings.clear()

        elif self._detection_state == DetectionState.CAT_PRESENT:
            if current_weight >= trigger_level:
                # Cat still present: add weight
                self._recent_presence_readings.append(current_weight)

                # Check if we've exceeded leave_timeout
                if (event_time - self._cat_confirmed_time) > self._leave_timeout:
                    _LOGGER.debug(
                        "%s: Cat presence took too long. Discarding event. baseline -> %.2f, clearing readings",
                        self._name,
                        current_weight,
                    )
                    self._detection_state = DetectionState.IDLE
                    self._baseline_weight = current_weight
                    self._recent_readings.clear()
                    self._recent_presence_readings.clear()
            else:
                # Cat left: finalize cat weight
                if self._recent_presence_readings:
                    median_weight = statistics.median(self._recent_presence_readings)
                else:
                    median_weight = current_weight  # fallback

                detected_cat_weight = median_weight - self._baseline_weight
                if detected_cat_weight < 0:
                    _LOGGER.debug(
                        "%s: Negative cat weight (%.2f). Forcing to 0. Possibly sensor drift/noise",
                        self._name,
                        detected_cat_weight,
                    )
                    detected_cat_weight = 0

                self._state = round(detected_cat_weight, 2)

                _LOGGER.debug(
                    "%s: Cat event recognized. baseline=%.2f, median=%.2f, final=%.2f",
                    self._name,
                    self._baseline_weight,
                    median_weight,
                    self._state,
                )

                self._detection_state = DetectionState.AFTER_CAT
                self._recent_readings.clear()
                self._recent_presence_readings.clear()
                self._add_reading(current_weight, event_time)

        elif self._detection_state == DetectionState.AFTER_CAT:
            self._add_reading(current_weight, event_time)
            stand_dev = statistics.stdev(r[1] for r in self._recent_readings)

            if (
                stand_dev <= self._after_cat_standard_deviation and len(self._recent_readings) >= 5
            ):  # TODO magic numbers
                self._detection_state = DetectionState.IDLE
                self._waste_weight = max(current_weight - self._baseline_weight, 0)
                self._baseline_weight = current_weight
                self._recent_readings.clear()
                _LOGGER.debug(
                    "%s: Finished cat event. baseline=%.2f, waste=%.2f",
                    self._name,
                    current_weight,
                    self._waste_weight,
                )

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        # Using native value and native unit of measurement, allows you to change units
        # in Lovelace and HA will automatically calculate the correct value.
        return float(self._state) if self._state is not None else None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of mass."""
        return UnitOfMass.GRAMS

    @property
    def state_class(self) -> str | None:
        """Return state class.

        This value is set to MEASUREMENT so it persists value over longer
        time.
        """
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes
        return SensorStateClass.MEASUREMENT

    @property
    def icon(self):
        """Return a suitable icon for the main sensor."""
        return "mdi:cat"

    @property
    def baseline_weight(self) -> float | None:
        """Expose the baseline weight for sub-sensors to use."""
        return self._baseline_weight

    @property
    def detection_state(self) -> str:
        """Expose the internal detection state for sub-sensors to use."""
        return self._detection_state

    @property
    def waste_weight(self) -> float:
        """Return the difference in baseline before cat arrived vs. after cat left.

        A positive value indicates more mass in the box (i.e. "waste").
        Negative might indicate litter was removed or scattered.
        """
        return self._waste_weight

    @property
    def should_poll(self) -> bool:
        """Event-driven; no polling."""
        return False


class CatLitterBaselineSensor(SensorEntity):
    """A secondary sensor entity that reports the 'baseline weight'.

    This sensor gets its value from the main cat-litter detection sensor.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_translation_key = "baseline"

    def __init__(self, main_sensor: CatLitterDetectionSensor) -> None:
        """Initialize the baseline sensor."""
        self._main_sensor = main_sensor
        self._attr_unique_id = f"{main_sensor.unique_id}_baseline_sensor"
        self.device_entry = main_sensor.device_entry

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        if self._main_sensor.baseline_weight is None:
            return 0
        return round(self._main_sensor.baseline_weight, 2)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of mass."""
        return UnitOfMass.GRAMS

    @property
    def icon(self):
        """Return an icon for baseline weight."""
        return "mdi:scale-balance"

    @property
    def should_poll(self) -> bool:
        """Updates are pushed by the main sensor, so no polling."""
        return False


class CatLitterDetectionStateSensor(SensorEntity):
    """A secondary sensor entity that shows the detection state."""

    _attr_has_entity_name = True
    _attr_translation_key = "detection_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        DetectionState.IDLE,
        DetectionState.WAITING_FOR_CONFIRMATION,
        DetectionState.CAT_PRESENT,
        DetectionState.AFTER_CAT,
    ]

    def __init__(self, main_sensor: CatLitterDetectionSensor) -> None:
        """Initialize the detection-state sensor."""
        self._main_sensor = main_sensor
        self._attr_unique_id = f"{main_sensor.unique_id}_cat_detection_state"
        self.device_entry = main_sensor.device_entry

    @property
    def native_value(self) -> str:
        """Return the internal detection state from the main sensor."""
        return self._main_sensor.detection_state

    @property
    def icon(self):
        """Return an icon for the detection state sensor."""
        return "mdi:radar"

    @property
    def should_poll(self) -> bool:
        """No need to poll—this updates when the main sensor updates."""
        return False


class CatLitterWasteSensor(SensorEntity):
    """A secondary sensor entity that shows the 'waste weight'.

    This is the difference in the litter box baseline before vs. after cat visits.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_translation_key = "waste_weight"

    def __init__(self, main_sensor: CatLitterDetectionSensor) -> None:
        """Initialize the waste sensor."""
        self._main_sensor = main_sensor
        self._attr_unique_id = f"{main_sensor.unique_id}_waste"
        self.device_entry = main_sensor.device_entry

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        if self._main_sensor.waste_weight is None:
            return 0
        return round(self._main_sensor.waste_weight, 2)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of mass."""
        return UnitOfMass.GRAMS

    @property
    def icon(self):
        return "mdi:delete-variant"

    @property
    def should_poll(self) -> bool:
        """No polling; event-driven from main sensor."""
        return False
