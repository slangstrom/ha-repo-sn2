"""
System Nexa 2 component
"""
import asyncio
import json
import logging
import voluptuous as vol
from typing import Any, Dict, List, Optional, Set

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

import websockets

_LOGGER = logging.getLogger(__name__)

# Define constants for the component
DOMAIN = "systemnexa2"
SWITCH_MODELS = ["WBR-01"]
PLUG_MODELS = ["WPR-01", "WPO-01"]
LIGHT_MODELS = ["WPD-01", "WBD-01"]

# Configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({})
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store device info
    device_info = {
        "host": entry.data[CONF_HOST],
        "model": entry.data[CONF_MODEL],
        "name": entry.data[CONF_NAME],
        "device_id": entry.data[CONF_DEVICE_ID],
        "ws_client": None,
        "ws_task": None,
    }
    
    hass.data[DOMAIN][entry.entry_id] = device_info
    
    # Determine which platform to load based on model
    device_type = entry.data[CONF_TYPE]
    
    platforms = []
    if device_type == "switch":
        platforms.append("switch")
    elif device_type == "light":
        platforms.append("light")
    
    if platforms:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
    
    # Set up connection and cleanup
    async def start_websocket_client():
        """Start the websocket client for the device."""
        device_info = hass.data[DOMAIN][entry.entry_id]
        host = device_info["host"]
        
        uri = f"ws://{host}:3000/live"
        
        while True:
            try:
                async with websockets.connect(uri) as websocket:
                    device_info["ws_client"] = websocket
                    _LOGGER.info(f"Connected to {uri}")
                    
                    # Send login message immediately after connection
                    login_message = {"type": "login", "value": ""}
                    await websocket.send(json.dumps(login_message))
                    _LOGGER.debug(f"Sent login message: {login_message}")
                    
                    # Listen for messages from the device
                    while True:
                        try:
                            message = await websocket.recv()
                            _LOGGER.debug(f"Received message: {message}")
                            
                            # Process the message and update entity states
                            await process_message(hass, entry.entry_id, message)
                            
                        except websockets.exceptions.ConnectionClosed:
                            _LOGGER.warning(f"Connection closed to {uri}")
                            break
                        
            except (OSError, websockets.exceptions.WebSocketException) as err:
                _LOGGER.error(f"Failed to connect to {uri}: {err}")
                device_info["ws_client"] = None
                
            # Wait before trying to reconnect
            await asyncio.sleep(30)
    
    async def stop_websocket_client(event):
        """Stop the websocket client."""
        device_info = hass.data[DOMAIN][entry.entry_id]
        if device_info["ws_task"] is not None:
            device_info["ws_task"].cancel()
            try:
                await device_info["ws_task"]
            except asyncio.CancelledError:
                pass
        
        if device_info["ws_client"] is not None:
            await device_info["ws_client"].close()
            device_info["ws_client"] = None
    
    # Start websocket client
    device_info["ws_task"] = asyncio.create_task(start_websocket_client())
    
    # Register stop callback
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_websocket_client)
    
    return True

async def process_message(hass: HomeAssistant, entry_id: str, message: str) -> None:
    """Process a message from the device."""
    try:
        data = json.loads(message)
        device_info = hass.data[DOMAIN][entry_id]
        device_type = device_info.get("type")
        
        # Handle state updates
        if data.get("type") == "state":
            state_value = float(data.get("value", 0))
            
            # Find the entity directly from the device_info
            entity = None
            if device_type == "switch":
                entity_id = f"switch.{device_info['name']}".lower().replace(" ", "_")
                entity = hass.data[DOMAIN].get(entity_id)
                
                # For switches, convert to boolean
                is_on = bool(state_value)
                
                if entity is not None:
                    entity.handle_state_update(is_on)
                    _LOGGER.debug(f"Updated switch {device_info['name']} state to {is_on}")
                
            elif device_type == "light":
                entity_id = f"light.{device_info['name']}".lower().replace(" ", "_")
                entity = hass.data[DOMAIN].get(entity_id)
                
                if entity is not None:
                    # For lights, pass the numeric brightness value (0-1)
                    # The entity will handle the conversion to HA brightness
                    entity.handle_state_update(state_value)
                    _LOGGER.debug(f"Updated light {device_info['name']} brightness to {state_value}")
            
            if entity is None:
                _LOGGER.warning(f"Couldn't find entity for {device_info['name']}")
        
    except json.JSONDecodeError:
        _LOGGER.error(f"Invalid JSON received: {message}")
    except Exception as e:
        _LOGGER.error(f"Error processing message: {e}")
        _LOGGER.exception("Detailed error:")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device_info = hass.data[DOMAIN][entry.entry_id]
    
    # Stop the websocket client
    if device_info["ws_task"] is not None:
        device_info["ws_task"].cancel()
        try:
            await device_info["ws_task"]
        except asyncio.CancelledError:
            pass
    
    if device_info["ws_client"] is not None:
        await device_info["ws_client"].close()
    
    # Determine which platform to unload
    device_type = entry.data[CONF_TYPE]
    platforms = []
    
    if device_type == "switch":
        platforms.append("switch")
    elif device_type == "light":
        platforms.append("light")
    
    # Unload the platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok