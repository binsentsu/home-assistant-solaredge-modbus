"""Solaredge sensors"""
import logging

from homeassistant.const import CONF_NAME

from .const import (
    ATTR_STATUS_DESCRIPTION,
    BATTERY_1,
    BATTERY_2,
    DEVICE_STATUSSES,
    INVERTER_SENSORS,
    DOMAIN,
    METER_1,
    METER_2,
    METER_3,
    METERS,
    BATTERIES,
)
from . import SolarEdgeEntity, SolaredgeModbusHub
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)


from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """setup sensors"""
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

    async_add_entities(entities)
    return True


class SolarEdgeSensor(SolarEdgeEntity, SensorEntity):
    """Representation of a solaredge sensor"""

    def __init__(
        self, hub: SolaredgeModbusHub, description: SensorEntityDescription
    ) -> None:
        super().__init__(hub)
        self.entity_description = description
        self._attr_name = f"{self.hub.name} ({description.name})"
        self._attr_unique_id = f"{self.hub.name}_{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.hub.data.get(self.entity_description.key)
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
            and "battery1_attrs" in self.hub.data
        ):
            self._attr_extra_state_attributes = self.hub.data["battery1_attrs"]
        elif (
            "battery2" in self.entity_description.key
            and "battery2_attrs" in self.hub.data
        ):
            self._attr_extra_state_attributes = self.hub.data["battery2_attrs"]
        return None
