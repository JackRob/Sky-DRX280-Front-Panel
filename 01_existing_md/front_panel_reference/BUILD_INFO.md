# DR-X280 Pico tester v1.0.0 build record

## Target and toolchain

- Board: original Raspberry Pi Pico / Pico H
- Microcontroller: RP2040, Cortex-M0+
- Pico SDK: 2.2.0
- Arm GNU Toolchain: 13.3.Rel1
- Build type: Release
- USB interface: CDC serial
- I2C interface: I2C0, GP4 SDA, GP5 SCL, 100 kHz

## Final artifact identities

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `main.c` | 43,778 | `0915ACAB53EDDC27B8638F65531A26D35DD465BA8062702DC08DBBDA4512F20A` |
| `drx280_frontpanel_tester.bin` | 60,192 | `01CA5C3368799407A7FA11E90F4F8A5726820AF2091752EED6BD5B645BE55353` |
| `DRX280_Pico_RP2040_Tester_v1.0.0.uf2` | 120,832 | `88A65AEB36A9FD20BA4EE74F3EB7B8584C7CEF0A1FF81C610581F4DB778F30C8` |

## Validation completed

- `main.c` compiled with `-Wall -Wextra -Wpedantic -Werror`.
- A clean Release build selected `PICO_BOARD=pico`, `PICO_PLATFORM=rp2040`,
  Cortex-M0+, and Thumb instructions.
- The 236 UF2 blocks are sequential, unique, and use RP2040 family ID
  `0xE48BFF56`; their contiguous flash range is
  `[0x10000000, 0x1000EC00)`.
- The UF2 payload reconstructs the linked BIN byte-for-byte, with only its
  final 224 zero-padding bytes added.
- The RP2040 boot2 CRC, initial stack pointer, and reset vector were checked.
- Microsoft’s official `uf2conv.py` produced a byte-for-byte identical UF2.
- Six reference-driver tests passed: register allowlist, blink bounds, direct
  buttons, guarded IR sentinel, LED/ring helpers, and STOP-separated reads.
- Eight transaction-model groups passed, including repeated-START rejection,
  STOP-separated transfers, register boundaries, and register `0x31` service
  behavior.
- The Windows console helper passed Python compilation and option checks.

The source, binary format, and protocol behavior have been checked without a
physically attached Pico or front panel. BOOTSEL flashing, USB enumeration, and
the visible panel mappings remain the first live hardware test.
