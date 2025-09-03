#!/usr/bin/env python3
import argparse
import logging
import signal
import sys
import time

import serial
import paho.mqtt.client as mqtt


running = True


def handle_signal(sig, frame):
    global running
    running = False


def on_connect_v1(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker")
    else:
        logging.error(f"Failed to connect, rc={rc}")


def on_disconnect_v1(client, userdata, rc):
    logging.info(f"Disconnected from MQTT broker, rc={rc}")


def on_connect_v2(client, userdata, flags, reason_code, properties=None):
    try:
        code = int(reason_code)
    except Exception:
        code = getattr(reason_code, "value", reason_code)
    if code == 0:
        logging.info("Connected to MQTT broker")
    else:
        logging.error(f"Failed to connect, reason_code={code}")


def on_disconnect_v2(client, userdata, reason_code, properties=None):
    try:
        code = int(reason_code)
    except Exception:
        code = getattr(reason_code, "value", reason_code)
    logging.info(f"Disconnected from MQTT broker, reason_code={code}")


def build_mqtt_client(args) -> mqtt.Client:
    # Prefer v2 callback API when available; fall back to v1 for older paho-mqtt
    client = None
    try:
        # paho-mqtt >=2.0
        client = mqtt.Client(
            client_id=args.client_id or None,
            clean_session=True,
            userdata=None,
            protocol=mqtt.MQTTv311,
            transport="tcp",
            callback_api_version=getattr(mqtt, "CallbackAPIVersion", None).V2,
        )
        client.on_connect = on_connect_v2
        client.on_disconnect = on_disconnect_v2
    except Exception:
        # paho-mqtt 1.x
        client = mqtt.Client(client_id=args.client_id or None, clean_session=True)
        client.on_connect = on_connect_v1
        client.on_disconnect = on_disconnect_v1

    if args.username or args.password:
        client.username_pw_set(args.username or "", args.password or "")
    if args.tls:
        # For real certificates, consider specifying ca_certs, certfile, keyfile
        client.tls_set()  # uses system CAs

    client.will_set(args.topic, payload="serial_publisher_offline", qos=args.qos, retain=False)
    # Reconnect backoff
    try:
        client.reconnect_delay_set(min_delay=1, max_delay=30)
    except Exception:
        pass
    return client


def main() -> int:
    parser = argparse.ArgumentParser(description="Read from serial and publish to MQTT")
    parser.add_argument("--device", required=True, help="Serial device, e.g. /dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=9600, help="Serial baud rate")
    parser.add_argument("--bytesize", type=int, default=8, choices=[5, 6, 7, 8], help="Serial byte size")
    parser.add_argument("--parity", default="N", choices=["N", "E", "O", "M", "S"], help="Serial parity")
    parser.add_argument("--stopbits", type=float, default=1, choices=[1, 1.5, 2], help="Serial stop bits")
    parser.add_argument("--timeout", type=float, default=1.0, help="Serial read timeout (s)")

    parser.add_argument("--mqtt-host", required=True, help="MQTT broker host")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port (8883 for TLS)")
    parser.add_argument("--topic", required=True, help="MQTT topic to publish to")
    parser.add_argument("--client-id", default=None, help="MQTT client ID (optional)")
    parser.add_argument("--username", default=None, help="MQTT username")
    parser.add_argument("--password", default=None, help="MQTT password")
    parser.add_argument("--qos", type=int, default=0, choices=[0, 1, 2], help="MQTT QoS")
    parser.add_argument("--retain", action="store_true", help="Set retain flag on messages")
    parser.add_argument("--tls", action="store_true", help="Enable TLS for MQTT connection")

    parser.add_argument(
        "--line-ending",
        default="auto",
        choices=["auto", "strip", "keep", "crlf", "lf"],
        help="How to handle serial line endings before publish",
    )
    parser.add_argument("--rate-limit-ms", type=int, default=0, help="Min ms between publishes (0=off)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARN", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        ser = serial.Serial(
            port=args.device,
            baudrate=args.baudrate,
            bytesize=args.bytesize,
            parity=args.parity,
            stopbits=args.stopbits,
            timeout=args.timeout,
        )
    except Exception as exc:
        logging.error(f"Failed to open serial device {args.device}: {exc}")
        return 2

    logging.info(f"Opened serial {args.device} @ {args.baudrate} baud")

    client = build_mqtt_client(args)
    try:
        client.connect(args.mqtt_host, port=args.mqtt_port, keepalive=60)
    except Exception as exc:
        logging.error(f"Failed to connect to MQTT broker {args.mqtt_host}:{args.mqtt_port}: {exc}")
        ser.close()
        return 3

    client.loop_start()

    last_publish_ns = 0
    rate_limit_ns = args.rate_limit_ms * 1_000_000

    try:
        while running:
            try:
                raw = ser.readline()
            except serial.SerialException as e:
                logging.error(f"Serial error: {e}")
                time.sleep(1)
                continue

            if not raw:
                continue

            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                text = raw.decode("latin1", errors="replace")

            if args.line_ending == "strip" or args.line_ending == "auto":
                payload = text.strip()
            elif args.line_ending == "keep":
                payload = text
            elif args.line_ending == "crlf":
                payload = text.rstrip("\r\n") + "\r\n"
            elif args.line_ending == "lf":
                payload = text.rstrip("\r\n") + "\n"
            else:
                payload = text

            if args.line_ending == "auto" and payload == "":
                # Skip empty lines commonly produced by strip()
                continue

            now_ns = time.monotonic_ns()
            if rate_limit_ns and (now_ns - last_publish_ns) < rate_limit_ns:
                # Simple rate limit
                continue

            info = client.publish(args.topic, payload=payload, qos=args.qos, retain=args.retain)
            # Optionally wait for publish when QoS>0
            try:
                if args.qos > 0:
                    info.wait_for_publish(timeout=5)
            except Exception:
                pass

            try:
                if getattr(info, "rc", mqtt.MQTT_ERR_SUCCESS) != mqtt.MQTT_ERR_SUCCESS:
                    logging.warning(f"Publish returned rc={getattr(info, 'rc', None)}")
            except Exception:
                pass

            last_publish_ns = now_ns

    finally:
        logging.info("Shutting down...")
        try:
            ser.close()
        except Exception:
            pass
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

