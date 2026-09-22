# DRX280 front-panel six-pin connector: continuity probe plan

**Board/controller:** ATmega16L-8PU, 40-pin PDIP  
**Purpose:** identify the physical connector order without relying on wire colour.  
**Status before starting:** the firmware proves that the application bus is **I²C/TWI**, not SPI. Its known logical connections are GND, the panel logic supply, SCL and SDA. The other two connector functions remain unknown.

## Non-negotiable setup

- [ ] Disconnect the panel from its original mainboard, Pico, USB, programmer and every power supply.
- [ ] Put the meter leads in **COM** and **V/Ω**. Never use the current/A socket for this work.
- [ ] Select DC volts first and confirm the board has **0 V** remaining.
- [ ] Then select resistance/continuity mode.
- [ ] Touch the two probes together and record the lead resistance: ______ Ω.
- [ ] Stabilise the PCB on a non-conductive surface.
- [ ] Do not force a meter probe into a connector socket; use a thin back-probe or touch the exposed PCB header/solder joint.

**Never use continuity or resistance mode on a powered board.**

## Number the connector before assigning functions

Use the actual metal contacts, not the rainbow wire colours. Check the physical connector in person: if it has more than six occupied contacts, extend every table to `J1-7`, `J1-8`, and so on.

Pick one fixed view, photograph it, and write the convention here:

> PCB side/view: ________________________________________________

Look for a silk-screen `1`, triangle, square solder pad or housing key. If none exists, temporarily call the contacts `J1-1` through `J1-6` from left to right in your stated view. This is a measurement convention, not a claim about the manufacturer's pin 1.

## How to count the ATmega16L legs

This is a **top view** of the chip, with its notch or semicircular end at the top. Pin 1 is immediately left of the notch. Count down the left side to pin 20, cross the bottom, then count up the right side from pin 21 to pin 40.

```text
                         NOTCH
                    ┌──────∪──────┐
       PB0       1  │ •          │ 40  PA0
       PB1       2  │            │ 39  PA1
       PB2       3  │            │ 38  PA2
       PB3       4  │            │ 37  PA3
       PB4       5  │            │ 36  PA4
       PB5/MOSI  6  │            │ 35  PA5
       PB6/MISO  7  │            │ 34  PA6
       PB7/SCK   8  │            │ 33  PA7
       RESET     9  │            │ 32  AREF       ← not a supply pin
       VCC      10  │            │ 31  GND
       GND      11  │            │ 30  AVCC
       XTAL2    12  │            │ 29  PC7
       XTAL1    13  │            │ 28  PC6
       PD0/RXD  14  │            │ 27  PC5
       PD1/TXD  15  │            │ 26  PC4
       PD2/INT0 16  │            │ 25  PC3
       PD3/INT1 17  │            │ 24  PC2
       PD4      18  │            │ 23  PC1/SDA    ← I²C data
       PD5      19  │            │ 22  PC0/SCL    ← I²C clock
       PD6      20  │____________│ 21  PD7
```

Probe a real chip leg or its solder pad gently. Avoid touching two adjacent legs with one probe.

## First-pass targets

| Test order | Function sought | ATmega16L pin(s) | What would count as good evidence |
|---:|---|---:|---|
| 1 | Ground | **11 and 31** | The same connector contact measures close to lead resistance to both pins and other known ground points |
| 2 | Logic supply | **10 (VCC) and 30 (AVCC)** | The same contact reaches both, directly or through a small filter/ferrite resistance |
| 3 | I²C clock | **22 (PC0/SCL)** | One remaining contact has the uniquely lowest resistance to pin 22 |
| 4 | I²C data | **23 (PC1/SDA)** | One remaining contact has the uniquely lowest resistance to pin 23 |
| 5 | First unknown wire | **9, 14, 15, 16, 17** | Direct or clearly lowest resistance to RESET, RXD, TXD, INT0 or INT1 |
| 6 | Second unknown wire | **9, 14, 15, 16, 17** | As above, or it may enter a transistor, LED or separate supply network rather than an MCU leg |
| Rule-out only | ISP/SPI pins | **6, 7 and 8** | Check only after the above; firmware does not use these as the panel's application link |

Do **not** call pin 32 (`AREF`) the supply. The supply pair is pins **10 and 30**; the ground pair is **11 and 31**.

## Exact measurement sequence

For every step, keep one probe on the named chip leg and touch the other probe to `J1-1`, `J1-2` … `J1-6`. Record the resistance, even if the continuity buzzer does not sound.

### A. Find ground

1. Measure all connector contacts to MCU pin **11**.
2. Repeat all contacts to MCU pin **31**.
3. A ground candidate should agree at both MCU ground pins.
4. If accessible, corroborate it at the negative/striped side connection of a decoupling capacitor whose other end is on VCC. Do not decide from capacitor stripe alone without tracing it.

Ground candidate: J1-____  Resistance to pin 11: ______ Ω  Resistance to pin 31: ______ Ω

### B. Find the logic-supply wire

1. Measure every non-ground contact to MCU pin **10**.
2. Repeat to MCU pin **30**.
3. The likely supply contact should reach both. A ferrite bead or resistor may make it higher than a bare copper trace.
4. Label it **logic-rail candidate**. Do not label it 5 V until a powered voltage measurement proves that.

