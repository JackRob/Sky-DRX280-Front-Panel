> **Replication note:** The wiring and supply examples below are reference measurements from one panel and test setup. Verify the rail, translator, connector orientation and Pico variant on your own hardware before applying power or flashing firmware. Adapt them for your own project.

# Working-box test for the six-wire DRX280 front-panel connector

This sheet uses the second, working receiver as the voltage reference. It separates **unpowered continuity tracing** from **powered voltage measurement** so the Pico and replacement PSU are not exposed to an unidentified wire.

## What the two photographs establish

- The panel cable has six occupied conductors, reported as purple, blue, green, orange, red and brown. Colour is only a convenient row label.
- The panel-side cable exits the white connector beside the ATmega16L.
- The mainboard has a six-pin unshrouded header marked **J807** near a circular mounting hole.
- J807 pin 1 is visibly identified by the printed `1` and the chamfered end of its silkscreen outline. In photograph 2 exactly as supplied, pin 1 is the far-right contact, nearest the mounting hole; left-to-right is therefore `J807-6, 5, 4, 3, 2, 1`. Confirm the printed mark on the real board before wiring.
- Because the mainboard header is unshrouded, photograph the connector **while still fitted correctly in the working box**. Mark which colour is nearest the mounting hole. Reversing or shifting the plug by one pin could damage the panel.

Firmware analysis already establishes that the normal control link is **I²C/TWI**, not SPI:

| Known logical connection | ATmega16L 40-pin PDIP leg |
|---|---:|
| VCC | 10 |
| GND | 11 |
| SCL | 22 |
| SDA | 23 |
| AVCC, should share the logic rail | 30 |
| Second GND | 31 |

## Corrected bench mapping, 2026-09-09

An initial 180-degree chip-counting error was found and corrected. Ground was then independently checked against an electrolytic capacitor's negative lead. These results assume the black six-way plug was disconnected from the Sky mainboard during resistance measurements.

| Wire | Corrected measurement | Function |
|---|---|---|
| Purple | Near zero to capacitor negative and MCU GND pins 11/31; near zero to blue | Ground |
| Blue | Near zero to capacitor negative and MCU GND pins 11/31; near zero to purple | Second ground conductor |
| Brown | Direct to MCU VCC pin 10 and AVCC pin 30; approximately 1 kΩ to ground on the 2 kΩ range and over-range on 200 Ω | Panel logic-supply rail; powered voltage not measured yet |
| Green | 110 Ω to PC0/SCL pin 22 on the 200 Ω range | I²C/TWI SCL through a 110 Ω series path |
| Orange | 110 Ω to PC1/SDA pin 23 on the 200 Ω range | I²C/TWI SDA through a 110 Ω series path |
| Red | Approximately 100 Ω bidirectionally to PD3/INT1 pin 17 on the 200 Ω range | Second IR-decoder/external interrupt input from the mainboard |

The matching 110 Ω readings establish deliberate series protection on both I²C lines. Firmware configures pin 17 as the second IR-decoder input; the local on-panel receiver uses pin 16, so red is very likely the mainboard/external remote-eye IR feed.

### Chip orientation on this PCB

In the supplied component-side photograph, the ATmega's pin-1 dimple is at the **lower-left** end. Therefore:

- lower row, left-to-right: pins **1 through 20**;
- upper row, left-to-right: pins **40 down through 21**;
- pin 22/SCL: **second upper leg from the right**;
- pin 23/SDA: **third upper leg from the right**;
- pin 17/INT1: **fourth lower leg from the right**;
- pin 16/INT0: **fifth lower leg from the right**.

Do not infer a junction from two traces appearing to meet. Measure between the actual chip legs.

### Remaining checks

1. Photograph the original plug installed on J807 and record which colour is nearest J807's printed pin 1/mounting-hole end.
2. In the powered working box, measure brown, green, orange and red relative to purple/blue in standby and while on.
3. Capture red during an external remote event if that function is to be reused.

## Equipment

- Multimeter with DC-voltage, resistance and continuity modes
- Six labelled insulated extension conductors
- One 1×6 male pin strip or a purpose-made 1×6 breakout
- Insulated mini-grabbers or back-probe needles
- Tape or heat-shrink to prevent adjacent conductors touching
- Camera/phone for orientation photographs

A logic analyser is useful later to verify red's external IR pulses, but it is not needed for the established cable mapping.

## Stage 1 — preserve the working connector orientation

