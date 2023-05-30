"""solaredge number platform"""
import logging

from . import (
    SolarEdgeEntity,
    SolaredgeModbusHub,
)
from .const import (
    DOMAIN,
    ACTIVE_POWER_LIMIT_TYPE,
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
    
    #TODO description If power control is enabled add power control
    if hub.power_control_enabled:
        number = SolarEdgeNumber(
            hub_name,
            hub,
            device_info,
            ACTIVE_POWER_LIMIT_TYPE[0],
            ACTIVE_POWER_LIMIT_TYPE[1],
            ACTIVE_POWER_LIMIT_TYPE[2],
            ACTIVE_POWER_LIMIT_TYPE[3],
            ACTIVE_POWER_LIMIT_TYPE[4]
        )
        entities.append(number)
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
        self._attr_name = f"{self.hub.name} {description.name}"
        self._attr_unique_id = f"{self.hub.name}_{description.key}"
        self._register = description.register
        self._fmt = description.fmt
        self._attr_native_min_value = description.attrs["min"]
        self._attr_native_max_value = description.attrs["max"]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        """get native value"""
        if self.entity_description.key in self.hub.data:
            return self.hub.data[self.entity_description.key]

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""
        builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Little)

        if self._fmt == "u32":
            builder.add_32bit_uint(int(value))
        elif self._fmt =="u16":
            builder.add_16bit_uint(int(value))
        elif self._fmt == "f":
            builder.add_32bit_float(float(value))
        else:
            _LOGGER.error(f"Invalid encoding format {self._fmt} for {self._key}")
            return

        response = self.hub.write_registers(
            unit=1, address=self._register, payload=builder.to_registers()
        )
        if response.isError():
            _LOGGER.error(f"Could not write value {value} to {self._key}")
            return

        self.hub.data[self.entity_description.key] = value
        self.async_write_ha_state()
