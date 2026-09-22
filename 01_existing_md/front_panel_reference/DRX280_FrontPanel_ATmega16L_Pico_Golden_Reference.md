# DR-X280_2 / PCBR-2694-01 front-panel controller

## ATmega16L firmware protocol and Raspberry Pi Pico golden reference

**Document version:** 1.1 — 2026-09-10  
**Board markings visible in the supplied evidence:** `DR-X280_2`, issue 3; `PCBR-2694-01`  
**Controller:** ATmega16L-8PU, 40-pin PDIP  
**Purpose:** a self-contained engineering reference for preserving the original controller, identifying its six-wire connector, and controlling and observing the panel from an RP2040/Pico.

This document deliberately contains only the front-panel controller, its firmware, electrical interface, and Pico-side software. It does not depend on a particular computer, enclosure conversion, operating system, or end use.

### Read this first

The application interface is **I²C/TWI**, with the panel acting as a target at seven-bit address **`0x40`**. The Pico is the controller. The AVR's MOSI/MISO/SCK pins are its programming interface and are not the application link established by this firmware.

Unpowered bench measurements now establish the panel-cable signal mapping: **purple and blue are both ground, brown is the MCU supply rail, green is SCL, orange is SDA, and red reaches PD3/INT1 through approximately 100 Ω**. Firmware identifies PD3/INT1 as the second IR-decoder input, making red the external/mainboard IR input. The mainboard connector is J807; its printed pin 1 is nearest the mounting hole. Colour-to-J807 order and the powered voltage on brown still require confirmation with the correctly fitted working-box harness.

The original controller is configured for nominal 8 MHz operation and a nominal 4.0 V brownout threshold. It will therefore not run reliably correctly from 3.3 V with the recorded fuse settings. If its logic rail is 5 V, Pico GPIO must not touch that rail or its bus directly. Use a bidirectional, open-drain I²C level translator.

The firmware has one unusual bus requirement: to read a register, write the register number, issue **STOP**, then perform a new addressed read. Do not use the common repeated-START memory-read transaction. This was established from the complete TWI state handler and checked with a narrow instruction-level model.

### What is already established

- Two independent Flash files are byte-for-byte identical.
- The apparent 62-byte shortage has a normal cause: AVRDUDE normally removes erased trailing `0xFF` bytes from Flash reads.
- The application contains a 65-byte public register bank, registers `0x00–0x40`, at SRAM `0x0107–0x0147`.
- The TWI slave address register is initialized to `0x80`, which encodes seven-bit address `0x40`.
- The transport auto-increments after each data byte and does not enforce read-only registers.
- The panel firmware scans 15 buttons as a 3×5 matrix.
- It drives six logical status-indicator channels and an eight-position animated ring.
- It contains a two-input, timing-based remote decoder and a 16-word remote-event FIFO.
- The default button mode is queued. Registers `0x26/0x27` are not guaranteed to be live current state in that mode.
- Register `0x31` has a hidden read-time event-service side effect.
- An exact 12-byte sequence written successively to register `0x28` enters the bootloader. Generic fuzzing must exclude that register.

### Evidence vocabulary

| Label | Meaning |
|---|---|
| **Firmware-proven** | Direct, repeated control/data flow in the supplied binary, or a computed checksum that exactly matches embedded values |
| **File-proven** | Direct property of the supplied files, such as length, hash, equality, or byte content |
| **Datasheet-proven** | Device behavior specified by the cited manufacturer document |
| **Strong inference** | The evidence has a clear interpretation but the board has not been powered and observed in this analysis |
| **Bench-required** | Firmware cannot determine it; continuity, voltage, waveform, or visible-behavior testing is required |

Whenever physical connector order, visible lamp names, button legends, ring orientation, supply current, or pull-up values are blank, that is intentional. A golden reference is more useful when unknowns stay explicit than when guesses harden into pinouts.

## Contents

1. Source artefacts and integrity
2. Architecture and memory layout
3. Exact host protocol
4. Complete application register map
5. Remote-event engine
6. Bootloader, fuses, lock bits, and EEPROM
7. ATmega16L/Pico electrical reference
8. Firmware GPIO, buttons, status indicators, and ring
9. Six-pin connector discovery
10. Safe bench bring-up
11. Pico software
12. Test records and update rules
13. Primary references

## 1. Source artefacts and integrity

### Supplied and adjacent preserved reads

| File | Bytes | SHA-256 | Finding |
|---|---:|---|---|
| `sky_frontpanel_1.bin` | 16,322 (`0x3FC2`) | `B3EFC1C7B1C14DFA66AF35D642BD24E408389E8CB7B676618F4A14B2EA6FE1E4` | Authoritative Flash file analysed here |
| `sky_frontpanel_2.bin` | 16,322 (`0x3FC2`) | same as dump 1 | Byte-for-byte identical independent saved dump |
| `sky_frontpanel_eeprom.bin` | 512 | `076A27C79E5ACE2A3D47F9DD2E83E4FF6EA8872B3C2218F66C92B89B55F36560` | Every byte is `0x00`; only one saved read was available |
| `sky_lfuse.bin` | 1 | — | `0x24` |
| `sky_hfuse.bin` | 1 | — | `0xD8` |
| `sky_lock.bin` | 1 | — | raw `0xCF`; implemented low six bits are `0x0F` |

Keep the original files unchanged. Derived padded images, disassemblies, maps, and code must be named as derivatives and must retain these hashes in their notes.

### Why the Flash file is 16,322 bytes

The ATmega16 has `0x4000` bytes of Flash. The file ends at byte `0x3FC1`, leaving `0x3E`, or 62, bytes to the device limit. AVRDUDE documents that Flash reads normally omit trailing `0xFF` bytes. Option `-A` disables that removal. The last saved instruction is `08 95` (`RET`) at byte addresses `0x3FC0–0x3FC1`; the omitted tail is consistent with erased Flash.

This resolves the size discrepancy without changing the authoritative file. A future hardware read can preserve the full physical extent under a new filename:

```powershell
avrdude -A -c usbasp -p m16 -U flash:r:sky_frontpanel_full_with_ff.bin:r
```

That command is a read operation. Do not add erase or write operations. Compare bytes `0x0000–0x3FC1` with the authoritative file and confirm bytes `0x3FC2–0x3FFF` are all `0xFF`.

### Embedded application integrity check

The image carries a ten-byte descriptor at byte `0x37C0`:

```text
A1 C0 37 00 00 A2 B7 11 C1 C3
```

The bootloader validates it. Static recomputation gives:

```text
sum of application bytes 0x0000..0x37BF modulo 65536 = 0xB7A2
descriptor bytes 5..6, little endian                      = 0xB7A2

sum of descriptor bytes 0x37C0..0x37C8 modulo 256         = 0xC3
descriptor byte 0x37C9                                      = 0xC3
```

Both checks match exactly. This is strong evidence that the application region is complete and internally consistent, including its unusual interrupt-vector layout. The region `0x37CA–0x37FF` is erased (`0xFF`), and the 2 KiB boot area begins at byte `0x3800`.

### Repeatable static-analysis basis

The file was disassembled as raw AVR5/ATmega16 code with byte addresses. Tables in this document cite Flash byte addresses. AVR program-counter or datasheet vector tables sometimes use word addresses; when that distinction matters, both are stated.

## 2. Architecture and memory layout

```text
Pico / RP2040, I²C controller
            │  3.3 V SDA/SCL
            │
bidirectional open-drain level translator
            │  panel-side SDA/SCL at measured pull-up voltage
            │
ATmega16L application, I²C target 0x40
    ├── 15-button 3×5 matrix
    ├── 6 logical status channels
    ├── 8-position ring renderer
    └── remote timing decoder and event queue
```

### Flash and SRAM layout established by the binary

| Region | Address | Purpose |
|---|---:|---|
| Reset/application vectors | Flash bytes `0x0000…` | Application reset jumps to `0x00E6`; TWI vector at byte `0x0044` jumps to `0x01EA` |
| Application code/data | Flash bytes `0x0000–0x37BF` | Main application covered by embedded checksum |
| Application descriptor | Flash bytes `0x37C0–0x37C9` | Marker, length/checksum/version-like fields, descriptor checksum |
| Erased gap | Flash bytes `0x37CA–0x37FF` | All `0xFF` in the saved image |
| Bootloader | Flash bytes `0x3800–0x3FFF` | Fuse-selected 2 KiB boot section; saved code ends at `0x3FC1` |
| Public register bank | SRAM `0x0107–0x0147` | Host registers `0x00–0x40` |
| Remote FIFO | SRAM `0x00E0–0x00FF` | Sixteen little-endian 16-bit words |
| Button FIFO | SRAM `0x01D3–0x01F2` | Sixteen little-endian 15-bit state snapshots |

The public address mapping is simply:

```text
SRAM address = 0x0107 + application register number
```

The transport accepts writes throughout this whole bank. “Identification,” “status,” and event fields are conventions enforced by the main application only; they are not hardware-protected read-only bytes.

## 3. Exact host protocol

### Address

Firmware initializes `TWAR=0x80`. AVR stores the seven-bit target address in bits 7:1, so:

```text
seven-bit API address = 0x40
write address byte    = 0x80
read address byte     = 0x81
```

Use `0x40` with MicroPython, the Pico SDK, Arduino-style Wire APIs, and Linux I²C APIs. Those libraries add the read/write bit.

### Correct register write

One or more consecutive bytes can be written:

```text
START
0x80          target address + W
register      first register, 0x00..0x40
data[0]
data[1] ...   optional consecutive bytes
STOP
```

The pointer advances after each byte. Once it reaches `0x41`, additional write bytes are ignored.

### Correct register read: STOP is required between phases

```text
START
0x80          target address + W
register
STOP          REQUIRED BY THIS FIRMWARE

START
0x81          target address + R
data[0] ACK
data[1] ACK ...
last byte NACK
STOP
```

The conventional register-read pattern uses a repeated START after the pointer byte. This firmware's state variable is still in receive mode at that point and does not accept `SLA+R` there. It enters its error branch, temporarily disables TWI, and the main loop reinitializes it. A library call can therefore look like an intermittent NACK or bus reset even though address `0x40` is correct.

Use two calls, with `stop=True`/`nostop=false` on the pointer write and a separate read call. Do not use MicroPython `readfrom_mem()` unless its exact port implementation is proven to insert STOP; the ordinary memory-read contract commonly uses repeated START.

### Pointer and boundary behavior

- A pointer byte `0x00–0x40` is accepted.
- A pointer byte `0x41–0xFF` is clamped to the internal invalid sentinel `0x41`.
- Reads and writes auto-increment the pointer.
- Writes at the sentinel are ignored.
- A transmit attempted at the sentinel substitutes register index zero in the accessor. With the unmodified defaults that returns `0x00`, but register zero is itself transport-writable. Do not use out-of-range reads as a constant-zero test.
- The pointer is initialized to the invalid sentinel when TWI starts. Set it explicitly before every read.

### ACK, STOP, and error behavior

The state handler explicitly recognizes AVR target states `0x60`, `0x80`, `0xA0`, `0xA8`, `0xB8`, and `0xC0`. Unexpected states set an internal error flag and reset/re-enable the interface. The main loop also re-enables TWI if it observes the interface disabled. A robust host should stop the failed transaction, wait briefly, identify the panel again, and restore only its own known configuration.

### Transport write exposure

There is no per-register write-protection table. A sequential write can overwrite IDs, status, event mirrors, reserved bytes, command fields, and the boot-key input. For that reason:

- Keep a driver allowlist.
- Reject any host write whose start plus length crosses outside that allowlist.
- Do not bulk-restore the entire 65-byte bank.
- Do not implement a generic “write every possible register” discovery loop.
- Exclude `0x28` from fuzzing and automated pattern tests.
- Blank/disable outputs before changing several related animation values, then enable the final state.

### Host watchdog, register 0x34

Bit 7 enables the communication timeout; bits 6:0 are an approximate seconds threshold. Scheduler slot 48 runs once per approximately 10 ms frame. It accumulates 100 frames, increments a seconds counter, and disables TWI when the counter is no longer below the programmed threshold. Any TWI interrupt clears the seconds counter. Threshold zero with enable set still reaches the disabling branch at the first approximately one-second tick. Leave register `0x34=0x00` during discovery.

### Static protocol-model result

A narrow emulator executed the actual TWI handler instruction subset, rather than a rewritten pseudocode implementation. It checked:

