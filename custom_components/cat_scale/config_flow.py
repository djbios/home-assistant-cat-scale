"""Config flow for the Cat Scale integration."""

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    AFTER_CAT_STANDARD_DEVIATION,
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


class CatScaleOptionsFlowHandler(OptionsFlow):
    """Handle a config options flow for cat_scale."""

    async def async_step_init(self, user_input=None):
        "Handle options flow."
        errors = {}

        # Use either current options or data or default
        options = self.config_entry.options
        data = self.config_entry.data

        if user_input is not None:
            # Validate if necessary
            # (Here: just accept all positive values)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CAT_WEIGHT_THRESHOLD,
                        default=options.get(
                            CONF_CAT_WEIGHT_THRESHOLD,
                            data.get(
                                CONF_CAT_WEIGHT_THRESHOLD, DEFAULT_CAT_WEIGHT_THRESHOLD
                            ),
                        ),
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_MIN_PRESENCE_TIME,
                        default=options.get(
                            CONF_MIN_PRESENCE_TIME,
                            data.get(CONF_MIN_PRESENCE_TIME, DEFAULT_MIN_PRESENCE_TIME),
                        ),
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_LEAVE_TIMEOUT,
                        default=options.get(
                            CONF_LEAVE_TIMEOUT,
                            data.get(CONF_LEAVE_TIMEOUT, DEFAULT_LEAVE_TIMEOUT),
                        ),
                    ): vol.Coerce(int),
                    vol.Required(
                        AFTER_CAT_STANDARD_DEVIATION,
                        default=options.get(
                            AFTER_CAT_STANDARD_DEVIATION,
                            data.get(
                                AFTER_CAT_STANDARD_DEVIATION,
                                DEFAULT_AFTER_CAT_STANDARD_DEVIATION,
                            ),
                        ),
                    ): vol.Coerce(int),
                }
            ),
            errors=errors,
        )


# Needed to connect to the config entry:
class CatScaleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for cat_scale."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return CatScaleOptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        """Handle the initial step of the config flow."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SOURCE_SENSOR])
            self._abort_if_unique_id_configured()
            # Save all settings to data (unmodifiable later unless by user editing storage directly)
            return self.async_create_entry(
                title=user_input[CONF_SOURCE_SENSOR],
                data={
                    CONF_SOURCE_SENSOR: user_input[CONF_SOURCE_SENSOR],
                    CONF_CAT_WEIGHT_THRESHOLD: user_input[CONF_CAT_WEIGHT_THRESHOLD],
                    CONF_MIN_PRESENCE_TIME: user_input[CONF_MIN_PRESENCE_TIME],
                    CONF_LEAVE_TIMEOUT: user_input[CONF_LEAVE_TIMEOUT],
                    AFTER_CAT_STANDARD_DEVIATION: user_input[
                        AFTER_CAT_STANDARD_DEVIATION
                    ],
                },
            )
        # Use either current options or data or default
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE_SENSOR): selector(
                        {
                            "entity": {
                                "domain": "sensor",
                                "device_class": "weight",
                                "multiple": False,
                            }
                        }
                    ),
                    vol.Required(
                        CONF_CAT_WEIGHT_THRESHOLD,
                        default=DEFAULT_CAT_WEIGHT_THRESHOLD,
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_MIN_PRESENCE_TIME,
                        default=DEFAULT_MIN_PRESENCE_TIME,
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_LEAVE_TIMEOUT,
                        default=DEFAULT_LEAVE_TIMEOUT,
                    ): vol.Coerce(int),
                    vol.Required(
                        AFTER_CAT_STANDARD_DEVIATION,
                        default=DEFAULT_AFTER_CAT_STANDARD_DEVIATION,
                    ): vol.Coerce(int),
                }
            ),
            errors=errors,
        )
