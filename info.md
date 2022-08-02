## SOLAREDGE MODBUS TCP

Home assistant Custom Component for reading data from Solaredge inverter through modbus TCP. Implements Inverter registers from https://www.solaredge.com/sites/default/files/sunspec-implementation-technical-note.pdf.

### Features

- Installation through Config Flow UI.
- Separate sensor per register
- Auto applies scaling factor
- Configurable polling interval
- All modbus registers are read within 1 read cycle for data consistency between sensors.
- Possible to select other modbus address than the default of 1
- Supports reading inverter data and meter (1->3) data.
- Supports reading battery data (1->2)
- Supports controlling storedge: Change battery charge / discharge profile
- Export control: allows control of how much power is exported
from the system to the grid

### Configuration
Go to the integrations page in your configuration and click on new integration -> SolarEdge Modbus

<img style="border: 5px solid #767676;border-radius: 10px;max-width: 350px;width: 100%;box-sizing: border-box;" src="https://github.com/binsentsu/home-assistant-solaredge-modbus/blob/master/demo.png?raw=true" alt="Demo">
