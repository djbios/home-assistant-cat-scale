"""Initialize the Average Sensor integration."""

from .const import (
    DOMAIN,
    CONF_CAT_WEIGHT_THRESHOLD,
    CONF_MIN_PRESENCE_TIME,
    CONF_LEAVE_TIMEOUT,
    DEFAULT_CAT_WEIGHT_THRESHOLD,
    DEFAULT_MIN_PRESENCE_TIME,
    DEFAULT_LEAVE_TIMEOUT,
)


from homeassistant.core import HomeAssistant, callback


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up the integration from config entry."""
    # Forward the config entry to the sensor platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload an entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")

async def async_setup_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Set up the integration from config entry."""
    
    cat_weight_threshold = config_entry.options.get(CONF_CAT_WEIGHT_THRESHOLD, config_entry.data.get(CONF_CAT_WEIGHT_THRESHOLD, DEFAULT_CAT_WEIGHT_THRESHOLD))
    min_presence_time = config_entry.options.get(CONF_MIN_PRESENCE_TIME, config_entry.data.get(CONF_MIN_PRESENCE_TIME, DEFAULT_MIN_PRESENCE_TIME))
    leave_timeout = config_entry.options.get(CONF_LEAVE_TIMEOUT, config_entry.data.get(CONF_LEAVE_TIMEOUT, DEFAULT_LEAVE_TIMEOUT))


    # Simple pass-through: no domain-level setup needed in this example
    return True