1. Leave the working receiver unplugged from mains.
2. Before removing the front-panel plug, take close photographs showing:
   - the plug fitted to the mainboard header;
   - the mounting hole;
   - the red and violet wire ends;
   - any printed `1`, triangle or chamfer.
3. Mark the header contacts `J807-1` through `J807-6`, using the printed `1` and chamfer. Remember that the mating face of the loose female plug reverses the apparent left/right order.
4. Write which colour lands on each contact below.

| Mainboard contact | Cable colour | Position description |
|---:|---|---|
| J807-1 |  | nearest mounting hole/chamfer |
| J807-2 |  |  |
| J807-3 |  |  |
| J807-4 |  |  |
| J807-5 |  |  |
| J807-6 |  | farthest from mounting hole in photograph 2 |

## Stage 2 — map the cable using the loose panel, completely unpowered

Disconnect the panel from the receiver, Pico, programmer and every supply. Confirm 0 V before selecting resistance/continuity.

At the ATmega16L, viewed from above with the notch at the top, pin 1 is upper-left. Count down the left side to pin 20, then up the right side from pin 21 to pin 40.

1. Touch the meter probes together and record lead resistance: ______ Ω.
2. For every cable colour, measure resistance to ATmega pins **11 and 31**. The colour reading near lead resistance to both is GND.
3. Measure the others to pins **10 and 30**. The colour reaching both is the logic-supply candidate. It may include a small resistance through a bead or resistor.
4. Measure the remaining colours to pin **22**. The uniquely low/direct path is SCL.
5. Measure the remaining colours to pin **23**. The uniquely low/direct path is SDA.
6. Check the final non-bus conductor against pins **9, 16, 17, 14 and 15**, in that order. Also check pins 6–8 only to rule out the ISP/SPI programming lines.
7. Reverse the probes on uncertain measurements. A reading that changes strongly with polarity probably passes through a semiconductor and is not plain wire continuity.

| Cable colour | Ω to GND 11/31 | Ω to VCC 10/30 | Ω to SCL 22 | Ω to SDA 23 | Best other destination | Established function |
|---|---:|---:|---:|---:|---|---|
| Purple | near zero |  |  |  | capacitor negative | Ground |
| Blue | near zero |  |  |  | capacitor negative; common with purple | Ground |
| Green |  |  | 110 Ω |  | pin 22 | SCL |
| Orange |  |  |  | 110 Ω | pin 23 | SDA |
| Red |  |  |  |  | about 100 Ω to pin 17 | External/mainboard IR input |
| Brown | about 1 kΩ | direct |  |  | pins 10/30 | MCU supply rail; live voltage pending |

Guidance after subtracting probe-lead resistance:

- roughly 0–2 Ω: likely direct trace;
- a few ohms to about 100 Ω: possible series resistor or ferrite bead;
- hundreds of ohms/kilohms: a component or pull-up path, not direct continuity;
- `OL`: no measurable path.

## Stage 3 — make a protected six-wire breakout

Do not try to hold pointed meter probes on adjacent live header pins.

Build a one-to-one extension:

```text
working mainboard header ── six separately labelled wires ── 1×6 male header ── original panel plug
                                      │
                                insulated test points
```

Check every extension conductor end-to-end with continuity. Check that no conductor has continuity to either neighbour. Keep the original colour/contact order exactly as photographed.

The safest arrangement routes the low-voltage breakout outside the receiver so its lid or PSU shield can be replaced before mains is applied. An open receiver can expose hazardous mains voltage even though this six-pin connector is low voltage.

## Stage 4 — powered measurements from the working receiver

1. Receiver unplugged: assemble the breakout and connect the panel.
2. Clip the meter's black lead to the wire already proved as GND.
3. Insulate that connection and ensure every test point is separated.
4. Select **DC volts**. Do not use resistance, continuity or current mode.
5. Apply mains with the receiver closed/shielded as far as the breakout permits.
6. Record every line in standby.
7. Turn the receiver on and record every line again.
8. Measure voltage directly at ATmega pin 10 relative to pin 11, and pin 30 relative to pin 31, only if these points can be reached without exposing or approaching mains circuitry. Otherwise the continuity-proved supply cable measurement is sufficient.
9. Check SDA and SCL at idle. Both should normally sit high near their bus pull-up voltage. A multimeter may show an averaged lower value while traffic is active.
10. Power down and unplug before changing any connections.

