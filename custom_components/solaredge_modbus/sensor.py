import logging
from typing import Optional, Dict, Any
from .const import (
    SENSOR_TYPES,
    METER1_SENSOR_TYPES,
    METER2_SENSOR_TYPES,
    METER3_SENSOR_TYPES,
    DOMAIN,
    ATTR_STATUS_DESCRIPTION,
    DEVICE_STATUSES,
    ATTR_MANUFACTURER,
)
from datetime import datetime
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)

try: # backward-compatibility to 2021.8
    from homeassistant.components.sensor import STATE_CLASS_TOTAL_INCREASING
except ImportError:
    from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT as STATE_CLASS_TOTAL_INCREASING


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

    for inverter_index in range(hub.number_of_inverters):
         inverter_variable_prefix = "i" + str(inverter_index + 1) + "_"
         inverter_title_prefix = "I" + str(inverter_index + 1) + " "
         for sensor_info in SENSOR_TYPES.values():
             sensor = SolarEdgeSensor(
                 hub_name,
                 hub,
                 device_info,
                 inverter_title_prefix + sensor_info[0],
                 inverter_variable_prefix + sensor_info[1],
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
        # not everything is a measurement, i.e. text status fields
        #self._attr_state_class = STATE_CLASS_MEASUREMENT
        if self._unit_of_measurement == ENERGY_KILO_WATT_HOUR:
            self._attr_state_class = STATE_CLASS_TOTAL_INCREASING
            self._attr_device_class = DEVICE_CLASS_ENERGY
            if STATE_CLASS_TOTAL_INCREASING == STATE_CLASS_MEASUREMENT: # compatibility to 2021.8
                self._attr_last_reset = dt_util.utc_from_timestamp(0)

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

#    @property
#   def extra_state_attributes(self):
#        if self._key in ["status"]:
#            if self.state in DEVICE_STATUSES:
#                return {ATTR_STATUS_DESCRIPTION: DEVICE_STATUSES[self.state]}
#        return None

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub"""
        return False

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        return self._device_info
