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

# Control of battery charge / discharge profile

Appendix B of the Solaredge [power control document][2] gives the necessary steps to allow changing the charge / discharge mode of the battery, but essentially all that you need to do is change the "Storage Control Mode" selector to "Remote" (it is usually set to "Maximise Self Consumption") and then select a mode using the "Storage Default Mode" selector. This can be done either from the UI or via an automation. Being able to control the battery charge / discharge mode like this opens up several possibilities:

- Set mode to "Off" during periods of cheap import rate, saving the energy for periods of high import rate. Also this mode can be used to avoid discharging the house battery during a period of high demand e.g. while charging an EV.
- Set mode to "Charge from PV and AC" during periods of negative import rate to get paid to charge it!
- Set mode to "Maximise export" during periods of high export rates to stabilise grid and get maximum income from the energy being exported.
- Set mode to "Maximise self consumption" at all other times to have the inverter automatically balance PV, battery and load.

Note that if you allow the battery to be charged from the grid, via the "Storage AC Charge Policy" selector, the self-consumption metric will disappear from the Solaredge monitoring - according to Solaredge technical support, this is because "they can't tell where the energy came from".

[1]: https://www.solaredge.com/sites/default/files/sunspec-implementation-technical-note.pdf
[2]: https://www.photovoltaikforum.com/core/attachment/88445-power-control-open-protocol-for-solaredge-inverters-pdf/