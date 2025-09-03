"""The SolarEdge Modbus Integration."""

import asyncio
from datetime import timedelta
import logging
import operator
from typing import cast

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    BATTERY_STATUSSES,
    CONF_MAX_EXPORT_CONTROL_SITE_LIMIT,
    CONF_MODBUS_ADDRESS,
    CONF_POWER_CONTROL,
    CONF_READ_BATTERY1,
    CONF_READ_BATTERY2,
    CONF_READ_BATTERY3,
    CONF_READ_METER1,
    CONF_READ_METER2,
    CONF_READ_METER3,
    DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT,
    DEFAULT_MODBUS_ADDRESS,
    DEFAULT_NAME,
    DEFAULT_POWER_CONTROL,
    DEFAULT_READ_BATTERY1,
    DEFAULT_READ_BATTERY2,
    DEFAULT_READ_BATTERY3,
    DEFAULT_READ_METER1,
    DEFAULT_READ_METER2,
    DEFAULT_READ_METER3,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EXPORT_CONTROL_LIMIT_MODE,
    EXPORT_CONTROL_MODE,
    STORAGE_AC_CHARGE_POLICY,
    STORAGE_CHARGE_DISCHARGE_MODE,
    STORAGE_CONTROL_MODE,
)
from .payload import BinaryPayloadDecoder, Endian

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


async def async_setup(hass: HomeAssistant, config):
    """Set up the Solaredge modbus component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a solaredge mobus."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    address = entry.data[CONF_MODBUS_ADDRESS]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    power_control = entry.data[CONF_POWER_CONTROL]
    read_meter1 = entry.data[CONF_READ_METER1]
    read_meter2 = entry.data[CONF_READ_METER2]
    read_meter3 = entry.data[CONF_READ_METER3]
    read_battery1 = entry.data[CONF_READ_BATTERY1]
    read_battery2 = entry.data[CONF_READ_BATTERY2]
    read_battery3 = entry.data[CONF_READ_BATTERY3]
    max_export_control_site_limit = entry.data[CONF_MAX_EXPORT_CONTROL_SITE_LIMIT]

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = SolaredgeModbusHub(host, port, address, scan_interval)
    coordinator = SolaredgeModbusCoordinator(
        hass,
        entry,
        hub,
        name,
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
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][name] = {"hub": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload Solaredge mobus entry."""
    coordinator: SolaredgeModbusCoordinator = hass.data[DOMAIN][entry.data["name"]][
        "hub"
    ]
    await coordinator.hub.close()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.data["name"])

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry, device_entry
) -> bool:
    """Remove a config entry from a device."""
    return True


async def async_migrate_entry(hass, config_entry):
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        address = config_entry.data.get(CONF_MODBUS_ADDRESS, 1)
        scan_interval = config_entry.data[CONF_SCAN_INTERVAL]

        # Update unique id to use serial number
        hub = SolaredgeModbusHub(host, port, address, scan_interval)
        if not await hub.check_and_reconnect():
            _LOGGER.error("Failed to connect to hub")
            return False

        if not await hub.read_device_info():
            _LOGGER.error("Failed to read device info")
            return False

        new_unique_id = hub.device_info["serial_number"]
        if existing_entity_id := hass.config_entries.async_entry_for_domain_unique_id(
            config_entry.domain, new_unique_id
        ):
            _LOGGER.error(
                "Cannot migrate to unique_id '%s', already exists for '%s', "
                "You may have to delete unavailable solaredge modbus entities",
                new_unique_id,
                existing_entity_id,
            )
            return False

        # Set config entry data which may not be present in older versions.
        data = {**config_entry.data}
        data[CONF_MODBUS_ADDRESS] = address
        data[CONF_POWER_CONTROL] = config_entry.data.get(CONF_POWER_CONTROL, False)
        data[CONF_READ_METER1] = config_entry.data.get(CONF_READ_METER1, False)
        data[CONF_READ_METER2] = config_entry.data.get(CONF_READ_METER2, False)
        data[CONF_READ_METER3] = config_entry.data.get(CONF_READ_METER3, False)
        data[CONF_READ_BATTERY1] = config_entry.data.get(CONF_READ_BATTERY1, False)
        data[CONF_READ_BATTERY2] = config_entry.data.get(CONF_READ_BATTERY2, False)
        data[CONF_READ_BATTERY3] = config_entry.data.get(CONF_READ_BATTERY3, False)
        data[CONF_MAX_EXPORT_CONTROL_SITE_LIMIT] = config_entry.data.get(
            CONF_MAX_EXPORT_CONTROL_SITE_LIMIT, False
        )

        if not hass.config_entries.async_update_entry(
            config_entry, unique_id=new_unique_id, data=data, version=2
        ):
            _LOGGER.error("Failed to update config entry")
            return False

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


