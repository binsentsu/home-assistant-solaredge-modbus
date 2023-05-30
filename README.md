[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# home-assistant-solaredge-modbus
Home assistant Custom Component for reading data from Solaredge inverter through modbus TCP.
Implements Inverter registers from the [Solaredge Sunspec Technical Note][1] and [Power Control Protocol for Solaredge Inverters Technical Note][2]

# Installation
Copy contents of custom_components folder to your home-assistant config/custom_components folder or install through HACS.
After reboot of Home-Assistant, this integration can be configured through the integration setup UI

# Enabling Modbus TCP on SolarEdge Inverter
1. Enable wifi direct on the inverter by switching the red toggle switch on the inverter to "P" position for less than 5 seconds.
2. Connect to the inverter access point like you would for a normal wifi network. The wifi password is published at the right side of the inverter. 
3. Open up a browser and go to http://172.16.0.1 > Site Communication. From this webpage you can enable modbus TCP without setApp or installer account.

## Wifi based communication:
We have seen several issues in the past, where the Integration was not able to connect to the inverter on Wifi-based setups.  
Back then, it seems that SolarEdge has changed something in their firmware and was later fixed in a specific firmware version.  
According to the feedback of some other users, it seems, that SolarEdge is going to remove the ability to establish a Wifi Connection to the Modbus interface completely in some future firmware versions.  

If you cannot switch to an Ethernet based connection, running a Modbus-Proxy could be a possible workaround for you.  
A documentation on how to setup the Modbus Proxy can be found in the Discussion section of this repository (https://github.com/binsentsu/home-assistant-solaredge-modbus/discussions/119).  
Basically, setup the Modbus Proxy on a small computer such as an rPI - connect it to your Inverter via Ethernet, and then use the Wifi Connection to connect to your rPI rather than to the inverter itself.

# Control of battery charge / discharge profile

Appendix B of the Solaredge [power control document][2] gives the necessary steps to allow changing the charge / discharge mode of the battery, but essentially all that you need to do is change the "Storage Control Mode" selector to "Remote" (it is usually set to "Maximise Self Consumption") and then select a mode using the "Storage Default Mode" selector. This can be done either from the UI or via an automation. Being able to control the battery charge / discharge mode like this opens up several possibilities:

- Set mode to "Off" during periods of cheap import rate, saving the energy for periods of high import rate. Also this mode can be used to avoid discharging the house battery during a period of high demand e.g. while charging an EV.
- Set mode to "Charge from PV and AC" during periods of negative import rate to get paid to charge it!
- Set mode to "Maximise export" during periods of high export rates to stabilise grid and get maximum income from the energy being exported.
- Set mode to "Maximise self consumption" at all other times to have the inverter automatically balance PV, battery and load.

Note that if you allow the battery to be charged from the grid, via the "Storage AC Charge Policy" selector, the self-consumption metric will disappear from the Solaredge monitoring - according to Solaredge technical support, this is because "they can't tell where the energy came from".

# Control of inverter power output
The active power limit of the inverter can be set from Home Assistant. This enables limiting or completely shutting down power output. For example in case of a dynamic energy contract in periods with a negative energy price. 

The active power limit is set as the percentage of the inverter’s maximum power via `number.solaredge_active_power_limit`. For example: when you have a SE5000 inverter that has a maximum output of 5000W, setting the value of `number.solaredge_active_power_limit` to 20 will limit the inverter to 1000W which is 20% of 5000W. See [Power Control Protocol for Solaredge Inverters Technical Note][2] for detailed information.

## Enabling Power Control in Home Assistant
Power control is disabled by default. It can be enabled in the configuration of this integration by setting `power_control` to true. When power control is enabled `number.solaredge_active_power_limit` is available in Home Assistant for reading and writing. The actual value of the active power limit is read together with the other values of the inverter. 

## Enabling Power Control on SolarEdge Inverter
With default settings the inverter will not allow power control. It can be enabled in the same way that Modbus TCP is enabled on the SolarEdge Inverter, by connecting to the inverter with a web browser.

These to settings must be applied in the Power Control menu:

1. Set Advanced Power Control to Enable
2. Set Reactive Power mode to RRCR


[1]: https://www.solaredge.com/sites/default/files/sunspec-implementation-technical-note.pdf
[2]: https://www.photovoltaikforum.com/core/attachment/88445-power-control-open-protocol-for-solaredge-inverters-pdf/
