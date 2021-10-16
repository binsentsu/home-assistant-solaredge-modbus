  
"""The SolarEdge Modbus Integration."""
import asyncio
import logging
import operator
import threading
from datetime import timedelta
from typing import Optional

import voluptuous as vol
from pyModbusTCP.client import ModbusClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    CONF_READ_METER1,
    CONF_READ_METER2,
    CONF_READ_METER3,
    CONF_READ_BATTERY1,
    CONF_READ_BATTERY2,
    DEFAULT_READ_METER1,
    DEFAULT_READ_METER2,
    DEFAULT_READ_METER3,
    DEFAULT_READ_BATTERY1,
    DEFAULT_READ_BATTERY2,
    BATTERY_STATUSSES,
    STOREDGE_CONTROL_MODE,
    STOREDGE_AC_CHARGE_POLICY,
    STOREDGE_CHARGE_DISCHARGE_MODE
)

_LOGGER = logging.getLogger(__name__)

SOLAREDGE_MODBUS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_READ_METER1, default=DEFAULT_READ_METER1): cv.boolean,
        vol.Optional(CONF_READ_METER2, default=DEFAULT_READ_METER2): cv.boolean,
        vol.Optional(CONF_READ_METER3, default=DEFAULT_READ_METER3): cv.boolean,
        vol.Optional(CONF_READ_BATTERY1, default=DEFAULT_READ_BATTERY1): cv.boolean,
        vol.Optional(CONF_READ_BATTERY2, default=DEFAULT_READ_BATTERY2): cv.boolean,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: SOLAREDGE_MODBUS_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = ["number", "select", "sensor"]


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
    read_meter1 = entry.data.get(CONF_READ_METER1, False)
    read_meter2 = entry.data.get(CONF_READ_METER2, False)
    read_meter3 = entry.data.get(CONF_READ_METER3, False)
    read_battery1 = entry.data.get(CONF_READ_BATTERY1, False)
    read_battery2 = entry.data.get(CONF_READ_BATTERY2, False)

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = SolaredgeModbusHub(
        hass, name, host, port, scan_interval, read_meter1, read_meter2, read_meter3, read_battery1, read_battery2
    )
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

def validate(value, comparison, against):
    ops = {
        '>': operator.gt,
        '<': operator.lt,
        '>=': operator.ge,
        '<=': operator.le,
        '==': operator.eq,
        '!=': operator.ne
    }
    if not ops[comparison](value, against):
        raise ValueError(f"Value {value} failed validation ({comparison}{against})")
    return value

class SolaredgeModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(
        self,
        hass,
        name,
        host,
        port,
        scan_interval,
        read_meter1=False,
        read_meter2=False,
        read_meter3=False,
        read_battery1=False,
        read_battery2=False
    ):
        """Initialize the Modbus hub."""
        self._hass = hass
        self._client = ModbusClient(host=host, port=port, unit_id=1, auto_open=True)
        self._lock = threading.Lock()
        self._name = name
        self.read_meter1 = read_meter1
        self.read_meter2 = read_meter2
        self.read_meter3 = read_meter3
        self.read_battery1 = read_battery1
        self.read_battery2 = read_battery2
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unsub_interval_method = None
        self._sensors = []
        self.data = {}

    @callback
    def async_add_solaredge_sensor(self, update_callback):
        """Listen for data updates."""
        # This is the first sensor, set up interval.
        if not self._sensors:
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

    async def async_refresh_modbus_data(self, _now: Optional[int] = None) -> None:
        """Time to update."""
        if not self._sensors:
            return

        try:
            update_result = self.read_modbus_data()
        except Exception as e:
            _LOGGER.exception("Error reading modbus data")
            update_result = False
        if update_result:
            for update_callback in self._sensors:
                update_callback()

        else:
            return

    @property
    def name(self):
        """Return the name of this hub."""
        return self._name

    def read_holding_registers(self, address, count):
        """Read holding registers."""
        with self._lock:
            return self._client.read_holding_registers(address, count)

    def write_single_register(self, address, payload):
        """Write registers."""
        with self._lock:
            return self._client.write_single_register(address, payload)

    def write_multiple_registers(self, address, payload):
        """Write registers."""
        with self._lock:
            return self._client.write_multiple_registers(address, payload)

    def calculate_value(self, value, sf):
        return value * 10 ** sf

    def read_modbus_data(self):
        return (
            self.read_modbus_data_inverter()
            and self.read_modbus_data_meter1()
            and self.read_modbus_data_meter2()
            and self.read_modbus_data_meter3()
            and self.read_modbus_data_storage()
            and self.read_modbus_data_battery1()
            and self.read_modbus_data_battery2()
        )

    def read_modbus_data_meter1(self):
        if not self.read_meter1:
            return True
        else:
            return self.read_modbus_data_meter("m1_", 40190)

    def read_modbus_data_meter2(self):
        if not self.read_meter2:
            return True
        else:
            return self.read_modbus_data_meter("m2_", 40364)

    def read_modbus_data_meter3(self):
        if not self.read_meter3:
            return True
        else:
            return self.read_modbus_data_meter("m3_", 40539)

    def read_modbus_data_meter(self, meter_prefix, start_address):
        """start reading meter  data """
        meter_data = self.read_holding_registers(
            address=start_address, count=103
        )

        if meter_data:
            decoder = BinaryPayloadDecoder.fromRegisters(
                meter_data, byteorder=Endian.Big
            )
            accurrent = decoder.decode_16bit_int()
            accurrenta = decoder.decode_16bit_int()
            accurrentb = decoder.decode_16bit_int()
            accurrentc = decoder.decode_16bit_int()
            accurrentsf = decoder.decode_16bit_int()

            accurrent = self.calculate_value(accurrent, accurrentsf)
            accurrenta = self.calculate_value(accurrenta, accurrentsf)
            accurrentb = self.calculate_value(accurrentb, accurrentsf)
            accurrentc = self.calculate_value(accurrentc, accurrentsf)

            self.data[meter_prefix + "accurrent"] = round(accurrent, abs(accurrentsf))
            self.data[meter_prefix + "accurrenta"] = round(accurrenta, abs(accurrentsf))
            self.data[meter_prefix + "accurrentb"] = round(accurrentb, abs(accurrentsf))
            self.data[meter_prefix + "accurrentc"] = round(accurrentc, abs(accurrentsf))

            acvoltageln = decoder.decode_16bit_int()
            acvoltagean = decoder.decode_16bit_int()
            acvoltagebn = decoder.decode_16bit_int()
            acvoltagecn = decoder.decode_16bit_int()
            acvoltagell = decoder.decode_16bit_int()
            acvoltageab = decoder.decode_16bit_int()
            acvoltagebc = decoder.decode_16bit_int()
            acvoltageca = decoder.decode_16bit_int()
            acvoltagesf = decoder.decode_16bit_int()

            acvoltageln = self.calculate_value(acvoltageln, acvoltagesf)
            acvoltagean = self.calculate_value(acvoltagean, acvoltagesf)
            acvoltagebn = self.calculate_value(acvoltagebn, acvoltagesf)
            acvoltagecn = self.calculate_value(acvoltagecn, acvoltagesf)
            acvoltagell = self.calculate_value(acvoltagell, acvoltagesf)
            acvoltageab = self.calculate_value(acvoltageab, acvoltagesf)
            acvoltagebc = self.calculate_value(acvoltagebc, acvoltagesf)
            acvoltageca = self.calculate_value(acvoltageca, acvoltagesf)

            self.data[meter_prefix + "acvoltageln"] = round(
                acvoltageln, abs(acvoltagesf)
            )
            self.data[meter_prefix + "acvoltagean"] = round(
                acvoltagean, abs(acvoltagesf)
            )
            self.data[meter_prefix + "acvoltagebn"] = round(
                acvoltagebn, abs(acvoltagesf)
            )
            self.data[meter_prefix + "acvoltagecn"] = round(
                acvoltagecn, abs(acvoltagesf)
            )
            self.data[meter_prefix + "acvoltagell"] = round(
                acvoltagell, abs(acvoltagesf)
            )
            self.data[meter_prefix + "acvoltageab"] = round(
                acvoltageab, abs(acvoltagesf)
            )
            self.data[meter_prefix + "acvoltagebc"] = round(
                acvoltagebc, abs(acvoltagesf)
            )
            self.data[meter_prefix + "acvoltageca"] = round(
                acvoltageca, abs(acvoltagesf)
            )

            acfreq = decoder.decode_16bit_int()
            acfreqsf = decoder.decode_16bit_int()

            acfreq = self.calculate_value(acfreq, acfreqsf)

            self.data[meter_prefix + "acfreq"] = round(acfreq, abs(acfreqsf))

            acpower = decoder.decode_16bit_int()
            acpowera = decoder.decode_16bit_int()
            acpowerb = decoder.decode_16bit_int()
            acpowerc = decoder.decode_16bit_int()
            acpowersf = decoder.decode_16bit_int()

            acpower = self.calculate_value(acpower, acpowersf)
            acpowera = self.calculate_value(acpowera, acpowersf)
            acpowerb = self.calculate_value(acpowerb, acpowersf)
            acpowerc = self.calculate_value(acpowerc, acpowersf)

            self.data[meter_prefix + "acpower"] = round(acpower, abs(acpowersf))
            self.data[meter_prefix + "acpowera"] = round(acpowera, abs(acpowersf))
            self.data[meter_prefix + "acpowerb"] = round(acpowerb, abs(acpowersf))
            self.data[meter_prefix + "acpowerc"] = round(acpowerc, abs(acpowersf))

            acva = decoder.decode_16bit_int()
            acvaa = decoder.decode_16bit_int()
            acvab = decoder.decode_16bit_int()
            acvac = decoder.decode_16bit_int()
            acvasf = decoder.decode_16bit_int()

            acva = self.calculate_value(acva, acvasf)
            acvaa = self.calculate_value(acvaa, acvasf)
            acvab = self.calculate_value(acvab, acvasf)
            acvac = self.calculate_value(acvac, acvasf)

            self.data[meter_prefix + "acva"] = round(acva, abs(acvasf))
            self.data[meter_prefix + "acvaa"] = round(acvaa, abs(acvasf))
            self.data[meter_prefix + "acvab"] = round(acvab, abs(acvasf))
            self.data[meter_prefix + "acvac"] = round(acvac, abs(acvasf))

            acvar = decoder.decode_16bit_int()
            acvara = decoder.decode_16bit_int()
            acvarb = decoder.decode_16bit_int()
            acvarc = decoder.decode_16bit_int()
            acvarsf = decoder.decode_16bit_int()

            acvar = self.calculate_value(acvar, acvarsf)
            acvara = self.calculate_value(acvara, acvarsf)
            acvarb = self.calculate_value(acvarb, acvarsf)
            acvarc = self.calculate_value(acvarc, acvarsf)

            self.data[meter_prefix + "acvar"] = round(acvar, abs(acvarsf))
            self.data[meter_prefix + "acvara"] = round(acvara, abs(acvarsf))
            self.data[meter_prefix + "acvarb"] = round(acvarb, abs(acvarsf))
            self.data[meter_prefix + "acvarc"] = round(acvarc, abs(acvarsf))

            acpf = decoder.decode_16bit_int()
            acpfa = decoder.decode_16bit_int()
            acpfb = decoder.decode_16bit_int()
            acpfc = decoder.decode_16bit_int()
            acpfsf = decoder.decode_16bit_int()

            acpf = self.calculate_value(acpf, acpfsf)
            acpfa = self.calculate_value(acpfa, acpfsf)
            acpfb = self.calculate_value(acpfb, acpfsf)
            acpfc = self.calculate_value(acpfc, acpfsf)

            self.data[meter_prefix + "acpf"] = round(acpf, abs(acpfsf))
            self.data[meter_prefix + "acpfa"] = round(acpfa, abs(acpfsf))
            self.data[meter_prefix + "acpfb"] = round(acpfb, abs(acpfsf))
            self.data[meter_prefix + "acpfc"] = round(acpfc, abs(acpfsf))

            exported = decoder.decode_32bit_uint()
            exporteda = decoder.decode_32bit_uint()
            exportedb = decoder.decode_32bit_uint()
            exportedc = decoder.decode_32bit_uint()
            imported = decoder.decode_32bit_uint()
            importeda = decoder.decode_32bit_uint()
            importedb = decoder.decode_32bit_uint()
            importedc = decoder.decode_32bit_uint()
            energywsf = decoder.decode_16bit_int()

            exported = validate(self.calculate_value(exported, energywsf), ">", 0)
            exporteda = self.calculate_value(exporteda, energywsf)
            exportedb = self.calculate_value(exportedb, energywsf)
            exportedc = self.calculate_value(exportedc, energywsf)
            imported = validate(self.calculate_value(imported, energywsf), ">", 0)
            importeda = self.calculate_value(importeda, energywsf)
            importedb = self.calculate_value(importedb, energywsf)
            importedc = self.calculate_value(importedc, energywsf)

            self.data[meter_prefix + "exported"] = round(exported * 0.001, 3)
            self.data[meter_prefix + "exporteda"] = round(exporteda * 0.001, 3)
            self.data[meter_prefix + "exportedb"] = round(exportedb * 0.001, 3)
            self.data[meter_prefix + "exportedc"] = round(exportedc * 0.001, 3)
            self.data[meter_prefix + "imported"] = round(imported * 0.001, 3)
            self.data[meter_prefix + "importeda"] = round(importeda * 0.001, 3)
            self.data[meter_prefix + "importedb"] = round(importedb * 0.001, 3)
            self.data[meter_prefix + "importedc"] = round(importedc * 0.001, 3)

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

            self.data[meter_prefix + "exportedva"] = round(exportedva, abs(energyvasf))
            self.data[meter_prefix + "exportedvaa"] = round(
                exportedvaa, abs(energyvasf)
            )
            self.data[meter_prefix + "exportedvab"] = round(
                exportedvab, abs(energyvasf)
            )
            self.data[meter_prefix + "exportedvac"] = round(
                exportedvac, abs(energyvasf)
            )
            self.data[meter_prefix + "importedva"] = round(importedva, abs(energyvasf))
            self.data[meter_prefix + "importedvaa"] = round(
                importedvaa, abs(energyvasf)
            )
            self.data[meter_prefix + "importedvab"] = round(
                importedvab, abs(energyvasf)
            )
            self.data[meter_prefix + "importedvac"] = round(
                importedvac, abs(energyvasf)
            )

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

            self.data[meter_prefix + "importvarhq1"] = round(
                importvarhq1, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq1a"] = round(
                importvarhq1a, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq1b"] = round(
                importvarhq1b, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq1c"] = round(
                importvarhq1c, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq2"] = round(
                importvarhq2, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq2a"] = round(
                importvarhq2a, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq2b"] = round(
                importvarhq2b, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq2c"] = round(
                importvarhq2c, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq3"] = round(
                importvarhq3, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq3a"] = round(
                importvarhq3a, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq3b"] = round(
                importvarhq3b, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq3c"] = round(
                importvarhq3c, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq4"] = round(
                importvarhq4, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq4a"] = round(
                importvarhq4a, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq4b"] = round(
                importvarhq4b, abs(energyvarsf)
            )
            self.data[meter_prefix + "importvarhq4c"] = round(
                importvarhq4c, abs(energyvarsf)
            )


            return True
        else:
            return False

    def read_modbus_data_inverter(self):
        inverter_data = self.read_holding_registers(address=40071, count=38)

        if inverter_data:
            decoder = BinaryPayloadDecoder.fromRegisters(
                inverter_data, byteorder=Endian.Big
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
            acenergy = validate(self.calculate_value(acenergy, acenergysf), ">", 0)

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

    def read_modbus_data_storage(self):
        if not self.read_battery1 and not self.read_battery2:
            return True


        storage_data = self.read_holding_registers(address=57348, count=14)
        if storage_data:
            decoder = BinaryPayloadDecoder.fromRegisters(
                storage_data, byteorder=Endian.Big,wordorder=Endian.Little

            )

            #0xE004 - 1 - storage control mode
            storage_control_mode = decoder.decode_16bit_uint()
            if storage_control_mode in STOREDGE_CONTROL_MODE:
                self.data["storage_contol_mode"] = STOREDGE_CONTROL_MODE[storage_control_mode]
            else:
                self.data["storage_contol_mode"] = storage_control_mode

            #0xE005 - 1 - storage ac charge policy
            storage_ac_charge_policy = decoder.decode_16bit_uint()
            if storage_ac_charge_policy in STOREDGE_AC_CHARGE_POLICY:
                self.data["storage_ac_charge_policy"] = STOREDGE_AC_CHARGE_POLICY[storage_ac_charge_policy]
            else:
                self.data["storage_ac_charge_policy"] = storage_ac_charge_policy

            #0xE006 - 2 - storage AC charge limit (kWh or %)
            self.data["storage_ac_charge_limit"] = round(decoder.decode_32bit_float(), 3)

            #0xE008 - 2 - storage backup reserved capacity (%)
            self.data["storage_backup_reserved"] = round(decoder.decode_32bit_float(), 3)

            #0xE00A - 1 - storage charge / discharge default mode
            storage_default_mode = decoder.decode_16bit_uint()
            if storage_default_mode in STOREDGE_CHARGE_DISCHARGE_MODE:
                self.data["storage_default_mode"] = STOREDGE_CHARGE_DISCHARGE_MODE[storage_default_mode]
            else:
                self.data["storage_default_mode"] = storage_default_mode

            #0xE00B - 2- storage remote command timeout (seconds)
            self.data["storage_remote_command_timeout"] = decoder.decode_32bit_uint()

            #0xE00D - 1 - storage remote command mode
            storage_remote_command_mode = decoder.decode_16bit_uint()
            if storage_remote_command_mode in STOREDGE_CHARGE_DISCHARGE_MODE:
                self.data["storage_remote_command_mode"] = STOREDGE_CHARGE_DISCHARGE_MODE[storage_remote_command_mode]
            else:
                self.data["storage_remote_command_mode"] = storage_remote_command_mode

            #0xE00E - 2- storate remote charge limit
            self.data["storage_remote_charge_limit"] = round(decoder.decode_32bit_float(), 3)

            #0xE010 - 2- storate remote discharge limit
            self.data["storage_remote_discharge_limit"] = round(decoder.decode_32bit_float(), 3)

        return True

    def read_modbus_data_battery1(self):
        if not self.read_battery1:
            return True
        else:
            return self.read_modbus_data_battery("battery1_", 0xE100)

    def read_modbus_data_battery2(self):
        if not self.read_battery2:
            return True
        else:
            return self.read_modbus_data_battery("battery2_", 0xE200)

    def read_modbus_data_battery(self, battery_prefix, start_address):
        if not battery_prefix + "attrs" in self.data:
            battery_data = self.read_holding_registers(address=start_address, count=0x4C)
            if battery_data:
                decoder = BinaryPayloadDecoder.fromRegisters(
                    battery_data, byteorder=Endian.Big,wordorder=Endian.Little
                )

                def decode_string(decoder):
                    s = decoder.decode_string(32) # get 32 char string
                    s = s.partition(b'\0')[0] # omit NULL terminators
                    s = s.decode("utf-8") # decode UTF-8
                    return str(s)

                battery_info = {}
                #0x00 - 16 - manufacturer
                battery_info["manufacturer"] = decode_string(decoder)

                #0x10 - 16 - model
                battery_info["model"] = decode_string(decoder)

                #0x20 - 16 - firmware version
                battery_info["firmware_version"] = decode_string(decoder)

                #0x30 - 16 - serial number
                battery_info["serial_number"] = decode_string(decoder)

                #0x40 - 1 - device ID
                battery_info["device_id"] = decoder.decode_16bit_uint()

                #0x41 - 1 - reserved
                decoder.decode_16bit_uint()

                #0x42 - 2 - rated energy
                battery_info["rated_energy"] = decoder.decode_32bit_float()

                #0x44 - 2 - max charge continuous power
                battery_info["max_power_continuous_charge"] = decoder.decode_32bit_float()

                #0x46 - 2 - max discharge continuous power
                battery_info["max_power_continuous_discharge"] = decoder.decode_32bit_float()

                #0x48 - 2 - max charge peak power
                battery_info["max_power_peak_charge"] = decoder.decode_32bit_float()#

                #0x4A - 2 - max discharge peak power
                battery_info["max_power_peak_discharge"] = decoder.decode_32bit_float()

                self.data[battery_prefix + "attrs"] = battery_info


        storage_data = self.read_holding_registers(address=start_address + 0x6C, count=28)
        if storage_data:
            decoder = BinaryPayloadDecoder.fromRegisters(
                storage_data, byteorder=Endian.Big,wordorder=Endian.Little
            )

            #0x6C - 2 - avg temp C
            tempavg = decoder.decode_32bit_float()
            #0x6E - 2 - max temp C
            tempmax = decoder.decode_32bit_float()
            #0x70 - 2 - inst voltage V
            batteryvoltage = decoder.decode_32bit_float()
            #0x72 - 2 - inst current A
            batterycurrent = decoder.decode_32bit_float()
            #0x74 - 2 - inst power W
            batterypower = decoder.decode_32bit_float()
            #0x76 - 4 - cumulative discharged (Wh)
            cumulative_discharged = decoder.decode_64bit_uint()
            #0x7a - 4 - cumulative charged (Wh)
            cumulative_charged = decoder.decode_64bit_uint()
            #0x7E - 2 - current max size Wh
            battery_max = decoder.decode_32bit_float()
            #0x80 - 2 - available size Wh
            battery_availbable = decoder.decode_32bit_float()
            #0x82 - 2 - SoH %
            battery_SoH = decoder.decode_32bit_float()
            #0x84 - 2 - SoC %
            battery_SoC = validate(decoder.decode_32bit_float(), ">", 0.1)
            battery_SoC = validate(battery_SoC, "<", 101)

            self.data[battery_prefix + 'temp_avg'] = round(tempavg, 1)
            self.data[battery_prefix + 'temp_max'] = round(tempmax, 1)
            self.data[battery_prefix + 'voltage'] = round(batteryvoltage, 3)
            self.data[battery_prefix + 'current'] = round(batterycurrent, 3)
            self.data[battery_prefix + 'power'] = round(batterypower, 3)
            self.data[battery_prefix + 'energy_discharged'] = round(cumulative_discharged / 1000, 3)
            self.data[battery_prefix + 'energy_charged'] = round(cumulative_charged / 1000, 3)
            self.data[battery_prefix + 'size_max'] = round(battery_max, 3)
            self.data[battery_prefix + 'size_available'] = round(battery_availbable, 3)
            self.data[battery_prefix + 'state_of_health'] = round(battery_SoH, 0)
            self.data[battery_prefix + 'state_of_charge'] = round(battery_SoC, 0)
            battery_status = decoder.decode_32bit_uint()

            # voltage and current are bogus in certain statuses
            if not battery_status in [3,4,6]:
                self.data[battery_prefix + 'voltage'] = 0
                self.data[battery_prefix + 'current'] = 0
                self.data[battery_prefix + 'power'] = 0

            if battery_status in BATTERY_STATUSSES:
                self.data[battery_prefix + 'status'] = BATTERY_STATUSSES[battery_status]
            else:
                self.data[battery_prefix + 'status'] = battery_status

            return True
        else:
            return False
