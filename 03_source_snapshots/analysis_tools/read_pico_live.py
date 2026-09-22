import time

import serial


device = serial.Serial("COM3", 9600, timeout=0.2)
device.dtr = True
device.rts = True
device.write(b"\r\n")
device.flush()
end = time.time() + 20
while time.time() < end:
    data = device.read(512)
    if data:
        print(data.decode("utf-8", errors="replace"), end="", flush=True)
device.close()