- STOP-separated pointer/read framing;
- sequential read and write auto-increment;
- the absence of transport read-only protection;
- upper-bank and invalid-pointer behavior;
- the fact that reading `0x2E/0x2F` alone does not consume a remote event;
- register `0x31`'s five-load suppression and subsequent event service.

This validates interpretation of the binary. It is not a substitute for an oscilloscope or logic-analyser trace on the physical board.

## 4. Complete application register map

Defaults are the values exported by the application initialization path. “Avoid” means the byte can be transported but should not be changed in first bring-up.

| Reg | Default | Application meaning | Initial host policy | Confidence |
|---:|---:|---|---|---|
| `00` | `00` | Reserved; also invalid-read fallback byte | Read only | Firmware-proven |
| `01` | `C1` | Identity/version byte 1 | Read only | Firmware-proven |
| `02` | `11` | Identity/version byte 2 | Read only | Firmware-proven |
| `03` | `02` | Identity/version byte 3 | Read only | Firmware-proven |
| `04` | `00` | Application command bits | Avoid | Firmware-proven |
| `05` | `00` | Reserved | Read only | Firmware-proven |
| `06` | `01` | Ready/status, bit 0 set after initialization | Read only | Firmware-proven |
| `07–0B` | `00` | Reserved | Read only | Firmware-proven |
| `0C` | `67` | Global brightness in bits 2:0; upper field reaches a stubbed path | Allow lower bits carefully | Firmware-proven |
| `0D` | `32` | Blink duty parameter; decimal 50 by default | Allow with validation | Firmware-proven |
| `0E` | `E8` | Blink period low byte | Allow with validation | Firmware-proven |
| `0F` | `03` | Blink period high byte; default `0x03E8` | Allow with validation | Firmware-proven |
| `10` | `00` | Six-bit status-channel enable mask | Allow | Firmware-proven |
| `11` | `00` | Six-bit blink-participation mask | Allow | Firmware-proven |
| `12–13` | `00` | Reserved | Read only | Firmware-proven |
| `14` | `60` | Ring intensity low nibble; upper field mostly stubbed | Allow carefully | Firmware-proven |
| `15` | `31` | Ring style, direction-change alignment, length, unused bit 7 | Allow carefully | Firmware-proven |
| `16–17` | `00` | Reserved | Read only | Firmware-proven |
| `18` | `01` | Ring speed bits 6:0; direction bit 7 | Allow | Firmware-proven |
| `19` | `00` | Ring phase/hold and blanking | Allow | Firmware-proven |
| `1A–1D` | `00` | Reserved | Read only | Firmware-proven |
| `1E` | `FF` | Stored but no useful downstream operation found | Read only | Firmware-proven/negative search |
| `1F` | `00` | Reserved | Read only | Firmware-proven |
| `20` | `13` | Status brightness channels 0/1, packed nibbles | Allow 0–7 per nibble | Firmware-proven |
| `21` | `33` | Status brightness channels 2/3, packed nibbles | Allow 0–7 per nibble | Firmware-proven |
| `22` | `74` | Status brightness channels 4/5, packed nibbles | Allow 0–7 per nibble | Firmware-proven |
| `23` | `01` | Zero selects global brightness; nonzero per-channel | Allow 0/1 | Firmware-proven |
| `24` | `21` | Button observation multiplier and mode | Use `01` for simple live polling | Firmware-proven |
| `25` | `00` | Button FIFO control/status with a defective overflow-clear path | Avoid initially | Firmware-proven |
| `26` | `00` | Button held/direct bitmap low byte | Read | Firmware-proven |
| `27` | `00` | Button held/direct bitmap high byte, bits 6:0 used | Read | Firmware-proven |
| `28` | `00` | Bootloader key input | Never fuzz | Firmware-proven |
| `29` | `00` | Reserved | Read only | Firmware-proven |
| `2A` | `0F` | Implemented lock bits, masked to six bits | Read only | Firmware-proven |
| `2B` | `24` | Low fuse snapshot | Read only | Firmware-proven |
| `2C` | `D8` | High fuse snapshot | Read only | Firmware-proven |
| `2D` | `00` | Reserved | Read only | Firmware-proven |
| `2E` | `00` | Remote event mirror low byte | Read; experimental sentinel method writes zero | Firmware-proven |
| `2F` | `00` | Remote event mirror high byte | Read; experimental sentinel method writes zero | Firmware-proven |
| `30` | `00` | Button low-byte change-written mirror | Avoid for normal polling | Firmware-proven |
| `31` | `00` | Button high-byte mirror; loading it for transmit services events | Side-effecting read | Firmware-proven |
| `32–33` | `00` | Reserved | Read only | Firmware-proven |
| `34` | `00` | Host/TWI watchdog enable and threshold | Keep zero | Firmware-proven |
| `35–40` | `00` | No main-application use found | Read only | Firmware-proven/negative search |

### Register 0x04 commands

| Bit | Effect |
|---:|---|
| 2 (`0x04`) | Firmware clears the bit and jumps to application byte zero. This is an application restart, not an asserted hardware RESET and not the fuse-selected boot reset path. |
| 3 (`0x08`) | Runs the front-panel/application hardware initialization path, then clears the bit. |
| Other bits | No useful main-path effect established. |

Do not use either command until basic reads and physical mapping are complete. A power-cycle remains the clearest recovery during early bench work.

Detailed button, indicator, blink, and ring behavior appears in Chapter 8.

## 5. Remote-event engine

### Inputs and decoder status

The application configures PD2/INT/INT0 (PDIP pin 16) and PD3/INT1 (PDIP pin 17) as pulled-up inputs and enables both external interrupt bits with falling-edge configuration. Timing windows in the decoder are consistent with an RC6-family waveform, but the protocol family and field names should remain provisional until known remote keys are captured.

There is a vector-layout anomaly worth preserving exactly:

- the INT0 vector at Flash byte `0x0004` jumps to `0x2720`;
- the normal INT1 vector slot at byte `0x0008` contains erased words;
- the Timer2 Compare vector slot at byte `0x000C` jumps to code at `0x2732` that samples PD3.

The application and descriptor checksums are correct, so this is not evidence that the dump was randomly truncated or corrupted. It may depend on reserved-opcode fall-through or another compiler/device convention, but that is not safe to assert from static analysis. A live trace should establish whether both input paths work.

### Timing model

Timer0 nominally interrupts every 200 µs at the fuse-selected 8 MHz clock. Decoder interval counters add two each interrupt, so one software timing unit is nominally 100 µs. Observed acceptance windows include:

| Units | Nominal interval |
|---:|---:|
| 28–42 | 2.8–4.2 ms |
| 6–11 | 0.6–1.1 ms |
| 11–15 | 1.1–1.5 ms |
| 13–22 | 1.3–2.2 ms |

A release is synthesized after counter threshold `0x060E=1550`, nominally about 155 ms without a continuation. Interrupt overhead and internal-RC tolerance apply.

### Packed event word

The enqueue routine always sets bit 0 and packs a press/release flag plus four internal decoded fields:

```text
event = 1
      | (press_flag  << 1)
      | (field_020D  << 2)
      | (field_020C  << 4)
      | (field_020A  << 6)
      | (field_020B  << 8)
```

For ordinary decoded values this can be viewed as:

| Bits | Static meaning |
|---:|---|
| 0 | Valid-event marker, always 1 for a real queued event |
| 1 | 1 on decoded press; 0 on synthesized release |
| 3:2 | Internal field from SRAM `0x020D` |
| 5:4 | Internal field from SRAM `0x020C` |
| 7:6 | Internal field from SRAM `0x020A` |
| 15:8 | Internal field from SRAM `0x020B` |

Do not label the fields “device,” “toggle,” “address,” or “command” until captures from known keys prove those names. Log both the raw 16-bit value and these subfields.

### Remote FIFO

- Sixteen little-endian words at SRAM `0x00E0–0x00FF`.
- Count at `0x0067`, producer index `0x0068`, consumer index `0x0069`.
- A seventeenth enqueue attempt is dropped and sets internal overflow latch `0x0066`.
- The latch is not exposed through the public register bank in the analysed path.
- Pop copies one word to an internal output at `0x0100/0x0101`; the host service then copies it to public registers `0x2E/0x2F`.
- Popping an empty queue leaves the previous output and public mirror unchanged. A repeated value is therefore not proof of a new event.

### Hidden register-0x31 service hook

When register `0x31` is loaded for transmission, a counter is consulted:

1. The first five such loads after application initialization only increment a warm-up/suppression counter.
2. The sixth and every later load calls the remote FIFO pop routine.
3. If an event exists, it becomes the next value in `0x2E/0x2F`.
4. If no event exists, `0x2E/0x2F` stay stale.
5. Register `0x25` bit 0 is set regardless, coupling this action to button-FIFO service in default button mode.

Reading `0x2E/0x2F` does not itself pop an event. A four-byte read starting at `0x2E` returns the existing IR word and button mirrors; only when byte `0x31` is loaded near the end does it prepare the next IR word for a later poll. This explains a one-poll pipeline and stale-event replay.

### Recommended discovery approaches

The least invasive method is to mimic the pipeline, log all four bytes, and interpret changes cautiously. It cannot distinguish an empty queue from an identical repeated event.

An experimental deterministic method follows directly from the static model:

1. On a standalone Pico-controlled panel, load register `0x31` five times during initialization to pass the suppression count. This can consume events if some other host already primed it, so do it before accepting remote input.
2. Write `00 00` to the public mirrors `0x2E/0x2F`.
3. Read register `0x31` once to request one service.
4. Read exactly `0x2E/0x2F`.
5. Zero means no event; any real packed event has marker bit 0 set.

That procedure intentionally writes event mirrors. It is supported by the transport and static data flow, but it must be labelled experimental until a live panel confirms it. The companion driver implements it behind explicitly named methods.

## 6. Bootloader, fuses, lock bits, and EEPROM

### Fuse decode

The full electrical decode is in Chapter 7. The application also reads the implemented lock bits and both fuse bytes through boot-signature instructions and exports `0F 24 D8` at registers `0x2A–0x2C`. This matches the saved raw files once the unimplemented top two lock bits are masked.

The recorded high fuse selects reset into a 1,024-word/2,048-byte boot area beginning at word `0x1C00`, byte `0x3800`. Normal hardware reset therefore enters the bootloader first. The application command at register `0x04` bit 2 instead jumps to application byte zero.

### Application validation at boot

On an ordinary boot, the loader checks the descriptor marker and checksums described in Chapter 1 before transferring to the application. This is why the embedded checksum match is meaningful evidence.

### Application-to-boot key

The application initializes this 12-byte key in SRAM:

```text
14 22 1A C1 EB BC 1E 51 70 89 D8 1F
```

Register `0x28` is mirrored into the key watcher. The main loop notices value changes and compares each newly observed byte with the next expected key byte. A match advances; a mismatch clears progress. On all 12 matches it disables interrupts, writes handoff marker `0x387A` to SRAM `0x0060/0x0061`, and jumps to byte `0x3800`. The bootloader recognizes that marker and enters its special path rather than doing the ordinary application-validation transfer.

This is not a normal host command. Never include register `0x28` in register sweeps, random write tests, walking-bit tests, bank restore code, or untrusted host-controlled writes. The key is recorded here so future tools can explicitly blacklist both its register and sequence.

### Lock meaning

Raw lock byte `0xCF` has unimplemented upper bits set. The implemented value is `0x0F`: external programming lock bits are unprogrammed; application-section self-programming is unrestricted; boot-section self-write is blocked and application code is blocked from reading the boot section with LPM. Do not infer permission to alter the original controller from those technical settings.

### EEPROM finding

The 512-byte saved EEPROM file contains only `0x00`, not the normal erased value `0xFF`. A scan of the supplied application and boot image found no direct access to the ATmega16 EEPROM control/data/address I/O registers. The ordinary panel behavior therefore does not appear to depend on EEPROM.

Only one EEPROM file was available, so distinguish these facts:

- **File-proven:** the saved file is exactly 512 zero bytes.
- **Firmware-proven negative search:** no direct EEPROM I/O access was found.
- **Not proved:** that every physical controller of this board revision has all-zero EEPROM, or that the one read was independently repeated.

The high fuse has EESAVE unprogrammed, so a chip erase would erase EEPROM as well as destroying the original Flash application. No chip erase is part of the preservation workflow.

## 7. ATmega16L and Pico electrical reference

Research date: 2026-09-08. This is an independently sourced electrical reference. Supplied handoff values are prior recorded claims; they are not new measurements of the board. The main firmware analysis must establish application behaviour. No hardware was contacted or modified.

### Most important corrections to the previous handoff

