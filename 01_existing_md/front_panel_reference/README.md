> **Replication note:** The wiring and supply examples below are reference measurements from one panel and test setup. Verify the rail, translator, connector orientation and Pico variant on your own hardware before applying power or flashing firmware. Adapt them for your own project.

# DR-X280 front-panel Pico tester v1.0.0

This package contains a ready-to-flash firmware image for an **original
Raspberry Pi Pico or Pico H using the RP2040**. It is not the correct build for
a Pico 2. If your board is a Pico W, ask for the Pico W build before flashing.

The firmware is compiled and its UF2 image has been independently decoded and
checked against the linked binary. The recovered panel protocol is backed by
the supplied AVR dump and a transaction-level model. Physical operation on
your panel is still awaiting this first live test.

## Wiring used by this firmware

```text
REGULATED +5 V FROM PSU
        │
        ├──────────── Panel BROWN (panel power)
        │
        └──────────── Level shifter HV (5 V reference)

Pico pin 36, 3V3(OUT) ───────── Level shifter LV (3.3 V reference)

Panel ORANGE, SDA ─── HV1  ⇄  LV1 ─── Pico GP4, physical pin 6
Panel GREEN,  SCL ─── HV2  ⇄  LV2 ─── Pico GP5, physical pin 7

PSU GND / 0 V ───────┬──────── Panel PURPLE
                     ├──────── Panel BLUE
                     ├──────── Level shifter GND pad(s)
                     └──────── Pico GND, physical pin 8

Panel RED, external IR ─────── insulated and disconnected for now
```

The PSU +5 V and Pico USB +5 V must not be joined. Their **grounds must be
joined** as shown. The level shifter's `HV` and `LV` pins are voltage references;
the panel is powered directly from the PSU branch to brown.

**Do not match the panel wires to PSU wires by colour.** The panel's purple wire
is ground, while purple on a standard ATX harness means **+5 V standby**. Use a
documented PSU output harness and verify it with a meter. Never take power from
an undocumented socket on the modular PSU itself; modular PSU pinouts vary.

For the first energisation, a current-limited 5 V bench supply is ideal. Start
near 250 mA and increase only if the limit trips with the wiring rechecked. If
using an ATX rail, put a small 0.5 A inline fuse in the panel's brown +5 V branch.
This limits the fault current available to the Dupont leads and panel traces.

### Verify the supply before connecting the panel

1. Disconnect the panel and Pico, and set the multimeter to **20 V DC**.
2. Turn on the intended PSU output and measure between its chosen +5 V and
   ground contacts. It should read approximately +5 V with the red probe on
   +5 V and black probe on ground.
3. Turn the supply off, wait for the reading to fall, and connect the panel.

Never use resistance or continuity mode on a powered circuit. Continuity mode
is only for checks made with every source of power disconnected.

## First flash and power sequence

A basic BSS138 level-shifter board is not guaranteed to isolate an unpowered
side. For this initial setup, use this order:

1. Disconnect Pico USB and turn the panel's 5 V supply off.
2. Recheck that brown is on regulated **+5 V**, not +12 V, and that every ground
   in the diagram is common.
3. Turn on the panel's +5 V supply first. The shifter `HV` reference must now
   also have +5 V.
4. Hold the Pico's **BOOTSEL** button and connect its USB cable while continuing
   to hold the button.
5. Release BOOTSEL when Windows shows a drive named `RPI-RP2`.
6. Copy `DRX280_Pico_RP2040_Tester_v1.0.0.uf2` onto that drive. It will disappear
   automatically when the Pico reboots.
7. At shutdown, unplug Pico USB first and then turn off the panel's 5 V supply.

Do not disconnect or rearrange signal wires while either side is powered.

Watch the front panel **before** copying the UF2 so you do not miss the short
test. After the `RPI-RP2` drive disappears, the Pico waits 1.5 seconds and then
the panel sequence takes about two seconds.

## What should happen automatically

The firmware waits 1.5 seconds, checks that SDA and SCL are high, and reads the
panel at I2C address `0x40`. It requires identity `C1 11 02` and ready bit 0
before it writes any configuration.

After a valid response it runs one brightness-2-of-7 test:

1. Six logical status channels illuminate one at a time.
2. Eight logical ring positions illuminate one at a time.
3. Every output turns off.
4. Button monitoring starts.

The Pico's own green LED stays off during the 1.5-second startup and the panel
self-test. It becomes solid afterward when the panel is identified. It blinks
when the panel is offline, and briefly dips off during reported activity.

The self-test is intentionally dim and finite. The physical names of the six
status channels and the ring's position order have not yet been measured, so
write down what you see for logical channels `0–5` and ring positions `0–7`.
An entirely dark front panel after the sequence is the successful resting
state; the outputs are deliberately turned off.

If the first check fails but one of the three automatic retries later succeeds,
the Pico LED can become solid without repeating the visual sequence. Open the
console and enter `demo` in that case.

## Open the Windows test console

Install the small serial dependency once:

```powershell
py -m pip install pyserial
```

Wait several seconds after `RPI-RP2` disappears for Windows to create the new
COM port. The BOOTSEL drive and running firmware's COM port are separate USB
device modes. Open PowerShell in this package folder and run:

