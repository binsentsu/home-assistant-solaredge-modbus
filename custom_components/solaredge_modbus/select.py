"""Solaredge select entities."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback

from . import SolarEdgeEntity, SolaredgeModbusHub
from .const import (
    DOMAIN,
    EXPORT_CONTROL_SELECT_TYPES,
    STORAGE_SELECT_TYPES,
    SolarEdgeSelectDescription,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Execute the setup."""
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    entities = []

    # If a meter is available add export control
    if hub.has_meter:
        for select_info in EXPORT_CONTROL_SELECT_TYPES:
            entities.append(SolarEdgeSelect(hub, select_info))

    # If a battery is available add storage control
    if hub.has_battery:
        for select_info in STORAGE_SELECT_TYPES:
            entities.append(SolarEdgeSelect(hub, select_info))

    async_add_entities(entities)
    return True


def get_key(my_dict, search):
    """GetKey."""
    for key, value in my_dict.items():
        if value == search:
            return key
    return None


class SolarEdgeSelect(SelectEntity, SolarEdgeEntity):
    """SolarEdge Select Entity."""

    def __init__(
        self,
        hub: SolaredgeModbusHub,
        description: SolarEdgeSelectDescription,
    ) -> None:
        """Init the select entity."""
        super().__init__(hub)
        self._attr_has_entity_name = True
        self.entity_description = description
        self._attr_unique_id = f"{self.hub.name}_{description.key}"
        self._register = description.register
        self._option_dict = description.options_dict
        self._attr_options = list(description.options_dict.values())

    @property
    def current_option(self) -> str:
        """Get current option."""
        if self.entity_description.key in self.hub.data:
            return self.hub.data[self.entity_description.key]
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        new_mode = get_key(self._option_dict, option)
        self.hub.write_registers(unit=1, address=self._register, payload=new_mode)

        self.hub.data[self.entity_description.key] = option
        self.async_write_ha_state()
