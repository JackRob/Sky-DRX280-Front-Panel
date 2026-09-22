#!/usr/bin/env python3
"""Small interactive USB-serial console for the front-panel tester."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
import threading
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("pyserial is required. Install it with:  py -m pip install pyserial")
    raise SystemExit(2)


RASPBERRY_PI_USB_VID = 0x2E8A


def available_ports():
    return list(list_ports.comports())


def choose_port(requested: str | None) -> str:
    ports = available_ports()
    if requested:
        return requested

    likely = [
        port
        for port in ports
        if port.vid == RASPBERRY_PI_USB_VID
        or "pico" in (port.description or "").lower()
        or "raspberry pi" in (port.manufacturer or "").lower()
    ]
    if len(likely) == 1:
        return likely[0].device

    if ports:
        print("Serial ports found:")
        for port in ports:
            marker = "  likely Pico" if port in likely else ""
            print(f"  {port.device}: {port.description}{marker}")
    if len(likely) > 1:
        print("More than one possible Pico was found; pass --port COMx.")
    else:
        print("No Pico USB serial port was identified; pass --port COMx.")
    raise SystemExit(1)


def append_log(log_file, log_lock: threading.Lock, text: str) -> None:
    if log_file is None:
        return
    with log_lock:
        log_file.write(text)
        log_file.flush()


def reader(device, stopped: threading.Event, log_file, log_lock: threading.Lock) -> None:
    while not stopped.is_set():
        try:
            data = device.read(256)
        except serial.SerialException as exc:
            print(f"\nSerial connection ended: {exc}")
            stopped.set()
            return
        if data:
            decoded = data.decode("utf-8", errors="replace")
            sys.stdout.write(decoded)
            sys.stdout.flush()
            append_log(log_file, log_lock, decoded)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive console for the RP2040 front-panel tester"
    )
    parser.add_argument("--port", help="Windows port such as COM5")
    parser.add_argument(
        "--list", action="store_true", help="list serial ports and exit"
    )
    parser.add_argument(
        "--log",
        metavar="FILE",
        help="save Pico output and entered commands to a UTF-8 transcript",
    )
    args = parser.parse_args()

    if args.list:
        for port in available_ports():
            print(f"{port.device}\t{port.description}\tVID={port.vid} PID={port.pid}")
        return

    port = choose_port(args.port)
    log_file = None
    log_lock = threading.Lock()
    if args.log:
        try:
            log_path = Path(args.log).expanduser().resolve()
            log_file = log_path.open("a", encoding="utf-8", buffering=1)
        except OSError as exc:
            print(f"Could not open log file {args.log}: {exc}")
            raise SystemExit(1) from exc
        append_log(
            log_file,
            log_lock,
            f"\n=== DRX280 tester session {datetime.now().astimezone().isoformat()} "
            f"port={port} ===\n",
        )
    try:
        device = serial.Serial(port, 115200, timeout=0.1, write_timeout=1)
    except serial.SerialException as exc:
        print(f"Could not open {port}: {exc}")
        print("Close any other terminal using this COM port, then try again.")
        if log_file is not None:
            log_file.close()
        raise SystemExit(1) from exc

    print(f"Connected to {port}. Type help, info, or demo.")
    print("Use /quit to close this console. Button and IR events appear automatically.")
    if log_file is not None:
        print(f"Saving this session to {log_path}")
    stopped = threading.Event()
    thread = threading.Thread(
        target=reader,
        args=(device, stopped, log_file, log_lock),
        daemon=True,
    )
    thread.start()
    time.sleep(0.25)

    # The Pico normally finishes its 1.5-second startup before Windows opens the
    # COM port. Request a fresh, safe read-only status snapshot on every connect.
    try:
        append_log(log_file, log_lock, "> info  [automatic status request]\n")
        device.write(b"info\r")
        device.flush()
    except serial.SerialException as exc:
        print(f"Could not request initial status: {exc}")

    try:
        while not stopped.is_set():
            try:
                line = input("> ")
            except EOFError:
                break
            if line.strip().lower() in {"/quit", "/exit"}:
                break
            try:
                append_log(log_file, log_lock, f"> {line}\n")
                device.write((line + "\r").encode("ascii"))
                device.flush()
            except (UnicodeEncodeError, serial.SerialException) as exc:
                print(f"Could not send command: {exc}")
                if isinstance(exc, serial.SerialException):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        device.close()
        thread.join(timeout=0.5)
        append_log(log_file, log_lock, "\n=== session closed ===\n")
        if log_file is not None:
            log_file.close()
        print("Console closed.")


if __name__ == "__main__":
    main()
