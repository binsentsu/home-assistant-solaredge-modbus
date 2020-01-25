import logging
import threading
from datetime import timedelta
from homeassistant.components.sensor import PLATFORM_SCHEMA
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from homeassistant.util import Throttle
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from .const import SENSOR_TYPES
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)

DOMAIN = "solaredge_modbus"

_LOGGER = logging.getLogger(__name__)

DEFAULT_HUB = "solaredge_modbus"

UPDATE_DELAY = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
    }
)


# TODO: make filtering of sensors possible through config.
def setup_platform(hass, config, add_entities, discovery_info=None):
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    platform_name = config[CONF_NAME]
    timeout = config[CONF_TIMEOUT]

    hub = SolaredgeModbusHub(hass, platform_name, host, port, timeout)

    entities = []
    for sensor_info in SENSOR_TYPES.values():
        sensor = SolarEdgeSensor(
            platform_name,
            hub,
            sensor_info[0],
            sensor_info[1],
            sensor_info[2],
            sensor_info[3],
            sensor_info[4],
        )
        entities.append(sensor)
    add_entities(entities, False)


class SolarEdgeSensor(Entity):
    """Representation of an SolarEdge Monitoring API sensor."""

    def __init__(self, platform_name, hub, name, key, unit, icon, attr):
        """Initialize the sensor."""
        self._platform_name = platform_name
        self._hub = hub
        self._state = None
        self._key = key
        self._name = name
        self._unit_of_measurement = unit
        self._icon = icon
        self._attr = attr

    @property
    def name(self):
        """Return the name."""
        return f"{self._platform_name} ({self._name})"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._attr:
            try:
                return {self._attr: self._hub.info[self._key]}
            except KeyError:
                return None
        return None

    @property
    def icon(self):
        """Return the sensor icon."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data from the sensor and update the state."""
        self._hub.update()
        if self._key in self._hub.data:
            self._state = self._hub.data[self._key]


def calculate_value(value, sf):
    return value * 10 ** sf


class SolaredgeModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, hass, name, host, port, timeout):
        """Initialize the Modbus hub."""
        self._hass = hass
        self._client = ModbusTcpClient(host=host, port=port)
        self._lock = threading.Lock()
        self._name = name
        self.data = {}

        def stop_modbus(event):
            self._client.close()

        def start_modbus(event):
            self._client.connect()
            hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_modbus)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_modbus)

    @property
    def name(self):
        """Return the name of this hub."""
        return self._name

    def close(self):
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def connect(self):
        """Connect client."""
        with self._lock:
            self._client.connect()

    def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_holding_registers(address, count, **kwargs)

    @Throttle(UPDATE_DELAY)
    def update(self):
        inverter_data = self.read_holding_registers(unit=1, address=40071, count=38)
        if not inverter_data.isError():
            decoder = BinaryPayloadDecoder.fromRegisters(inverter_data.registers, byteorder=Endian.Big)
            accurrent = decoder.decode_16bit_uint()
            accurrenta = decoder.decode_16bit_uint()
            accurrentb = decoder.decode_16bit_uint()
            accurrentc = decoder.decode_16bit_uint()
            accurrentsf = decoder.decode_16bit_int()

            accurrent = calculate_value(accurrent, accurrentsf)
            accurrenta = calculate_value(accurrenta, accurrentsf)
            accurrentb = calculate_value(accurrentb, accurrentsf)
            accurrentc = calculate_value(accurrentc, accurrentsf)

            self.data["accurrent"] = round(accurrent, abs(accurrentsf))
            self.data["accurrenta"] = round(accurrenta, abs(accurrentsf))
            self.data["accurrentb"] = round(accurrentb, abs(accurrentsf))
            self.data["accurrentc"] = round(accurrentc, abs(accurrentsf))

            acvoltageab = decoder.decode_16bit_uint()
            acvoltagebc = decoder.decode_16bit_uint()
            acvoltageca = decoder.decode_16bit_uint()
            acvoltagean = decoder.decode_16bit_uint()
            acvoltagebn = decoder.decode_16bit_uint()
            acvoltagecn = decoder.decode_16bit_uint()
            acvoltagesf = decoder.decode_16bit_int()

            acvoltageab = calculate_value(acvoltageab, acvoltagesf)
            acvoltagebc = calculate_value(acvoltagebc, acvoltagesf)
            acvoltageca = calculate_value(acvoltageca, acvoltagesf)
            acvoltagean = calculate_value(acvoltagean, acvoltagesf)
            acvoltagebn = calculate_value(acvoltagebn, acvoltagesf)
            acvoltagecn = calculate_value(acvoltagecn, acvoltagesf)

            self.data["acvoltageab"] = round(acvoltageab, abs(acvoltagesf))
            self.data["acvoltagebc"] = round(acvoltagebc, abs(acvoltagesf))
            self.data["acvoltageca"] = round(acvoltageca, abs(acvoltagesf))
            self.data["acvoltagean"] = round(acvoltagean, abs(acvoltagesf))
            self.data["acvoltagebn"] = round(acvoltagebn, abs(acvoltagesf))
            self.data["acvoltagecn"] = round(acvoltagecn, abs(acvoltagesf))

            acpower = decoder.decode_16bit_int()
            acpowersf = decoder.decode_16bit_int()
            acpower = calculate_value(acpower, acpowersf)

            self.data["acpower"] = round(acpower, abs(acpowersf))

            acfreq = decoder.decode_16bit_uint()
            acfreqsf = decoder.decode_16bit_int()
            acfreq = calculate_value(acfreq, acfreqsf)

            self.data["acfreq"] = round(acfreq, abs(acfreqsf))

            acva = decoder.decode_16bit_int()
            acvasf = decoder.decode_16bit_int()
            acva = calculate_value(acva, acvasf)

            self.data["acva"] = round(acva, abs(acvasf))

            acvar = decoder.decode_16bit_int()
            acvarsf = decoder.decode_16bit_int()
            acvar = calculate_value(acvar, acvarsf)

            self.data["acvar"] = round(acvar, abs(acvarsf))

            acpf = decoder.decode_16bit_int()
            acpfsf = decoder.decode_16bit_int()
            acpf = calculate_value(acpf, acpfsf)

            self.data["acpf"] = round(acpf, abs(acpfsf))

            acenergy = decoder.decode_32bit_uint()
            acenergysf = decoder.decode_16bit_uint()
            acenergy = calculate_value(acenergy, acenergysf)

            self.data["acenergy"] = round(acenergy * 0.001, 3)

            dccurrent = decoder.decode_16bit_uint()
            dccurrentsf = decoder.decode_16bit_int()
            dccurrent = calculate_value(dccurrent, dccurrentsf)

            self.data["dccurrent"] = round(dccurrent, abs(dccurrentsf))

            dcvoltage = decoder.decode_16bit_uint()
            dcvoltagesf = decoder.decode_16bit_int()
            dcvoltage = calculate_value(dcvoltage, dcvoltagesf)

            self.data["dcvoltage"] = round(dcvoltage, abs(dcvoltagesf))

            dcpower = decoder.decode_16bit_int()
            dcpowersf = decoder.decode_16bit_int()
            dcpower = calculate_value(dcpower, dcpowersf)

            self.data["dcpower"] = round(dcpower, abs(dcpowersf))

            # skip register
            decoder.skip_bytes(2)

            tempsink = decoder.decode_16bit_int()

            # skip 2 registers
            decoder.skip_bytes(4)

            tempsf = decoder.decode_16bit_int()
            tempsink = calculate_value(tempsink, tempsf)

            self.data["tempsink"] = round(tempsink, abs(tempsf))

            status = decoder.decode_16bit_int()
            self.data["status"] = status
            statusvendor = decoder.decode_16bit_int()
            self.data["statusvendor"] = statusvendor

