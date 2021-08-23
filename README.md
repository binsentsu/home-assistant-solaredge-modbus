[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# Multiple Inverter Fork (PR#12)
The purpose of this fork is to track the upstream, but with the multiple inverter pull request #12 that hasn't been merged.

# home-assistant-solaredge-modbus
Home assistant Custom Component for reading data from Solaredge inverter through modbus TCP.
Implements Inverter registers from https://www.solaredge.com/sites/default/files/sunspec-implementation-technical-note.pdf

# Installation
Copy contents of custom_components folder to your home-assistant config/custom_components folder or install through HACS.
After reboot of Home-Assistant, this integration can be configured through the integration setup UI

# Enabling Modbus TCP on SolarEdge Inverter
1. Enable wifi direct on the inverter by switching the red toggle switch on the inverter to "P" position for less than 5 seconds.
2. Connect to the inverter access point like you would for a normal wifi network. The wifi password is published at the right side of the inverter. 
3. Open up a browser and go to http://172.16.0.1 > Site Communication. From this webpage you can enable modbus TCP without setApp or installer account.