```powershell
py serial_console.py --log frontpanel-test.txt
```

The helper normally finds the Pico automatically. If it finds more than one
serial device, use:

```powershell
py serial_console.py --list
py serial_console.py --port COM5 --log frontpanel-test.txt
```

Replace `COM5` with the port shown on your computer. Enter `help` after it
connects. The helper automatically requests a fresh `info` report, since the
startup text often finishes before Windows opens the port. Enter `/quit` to
close it. Only one program can have the COM port open at a time.

If the `py` command is unavailable, open **Device Manager → Ports**, find `USB
Serial Device (COMx)`, and connect with PuTTY or Tera Term at 115200 baud. Close
that terminal before running the Python helper.

## Recommended first test

Run these in order:

```text
info
buttons once
ledtest 2 700
ringtest 2 500
demo
off
stats
```

Then press and release every front-panel button once. The console reports the
raw 15-bit mask and a provisional printed name. Save the complete output so the
mapping can be corrected from real observations.

Press one button at a time, hold it briefly, and wait for its release line
before pressing another. With no button held, `buttons once` should say:

```text
BUTTON one-shot state=0x0000 [none]
```

A normal press and release looks like this example:

```text
BUTTON state=0x0001 pressed=0x0001 [0:Standby/power]
BUTTON state=0x0000 released=0x0001 [0:Standby/power]
```

Record results in `MAPPING_WORKSHEET.md`. For exact visual mapping, use one
individual command at a time, such as `led 0 2`, record the lamp, then enter
`off`; repeat with channels `1–5`. Do the same with `ring 0 2` through
`ring 7 2`. The automatic sweep is useful as a quick check but is too fast for
careful annotation.

`demo` tests all six status channels, blinking, all eight stationary ring
positions, and the moving ring in both directions. It always requests all
outputs off at the end.

## Command reference

Numbers accept decimal or `0x`-prefixed hexadecimal notation.

```text
help
info
off
led <0-5|all> <brightness 0-6>
ledtest [brightness 1-6] [step-ms 50-5000]
blink <mask 1..0x3f> <brightness 1-6> <period-ms> <duty 1-99>
ring <position 0-7> [intensity 1-7]
ringtest [intensity 1-7] [step-ms 50-5000]
spin <speed 1-127> [intensity 1-7] [trail 1-8] [reverse 0|1]
demo
buttons [on|off|once]
ir [on|off|once]
read <register 0x00-0x40> [count 1-16]
recover
stats
```

Examples:

```text
led 2 2
led all 1
blink 0x04 2 1000 50
ring 3 2
spin 10 4 4 0
off
```

Status brightness is capped at 6 to avoid the panel firmware's exceptional
channel-5 behaviour at level 7. There is no arbitrary register-write command.
The protected bootloader-key register `0x28` cannot be written, and ordinary
reads through side-effecting register `0x31` are blocked.

## Buttons

Button reporting is enabled after a successful boot. The firmware reads the
panel every 20 ms, requires coherent samples, and applies 30 ms of stability
before reporting a change.

| Bit | Mask | Provisional label |
|---:|---:|---|
| 0 | `0x0001` | Standby/power |
| 1 | `0x0002` | Record |
| 2 | `0x0004` | Play |
| 3 | `0x0008` | Info |
| 4 | `0x0010` | Rewind |
| 5 | `0x0020` | Select |
| 6 | `0x0040` | Left |
| 7 | `0x0080` | Up |
| 8 | `0x0100` | Fast-forward |
| 9 | `0x0200` | Stop |
| 10 | `0x0400` | TV Guide |
| 11 | `0x0800` | Pause |
| 12 | `0x1000` | Back Up |
| 13 | `0x2000` | Right |
| 14 | `0x4000` | Down |

Trust the raw bit and mask if a printed name differs from the physical button.

## Experimental infrared test

The on-panel IR receiver should work with the red cable disconnected. Start raw
capture explicitly:

```text
ir on
```

Point the original remote at the panel and press one key at a time. The console
prints the complete raw word and four unnamed fields. This path follows the
static firmware model but has not yet been validated on hardware, so it does
not generate keyboard input or assign remote key names. Finish with:

```text
ir off
```

## If the Pico LED blinks and the panel does nothing

Open the console and enter `recover`. If recovery fails, power everything down
and check:

- panel brown to panel ground is approximately +5 V;
- shifter `HV` to ground is approximately +5 V;
- shifter `LV` to ground is approximately +3.3 V while Pico USB is connected;
- Pico-side SDA and SCL idle near +3.3 V;
- panel-side orange/SDA and green/SCL idle near +5 V;
- orange uses one matching `HVx/LVx` channel and green uses another;
- both level-shifter ground pads, Pico ground, PSU ground, purple and blue are
  the same common ground.

Power down before correcting a wire. If SCL remains low, software bus recovery
cannot fix a power, ground, or wiring fault.

## Scope of this tester

This release exercises and reports the original front-panel controller. It does
not yet present the buttons as a USB keyboard and does not control a computer's
power-switch header. Those behaviours can be added after the live LED, ring,
button, and IR mappings are recorded.
