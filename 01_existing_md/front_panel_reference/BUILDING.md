# DR-X280 front-panel tester source

This is the release source for tester firmware v1.0.0, targeting an **original
Raspberry Pi Pico or Pico H with RP2040**. The ready-made UF2 and the user guide
are supplied at the package root; most users do not need to compile this source.

The firmware uses Pico I2C0 at 100 kHz, GP4 for SDA, GP5 for SCL, and USB CDC
for its text console. It was built with Raspberry Pi Pico SDK 2.2.0 and Arm GNU
Toolchain 13.3.Rel1.

## Build

Install Python 3, CMake, Ninja, the Arm GNU `arm-none-eabi` toolchain, and a
Pico SDK checkout with its submodules. From this directory:

```powershell
cmake -S . -B build -G Ninja `
  -DPICO_SDK_PATH="C:\path\to\pico-sdk" `
  -DPICO_BOARD=pico `
  -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

The build creates:

```text
build/drx280_frontpanel_tester.elf
build/drx280_frontpanel_tester.bin
build/drx280_frontpanel_tester.uf2
```

`uf2conv_min.py` converts the linked binary to the standard RP2040 UF2 format
and immediately decodes it again to verify block numbering, addresses, family
ID, payloads, and reconstructed bytes. `main.c` is compiled with
`-Wall -Wextra -Wpedantic -Werror`.

## Protocol safety properties

- Register reads use a pointer write with STOP followed by a separate addressed
  read with STOP. This panel application rejects a repeated START.
- The identity `C1 11 02` and ready bit must be verified before any normal
  configuration write.
- Normal writes are limited to `0x0C..0x11`, `0x14..0x15`, `0x18..0x19`, and
  `0x20..0x24`.
- Register `0x28`, which accepts a bootloader entry key, is never writable.
- Ordinary reads spanning side-effecting register `0x31` are rejected.
- Experimental IR uses one fixed, audited sentinel write to `0x2E/0x2F` and an
  exact one-byte service read from `0x31`; it is disabled until requested.
- Status brightness is capped at 6 because logical channel 5 has exceptional
  duty at level 7 in the recovered AVR firmware.
- Bus clearing drives SDA/SCL low or releases them to the external pull-ups; it
  never actively drives a logic high through the level shifter.
- Link loss synthesizes a button release, disables IR, and permits three bounded
  automatic recovery attempts.

The firmware and UF2 have been checked without live panel hardware. The first
physical run is intended to establish the visible status-channel, ring-position,
button, and raw IR mappings recorded in `MAPPING_WORKSHEET.md`.
