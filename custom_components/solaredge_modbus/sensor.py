import logging
from typing import Optional, Dict, Any
from .const import (
    SENSOR_TYPES,
    METER1_SENSOR_TYPES,
    METER2_SENSOR_TYPES,
    METER3_SENSOR_TYPES,
    BATTERY1_SENSOR_TYPES,
    BATTERY2_SENSOR_TYPES,
    BATTERY3_SENSOR_TYPES,
    DOMAIN,
    ATTR_STATUS_DESCRIPTION,
    DEVICE_STATUSSES,
    BATTERY_STATUSSES,
    ATTR_MANUFACTURER,
)
from datetime import datetime
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME, UnitOfEnergy, UnitOfPower
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass
)

from homeassistant.core import callback
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "name": hub_name,
        "manufacturer": ATTR_MANUFACTURER,
    }

    entities = []
    for sensor_info in SENSOR_TYPES.values():
        sensor = SolarEdgeSensor(
            hub_name,
            hub,
            device_info,
            sensor_info[0],
            sensor_info[1],
            sensor_info[2],
            sensor_info[3],
        )
        entities.append(sensor)

    if hub.read_meter1 == True:
        for meter_sensor_info in METER1_SENSOR_TYPES.values():
            sensor = SolarEdgeSensor(
                hub_name,
                hub,
                device_info,
                meter_sensor_info[0],
                meter_sensor_info[1],
                meter_sensor_info[2],
                meter_sensor_info[3],
            )
            entities.append(sensor)

    if hub.read_meter2 == True:
        for meter_sensor_info in METER2_SENSOR_TYPES.values():
            sensor = SolarEdgeSensor(
                hub_name,
                hub,
                device_info,
                meter_sensor_info[0],
                meter_sensor_info[1],
                meter_sensor_info[2],
                meter_sensor_info[3],
            )
            entities.append(sensor)

    if hub.read_meter3 == True:
        for meter_sensor_info in METER3_SENSOR_TYPES.values():
            sensor = SolarEdgeSensor(
                hub_name,
                hub,
                device_info,
                meter_sensor_info[0],
                meter_sensor_info[1],
                meter_sensor_info[2],
                meter_sensor_info[3],
            )
            entities.append(sensor)

    if hub.read_battery1 == True:
        for sensor_info in BATTERY1_SENSOR_TYPES.values():
            sensor = SolarEdgeSensor(
                hub_name,
                hub,
                device_info,
                sensor_info[0],
                sensor_info[1],
                sensor_info[2],
                sensor_info[3],
            )
            entities.append(sensor)

    if hub.read_battery2 == True:
        for sensor_info in BATTERY2_SENSOR_TYPES.values():
            sensor = SolarEdgeSensor(
                hub_name,
                hub,
                device_info,
                sensor_info[0],
                sensor_info[1],
                sensor_info[2],
                sensor_info[3],
            )
            entities.append(sensor)

    if hub.read_battery3 == True:
        for sensor_info in BATTERY3_SENSOR_TYPES.values():
            sensor = SolarEdgeSensor(
                hub_name,
                hub,
                device_info,
                sensor_info[0],
                sensor_info[1],
                sensor_info[2],
                sensor_info[3],
            )
            entities.append(sensor)

    async_add_entities(entities)
    return True


class SolarEdgeSensor(SensorEntity):
    """Representation of an SolarEdge Modbus sensor."""

    def __init__(self, platform_name, hub, device_info, name, key, unit, icon):
        """Initialize the sensor."""
        self._platform_name = platform_name
        self._hub = hub
        self._key = key
        self._name = name
        self._unit_of_measurement = unit
        self._icon = icon
        self._device_info = device_info
        self._attr_state_class = SensorStateClass.MEASUREMENT
        if self._unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR :
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_device_class = SensorDeviceClass.ENERGY
        if self._unit_of_measurement == UnitOfPower.WATT :
            self._attr_device_class = SensorDeviceClass.POWER

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._hub.async_add_solaredge_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_solaredge_sensor(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self):
        self.async_write_ha_state()

    @callback
    def _update_state(self):
        if self._key in self._hub.data:
            self._state = self._hub.data[self._key]

    @property
    def name(self):
        """Return the name."""
        return f"{self._platform_name} ({self._name})"

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._platform_name}_{self._key}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the sensor icon."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._key in self._hub.data:
            return self._hub.data[self._key]

    @property
    def extra_state_attributes(self):
        if self._key in ["status", "statusvendor"] and self.state in DEVICE_STATUSSES:
            return {ATTR_STATUS_DESCRIPTION: DEVICE_STATUSSES[self.state]}
        elif "battery1" in self._key and "battery1_attrs" in self._hub.data:
            return self._hub.data["battery1_attrs"]
        elif "battery2" in self._key and "battery2_attrs" in self._hub.data:
            return self._hub.data["battery2_attrs"]
        elif "battery3" in self._key and "battery3_attrs" in self._hub.data:
            return self._hub.data["battery3_attrs"]
        return None

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub"""
        return False

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        return self._device_info
