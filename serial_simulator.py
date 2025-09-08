#!/usr/bin/env python3
"""
Machine Serial Simulator
This script simulates a CNC machine that responds to Q-code requests over serial port (ttyUSB0).
It implements the Q-code table and RS-232 output format with STX/ETB control characters.
"""

import serial
import time
import random
import sys
import threading
from datetime import datetime

class MachineSimulator:
    def __init__(self):
        self.serial_port = None
        self.running = False
        self.spontaneous_messages = []
        self.spontaneous_thread = None
        
        # Q-code response data (simulated machine data)
        self.machine_data = {
            'Q100': 'CNC001234',  # Machine Serial Number
            'Q101': 'V2.1.5',     # Control Software Version
            'Q102': 'CNC-5000',   # Machine Model Number
            'Q104': 'MEM',        # Mode (LIST, PROG, MDI, MEM, etc.)
            'Q200': '1247',       # Tool Changes (Total)
            'Q201': 'T05',        # Tool Number in use
            'Q300': '1250.5',     # Power-on Time (Total) - hours
            'Q301': '890.2',      # Motion Time (Total) - hours
            'Q303': '45.3',       # Last Cycle Time - minutes
            'Q304': '44.8',       # Previous Cycle Time - minutes
            'Q402': '156',        # M30 Parts Counter #1
            'Q403': '89',         # M30 Parts Counter #2
            'Q500': 'O1234,READY' # Three-in-one (PROGRAM, Oxxxxx, STATUS, xxxxx)
        }
    
    def setup_serial(self):
        """Setup serial connection to ttyUSB0"""
        try:
            # Configure serial port
            self.serial_port = serial.Serial(
                port='/dev/ttyUSB0',
                baudrate=38400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=True,  # Enable XON/XOFF flow control
                timeout=1
            )
            print(f"Serial port /dev/ttyUSB0 opened successfully")
            return True
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            print("Make sure the port exists and you have permission to access it")
            return False
    
    def format_rs232_response(self, qcode, data):
        """Format response according to RS-232 specification: <STX><CSV response><ETB><CR/LF><0x3E>"""
        # STX = 0x02 (ctl-B), ETB = 0x17 (ctl-W)
        stx = chr(0x02)
        etb = chr(0x17)
        crlf = '\r\n'
        prompt = chr(0x3E)  # '>'
        
        # Create CSV response: Qcode,Data
        csv_response = f"{qcode},{data}"
        
        # Format complete response
        response = f"{stx}{csv_response}{etb}{crlf}{prompt}"
        return response
    
    def handle_qcode_request(self, request):
        """Handle incoming Q-code requests"""
        request = request.strip()
        print(f"Received request: {repr(request)}")
        
        # Check if it's a valid Q-code
        if request in self.machine_data:
            data = self.machine_data[request]
            response = self.format_rs232_response(request, data)
            
            # Send response
            self.serial_port.write(response.encode('utf-8'))
            print(f"Sent response for {request}: {data}")
            return True
        else:
            # Unknown Q-code - send error response
            error_response = self.format_rs232_response(request, "ERROR:UNKNOWN_CODE")
            self.serial_port.write(error_response.encode('utf-8'))
            print(f"Unknown Q-code requested: {request}")
            return False
    
    def add_spontaneous_message(self, message_type, data):
        """Add a spontaneous message to be sent periodically"""
        self.spontaneous_messages.append({
            'type': message_type,
            'data': data,
            'timestamp': datetime.now()
        })
    
    def send_spontaneous_messages(self):
        """Send spontaneous messages periodically"""
        while self.running:
            try:
                if self.spontaneous_messages:
                    # Send a random spontaneous message
                    msg = random.choice(self.spontaneous_messages)
                    response = self.format_rs232_response(f"SPONT_{msg['type']}", msg['data'])
                    self.serial_port.write(response.encode('utf-8'))
                    print(f"Sent spontaneous message: {msg['type']} = {msg['data']}")
                
                # Wait 10-30 seconds before next spontaneous message
                time.sleep(random.uniform(10, 30))
                
            except Exception as e:
                print(f"Error sending spontaneous message: {e}")
                time.sleep(5)
    
    def listen_for_requests(self):
        """Main loop to listen for Q-code requests"""
        print("Machine simulator is running. Listening for Q-code requests...")
        print("Supported Q-codes: Q100, Q101, Q102, Q104, Q200, Q201, Q300, Q301, Q303, Q304, Q402, Q403, Q500")
        print("Press Ctrl+C to stop")
        print("-" * 60)
        
        self.running = True
        
        # Start spontaneous message thread
        self.spontaneous_thread = threading.Thread(target=self.send_spontaneous_messages, daemon=True)
        self.spontaneous_thread.start()
        
        # Add some default spontaneous messages
        self.add_spontaneous_message("STATUS", "RUNNING")
        self.add_spontaneous_message("ALARM", "NONE")
        self.add_spontaneous_message("TEMPERATURE", "23.5")
        
        try:
            while self.running:
                # Check for incoming data
                if self.serial_port.in_waiting > 0:
                    # Read until we get a complete line or timeout
                    data = self.serial_port.readline()
                    if data:
                        request = data.decode('utf-8').strip()
                        self.handle_qcode_request(request)
                
                time.sleep(0.1)  # Small delay to prevent high CPU usage
                
        except KeyboardInterrupt:
            print("\nSimulator stopped by user")
        except Exception as e:
            print(f"Error in main loop: {e}")
        finally:
            self.running = False
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                print("Serial port closed")

def main():
    """Main function to run the machine simulator"""
    print("Starting Machine Serial Simulator...")
    print("This script simulates a CNC machine that responds to Q-code requests")
    print("Serial port: /dev/ttyUSB0, Baud rate: 38400, XON/XOFF flow control")
    print("-" * 60)
    
    # Create and setup simulator
    simulator = MachineSimulator()
    
    if not simulator.setup_serial():
        sys.exit(1)
    
    try:
        # Start listening for requests
        simulator.listen_for_requests()
    finally:
        # Cleanup is handled in listen_for_requests
        pass

if __name__ == "__main__":
    main()

