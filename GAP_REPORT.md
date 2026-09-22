# Documentation and evidence gap report

This report lists remaining panel-only gaps. It intentionally excludes host-computer integration and external power-control design.

## Covered

- ATmega16L device facts, fuse/lock interpretation and firmware provenance.
- Original flash and EEPROM dumps.
- I²C/TWI address, register framing and register-bank behavior.
- Status-channel colors, PWM behavior and ring-engine analysis.
- Button-matrix structure and measured public masks.
- Harness continuity findings for ground, logic supply, SDA, SCL and the external IR path.
- Pico software-I²C reference source and diagnostic UF2 images.
- High-resolution front/rear/component-side photographs.

## Still incomplete

### Physical six-pin connector order

The colour-to-signal findings are documented, but the physical position order at the mainboard header and a final pin-1 convention remain unsigned-off.

### Powered electrical measurements

The archive does not contain a final table of brown-rail voltage, SDA/SCL idle levels on both translator sides, red-line voltage, panel current draw or LED peak current.

### Ring orientation

The firmware logical positions are known, but the physical clockwise segment numbering needs a controlled one-position-at-a-time observation on the exact board revision.

### Reproduction validation

A dated panel-only test sheet covering cold start, bus identification, all status channels, ring positions, every button mask and recovery behavior would make the archive easier to reproduce.

### Revision comparison

Only one board revision has been measured in detail. A second board could differ in harness order, LED colors, resistor values or populated components.

## Reproduction disclaimer

The UF2 images, component references, pin assignments and voltage guidance are research artifacts from a particular board and test setup. Verify them against your own panel, Pico variant, level translator and power arrangement before use. Adapt the design for your own project.
