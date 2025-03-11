"""Switch"""
import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN, PLUG_MODELS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches based on a config entry."""
    device_info = hass.data[DOMAIN][entry.entry_id]
    
    # Store the device type in the device_info
    device_info["type"] = "switch"
    
    # Create switch entity
    switch = SN2SwitchPlug(hass, entry.entry_id, device_info)
    
    # Register the entity for state updates
    entity_id = f"switch.{device_info['name']}".lower().replace(" ", "_")
    hass.data[DOMAIN][entity_id] = switch
    
    # Add entity to Home Assistant
    async_add_entities([switch])

class SN2SwitchPlug(SwitchEntity):
    """Representation of a Switch."""

    def __init__(self, hass: HomeAssistant, entry_id: str, device_info: Dict[str, Any]) -> None:
        """Initialize the switch."""
        self.hass = hass
        self.entry_id = entry_id
        self._device_info = device_info
        self._attr_name = device_info["name"]
        self._attr_unique_id = f"{device_info['device_id']}_switch"
        self._attr_is_on = False
        
        # If it is a plug, classify as a OUTLET
        model = device_info["model"]
        if model in PLUG_MODELS:
            self._attr_device_class = SwitchDeviceClass.OUTLET
        
        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_info["device_id"])},
            name=device_info["name"],
            manufacturer="NEXA",
            model=device_info["model"],
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._send_command({"type": "state", "value": 1})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._send_command({"type": "state", "value": 0})
        
    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the switch."""
        await self._send_command({"type": "state", "value": -1})
        # Note: We'll let the state update come from the device

    async def _send_command(self, command: Dict[str, Any]) -> None:
        """Send command to the device."""
        device_info = self.hass.data[DOMAIN][self.entry_id]
        websocket = device_info.get("ws_client")
        device_name = device_info.get("name", "unknown")
        
        if websocket is None:
            _LOGGER.error(f"Cannot send command to {device_name} - no WebSocket connection available")
            return
            
        try:
            command_str = json.dumps(command)
            _LOGGER.info(f"Sending command to {device_name}: {command_str}")
            await websocket.send(command_str)
            _LOGGER.debug(f"Command sent successfully to {device_name}")
        except websockets.exceptions.ConnectionClosed as err:
            _LOGGER.error(f"Failed to send command to {device_name} - connection closed: {err.code} {err.reason}")
        except Exception as err:
            _LOGGER.error(f"Failed to send command to {device_name}: {err}")
            _LOGGER.exception("Command send error details:")

    @callback
    def handle_state_update(self, state: bool) -> None:
        """Handle state updates from the device."""
        self._attr_is_on = state
        self.async_write_ha_state()