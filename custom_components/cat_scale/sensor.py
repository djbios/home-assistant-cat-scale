from datetime import timedelta
import logging


from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

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
    DOMAIN,
)
from .states import LitterboxStateMachine, IdleState, LitterboxContext, Reading

logger = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up sensor(s) from a config entry."""
    # Extract config from entry.options with fallbacks
    source_sensor = entry.data[CONF_SOURCE_SENSOR]  # this should be in your initial config flow

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
    main_sensor = CatWeightMainSensor(
        hass=hass,
        name=entry.title,
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


class CatWeightMainSensor(RestoreSensor):
    """Main sensor that detects the presence of a cat on a litter scale
    and computes the cat's weight as (peak_weight - baseline_weight).

    Also tracks 'waste weight' by comparing new baseline after cat leaves
    to the baseline before the cat arrived.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_translation_key = "cat_weight"

    icon = "mdi:cat"
    should_poll = False
    state_class = SensorStateClass.MEASUREMENT
    native_unit_of_measurement = UnitOfMass.GRAMS

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

        # State machine
        self.state_machine = LitterboxStateMachine(
            initial_state=IdleState,
            initial_context=LitterboxContext(
                cat_weight_threshold=cat_weight_threshold,
                min_presence_time=timedelta(seconds=min_presence_time),
                leave_timeout=timedelta(seconds=leave_timeout),
                after_cat_standard_deviation=after_cat_standard_deviation,
                name=name,
            ),
        )
        self._unsub_listener = None

        # Sub-sensors for baseline, detection state, waste, etc.
        self._sub_sensors: list[SensorEntity] = []

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
        msg = f"Adding {self._name} to hass. Subscribing to source sensor: {self._source_entity}"
        logger.debug(msg)

        # Restore previous native value if available
        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            try:
                self.state_machine.force_set_cat_weight(
                    float(last_sensor_data.native_value)
                )  # TODO maybe worth it to have sensor state still
                msg = f"{self._name}: Restored native_value to {self.state_machine.cat_weight:.2f}"
                logger.debug(msg)
            except (ValueError, TypeError):
                msg = f"{self._name}: Could not restore native_value from {last_sensor_data.native_value}"
                logger.debug(msg)

        self._unsub_listener = async_track_state_change_event(
            self._hass, [self._source_entity], self._handle_source_sensor_state_event
        )

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        msg = f"Removing {self._name} from hass and unsubscribing"
        logger.debug(msg)
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    @callback
    def _handle_source_sensor_state_event(self, event):
        """Handle state changes of the source sensor."""
        new_state = event.data.get("new_state")
        if not new_state:
            msg = f"{self._name}: No new_state in event"
            logger.debug(msg)
            return

        if new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
            msg = f"{self._name}: State is unknown/unavailable ({new_state.state}) Ignoring"
            logger.debug(msg)
            return

        try:
            weight = float(new_state.state)
        except ValueError:
            msg = f"{self._name}: State ({new_state.state}) is non-numeric. Ignoring"
            logger.debug(msg)
            return

        # Use last_changed if available; else fallback to event.time_fired
        event_time = new_state.last_changed or event.time_fired

        msg = f"{self._name}: New weight={weight:.2f} at {event_time}"
        logger.debug(msg)

        # Add the reading to our records
        reading = Reading(event_time, weight)
        # Run detection logic
        self.state_machine.process_data(reading)
        # Update the entity state if needed
        self.async_write_ha_state()
        # Also update sub-sensors
        self._update_sub_sensors()

    @property
    def device_info(self):
        """Return device information for the cat litter detection sensor.

        This method attempts to merge device info with the source sensor's device,
        so that entities are grouped together in the device registry.
        """
        entity_reg = er.async_get(self._hass)
        device_reg = dr.async_get(self._hass)
        if entity_reg and device_reg:
            if entry := entity_reg.async_get(self._source_entity):
                if entry.device_id and (device := device_reg.async_get(entry.device_id)):
                    # Use all information from source sensor device
                    # Such that our entities will me merged with the scale device
                    return DeviceInfo(
                        identifiers=device.identifiers,
                        connections=device.connections,
                        manufacturer=device.manufacturer,
                        model=device.model,
                        name=device.name,
                        sw_version=device.sw_version,
                        hw_version=device.hw_version,
                        serial_number=device.serial_number,
                        configuration_url=device.configuration_url,
                        suggested_area=device.suggested_area,
                        entry_type=device.entry_type,
                    )
        return DeviceInfo(
            identifiers={(DOMAIN, self._source_entity)},
            name="Cat weight",
            manufacturer="Weight sensor for ordinary Cat litterbox",
            model="Smart Litter Box",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        return self.state_machine.cat_weight


class CatLitterBaselineSensor(SensorEntity):
    """A secondary sensor entity that reports the 'baseline weight'.

    This sensor gets its value from the main cat-litter detection sensor.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_translation_key = "baseline"

    def __init__(self, main_sensor: CatWeightMainSensor) -> None:
        """Initialize the baseline sensor."""
        self._main_sensor = main_sensor
        self._attr_unique_id = f"{main_sensor.unique_id}_baseline_sensor"

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        baseline_weight = self._main_sensor.state_machine.baseline_weight
        if baseline_weight is None:
            return 0.0
        return round(baseline_weight, 2)

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

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the waste sensor."""
        return self._main_sensor.device_info


class CatLitterDetectionStateSensor(SensorEntity):
    """A secondary sensor entity that shows the detection state."""

    _attr_has_entity_name = True
    _attr_translation_key = "detection_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [s.state_key for s in LitterboxStateMachine.get_all_states()]

    icon = "mdi:radar"
    should_poll = False

    def __init__(self, main_sensor: CatWeightMainSensor) -> None:
        """Initialize the detection-state sensor."""
        self._main_sensor = main_sensor
        self._attr_unique_id = f"{main_sensor.unique_id}_cat_detection_state"

    @property
    def native_value(self) -> str:
        """Return the internal detection state from the main sensor."""
        return self._main_sensor.state_machine.state.state_key

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the Detection sensor."""
        return self._main_sensor.device_info


class CatLitterWasteSensor(SensorEntity):
    """A secondary sensor entity that shows the 'waste weight'.

    This is the difference in the litter box baseline before vs. after cat visits.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_translation_key = "waste_weight"

    icon = "mdi:delete-variant"
    should_poll = False

    def __init__(self, main_sensor: CatWeightMainSensor) -> None:
        """Initialize the waste sensor."""
        self._main_sensor = main_sensor
        self._attr_unique_id = f"{main_sensor.unique_id}_waste"

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        waste_weight = self._main_sensor.state_machine.waste_weight
        if waste_weight is None:
            return 0.0
        return round(self._main_sensor.state_machine.waste_weight, 2)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of mass."""
        return UnitOfMass.GRAMS

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the waste sensor."""
        return self._main_sensor.device_info
