"""The SolarEdge Modbus Integration."""
import asyncio
import logging
import operator
import threading
from datetime import timedelta
from typing import Optional

import voluptuous as vol
from pymodbus.client import ModbusTcpClient
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
    DEFAULT_MODBUS_ADDRESS,
    CONF_MODBUS_ADDRESS,
    CONF_POWER_CONTROL,
    CONF_READ_METER1,
    CONF_READ_METER2,
    CONF_READ_METER3,
    CONF_READ_BATTERY1,
    CONF_READ_BATTERY2,
    CONF_READ_BATTERY3,
    DEFAULT_POWER_CONTROL,
    DEFAULT_READ_METER1,
    DEFAULT_READ_METER2,
    DEFAULT_READ_METER3,
    DEFAULT_READ_BATTERY1,
    DEFAULT_READ_BATTERY2,
    DEFAULT_READ_BATTERY3,
    BATTERY_STATUSSES,
    EXPORT_CONTROL_MODE,
    EXPORT_CONTROL_LIMIT_MODE,
    STOREDGE_CONTROL_MODE,
    STOREDGE_AC_CHARGE_POLICY,
    STOREDGE_CHARGE_DISCHARGE_MODE,
    CONF_MAX_EXPORT_CONTROL_SITE_LIMIT,
    DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT,
)

_LOGGER = logging.getLogger(__name__)

