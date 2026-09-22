# Sky front-panel archive index

This public repository is limited to the front-panel hardware, its original firmware, the panel protocol, measurements, diagnostic firmware and Pico-side reference code. Host-computer integration, enclosure conversions and external power-control circuits are intentionally outside the scope of this repository.

## Folders

- `01_existing_md/front_panel_reference` — chip, protocol, register, LED, button and electrical reference material.
- `01_existing_md/electrical_and_pinout` — six-wire continuity and signal-identification records.
- `01_existing_md/panel_control` — generic button calibration and status-channel test notes.
- `02_firmware_artifacts` — original panel dumps and diagnostic/reference UF2 images.
- `03_source_snapshots` — analysis tools and the software-I²C status-mapping source.
- `04_evidence` — original high-resolution board photographs.
- `MANIFEST_SHA256.md` — archive integrity manifest.

## Reference wiring recorded from the tested panel

- Green harness wire reaches the MCU SCL net and is assigned to Pico GP16 in the reference software.
- Orange harness wire reaches the MCU SDA net and is assigned to Pico GP17 in the reference software.
- Purple and blue are ground.
- Brown is the panel logic-supply rail; its powered value must be measured on the board being reproduced.
- Red reaches the external IR path and should remain isolated until independently identified.

These are signal findings from one documented board revision. They do not establish a universal connector-position order or a universal supply voltage.
