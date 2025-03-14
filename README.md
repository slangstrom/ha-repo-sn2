# System Nexa 2 HA integration

Integration for [System Nexa 2](https://nexa.se/system-nexa-2) for Home Assistant, this is a repository for a custom Respository that is installed through HACS.

The integration will find devices on the network and add all of them automatically. A direct connection over websocket will be made to each device, for control and state updates.

### Models

Supports all models.

- WPR-01
- WPD-01
- WPO-01
- WBR-01
- WBD-01

### Installation

1. Open HACS in your Home Assistant
2. Press the three dot menu in the top right menu and select Custom Repositories (eller Anpassade arkiv på svenska)
3. In the popup, paste the URL for this repository and select Integration as type.
4. Press Add (or Lägg till)
5. System Nexa 2 can now be seen in the store. Press it, download and follow the instructions.

Home Assistant needs to be restarted after installation.