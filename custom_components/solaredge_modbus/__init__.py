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
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    CONF_READ_METER1,
    DEFAULT_READ_METER1,
)

_LOGGER = logging.getLogger(__name__)

SOLAREDGE_MODBUS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_READ_METER1, default=DEFAULT_READ_METER1): cv.boolean,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
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
    read_meter1 = entry.data[CONF_READ_METER1]

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = SolaredgeModbusHub(hass, name, host, port, scan_interval, read_meter1)
    """Register the hub."""
    hass.data[DOMAIN][name] = {"hub": hub}

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

    def __init__(self, hass, name, host, port, scan_interval, read_meter1=False):
        """Initialize the Modbus hub."""
        self._hass = hass
        self._client = ModbusTcpClient(host=host, port=port)
        self._lock = threading.Lock()
        self._name = name
        self.read_meter1 = read_meter1
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
        return (
            self.read_modbus_data_inverter_stub()
            and self.read_modbus_data_meter1_stub()
        )

    def read_modbus_data_inverter_stub(self):
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

    def read_modbus_data_meter1_stub(self):
        self.data["m1_accurrent"] = 2
        self.data["m1_accurrenta"] = 2
        self.data["m1_accurrentb"] = 2
        self.data["m1_accurrentc"] = 2

        self.data["m1_acvoltageln"] = 2
        self.data["m1_acvoltagean"] = 2
        self.data["m1_acvoltagebn"] = 2
        self.data["m1_acvoltagecn"] = 2
        self.data["m1_acvoltagell"] = 2
        self.data["m1_acvoltageab"] = 2
        self.data["m1_acvoltagebc"] = 2
        self.data["m1_acvoltageca"] = 2

        self.data["m1_acfreq"] = 2

        self.data["m1_acpower"] = 2
        self.data["m1_acpowera"] = 2
        self.data["m1_acpowerb"] = 2
        self.data["m1_acpowerc"] = 2

        self.data["m1_acva"] = 2
        self.data["m1_acvaa"] = 2
        self.data["m1_acvab"] = 2
        self.data["m1_acvac"] = 2

        self.data["m1_acvar"] = 2
        self.data["m1_acvara"] = 2
        self.data["m1_acvarb"] = 2
        self.data["m1_acvarc"] = 2

        self.data["m1_acpf"] = 2
        self.data["m1_acpfa"] = 2
        self.data["m1_acpfb"] = 2
        self.data["m1_acpfc"] = 2

        self.data["m1_exported"] = 2
        self.data["m1_exporteda"] = 2
        self.data["m1_exportedb"] = 2
        self.data["m1_exportedc"] = 2

        self.data["m1_imported"] = 2
        self.data["m1_importeda"] = 2
        self.data["m1_importedb"] = 2
        self.data["m1_importedc"] = 2

        self.data["m1_exportedva"] = 2
        self.data["m1_exportedvaa"] = 2
        self.data["m1_exportedvab"] = 2
        self.data["m1_exportedvac"] = 2

        self.data["m1_importedva"] = 2
        self.data["m1_importedvaa"] = 2
        self.data["m1_importedvab"] = 2
        self.data["m1_importedvac"] = 2

        self.data["m1_importvarhq1"] = 2
        self.data["m1_importvarhq1a"] = 2
        self.data["m1_importvarhq1b"] = 2
        self.data["m1_importvarhq1c"] = 2

        self.data["m1_importvarhq2"] = 2
        self.data["m1_importvarhq2a"] = 2
        self.data["m1_importvarhq2b"] = 2
        self.data["m1_importvarhq2c"] = 2

        self.data["m1_importvarhq3"] = 2
        self.data["m1_importvarhq3a"] = 2
        self.data["m1_importvarhq3b"] = 2
        self.data["m1_importvarhq3c"] = 2

        self.data["m1_importvarhq4"] = 2
        self.data["m1_importvarhq4a"] = 2
        self.data["m1_importvarhq4b"] = 2
        self.data["m1_importvarhq4c"] = 2

        return True

    def read_modbus_data(self):
        return self.read_modbus_data_inverter() and self.read_modbus_data_meter1()

    def read_modbus_data_meter1(self):
        """ if we don't need meter1 data, its ok"""
        if not self.read_meter1:
            return True

        """start reading meter 1 data """
        meter1_data = self.read_holding_registers(unit=1, address=40189, count=103)
        if not meter1_data.isError():
            decoder = BinaryPayloadDecoder.fromRegisters(
                meter1_data.registers, byteorder=Endian.Big
            )
            accurrent = decoder.decode_16bit_uint()
            accurrenta = decoder.decode_16bit_uint()
            accurrentb = decoder.decode_16bit_uint()
            accurrentc = decoder.decode_16bit_uint()
            accurrentsf = decoder.decode_16bit_int()

            accurrent = self.calculate_value(accurrent, accurrentsf)
            accurrenta = self.calculate_value(accurrenta, accurrentsf)
            accurrentb = self.calculate_value(accurrentb, accurrentsf)
            accurrentc = self.calculate_value(accurrentc, accurrentsf)

            self.data["m1_accurrent"] = round(accurrent, abs(accurrentsf))
            self.data["m1_accurrenta"] = round(accurrenta, abs(accurrentsf))
            self.data["m1_accurrentb"] = round(accurrentb, abs(accurrentsf))
            self.data["m1_accurrentc"] = round(accurrentc, abs(accurrentsf))

            acvoltageln = decoder.decode_16bit_uint()
            acvoltagean = decoder.decode_16bit_uint()
            acvoltagebn = decoder.decode_16bit_uint()
            acvoltagecn = decoder.decode_16bit_uint()
            acvoltagell = decoder.decode_16bit_uint()
            acvoltageab = decoder.decode_16bit_uint()
            acvoltagebc = decoder.decode_16bit_uint()
            acvoltageca = decoder.decode_16bit_uint()
            acvoltagesf = decoder.decode_16bit_int()

            acvoltageln = self.calculate_value(acvoltageln, acvoltagesf)
            acvoltagean = self.calculate_value(acvoltagean, acvoltagesf)
            acvoltagebn = self.calculate_value(acvoltagebn, acvoltagesf)
            acvoltagecn = self.calculate_value(acvoltagecn, acvoltagesf)
            acvoltagell = self.calculate_value(acvoltagell, acvoltagesf)
            acvoltageab = self.calculate_value(acvoltageab, acvoltagesf)
            acvoltagebc = self.calculate_value(acvoltagebc, acvoltagesf)
            acvoltageca = self.calculate_value(acvoltageca, acvoltagesf)

            self.data["m1_acvoltageln"] = round(acvoltageln, abs(acvoltagesf))
            self.data["m1_acvoltagean"] = round(acvoltagean, abs(acvoltagesf))
            self.data["m1_acvoltagebn"] = round(acvoltagebn, abs(acvoltagesf))
            self.data["m1_acvoltagecn"] = round(acvoltagecn, abs(acvoltagesf))
            self.data["m1_acvoltagell"] = round(acvoltagell, abs(acvoltagesf))
            self.data["m1_acvoltageab"] = round(acvoltageab, abs(acvoltagesf))
            self.data["m1_acvoltagebc"] = round(acvoltagebc, abs(acvoltagesf))
            self.data["m1_acvoltageca"] = round(acvoltageca, abs(acvoltagesf))

            acfreq = decoder.decode_16bit_uint()
            acfreqsf = decoder.decode_16bit_int()

            acfreq = self.calculate_value(acfreq, acfreqsf)

            self.data["m1_acfreq"] = round(acfreq, abs(acfreqsf))

            acpower = decoder.decode_16bit_uint()
            acpowera = decoder.decode_16bit_uint()
            acpowerb = decoder.decode_16bit_uint()
            acpowerc = decoder.decode_16bit_uint()
            acpowersf = decoder.decode_16bit_int()

            acpower = self.calculate_value(acpower, acpowersf)
            acpowera = self.calculate_value(acpowera, acpowersf)
            acpowerb = self.calculate_value(acpowerb, acpowersf)
            acpowerc = self.calculate_value(acpowerc, acpowersf)

            self.data["m1_acpower"] = round(acpower, abs(acpowersf))
            self.data["m1_acpowera"] = round(acpowera, abs(acpowersf))
            self.data["m1_acpowerb"] = round(acpowerb, abs(acpowersf))
            self.data["m1_acpowerc"] = round(acpowerc, abs(acpowersf))

            acva = decoder.decode_16bit_uint()
            acvaa = decoder.decode_16bit_uint()
            acvab = decoder.decode_16bit_uint()
            acvac = decoder.decode_16bit_uint()
            acvasf = decoder.decode_16bit_int()

            acva = self.calculate_value(acva, acvasf)
            acvaa = self.calculate_value(acvaa, acvasf)
            acvab = self.calculate_value(acvab, acvasf)
            acvac = self.calculate_value(acvac, acvasf)

            self.data["m1_acva"] = round(acva, abs(acvasf))
            self.data["m1_acvaa"] = round(acvaa, abs(acvasf))
            self.data["m1_acvab"] = round(acvab, abs(acvasf))
            self.data["m1_acvac"] = round(acvac, abs(acvasf))

            acvar = decoder.decode_16bit_uint()
            acvara = decoder.decode_16bit_uint()
            acvarb = decoder.decode_16bit_uint()
            acvarc = decoder.decode_16bit_uint()
            acvarsf = decoder.decode_16bit_int()

            acvar = self.calculate_value(acvar, acvarsf)
            acvara = self.calculate_value(acvara, acvarsf)
            acvarb = self.calculate_value(acvarb, acvarsf)
            acvarc = self.calculate_value(acvarc, acvarsf)

            self.data["m1_acvar"] = round(acvar, abs(acvarsf))
            self.data["m1_acvara"] = round(acvara, abs(acvarsf))
            self.data["m1_acvarb"] = round(acvarb, abs(acvarsf))
            self.data["m1_acvarc"] = round(acvarc, abs(acvarsf))

            acpf = decoder.decode_16bit_uint()
            acpfa = decoder.decode_16bit_uint()
            acpfb = decoder.decode_16bit_uint()
            acpfc = decoder.decode_16bit_uint()
            acpfsf = decoder.decode_16bit_int()

            acpf = self.calculate_value(acpf, acpfsf)
            acpfa = self.calculate_value(acpfa, acpfsf)
            acpfb = self.calculate_value(acpfb, acpfsf)
            acpfc = self.calculate_value(acpfc, acpfsf)

            self.data["m1_acpf"] = round(acpf, abs(acpfsf))
            self.data["m1_acpfa"] = round(acpfa, abs(acpfsf))
            self.data["m1_acpfb"] = round(acpfb, abs(acpfsf))
            self.data["m1_acpfc"] = round(acpfc, abs(acpfsf))

            exported = decoder.decode_32bit_uint()
            exporteda = decoder.decode_32bit_uint()
            exportedb = decoder.decode_32bit_uint()
            exportedc = decoder.decode_32bit_uint()
            imported = decoder.decode_32bit_uint()
            importeda = decoder.decode_32bit_uint()
            importedb = decoder.decode_32bit_uint()
            importedc = decoder.decode_32bit_uint()
            energywsf = decoder.decode_16bit_int()

            exported = self.calculate_value(exported, energywsf)
            exporteda = self.calculate_value(exporteda, energywsf)
            exportedb = self.calculate_value(exportedb, energywsf)
            exportedc = self.calculate_value(exportedc, energywsf)
            imported = self.calculate_value(imported, energywsf)
            importeda = self.calculate_value(importeda, energywsf)
            importedb = self.calculate_value(importedb, energywsf)
            importedc = self.calculate_value(importedc, energywsf)

            self.data["m1_exported"] = round(exported * 0.001, 3)
            self.data["m1_exporteda"] = round(exporteda * 0.001, 3)
            self.data["m1_exportedb"] = round(exportedb * 0.001, 3)
            self.data["m1_exportedc"] = round(exportedc * 0.001, 3)
            self.data["m1_imported"] = round(imported * 0.001, 3)
            self.data["m1_importeda"] = round(importeda * 0.001, 3)
            self.data["m1_importedb"] = round(importedb * 0.001, 3)
            self.data["m1_importedc"] = round(importedc * 0.001, 3)

            exportedva = decoder.decode_32bit_uint()
            exportedvaa = decoder.decode_32bit_uint()
            exportedvab = decoder.decode_32bit_uint()
            exportedvac = decoder.decode_32bit_uint()
            importedva = decoder.decode_32bit_uint()
            importedvaa = decoder.decode_32bit_uint()
            importedvab = decoder.decode_32bit_uint()
            importedvac = decoder.decode_32bit_uint()
            energyvasf = decoder.decode_16bit_int()

            exportedva = self.calculate_value(exportedva, energyvasf)
            exportedvaa = self.calculate_value(exportedvaa, energyvasf)
            exportedvab = self.calculate_value(exportedvab, energyvasf)
            exportedvac = self.calculate_value(exportedvac, energyvasf)
            importedva = self.calculate_value(importedva, energyvasf)
            importedvaa = self.calculate_value(importedvaa, energyvasf)
            importedvab = self.calculate_value(importedvab, energyvasf)
            importedvac = self.calculate_value(importedvac, energyvasf)

            self.data["m1_exportedva"] = round(exportedva, abs(energyvasf))
            self.data["m1_exportedvaa"] = round(exportedvaa, abs(energyvasf))
            self.data["m1_exportedvab"] = round(exportedvab, abs(energyvasf))
            self.data["m1_exportedvac"] = round(exportedvac, abs(energyvasf))
            self.data["m1_importedva"] = round(importedva, abs(energyvasf))
            self.data["m1_importedvaa"] = round(importedvaa, abs(energyvasf))
            self.data["m1_importedvab"] = round(importedvab, abs(energyvasf))
            self.data["m1_importedvac"] = round(importedvac, abs(energyvasf))

            importvarhq1 = decoder.decode_32bit_uint()
            importvarhq1a = decoder.decode_32bit_uint()
            importvarhq1b = decoder.decode_32bit_uint()
            importvarhq1c = decoder.decode_32bit_uint()
            importvarhq2 = decoder.decode_32bit_uint()
            importvarhq2a = decoder.decode_32bit_uint()
            importvarhq2b = decoder.decode_32bit_uint()
            importvarhq2c = decoder.decode_32bit_uint()
            importvarhq3 = decoder.decode_32bit_uint()
            importvarhq3a = decoder.decode_32bit_uint()
            importvarhq3b = decoder.decode_32bit_uint()
            importvarhq3c = decoder.decode_32bit_uint()
            importvarhq4 = decoder.decode_32bit_uint()
            importvarhq4a = decoder.decode_32bit_uint()
            importvarhq4b = decoder.decode_32bit_uint()
            importvarhq4c = decoder.decode_32bit_uint()
            energyvarsf = decoder.decode_16bit_int()

            importvarhq1 = self.calculate_value(importvarhq1, energyvarsf)
            importvarhq1a = self.calculate_value(importvarhq1a, energyvarsf)
            importvarhq1b = self.calculate_value(importvarhq1b, energyvarsf)
            importvarhq1c = self.calculate_value(importvarhq1c, energyvarsf)
            importvarhq2 = self.calculate_value(importvarhq2, energyvarsf)
            importvarhq2a = self.calculate_value(importvarhq2a, energyvarsf)
            importvarhq2b = self.calculate_value(importvarhq2b, energyvarsf)
            importvarhq2c = self.calculate_value(importvarhq2c, energyvarsf)
            importvarhq3 = self.calculate_value(importvarhq3, energyvarsf)
            importvarhq3a = self.calculate_value(importvarhq3a, energyvarsf)
            importvarhq3b = self.calculate_value(importvarhq3b, energyvarsf)
            importvarhq3c = self.calculate_value(importvarhq3c, energyvarsf)
            importvarhq4 = self.calculate_value(importvarhq4, energyvarsf)
            importvarhq4a = self.calculate_value(importvarhq4a, energyvarsf)
            importvarhq4b = self.calculate_value(importvarhq4b, energyvarsf)
            importvarhq4c = self.calculate_value(importvarhq4c, energyvarsf)

            self.data["m1_importvarhq1"] = round(importvarhq1, abs(energyvarsf))
            self.data["m1_importvarhq1a"] = round(importvarhq1a, abs(energyvarsf))
            self.data["m1_importvarhq1b"] = round(importvarhq1b, abs(energyvarsf))
            self.data["m1_importvarhq1c"] = round(importvarhq1c, abs(energyvarsf))
            self.data["m1_importvarhq2"] = round(importvarhq2, abs(energyvarsf))
            self.data["m1_importvarhq2a"] = round(importvarhq2a, abs(energyvarsf))
            self.data["m1_importvarhq2b"] = round(importvarhq2b, abs(energyvarsf))
            self.data["m1_importvarhq2c"] = round(importvarhq2c, abs(energyvarsf))
            self.data["m1_importvarhq3"] = round(importvarhq3, abs(energyvarsf))
            self.data["m1_importvarhq3a"] = round(importvarhq3a, abs(energyvarsf))
            self.data["m1_importvarhq3b"] = round(importvarhq3b, abs(energyvarsf))
            self.data["m1_importvarhq3c"] = round(importvarhq3c, abs(energyvarsf))
            self.data["m1_importvarhq4"] = round(importvarhq4, abs(energyvarsf))
            self.data["m1_importvarhq4a"] = round(importvarhq4a, abs(energyvarsf))
            self.data["m1_importvarhq4b"] = round(importvarhq4b, abs(energyvarsf))
            self.data["m1_importvarhq4c"] = round(importvarhq4c, abs(energyvarsf))

            return True
        else:
            return False

    def read_modbus_data_inverter(self):
        inverter_data = self.read_holding_registers(unit=1, address=40071, count=38)
        if not inverter_data.isError():
            decoder = BinaryPayloadDecoder.fromRegisters(
                inverter_data.registers, byteorder=Endian.Big
            )
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
