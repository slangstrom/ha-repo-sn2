
"""Config flow for the integration."""
import logging
import asyncio
from typing import Any, Dict, List, Optional, Set

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_TYPE,
)
from homeassistant.data_entry_flow import FlowResult

from . import (
    DOMAIN,
    SWITCH_MODELS,
    LIGHT_MODELS,
    PLUG_MODELS
)

_LOGGER = logging.getLogger(__name__)

class SN2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the devices."""

    VERSION = 1
    
    # This integration creates config entries automatically from discovery
    # and doesn't require any user interaction
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices = {}

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle user-initiated flow but don't actually show any UI."""
        # This will be called if the user adds the integration manually,
        # but we want all setup to be automatic, so just return to show
        # that setup is complete.
        return self.async_abort(reason="already_auto_configured")

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery and automatically set up the device."""
        # Extract device information
        host = discovery_info.host
        name = discovery_info.name.split(".")[0]
        properties = discovery_info.properties
        
        # Check if this is a supported device
        if "model" not in properties:
            _LOGGER.warning(f"Device {name} at {host} missing model information in mDNS record")
            return self.async_abort(reason="not_supported")
            
        model = properties["model"]
        
        # Verify model is in our supported lists
        if model not in SWITCH_MODELS and model not in LIGHT_MODELS and model not in PLUG_MODELS:
            _LOGGER.warning(f"Device {name} at {host} has unsupported model: {model}")
            return self.async_abort(reason="unsupported_model")
            
        # Check firmware version requirement
        if "version" not in properties:
            _LOGGER.warning(f"Device {name} at {host} doesn't advertise firmware version - skipping")
            return self.async_abort(reason="firmware_version_missing")
            
        # Version check - require at least 0.9.5
        device_version = properties["version"]
        if not self._is_version_compatible(device_version, min_version="0.9.5"):
            _LOGGER.warning(f"Device {name} at {host} has incompatible firmware version {device_version} (min required: 0.9.5)")
            return self.async_abort(reason="firmware_version_incompatible")
            
        device_id = properties.get("id", name)
        
        # Determine device type based on model
        if model in SWITCH_MODELS:
            device_type = "switch"
        if model in PLUG_MODELS:
            device_type = "switch"
        elif model in LIGHT_MODELS:
            device_type = "light"
        else:
            # This should never happen due to the check above, but keeping as a safety measure
            return self.async_abort(reason="not_supported")
        
        # Set unique ID and check if already configured
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        
        # Log the discovered device
        _LOGGER.info(f"Automatically configuring discovered {device_type}: {name} ({model}) at {host}")
        
        # Automatically create the config entry without any user interaction
        return self.async_create_entry(
            title=f"{name} ({model})",
            data={
                CONF_HOST: host,
                CONF_NAME: name,
                CONF_MODEL: model,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: device_type,
            },
        )
    
    def _is_version_compatible(self, version: str, min_version: str) -> bool:
        """Check if a version string meets minimum version requirements."""
        try:
            # Clean up version strings - remove any pre-release indicators
            # Example: "0.9.5-beta.2" becomes "0.9.5"
            clean_version = version.split("-")[0].split("+")[0]
            clean_min_version = min_version.split("-")[0].split("+")[0]
            
            # Split version strings into components
            version_parts = [int(part) for part in clean_version.split(".")]
            min_version_parts = [int(part) for part in clean_min_version.split(".")]
            
            # Pad shorter lists with zeros
            while len(version_parts) < len(min_version_parts):
                version_parts.append(0)
            while len(min_version_parts) < len(version_parts):
                min_version_parts.append(0)
                
            # Compare version components
            for v, m in zip(version_parts, min_version_parts):
                if v > m:
                    return True
                if v < m:
                    return False
            
            # All components are equal, so versions are equal
            return True
            
        except (ValueError, IndexError) as e:
            # If parsing fails, log the error and reject the version
            _LOGGER.error(f"Error parsing version strings '{version}' and '{min_version}': {e}")
            return False