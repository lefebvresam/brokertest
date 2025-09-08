# CNC Machine Communication System

This project implements a complete CNC machine communication system with Q-code support, RS-232 protocol handling, and MQTT integration. It simulates a CNC machine that responds to Q-code requests and publishes machine data to an MQTT broker.

## Files

- **`serial_simulator.py`** - CNC machine simulator that responds to Q-code requests over `/dev/ttyUSB0`
- **`broker.py`** - MQTT bridge that sends Q-code requests and publishes responses to Mosquitto broker
- **`test_system.py`** - Comprehensive system test using virtual serial ports
- **`simple_test.py`** - Basic functionality test without hardware requirements

## Prerequisites

1. **Python 3.6+** installed on your system
2. **Mosquitto MQTT broker** already installed and running
3. **Two USB-to-Serial adapters** connected to create `/dev/ttyUSB0` and `/dev/ttyUSB1` (for hardware testing)
4. **socat** (optional, for virtual serial port testing): `sudo apt-get install socat`

## Installation

1. Install Python dependencies using the system package manager:
   ```bash
   sudo apt update
   sudo apt install -y python3-serial python3-paho-mqtt
   ```

2. Ensure Mosquitto broker is running with authentication:
   ```bash
   # Check if mosquitto is running
   systemctl status mosquitto
   
   # If not running, start it
   sudo systemctl start mosquitto
   ```

3. Verify your serial ports exist:
   ```bash
   ls -la /dev/ttyUSB*
   ```

## Usage

### Quick Test (No Hardware Required)

Run the basic functionality test:
```bash
python3 simple_test.py
```

### Hardware Testing

#### 1. Start the CNC Machine Simulator

In one terminal, run the machine simulator:
```bash
python3 serial_simulator.py
```

This script will:
- Open `/dev/ttyUSB0` with 38400 baud, XON/XOFF flow control
- Listen for Q-code requests (Q100-Q500)
- Respond with RS-232 formatted data: `<STX><CSV response><ETB><CR/LF><0x3E>`
- Send spontaneous messages periodically
- Display all communication in the terminal

#### 2. Start the MQTT Bridge

In another terminal, run the broker script:
```bash
python3 broker.py [--interval 30] [--qcodes Q100 Q101 Q104]
```

This script will:
- Open `/dev/ttyUSB1` with matching serial settings
- Connect to Mosquitto broker with username `vives` and password `vives`
- Send Q-code requests every 30 seconds (configurable)
- Parse RS-232 responses and spontaneous messages
- Publish structured data to MQTT topics

### Virtual Serial Port Testing

For testing without hardware:
```bash
# Install socat if not already installed
sudo apt-get install socat

# Run the comprehensive test
python3 test_system.py
```

## Q-Code Support

The system supports the following Q-codes as defined in the machine specification:

| Q-Code | Description | Example Response |
|--------|-------------|------------------|
| Q100 | Machine Serial Number | CNC001234 |
| Q101 | Control Software Version | V2.1.5 |
| Q102 | Machine Model Number | CNC-5000 |
| Q104 | Mode (LIST, PROG, MDI, MEM, etc.) | MEM |
| Q200 | Tool Changes (Total) | 1247 |
| Q201 | Tool Number in use | T05 |
| Q300 | Power-on Time (Total) | 1250.5 |
| Q301 | Motion Time (Total) | 890.2 |
| Q303 | Last Cycle Time | 45.3 |
| Q304 | Previous Cycle Time | 44.8 |
| Q402 | M30 Parts Counter #1 | 156 |
| Q403 | M30 Parts Counter #2 | 89 |
| Q500 | Three-in-one (PROGRAM, Oxxxxx, STATUS, xxxxx) | O1234,READY |

## RS-232 Protocol

The system implements the RS-232 output format:
- **Format**: `<STX><CSV response><ETB><CR/LF><0x3E>`
- **STX**: 0x02 (Start of Text)
- **ETB**: 0x17 (End of Transmission Block)
- **CSV Response**: `Qcode,Data`
- **Example**: `\x02Q100,CNC001234\x17\r\n>`

## MQTT Topics

Data is published to topics with the format:
```
serial/data/{message_type}/{qcode}
```

### Q-Code Response Topics
- `serial/data/qcode/q100` - Machine Serial Number
- `serial/data/qcode/q101` - Software Version
- `serial/data/qcode/q104` - Machine Mode
- `serial/data/qcode/q201` - Current Tool
- `serial/data/qcode/q303` - Last Cycle Time
- etc.

### Spontaneous Message Topics
- `serial/data/spontaneous/spont_status` - Status updates
- `serial/data/spontaneous/spont_alarm` - Alarm messages
- `serial/data/spontaneous/spont_temperature` - Temperature readings

## Message Format

Each MQTT message contains JSON data:
```json
{
  "timestamp": "17:06:52",
  "qcode": "Q100",
  "value": "CNC001234",
  "message_type": "qcode_response",
  "raw_data": "\x02Q100,CNC001234\x17\r\n>"
}
```

## Testing

### Basic Functionality Test
```bash
python3 simple_test.py
```

### Hardware Testing
1. **Connect two USB-to-Serial adapters** to your machine
2. **Connect the adapters together** with a serial cable (or use a loopback connector)
3. **Run both scripts** in separate terminals:
   ```bash
   # Terminal 1: Machine Simulator
   python3 serial_simulator.py
   
   # Terminal 2: MQTT Bridge
   python3 broker.py
   ```
4. **Monitor MQTT messages** using mosquitto_sub:
   ```bash
   mosquitto_sub -h localhost -u vives -P vives -t "serial/data/#"
   ```

### Virtual Serial Port Testing
```bash
# Install socat
sudo apt-get install socat

# Run comprehensive test
python3 test_system.py
```

## Troubleshooting

### Serial Port Permission Issues
If you get permission errors:
```bash
sudo usermod -a -G dialout $USER
# Then log out and back in, or run:
newgrp dialout
```

### Port Not Found
- Check if USB adapters are properly connected
- Verify with `ls -la /dev/ttyUSB*`
- Try different USB ports

### MQTT Connection Issues
- Ensure Mosquitto is running: `systemctl status mosquitto`
- Check authentication in `/etc/mosquitto/mosquitto.conf`
- Verify username/password are correct

### Data Not Flowing
- Check serial cable connection between adapters
- Verify baudrate settings match (38400 by default)
- Ensure both scripts are running simultaneously
- Check XON/XOFF flow control settings

### Q-Code Issues
- Verify Q-code requests are being sent (check broker logs)
- Ensure machine simulator is responding (check simulator logs)
- Check RS-232 format parsing (run simple_test.py)

## Customization

### Serial Settings
- **Change serial ports**: Modify the `port` parameter in both scripts
- **Adjust baudrate**: Change the `baudrate` parameter (default: 38400)
- **Flow control**: Modify `xonxoff` parameter for XON/XOFF control

### MQTT Configuration
- **Broker settings**: Update `MQTT_BROKER` and `MQTT_PORT` in `broker.py`
- **Authentication**: Modify `MQTT_USERNAME` and `MQTT_PASSWORD`
- **Topic prefix**: Change `MQTT_TOPIC_PREFIX`

### Q-Code Configuration
- **Request interval**: Use `--interval` parameter with broker.py
- **Specific Q-codes**: Use `--qcodes` parameter to request only specific codes
- **Machine data**: Modify `machine_data` dictionary in `serial_simulator.py`
- **Spontaneous messages**: Add/remove messages in `add_spontaneous_message()` calls

## Stopping the Scripts

Press `Ctrl+C` in each terminal to stop the respective scripts gracefully.

