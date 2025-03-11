"""Light"""
import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lights based on a config entry."""
    device_info = hass.data[DOMAIN][entry.entry_id]
    
    # Store the device type in the device_info
    device_info["type"] = "light"
    
    # Create light entity
    light = SN2Light(hass, entry.entry_id, device_info)
    
    # Register the entity for state updates
    entity_id = f"light.{device_info['name']}".lower().replace(" ", "_")
    hass.data[DOMAIN][entity_id] = light
    
    # Add entity to Home Assistant
    async_add_entities([light])

class SN2Light(LightEntity):
    """Representation of a Light."""

    def __init__(self, hass: HomeAssistant, entry_id: str, device_info: Dict[str, Any]) -> None:
        """Initialize the light."""
        self.hass = hass
        self.entry_id = entry_id
        self._device_info = device_info
        self._attr_name = device_info["name"]
        self._attr_unique_id = f"{device_info['device_id']}_light"
        self._attr_is_on = False
        self._attr_brightness = 255  # Scale from 0-255 for HA
        
        # All our lights support brightness
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS
        
        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_info["device_id"])},
            name=device_info["name"],
            manufacturer="NEXA",
            model=device_info["model"],
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
         # Default value -1 which is toggle
        value = -1
        # Check if we're setting brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            # Convert HomeAssistant brightness (0-255) to device brightness (0-1)
            value = round(brightness / 255, 2)
                    
        await self._send_command({"type": "state", "value": value})
            

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._send_command({"type": "state", "value": 0})

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the light."""
        await self._send_command({"type": "state", "value": -1})

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
    def handle_state_update(self, state: Any) -> None:
        """Handle state updates from the device."""
        # If it's a direct boolean state
        if isinstance(state, bool):
            self._attr_is_on = state
            if state:
                self._attr_brightness = 255  # Full brightness when turned on
            self.async_write_ha_state()
            return
            
        # If it's a number value (0-1) for direct brightness control
        if isinstance(state, (int, float)):
            brightness_value = float(state)
            if brightness_value == 0:
                self._attr_is_on = False
            else:
                self._attr_is_on = True
                # Convert device brightness (0-1) to HomeAssistant brightness (0-255)
                self._attr_brightness = min(255, max(0, round(brightness_value * 255)))
            
            self.async_write_ha_state()