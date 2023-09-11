import logging
from typing import Optional, Dict, Any

from .const import (
    DOMAIN,
    ATTR_MANUFACTURER,
    ACTIVE_POWER_LIMIT_TYPE,
    EXPORT_CONTROL_NUMBER_TYPES,
    STORAGE_NUMBER_TYPES,
)

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder

from homeassistant.const import CONF_NAME
from homeassistant.components.number import (
    PLATFORM_SCHEMA,
    NumberEntity,
)

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "name": hub_name,
        "manufacturer": ATTR_MANUFACTURER,
    }

    entities = []

    # If power control is enabled add power control
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
            number = SolarEdgeNumber(
                hub_name,
                hub,
                device_info,
                number_info[0],
                number_info[1],
                number_info[2],
                number_info[3],
                dict(min=number_info[4]['min'],
                     max=hub.max_export_control_site_limit,
                     unit=number_info[4]['unit']
                )
            )
            entities.append(number)

    # If a battery is available add storage control
    if hub.has_battery:
        for number_info in STORAGE_NUMBER_TYPES:
            number = SolarEdgeNumber(
                hub_name,
                hub,
                device_info,
                number_info[0],
                number_info[1],
                number_info[2],
                number_info[3],
                number_info[4],
            )
            entities.append(number)

    async_add_entities(entities)
    return True

class SolarEdgeNumber(NumberEntity):
    """Representation of an SolarEdge Modbus number."""

    def __init__(self,
                 platform_name,
                 hub,
                 device_info,
                 name,
                 key,
                 register,
                 fmt,
                 attrs
    ) -> None:
        """Initialize the selector."""
        self._platform_name = platform_name
        self._hub = hub
        self._device_info = device_info
        self._name = name
        self._key = key
        self._register = register
        self._fmt = fmt

        self._attr_native_min_value = attrs["min"]
        self._attr_native_max_value = attrs["max"]
        if "unit" in attrs.keys():
            self._attr_native_unit_of_measurement = attrs["unit"]

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.async_add_solaredge_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_solaredge_sensor(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self) -> None:
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._platform_name} ({self._name})"

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._platform_name}_{self._key}"

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub"""
        return False

    @property
    def native_value(self) -> float:
        if self._key in self._hub.data:
            return self._hub.data[self._key]

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)

        if self._fmt == "u32":
            builder.add_32bit_uint(int(value))
        elif self._fmt =="u16":
            builder.add_16bit_uint(int(value))
        elif self._fmt == "f":
            builder.add_32bit_float(float(value))
        else:
            _LOGGER.error(f"Invalid encoding format {self._fmt} for {self._key}")
            return

        response = self._hub.write_registers(unit=1, address=self._register, payload=builder.to_registers())
        if response.isError():
            _LOGGER.error(f"Could not write value {value} to {self._key}")
            return

        self._hub.data[self._key] = value
        self.async_write_ha_state()
