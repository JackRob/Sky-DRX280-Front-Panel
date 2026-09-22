# Temporary status LED mapping firmware

- File: `DRX280_Pico_RP2040_STATUS_MAPPING_GP17_GP16_v1.2.0.uf2`
- Wiring: orange/SDA = GP17, green/SCL = GP16
- This is a temporary tester for identifying the panel's status channels.
- Serial: 115200 8-N-1

After flashing, open the Pico serial port and send one command at a time:

```text
off
led 0 2
```

Record which physical LED lights, then send `off` before testing the next channel (`led 1 2` through `led 5 2`). Brightness `2` is deliberately low. The tester also accepts `help`, `info`, and `ledtest 2 700`.

After mapping, reflash the firmware appropriate for your own panel interface.
SHA-256 of the reference UF2: `585C624AD7382C1A8146170FAA1804B2F4AF2028E7A7639A0C08D2E8482BA063`.
