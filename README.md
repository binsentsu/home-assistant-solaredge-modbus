[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# Multiple Inverter Support
This fork was created to track the upstream, but with the multiple inverter pull request #12 that wasn't merged. Unfortuantely as of upstream release 1.4.0 I will no longer be able to keep up because of changes that were pulled in to add a bunch of control stuff exceed my Python + Home Assistant skill level. I will keep maintaining this fork where applicable because I need it for my inverter setup, but beyond that hopefully someone with better Python skills will be able to add multiple inverter support upstream.

My setup consists of two inverters and one meter:
* Inverters (addressed 1 and 2) on RS485-1
* Ethernet connected to inverter 1 for modbus/tcp
* E+I meter (address 2) connected to inverter 1 on RS485-2.
* Ethernet is also for Solaredge comms - no wireless or cell options

Important: The inverters must have sequential unit IDs (i.e. 1, 2, 3, ...). It doesn't matter which RS485 bus your inverter chain is on as long as it's configured as Solaredge leader/follower (master/slave in older firmware). If you have meters connected to inverter unit 1 the meter IDs *can* overlap the inverter unit IDs because they're on different busses (the solaredge meter ships with default ID 2).

Q: Why don't you have batteries?
A: Because I have net metering without TOU and I get paid for exported energy, so there was no ROI to invest in a battery system.

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
Credit for multiple inverter support goes to: https://github.com/julezman/home-assistant-solaredge-modbus/tree/multiple_inverters

I needed to start this fork becasue Home Assistant evolved and more changes were needed (like energy dashboard), and I wanted to be able to make it easier to merge them from the upstream.
