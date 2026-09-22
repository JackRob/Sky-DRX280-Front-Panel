# ATmega16L front-panel / Pico electrical reference

Research date: 2026-09-08. This is an independently sourced electrical reference. Supplied handoff values are prior recorded claims; they are not new measurements of the board. The main firmware analysis must establish application behaviour. No hardware was contacted or modified.

## Most important corrections to the previous handoff

1. The two-wire application interface and the SPI ISP programming interface are separate interfaces on separate pins. Programming access does not establish that the six-pin board connector is SPI.
2. A 3.3 V pull-up on a 5 V ATmega TWI bus does not meet its guaranteed high-input threshold: `0.7 × 5 = 3.5 V`. The general GPIO threshold does not apply to TWI.
3. A directly driven 3.3 V RESET is also unsuitable: its guaranteed high threshold at 5 V is `0.9 × 5 = 4.5 V`.
4. If the recorded low fuse `0x24` is correct, brownout is enabled at nominal 4.0 V. Running this original firmware at 3.3 V is therefore not an alternative to level translation. The general low-voltage capability of ATmega16L does not override its fuse settings.
5. The fuse values are separate nonvolatile configuration. Finding firmware instructions which read them proves the mechanism, not the actual values currently on a different panel. A raw Flash dump does not include the fuse memories.

The threshold calculations and fuse interpretation here use [ATmega16(L) datasheet 2466T, tables 9, 10, 15, 100, 103–106 and 120](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/doc2466.pdf).

## Device facts and complete PDIP-40 pin reference

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

## Recorded fuse decode

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

## Logic voltages

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

## Selecting the arriving level-shifter modules

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

## Proposed wiring once connector continuity and supply are established

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

## Pull-ups and waveform checks

I2C Standard-mode runs up to 100 kbit/s. Both lines normally use open-drain/open-collector outputs with pull-ups; an idle bus is high. Clock stretching lets a target keep SCL low while it is busy. Recovery guidance: if SDA is stuck low and SCL can rise, send up to nine clock pulses; persistent low then requires device reset or power-cycle. If SCL is stuck low, hardware reset/power-cycle is the preferred recovery. [NXP UM10204, sections 3.1.1, 3.1.9 and 3.1.16](https://www.nxp.com/docs/en/user-guide/UM10204.pdf).

The pull-up range follows `Rmin=(Vpullup−VOLmax)/IOL` and `Rmax=trmax/(0.8473×Cbus)`. Standard-mode maximum rise time is 1,000 ns; Fast-mode is 300 ns. [TI SLVA689, equations 1 and 6, table 1](https://www.ti.com/lit/an/slva689/slva689.pdf).

Worked engineering example, not measured panel values: 4.7 kΩ and 100 pF gives about 398 ns rise time; 10 kΩ gives about 847 ns. At 200 pF, 10 kΩ gives about 1.695 µs and misses the Standard-mode limit. These calculations ignore transistor and interconnect detail and must be checked on the assembled bus. A MOSFET-coupled low state also sinks pull-up current from both sides: at 5 V and 3.3 V with 4.7 kΩ each, `(5−0.4)/4700+(3.3−0.4)/4700≈1.60 mA`. Count existing module and panel pull-ups before adding resistors; two 4.7 kΩ resistors in parallel make 2.35 kΩ.

Recommended initial target: short leads, 100 kHz, measured idle LV approximately 3.3 V and HV approximately verified logic supply. Scope actual rise time and low voltage if unreliable. Slowing the clock can improve timing margin, but cannot correct wrong polarity, excessive voltage, inadequate high level or a shorted signal. Do not make numeric pull-up or supply-current choices permanent before measurement.

## Pico power and USB coexistence

On original RP2040 Pico, VBUS is the USB 5 V rail and feeds VSYS through the board's Schottky diode. VSYS is the regulator input and accepts approximately 1.8–5.5 V. For an additional external supply while USB may be connected, Raspberry Pi shows feeding external power into VSYS through another Schottky diode. That second diode prevents the USB-derived VSYS from driving backwards into the external supply. [Pico datasheet sections 4.4–4.5](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf), [Hardware design with RP2040, section 3.1.1](https://datasheets.raspberrypi.com/rp2040/hardware-design-with-rp2040.pdf).

Practical interpretation: do not tie an external regulated 5 V directly to Pico VBUS while also plugging in an independently powered USB host. The 3V3(OUT) pin is appropriate as the low-side translator reference/pull-up supply, not an assumed supply for the whole panel. Confirm model-specific power circuitry for Pico W, Pico 2 or third-party RP2040 boards; their names do not guarantee an identical power path.

## Software details useful to the driver author

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

## Remaining board evidence required

No MCU datasheet can reveal the PCB designer's connector order. The six positions require unpowered continuity measurements to known GND, VCC/AVCC, SCL and SDA pins, plus tracing of the remaining two. A near-zero resistance is stronger evidence of a direct trace than a generic continuity beep; repeat readings with probe orientation reversed to distinguish semiconductor paths. Photographs of both PCB faces and a clearly marked connector orientation help, but are not a substitute for electrical confirmation. Firmware can establish which MCU pins are used, yet cannot uniquely prove wire colours, cable reversal, connector pin 1 or external pull-up voltage.
