from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
OUT = ROOT / "outputs"


def demote(markdown, chapter_title):
    """Turn a standalone report into a chapter without changing its prose."""
    lines = markdown.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    shifted = []
    for line in lines:
        if re.match(r"^#{2,6} ", line):
            line = "#" + line
        shifted.append(line)
    return "## " + chapter_title + "\n\n" + "\n".join(shifted).strip() + "\n"


INTRO = r'''# DR-X280_2 / PCBR-2694-01 front-panel controller

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
'''


ARTEFACTS = r'''## 1. Source artefacts and integrity

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
'''


ARCH = r'''## 2. Architecture and memory layout

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
'''


PROTOCOL = r'''## 3. Exact host protocol

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
'''


REGISTERS = r'''## 4. Complete application register map

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
'''


IR_BOOT = r'''## 5. Remote-event engine

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
'''


CONNECTOR = r'''## 9. Six-pin connector discovery

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
'''


PHOTO_MAPPING = r'''### Photo-derived provisional button legend map

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
'''


PICO_INTRO = r'''## 11. Pico software

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
'''


PICO_AFTER = r'''```

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
'''


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    electrical = demote((WORK / "electrical_reference.md").read_text(encoding="utf-8"),
                         "7. ATmega16L and Pico electrical reference")
    peripherals = demote((WORK / "peripherals.md").read_text(encoding="utf-8"),
                          "8. Firmware GPIO, buttons, status indicators, and ring")
    panel_code = (WORK / "panel.py").read_text(encoding="utf-8").rstrip()
    document = "\n\n".join((INTRO.strip(), ARTEFACTS.strip(), ARCH.strip(),
                              PROTOCOL.strip(), REGISTERS.strip(), IR_BOOT.strip(),
                              electrical.strip(), peripherals.strip(), PHOTO_MAPPING.strip(),
                              CONNECTOR.strip(),
                              PICO_INTRO.strip() + "\n" + panel_code + "\n" +
                              PICO_AFTER.strip())) + "\n"
    md_path = OUT / "DRX280_FrontPanel_ATmega16L_Pico_Golden_Reference.md"
    code_path = OUT / "panel.py"
    md_path.write_text(document, encoding="utf-8", newline="\n")
    code_path.write_text(panel_code + "\n", encoding="utf-8", newline="\n")
    print(md_path)
    print(code_path)


if __name__ == "__main__":
    build()
