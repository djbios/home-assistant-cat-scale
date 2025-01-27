import logging
from collections import deque
from datetime import datetime, timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity
)
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

CONF_SOURCE_SENSOR = "source_sensor"
DEFAULT_NAME = "Average Sensor (1m)"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    """Set up the average sensor platform."""
    source_sensor = config[CONF_SOURCE_SENSOR]
    name = config[CONF_NAME]

    entity = OneMinuteAverageSensor(hass, name, source_sensor)
    async_add_entities([entity])


class OneMinuteAverageSensor(SensorEntity):
    """Sensor that calculates 1-minute average from another sensor."""

    def __init__(self, hass, name, source_entity):
        """Initialize the 1-min average sensor."""
        self._hass = hass
        self._name = name
        self._source_entity = source_entity

        # Keep data points of the last minute: deque of (timestamp, value)
        self._data_points = deque()
        self._state = None

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        # Listen for state changes of the source entity
        self._unsub_listener = async_track_state_change_event(
            self._hass, [self._source_entity], self._handle_source_sensor_state_event
        )
        # Initialize right away by getting the current state
        state = self._hass.states.get(self._source_entity)
        if state and state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
            self._add_data_point(float(state.state))
            self._calculate_average()

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        # Unsubscribe from source sensor updates
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    @callback
    def _handle_source_sensor_state_event(self, event):
        """Handle the event from the source sensor state change."""
        new_state = event.data.get("new_state")
        if not new_state:
            return

        # Filter out unknown/unavailable states
        if new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
            return

        try:
            value = float(new_state.state)
        except ValueError:
            # If we can't parse it to float, ignore
            return

        # Add data point and recalc average
        self._add_data_point(value)
        self._calculate_average()
        # Notify Home Assistant that we have updated
        self.async_write_ha_state()

    def _add_data_point(self, value):
        """Add a data point with the current time to the deque."""
        now = datetime.now()
        self._data_points.append((now, value))

    def _calculate_average(self):
        """Prune old data and calculate the 1-min average."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=60)

        # Remove data older than 60 seconds
        while self._data_points and self._data_points[0][0] < cutoff:
            self._data_points.popleft()

        # Compute average over the remaining points
        if len(self._data_points) == 0:
            self._state = None  # or 0.0, or however you want to handle "no data"
        else:
            values = [v for (_, v) in self._data_points]
            self._state = sum(values) / len(values)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the current average."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        # You may want to match the source sensor's unit_of_measurement
        return "avg"

    @property
    def icon(self):
        """Return an icon."""
        return "mdi:chart-line-variant"
