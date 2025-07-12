"""Unit tests for the Cat Scale config & options flows."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Import the module under test
from custom_components.cat_scale.const import (
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

_SOURCE_USER = config_entries.SOURCE_USER


async def _start_user_flow(hass: HomeAssistant, user_input: dict | None = None) -> dict:
    """Helper: start a user‐initiated flow, optionally with first-step data."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": _SOURCE_USER}, data=user_input
    )


# ---------------------------------------------------------------------------
# Initial / user step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_show_form(hass: HomeAssistant) -> None:
    """The first step should present a form without errors."""
    result = await _start_user_flow(hass)
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.asyncio
async def test_user_create_entry_success(hass: HomeAssistant) -> None:
    """Happy-path: valid data -> create_entry with correct contents."""
    user_input = {
        CONF_SOURCE_SENSOR: "sensor.cat_weight",
        CONF_CAT_WEIGHT_THRESHOLD: 3000,
        CONF_MIN_PRESENCE_TIME: 5,
        CONF_LEAVE_TIMEOUT: 10,
        CONF_AFTER_CAT_STANDARD_DEVIATION: 2,
    }

    result = await _start_user_flow(hass, user_input)
    assert result["type"] == "create_entry"
    assert result["title"] == user_input[CONF_SOURCE_SENSOR]
    assert result["data"] == user_input


@pytest.mark.asyncio
async def test_user_duplicate_source_aborts(hass: HomeAssistant) -> None:
    """If a config entry already exists for the sensor, the flow should abort."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="sensor.cat_weight",
        data={
            CONF_SOURCE_SENSOR: "sensor.cat_weight",
            CONF_CAT_WEIGHT_THRESHOLD: DEFAULT_CAT_WEIGHT_THRESHOLD,
            CONF_MIN_PRESENCE_TIME: DEFAULT_MIN_PRESENCE_TIME,
            CONF_LEAVE_TIMEOUT: DEFAULT_LEAVE_TIMEOUT,
            CONF_AFTER_CAT_STANDARD_DEVIATION: DEFAULT_AFTER_CAT_STANDARD_DEVIATION,
        },
    )
    existing_entry.add_to_hass(hass)

    result = await _start_user_flow(
        hass,
        {
            CONF_SOURCE_SENSOR: "sensor.cat_weight",
            CONF_CAT_WEIGHT_THRESHOLD: 2500,
            CONF_MIN_PRESENCE_TIME: 5,
            CONF_LEAVE_TIMEOUT: 15,
            CONF_AFTER_CAT_STANDARD_DEVIATION: 1,
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


async def _start_options_flow(
    hass: HomeAssistant, entry: MockConfigEntry, user_input: dict | None = None
) -> dict:
    """Helper: start an options flow for *entry* with optional data."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    if user_input is None:
        return result
    return await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=user_input
    )


@pytest.fixture(name="configured_entry")
def fixture_configured_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A fully set-up config entry used by options-flow tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="sensor.cat_weight",
        data={
            CONF_SOURCE_SENSOR: "sensor.cat_weight",
            CONF_CAT_WEIGHT_THRESHOLD: DEFAULT_CAT_WEIGHT_THRESHOLD,
            CONF_MIN_PRESENCE_TIME: DEFAULT_MIN_PRESENCE_TIME,
            CONF_LEAVE_TIMEOUT: DEFAULT_LEAVE_TIMEOUT,
            CONF_AFTER_CAT_STANDARD_DEVIATION: DEFAULT_AFTER_CAT_STANDARD_DEVIATION,
        },
        options={},  # start with no options stored
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_options_show_form(hass: HomeAssistant, configured_entry: MockConfigEntry):
    """The first options step should return a form with no errors."""
    result = await _start_options_flow(hass, configured_entry)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["errors"] == {}


@pytest.mark.asyncio
async def test_options_create_entry_success(hass: HomeAssistant, configured_entry: MockConfigEntry):
    """Valid options input should store the data and finish."""
    new_options = {
        CONF_CAT_WEIGHT_THRESHOLD: 3500,
        CONF_MIN_PRESENCE_TIME: 8,
        CONF_LEAVE_TIMEOUT: 20,
        CONF_AFTER_CAT_STANDARD_DEVIATION: 2,
    }

    result = await _start_options_flow(hass, configured_entry, new_options)
    assert result["type"] == "create_entry"
    assert result["data"] == new_options
    # ConfigEntry object should now reflect the new options
    assert configured_entry.options == new_options
