"""The SolarEdge Modbus Integration."""
import asyncio
import logging
import threading
from datetime import timedelta
from typing import Optional

import voluptuous as vol
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from .const import DOMAIN, DEFAULT_NAME, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

SOLAREDGE_MODBUS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: SOLAREDGE_MODBUS_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = ["sensor"]


async def async_setup(hass, config):
    """Set up the Solaredge modbus component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a solaredge mobus."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = SolaredgeModbusHub(hass, name, host, port, scan_interval)
    """Register the hub."""
    hass.data[DOMAIN][name] = {
        "hub": hub
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass, entry):
    """Unload Solaredge mobus entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if not unload_ok:
        return False

    hass.data[DOMAIN].pop(entry.data["name"])
    return True


class SolaredgeModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, hass, name, host, port, scan_interval):
        """Initialize the Modbus hub."""
        self._hass = hass
        self._client = ModbusTcpClient(host=host, port=port)
        self._lock = threading.Lock()
        self._name = name
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unsub_interval_method = None
        self._sensors = []
        self.data = {}

    @callback
    def async_add_solaredge_sensor(self, update_callback):
        """Listen for data updates."""
        # This is the first sensor, set up interval.
        if not self._sensors:
            self.connect()
            self._unsub_interval_method = async_track_time_interval(
                self._hass, self.async_refresh_modbus_data, self._scan_interval
            )

        self._sensors.append(update_callback)

    @callback
    def async_remove_solaredge_sensor(self, update_callback):
        """Remove data update."""
        self._sensors.remove(update_callback)

        if not self._sensors:
            """stop the interval timer upon removal of last sensor"""
            self._unsub_interval_method()
            self._unsub_interval_method = None
            self.close()

    async def async_refresh_modbus_data(self, _now: Optional[int] = None) -> None:
        """Time to update."""
        if not self._sensors:
            return

        update_result = self.read_modbus_data()

        if update_result:
            for update_callback in self._sensors:
                update_callback()

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

    def calculate_value(self, value, sf):
        return value * 10 ** sf

    def read_modbus_data_stub(self):
        self.data["accurrent"] = 1
        self.data["accurrenta"] = 1
        self.data["accurrentb"] = 1
        self.data["accurrentc"] = 1
        self.data["acvoltageab"] = 1
        self.data["acvoltagebc"] = 1
        self.data["acvoltageca"] = 1
        self.data["acvoltagean"] = 1
        self.data["acvoltagebn"] = 1
        self.data["acvoltagecn"] = 1
        self.data["acpower"] = 1
        self.data["acfreq"] = 1
        self.data["acva"] = 1
        self.data["acvar"] = 1
        self.data["acpf"] = 1
        self.data["acenergy"] = 1
        self.data["dccurrent"] = 1
        self.data["dcvoltage"] = 1
        self.data["dcpower"] = 1
        self.data["tempsink"] = 1
        self.data["status"] = 1
        self.data["statusvendor"] = 1
        return True

    def read_modbus_data(self):
        inverter_data = self.read_holding_registers(unit=1, address=40071, count=38)
        if not inverter_data.isError():
            decoder = BinaryPayloadDecoder.fromRegisters(inverter_data.registers, byteorder=Endian.Big)
            accurrent = decoder.decode_16bit_uint()
            accurrenta = decoder.decode_16bit_uint()
            accurrentb = decoder.decode_16bit_uint()
            accurrentc = decoder.decode_16bit_uint()
            accurrentsf = decoder.decode_16bit_int()

            accurrent = self.calculate_value(accurrent, accurrentsf)
            accurrenta = self.calculate_value(accurrenta, accurrentsf)
            accurrentb = self.calculate_value(accurrentb, accurrentsf)
            accurrentc = self.calculate_value(accurrentc, accurrentsf)

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

            acvoltageab = self.calculate_value(acvoltageab, acvoltagesf)
            acvoltagebc = self.calculate_value(acvoltagebc, acvoltagesf)
            acvoltageca = self.calculate_value(acvoltageca, acvoltagesf)
            acvoltagean = self.calculate_value(acvoltagean, acvoltagesf)
            acvoltagebn = self.calculate_value(acvoltagebn, acvoltagesf)
            acvoltagecn = self.calculate_value(acvoltagecn, acvoltagesf)

            self.data["acvoltageab"] = round(acvoltageab, abs(acvoltagesf))
            self.data["acvoltagebc"] = round(acvoltagebc, abs(acvoltagesf))
            self.data["acvoltageca"] = round(acvoltageca, abs(acvoltagesf))
            self.data["acvoltagean"] = round(acvoltagean, abs(acvoltagesf))
            self.data["acvoltagebn"] = round(acvoltagebn, abs(acvoltagesf))
            self.data["acvoltagecn"] = round(acvoltagecn, abs(acvoltagesf))

            acpower = decoder.decode_16bit_int()
            acpowersf = decoder.decode_16bit_int()
            acpower = self.calculate_value(acpower, acpowersf)

            self.data["acpower"] = round(acpower, abs(acpowersf))

            acfreq = decoder.decode_16bit_uint()
            acfreqsf = decoder.decode_16bit_int()
            acfreq = self.calculate_value(acfreq, acfreqsf)

            self.data["acfreq"] = round(acfreq, abs(acfreqsf))

            acva = decoder.decode_16bit_int()
            acvasf = decoder.decode_16bit_int()
            acva = self.calculate_value(acva, acvasf)

            self.data["acva"] = round(acva, abs(acvasf))

            acvar = decoder.decode_16bit_int()
            acvarsf = decoder.decode_16bit_int()
            acvar = self.calculate_value(acvar, acvarsf)

            self.data["acvar"] = round(acvar, abs(acvarsf))

            acpf = decoder.decode_16bit_int()
            acpfsf = decoder.decode_16bit_int()
            acpf = self.calculate_value(acpf, acpfsf)

            self.data["acpf"] = round(acpf, abs(acpfsf))

            acenergy = decoder.decode_32bit_uint()
            acenergysf = decoder.decode_16bit_uint()
            acenergy = self.calculate_value(acenergy, acenergysf)

            self.data["acenergy"] = round(acenergy * 0.001, 3)

            dccurrent = decoder.decode_16bit_uint()
            dccurrentsf = decoder.decode_16bit_int()
            dccurrent = self.calculate_value(dccurrent, dccurrentsf)

            self.data["dccurrent"] = round(dccurrent, abs(dccurrentsf))

            dcvoltage = decoder.decode_16bit_uint()
            dcvoltagesf = decoder.decode_16bit_int()
            dcvoltage = self.calculate_value(dcvoltage, dcvoltagesf)

            self.data["dcvoltage"] = round(dcvoltage, abs(dcvoltagesf))

            dcpower = decoder.decode_16bit_int()
            dcpowersf = decoder.decode_16bit_int()
            dcpower = self.calculate_value(dcpower, dcpowersf)

            self.data["dcpower"] = round(dcpower, abs(dcpowersf))

            # skip register
            decoder.skip_bytes(2)

            tempsink = decoder.decode_16bit_int()

            # skip 2 registers
            decoder.skip_bytes(4)

            tempsf = decoder.decode_16bit_int()
            tempsink = self.calculate_value(tempsink, tempsf)

            self.data["tempsink"] = round(tempsink, abs(tempsf))

            status = decoder.decode_16bit_int()
            self.data["status"] = status
            statusvendor = decoder.decode_16bit_int()
            self.data["statusvendor"] = statusvendor

            return True
        else:
            return False
