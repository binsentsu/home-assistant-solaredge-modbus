"""Constants and entity descriptions for solardedge modbus integration."""

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_SECONDS,
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
)

DOMAIN = "solaredge_modbus"
DEFAULT_NAME = "solaredge"
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_PORT = 1502
DEFAULT_MODBUS_ADDRESS = 1
DEFAULT_POWER_CONTROL = False
DEFAULT_READ_METER1 = False
DEFAULT_READ_METER2 = False
DEFAULT_READ_METER3 = False
DEFAULT_READ_BATTERY1 = False
DEFAULT_READ_BATTERY2 = False
DEFAULT_READ_BATTERY3 = False
CONF_SOLAREDGE_HUB = "solaredge_hub"
ATTR_STATUS_DESCRIPTION = "status_description"
CONF_MODBUS_ADDRESS = "modbus_address"
CONF_POWER_CONTROL = "power_control"
CONF_READ_METER1 = "read_meter_1"
CONF_READ_METER2 = "read_meter_2"
CONF_READ_METER3 = "read_meter_3"
CONF_READ_BATTERY1 = "read_battery_1"
CONF_READ_BATTERY2 = "read_battery_2"
CONF_READ_BATTERY3 = "read_battery_3"
CONF_MAX_EXPORT_CONTROL_SITE_LIMIT = "max_export_control_site_limit"
DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT = 10000
METER_1 = "m1"
METER_2 = "m2"
METER_3 = "m3"
BATTERY_1 = "battery1"
BATTERY_2 = "battery2"
BATTERY_3 = "battery3"

ENERGY_VOLT_AMPERE_HOUR: Final = "VAh"
ENERGY_VOLT_AMPERE_REACTIVE_HOUR: Final = "varh"


@dataclass
class SolarEdgeNumberDescriptionMixin:
    """Define an entity description mixin for number entities."""

    register: Any
    fmt: str
    attrs: dict


@dataclass
class SolarEdgeNumberDescription(
    NumberEntityDescription, SolarEdgeNumberDescriptionMixin
):
    """Class to describe an solaredge select entity."""


@dataclass
class SolarEdgeSelectDescriptionMixin:
    """Define an entity description mixin for select entities."""

    register: Any
    options_dict: dict[int, str]


@dataclass
class SolarEdgeSelectDescription(
    SelectEntityDescription, SolarEdgeSelectDescriptionMixin
):
    """Class to describe an solaredge select entity."""


INVERTER_CURRENT_TYPES: dict = {
    "accurrent": "AC Current",
    "accurrenta": "AC Current A",
    "accurrentb": "AC Current B",
    "accurrentc": "AC Current C",
    "dccurrent": "DC Current",
}

INVERTER_VOLTAGE_TYPES: dict = {
    "acvoltageab": "AC Voltage AB",
    "acvoltagebc": "AC Voltage BC",
    "acvoltageca": "AC Voltage CA",
    "acvoltagean": "AC Voltage AN",
    "acvoltagebn": "AC Voltage BN",
    "acvoltagecn": "AC Voltage CN",
    "dcvoltage": "DC Voltage",
}

INVERTER_POWER_TYPES: dict = {
    "acpower": "AC Power",
    "dcpower": "DC Power",
}

INVERTER_SENSORS: list[SensorEntityDescription] = []

for key, value in INVERTER_CURRENT_TYPES.items():
    INVERTER_SENSORS.append(
        SensorEntityDescription(
            key=key,
            name=value,
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
        )
    )

