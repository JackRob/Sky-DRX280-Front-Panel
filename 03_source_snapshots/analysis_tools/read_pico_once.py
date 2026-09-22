import time
import serial

device = serial.Serial("COM3", 9600, timeout=0.2)
device.dtr = True
device.rts = True
device.write(b"\r\n")
device.flush()
time.sleep(2.0)
data = device.read_all()
print(repr(data), flush=True)
device.close()
