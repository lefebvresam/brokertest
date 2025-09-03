## Serial to MQTT Publisher

Python script that reads lines from a serial port and publishes them to an MQTT topic (supports username/password and optional TLS).

### Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

### Usage

Basic (no TLS):

```bash
python broker.py \
  --device /dev/ttyUSB0 --baudrate 9600 \
  --mqtt-host 192.168.1.10 --mqtt-port 1883 \
  --topic sensors/machine1/serial \
  --username myuser --password 'mypassword'
```

TLS (typical port 8883):

```bash
python broker.py \
  --device /dev/ttyUSB0 --baudrate 9600 \
  --mqtt-host broker.example.com --mqtt-port 8883 --tls \
  --topic sensors/machine1/serial \
  --username myuser --password 'mypassword'
```

Options:

```text
--device           Serial device, e.g. /dev/ttyUSB0 (required)
--baudrate         Serial baud rate (default 9600)
--bytesize         Serial byte size (5,6,7,8; default 8)
--parity           Serial parity (N,E,O,M,S; default N)
--stopbits         Serial stop bits (1,1.5,2; default 1)
--timeout          Serial read timeout seconds (default 1.0)

--mqtt-host        MQTT broker host (required)
--mqtt-port        MQTT broker port (default 1883; 8883 for TLS)
--topic            MQTT topic to publish to (required)
--client-id        Optional client ID
--username         MQTT username
--password         MQTT password
--qos              MQTT QoS 0/1/2 (default 0)
--retain           Set retain flag
--tls              Enable TLS (uses system CAs)

--line-ending      auto|strip|keep|crlf|lf (default auto)
--rate-limit-ms    Minimum milliseconds between publishes (default 0)
--log-level        DEBUG|INFO|WARN|ERROR (default INFO)
```

### Notes

- Ensure your user can access the serial device (e.g., add to `dialout` group on Linux).
- Test the publish path with:

```bash
mosquitto_sub -h <broker> -t sensors/machine1/serial -v
```

- For custom CA or client certs, configure TLS explicitly in `broker.py` if needed.