1. The two-wire application interface and the SPI ISP programming interface are separate interfaces on separate pins. Programming access does not establish that the six-pin board connector is SPI.
2. A 3.3 V pull-up on a 5 V ATmega TWI bus does not meet its guaranteed high-input threshold: `0.7 × 5 = 3.5 V`. The general GPIO threshold does not apply to TWI.
3. A directly driven 3.3 V RESET is also unsuitable: its guaranteed high threshold at 5 V is `0.9 × 5 = 4.5 V`.
4. If the recorded low fuse `0x24` is correct, brownout is enabled at nominal 4.0 V. Running this original firmware at 3.3 V is therefore not an alternative to level translation. The general low-voltage capability of ATmega16L does not override its fuse settings.
5. The fuse values are separate nonvolatile configuration. Finding firmware instructions which read them proves the mechanism, not the actual values currently on a different panel. A raw Flash dump does not include the fuse memories.

The threshold calculations and fuse interpretation here use [ATmega16(L) datasheet 2466T, tables 9, 10, 15, 100, 103–106 and 120](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/doc2466.pdf).

### Device facts and complete PDIP-40 pin reference

ATmega16L: 16,384-byte Flash; 512-byte EEPROM; 1,024-byte SRAM; rated 2.7–5.5 V and 0–8 MHz. AVCC must be connected even without ADC use. AREF is an ADC reference, not a spare supply input. [ATmega16(L) datasheet, pages 1–5](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/doc2466.pdf).

Top view; notch at top; pin 1 upper left; numbering proceeds down the left and up the right. Board orientation is independent of this chip convention. Trace from the actual package notch/dot, not text direction in a photo.

| Pin | Signal | Pin | Signal |
|---:|---|---:|---|
| 1 | PB0/XCK/T0 | 40 | PA0/ADC0 |
| 2 | PB1/T1 | 39 | PA1/ADC1 |
| 3 | PB2/INT2/AIN0 | 38 | PA2/ADC2 |
| 4 | PB3/OC0/AIN1 | 37 | PA3/ADC3 |
| 5 | PB4/SS | 36 | PA4/ADC4 |
| 6 | PB5/MOSI | 35 | PA5/ADC5 |
| 7 | PB6/MISO | 34 | PA6/ADC6 |
| 8 | PB7/SCK | 33 | PA7/ADC7 |
| 9 | RESET | 32 | AREF |
| 10 | VCC | 31 | GND |
| 11 | GND | 30 | AVCC |
| 12 | XTAL2 | 29 | PC7/TOSC2 |
| 13 | XTAL1 | 28 | PC6/TOSC1 |
| 14 | PD0/RXD | 27 | PC5/TDI |
| 15 | PD1/TXD | 26 | PC4/TDO |
| 16 | PD2/INT0 | 25 | PC3/TMS |
| 17 | PD3/INT1 | 24 | PC2/TCK |
| 18 | PD4/OC1B | 23 | PC1/SDA |
| 19 | PD5/OC1A | 22 | PC0/SCL |
| 20 | PD6/ICP1 | 21 | PD7/OC2 |

