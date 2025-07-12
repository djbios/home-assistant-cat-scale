"""Initialize the Average Sensor integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Cat Scale component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from config entry."""
    # Forward the config entry to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
