#!/usr/bin/env python3
"""
MQTT Broker Client for Machine Communication
This script communicates with a CNC machine via serial port (ttyUSB1), sends Q-code requests,
receives responses, and publishes data to a Mosquitto MQTT broker.
It handles both Q-code responses and spontaneous messages from the machine.
"""

import serial
import paho.mqtt.client as mqtt
import time
import json
import sys
import threading
import argparse
from datetime import datetime

# MQTT Broker configuration
MQTT_BROKER = "localhost"  # Change this if broker is on different machine
MQTT_PORT = 1883
MQTT_USERNAME = "vives"
MQTT_PASSWORD = "vives"
MQTT_TOPIC_PREFIX = "serial/data"

class SerialMQTTBridge:
    def __init__(self, request_interval=30):
        """Initialize the Serial-MQTT bridge"""
        self.serial_port = None
        self.mqtt_client = None
        self.connected = False
        self.request_interval = request_interval
        self.running = False
        self.request_thread = None
        
        # Q-codes to request from the machine
        self.qcodes_to_request = [
            'Q100',  # Machine Serial Number
            'Q101',  # Control Software Version
            'Q102',  # Machine Model Number
            'Q104',  # Mode
            'Q200',  # Tool Changes (Total)
            'Q201',  # Tool Number in use
            'Q300',  # Power-on Time (Total)
            'Q301',  # Motion Time (Total)
            'Q303',  # Last Cycle Time
            'Q304',  # Previous Cycle Time
            'Q402',  # M30 Parts Counter #1
            'Q403',  # M30 Parts Counter #2
            'Q500'   # Three-in-one
        ]
        
    def setup_serial(self):
        """Setup serial connection to ttyUSB1"""
        try:
            # Configure serial port
            self.serial_port = serial.Serial(
                port='/dev/ttyUSB1',
                baudrate=38400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=True,  # Enable XON/XOFF flow control
                timeout=1
            )
            print(f"Serial port /dev/ttyUSB1 opened successfully")
            return True
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            print("Make sure the port exists and you have permission to access it")
            return False
    
    def setup_mqtt(self):
        """Setup MQTT client and connect to broker"""
        try:
            # Create MQTT client
            self.mqtt_client = mqtt.Client()
            
            # Set username and password
            self.mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            
            # Set callback functions
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_publish = self.on_mqtt_publish
            
            # Connect to broker
            print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            
            # Start the loop in a non-blocking way
            self.mqtt_client.loop_start()
            
            # Wait for connection
            timeout = 10
            while not self.connected and timeout > 0:
                time.sleep(1)
                timeout -= 1
            
            if self.connected:
                print("Successfully connected to MQTT broker")
                return True
            else:
                print("Failed to connect to MQTT broker")
                return False
                
        except Exception as e:
            print(f"Error setting up MQTT: {e}")
            return False
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when MQTT client connects"""
        if rc == 0:
            print("Connected to MQTT broker successfully")
            self.connected = True
        else:
            print(f"Failed to connect to MQTT broker with code: {rc}")
            self.connected = False
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when MQTT client disconnects"""
        print(f"Disconnected from MQTT broker with code: {rc}")
        self.connected = False
    
    def on_mqtt_publish(self, client, userdata, mid):
        """Callback when MQTT message is published"""
        print(f"Message published with ID: {mid}")
    
    def parse_rs232_response(self, data):
        """Parse RS-232 response format: <STX><CSV response><ETB><CR/LF><0x3E>"""
        try:
            # Decode the data
            data_str = data.decode('utf-8')
            
            # Check for STX (0x02) at the beginning
            if data_str.startswith(chr(0x02)):
                # Find ETB (0x17) to locate the CSV response
                etb_pos = data_str.find(chr(0x17))
                if etb_pos > 0:
                    # Extract CSV response (skip STX, stop at ETB)
                    csv_response = data_str[1:etb_pos]
                    
                    # Parse CSV: Qcode,Data
                    if ',' in csv_response:
                        qcode, value = csv_response.split(',', 1)
                        return {
                            'timestamp': datetime.now().strftime("%H:%M:%S"),
                            'qcode': qcode,
                            'value': value,
                            'raw_data': data_str,
                            'message_type': 'qcode_response'
                        }
                    else:
                        return {
                            'timestamp': datetime.now().strftime("%H:%M:%S"),
                            'qcode': 'UNKNOWN',
                            'value': csv_response,
                            'raw_data': data_str,
                            'message_type': 'qcode_response'
                        }
            
            # Check for spontaneous messages (SPONT_ prefix)
            if 'SPONT_' in data_str:
                # Try to extract spontaneous message data
                lines = data_str.split('\n')
                for line in lines:
                    if 'SPONT_' in line and chr(0x17) in line:
                        etb_pos = line.find(chr(0x17))
                        if etb_pos > 0:
                            csv_part = line[1:etb_pos]  # Skip STX
                            if ',' in csv_part:
                                msg_type, value = csv_part.split(',', 1)
                                return {
                                    'timestamp': datetime.now().strftime("%H:%M:%S"),
                                    'qcode': msg_type,
                                    'value': value,
                                    'raw_data': data_str,
                                    'message_type': 'spontaneous'
                                }
            
            # Fallback for unparseable data
            return {
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'qcode': 'RAW',
                'value': data_str.strip(),
                'raw_data': data_str,
                'message_type': 'unknown'
            }
            
        except Exception as e:
            print(f"Error parsing RS-232 response: {e}")
            return None
    
    def send_qcode_request(self, qcode):
        """Send a Q-code request to the machine"""
        try:
            if self.serial_port and self.serial_port.is_open:
                # Send the Q-code request
                request = f"{qcode}\n"
                self.serial_port.write(request.encode('utf-8'))
                print(f"Sent Q-code request: {qcode}")
                return True
            else:
                print("Serial port not available for sending request")
                return False
        except Exception as e:
            print(f"Error sending Q-code request {qcode}: {e}")
            return False
    
    def request_qcodes_periodically(self):
        """Periodically request Q-codes from the machine"""
        while self.running:
            try:
                for qcode in self.qcodes_to_request:
                    if not self.running:
                        break
                    
                    # Send request
                    self.send_qcode_request(qcode)
                    
                    # Wait for response (give machine time to respond)
                    time.sleep(2)
                
                # Wait before next round of requests
                if self.running:
                    print(f"Waiting {self.request_interval} seconds before next Q-code request cycle...")
                    time.sleep(self.request_interval)
                    
            except Exception as e:
                print(f"Error in Q-code request thread: {e}")
                time.sleep(5)
    
    def publish_to_mqtt(self, parsed_data):
        """Publish parsed data to MQTT broker"""
        if not self.connected or not parsed_data:
            return False
        
        try:
            # Create topic based on message type and qcode
            if parsed_data['message_type'] == 'qcode_response':
                topic = f"{MQTT_TOPIC_PREFIX}/qcode/{parsed_data['qcode'].lower()}"
            elif parsed_data['message_type'] == 'spontaneous':
                topic = f"{MQTT_TOPIC_PREFIX}/spontaneous/{parsed_data['qcode'].lower()}"
            else:
                topic = f"{MQTT_TOPIC_PREFIX}/unknown/{parsed_data['qcode'].lower()}"
            
            # Create message payload
            message = {
                'timestamp': parsed_data['timestamp'],
                'qcode': parsed_data['qcode'],
                'value': parsed_data['value'],
                'message_type': parsed_data['message_type'],
                'raw_data': parsed_data['raw_data']
            }
            
            # Convert to JSON
            payload = json.dumps(message)
            
            # Publish message
            result = self.mqtt_client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"Published to {topic}: {parsed_data['qcode']} = {parsed_data['value']}")
                return True
            else:
                print(f"Failed to publish message: {result.rc}")
                return False
                
        except Exception as e:
            print(f"Error publishing to MQTT: {e}")
            return False
    
    def run(self):
        """Main loop to read serial data and publish to MQTT"""
        print("Starting Machine-MQTT Bridge...")
        print("This script communicates with a CNC machine via /dev/ttyUSB1")
        print("Sends Q-code requests and publishes responses to MQTT broker")
        print("Press Ctrl+C to stop")
        print("-" * 60)
        
        # Setup connections
        if not self.setup_serial():
            return
        
        if not self.setup_mqtt():
            self.serial_port.close()
            return
        
        self.running = True
        
        # Start Q-code request thread
        self.request_thread = threading.Thread(target=self.request_qcodes_periodically, daemon=True)
        self.request_thread.start()
        
        try:
            print("Bridge is running. Listening for machine responses and spontaneous messages...")
            print(f"Q-code request interval: {self.request_interval} seconds")
            
            while self.running:
                # Check if serial port has data
                if self.serial_port.in_waiting > 0:
                    # Read data
                    data = self.serial_port.readline()
                    if data:
                        print(f"Received: {repr(data.decode('utf-8'))}")
                        
                        # Parse the RS-232 response
                        parsed_data = self.parse_rs232_response(data)
                        if parsed_data:
                            # Publish to MQTT
                            self.publish_to_mqtt(parsed_data)
                
                # Small delay to prevent high CPU usage
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nBridge stopped by user")
        except Exception as e:
            print(f"Error in main loop: {e}")
        finally:
            # Cleanup
            self.running = False
            
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                print("Serial port closed")
            
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                print("MQTT connection closed")

def main():
    """Main function to run the Machine-MQTT bridge"""
    parser = argparse.ArgumentParser(description='Machine-MQTT Bridge for CNC Communication')
    parser.add_argument('--interval', type=int, default=30, 
                       help='Q-code request interval in seconds (default: 30)')
    parser.add_argument('--qcodes', nargs='+', 
                       help='Specific Q-codes to request (default: all supported Q-codes)')
    
    args = parser.parse_args()
    
    # Create bridge with specified interval
    bridge = SerialMQTTBridge(request_interval=args.interval)
    
    # Override Q-codes if specified
    if args.qcodes:
        bridge.qcodes_to_request = args.qcodes
        print(f"Using custom Q-codes: {args.qcodes}")
    
    bridge.run()

if __name__ == "__main__":
    main()

