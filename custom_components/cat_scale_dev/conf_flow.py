import voluptuous as vol

from homeassistant.core import callback

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)

from .const import (
    DOMAIN,
    CONF_CAT_WEIGHT_THRESHOLD,
    CONF_MIN_PRESENCE_TIME,
    CONF_LEAVE_TIMEOUT,
    DEFAULT_CAT_WEIGHT_THRESHOLD,
    DEFAULT_MIN_PRESENCE_TIME,
    DEFAULT_LEAVE_TIMEOUT,
    AFTER_CAT_STANDARD_DEVIATION,
)

class CatLitterOptionsFlowHandler(OptionsFlow):
    """Handle a config options flow for cat_litter."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        "Handle options flow"
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
            data_schema=vol.Schema({
                vol.Required(
                    CONF_CAT_WEIGHT_THRESHOLD, 
                    default=options.get(CONF_CAT_WEIGHT_THRESHOLD, data.get(CONF_CAT_WEIGHT_THRESHOLD, DEFAULT_CAT_WEIGHT_THRESHOLD))
                ): vol.Coerce(int),

                vol.Required(
                    CONF_MIN_PRESENCE_TIME, 
                    default=options.get(CONF_MIN_PRESENCE_TIME, data.get(CONF_MIN_PRESENCE_TIME, DEFAULT_MIN_PRESENCE_TIME))
                ): vol.Coerce(int),

                vol.Required(
                    CONF_LEAVE_TIMEOUT, 
                    default=options.get(CONF_LEAVE_TIMEOUT, data.get(CONF_LEAVE_TIMEOUT, DEFAULT_LEAVE_TIMEOUT))
                ): vol.Coerce(int),
            }),
            errors=errors,
        )

# Needed to connect to the config entry:
class CatLitterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for cat_litter."""
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Validate here if you want

            # Save the settings to data (unmodifiable later unless by user editing storage directly)
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={
                    CONF_SOURCE_SENSOR: user_input[CONF_SOURCE_SENSOR],
                    CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME)
                    # ...add other fixed config values here
                },
                # options can be empty for first run, or can contain tunables
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SOURCE_SENSOR): str,  # or cv.entity_id for entity selector
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        from .config_flow import CatLitterOptionsFlowHandler
        return CatLitterOptionsFlowHandler(config_entry)