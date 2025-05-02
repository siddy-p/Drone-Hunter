import serial

ser = serial.Serial('/dev/tty.usbmodem1301', 115200)  # update this
while True:
    line = ser.readline().decode(errors='ignore').strip()
    print("[PC RECEIVED]", line)
