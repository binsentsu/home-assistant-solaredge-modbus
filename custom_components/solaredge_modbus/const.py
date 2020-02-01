DOMAIN = "solaredge_modbus"
DEFAULT_NAME = "solaredge"
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_PORT = 1502
CONF_SOLAREDGE_HUB = "solaredge_hub"
ATTR_STATUS_DESCRIPTION = "status_description"
ATTR_MANUFACTURER = "Solaredge"

SENSOR_TYPES = {
    "AC_Current": ["AC Current", "accurrent", "A", "mdi:current-ac"],
    "AC_CurrentA": ["AC Current A", "accurrenta", "A", "mdi:current-ac"],
    "AC_CurrentB": ["AC Current B", "accurrentb", "A", "mdi:current-ac"],
    "AC_CurrentC": ["AC Current C", "accurrentc", "A", "mdi:current-ac"],
    "AC_VoltageAB": ["AC Voltage AB", "acvoltageab", "V", None],
    "AC_VoltageBC": ["AC Voltage BC", "acvoltagebc", "V", None],
    "AC_VoltageCA": ["AC Voltage CA", "acvoltageca", "V", None],
    "AC_VoltageAN": ["AC Voltage AN", "acvoltagean", "V", None],
    "AC_VoltageBN": ["AC Voltage BN", "acvoltagebn", "V", None],
    "AC_VoltageCN": ["AC Voltage CN", "acvoltagecn", "V", None],
    "AC_Power": ["AC Power", "acpower", "W", "mdi:solar-power"],
    "AC_Frequency": ["AC Frequency", "acfreq", "Hz", None],
    "AC_VA": ["AC VA", "acva", "VA", None],
    "AC_VAR": ["AC VAR", "acvar", "VAR", None],
    "AC_PF": ["AC PF", "acpf", "%", None],
    "AC_Energy_KWH": ["AC Energy KWH", "acenergy", "kWh", "mdi:solar-power"],
    "DC_Current": ["DC Current", "dccurrent", "A", "mdi:current-dc"],
    "DC_Voltage": ["DC Voltage", "dcvoltage", "V", None],
    "DC_Power": ["DC Power", "dcpower", "W", "mdi:solar-power"],
    "Temp_Sink": ["Temp Sink", "tempsink", "°C", None],
    "Status": ["Status", "status", None, None],
    "Status_Vendor": ["Status Vendor", "statusvendor", None, None]
}

DEVICE_STATUSSES = {
    1: "Off",
    2: "Sleeping (auto-shutdown) – Night mode",
    3: "Grid Monitoring/wake-up",
    4: "Inverter is ON and producing power",
    5: "Production (curtailed)",
    6: "Shutting down",
    7: "Fault",
    8: "Maintenance/setup"
}