SOLAREDGE_MODBUS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(
            CONF_MODBUS_ADDRESS, default=DEFAULT_MODBUS_ADDRESS
        ): cv.positive_int,
        vol.Optional(CONF_POWER_CONTROL, default=DEFAULT_POWER_CONTROL): cv.boolean,
        vol.Optional(CONF_READ_METER1, default=DEFAULT_READ_METER1): cv.boolean,
        vol.Optional(CONF_READ_METER2, default=DEFAULT_READ_METER2): cv.boolean,
        vol.Optional(CONF_READ_METER3, default=DEFAULT_READ_METER3): cv.boolean,
        vol.Optional(CONF_READ_BATTERY1, default=DEFAULT_READ_BATTERY1): cv.boolean,
        vol.Optional(CONF_READ_BATTERY2, default=DEFAULT_READ_BATTERY2): cv.boolean,
        vol.Optional(CONF_READ_BATTERY3, default=DEFAULT_READ_BATTERY3): cv.boolean,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(
            CONF_MAX_EXPORT_CONTROL_SITE_LIMIT,
            default=DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT,
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
    address = entry.data.get(CONF_MODBUS_ADDRESS, 1)
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    power_control = entry.data.get(CONF_POWER_CONTROL, DEFAULT_POWER_CONTROL),
    read_meter1 = entry.data.get(CONF_READ_METER1, DEFAULT_READ_METER1)
    read_meter2 = entry.data.get(CONF_READ_METER2, DEFAULT_READ_METER2)
    read_meter3 = entry.data.get(CONF_READ_METER3, DEFAULT_READ_METER3)
    read_battery1 = entry.data.get(CONF_READ_BATTERY1, DEFAULT_READ_BATTERY1)
    read_battery2 = entry.data.get(CONF_READ_BATTERY2, DEFAULT_READ_BATTERY2)
    read_battery3 = entry.data.get(CONF_READ_BATTERY3, DEFAULT_READ_BATTERY3)
    max_export_control_site_limit = entry.data.get(
        CONF_MAX_EXPORT_CONTROL_SITE_LIMIT, DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT
    )

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = SolaredgeModbusHub(
        hass,
        name,
        host,
        port,
        address,
        scan_interval,
        power_control,
        read_meter1,
        read_meter2,
        read_meter3,
        read_battery1,
        read_battery2,
        read_battery3,
        max_export_control_site_limit,
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
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
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
        address,
        scan_interval,
        power_control=DEFAULT_POWER_CONTROL,
        read_meter1=DEFAULT_READ_METER1,
        read_meter2=DEFAULT_READ_METER2,
        read_meter3=DEFAULT_READ_METER3,
        read_battery1=DEFAULT_READ_BATTERY1,
        read_battery2=DEFAULT_READ_BATTERY2,
        read_battery3=DEFAULT_READ_BATTERY3,
        max_export_control_site_limit=DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT
    ):
        """Initialize the Modbus hub."""
        self._hass = hass
        self._client = ModbusTcpClient(host=host, port=port, timeout=max(3, (scan_interval - 1)))
        self._lock = threading.Lock()
        self._name = name
        self._address = address
        self.power_control = power_control
        self.read_meter1 = read_meter1
        self.read_meter2 = read_meter2
        self.read_meter3 = read_meter3
        self.read_battery1 = read_battery1
        self.read_battery2 = read_battery2
        self.read_battery3 = read_battery3
        self._scan_interval = timedelta(seconds=scan_interval)
        self.max_export_control_site_limit = max_export_control_site_limit
        self._unsub_interval_method = None
        self._sensors = []
        self.data = {}

    @callback
    def async_add_solaredge_sensor(self, update_callback):
        """Listen for data updates."""
        # This is the first sensor, set up interval.
        if not self._sensors:
           # self.connect()
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

    async def async_refresh_modbus_data(self, _now: Optional[int] = None) -> dict:
        """Time to update."""
        result : bool = await self._hass.async_add_executor_job(self._refresh_modbus_data)
        if result:
            for update_callback in self._sensors:
                update_callback()


    def _refresh_modbus_data(self, _now: Optional[int] = None) -> bool:
        """Time to update."""
        if not self._sensors:
            return False

        if not self._check_and_reconnect():
            #if not connected, skip
            return False

        try:
            update_result = self.read_modbus_data()
        except Exception as e:
            _LOGGER.exception("Error reading modbus data", exc_info=True)
            update_result = False
        return update_result



    @property
    def name(self):
        """Return the name of this hub."""
        return self._name

    def close(self):
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def _check_and_reconnect(self):
        if not self._client.connected:
            _LOGGER.info("modbus client is not connected, trying to reconnect")
            return self.connect()

        return self._client.connected

    def connect(self):
        """Connect client."""
        result = False
        with self._lock:
            result = self._client.connect()

        if result:
            _LOGGER.info("successfully connected to %s:%s",
                         self._client.comm_params.host, self._client.comm_params.port)
        else:
            _LOGGER.warning("not able to connect to %s:%s",
                            self._client.comm_params.host, self._client.comm_params.port)
        return result


    @property
    def power_control_enabled(self):
        """Return true if power control has been enabled"""
        return self.power_control

    @property
    def has_meter(self):
        """Return true if a meter is available"""
        return self.read_meter1 or self.read_meter2 or self.read_meter3

    @property
    def has_battery(self):
        """Return true if a battery is available"""
        return self.read_battery1 or self.read_battery2 or self.read_battery3

    def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        with self._lock:
            return self._client.read_holding_registers(
                address=address, count=count, slave=unit
            )

    def write_registers(self, unit, address, payload):
        """Write registers."""
        with self._lock:
            return self._client.write_registers(
                address=address, values=payload, slave=unit
            )

    def calculate_value(self, value, sf):
        return value * 10**sf

    def read_modbus_data(self):
        return (
            self.read_modbus_data_inverter()
            and self.read_modbus_power_limit()
            and self.read_modbus_data_meter1()
            and self.read_modbus_data_meter2()
            and self.read_modbus_data_meter3()
            and self.read_modbus_data_storage()
            and self.read_modbus_data_battery1()
            and self.read_modbus_data_battery2()
            and self.read_modbus_data_battery3()
        )

    def read_modbus_data_meter1(self):
        if self.read_meter1:
            return self.read_modbus_data_meter("m1_", 40190)
        return True

    def read_modbus_data_meter2(self):
        if self.read_meter2:
            return self.read_modbus_data_meter("m2_", 40364)
        return True

    def read_modbus_data_meter3(self):
        if self.read_meter3:
            return self.read_modbus_data_meter("m3_", 40539)
        return True

    def read_modbus_data_meter(self, meter_prefix, start_address):
        """start reading meter  data"""
        meter_data = self.read_holding_registers(
            unit=self._address, address=start_address, count=103
        )
        if meter_data.isError():
            return False

        decoder = BinaryPayloadDecoder.fromRegisters(
            meter_data.registers, byteorder=Endian.BIG
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

        self.data[meter_prefix + "acvoltageln"] = round(acvoltageln, abs(acvoltagesf))
        self.data[meter_prefix + "acvoltagean"] = round(acvoltagean, abs(acvoltagesf))
        self.data[meter_prefix + "acvoltagebn"] = round(acvoltagebn, abs(acvoltagesf))
        self.data[meter_prefix + "acvoltagecn"] = round(acvoltagecn, abs(acvoltagesf))
        self.data[meter_prefix + "acvoltagell"] = round(acvoltagell, abs(acvoltagesf))
        self.data[meter_prefix + "acvoltageab"] = round(acvoltageab, abs(acvoltagesf))
        self.data[meter_prefix + "acvoltagebc"] = round(acvoltagebc, abs(acvoltagesf))
        self.data[meter_prefix + "acvoltageca"] = round(acvoltageca, abs(acvoltagesf))

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
        self.data[meter_prefix + "exportedvaa"] = round(exportedvaa, abs(energyvasf))
        self.data[meter_prefix + "exportedvab"] = round(exportedvab, abs(energyvasf))
        self.data[meter_prefix + "exportedvac"] = round(exportedvac, abs(energyvasf))
        self.data[meter_prefix + "importedva"] = round(importedva, abs(energyvasf))
        self.data[meter_prefix + "importedvaa"] = round(importedvaa, abs(energyvasf))
        self.data[meter_prefix + "importedvab"] = round(importedvab, abs(energyvasf))
        self.data[meter_prefix + "importedvac"] = round(importedvac, abs(energyvasf))

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

        self.data[meter_prefix + "importvarhq1"] = round(importvarhq1, abs(energyvarsf))
        self.data[meter_prefix + "importvarhq1a"] = round(
            importvarhq1a, abs(energyvarsf)
        )
        self.data[meter_prefix + "importvarhq1b"] = round(
            importvarhq1b, abs(energyvarsf)
        )
        self.data[meter_prefix + "importvarhq1c"] = round(
            importvarhq1c, abs(energyvarsf)
        )
        self.data[meter_prefix + "importvarhq2"] = round(importvarhq2, abs(energyvarsf))
        self.data[meter_prefix + "importvarhq2a"] = round(
            importvarhq2a, abs(energyvarsf)
        )
        self.data[meter_prefix + "importvarhq2b"] = round(
            importvarhq2b, abs(energyvarsf)
        )
        self.data[meter_prefix + "importvarhq2c"] = round(
            importvarhq2c, abs(energyvarsf)
        )
        self.data[meter_prefix + "importvarhq3"] = round(importvarhq3, abs(energyvarsf))
        self.data[meter_prefix + "importvarhq3a"] = round(
            importvarhq3a, abs(energyvarsf)
        )
        self.data[meter_prefix + "importvarhq3b"] = round(
            importvarhq3b, abs(energyvarsf)
        )
        self.data[meter_prefix + "importvarhq3c"] = round(
            importvarhq3c, abs(energyvarsf)
        )
        self.data[meter_prefix + "importvarhq4"] = round(importvarhq4, abs(energyvarsf))
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

    def read_modbus_data_inverter(self):
        inverter_data = self.read_holding_registers(
            unit=self._address, address=40071, count=38
        )
        if inverter_data.isError():
            return False

        decoder = BinaryPayloadDecoder.fromRegisters(
            inverter_data.registers, byteorder=Endian.BIG
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

    def read_modbus_power_limit(self):
        """
        Read the active power limit value (%)
        """

        if not self.power_control_enabled:
            return True

        inverter_data = self.read_holding_registers(
            unit=self._address, address=0xF001, count=1
        )
        if inverter_data.isError():
            _LOGGER.debug("Could not read Active Power Limit")
            # Don't stop reading other data, could just be advanced power management not enabled
            return True

        decoder = BinaryPayloadDecoder.fromRegisters(
            inverter_data.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE
        )
        # 0xF001 - 1 - Active Power Limit
        self.data["nominal_active_power_limit"] = decoder.decode_16bit_uint()

        return True

    def read_modbus_data_storage(self):
        if self.has_battery:
            count = 0x12  # Read storedge block as well
        elif self.has_meter:
            count = 4  # Just read export control block
        else:
            return True  # Nothing to read here

        storage_data = self.read_holding_registers(
            unit=self._address, address=0xE000, count=count
        )
        if not storage_data.isError():
            decoder = BinaryPayloadDecoder.fromRegisters(
                storage_data.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE
            )

            # 0xE000 - 1 - Export control mode
            export_control_mode = decoder.decode_16bit_uint() & 7
            if export_control_mode in EXPORT_CONTROL_MODE:
                self.data["export_control_mode"] = EXPORT_CONTROL_MODE[
                    export_control_mode
                ]
            else:
                self.data["export_control_mode"] = export_control_mode

            # 0xE001 - 1 - Export control limit mode
            export_control_limit_mode = decoder.decode_16bit_uint() & 1
            if export_control_limit_mode in EXPORT_CONTROL_MODE:
                self.data["export_control_limit_mode"] = EXPORT_CONTROL_LIMIT_MODE[
                    export_control_limit_mode
                ]
            else:
                self.data["export_control_limit_mode"] = export_control_limit_mode

            # 0xE002 - 2 - Export control site limit
            self.data["export_control_site_limit"] = round(
                decoder.decode_32bit_float(), 3
            )

            if not self.has_battery:
                # Done with the export control block
                return True

            # 0xE004 - 1 - storage control mode
            storage_control_mode = decoder.decode_16bit_uint()
            if storage_control_mode in STOREDGE_CONTROL_MODE:
                self.data["storage_contol_mode"] = STOREDGE_CONTROL_MODE[
                    storage_control_mode
                ]
            else:
                self.data["storage_contol_mode"] = storage_control_mode

            # 0xE005 - 1 - storage ac charge policy
            storage_ac_charge_policy = decoder.decode_16bit_uint()
            if storage_ac_charge_policy in STOREDGE_AC_CHARGE_POLICY:
                self.data["storage_ac_charge_policy"] = STOREDGE_AC_CHARGE_POLICY[
                    storage_ac_charge_policy
                ]
            else:
                self.data["storage_ac_charge_policy"] = storage_ac_charge_policy

            # 0xE006 - 2 - storage AC charge limit (kWh or %)
            self.data["storage_ac_charge_limit"] = round(
                decoder.decode_32bit_float(), 3
            )

            # 0xE008 - 2 - storage backup reserved capacity (%)
            self.data["storage_backup_reserved"] = round(
                decoder.decode_32bit_float(), 3
            )

            # 0xE00A - 1 - storage charge / discharge default mode
            storage_default_mode = decoder.decode_16bit_uint()
            if storage_default_mode in STOREDGE_CHARGE_DISCHARGE_MODE:
                self.data["storage_default_mode"] = STOREDGE_CHARGE_DISCHARGE_MODE[
                    storage_default_mode
                ]
            else:
                self.data["storage_default_mode"] = storage_default_mode

            # 0xE00B - 2- storage remote command timeout (seconds)
            self.data["storage_remote_command_timeout"] = decoder.decode_32bit_uint()

            # 0xE00D - 1 - storage remote command mode
            storage_remote_command_mode = decoder.decode_16bit_uint()
            if storage_remote_command_mode in STOREDGE_CHARGE_DISCHARGE_MODE:
                self.data[
                    "storage_remote_command_mode"
                ] = STOREDGE_CHARGE_DISCHARGE_MODE[storage_remote_command_mode]
            else:
                self.data["storage_remote_command_mode"] = storage_remote_command_mode

            # 0xE00E - 2- storate remote charge limit
            self.data["storage_remote_charge_limit"] = round(
                decoder.decode_32bit_float(), 3
            )

            # 0xE010 - 2- storate remote discharge limit
            self.data["storage_remote_discharge_limit"] = round(
                decoder.decode_32bit_float(), 3
            )

        return True

    def read_modbus_data_battery1(self):
        if self.read_battery1:
            return self.read_modbus_data_battery("battery1_", 0xE100)
        return True

    def read_modbus_data_battery2(self):
        if self.read_battery2:
            return self.read_modbus_data_battery("battery2_", 0xE200)
        return True
        
    def read_modbus_data_battery3(self):
        if self.read_battery3:
            return self.read_modbus_data_battery("battery3_", 0xE400)
        return True
        
    def read_modbus_data_battery(self, battery_prefix, start_address):
        if not battery_prefix + "attrs" in self.data:
            battery_data = self.read_holding_registers(
                unit=self._address, address=start_address, count=0x4C
            )
            if not battery_data.isError():
                decoder = BinaryPayloadDecoder.fromRegisters(
                    battery_data.registers,
                    byteorder=Endian.BIG,
                    wordorder=Endian.LITTLE,
                )

                def decode_string(decoder):
                    s = decoder.decode_string(32)  # get 32 char string
                    s = s.partition(b"\0")[0]  # omit NULL terminators
                    s = s.decode("utf-8")  # decode UTF-8
                    return str(s)

                battery_info = {}
                # 0x00 - 16 - manufacturer
                battery_info["manufacturer"] = decode_string(decoder)

                # 0x10 - 16 - model
                battery_info["model"] = decode_string(decoder)

                # 0x20 - 16 - firmware version
                battery_info["firmware_version"] = decode_string(decoder)

                # 0x30 - 16 - serial number
                battery_info["serial_number"] = decode_string(decoder)

                # 0x40 - 1 - device ID
                battery_info["device_id"] = decoder.decode_16bit_uint()

                # 0x41 - 1 - reserved
                decoder.decode_16bit_uint()

                # 0x42 - 2 - rated energy
                battery_info["rated_energy"] = decoder.decode_32bit_float()

                # 0x44 - 2 - max charge continuous power
                battery_info[
                    "max_power_continuous_charge"
                ] = decoder.decode_32bit_float()

                # 0x46 - 2 - max discharge continuous power
                battery_info[
                    "max_power_continuous_discharge"
                ] = decoder.decode_32bit_float()

                # 0x48 - 2 - max charge peak power
                battery_info["max_power_peak_charge"] = decoder.decode_32bit_float()  #

                # 0x4A - 2 - max discharge peak power
                battery_info["max_power_peak_discharge"] = decoder.decode_32bit_float()

                self.data[battery_prefix + "attrs"] = battery_info

        storage_data = self.read_holding_registers(
            unit=self._address, address=start_address + 0x6C, count=28
        )
        if storage_data.isError():
            return False

        decoder = BinaryPayloadDecoder.fromRegisters(
            storage_data.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE
        )

        # 0x6C - 2 - avg temp C
        tempavg = decoder.decode_32bit_float()
        # 0x6E - 2 - max temp C
        tempmax = decoder.decode_32bit_float()
        # 0x70 - 2 - inst voltage V
        batteryvoltage = decoder.decode_32bit_float()
        # 0x72 - 2 - inst current A
        batterycurrent = decoder.decode_32bit_float()
        # 0x74 - 2 - inst power W
        batterypower = decoder.decode_32bit_float()
        # 0x76 - 4 - cumulative discharged (Wh)
        cumulative_discharged = decoder.decode_64bit_uint()
        # 0x7a - 4 - cumulative charged (Wh)
        cumulative_charged = decoder.decode_64bit_uint()
        # 0x7E - 2 - current max size Wh
        battery_max = decoder.decode_32bit_float()
        # 0x80 - 2 - available size Wh
        battery_availbable = decoder.decode_32bit_float()
        # 0x82 - 2 - SoH %
        battery_SoH = decoder.decode_32bit_float()
        # 0x84 - 2 - SoC %
        battery_SoC = validate(decoder.decode_32bit_float(), ">=", 0.0)
        battery_SoC = validate(battery_SoC, "<", 101)

        self.data[battery_prefix + "temp_avg"] = round(tempavg, 1)
        self.data[battery_prefix + "temp_max"] = round(tempmax, 1)
        self.data[battery_prefix + "voltage"] = round(batteryvoltage, 3)
        self.data[battery_prefix + "current"] = round(batterycurrent, 3)
        self.data[battery_prefix + "power"] = round(batterypower, 3)
        self.data[battery_prefix + "energy_discharged"] = round(
            cumulative_discharged / 1000, 3
        )
        self.data[battery_prefix + "energy_charged"] = round(
            cumulative_charged / 1000, 3
        )
        self.data[battery_prefix + "size_max"] = round(battery_max, 3)
        self.data[battery_prefix + "size_available"] = round(battery_availbable, 3)
        self.data[battery_prefix + "state_of_health"] = round(battery_SoH, 0)
        self.data[battery_prefix + "state_of_charge"] = round(battery_SoC, 0)
        battery_status = decoder.decode_32bit_uint()

        # voltage and current are bogus in certain statuses
        if not battery_status in [3, 4, 6]:
            self.data[battery_prefix + "voltage"] = 0
            self.data[battery_prefix + "current"] = 0
            self.data[battery_prefix + "power"] = 0

        if battery_status in BATTERY_STATUSSES:
            self.data[battery_prefix + "status"] = BATTERY_STATUSSES[battery_status]
        else:
            self.data[battery_prefix + "status"] = battery_status

        return True
