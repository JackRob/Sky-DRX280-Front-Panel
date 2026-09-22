# Firmware-derived GPIO, buttons, status indicators and ring

This is a static analysis of the supplied unmodified `sky_frontpanel_1.bin`, using its disassembly. All code addresses below are **Flash byte addresses**, not AVR word addresses. SRAM and I/O addresses are explicitly identified. It establishes how firmware drives MCU pins; PCB traces and powered observations are still required to associate pins with printed button legends or visible indicators. The application register bank begins at SRAM `0x0107`, so `reg[n]` means SRAM `0x0107+n`.

## Evidence map

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

## GPIO initialization and sharing

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

## Scheduler and real time

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

## Exact button-to-MCU matrix mapping

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

## Button modes: the default output is queued, not simply current state

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

### Register 0x25 semantics and firmware defect

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

### Practical Pico polling policy

For initial physical button mapping, direct mode `reg[0x24]=0x01` is the simplest firmware-derived choice. Keep any desired queue-based behavior as a separate tested mode. Read 0x26 and 0x27 in one transaction, mask to 0x7FFF, and compare snapshots:

```python
pressed = current & ~previous & 0x7FFF
released = previous & ~current & 0x7FFF
previous = current
```

Run mapping with one key at a time. Log raw hexadecimal words, not guessed legends. A nominal 10–20 ms Pico poll is reasonable; the MCU samples only once per approximately 10 ms frame and publishes every approximately 20 ms at multiplier 1. Additional Pico polling cannot recover pulses that occurred between matrix samples.

For queue mode, explicitly request a pop, allow at least one measured frame plus main-loop time for it to service, then read the held output. Continue servicing while the application runs; the queue can lose final releases on overflow. Recover host key state deliberately after any disconnection or overflow so a macro key cannot remain stuck.

## Six status indicator channels

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

The upper nibble of register 0x0C and upper nibble of 0x14 both feed a shared variable `0x01B0`, but its downstream routine `0x0CC2` merely sets `0x01C5=1`; no reader of that flag was found. Those upper nibbles are not established colour, hardware-current, or contrast settings. Preserve their defaults if only adjusting a lower field.

### Channel 5 PWM exception

At the blank slice, `0x118C–0x1198` disables PB bank gates, raises PB0–PB3 and raises PA1. It **does not raise PA0**. Therefore, when channel 5 has brightness 7 or higher and remains enabled, its active-low PA0 output can remain low between frames, producing a much larger effective duty than the ordinary seven-slice channels. At brightness 1–6, a later inactive slice explicitly raises PA0. Treat channel 5 brightness 7 as a special firmware behavior, not a linear small increment from 6. This is a pin-waveform conclusion; the visible result depends on circuitry connected to PA0.

For channels 0–4 and ordinary PWM operation, one brightness unit occupies approximately one out of 50 frame slots, and maximum seven slices is approximately 14% of the frame. LED peak current and perceived brightness cannot be computed from firmware alone.

### Blink formula, clipping and limits

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

## Eight-position ring/animation engine

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

### Fade arithmetic

Let intensity be B and length L. For style 0, all L positions have intensity B. For style 1, the head has B, and trailing position j=1..L-1 gets:

```text
max(1, B - floor(B/L) × j)
```

This expression applies to nonzero B in the ordinary initialized state, where internal adjustment variables `0x01AA` and `0x01AB` remain zero. If B<L, integer division gives zero, so the supposedly fading trail is actually flat. Example B=7,L=4 gives 7,6,5,4; B=4,L=4 gives 4,3,2,1; B=3,L=4 gives 3,3,3,3. All generated positions then pass through seven PWM thresholds, saturating values above seven.

Default exposed `reg[0x15]=0x31` needs one subtle qualification: initialization stores internal alignment=1 and length-selector=2, but the export routine shifts alignment by **four** rather than three and ORs it with length-selector<<4. That produces 0x31. The main loop subsequently decodes it as alignment=0 and length-selector=3, so the eventual running configuration is a four-position trail. The public default is real, but the startup/export code is not a clean inverse of the decoder.

### Speed arithmetic and examples

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

### Controlled output discovery recipes

All writes below refer to the firmware application registers, not direct MCU register writes. Only use them after supply, ground, host bus and level shifting have been verified.

To map a status channel, preserve existing settings, blank the ring (`0x19 bit4`), clear the status enable mask, select per-channel brightness, set modest brightness (for example 1 or 2 in each nibble), set blink mask zero, and enable exactly `1<<channel`. Log the visible lamp against that channel. Be particularly deliberate with channel 5 and brightness 7 because of the PA0 blanking exception.

To map ring position n, blank rendering first, set speed low seven bits to zero, choose style 0 and length 1 (`reg[0x15]=0x00`), set low intensity to 1 or 2 while preserving its upper nibble, and write `reg[0x19]=0x08 | (n&7)` to unblank and hold desired position. Step n from 0 through 7 and record the illuminated physical segment. Keep direction fixed while mapping. Restore saved settings after discovery.

To request a conventional moving four-position fading trail, intensity 4 and style/length value 0x31 yield levels 4,3,2,1; use a modest nonzero speed, clear reg19 bit3 and bit4, and leave direction fixed. This is an expected firmware-derived recipe, not a bench-verified cosmetic match to original animations.

### What this analysis cannot settle

- The visible names and colours of six status channels.
- Which logical button bit corresponds to each printed legend.
- The physical ring orientation or whether one bank is wired through an unexpected external inversion.
- Peak LED current, resistor values, transistor topology or acceptable supply voltage for the whole board.
- The six-pin host connector's physical order.
- Actual frame rate, contact bounce, simultaneous-key ghosting, maximum reliable host bus speed, and any wiring-revision differences.

Those are finite measurements, not missing firmware algorithms. Preserve the tables above and fill their physical labels from controlled observations rather than replacing proven logical mappings with guesses.
