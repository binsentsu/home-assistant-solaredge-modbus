"""solaredge number platform"""
import logging

from . import (
    SolarEdgeEntity,
    SolaredgeModbusHub,
)
from .const import (
    DOMAIN,
    EXPORT_CONTROL_NUMBER_TYPES,
    STORAGE_NUMBER_TYPES,
    SolarEdgeNumberDescription,
)

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder

from homeassistant.const import CONF_NAME
from homeassistant.components.number import (
    NumberEntity,
)

from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """setup number entities"""
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    entities = []

    # If a meter is available add export control
    if hub.has_meter:
        for number_info in EXPORT_CONTROL_NUMBER_TYPES:
            entities.append(SolarEdgeNumberNew(hub, number_info))

    # If a battery is available add storage control
    if hub.has_battery:
        for number_info in STORAGE_NUMBER_TYPES:
            entities.append(SolarEdgeNumberNew(hub, number_info))

    async_add_entities(entities)
    return True


class SolarEdgeNumberNew(SolarEdgeEntity, NumberEntity):
    """Solaredge Number Entity"""

    def __init__(
        self, hub: SolaredgeModbusHub, description: SolarEdgeNumberDescription
    ) -> None:
        super().__init__(hub)
        self.entity_description = description
        self._attr_name = f"{self.hub.hubname} {description.name}"
        self._attr_unique_id = f"{self.hub.hubname}_{description.key}"
        self._register = description.register
        self._fmt = description.fmt
        self._attr_native_min_value = description.attrs["min"]
        self._attr_native_max_value = description.attrs["max"]

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.hub.async_add_solaredge_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        self.hub.async_remove_solaredge_sensor(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        if self.entity_description.key in self.hub.data:
            return self.hub.data[self.entity_description.key]

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""
        builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Little)

        if self._fmt == "i":
            builder.add_32bit_uint(int(value))
        elif self._fmt == "f":
            builder.add_32bit_float(float(value))

        self.hub.write_registers(
            unit=1, address=self._register, payload=builder.to_registers()
        )

        self.hub.data[self.entity_description.key] = value
        self.async_write_ha_state()
