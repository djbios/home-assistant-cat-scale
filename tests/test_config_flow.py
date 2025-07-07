import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from custom_components.cat_scale.const import (
    DOMAIN,
    CONF_SOURCE_SENSOR,
    CONF_CAT_WEIGHT_THRESHOLD,
    CONF_MIN_PRESENCE_TIME,
    CONF_LEAVE_TIMEOUT,
    CONF_AFTER_CAT_STANDARD_DEVIATION,
)


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant):
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = {
        CONF_SOURCE_SENSOR: "sensor.my_weight",
        CONF_CAT_WEIGHT_THRESHOLD: 1000,
        CONF_MIN_PRESENCE_TIME: 10,
        CONF_LEAVE_TIMEOUT: 60,
        CONF_AFTER_CAT_STANDARD_DEVIATION: 50,
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == user_input[CONF_SOURCE_SENSOR]
    assert result2["data"] == user_input


# @pytest.mark.asyncio
# async def test_user_flow_invalid_values(hass: HomeAssistant):
#     """Test config flow with invalid (non-positive) values."""
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": "user"}
#     )
#     user_input = {
#         CONF_SOURCE_SENSOR: "sensor.my_weight",
#         CONF_CAT_WEIGHT_THRESHOLD: 0,  # Invalid
#         CONF_MIN_PRESENCE_TIME: -1,    # Invalid
#         CONF_LEAVE_TIMEOUT: 0,         # Invalid
#         CONF_AFTER_CAT_STANDARD_DEVIATION: 50,
#     }
#     result2 = await hass.config_entries.flow.async_configure(
#         result["flow_id"], user_input=user_input
#     )
#     assert result2["type"] == FlowResultType.FORM
#     # Should return errors for the invalid fields
#     assert CONF_CAT_WEIGHT_THRESHOLD in result2["errors"]
#     assert CONF_MIN_PRESENCE_TIME in result2["errors"]
#     assert CONF_LEAVE_TIMEOUT in result2["errors"]

# @pytest.mark.asyncio
# async def test_duplicate_entry_aborts(hass: HomeAssistant):
#     """Test that duplicate config entries are aborted."""
#     # First entry
#     user_input = {
#         CONF_SOURCE_SENSOR: "sensor.my_weight",
#         CONF_CAT_WEIGHT_THRESHOLD: 1000,
#         CONF_MIN_PRESENCE_TIME: 10,
#         CONF_LEAVE_TIMEOUT: 60,
#         CONF_AFTER_CAT_STANDARD_DEVIATION: 50,
#     }
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": "user"}
#     )
#     await hass.config_entries.flow.async_configure(result["flow_id"], user_input=user_input)

#     # Try to add the same entry again
#     result2 = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": "user"}
#     )
#     result3 = await hass.config_entries.flow.async_configure(
#         result2["flow_id"], user_input=user_input
#     )
#     assert result3["type"] == FlowResultType.ABORT
#     assert result3["reason"] == "already_configured"
