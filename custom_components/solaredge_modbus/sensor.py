"""Solaredge sensors."""

import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback

from . import SolarEdgeEntity, SolaredgeModbusCoordinator
from .const import (
    ATTR_STATUS_DESCRIPTION,
    BATTERIES,
    BATTERY_1,
    BATTERY_2,
    BATTERY_3,
    DEVICE_STATUSSES,
    DOMAIN,
    INVERTER_SENSORS,
    METER_1,
    METER_2,
    METER_3,
    METERS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Execute the setup of the sensors."""
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    entities = []

    for sensor_info in INVERTER_SENSORS:
        entities.append(SolarEdgeSensor(hub, sensor_info))

    if hub.read_meter1:
        for meter_sensor_info in METERS.get(METER_1):
            entities.append(SolarEdgeSensor(hub, meter_sensor_info))

    if hub.read_meter2:
        for meter_sensor_info in METERS.get(METER_2):
            entities.append(SolarEdgeSensor(hub, meter_sensor_info))

    if hub.read_meter3:
        for meter_sensor_info in METERS.get(METER_3):
            entities.append(SolarEdgeSensor(hub, meter_sensor_info))

    if hub.read_battery1:
        for battery_sensor_info in BATTERIES.get(BATTERY_1):
            entities.append(SolarEdgeSensor(hub, battery_sensor_info))

    if hub.read_battery2:
        for battery_sensor_info in BATTERIES.get(BATTERY_2):
            entities.append(SolarEdgeSensor(hub, battery_sensor_info))

    if hub.read_battery3:
        for battery_sensor_info in BATTERIES.get(BATTERY_3):
            entities.append(SolarEdgeSensor(hub, battery_sensor_info))

    async_add_entities(entities)
    return True


class SolarEdgeSensor(SolarEdgeEntity, SensorEntity):
    """Representation of a solaredge sensor."""

    def __init__(
        self, hub: SolaredgeModbusCoordinator, description: SensorEntityDescription
    ) -> None:
        """Init the sensor."""
        super().__init__(hub)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self.hub.name}_{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        new_value = self.hub.modbus_data.get(self.entity_description.key)
        """We keep old value when we would get a new value of 0 for a total increasing sensor."""
        if (
            (self.entity_description.state_class != SensorStateClass.TOTAL_INCREASING)
            or (new_value is None)
            or (new_value > 0)
        ):
            self._attr_native_value = new_value

        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update extra attributes."""

        if (
            self.entity_description.key in ["status", "statusvendor"]
            and self._attr_native_value in DEVICE_STATUSSES
        ):
            self._attr_extra_state_attributes = {
                ATTR_STATUS_DESCRIPTION: DEVICE_STATUSSES[self.state]
            }
        elif (
            "battery1" in self.entity_description.key
            and "battery1_attrs" in self.hub.modbus_data
        ):
            self._attr_extra_state_attributes = self.hub.modbus_data["battery1_attrs"]
        elif (
            "battery2" in self.entity_description.key
            and "battery2_attrs" in self.hub.modbus_data
        ):
            self._attr_extra_state_attributes = self.hub.modbus_data["battery2_attrs"]
        elif (
            "battery3" in self.entity_description.key
            and "battery3_attrs" in self.hub.modbus_data
        ):
            self._attr_extra_state_attributes = self.hub.modbus_data["battery3_attrs"]
