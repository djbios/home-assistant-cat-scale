import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr


@pytest.mark.asyncio
async def test_entities_registered_and_available(init_integration, hass, snapshot):
    """Test that sensor entities are registered, available, and match snapshot."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
    assert entries  # Ensure entities are registered

    # Check state and attributes for all entities
    for entry in entries:
        state = hass.states.get(entry.entity_id)
        assert state is not None
        assert state.state != "unavailable"
        assert state == snapshot

    # Check device registry
    for entry in entries:
        device = device_registry.async_get(entry.device_id)
        assert device is not None
