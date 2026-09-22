import subprocess
import time

import serial
from serial.tools import list_ports


subprocess.run(
    [
        r"work\picotool-2.2.0-x64-win\picotool\picotool.exe",
        "reboot",
        "-f",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=False,
)

for _ in range(100):
    if any(port.device == "COM3" for port in list_ports.comports()):
        break
    time.sleep(0.05)

device = serial.Serial("COM3", 115200, timeout=0.05)
device.dtr = True
device.rts = True
received = bytearray()
for _ in range(160):
    received.extend(device.read(512))
    time.sleep(0.05)
device.close()
print(received.decode("utf-8", errors="replace"))