| Colour / mainboard contact | Standby voltage | Receiver-on voltage | Start-up/button/remote change | Function after continuity test |
|---|---:|---:|---|---|
| Purple / J807-___ |  |  |  |  |
| Blue / J807-___ |  |  |  |  |
| Green / J807-___ |  |  |  |  |
| Orange / J807-___ |  |  |  |  |
| Red / J807-___ |  |  |  |  |
| Brown / J807-___ |  |  |  |  |

Expected evidence:

- GND remains approximately 0 V.
- The logic-supply wire should match the voltage measured across MCU VCC/GND.
- SDA and SCL should idle near their pull-up rail and may average lower during activity.
- A line that measures 12 V must never connect to the Pico or the 3.3↔5 V level shifter.
- Red should normally be pulled high and may show only an averaged change during fast remote pulses.

## Stage 5 — verify the external IR conductor

Compare red's standby and receiver-on readings, then observe it while sending a remote command through the mainboard's external remote path. A basic multimeter can reveal its idle voltage or a slow averaged change but cannot reliably display fast pulses.

For waveform confirmation, capture red with a logic analyser of verified input-voltage tolerance. Use the proved ground as reference. Do not connect an analyser, Pico or level shifter to red until its maximum voltage is known. Green/orange I²C traffic to target address `0x40` independently confirms the bus pair.

## Stop point before connecting the replacement PSU or Pico

Do not proceed until all of these are true:

- [ ] GND colour/contact is proved by continuity to MCU pins 11 and 31.
- [ ] Panel supply colour/contact is proved by continuity to pins 10/30 or its input-power network.
- [ ] Its actual voltage is measured in the working box.
- [ ] SDA is proved to MCU pin 23 and its idle-high voltage is measured.
- [ ] SCL is proved to MCU pin 22 and its idle-high voltage is measured.
- [ ] Red's powered voltage is measured; leave it insulated if external IR is not yet being used.
- [ ] The original plug orientation is recorded.

## Replacement PSU and Pico wiring after confirmation

The panel should receive only the rail proved by measurement. Do not supply both 5 V and 12 V merely because both exist on an ATX/Flex-ATX PSU. The ATmega16L itself cannot accept 12 V at VCC.

For the first independent test, a current-limited bench supply is preferable to an ATX PSU, which can deliver enough current to destroy a mistaken trace. Measure the panel's normal current in the working receiver or begin with a conservative current limit, then choose an inline fuse/PTC appropriate to the measured current before using the ATX rail.

If the Pico must remain awake while the PC is shut down so it can recognise the front-panel power button, the final design will probably use the PSU's **+5VSB standby rail**, subject to its current rating and the measurements above. The ordinary +5 V main rail switches off when `PS_ON#` is inactive; +5VSB remains present while AC is available. Do not make this connection until the panel voltage and total standby current have been measured.

If you measure panel current, open only the proved supply wire in the external breakout and insert the meter **in series**, beginning on its highest fused current range. Never place a current-mode meter across supply and ground, and return its red lead to the V/Ω socket immediately afterward.

| Connection | Destination |
|---|---|
| Proved panel supply | Matching measured PSU rail only |
| Proved panel ground | PSU ground and Pico/translator common ground |
| Proved panel SDA | Level shifter `HV1`; corresponding `LV1` to Pico GP4 |
| Proved panel SCL | Level shifter `HV2`; corresponding `LV2` to Pico GP5 |
| Panel I²C pull-up voltage | Level shifter `HV` reference |
| Pico `3V3(OUT)` | Level shifter `LV` reference |
| Unknown conductors | Individually insulated until identified |

Power the Pico from USB during the initial test. The level shifter does not power the Pico or panel. Never feed 5 V or 12 V into Pico `3V3(OUT)`.

Dupont-style leads are suitable for supervised bench tests. For permanent installation, use a single polarised/keyed six-way housing, strain relief and labelled wires. Loose individual Dupont sockets can be reversed, shifted by one pin or pulled off.

Take PSU power from a documented standard output connector or verified harness. Modular PSU-side socket pinouts are not universal even when the detachable cable colours look familiar.

## Return these results

Send back:

1. the photograph of the plug fitted to the working mainboard;
2. the completed continuity table;
3. standby and receiver-on voltages for all six colours;
4. any change seen when pressing standby or using the remote.

Those readings will allow a final physical pinout and exact PSU/level-shifter/Pico wiring table to be written without relying on colour assumptions.
