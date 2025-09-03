"""Solaredge number platform."""

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback

from . import SolarEdgeEntity, SolaredgeModbusCoordinator
from .const import (
    ACTIVE_POWER_LIMIT_TYPES,
    DOMAIN,
    EXPORT_CONTROL_NUMBER_TYPES,
    STORAGE_NUMBER_TYPES,
    SolarEdgeNumberDescription,
)
from .payload import BinaryPayloadBuilder, Endian

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Execute the setup of number entities."""
    hub_name = entry.data[CONF_NAME]
    hub: SolaredgeModbusCoordinator = hass.data[DOMAIN][hub_name]["hub"]

    entities = []

    # If power control is enabled add power control
    if hub.power_control_enabled:
        for number_info in ACTIVE_POWER_LIMIT_TYPES:
            entities.append(SolarEdgeNumber(hub, number_info))

    # If a meter is available add export control
    if hub.has_meter:
        for number_info in EXPORT_CONTROL_NUMBER_TYPES:
            entities.append(SolarEdgeNumber(hub, number_info))

    # If a battery is available add storage control
    if hub.has_battery:
        for number_info in STORAGE_NUMBER_TYPES:
            entities.append(SolarEdgeNumber(hub, number_info))

    async_add_entities(entities)
    return True


class SolarEdgeNumber(SolarEdgeEntity, NumberEntity):
    """Solaredge Number Entity."""

    def __init__(
        self, hub: SolaredgeModbusCoordinator, description: SolarEdgeNumberDescription
    ) -> None:
        """Init."""
        super().__init__(hub)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self.hub.name}_{description.key}"
        self._register = description.register
        self._fmt = description.fmt
        self._attr_native_min_value = description.attrs["min"]
        if description.key == "export_control_site_limit":
            self._attr_native_max_value = hub.max_export_control_site_limit
        else:
            self._attr_native_max_value = description.attrs["max"]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        """Get native value."""
        if self.entity_description.key in self.hub.modbus_data:
            return self.hub.modbus_data[self.entity_description.key]
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)

        if self._fmt == "u32":
            builder.add_32bit_uint(int(value))
        elif self._fmt == "u16":
            builder.add_16bit_uint(int(value))
        elif self._fmt == "f":
            builder.add_32bit_float(float(value))
        else:
            _LOGGER.error(
                "Invalid encoding format %s for %s",
                self._fmt,
                self.entity_description.key,
            )
            return

        response = await self.hub.hub.write_registers(
            unit=self.hub.hub.get_unit(),
            address=self._register,
            payload=builder.to_registers(),
        )
        if response.isError():
            _LOGGER.error(
                "Could not write value %s to %s", value, self.entity_description.key
            )
            return

        self.hub.modbus_data[self.entity_description.key] = value
        self.async_write_ha_state()