Source: [ATmega16(L), figure 1, page 2](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/doc2466.pdf#page=2). Alternate-function labels describe silicon capabilities; they do not establish which functions this firmware enables or which pins reach the connector.

### Recorded fuse decode

Programmed fuse bit means **0**. These decoded settings are conditional on the prior handoff's `lfuse=0x24`, `hfuse=0xD8`, `lock & 0x3F=0x0F` being correct for the actual board.

| Recorded field | Decode |
|---|---|
| Low `0x24 = 0010 0100` | BODLEVEL=0; BODEN=0; SUT=10; CKSEL=0100 |
| BOD | Enabled, nominal 4.0 V; specified threshold range 3.6–4.5 V |
| Clock | Internal RC, nominal 8 MHz |
| Startup | 6 cycles plus nominal 65 ms |
| High `0xD8 = 1101 1000` | OCDEN=1; JTAGEN=1; SPIEN=0; CKOPT=1; EESAVE=1; BOOTSZ=00; BOOTRST=0 |
| Debug/programming | OCD disabled; JTAG disabled; ISP enabled |
| Erase consequence | EESAVE unprogrammed: EEPROM is not preserved by chip erase |
| Boot | 1,024 words / 2,048 bytes; reset at word `0x1C00`, byte `0x3800` |
| Lock low six bits `0x0F` | BLB12=0; BLB11=0; BLB02=1; BLB01=1; LB2=1; LB1=1 |
| Protection interpretation | External memory locks off; application self-programming unrestricted; boot self-write blocked and application LPM reads of boot blocked |

Source: [ATmega16(L), pages 29, 38, 249, 257 and 259–261](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/doc2466.pdf).

Inference for this panel: a missing external crystal is consistent with the decoded internal clock; it does not itself prove the fuse value. A fuse-selected boot reset also means power-on can pass through the bootloader before the application. A software jump to application byte zero is not necessarily equivalent to asserting the chip's RESET input. Clock-derived timing remains approximate until oscillator calibration and actual clock frequency are measured. Do not describe 65 ms as the complete time until the application is ready.

### Logic voltages

| Input class | High minimum | Low maximum | At 5 V: high / low |
|---|---:|---:|---:|
| ATmega ordinary GPIO | 0.6 VCC | 0.2 VCC | 3.0 / 1.0 V |
| ATmega TWI | 0.7 VCC | 0.3 VCC | 3.5 / 1.5 V |
| ATmega RESET | 0.9 VCC | 0.2 VCC | 4.5 / 1.0 V |

Source: [ATmega16(L), DC characteristics page 291 and TWI table 120 page 294](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/doc2466.pdf).

RP2040 uses 3.3 V I/O on Pico. Its GPIO absolute maximum is IOVDD+0.5 V; at nominal 3.3 V this is 3.8 V, **not an allowed 5 V input**. Recommended input high is at least 2.0 V and low at most 0.8 V at IOVDD=3.3 V. Internal pulls are weak, approximately 50–80 kΩ. Its specified loaded output-high floor is 2.62 V at configured drive current, so “Pico output is 3.3 V” is not a worst-case guarantee for an arbitrary load. [RP2040 datasheet, section 5.5.3, tables 622, 624 and 625](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf).

Engineering implications:

- For SDA and SCL, use bidirectional open-drain level translation with 3.3 V pull-ups on Pico side and the verified panel logic supply on panel side.
- Ordinary lightly loaded 5 V AVR inputs may recognise Pico outputs, but direct connection needs actual loading/noise-margin analysis. Do not generalise this to RESET or TWI.
- A unidirectional resistor divider is useful only for a confirmed unidirectional output into the Pico, with speed/loading checked. It is not a bidirectional I2C translator.
- A series resistor alone does not turn a Pico pin into a 5 V-tolerant input.
- If reset control is later required, an appropriate transistor/MOSFET can pull AVR RESET low, then release it to its target-side pull-up. The Pico must never be connected to that 5 V pull-up directly. Keep this additional control disconnected during first I2C tests.

### Selecting the arriving level-shifter modules

“5 V to 3.3 V stepdown” can describe several incompatible products. Identify the actual module circuitry before using it.

| Module type | Application to this panel |
|---|---|
| Buck/LDO power regulator | Converts supply voltage; does not translate SDA or SCL |
| Resistor-divider signal board | Unidirectional scaling; not suitable for this SDA/SCL link |
| Discrete MOSFET bidirectional I2C board | Suitable candidate, subject to pull-up and waveform checks |
| Explicit I2C translator, e.g. PCA9306 | Suitable candidate; obey that exact module/chip wiring |
| Push-pull/direction-controlled SPI translator | Do not assume I2C compatibility |

The discrete translator uses one N-channel MOSFET per signal: gate at the lower supply, source at the lower-voltage bus and drain at the higher-voltage bus. Each bus section has its own pull-ups. Either side pulling low must bring both sides low; when released, each side rises to its own supply. This supports bidirectional SDA and target clock stretching on SCL. [Nexperia AN10441, sections 2.1–2.1.1](https://assets.nexperia.com/documents/application-note/AN10441.pdf).

PCA9306 supports bidirectional I2C without a direction input, including 3.3/5 V translation. It is a named alternative, not a claim that the user's purchased module contains one. Bare-chip VREF2/EN wiring has a required bias-resistor arrangement; do not substitute the simplistic HV/LV module diagram for its datasheet circuit. [TI PCA9306](https://www.ti.com/product/PCA9306), [PCA9306 datasheet sections 8.1 and 9.2](https://www.ti.com/lit/ds/symlink/pca9306.pdf).

### Proposed wiring once connector continuity and supply are established

This table is a logical wiring plan, **not the six-pin connector's physical pin order**.

| Pico function | Pico physical pin | Translator | Panel destination |
|---|---:|---|---|
| GP4 / I2C0 SDA | 6 | LV1 ↔ HV1 | verified connector wire reaching AVR pin 23 |
| GP5 / I2C0 SCL | 7 | LV2 ↔ HV2 | verified connector wire reaching AVR pin 22 |
| 3V3(OUT) | 36 | LV supply/reference | no direct 5 V connection |
| GND | 8 or other GND | GND | verified panel ground |
| — | — | HV supply/reference | verified panel logic supply |

Pico pin numbering source: [official Pico Rev3 pinout](https://datasheets.raspberrypi.com/pico/Pico-R3-A4-Pinout.pdf). GP4/GP5 are a valid I2C0 pair, also used by the SDK's default Pico I2C example. [Raspberry Pi hardware I2C API](https://www.raspberrypi.com/documentation/pico-sdk/hardware.html#hardware_i2c).

Design recommendation: initially power Pico from its own USB connector and panel from a regulated, current-limited supply of the independently verified voltage; share only ground and translated signals. Measure the shifter low-side idle voltage before attaching Pico GPIO. Leave the two unidentified extra connector wires individually insulated. Do not infer supply from wire colour, capacitor voltage rating or the six-pin count.

### Pull-ups and waveform checks

I2C Standard-mode runs up to 100 kbit/s. Both lines normally use open-drain/open-collector outputs with pull-ups; an idle bus is high. Clock stretching lets a target keep SCL low while it is busy. Recovery guidance: if SDA is stuck low and SCL can rise, send up to nine clock pulses; persistent low then requires device reset or power-cycle. If SCL is stuck low, hardware reset/power-cycle is the preferred recovery. [NXP UM10204, sections 3.1.1, 3.1.9 and 3.1.16](https://www.nxp.com/docs/en/user-guide/UM10204.pdf).

The pull-up range follows `Rmin=(Vpullup−VOLmax)/IOL` and `Rmax=trmax/(0.8473×Cbus)`. Standard-mode maximum rise time is 1,000 ns; Fast-mode is 300 ns. [TI SLVA689, equations 1 and 6, table 1](https://www.ti.com/lit/an/slva689/slva689.pdf).

Worked engineering example, not measured panel values: 4.7 kΩ and 100 pF gives about 398 ns rise time; 10 kΩ gives about 847 ns. At 200 pF, 10 kΩ gives about 1.695 µs and misses the Standard-mode limit. These calculations ignore transistor and interconnect detail and must be checked on the assembled bus. A MOSFET-coupled low state also sinks pull-up current from both sides: at 5 V and 3.3 V with 4.7 kΩ each, `(5−0.4)/4700+(3.3−0.4)/4700≈1.60 mA`. Count existing module and panel pull-ups before adding resistors; two 4.7 kΩ resistors in parallel make 2.35 kΩ.

Recommended initial target: short leads, 100 kHz, measured idle LV approximately 3.3 V and HV approximately verified logic supply. Scope actual rise time and low voltage if unreliable. Slowing the clock can improve timing margin, but cannot correct wrong polarity, excessive voltage, inadequate high level or a shorted signal. Do not make numeric pull-up or supply-current choices permanent before measurement.

### Pico power and USB coexistence

On original RP2040 Pico, VBUS is the USB 5 V rail and feeds VSYS through the board's Schottky diode. VSYS is the regulator input and accepts approximately 1.8–5.5 V. For an additional external supply while USB may be connected, Raspberry Pi shows feeding external power into VSYS through another Schottky diode. That second diode prevents the USB-derived VSYS from driving backwards into the external supply. [Pico datasheet sections 4.4–4.5](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf), [Hardware design with RP2040, section 3.1.1](https://datasheets.raspberrypi.com/rp2040/hardware-design-with-rp2040.pdf).

Practical interpretation: do not tie an external regulated 5 V directly to Pico VBUS while also plugging in an independently powered USB host. The 3V3(OUT) pin is appropriate as the low-side translator reference/pull-up supply, not an assumed supply for the whole panel. Confirm model-specific power circuitry for Pico W, Pico 2 or third-party RP2040 boards; their names do not guarantee an identical power path.

### Software details useful to the driver author

MicroPython `machine.I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)` selects the suggested pins. `writeto` returns the number of acknowledged data bytes, so check it. The methods `readfrom_mem` and `writeto_mem` use a separate device address and register/memory address; `addrsize=8` selects a one-byte register address. The `timeout` constructor parameter is port/version dependent. `SoftI2C` documents a clock-stretch timeout explicitly. [MicroPython I2C API](https://docs.micropython.org/en/latest/library/machine.I2C.html), [RP2 quick reference](https://docs.micropython.org/en/latest/rp2/quickref.html#hardware-i2c-bus).

Pico C SDK `i2c_write_timeout_us` and `i2c_read_timeout_us` take a seven-bit target address. `nostop=true` retains the bus and makes the next transfer begin with a repeated START; `false` ends it with STOP. Check the returned count, generic error and timeout error. Use finite timeouts during discovery. [Raspberry Pi SDK I2C API](https://www.raspberrypi.com/documentation/pico-sdk/hardware.html#hardware_i2c).

Driver-specific engineering recommendations:

- Set the panel register pointer explicitly before every read. Use the exact framing independently proven by the firmware analysis.
- Prefer a targeted identification read over scanning the whole bus. A library scan is an active bus transaction; some scanners perform one-byte reads with possible device side effects.
- Do not equate “read-only discovery” with purely passive observation: register-pointer writes and ACKs are active transmissions.
- A logic analyser listening to an existing host needs protected inputs and must not enable extra bus-driving outputs or pull-ups accidentally.
- Bus recovery may complete a partial write transaction. Log the fault, recover only on the standalone known bus, then re-read identity and restore explicitly chosen state. Do not silently retry every failed write indefinitely.
- Keep any translator enable arrangement consistent with board power states. Validate that a powered Pico does not unintentionally feed an unpowered panel through signal paths.
- Add no application writes until the register map and side effects are confirmed. Avoid reset/bootloader commands in automatic discovery.

### Remaining board evidence required

No MCU datasheet can reveal the PCB designer's connector order. The six positions require unpowered continuity measurements to known GND, VCC/AVCC, SCL and SDA pins, plus tracing of the remaining two. A near-zero resistance is stronger evidence of a direct trace than a generic continuity beep; repeat readings with probe orientation reversed to distinguish semiconductor paths. Photographs of both PCB faces and a clearly marked connector orientation help, but are not a substitute for electrical confirmation. Firmware can establish which MCU pins are used, yet cannot uniquely prove wire colours, cable reversal, connector pin 1 or external pull-up voltage.

## 8. Firmware GPIO, buttons, status indicators, and ring

This is a static analysis of the supplied unmodified `sky_frontpanel_1.bin`, using its disassembly. All code addresses below are **Flash byte addresses**, not AVR word addresses. SRAM and I/O addresses are explicitly identified. It establishes how firmware drives MCU pins; PCB traces and powered observations are still required to associate pins with printed button legends or visible indicators. The application register bank begins at SRAM `0x0107`, so `reg[n]` means SRAM `0x0107+n`.

### Evidence map

| Code byte address | Function |
|---|---|
| `0x010A–0x0120` | Copy Flash data `0x0070–0x00E5` into SRAM `0x0063–0x00D8`, including scheduler |
| `0x043C–0x08D8` | Main-loop register interpretation and output publication |
| `0x08DA–0x0A1C` | Export initial internal settings to public register bank |
| `0x0B8C–0x0C52` | Indicator and animation initialization |
| `0x0C54–0x0CC0` | Blink duration calculation |
| `0x0CCA–0x0CF6` | Ring speed to step threshold |
| `0x0CF8–0x0F64` | Generate eight phases of seven PWM bitmaps |
| `0x0F66–0x108A` | Generate six-channel status PWM bitmaps |
| `0x108C–0x10DE` | First four ring outputs, PB5 bank |
| `0x10E0–0x1136` | Second four ring outputs, PB4 bank |
| `0x1138–0x11B4` | Status output PWM, PB6 bank plus PA1 and PA0 |
| `0x11B6–0x1242` | Blink tick |
| `0x1244–0x12A6` | Ring phase tick |
| `0x12A8–0x12E6` | Copy current ring phase into active PWM buffer |
| `0x1300–0x1334` | GPIO configuration |
| `0x1336–0x1362` | Ring logical-to-wiring bit permutation |
| `0x1364–0x1388` | Status logical-to-wiring permutation, identity for bits 0–5 |
| `0x138A–0x13BA` | Button engine initialization |
| `0x13BC–0x1404` | Append changed button snapshot to FIFO |
| `0x1406–0x1448` | Pop button FIFO into held output |
| `0x144A–0x1486` | Clear button FIFO |
| `0x1488–0x14BC` | Select one button column |
| `0x14BE–0x1558` | Sample button rows and build matrix word |
| `0x155A–0x1580` | Advance button accumulation-window timer |
| `0x1582–0x1600` | Permute and publish/queue button observation |
| `0x1602–0x160E` | Clear per-frame matrix word |
| `0x1610–0x1628` | Service button FIFO pop request |
| `0x162A–0x1694` | Button raw matrix to public bit permutation |
| `0x16A0–0x16BE` | Timer0 and interrupt setup |
| `0x1AE0–0x1B4A` | Timer0 overflow ISR |
| `0x1B50–0x1B8A` | 50-slot scheduler dispatcher |

### GPIO initialization and sharing

At `0x1300`, firmware sets bit 7 in `MCUCSR` twice, disabling JTAG so PC2–PC5 can be used as GPIO. It then writes:

| MCU register | I/O address | Value | Meaning |
|---|---:|---:|---|
| DDRA | `0x1A` | `03` | PA0 and PA1 outputs; other Port A pins inputs |
| PORTA | `0x1B` | `0C`, then `0F` | PA2/PA3 input pull-ups; PA0/PA1 initially high/off |
| DDRB | `0x17` | `FF` | All Port B pins outputs |
| PORTB | `0x18` | `00`, finally `0F` | PB0–PB3 high; PB4–PB6 bank enables low |
| DDRC | `0x14` | `00` | Port C inputs; hardware TWI later controls PC0/PC1 |
| PORTC | `0x15` | `FF` | Port C pull-ups enabled |
| DDRD | `0x11` | `00` | Port D inputs |
| PORTD | `0x12` | `FF` | Port D pull-ups enabled |

These MCU pins are multifunction and multiplexed by the existing firmware. PB0–PB2 are **both button columns and LED drive lines**. PB4–PB6 select LED banks. This matters when tracing: finding a button trace connected to PB0 is fully consistent with also finding an LED drive connection there.

The following physical numbering assumes the ATmega16L **40-pin PDIP** package viewed according to its notch/pin-1 mark, not the photograph's left/right orientation.

| MCU pin | PDIP pin | Firmware role |
|---|---:|---|
| PB0 | 1 | Matrix column 0; shared active-low indicator/ring drive 0 |
| PB1 | 2 | Matrix column 1; shared active-low indicator/ring drive 1 |
| PB2 | 3 | Matrix column 2; shared active-low indicator/ring drive 2 |
| PB3 | 4 | Shared active-low indicator/ring drive 3 |
| PB4 | 5 | Second ring bank enable, driven high during that bank |
| PB5 | 6 | First ring bank enable, driven high during that bank |
| PB6 | 7 | Status indicator bank enable, driven high during that bank |
| PB7 | 8 | Configured output, generally kept low by full PORTB writes; no application SPI engine established |
| PC2 | 24 | Matrix row 0, active low |
| PC3 | 25 | Matrix row 1, active low |
| PC4 | 26 | Matrix row 2, active low |
| PC5 | 27 | Matrix row 3, active low |
| PC6 | 28 | Matrix row 4, active low |
| PA1 | 39 | Logical status channel 4, active-low output |
| PA0 | 40 | Logical status channel 5, active-low output |

The phrase “active low” here describes firmware output logic, not a complete LED schematic. External transistors, resistors, rail polarity and visible LED labels require board tracing.

### Scheduler and real time

Timer0 setup writes `TCCR0=0`, `TCNT0=0x38`, then `TCCR0=0x02`. On this MCU, that is normal counting with clock prescaler 8. The Timer0 overflow ISR reloads `TCNT0=0x38` at `0x1AE8` each time.

Ignoring interrupt entry/reload overhead:

```text
timer counts per overflow = 256 - 0x38 = 200
nominal interrupt period  = 200 × 8 / F_CPU
at F_CPU=8 MHz           = 200 microseconds
nominal scheduler frame  = 50 interrupts = 10 milliseconds
```

The verified low fuse `0x24` selects the calibrated internal 8 MHz RC oscillator, subject to oscillator tolerance. There is no exact 1 ms hardware tick in these LED/button paths. Several routines use a 10-unit increment once per nominal 10 ms frame.

**The physical intervals are longer than these nominal numbers.** Reload is done after interrupt entry, the vector jump, a call, and a software register-saving prologue. The prologue `0x2A5E–0x2A8A` saves 20 registers plus SREG before the reload. Nominal 200 microseconds does not include this delay, interrupt collisions, periods with interrupts disabled, or RC oscillator error. Around 3–4% overhead is already plausible from this prologue at 8 MHz; do not advertise a crystal-accurate 1 second blink. For exact timing, measure a repeating bank-enable waveform and substitute its measured frame duration into the formulas below.

The scheduler table is Flash `0x0082–0x00E5`, copied into SRAM `0x0075–0x00D8`. It contains 50 pointers to Flash function-pointer words at `0x0054–0x006E`. Dispatch at `0x1B50` reads the slot, resolves the function pointer, and wraps slot number at 50.

| Slots | Function | Consequence |
|---|---|---|
| 0–7 | `0x108C` | Seven PWM slices and one blank slice for first ring bank |
| 8, 10, 12 | `0x1488` | Drive matrix columns PB0, PB1, PB2 low in order |
| 9, 11, 13 | `0x14BE` | Read PC2–PC6 after one nominal 200 us settling interval |
| 14–15 | Return stub | No scheduled operation |
| 16–23 | `0x10E0` | Seven PWM slices and blank for second ring bank |
| 24 | `0x11B6` | Advance blink engine once |
| 25 | `0x1244` | Advance ring step accumulator by 10 |
| 26 | `0x12A8` | Copy selected phase into active PWM masks |
| 27–31 | Return stub | No scheduled operation |
| 32–39 | `0x1138` | Seven status PWM slices and blank slice |
| 40–42 | Return stub | No scheduled operation |
| 43 | `0x155A` | Advance button observation-window counter |
| 44 | `0x1582` | Publish or enqueue completed button observation |
| 45 | `0x1602` | Clear per-frame matrix assembly word |
| 46 | `0x1610` | Service requested button queue pop |
| 47 | Return stub | No scheduled operation |
| 48 | `0x03BA` | Advance host watchdog |
| 49 | Return stub | No scheduled operation |

The shared PWM slice counter SRAM `0x01A9` runs 0–7 and returns to zero after each eight-slot group. This is why the three banks can share one counter.

### Exact button-to-MCU matrix mapping

The matrix contains 3 driven columns and 5 input rows. Drive order is PB0, PB1, PB2. A selected column is low while the other column lines are high. Row sampling uses:

```text
row_bits = ((~PINC) & 0x7C) >> 2
```

The first two column words are shifted left by five before the next row word is added. Thus the raw word is:

```text
raw = (rows_when_PB0_low << 10)
    | (rows_when_PB1_low << 5)
    |  rows_when_PB2_low
```

`0x162A–0x1694` permutes that word into public button bits. This permutation is explicit firmware evidence:

```text
raw bit -> public bit
0 -> 13, 1 -> 5, 2 -> 11, 3 -> 6, 4 -> 7,
5 -> 0, 6 -> 1, 7 -> 2, 8 -> 3, 9 -> 4,
10 -> 8, 11 -> 9, 12 -> 10, 13 -> 14, 14 -> 12.
```

The complete electrical mapping is therefore:

| Public bit | Mask | Driven column | Column PDIP pin | Sensed row | Row PDIP pin | Raw bit | Physical button legend |
|---:|---:|---|---:|---|---:|---:|---|
| 0 | `0001` | PB1 | 2 | PC2 | 24 | 5 | To measure |
| 1 | `0002` | PB1 | 2 | PC3 | 25 | 6 | To measure |
| 2 | `0004` | PB1 | 2 | PC4 | 26 | 7 | To measure |
| 3 | `0008` | PB1 | 2 | PC5 | 27 | 8 | To measure |
| 4 | `0010` | PB1 | 2 | PC6 | 28 | 9 | To measure |
| 5 | `0020` | PB2 | 3 | PC3 | 25 | 1 | To measure |
| 6 | `0040` | PB2 | 3 | PC5 | 27 | 3 | To measure |
| 7 | `0080` | PB2 | 3 | PC6 | 28 | 4 | To measure |
| 8 | `0100` | PB0 | 1 | PC2 | 24 | 10 | To measure |
| 9 | `0200` | PB0 | 1 | PC3 | 25 | 11 | To measure |
| 10 | `0400` | PB0 | 1 | PC4 | 26 | 12 | To measure |
| 11 | `0800` | PB2 | 3 | PC4 | 26 | 2 | To measure |
| 12 | `1000` | PB0 | 1 | PC6 | 28 | 14 | To measure |
| 13 | `2000` | PB2 | 3 | PC2 | 24 | 0 | To measure |
| 14 | `4000` | PB0 | 1 | PC5 | 27 | 13 | To measure |

This is already enough to identify a physical button by unpowered continuity tracing from its switch contacts to the column and row nets. It does not establish a front-to-back wire colour convention or a host connector pinout.

The PCB may include resistors and switching paths between a switch contact and the MCU, so a continuity buzzer alone may miss a valid route. Record resistance and both-direction diode-mode readings if a net is indirect. Do not power the board for resistance/continuity measurements. Firmware does not demonstrate matrix isolation diodes or establish safe multi-key rollover; test combinations before using button chords.

### Button modes: the default output is queued, not simply current state

`reg[0x24]` is decoded at `0x079C–0x07D0`:

```text
window_multiplier = reg[0x24] & 0x0F
mode              = (reg[0x24] >> 4) & 3
```

At slot 43, an 8-bit counter is incremented. A publish request occurs when it reaches `2 × window_multiplier`. For nonzero multipliers, the accumulation window is `2 × multiplier` scheduler frames: nominally `20 × multiplier` ms. Zero causes the condition to pass at the first tick, effectively one frame, nominal 10 ms.

Samples are **ORed across that window**. This is a “seen pressed at least once” window, not a proof that a switch was stable for its whole duration. Multiple presses seen at separate instants within the window can appear simultaneously in one reported bitmap. For macros, apply edge tracking and any additional debounce at the Pico/host layer.

| Mode | `reg[0x24]` example | Observed behavior at `0x1582` |
|---:|---:|---|
| 0 | `01` | Copy every completed observation directly into held output SRAM `0x014B–0x014C` |
| 1 | `11` | No branch publishes the observation; no established useful mode |
| 2 | `21`, factory default | Queue a new 15-bit snapshot when it differs from previous observed snapshot |
| 3 | `31` | No branch publishes the observation; no established useful mode |

In mode 0, `reg[0x26] | reg[0x27]<<8` is an observation of recent button state and is suitable for simple polling. In mode 2, it is the **held last dequeued snapshot**, and can remain zero while a button is pressed if the queue has not been advanced. Calling it “current buttons” without the mode qualification is wrong.

FIFO properties:

- 16 entries, each a 16-bit snapshot; SRAM buffer `0x01D3–0x01F2`.
- Count is SRAM `0x0070`, producer index `0x0071`, consumer index `0x0072`.
- Last observed state for change detection is SRAM `0x01F3–0x01F4`.
- Window accumulation is SRAM `0x01F7–0x01F8`.
- Held output is SRAM `0x014B–0x014C`.
- Empty pop leaves held output unchanged; there is no public “empty event” token.
- An entry represents a complete state, including releases, not just the newly pressed key.
- On a change with count 16, the new entry is dropped and internal overflow latch SRAM `0x0149` is set. Count exactly 16 does not itself set the latch: another enqueue attempt is necessary.
- Last observed state is updated **before** an attempted enqueue. If a final release is dropped, it will not be retried merely because queue space later becomes available.

#### Register 0x25 semantics and firmware defect

| Bit | Observed behavior |
|---:|---|
| 0 | Main loop sees bit set, sets internal pop request `0x014A=1`, clears bit 0; scheduler slot 46 consumes one queue entry in mode 2 and clears internal request |
| 1 | Calls FIFO clear `0x144A`, then clears bit 1 |
| 2 | Sticky public indication that internal overflow latch was set; **overflow**, not reliable current queue-full status |
| 3 | Clears internal overflow latch, but code at `0x0834` uses `ANDI 0xFD`, clearing bit 1 instead of bit 3; bit 3 and public bit 2 remain set unless host overwrites them |
| 4–7 | No useful effect established in this path |

Writing a literal `0x01` requests one pop and also overwrites other public status bits. Use a deliberate driver operation rather than generic read/modify/write, because copying back bit 3 repeats the defective branch. See the protocol chapter for the additional automatic pop request caused by reads through `0x31`.

FIFO clear zeros entries, counts, indices, overflow latch, and held output. It does **not** clear the last-observed state used for change detection (`0x01F3–0x01F4`). Consequently, clearing the queue while a key is held does not guarantee that held key will be re-enqueued; wait for a release and new press or switch to direct mode for resynchronization. Register 0x25 bit 2 is not cleared by the FIFO-clear routine itself.

`reg[0x26]/[0x27]` are populated from held output in the main loop only when no pop request is pending. Each byte is compared and updated separately. `reg[0x30]/[0x31]` receive the corresponding byte when that comparison detects a change. They are **change-written mirrors of the same output bytes**, not an independent button event queue. Because updates are bytewise, mixed old/new words are possible around transitions; a driver can read until two consecutive 16-bit samples agree if coherent state is essential. Reading through 0x31 has separate protocol side effects, so use 0x26/0x27 for direct-mode reads.

#### Practical Pico polling policy

For initial physical button mapping, direct mode `reg[0x24]=0x01` is the simplest firmware-derived choice. Keep any desired queue-based behavior as a separate tested mode. Read 0x26 and 0x27 in one transaction, mask to 0x7FFF, and compare snapshots:

```python
pressed = current & ~previous & 0x7FFF
released = previous & ~current & 0x7FFF
previous = current
```

Run mapping with one key at a time. Log raw hexadecimal words, not guessed legends. A nominal 10–20 ms Pico poll is reasonable; the MCU samples only once per approximately 10 ms frame and publishes every approximately 20 ms at multiplier 1. Additional Pico polling cannot recover pulses that occurred between matrix samples.

For queue mode, explicitly request a pop, allow at least one measured frame plus main-loop time for it to service, then read the held output. Continue servicing while the application runs; the queue can lose final releases on overflow. Recover host key state deliberately after any disconnection or overflow so a macro key cannot remain stuck.

### Six status indicator channels

The status LED engine builds seven threshold masks from brightness values and applies:

```text
active_channels = pwm_mask[slice] & reg[0x10] & current_blink_gate & 0x3F
```

`reg[0x10]` is the enable mask, bits 0–5. `reg[0x11]&0x3F` selects which channels participate in blinking. Nonblinking channels are included in the blink gate continuously. Disabled channels remain disabled even if their blink or brightness values are nonzero.

| Logical channel | Enable/blink bit | Brightness source | Firmware pin drive |
|---:|---:|---|---|
| 0 | `01` | `reg[0x20] & 15` | PB0 low while PB6 bank enabled |
| 1 | `02` | `reg[0x20] >> 4` | PB1 low while PB6 bank enabled |
| 2 | `04` | `reg[0x21] & 15` | PB2 low while PB6 bank enabled |
| 3 | `08` | `reg[0x21] >> 4` | PB3 low while PB6 bank enabled |
| 4 | `10` | `reg[0x22] & 15` | PA1 low |
| 5 | `20` | `reg[0x22] >> 4` | PA0 low |

`reg[0x23]=0` replaces all six per-channel nibbles with the common brightness `reg[0x0C]&7`. Any nonzero value selects the nibbles. Default `13 33 74` gives brightness 3, 1, 3, 3, 4, 7, and default source 1 selects them. Seven thresholds are generated: brightness 0 is dark, 1–7 enables that many slices, and 8–15 produces the same masks as 7.

#### Red/green standby indicator conclusion from the exact dump

The user supplied the exact panel image as `sky_frontpanel_1.bin` (16,322 bytes,
SHA-256 `B3EFC1C7B1C14DFA66AF35D642BD24E408389E8CB7B676618F4A14B2EA6FE1E4`).
The disassembly contains no colour names, colour selector, or power-state
variable. It exposes six generic active-low status outputs only: channels 0–3
are PB0–PB3 while the PB6 status bank is enabled, channel 4 is PA1, and channel
5 is PA0. The mainboard must write the status registers over the panel bus.

Therefore the dump alone cannot identify which output is the red die and which
is the green die, or prove that the visible standby lamp is connected to this
controller at all. If the lamp is a two-die LED on this board, its red and green
dies will appear as two of the six channels; if it is on the mainboard,
the panel MCU has no path to change it.

To identify the pair safely, blank the ring, clear the status mask, select low
per-channel brightness, then enable exactly one mask bit at a time (`0x01`,
`0x02`, `0x04`, `0x08`, `0x10`, `0x20`) and record the visible colour. The same
mapping can be captured non-invasively on the working Sky box by recording the
mainboard's writes to registers `0x10`, `0x11`, and `0x20`–`0x22` while the box
changes from red/off to green/on. Do not guess a colour from the logical
channel number.

#### Bench mapping recorded on the supplied panel

Using the panel's software-I²C bus and one mask at a time at low brightness:

| Mask | Channel | Observed lamp |
|---:|---:|---|
| `0x01` | 0 | Online indicator, green |
| `0x02` | 1 | Record indicator, red |
| `0x04` | 2 | Play indicator, green |
| `0x08` | 3 | Message indicator, yellow |
| `0x10` | 4 | Remote indicator, red |
| `0x20` | 5 | No visible lamp at brightness 2; the normal standby red power-button light remained unchanged |

This shows that the normal standby red power-button light is not selected by
channels 0–4. Channel 5 needs a separate brightness-7 test because PA0 has a
documented blank-slice exception; if it still does not change the standby lamp,
that lamp is electrically separate from the six status outputs (or is driven by
the mainboard/another LED path).

The upper nibble of register 0x0C and upper nibble of 0x14 both feed a shared variable `0x01B0`, but its downstream routine `0x0CC2` merely sets `0x01C5=1`; no reader of that flag was found. Those upper nibbles are not established colour, hardware-current, or contrast settings. Preserve their defaults if only adjusting a lower field.

#### Channel 5 PWM exception

At the blank slice, `0x118C–0x1198` disables PB bank gates, raises PB0–PB3 and raises PA1. It **does not raise PA0**. Therefore, when channel 5 has brightness 7 or higher and remains enabled, its active-low PA0 output can remain low between frames, producing a much larger effective duty than the ordinary seven-slice channels. At brightness 1–6, a later inactive slice explicitly raises PA0. Treat channel 5 brightness 7 as a special firmware behavior, not a linear small increment from 6. This is a pin-waveform conclusion; the visible result depends on circuitry connected to PA0.

For channels 0–4 and ordinary PWM operation, one brightness unit occupies approximately one out of 50 frame slots, and maximum seven slices is approximately 14% of the frame. LED peak current and perceived brightness cannot be computed from firmware alone.

#### Blink formula, clipping and limits

Let `P = reg[0x0E] | (reg[0x0F]<<8)` and `D = reg[0x0D]`. Code `0x0C54` computes:

```text
on16  = floor(P × D / 1000)
off16 = (floor(P / 10) - on16) modulo 65536
```

These are intended numbers of nominal 10 ms frames. However, `0x11FE–0x1220` copies only the **low byte** of either duration into the active counter limit `0x01C8`. Because the tick increments before comparison, an active limit of zero lasts one frame rather than zero:

```text
on_frames  = max(1, on16 & 0xFF)
off_frames = max(1, off16 & 0xFF)
period_real = (on_frames + off_frames) × measured_frame_time
```

Defaults `P=1000`, `D=50` give 50 frames on, 50 frames off: approximately one second, with the timer/oscillator qualifications above. `P=5000,D=50` gives 250+250 frames and is representable. `P=10000,D=50` yields 500 per half, truncated to 244 per half, so it does **not** yield ten seconds. Values D>100 can underflow the off-duration subtraction and have no established useful semantics.

Duty 0 or 100 still produces a minimum one-frame opposite phase. Use the enable and blink masks to request completely off or completely steady output instead of duty endpoints. A safe conventional blink helper should accept only D=1–99 and verify that both computed durations are in 1–255. Brightness and enable masks should be set before making the channel visible.

### Eight-position ring/animation engine

This engine produces eight logical positions. It stores eight phases × seven PWM masks at SRAM `0x0162–0x0199`, then copies the selected phase to SRAM `0x019A–0x01A0`. The scanner renders low packed nibble with PB5 enabled and high packed nibble with PB4 enabled.

`0x1336` maps logical ring position bits into physical packed bits:

| Logical position | Packed bit | Active-low drive | Bank high |
|---:|---:|---|---|
| 0 | 3 | PB3, pin 4 | PB5, pin 6 |
| 1 | 6 | PB2, pin 3 | PB4, pin 5 |
| 2 | 2 | PB2, pin 3 | PB5, pin 6 |
| 3 | 5 | PB1, pin 2 | PB4, pin 5 |
| 4 | 1 | PB1, pin 2 | PB5, pin 6 |
| 5 | 4 | PB0, pin 1 | PB4, pin 5 |
| 6 | 0 | PB0, pin 1 | PB5, pin 6 |
| 7 | 7 | PB3, pin 4 | PB4, pin 5 |

These are firmware positions, not verified clock-face positions. Find clockwise orientation by displaying one stationary position at a time and recording which segment glows.

| Register/field | Exact observed interpretation |
|---|---|
| `0x14 & 0x0F` | Head/flat trail brightness. Zero suppresses generated illumination. Threshold masks support 0–7; 8–15 saturates individual positions but changes fade arithmetic |
| `0x14 >> 4` | Shared mostly stubbed field described above |
| `0x15 & 7` | Style 0: flat brightness; style 1: integer linear fade; styles 2–7 leave positions dark in the observed generator |
| `0x15 bit 3` | Used to adjust phase when direction changes; does not independently relocate trail during ordinary steady-direction operation |
| `(0x15 >> 4)&7` | Length minus one; generated length 1–8 |
| `0x15 bit 7` | Stored, no meaningful downstream effect found |
| `0x18 & 0x7F` | Speed 0 stops automatic phase increment; 1–127 selects the threshold below |
| `0x18 bit 7` | Direction; changes phase rotation and trail layout. Physical clockwise/counterclockwise assignment needs observation |
| `0x19 & 7` | Desired position when bit 3 set |
| `0x19 bit 3` | Main loop repeatedly forces internal phase to low three register bits; automatic ticking can briefly increment it, so speed 0 should also be used for a fully stationary test |
| `0x19 bit 4` | Blanks ring rendering while retaining configuration and phase engine |
| `0x19 bits 5–7` | No effect established |
| `0x1E` | Copied internally but no downstream useful operation found |

#### Fade arithmetic

Let intensity be B and length L. For style 0, all L positions have intensity B. For style 1, the head has B, and trailing position j=1..L-1 gets:

```text
max(1, B - floor(B/L) × j)
```

This expression applies to nonzero B in the ordinary initialized state, where internal adjustment variables `0x01AA` and `0x01AB` remain zero. If B<L, integer division gives zero, so the supposedly fading trail is actually flat. Example B=7,L=4 gives 7,6,5,4; B=4,L=4 gives 4,3,2,1; B=3,L=4 gives 3,3,3,3. All generated positions then pass through seven PWM thresholds, saturating values above seven.

Default exposed `reg[0x15]=0x31` needs one subtle qualification: initialization stores internal alignment=1 and length-selector=2, but the export routine shifts alignment by **four** rather than three and ORs it with length-selector<<4. That produces 0x31. The main loop subsequently decodes it as alignment=0 and length-selector=3, so the eventual running configuration is a four-position trail. The public default is real, but the startup/export code is not a clean inverse of the decoder.

#### Speed arithmetic and examples

For nonzero speed s, `0x0CCA` performs a 16-bit unsigned divide of 10000 by s followed by three right shifts:

```text
threshold = floor(floor(10000/s)/8) = floor(1250/s)
step_frames = ceil(threshold/10)
step_real = step_frames × measured_frame_time
revolution_real = 8 × step_real
```

For all valid s=1–127, threshold is at least 9, so step_frames is at least 1. Accumulator is reset to zero on reaching the threshold, dropping any remainder; the result is quantized rather than a perfectly proportional speed.

| Speed | Threshold | Frames per step | Nominal step | Nominal revolution |
|---:|---:|---:|---:|---:|
| 0 | Retains previous threshold | No auto step | Stationary | Stationary |
| 1 | 1250 | 125 | 1.25 s | 10 s |
| 2 | 625 | 63 | 630 ms | 5.04 s |
| 5 | 250 | 25 | 250 ms | 2 s |
| 10 | 125 | 13 | 130 ms | 1.04 s |
| 25 | 50 | 5 | 50 ms | 400 ms |
| 50 | 25 | 3 | 30 ms | 240 ms |
| 100 | 12 | 2 | 20 ms | 160 ms |
| 125–127 | 10 or 9 | 1 | 10 ms | 80 ms |

#### Controlled output discovery recipes

All writes below refer to the firmware application registers, not direct MCU register writes. Only use them after supply, ground, host bus and level shifting have been verified.

To map a status channel, preserve existing settings, blank the ring (`0x19 bit4`), clear the status enable mask, select per-channel brightness, set modest brightness (for example 1 or 2 in each nibble), set blink mask zero, and enable exactly `1<<channel`. Log the visible lamp against that channel. Be particularly deliberate with channel 5 and brightness 7 because of the PA0 blanking exception.

To map ring position n, blank rendering first, set speed low seven bits to zero, choose style 0 and length 1 (`reg[0x15]=0x00`), set low intensity to 1 or 2 while preserving its upper nibble, and write `reg[0x19]=0x08 | (n&7)` to unblank and hold desired position. Step n from 0 through 7 and record the illuminated physical segment. Keep direction fixed while mapping. Restore saved settings after discovery.

To request a conventional moving four-position fading trail, intensity 4 and style/length value 0x31 yield levels 4,3,2,1; use a modest nonzero speed, clear reg19 bit3 and bit4, and leave direction fixed. This is an expected firmware-derived recipe, not a bench-verified cosmetic match to original animations.

#### What this analysis cannot settle

- The visible names and colours of six status channels.
- Which logical button bit corresponds to each printed legend.
- The physical ring orientation or whether one bank is wired through an unexpected external inversion.
- Peak LED current, resistor values, transistor topology or acceptable supply voltage for the whole board.
- The six-pin host connector's physical order.
- Actual frame rate, contact bounce, simultaneous-key ghosting, maximum reliable host bus speed, and any wiring-revision differences.

Those are finite measurements, not missing firmware algorithms. Preserve the tables above and fill their physical labels from controlled observations rather than replacing proven logical mappings with guesses.

### Photo-derived provisional button legend map

The supplied top-side photograph shows a complete `SW1…SW15` designator scheme. The firmware exposes exactly 15 public bits, and the apparent designator/legend sequence is a clean match for `public bit = SW number - 1`. This is a **strong photo-plus-firmware inference**, not yet a continuity or powered-press result:

| Public bit | Mask | Provisional PCB switch | Visible legend |
|---:|---:|---|---|
| 0 | `0001` | SW1 | Standby/power |
| 1 | `0002` | SW2 | Record |
| 2 | `0004` | SW3 | Play |
| 3 | `0008` | SW4 | Info |
| 4 | `0010` | SW5 | Rewind |
| 5 | `0020` | SW6 | Select |
| 6 | `0040` | SW7 | Left |
| 7 | `0080` | SW8 | Up |
| 8 | `0100` | SW9 | Fast-forward |
| 9 | `0200` | SW10 | Stop |
| 10 | `0400` | SW11 | TV Guide |
| 11 | `0800` | SW12 | Pause |
| 12 | `1000` | SW13 | Back Up |
| 13 | `2000` | SW14 | Right |
| 14 | `4000` | SW15 | Down |

Confirm this table by switching register `0x24` to direct mode and pressing each button once. If even one result differs, preserve the raw firmware matrix table and replace this provisional table with measured results for the exact board revision.

## 9. Six-pin connector discovery

### What firmware can and cannot tell us

Firmware proves the active application bus uses:

| Function | MCU signal | ATmega16L PDIP pin |
|---|---|---:|
| TWI clock | PC0/SCL | 22 |
| TWI data | PC1/SDA | 23 |
| Logic supply | VCC and AVCC | 10 and 30 |
| Ground | GND | 11 and 31 |

Firmware alone cannot reveal the physical order of an off-chip connector, but the measurements below now establish all six cable nets. Firmware still cannot prove the powered supply voltage or which cable colour lands on each J807 contact without the correctly oriented mainboard harness.

### Bench mapping completed 2026-09-09

An initial 180-degree package-counting error produced contradictory results. The chip was then recounted from the real pin-1 index and ground was independently corroborated at an electrolytic capacitor's negative terminal. With the loose panel isolated and unpowered, the corrected measurements are:

| Cable colour | Corrected measurement | Established function |
|---|---|---|
| Purple | Near zero to capacitor negative and MCU GND pin 11; also common with pin 31 | Ground |
| Blue | Near zero to capacitor negative and MCU GND pin 11; also common with pin 31 and purple | Second ground conductor |
| Brown | Direct to MCU VCC pin 10 and AVCC pin 30; approximately 1 kΩ to ground on the 2 kΩ range and over-range on 200 Ω | Panel MCU supply rail; actual powered voltage still to be measured |
| Green | 110 Ω to PC0/SCL pin 22 on the 200 Ω range; no corresponding low path to the other tested signal pins | I²C/TWI SCL through a 110 Ω series path |
| Orange | 110 Ω to PC1/SDA pin 23 on the 200 Ω range; no corresponding low path to the other tested signal pins | I²C/TWI SDA through a 110 Ω series path |
| Red | Approximately 100 Ω bidirectionally to PD3/INT1 pin 17 on the 200 Ω range; no corresponding path to pin 22 after correcting the package count | Second IR-decoder/external interrupt input, through a 100 Ω series path |

The equal 110 Ω readings establish deliberate series protection on both I²C lines. Red's destination agrees with firmware configuring PD3/INT1 as the second IR decoder input; the on-panel receiver uses the other IR input path at PD2/INT0. This makes red a mainboard-supplied external/remote-eye IR input with high confidence. Its idle voltage and pulse polarity should still be captured in the working box.

On the supplied component-side photograph, the ATmega pin-1 index is at the lower-left. The lower row runs pins 1→20 from left to right, while the upper row runs pins 40→21 from left to right. Pin 22/SCL is the second upper leg from the right; pin 23/SDA is the third upper leg from the right. Pin 17/INT1 is the fourth lower leg from the right and pin 16/INT0 is the fifth lower leg from the right. A 180-degree PDIP error is especially deceptive because it swaps the apparent VCC and GND pin groups while preserving their pair pattern.

The panel connector's observed board-entry colour order is purple, blue, green, orange, red, brown. If the original black plug is installed on J807 with brown nearest the printed pin-1/mounting-hole end, the provisional J807 order is `1 brown/VCC, 2 red/external IR, 3 orange/SDA, 4 green/SCL, 5 blue/GND, 6 purple/GND`. Confirm this by photographing the correctly fitted working-box plug or by continuity from J807 pin 1 to brown before treating it as the physical mainboard pinout.

### Define connector numbering before measuring

1. Disconnect every power source, USB lead, original host cable, programmer, and Pico.
2. Discharge the board and verify zero volts.
3. View the PCB connector from one fixed side and photograph it.
4. Find an actual PCB pin-1 triangle, square pad, silk number, or keyed-housing convention. Do not use rainbow colour order as the definition.
5. The mainboard header is `J807`; its printed pin 1 is at the chamfered end nearest the mounting hole. Record which cable colour reaches `J807-1` before relying on the provisional order below. State whether the view is board-entry side, mating face, or solder side.

### Unpowered continuity workflow

Use resistance mode as well as the continuity buzzer. Record actual resistance; repeat questionable measurements with probe polarity reversed.

1. Find any connector position near zero ohms to MCU pins 11 and 31 and the ground side of decoupling capacitors. Mark it **GND candidate**, then corroborate it at several ground nodes.
2. Find any position connected to MCU pins 10 and 30. Trace whether it is direct, through a filter/ferrite/resistor, or after a regulator/transistor. Mark it **logic-rail candidate**, not “5 V,” until powered measurement proves voltage.
3. Check every remaining position to pin 22 (SCL) and pin 23 (SDA). Also note pull-up resistance from each candidate bus line to the logic-rail candidate.
4. Check any remaining conductor against RESET pin 9, RXD/TXD pins 14/15, INT0/INT1 pins 16/17, and obvious transistor or LED-supply networks.
5. Check for diode-mode paths to either rail. Semiconductor paths can make a continuity buzzer misleading.
6. Inspect both board faces if possible. A top-only photo cannot follow vias and bottom traces reliably.

| Provisional J807 position | Wire colour | Resistance to MCU destination | Established cable function | Powered idle voltage | Confidence/notes |
|---:|---|---:|---|---:|---|
| 1 | Brown | Direct to pins 10/30 | MCU supply rail | not measured | J807 position provisional until fitted orientation is checked |
| 2 | Red | Approximately 100 Ω to pin 17 | External/mainboard IR input | not measured | Cable function high confidence; J807 position provisional |
| 3 | Orange | 110 Ω to pin 23 | SDA | not measured | Cable function established; J807 position provisional |
| 4 | Green | 110 Ω to pin 22 | SCL | not measured | Cable function established; J807 position provisional |
| 5 | Blue | Near zero to pins 11/31 and capacitor negative | Ground | not measured | Cable function established; J807 position provisional |
| 6 | Purple | Near zero to pins 11/31 and capacitor negative | Ground | not measured | Cable function established; J807 position provisional |

### Powered confirmation

The safest source of connector-voltage truth is the unmodified original host, measured at the connector with a common meter reference, if it is available and can be operated safely. Otherwise, trace the power network far enough to establish which rail feeds the MCU before applying a regulated current-limited supply.

With correct power and no Pico GPIO attached:

- measure MCU VCC at pins 10/11 and AVCC at 30/31;
- measure every connector position at idle;
- measure SDA and SCL idle-high voltage;
- watch start-up current and component temperature;
- check red's idle voltage and whether it pulses during an external/mainboard remote event;
- do not apply 12 V merely because an electrolytic capacitor is rated for 16 V.

The brownout fuse makes approximately 5 V logic a strong expectation, but it is not a substitute for tracing the board supply.

### Logical finished wiring after confirmation

| Pico | Translator | Panel |
|---|---|---|
| GP4, physical pin 6, I2C0 SDA | LV1 ↔ HV1 | verified connector position reaching AVR pin 23 |
| GP5, physical pin 7, I2C0 SCL | LV2 ↔ HV2 | verified connector position reaching AVR pin 22 |
| 3V3(OUT), physical pin 36 | LV reference/pull-up rail | no direct connection to panel 5 V |
| GND, e.g. physical pin 8 | common GND | verified connector ground |
| verified panel logic rail | HV reference/pull-up rail | panel supply side only |

Leave red, the external/mainboard IR input, insulated during initial I²C testing. It is not needed for basic panel register access.

## 10. Safe bench bring-up

### Phase A — preservation

- Keep both original Flash reads, EEPROM read, and fuse/lock reads unchanged.
- Record board revision, chip notch orientation, connector-view convention, and all file hashes.
- If hardware remains available, obtain another full Flash read with `-A` and a second EEPROM/fuse/lock read. These are read-only operations.
- Never use chip erase on the preservation controller.

### Phase B — identify power and bus with no Pico attached

- Complete the continuity table above.
- Confirm rail polarity and voltage with a current-limited setup or the original host.
- Measure bus pull-ups and idle voltages.
- Verify that SDA/SCL are high at idle and show no unexpected voltage when the panel is unpowered.

### Phase C — validate the translator by itself

- Confirm it is a bidirectional open-drain I²C translator, not a power regulator, resistor-divider board, or direction-controlled push-pull SPI translator.
- Connect LV to Pico 3.3 V, HV to the verified panel logic rail, and common ground.
- Before connecting GP4/GP5, power both sides and measure about 3.3 V on LV SDA/SCL and the verified logic voltage on HV SDA/SCL.
- Count built-in and external pull-ups. Start with short leads and 100 kHz.

### Phase D — identity read

Target address `0x40` directly. Do not begin with writes to application controls. Perform the required STOP-separated transactions:

```text
pointer 0x01 + STOP; read 3 bytes  -> expected C1 11 02
pointer 0x06 + STOP; read 1 byte   -> expected bit 0 = 1
pointer 0x2A + STOP; read 3 bytes  -> expected 0F 24 D8
```

If the target ACKs but reads fail, inspect the transaction shape first. A repeated START is a known incompatibility. If nothing ACKs, confirm bus sides, grounds, pull-up voltages, pinout, and MCU supply before changing software timing.

### Phase E — button mapping

1. Write `0x01` to register `0x24` to select simple direct mode, multiplier 1.
2. Read `0x26/0x27` together twice until two successive values match.
3. Press one physical button at a time and record the 15-bit mask on press and release.
4. Confirm idle returns to zero.
5. Test carefully chosen two-key combinations and record ghosting; do not assume arbitrary chords work.

| Public bit | Mask | Printed legend | Idle | Pressed | Released | Multi-key notes |
|---:|---:|---|---:|---:|---:|---|
| 0 | `0001` |  |  |  |  |  |
| 1 | `0002` |  |  |  |  |  |
| 2 | `0004` |  |  |  |  |  |
| 3 | `0008` |  |  |  |  |  |
| 4 | `0010` |  |  |  |  |  |
| 5 | `0020` |  |  |  |  |  |
| 6 | `0040` |  |  |  |  |  |
| 7 | `0080` |  |  |  |  |  |
| 8 | `0100` |  |  |  |  |  |
| 9 | `0200` |  |  |  |  |  |
| 10 | `0400` |  |  |  |  |  |
| 11 | `0800` |  |  |  |  |  |
| 12 | `1000` |  |  |  |  |  |
| 13 | `2000` |  |  |  |  |  |
| 14 | `4000` |  |  |  |  |  |

### Phase F — status-channel mapping

Blank the ring, clear `0x10` and `0x11`, select low brightness, then enable one of six bits at a time. Never begin with all outputs at maximum. Record visible color and name.

| Logical channel | Mask | MCU output path | Visible indicator/color | Brightness notes |
|---:|---:|---|---|---|
| 0 | `01` | PB0/PB6 bank |  |  |
| 1 | `02` | PB1/PB6 bank |  |  |
| 2 | `04` | PB2/PB6 bank |  |  |
| 3 | `08` | PB3/PB6 bank |  |  |
| 4 | `10` | PA1 |  |  |
| 5 | `20` | PA0 |  | note special maximum behavior |

### Phase G — ring mapping

Use speed zero, trail length one, modest intensity, and positional hold. Step positions 0–7. Record clock-face position and direction; firmware logical numbering alone cannot establish the visible order.

| Logical position | Packed bit/path | Visible position | Notes |
|---:|---|---|---|
| 0 | bit 3, PB3/PB5 |  |  |
| 1 | bit 6, PB2/PB4 |  |  |
| 2 | bit 2, PB2/PB5 |  |  |
| 3 | bit 5, PB1/PB4 |  |  |
| 4 | bit 1, PB1/PB5 |  |  |
| 5 | bit 4, PB0/PB4 |  |  |
| 6 | bit 0, PB0/PB5 |  |  |
| 7 | bit 7, PB3/PB4 |  |  |

### Phase H — remote capture

- Prime the service hook on a standalone initialized panel.
- Capture one known key at a time, including hold and release.
- Record raw word, press flag, all four generic fields, delay to release, and whether both IR inputs are active.
- Repeat each key to find toggle/repeat behavior before naming fields.

| Key label | Raw press | Raw release | bits 3:2 | bits 5:4 | bits 7:6 | bits 15:8 | Repeat/toggle notes |
|---|---:|---:|---:|---:|---:|---:|---|
|  |  |  |  |  |  |  |  |

### Failure recovery

On timeout, NACK, or malformed data:

1. End the transaction with STOP if the controller permits it.
2. Do not blindly replay a multi-register write.
3. Allow the panel main loop to re-enable TWI, then read identity and ready state.
4. If SDA is stuck low while SCL can rise, up to nine controller-generated SCL pulses are the standard bus-clear attempt; then issue STOP.
5. If SCL stays low or identity does not recover, remove panel power, inspect wiring, and restart from known settings.
6. Reconcile button state so a prior press cannot remain logically stuck in the Pico application.

## 11. Pico software

### MicroPython setup

The companion driver uses I2C0 on GP4/GP5 at 100 kHz:

```python
from machine import I2C, Pin
from panel import Panel

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100_000)
panel = Panel(i2c)
print(panel.identify())       # expected b"\xC1\x11\x02"
panel.direct_button_mode(1)

previous = panel.buttons()
while True:
    current = panel.buttons()
    pressed = current & ~previous & 0x7FFF
    released = previous & ~current & 0x7FFF
    previous = current
```

The driver calls `writeto(..., stop=True)` for the register pointer and then makes a separate `readfrom()` call. This detail is intentional.

### Complete reference driver

The same code is supplied as `panel.py` beside this Markdown file. It is syntax-checked and its transaction guardrails are host-tested, but physical behavior remains to be confirmed on the panel.

```python
"""ATmega16L panel host driver for MicroPython on RP2040.

Static-analysis reference implementation; not yet tested on physical hardware.
This talks to the original application over I2C. It does not program the AVR.
"""
try:
    from time import sleep_ms
except ImportError:  # Allows host-side tests under ordinary CPython.
    from time import sleep

    def sleep_ms(milliseconds):
        sleep(milliseconds / 1000)


class Panel:
    ADDRESS = 0x40
    ID = b'\xc1\x11\x02'
    # Only configuration registers used by this reference driver are writable.
    WRITABLE = frozenset((0x0c, 0x0d, 0x0e, 0x0f, 0x10, 0x11,
                          0x14, 0x15, 0x18, 0x19, 0x20, 0x21,
                          0x22, 0x23, 0x24))

    def __init__(self, i2c):
        self.i2c = i2c
        self.identified = False
        self._ir_service_primed = False

    @staticmethod
    def _range(reg, length):
        if not isinstance(reg, int) or not isinstance(length, int):
            raise ValueError('integer register and length required')
        if length < 1 or reg < 0 or reg + length > 0x41:
            raise ValueError('register range must fit 0x00..0x40')

    def read(self, reg, length=1, allow_event_service=False):
        self._range(reg, length)
        if reg <= 0x31 < reg + length and not allow_event_service:
            raise ValueError('reading 0x31 has event-service side effects')
        # This AVR firmware requires STOP after the pointer byte.  Its TWI
        # state machine does not accept the usual repeated-START memory read.
        acked = self.i2c.writeto(self.ADDRESS, bytes((reg,)), True)
        if acked != 1:
            raise OSError('register pointer was not acknowledged')
        data = self.i2c.readfrom(self.ADDRESS, length, True)
        if len(data) != length:
            raise OSError('short panel read')
        return data

    def identify(self):
        self.identified = False
        ident = self.read(0x01, 3)
        if ident != self.ID:
            raise OSError('unexpected panel identity: ' + repr(ident))
        if not (self.read(0x06)[0] & 1):
            raise OSError('panel is not ready')
        self.identified = True
        return ident

    def write(self, reg, data):
        data = bytes(data)
        self._range(reg, len(data))
        if not self.identified:
            raise RuntimeError('call identify() successfully before configuration')
        if any(r not in self.WRITABLE for r in range(reg, reg + len(data))):
            raise ValueError('write outside the driver configuration allowlist')
        payload = bytes((reg,)) + data
        acked = self.i2c.writeto(self.ADDRESS, payload, True)
        if acked != len(payload):
            raise OSError('panel configuration was not fully acknowledged')

    def _write_mirrors(self, reg, data):
        """Narrow internal write for the experimental IR empty sentinel."""
        data = bytes(data)
        if reg != 0x2e or data != b'\x00\x00':
            raise ValueError('only zeroing the two IR mirrors is allowed')
        payload = bytes((reg,)) + data
        acked = self.i2c.writeto(self.ADDRESS, payload, True)
        if acked != len(payload):
            raise OSError('IR mirror clear was not fully acknowledged')

    def direct_button_mode(self, scan_multiplier=1):
        if not 1 <= scan_multiplier <= 15:
            raise ValueError('scan multiplier must be 1..15')
        # Keep bits 6..7; bits 4..5 = 0 selects direct sampled state.
        config = (self.read(0x24)[0] & 0xc0) | scan_multiplier
        self.write(0x24, (config,))
        # Nominal report interval is (multiplier + 1) * 10ms.
        sleep_ms((scan_multiplier + 2) * 12)

    def buttons(self):
        # Two matching reads reduce tearing; the firmware has no atomic snapshot.
        previous = self.read(0x26, 2)
        for _ in range(3):
            current = self.read(0x26, 2)
            if current == previous:
                return (current[0] | (current[1] << 8)) & 0x7fff
            previous = current
        raise OSError('button state changed throughout repeated reads')

    def steady_leds(self, mask, brightness=(1, 1, 1, 1, 1, 1)):
        if not 0 <= mask <= 0x3f:
            raise ValueError('LED mask must be 0..0x3f')
        if len(brightness) != 6 or any(not 0 <= b <= 7 for b in brightness):
            raise ValueError('six brightness values, each 0..7, required')
        self.write(0x10, (0, 0))  # Disable status channels and their blink mask.
        packed = tuple(brightness[i] | (brightness[i + 1] << 4)
                       for i in (0, 2, 4))
        self.write(0x20, packed + (1,))
        sleep_ms(20)
        self.write(0x10, (mask,))

    def blink_leds(self, enable_mask, blink_mask, period_ms=1000, duty=50):
        if not 0 <= enable_mask <= 0x3f or not 0 <= blink_mask <= 0x3f:
            raise ValueError('LED masks must be 0..0x3f')
        # Firmware stores phase durations as 8-bit counts of nominal 10ms.
        if not 1 <= period_ms <= 65535 or not 1 <= duty <= 99:
            raise ValueError('nonzero period; duty 1..99 required')
        on = period_ms * duty // 1000
        off = period_ms // 10 - on
        if not 1 <= on <= 255 or not 1 <= off <= 255:
            raise ValueError('each blink phase must fit 1..255 firmware frames')
        self.write(0x11, (0,))
        self.write(0x0d, (duty, period_ms & 255, period_ms >> 8))
        sleep_ms(20)
        self.write(0x10, (enable_mask, blink_mask & enable_mask))

    def ring_off(self):
        self.write(0x19, (self.read(0x19)[0] | 0x10,))

    def ring(self, intensity=1, speed=8, reverse=False,
             trail=4, style=1, phase=0):
        if not 0 <= intensity <= 7 or not 0 <= speed <= 127:
            raise ValueError('intensity 0..7 and speed 0..127 required')
        if not 1 <= trail <= 8 or style not in (0, 1) or not 0 <= phase <= 7:
            raise ValueError('trail 1..8, style 0/1, phase 0..7 required')
        self.ring_off()
        sleep_ms(20)
        self.write(0x14, (0x60 | intensity, ((trail - 1) << 4) | style))
        self.write(0x18, (speed | (0x80 if reverse else 0),))
        sleep_ms(20)
        self.write(0x19, ((0x08 | phase) if speed == 0 else 0,))

    def prime_ir_service_experimental(self):
        """Pass the firmware's five-load suppression counter after boot.

        Call before relying on IR.  If another host has already primed this
        counter, these reads can consume queued events, so use only on a Pico-
        controlled standalone panel during initialization.
        """
        if not self.identified:
            raise RuntimeError('identify the panel before priming IR service')
        for _ in range(5):
            self.read(0x31, 1, allow_event_service=True)
        self._ir_service_primed = True

    def poll_ir_experimental(self):
        """Return one decoded raw event dictionary or None if the queue is empty.

        This procedure follows the static firmware model but needs live-panel
        validation.  Every real packed event has marker bit 0 set.
        """
        if not self._ir_service_primed:
            raise RuntimeError('prime IR service once after panel initialization')
        self._write_mirrors(0x2e, b'\x00\x00')
        self.read(0x31, 1, allow_event_service=True)
        raw = self.read(0x2e, 2)
        word = raw[0] | (raw[1] << 8)
        if word == 0:
            return None
        if not (word & 1):
            raise OSError('malformed IR event without marker bit')
        return {'raw': word,
                'pressed': bool(word & 0x0002),
                'field_020d': (word >> 2) & 0x03,
                'field_020c': (word >> 4) & 0x03,
                'field_020a': (word >> 6) & 0x03,
                'field_020b': (word >> 8) & 0xff}

    def event_probe(self):
        # Diagnostic only: low IR pair is read before the 0x31 preload updates it.
        # The IR word can be stale, including its bit 0. Do not emit HID from it.
        data = self.read(0x2e, 4, allow_event_service=True)
        return {'ir_previous': data[0] | (data[1] << 8),
                'button_mirror': (data[2] | (data[3] << 8)) & 0x7fff}
```

### Minimal Pico SDK C primitives

Both calls below pass `nostop=false`. The pointer phase therefore ends with STOP.

```c
#include <stddef.h>
#include <stdint.h>
#include "hardware/i2c.h"

#define PANEL_ADDR 0x40u
#define PANEL_TIMEOUT_US 20000u

int panel_read(i2c_inst_t *bus, uint8_t reg, uint8_t *dst, size_t len) {
    if (!dst || len == 0 || reg > 0x40 || len > (size_t)(0x41 - reg)) {
        return PICO_ERROR_GENERIC;
    }
    int rc = i2c_write_timeout_us(bus, PANEL_ADDR, &reg, 1,
                                  false, PANEL_TIMEOUT_US); /* STOP */
    if (rc != 1) return rc < 0 ? rc : PICO_ERROR_GENERIC;
    rc = i2c_read_timeout_us(bus, PANEL_ADDR, dst, len,
                            false, PANEL_TIMEOUT_US);       /* STOP */
    return rc == (int)len ? rc : (rc < 0 ? rc : PICO_ERROR_GENERIC);
}

int panel_write(i2c_inst_t *bus, uint8_t reg,
                const uint8_t *src, size_t len) {
    if (!src || len == 0 || reg > 0x40 || len > (size_t)(0x41 - reg)
        || len > 8) {
        return PICO_ERROR_GENERIC;
    }
    uint8_t frame[9];
    frame[0] = reg;
    for (size_t i = 0; i < len; ++i) frame[i + 1] = src[i];
    int rc = i2c_write_timeout_us(bus, PANEL_ADDR, frame, len + 1,
                                  false, PANEL_TIMEOUT_US);
    return rc == (int)(len + 1) ? rc : (rc < 0 ? rc : PICO_ERROR_GENERIC);
}
```

Put a semantic allowlist above `panel_write()` in production. The primitive intentionally shows framing, not permission policy.

### Ready-to-flash RP2040 tester

The companion `Pico_FrontPanel_Tester` package contains a native Pico SDK
firmware image for the original Raspberry Pi Pico/Pico H (RP2040), plus its
complete source and a Windows USB-serial helper. The hardware-facing release is
`DRX280_Pico_RP2040_Tester_v1.0.0.uf2`. It was built with Pico SDK 2.2.0 and Arm
GNU Toolchain 13.3.1. Its UF2 blocks were decoded, reconstructed and compared
byte-for-byte with the linked flat binary; the result also matches the Microsoft
UF2 reference converter. Physical-panel behavior still needs the first live
test.

The tester starts with GP4 and GP5 released and confirms both translated bus
lines are high. It reads identity `C1 11 02` and ready bit 0 before any
configuration write. After identification it turns every output off, selects
direct button mode, runs one brightness-2-of-7 status/ring sweep, turns every
output off again, and begins debounced button reporting over USB serial. The
Pico's onboard LED is solid while the panel is identified and blinks while the
link is offline.

Its serial commands cover individual and swept status channels, validated
blink timing, stationary and moving ring patterns in both directions, coherent
button snapshots and edges, safe register reads, a bounded open-drain bus-clear
procedure, link statistics, and explicit opt-in experimental IR capture. There
is no arbitrary register-write command. All ordinary writes go through the
same semantic allowlist as the MicroPython reference. Register `0x28` is
explicitly forbidden, reads spanning side-effecting register `0x31` are refused,
and the only exceptional write is a fixed two-byte zero sentinel at `0x2E/0x2F`
inside the experimental IR routine.

The principal console commands are:

```text
info
off
led <0-5|all> <brightness 0-6>
ledtest [brightness] [step-ms]
blink <mask> <brightness> <period-ms> <duty>
ring <position 0-7> [intensity]
ringtest [intensity] [step-ms]
spin <speed> [intensity] [trail] [reverse 0|1]
demo
buttons [on|off|once]
ir [on|off|once]
read <register> [count]
recover
stats
```

`demo` is finite and ends off. It covers all six logical status channels,
blinking, all eight stationary ring positions, and a moving trail in both
directions. IR remains off until explicitly requested. The tester reports raw
button bits and provisional names; it does not yet emit USB keyboard events.

With a basic BSS138 translator, power the confirmed panel rail and HV reference
first, then attach Pico USB so the LV reference rises to 3.3 V. At shutdown,
remove Pico USB first and then panel power. This avoids relying on an inexpensive
translator for powered-off-side isolation. Do not move Dupont connections while
powered.

### Suggested Pico-side state model

- Treat the hardware register bank as volatile. Identify and configure it after every power-up or application restart.
- Keep a local desired-output state. Update related registers while their output is blank/disabled, then enable once coherent.
- In direct button mode, derive press and release edges from successive 15-bit snapshots.
- Map physical legends only after filling the measurement table; keep raw bit numbers in logs.
- If producing downstream key events, release every logically held key on bus loss, Pico USB reset, mode change, or panel reinitialization.
- Rate-limit retries and log the first bus fault. A tight retry loop can hide a repeated-START framing bug and continually reset the target interface.
- Preserve unknown/reserved bytes rather than treating them as scratch storage.

### Driver validation status

The static TWI harness and Python syntax checks pass. The reference code also constrains register ranges, checks ACK counts, blocks writes before identity, uses a configuration allowlist, refuses implicit reads through side-effecting register `0x31`, validates blink-duration truncation limits, and labels IR service experimental. The six cable colours now have bench-traced logical functions. The remaining connector work is to confirm colour-to-J807 order with the correctly fitted plug and measure live voltage, current and signal levels in the working receiver; visible indicator orientation still requires live validation.

## 12. Test records and update rules

### Facts to add after measurements

When a bench result is obtained, add:

- board marking/revision and which physical panel was tested;
- connector viewing direction and marked pin 1;
- instrument and mode;
- power state and rail voltage;
- exact procedure;
- raw reading or logic trace;
- conclusion and confidence;
- whether a second run reproduced it.

Do not silently replace a firmware logical mapping with a visible-label guess. Add the visible label in the blank column and preserve the logical bit/path.

### Revision checklist

- Recompute and retain all source hashes.
- Keep Flash byte addresses distinct from AVR word addresses.
- Mark code as static-model tested or hardware tested.
- Record translator part number and module schematic, not only a marketplace title.
- Record pull-ups actually fitted on both sides.
- Record panel supply current in idle, all-status-on, and ring-active conditions once safely measured.
- Record exact I²C waveform shape, including the STOP between pointer and read.
- Capture the original host traffic if available; it is the best way to confirm intended queue and remote semantics.
- Never mark connector positions confirmed from colour alone.

## 13. Primary references

- [Microchip ATmega16(L) datasheet 2466T](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/doc2466.pdf)
- [Raspberry Pi RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [Raspberry Pi Pico datasheet](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf)
- [Raspberry Pi Pico Rev3 pinout](https://datasheets.raspberrypi.com/pico/Pico-R3-A4-Pinout.pdf)
- [Raspberry Pi Pico SDK hardware I²C API](https://www.raspberrypi.com/documentation/pico-sdk/hardware.html#hardware_i2c)
- [MicroPython machine.I2C API](https://docs.micropython.org/en/latest/library/machine.I2C.html)
- [MicroPython RP2 quick reference](https://docs.micropython.org/en/latest/rp2/quickref.html#hardware-i2c-bus)
- [NXP UM10204 I²C-bus specification and user manual](https://www.nxp.com/docs/en/user-guide/UM10204.pdf)
- [Nexperia AN10441 bidirectional level shifting for I²C](https://assets.nexperia.com/documents/application-note/AN10441.pdf)
- [TI PCA9306 product page and datasheet](https://www.ti.com/product/PCA9306)
- [TI SLVA689 I²C bus pull-up resistor calculation](https://www.ti.com/lit/an/slva689/slva689.pdf)
- [AVRDUDE 8 option documentation, including `-A` and Flash-read truncation](https://avrdudes.github.io/avrdude/8.0/avrdude_4.html)

---

End of golden reference version 1.1.