for key, value in INVERTER_VOLTAGE_TYPES.items():
    INVERTER_SENSORS.append(
        SensorEntityDescription(
            key=key,
            name=value,
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    )

for key, value in INVERTER_POWER_TYPES.items():
    INVERTER_SENSORS.append(
        SensorEntityDescription(
            key=key,
            name=value,
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
        )
    )

INVERTER_SENSORS.extend(
    [
        SensorEntityDescription(
            key="acfreq",
            name="AC Frequency",
            device_class=SensorDeviceClass.FREQUENCY,
            native_unit_of_measurement=UnitOfFrequency.HERTZ,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="acva",
            name="AC VA",
            device_class=SensorDeviceClass.APPARENT_POWER,
            native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="acvar",
            name="AC VAR",
            device_class=SensorDeviceClass.REACTIVE_POWER,
            native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="acpf",
            name="AC PF",
            device_class=SensorDeviceClass.POWER_FACTOR,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="acenergy",
            name="AC Energy kWh",
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SensorEntityDescription(
            key="tempsink",
            name="Temp Sink",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="status",
            name="Status",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="statusvendor",
            name="Status Vendor",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ]
)


METER_CURRENT_TYPES = {
    "accurrent": "AC Current",
    "accurrenta": "AC Current_A",
    "accurrentb": "AC Current_B",
    "accurrentc": "AC Current_C",
}

METER_VOLTAGE_TYPES = {
    "acvoltageln": "AC Voltage LN",
    "acvoltagean": "AC Voltage AN",
    "acvoltagebn": "AC Voltage BN",
    "acvoltagecn": "AC Voltage CN",
    "acvoltagell": "AC Voltage LL",
    "acvoltageab": "AC Voltage AB",
    "acvoltagebc": "AC Voltage BC",
    "acvoltageca": "AC Voltage CA",
}

METER_POWER_TYPES = {
    "acpower": "AC Power",
    "acpowera": "AC Power A",
    "acpowerb": "AC Power B",
    "acpowerc": "AC Power C",
}

METER_VA_TYPES = {
    "acva": "AC VA",
    "acvaa": "AC VA A",
    "acvab": "AC VA B",
    "acvac": "AC VA C",
}

METER_VAR_TYPES = {
    "acvar": "AC VAR",
    "acvara": "AC VAR A",
    "acvarb": "AC VAR B",
    "acvarc": "AC VAR C",
}

METER_PF_TYPES = {
    "acpf": "AC PF",
    "acpfa": "AC PF A",
    "acpfb": "AC PF B",
    "acpfc": "AC PF C",
}

METER_KWH_TYPES = {
    "exported": "EXPORTED KWH",
    "exporteda": "EXPORTED A KWH",
    "exportedb": "EXPORTED B KWH",
    "exportedc": "EXPORTED C KWH",
    "imported": "IMPORTED KWH",
    "importeda": "IMPORTED A KWH",
    "importedb": "IMPORTED B KWH",
    "importedc": "IMPORTED C KWH",
}

METER_VAH_TYPES = {
    "exportedva": "EXPORTED VAh",
    "exportedvaa": "EXPORTED A VAh",
    "exportedvab": "EXPORTED B VAh",
    "exportedvac": "EXPORTED C VAh",
    "importedva": "IMPORTED VAh",
    "importedvaa": "IMPORTED A VAh",
    "importedvab": "IMPORTED B VAh",
    "importedvac": "IMPORTED C VAh",
}

METER_VARH_TYPES = {
    "importvarhq1": "IMPORT VARH Q1",
    "importvarhq1a": "IMPORT VARH Q1 A",
    "importvarhq1b": "IMPORT VARH Q1 B",
    "importvarhq1c": "IMPORT VARH Q1 C",
    "importvarhq2": "IMPORT VARH Q2",
    "importvarhq2a": "IMPORT VARH Q2 A",
    "importvarhq2b": "IMPORT VARH Q2 B",
    "importvarhq2c": "IMPORT VARH Q2 C",
    "importvarhq3": "IMPORT VARH Q3",
    "importvarhq3a": "IMPORT VARH Q3 A",
    "importvarhq3b": "IMPORT VARH Q3 B",
    "importvarhq3c": "IMPORT VARH Q3 C",
    "importvarhq4": "IMPORT VARH Q4",
    "importvarhq4a": "IMPORT VARH Q4 A",
    "importvarhq4b": "IMPORT VARH Q4 B",
    "importvarhq4c": "IMPORT VARH Q4 C",
}


METERS = {METER_1: [], METER_2: [], METER_3: []}

for key, value in METER_CURRENT_TYPES.items():
    for meterKey, meterList in METERS.items():
        meterList.append(
            SensorEntityDescription(
                key=meterKey + "_" + key,
                name=meterKey.upper() + " " + value,
                device_class=SensorDeviceClass.CURRENT,
                native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

for key, value in METER_VOLTAGE_TYPES.items():
    for meterKey, meterList in METERS.items():
        meterList.append(
            SensorEntityDescription(
                key=meterKey + "_" + key,
                name=meterKey.upper() + " " + value,
                device_class=SensorDeviceClass.VOLTAGE,
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )


for key, value in METER_POWER_TYPES.items():
    for meterKey, meterList in METERS.items():
        meterList.append(
            SensorEntityDescription(
                key=meterKey + "_" + key,
                name=meterKey.upper() + " " + value,
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement=UnitOfPower.WATT,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

for key, value in METER_VA_TYPES.items():
    for meterKey, meterList in METERS.items():
        meterList.append(
            SensorEntityDescription(
                key=meterKey + "_" + key,
                name=meterKey.upper() + " " + value,
                device_class=SensorDeviceClass.APPARENT_POWER,
                native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )


for key, value in METER_VAR_TYPES.items():
    for meterKey, meterList in METERS.items():
        meterList.append(
            SensorEntityDescription(
                key=meterKey + "_" + key,
                name=meterKey.upper() + " " + value,
                device_class=SensorDeviceClass.REACTIVE_POWER,
                native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )


for key, value in METER_PF_TYPES.items():
    for meterKey, meterList in METERS.items():
        meterList.append(
            SensorEntityDescription(
                key=meterKey + "_" + key,
                name=meterKey.upper() + " " + value,
                device_class=SensorDeviceClass.POWER_FACTOR,
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )


for key, value in METER_KWH_TYPES.items():
    for meterKey, meterList in METERS.items():
        meterList.append(
            SensorEntityDescription(
                key=meterKey + "_" + key,
                name=meterKey.upper() + " " + value,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
            )
        )


for key, value in METER_VAH_TYPES.items():
    for meterKey, meterList in METERS.items():
        meterList.append(
            SensorEntityDescription(
                key=meterKey + "_" + key,
                name=meterKey.upper() + " " + value,
                native_unit_of_measurement=ENERGY_VOLT_AMPERE_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
            )
        )

for key, value in METER_VARH_TYPES.items():
    for meterKey, meterList in METERS.items():
        meterList.append(
            SensorEntityDescription(
                key=meterKey + "_" + key,
                name=meterKey.upper() + " " + value,
                native_unit_of_measurement=ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
            )
        )

BATTERIES = {BATTERY_1: [], BATTERY_2: [], BATTERY_3: []}

BATTERY_TEMP_TYPES = {
    "temp_avg": "Temp Average",
    "temp_max": "Temp Maximum",
}

BATTERY_VOLT_TYPES = {"voltage": "Voltage"}

BATTERY_CURRENT_TYPES = {"current": "Current"}

BATTERY_POWER_TYPES = {"power": "Power"}

BATTERY_ENERGY_KWH_TYPES = {
    "energy_discharged": "Discharged",
    "energy_charged": "Charged",
}

BATTERY_ENERGY_WH_TYPES = {
    "size_max": "Size Max",
    "size_available": "Size Available",
}

BATTERY_PERCENT_TYPES = {
    "state_of_health": "State of Health",
    "state_of_charge": "State of Charge",
}

for key, value in BATTERY_TEMP_TYPES.items():
    for batteryKey, batteryList in BATTERIES.items():
        batteryList.append(
            SensorEntityDescription(
                key=batteryKey + "_" + key,
                name=batteryKey.capitalize() + " " + value,
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

for key, value in BATTERY_VOLT_TYPES.items():
    for batteryKey, batteryList in BATTERIES.items():
        batteryList.append(
            SensorEntityDescription(
                key=batteryKey + "_" + key,
                name=batteryKey.capitalize() + " " + value,
                device_class=SensorDeviceClass.VOLTAGE,
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

for key, value in BATTERY_CURRENT_TYPES.items():
    for batteryKey, batteryList in BATTERIES.items():
        batteryList.append(
            SensorEntityDescription(
                key=batteryKey + "_" + key,
                name=batteryKey.capitalize() + " " + value,
                device_class=SensorDeviceClass.CURRENT,
                native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

for key, value in BATTERY_POWER_TYPES.items():
    for batteryKey, batteryList in BATTERIES.items():
        batteryList.append(
            SensorEntityDescription(
                key=batteryKey + "_" + key,
                name=batteryKey.capitalize() + " " + value,
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement=UnitOfPower.WATT,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

for key, value in BATTERY_ENERGY_KWH_TYPES.items():
    for batteryKey, batteryList in BATTERIES.items():
        batteryList.append(
            SensorEntityDescription(
                key=batteryKey + "_" + key,
                name=batteryKey.capitalize() + " " + value,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
            )
        )

for key, value in BATTERY_ENERGY_WH_TYPES.items():
    for batteryKey, batteryList in BATTERIES.items():
        batteryList.append(
            SensorEntityDescription(
                key=batteryKey + "_" + key,
                name=batteryKey.capitalize() + " " + value,
                device_class=SensorDeviceClass.ENERGY_STORAGE,
                native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

for key, value in BATTERY_PERCENT_TYPES.items():
    for batteryKey, batteryList in BATTERIES.items():
        batteryList.append(
            SensorEntityDescription(
                key=batteryKey + "_" + key,
                name=batteryKey.capitalize() + " " + value,
                device_class=SensorDeviceClass.BATTERY,
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

for batteryKey, batteryList in BATTERIES.items():
    batteryList.append(
        SensorEntityDescription(
            key=batteryKey + "_status", name=batteryKey.capitalize() + " Status"
        )
    )

DEVICE_STATUSSES = {
    1: "Off",
    2: "Sleeping (auto-shutdown) – Night mode",
    3: "Grid Monitoring/wake-up",
    4: "Inverter is ON and producing power",
    5: "Production (curtailed)",
    6: "Shutting down",
    7: "Fault",
    8: "Maintenance/setup",
}

BATTERY_STATUSSES = {1: "Off", 3: "Charging", 4: "Discharging", 6: "Idle", 10: "Sleep"}

EXPORT_CONTROL_MODE = {
    0: "Disabled",
    1: "Direct Export Limitation",
    2: "Indirect Export Limitation",
    4: "Production Limitation",
}

EXPORT_CONTROL_LIMIT_MODE = {0: "Total", 1: "Per phase"}

STORAGE_CONTROL_MODE = {
    0: "Disabled",
    1: "Maximize Self Consumption",
    2: "Time of Use",
    3: "Backup Only",
    4: "Remote Control",
}

STORAGE_AC_CHARGE_POLICY = {
    0: "Disabled",
    1: "Always Allowed",
    2: "Fixed Energy Limit",
    3: "Percent of Production",
}

STORAGE_CHARGE_DISCHARGE_MODE = {
    0: "Off",
    1: "Charge from excess PV power only",
    2: "Charge from PV first",
    3: "Charge from PV and AC",
    4: "Maximize export",
    5: "Discharge to match load",
    7: "Maximize self consumption",
}

ACTIVE_POWER_LIMIT_TYPES: list[SolarEdgeNumberDescription] = []
ACTIVE_POWER_LIMIT_TYPES.append(
    SolarEdgeNumberDescription(
        name="Active Power Limit",
        key="nominal_active_power_limit",
        register=0xF001,
        fmt="u16",
        attrs={"min": 0, "max": 100},
        native_unit_of_measurement=PERCENTAGE,
    )
)


EXPORT_CONTROL_SELECT_TYPES: list[SolarEdgeSelectDescription] = []

EXPORT_CONTROL_SELECT_TYPES.extend(
    [
        SolarEdgeSelectDescription(
            key="export_control_mode",
            name="Export control mode",
            register=0xE000,
            options_dict=EXPORT_CONTROL_MODE,
        ),
        SolarEdgeSelectDescription(
            key="export_control_limit_mode",
            name="Export control limit mode",
            register=0xE001,
            options_dict=EXPORT_CONTROL_LIMIT_MODE,
        ),
    ]
)

EXPORT_CONTROL_NUMBER_TYPES: list[SolarEdgeNumberDescription] = []
EXPORT_CONTROL_NUMBER_TYPES.append(
    SolarEdgeNumberDescription(
        name="Export control site limit",
        key="export_control_site_limit",
        register=0xE002,
        fmt="f",
        attrs={"min": 0, "max": DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT},
        native_unit_of_measurement=UnitOfPower.WATT,
    )
)

STORAGE_SELECT_TYPES: list[SolarEdgeSelectDescription] = []

STORAGE_SELECT_TYPES.extend(
    [
        SolarEdgeSelectDescription(
            key="storage_contol_mode",
            name="Storage Control Mode",
            register=0xE004,
            options_dict=STORAGE_CONTROL_MODE,
        ),
        SolarEdgeSelectDescription(
            key="storage_ac_charge_policy",
            name="Storage AC Charge Policy",
            register=0xE005,
            options_dict=STORAGE_AC_CHARGE_POLICY,
        ),
        SolarEdgeSelectDescription(
            key="storage_default_mode",
            name="Storage Default Mode",
            register=0xE00A,
            options_dict=STORAGE_CHARGE_DISCHARGE_MODE,
        ),
        SolarEdgeSelectDescription(
            key="storage_remote_command_mode",
            name="Storage Remote Command Mode",
            register=0xE00D,
            options_dict=STORAGE_CHARGE_DISCHARGE_MODE,
        ),
    ]
)


STORAGE_NUMBER_TYPES: list[SolarEdgeNumberDescription] = []

STORAGE_NUMBER_TYPES.extend(
    [
        SolarEdgeNumberDescription(
            name="Storage AC Charge Limit",
            key="storage_ac_charge_limit",
            register=0xE006,
            fmt="f",
            attrs={"min": 0, "max": 100000000000},
        ),
        SolarEdgeNumberDescription(
            name="Storage Backup reserved",
            key="storage_backup_reserved",
            register=0xE008,
            fmt="f",
            attrs={"min": 0, "max": 100},
            native_unit_of_measurement=PERCENTAGE,
        ),
        SolarEdgeNumberDescription(
            name="Storage Remote Command Timeout",
            key="storage_remote_command_timeout",
            register=0xE00B,
            fmt="u32",
            attrs={"min": 0, "max": 86400},
            native_unit_of_measurement=ATTR_SECONDS,
        ),
        SolarEdgeNumberDescription(
            name="Storage Remote Charge Limit",
            key="storage_remote_charge_limit",
            register=0xE00E,
            fmt="f",
            attrs={"min": 0, "max": 20000},
            native_unit_of_measurement=UnitOfPower.WATT,
        ),
        SolarEdgeNumberDescription(
            name="Storage Remote Discharge Limit",
            key="storage_remote_discharge_limit",
            register=0xE010,
            fmt="f",
            attrs={"min": 0, "max": 20000},
            native_unit_of_measurement=UnitOfPower.WATT,
        ),
    ]
)
