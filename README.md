[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# Multiple Inverter Fork (PR#12)
The purpose of this fork is to track the upstream, but with the multiple inverter pull request #12 that hasn't been merged yet.

This fork also removes the "stub" methods from the upstream that were used for testing since I'm testing it with a live mutiple-inverter solaredge installation plus tools like https://www.modbusdriver.com/diagslave.html to provide simulated connections.

My setup consists of two inverters and one meter:
* Inverters (addressed 1 and 2) on RS485-1
* Ethernet connected to inverter 1 for modbus/tcp
* E+I meter connected to inverter 1 on RS485-2.
* Ethernet is also for Solaredge comms - no wireless or cell options

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

# Credits
Credit for multiple inverter support on this integration goes to: https://github.com/julezman/home-assistant-solaredge-modbus/tree/multiple_inverters

I first used that branch as-is, but needed to start this fork becasue Home Assistant evolved and more changes were needed (like energy dashboard), and I wanted to be able to make it easier to merge them from the upstream.
