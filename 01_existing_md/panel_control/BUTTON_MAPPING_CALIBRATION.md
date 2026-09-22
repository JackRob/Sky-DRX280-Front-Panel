# Button mapping calibration

A button-reporting diagnostic build can report the panel's public button mask
over its USB CDC serial port. The masks below were captured from the current
board. The original capture build is not included in this public panel-only
archive; use a compatible build from your own project or rebuild the reference
source under `03_source_snapshots/status_mapping_sw`.

1. Flash a compatible button-reporting diagnostic build for your Pico variant.
2. Open the Pico's USB serial port at any baud rate.
3. Start with no button pressed and wait for a `STATUS` line.
4. Press and release exactly one physical key. Record the `BUTTON` line, for
   example `pressed=0x0400`.
5. Repeat for each control, including the four D-pad directions, Select,
   Back Up, Info, TV Guide, Record, transport keys, and PWR.

Use this table when sending the results back:

| Physical legend | Pressed mask |
|---|---|
| PWR/standby | `0x0080` |
| Record | `0x0040` |
| Play | `0x0020` |
| Info (i) | `0x0010` |
| Rewind | `0x0008` |
| Select/centre | `0x0004` |
| D-pad left | `0x0002` |
| D-pad up | `0x0001` |
| Fast-forward | `0x0800` |
| Stop | `0x2000` |
| TV guide | `0x1000` |
| Pause | `0x4000` |
| Back up | `0x0400` |
| D-pad right | `0x0200` |
| D-pad down | `0x0100` |

Do not press two keys together during calibration. These masks can be used to
construct a HID map or any other host-side control scheme. Verify the raw
values again if the panel revision or firmware changes.
