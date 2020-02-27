[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

# home-assistant-solaredge-modbus
Home assistant Custom Component for reading data from Solaredge inverter through modbus TCP.
Implements Inverter registers from https://www.solaredge.com/sites/default/files/sunspec-implementation-technical-note.pdf

# Installation
Copy contents of custom_components folder to your home-assistant config/custom_components folder.
After reboot of Home-Assistant, this integration can be configured through the integration setup UI

# Enabling Modbus TCP on SolarEdge Inverter
Enable wifi direct on the inverter. Connect to the inverter access point like you would for a normal wifi network. The wifi password is published at the right side of the inverter. Then open up a browser and go to http://172.16.0.1 . From this webpage you can enable modbus TCP without setApp or installer account.