Logic-rail candidate: J1-____  Resistance to pin 10: ______ Ω  Resistance to pin 30: ______ Ω

### C. Find SCL and SDA

1. Measure every remaining contact to pin **22**. The best direct/lowest match is the **SCL candidate**.
2. Measure every remaining contact to pin **23**. The best direct/lowest match is the **SDA candidate**.
3. Reverse the probes and repeat any uncertain result. A reading that changes greatly with probe direction may be going through a diode/transistor rather than a direct trace.

SCL candidate: J1-____  Resistance to pin 22: ______ Ω / reversed: ______ Ω  
SDA candidate: J1-____  Resistance to pin 23: ______ Ω / reversed: ______ Ω

### D. Investigate the last two wires

Test each unidentified connector contact against these chip pins, in this order:

1. pin **9** — RESET
2. pin **16** — PD2/INT0
3. pin **17** — PD3/INT1
4. pin **14** — PD0/RXD
5. pin **15** — PD1/TXD
6. pins **6, 7, 8** — MOSI, MISO, SCK, only to rule them out

The firmware does not show an active application UART, so continuity to pins 14/15 would be a physical fact but would not by itself prove a serial protocol. One or both unknown wires may instead connect through discrete components and have no near-zero path to any MCU leg.

## Results sheet

| Connector position | Observed wire colour | Ω to GND 11/31 | Ω to VCC 10/30 | Ω to SCL 22 | Ω to SDA 23 | Best other MCU pin/path | Provisional function | Confidence/notes |
|---:|---|---:|---:|---:|---:|---|---|---|
| J1-1 |  |  |  |  |  |  |  |  |
| J1-2 |  |  |  |  |  |  |  |  |
| J1-3 |  |  |  |  |  |  |  |  |
| J1-4 |  |  |  |  |  |  |  |  |
| J1-5 |  |  |  |  |  |  |  |  |
| J1-6 |  |  |  |  |  |  |  |  |

### Interpreting readings

These are guides, not automatic verdicts:

| Reading after subtracting lead resistance | Likely interpretation |
|---:|---|
| About 0–2 Ω | Direct copper trace/contact is likely |
| A few ohms to about 100 Ω | Could be a trace through a ferrite bead or series resistor; inspect the route |
| Hundreds of ohms or kilohms | Probably a component/pull-up/alternate circuit path, not direct continuity |
| `OL` / no stable reading | No conductive path at the meter's test voltage |

The lowest unique reading to the target pin matters more than whether the meter happens to beep. Continuity buzzers often accept tens of ohms.

## Powered confirmation — only after the unpowered map is complete

The safest check is to reconnect the panel to its original host and power it normally, if that equipment is available. Keep the Pico and level shifter disconnected.

1. Put the meter in **DC volts**, never continuity/ohms.
2. Put the black probe on the connector contact already proved as ground.
3. Measure MCU pin 10 relative to ground and MCU pin 30 relative to ground.
4. Measure every connector contact at idle and record it below.
5. SCL and SDA should normally idle high near their pull-up voltage. This confirms which voltage belongs on the translator's `HV` reference.
6. The fuse settings make approximately 5 V operation likely, but the meter measurement is the deciding evidence.

| Connector position | Idle DC voltage | Changes during start-up/button/remote activity? | Confirmed function/notes |
|---:|---:|---|---|
| J1-1 |  |  |  |
| J1-2 |  |  |  |
| J1-3 |  |  |  |
| J1-4 |  |  |  |
| J1-5 |  |  |  |
| J1-6 |  |  |  |

Do not inject voltage into an unknown connector contact. Do not infer 12 V from the rating printed on a capacitor.

## Level-shifter connection after voltage confirmation

The purchased four-channel bidirectional 3.3 V↔5 V MOSFET module is the correct **type** for I²C. Only two channels are needed.

| Pico | Level shifter | Front panel |
|---|---|---|
| `GP4`, physical pin 6 | low-side channel 1 (`LV1`) | matching high-side channel 1 (`HV1`) to proved **SDA**, MCU pin 23 |
| `GP5`, physical pin 7 | low-side channel 2 (`LV2`) | matching high-side channel 2 (`HV2`) to proved **SCL**, MCU pin 22 |
| `3V3(OUT)`, physical pin 36 | `LV` reference | no direct connection to the panel supply |
| Any Pico GND, e.g. physical pin 8 | both/common `GND` | proved panel GND |
| Proved panel logic rail | `HV` reference | panel supply side |

The module translates signal levels; it does not create either supply and does not power the front panel. Never connect panel 5 V to Pico `3V3(OUT)`. Leave the two unidentified connector wires individually insulated during the first I²C test.

## Evidence to send back for a definitive pinout

- The completed resistance table, including readings rather than only beep/no-beep.
- The completed powered-voltage table.
- A close, sharp photo of the connector from the numbered view.
- Close photos of both PCB faces around the connector and MCU.
- Which end of the ATmega package has the notch/dot.

With those measurements, each physical connector position can be promoted from candidate to confirmed.

## References

- [Microchip ATmega16(L) datasheet, PDIP pinout on page 2](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/doc2466.pdf#page=2)
- [Nexperia AN10441: bidirectional level shifting for I²C](https://assets.nexperia.com/documents/application-note/AN10441.pdf)
- Companion reference: `DRX280_FrontPanel_ATmega16L_Pico_Golden_Reference.md`