def validate(value, comparison, against):
    """Validate value."""
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
        host,
        port,
        address,
        scan_interval,
    ) -> None:
        """Initialize the Modbus hub."""
        self._client = None
        self._host = host
        self._port = port
        self._timeout = max(3, (scan_interval - 1))
        self._lock = asyncio.Lock()
        self._address = address

        self.modbus_data = {}
        self.device_info = {}

    def get_unit(self) -> int:
        """Get the configured unit."""
        return cast(int, self._address)

    async def close(self):
        """Disconnect client."""
        if self._client is None:
            return

        async with self._lock:
            self._client.close()
            self._client = None

    async def check_and_reconnect(self):
        if self._client is None:
            self._client = AsyncModbusTcpClient(
                host=self._host, port=self._port, timeout=self._timeout
            )
        if not self._client.connected:
            _LOGGER.info("Modbus client is not connected, trying to reconnect")
            return await self.connect()

        return self._client.connected

    async def connect(self):
        """Connect client."""
        async with self._lock:
            result = await self._client.connect()

        if result:
            _LOGGER.info(
                "Successfully connected to %s:%s",
                self._client.comm_params.host,
                self._client.comm_params.port,
            )
        else:
            _LOGGER.warning(
                "Not able to connect to %s:%s",
                self._client.comm_params.host,
                self._client.comm_params.port,
            )
        return result

    async def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        async with self._lock:
            return await self._client.read_holding_registers(
                address=address, count=count, device_id=unit
            )

    async def write_registers(self, unit, address, payload):
        """Write registers."""
        try:
            async with self._lock:
                return await self._client.write_registers(
                    address=address, values=payload, device_id=unit
                )
        except ModbusException as err:
            raise HomeAssistantError(err) from err

    async def write_register(self, unit, address, payload):
        """Write register."""
        try:
            async with self._lock:
                return await self._client.write_register(
                    address=address, value=payload, device_id=unit
                )
        except ModbusException as err:
            raise HomeAssistantError(err) from err

    def calculate_value(self, value, sf):
        """Calculate a value using scaling factor."""
        return round(value * 10**sf, max(0, -sf))

    async def read_device_info(self):
        data = await self.read_holding_registers(
            unit=self._address, address=40004, count=64
        )
        if data.isError():
            return False

        decoder = BinaryPayloadDecoder.fromRegisters(
            data.registers, byteorder=Endian.BIG
        )

        manufacturer = decoder.decode_string(size=32)
        model = decoder.decode_string(size=32)
        decoder.skip_bytes(16)
        version = decoder.decode_string(size=16)
        serial_number = decoder.decode_string(size=32)

        self.device_info = {
            "manufacturer": manufacturer,
            "model": model,
            "version": version,
            "serial_number": serial_number,
        }

        return True

    async def read_modbus_data_meter1(self):
        """Read meter 1 modbus data."""
        return await self.read_modbus_data_meter("m1_", 40190)

    async def read_modbus_data_meter2(self):
        """Read meter 2 modbus data."""
        return await self.read_modbus_data_meter("m2_", 40364)

    async def read_modbus_data_meter3(self):
        """Read meter 3 modbus data."""
        return await self.read_modbus_data_meter("m3_", 40539)

    async def read_modbus_data_meter(self, meter_prefix, start_address):
        """Start reading meter  data."""
        meter_data = await self.read_holding_registers(
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

        self.modbus_data[meter_prefix + "accurrent"] = accurrent
        self.modbus_data[meter_prefix + "accurrenta"] = accurrenta
        self.modbus_data[meter_prefix + "accurrentb"] = accurrentb
        self.modbus_data[meter_prefix + "accurrentc"] = accurrentc

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

        self.modbus_data[meter_prefix + "acvoltageln"] = acvoltageln
        self.modbus_data[meter_prefix + "acvoltagean"] = acvoltagean
        self.modbus_data[meter_prefix + "acvoltagebn"] = acvoltagebn
        self.modbus_data[meter_prefix + "acvoltagecn"] = acvoltagecn
        self.modbus_data[meter_prefix + "acvoltagell"] = acvoltagell
        self.modbus_data[meter_prefix + "acvoltageab"] = acvoltageab
        self.modbus_data[meter_prefix + "acvoltagebc"] = acvoltagebc
        self.modbus_data[meter_prefix + "acvoltageca"] = acvoltageca

        acfreq = decoder.decode_16bit_int()
        acfreqsf = decoder.decode_16bit_int()

        acfreq = self.calculate_value(acfreq, acfreqsf)

        self.modbus_data[meter_prefix + "acfreq"] = acfreq

        acpower = decoder.decode_16bit_int()
        acpowera = decoder.decode_16bit_int()
        acpowerb = decoder.decode_16bit_int()
        acpowerc = decoder.decode_16bit_int()
        acpowersf = decoder.decode_16bit_int()

        acpower = self.calculate_value(acpower, acpowersf)
        acpowera = self.calculate_value(acpowera, acpowersf)
        acpowerb = self.calculate_value(acpowerb, acpowersf)
        acpowerc = self.calculate_value(acpowerc, acpowersf)

        self.modbus_data[meter_prefix + "acpower"] = acpower
        self.modbus_data[meter_prefix + "acpowera"] = acpowera
        self.modbus_data[meter_prefix + "acpowerb"] = acpowerb
        self.modbus_data[meter_prefix + "acpowerc"] = acpowerc

        acva = decoder.decode_16bit_int()
        acvaa = decoder.decode_16bit_int()
        acvab = decoder.decode_16bit_int()
        acvac = decoder.decode_16bit_int()
        acvasf = decoder.decode_16bit_int()

        acva = self.calculate_value(acva, acvasf)
        acvaa = self.calculate_value(acvaa, acvasf)
        acvab = self.calculate_value(acvab, acvasf)
        acvac = self.calculate_value(acvac, acvasf)

        self.modbus_data[meter_prefix + "acva"] = acva
        self.modbus_data[meter_prefix + "acvaa"] = acvaa
        self.modbus_data[meter_prefix + "acvab"] = acvab
        self.modbus_data[meter_prefix + "acvac"] = acvac

        acvar = decoder.decode_16bit_int()
        acvara = decoder.decode_16bit_int()
        acvarb = decoder.decode_16bit_int()
        acvarc = decoder.decode_16bit_int()
        acvarsf = decoder.decode_16bit_int()

        acvar = self.calculate_value(acvar, acvarsf)
        acvara = self.calculate_value(acvara, acvarsf)
        acvarb = self.calculate_value(acvarb, acvarsf)
        acvarc = self.calculate_value(acvarc, acvarsf)

        self.modbus_data[meter_prefix + "acvar"] = acvar
        self.modbus_data[meter_prefix + "acvara"] = acvara
        self.modbus_data[meter_prefix + "acvarb"] = acvarb
        self.modbus_data[meter_prefix + "acvarc"] = acvarc

        acpf = decoder.decode_16bit_int()
        acpfa = decoder.decode_16bit_int()
        acpfb = decoder.decode_16bit_int()
        acpfc = decoder.decode_16bit_int()
        acpfsf = decoder.decode_16bit_int()

        acpf = self.calculate_value(acpf, acpfsf)
        acpfa = self.calculate_value(acpfa, acpfsf)
        acpfb = self.calculate_value(acpfb, acpfsf)
        acpfc = self.calculate_value(acpfc, acpfsf)

        self.modbus_data[meter_prefix + "acpf"] = acpf
        self.modbus_data[meter_prefix + "acpfa"] = acpfa
        self.modbus_data[meter_prefix + "acpfb"] = acpfb
        self.modbus_data[meter_prefix + "acpfc"] = acpfc

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

        self.modbus_data[meter_prefix + "exported"] = round(exported * 0.001, 3)
        self.modbus_data[meter_prefix + "exporteda"] = round(exporteda * 0.001, 3)
        self.modbus_data[meter_prefix + "exportedb"] = round(exportedb * 0.001, 3)
        self.modbus_data[meter_prefix + "exportedc"] = round(exportedc * 0.001, 3)
        self.modbus_data[meter_prefix + "imported"] = round(imported * 0.001, 3)
        self.modbus_data[meter_prefix + "importeda"] = round(importeda * 0.001, 3)
        self.modbus_data[meter_prefix + "importedb"] = round(importedb * 0.001, 3)
        self.modbus_data[meter_prefix + "importedc"] = round(importedc * 0.001, 3)

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

        self.modbus_data[meter_prefix + "exportedva"] = exportedva
        self.modbus_data[meter_prefix + "exportedvaa"] = exportedvaa
        self.modbus_data[meter_prefix + "exportedvab"] = exportedvab
        self.modbus_data[meter_prefix + "exportedvac"] = exportedvac
        self.modbus_data[meter_prefix + "importedva"] = importedva
        self.modbus_data[meter_prefix + "importedvaa"] = importedvaa
        self.modbus_data[meter_prefix + "importedvab"] = importedvab
        self.modbus_data[meter_prefix + "importedvac"] = importedvac

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

        self.modbus_data[meter_prefix + "importvarhq1"] = importvarhq1
        self.modbus_data[meter_prefix + "importvarhq1a"] = importvarhq1a
        self.modbus_data[meter_prefix + "importvarhq1b"] = importvarhq1b
        self.modbus_data[meter_prefix + "importvarhq1c"] = importvarhq1c
        self.modbus_data[meter_prefix + "importvarhq2"] = importvarhq2
        self.modbus_data[meter_prefix + "importvarhq2a"] = importvarhq2a
        self.modbus_data[meter_prefix + "importvarhq2b"] = importvarhq2b
        self.modbus_data[meter_prefix + "importvarhq2c"] = importvarhq2c
        self.modbus_data[meter_prefix + "importvarhq3"] = importvarhq3
        self.modbus_data[meter_prefix + "importvarhq3a"] = importvarhq3a
        self.modbus_data[meter_prefix + "importvarhq3b"] = importvarhq3b
        self.modbus_data[meter_prefix + "importvarhq3c"] = importvarhq3c
        self.modbus_data[meter_prefix + "importvarhq4"] = importvarhq4
        self.modbus_data[meter_prefix + "importvarhq4a"] = importvarhq4a
        self.modbus_data[meter_prefix + "importvarhq4b"] = importvarhq4b
        self.modbus_data[meter_prefix + "importvarhq4c"] = importvarhq4c

        return True

    async def read_modbus_data_inverter(self):
        """Read inverter data."""
        inverter_data = await self.read_holding_registers(
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

        self.modbus_data["accurrent"] = accurrent
        self.modbus_data["accurrenta"] = accurrenta
        self.modbus_data["accurrentb"] = accurrentb
        self.modbus_data["accurrentc"] = accurrentc

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

        self.modbus_data["acvoltageab"] = acvoltageab
        self.modbus_data["acvoltagebc"] = acvoltagebc
        self.modbus_data["acvoltageca"] = acvoltageca
        self.modbus_data["acvoltagean"] = acvoltagean
        self.modbus_data["acvoltagebn"] = acvoltagebn
        self.modbus_data["acvoltagecn"] = acvoltagecn

        acpower = decoder.decode_16bit_int()
        acpowersf = decoder.decode_16bit_int()
        acpower = self.calculate_value(acpower, acpowersf)

        self.modbus_data["acpower"] = acpower

        acfreq = decoder.decode_16bit_uint()
        acfreqsf = decoder.decode_16bit_int()
        acfreq = self.calculate_value(acfreq, acfreqsf)

        self.modbus_data["acfreq"] = acfreq

        acva = decoder.decode_16bit_int()
        acvasf = decoder.decode_16bit_int()
        acva = self.calculate_value(acva, acvasf)

        self.modbus_data["acva"] = acva

        acvar = decoder.decode_16bit_int()
        acvarsf = decoder.decode_16bit_int()
        acvar = self.calculate_value(acvar, acvarsf)

        self.modbus_data["acvar"] = acvar

        acpf = decoder.decode_16bit_int()
        acpfsf = decoder.decode_16bit_int()
        acpf = self.calculate_value(acpf, acpfsf)

        self.modbus_data["acpf"] = acpf

        acenergy = decoder.decode_32bit_uint()
        acenergysf = decoder.decode_16bit_uint()
        acenergy = validate(self.calculate_value(acenergy, acenergysf), ">", 0)

        self.modbus_data["acenergy"] = round(acenergy * 0.001, 3)

        dccurrent = decoder.decode_16bit_uint()
        dccurrentsf = decoder.decode_16bit_int()
        dccurrent = self.calculate_value(dccurrent, dccurrentsf)

        self.modbus_data["dccurrent"] = dccurrent

        dcvoltage = decoder.decode_16bit_uint()
        dcvoltagesf = decoder.decode_16bit_int()
        dcvoltage = self.calculate_value(dcvoltage, dcvoltagesf)

        self.modbus_data["dcvoltage"] = dcvoltage

        dcpower = decoder.decode_16bit_int()
        dcpowersf = decoder.decode_16bit_int()
        dcpower = self.calculate_value(dcpower, dcpowersf)

        self.modbus_data["dcpower"] = dcpower

        # skip register
        decoder.skip_bytes(2)

        tempsink = decoder.decode_16bit_int()

        # skip 2 registers
        decoder.skip_bytes(4)

        tempsf = decoder.decode_16bit_int()
        tempsink = self.calculate_value(tempsink, tempsf)

        self.modbus_data["tempsink"] = tempsink

        status = decoder.decode_16bit_int()
        self.modbus_data["status"] = status
        statusvendor = decoder.decode_16bit_int()
        self.modbus_data["statusvendor"] = statusvendor

        return True

    async def read_modbus_power_limit(self):
        """Read the active power limit value (%)."""

        inverter_data = await self.read_holding_registers(
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
        self.modbus_data["nominal_active_power_limit"] = decoder.decode_16bit_uint()

        return True

    async def read_modbus_data_storage(self, has_battery, has_meter):
        """Read storage data."""
        if has_battery:
            count = 0x12  # Read storage block as well
        elif has_meter:
            count = 4  # Just read export control block
        else:
            return True  # Nothing to read here

        storage_data = await self.read_holding_registers(
            unit=self._address, address=0xE000, count=count
        )
        if not storage_data.isError():
            decoder = BinaryPayloadDecoder.fromRegisters(
                storage_data.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE
            )

            # 0xE000 - 1 - Export control mode
            export_control_mode = decoder.decode_16bit_uint() & 7
            if export_control_mode in EXPORT_CONTROL_MODE:
                self.modbus_data["export_control_mode"] = EXPORT_CONTROL_MODE[
                    export_control_mode
                ]
            else:
                self.modbus_data["export_control_mode"] = export_control_mode

            # 0xE001 - 1 - Export control limit mode
            export_control_limit_mode = decoder.decode_16bit_uint() & 1
            if export_control_limit_mode in EXPORT_CONTROL_MODE:
                self.modbus_data["export_control_limit_mode"] = (
                    EXPORT_CONTROL_LIMIT_MODE[export_control_limit_mode]
                )
            else:
                self.modbus_data["export_control_limit_mode"] = (
                    export_control_limit_mode
                )

            # 0xE002 - 2 - Export control site limit
            self.modbus_data["export_control_site_limit"] = round(
                decoder.decode_32bit_float(), 3
            )

            if not has_battery:
                # Done with the export control block
                return True

            # 0xE004 - 1 - storage control mode
            storage_control_mode = decoder.decode_16bit_uint()
            if storage_control_mode in STORAGE_CONTROL_MODE:
                self.modbus_data["storage_contol_mode"] = STORAGE_CONTROL_MODE[
                    storage_control_mode
                ]
            else:
                self.modbus_data["storage_contol_mode"] = storage_control_mode

            # 0xE005 - 1 - storage ac charge policy
            storage_ac_charge_policy = decoder.decode_16bit_uint()
            if storage_ac_charge_policy in STORAGE_AC_CHARGE_POLICY:
                self.modbus_data["storage_ac_charge_policy"] = STORAGE_AC_CHARGE_POLICY[
                    storage_ac_charge_policy
                ]
            else:
                self.modbus_data["storage_ac_charge_policy"] = storage_ac_charge_policy

            # 0xE006 - 2 - storage AC charge limit (kWh or %)
            self.modbus_data["storage_ac_charge_limit"] = round(
                decoder.decode_32bit_float(), 3
            )

            # 0xE008 - 2 - storage backup reserved capacity (%)
            self.modbus_data["storage_backup_reserved"] = round(
                decoder.decode_32bit_float(), 3
            )

            # 0xE00A - 1 - storage charge / discharge default mode
            storage_default_mode = decoder.decode_16bit_uint()
            if storage_default_mode in STORAGE_CHARGE_DISCHARGE_MODE:
                self.modbus_data["storage_default_mode"] = (
                    STORAGE_CHARGE_DISCHARGE_MODE[storage_default_mode]
                )
            else:
                self.modbus_data["storage_default_mode"] = storage_default_mode

            # 0xE00B - 2- storage remote command timeout (seconds)
            self.modbus_data["storage_remote_command_timeout"] = (
                decoder.decode_32bit_uint()
            )

            # 0xE00D - 1 - storage remote command mode
            storage_remote_command_mode = decoder.decode_16bit_uint()
            if storage_remote_command_mode in STORAGE_CHARGE_DISCHARGE_MODE:
                self.modbus_data["storage_remote_command_mode"] = (
                    STORAGE_CHARGE_DISCHARGE_MODE[storage_remote_command_mode]
                )
            else:
                self.modbus_data["storage_remote_command_mode"] = (
                    storage_remote_command_mode
                )

            # 0xE00E - 2- storate remote charge limit
            self.modbus_data["storage_remote_charge_limit"] = round(
                decoder.decode_32bit_float(), 3
            )

            # 0xE010 - 2- storate remote discharge limit
            self.modbus_data["storage_remote_discharge_limit"] = round(
                decoder.decode_32bit_float(), 3
            )

        return True

    async def read_modbus_data_battery1(self):
        """Read battery 1."""
        return await self.read_modbus_data_battery("battery1_", 0xE100)

    async def read_modbus_data_battery2(self):
        """Read battery 2."""
        return await self.read_modbus_data_battery("battery2_", 0xE200)

    async def read_modbus_data_battery3(self):
        """Read battery 3."""
        return await self.read_modbus_data_battery("battery3_", 0xE400)

    async def read_modbus_data_battery(self, battery_prefix, start_address):
        """Read battery data."""
        if battery_prefix + "attrs" not in self.modbus_data:
            battery_data = await self.read_holding_registers(
                unit=self._address, address=start_address, count=0x4C
            )
            if not battery_data.isError():
                decoder = BinaryPayloadDecoder.fromRegisters(
                    battery_data.registers,
                    byteorder=Endian.BIG,
                    wordorder=Endian.LITTLE,
                )

                battery_info = {}
                # 0x00 - 16 - manufacturer
                battery_info["manufacturer"] = decoder.decode_string(32)

                # 0x10 - 16 - model
                battery_info["model"] = decoder.decode_string(32)

                # 0x20 - 16 - firmware version
                battery_info["firmware_version"] = decoder.decode_string(32)

                # 0x30 - 16 - serial number
                battery_info["serial_number"] = decoder.decode_string(32)

                # 0x40 - 1 - device ID
                battery_info["device_id"] = decoder.decode_16bit_uint()

                # 0x41 - 1 - reserved
                decoder.decode_16bit_uint()

                # 0x42 - 2 - rated energy
                battery_info["rated_energy"] = decoder.decode_32bit_float()

                # 0x44 - 2 - max charge continuous power
                battery_info["max_power_continuous_charge"] = (
                    decoder.decode_32bit_float()
                )

                # 0x46 - 2 - max discharge continuous power
                battery_info["max_power_continuous_discharge"] = (
                    decoder.decode_32bit_float()
                )

                # 0x48 - 2 - max charge peak power
                battery_info["max_power_peak_charge"] = decoder.decode_32bit_float()

                # 0x4A - 2 - max discharge peak power
                battery_info["max_power_peak_discharge"] = decoder.decode_32bit_float()

                self.modbus_data[battery_prefix + "attrs"] = battery_info

        storage_data = await self.read_holding_registers(
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

        self.modbus_data[battery_prefix + "temp_avg"] = round(tempavg, 1)
        self.modbus_data[battery_prefix + "temp_max"] = round(tempmax, 1)
        self.modbus_data[battery_prefix + "voltage"] = round(batteryvoltage, 3)
        self.modbus_data[battery_prefix + "current"] = round(batterycurrent, 3)
        self.modbus_data[battery_prefix + "power"] = round(batterypower, 3)
        self.modbus_data[battery_prefix + "energy_discharged"] = round(
            cumulative_discharged / 1000, 3
        )
        self.modbus_data[battery_prefix + "energy_charged"] = round(
            cumulative_charged / 1000, 3
        )
        self.modbus_data[battery_prefix + "size_max"] = round(battery_max, 3)
        self.modbus_data[battery_prefix + "size_available"] = round(
            battery_availbable, 3
        )
        self.modbus_data[battery_prefix + "state_of_health"] = round(battery_SoH, 0)
        self.modbus_data[battery_prefix + "state_of_charge"] = round(battery_SoC, 0)
        battery_status = decoder.decode_32bit_uint()

        # voltage and current are bogus in certain statuses
        if battery_status not in [3, 4, 6]:
            self.modbus_data[battery_prefix + "voltage"] = 0
            self.modbus_data[battery_prefix + "current"] = 0
            self.modbus_data[battery_prefix + "power"] = 0

        if battery_status in BATTERY_STATUSSES:
            self.modbus_data[battery_prefix + "status"] = BATTERY_STATUSSES[
                battery_status
            ]
        else:
            self.modbus_data[battery_prefix + "status"] = battery_status

        return True


class SolaredgeModbusCoordinator(DataUpdateCoordinator):
    """Thread safe wrapper class for pymodbus."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hub: SolaredgeModbusHub,
        name,
        scan_interval,
        power_control=False,
        read_meter1=False,
        read_meter2=False,
        read_meter3=False,
        read_battery1=False,
        read_battery2=False,
        read_battery3=False,
        max_export_control_site_limit=False,
    ) -> None:
        """Initialize the Modbus hub."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.hub = hub
        self.power_control_enabled = power_control
        self.read_meter1 = read_meter1
        self.read_meter2 = read_meter2
        self.read_meter3 = read_meter3
        self.read_battery1 = read_battery1
        self.read_battery2 = read_battery2
        self.read_battery3 = read_battery3
        self.max_export_control_site_limit = max_export_control_site_limit

    @property
    def modbus_data(self):
        return self.hub.modbus_data

    @property
    def device_info(self):
        return self.hub.device_info

    async def _async_setup(self):
        """Initialize device information."""
        if not await self.hub.check_and_reconnect():
            raise UpdateFailed("Unable to connect")
        if not await self.hub.read_device_info():
            raise UpdateFailed("Unable to read serial number")

    async def _async_update_data(self) -> dict:
        """Time to update."""
        if not await self.hub.check_and_reconnect():
            raise UpdateFailed("Unable to connect")

        try:
            update_succeeded = await self.read_modbus_data()
        except Exception as error:
            await self.hub.close()
            raise UpdateFailed(error) from error

        if not update_succeeded:
            raise UpdateFailed("Modbus update failed")

        return self.modbus_data

    async def read_modbus_data(self):
        """Read all modbus data."""
        return (
            await self.hub.read_modbus_data_inverter()
            and (
                not self.power_control_enabled
                or await self.hub.read_modbus_power_limit()
            )
            and (not self.read_meter1 or await self.hub.read_modbus_data_meter1())
            and (not self.read_meter2 or await self.hub.read_modbus_data_meter2())
            and (not self.read_meter2 or await self.hub.read_modbus_data_meter3())
            and await self.hub.read_modbus_data_storage(
                self.has_battery, self.has_meter
            )
            and (not self.read_battery1 or await self.hub.read_modbus_data_battery1())
            and (not self.read_battery2 or await self.hub.read_modbus_data_battery2())
            and (not self.read_battery3 or await self.hub.read_modbus_data_battery3())
        )

    @property
    def has_meter(self):
        """Return true if a meter is available."""
        return self.read_meter1 or self.read_meter2 or self.read_meter3

    @property
    def has_battery(self):
        """Return true if a battery is available."""
        return self.read_battery1 or self.read_battery2 or self.read_battery3


class SolarEdgeEntity(CoordinatorEntity):
    """Representation of a solaredge entity."""

    def __init__(self, hub: SolaredgeModbusCoordinator) -> None:
        """Init SolarEdgeEntity."""
        super().__init__(hub)
        self.hub = hub
        self._attr_device_info = DeviceInfo(
            name=hub.name,
            identifiers={(DOMAIN, hub.device_info["serial_number"])},
            manufacturer=hub.device_info["manufacturer"],
            model=hub.device_info["model"],
            serial_number=hub.device_info["serial_number"],
            sw_version=hub.device_info["version"],
        )
