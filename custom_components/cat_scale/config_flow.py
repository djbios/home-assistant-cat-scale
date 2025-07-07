"""Config flow for the Cat Scale integration."""

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import selector
import homeassistant.helpers.config_validation as cv


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
from homeassistant.config_entries import OptionsFlowWithConfigEntry


class CatScaleOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle a config options flow for cat_scale."""

    async def async_step_init(self, user_input=None):
        "Handle options flow."
        errors = {}

        # Use either current options or data or default
        options = self.config_entry.options
        data = self.config_entry.data

        if user_input is not None:
            if not user_input[CONF_CAT_WEIGHT_THRESHOLD] > 0:
                errors[CONF_CAT_WEIGHT_THRESHOLD] = "not_positive"
            if not user_input[CONF_MIN_PRESENCE_TIME] > 0:
                errors[CONF_MIN_PRESENCE_TIME] = "not_positive"
            if not user_input[CONF_LEAVE_TIMEOUT] > 0:
                errors[CONF_LEAVE_TIMEOUT] = "not_positive"
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CAT_WEIGHT_THRESHOLD,
                        default=options.get(
                            CONF_CAT_WEIGHT_THRESHOLD,
                            data.get(CONF_CAT_WEIGHT_THRESHOLD, DEFAULT_CAT_WEIGHT_THRESHOLD),
                        ),
                    ): cv.positive_int,
                    vol.Required(
                        CONF_MIN_PRESENCE_TIME,
                        default=options.get(
                            CONF_MIN_PRESENCE_TIME,
                            data.get(CONF_MIN_PRESENCE_TIME, DEFAULT_MIN_PRESENCE_TIME),
                        ),
                    ): cv.positive_int,
                    vol.Required(
                        CONF_LEAVE_TIMEOUT,
                        default=options.get(
                            CONF_LEAVE_TIMEOUT,
                            data.get(CONF_LEAVE_TIMEOUT, DEFAULT_LEAVE_TIMEOUT),
                        ),
                    ): cv.positive_int,
                    vol.Required(
                        CONF_AFTER_CAT_STANDARD_DEVIATION,
                        default=options.get(
                            CONF_AFTER_CAT_STANDARD_DEVIATION,
                            data.get(
                                CONF_AFTER_CAT_STANDARD_DEVIATION,
                                DEFAULT_AFTER_CAT_STANDARD_DEVIATION,
                            ),
                        ),
                    ): cv.positive_int,
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
            if not user_input[CONF_CAT_WEIGHT_THRESHOLD] > 0:
                errors[CONF_CAT_WEIGHT_THRESHOLD] = "not_positive"
            if not user_input[CONF_MIN_PRESENCE_TIME] > 0:
                errors[CONF_MIN_PRESENCE_TIME] = "not_positive"
            if not user_input[CONF_LEAVE_TIMEOUT] > 0:
                errors[CONF_LEAVE_TIMEOUT] = "not_positive"
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_SOURCE_SENSOR],
                    data={
                        CONF_SOURCE_SENSOR: user_input[CONF_SOURCE_SENSOR],
                        CONF_CAT_WEIGHT_THRESHOLD: user_input[CONF_CAT_WEIGHT_THRESHOLD],
                        CONF_MIN_PRESENCE_TIME: user_input[CONF_MIN_PRESENCE_TIME],
                        CONF_LEAVE_TIMEOUT: user_input[CONF_LEAVE_TIMEOUT],
                        CONF_AFTER_CAT_STANDARD_DEVIATION: user_input[
                            CONF_AFTER_CAT_STANDARD_DEVIATION
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
                    ): cv.positive_int,
                    vol.Required(
                        CONF_MIN_PRESENCE_TIME,
                        default=DEFAULT_MIN_PRESENCE_TIME,
                    ): cv.positive_int,
                    vol.Required(
                        CONF_LEAVE_TIMEOUT,
                        default=DEFAULT_LEAVE_TIMEOUT,
                    ): cv.positive_int,
                    vol.Required(
                        CONF_AFTER_CAT_STANDARD_DEVIATION,
                        default=DEFAULT_AFTER_CAT_STANDARD_DEVIATION,
                    ): cv.positive_int,
                }
            ),
            errors=errors,
        )
