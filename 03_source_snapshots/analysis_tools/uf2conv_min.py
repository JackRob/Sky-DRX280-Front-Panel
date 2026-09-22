#!/usr/bin/env python3
"""Convert a flat RP2040 flash binary into a UF2 drag-and-drop image.

This deliberately small converter emits 256-byte payload blocks for the
official RP2040 UF2 family.  It is used only as a build helper for the panel
tester; it does not communicate with a Pico.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
UF2_FLAG_FAMILY_ID_PRESENT = 0x00002000
RP2040_FAMILY_ID = 0xE48BFF56
FLASH_BASE = 0x10000000
PAYLOAD_SIZE = 256
UF2_DATA_CAPACITY = 476


def convert(binary: bytes) -> bytes:
    if not binary:
        raise ValueError("input binary is empty")

    block_count = (len(binary) + PAYLOAD_SIZE - 1) // PAYLOAD_SIZE
    output = bytearray()

    for block_number in range(block_count):
        offset = block_number * PAYLOAD_SIZE
        payload = binary[offset : offset + PAYLOAD_SIZE]
        payload = payload.ljust(PAYLOAD_SIZE, b"\x00")
        header = struct.pack(
            "<8I",
            UF2_MAGIC_START0,
            UF2_MAGIC_START1,
            UF2_FLAG_FAMILY_ID_PRESENT,
            FLASH_BASE + offset,
            PAYLOAD_SIZE,
            block_number,
            block_count,
            RP2040_FAMILY_ID,
        )
        output += header
        output += payload.ljust(UF2_DATA_CAPACITY, b"\x00")
        output += struct.pack("<I", UF2_MAGIC_END)

    return bytes(output)


def verify(uf2: bytes, expected_binary: bytes) -> None:
    if not uf2 or len(uf2) % 512:
        raise ValueError("UF2 length is not a nonzero multiple of 512")

    count = len(uf2) // 512
    reconstructed = bytearray()
    expected_address = FLASH_BASE

    for index in range(count):
        block = uf2[index * 512 : (index + 1) * 512]
        fields = struct.unpack_from("<8I", block)
        magic0, magic1, flags, address, size, number, total, family = fields
        end_magic = struct.unpack_from("<I", block, 508)[0]
        if (magic0, magic1, end_magic) != (
            UF2_MAGIC_START0,
            UF2_MAGIC_START1,
            UF2_MAGIC_END,
        ):
            raise ValueError(f"bad magic in UF2 block {index}")
        if not flags & UF2_FLAG_FAMILY_ID_PRESENT or family != RP2040_FAMILY_ID:
            raise ValueError(f"wrong UF2 family in block {index}")
        if number != index or total != count:
            raise ValueError(f"bad UF2 sequence at block {index}")
        if size != PAYLOAD_SIZE or address != expected_address:
            raise ValueError(f"bad UF2 address or payload size at block {index}")
        reconstructed += block[32 : 32 + size]
        expected_address += size

    if reconstructed[: len(expected_binary)] != expected_binary:
        raise ValueError("UF2 payload does not reproduce the input binary")
    if any(reconstructed[len(expected_binary) :]):
        raise ValueError("UF2 final-block padding is not zero")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    binary = args.input.read_bytes()
    uf2 = convert(binary)
    verify(uf2, binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(uf2)
    print(
        f"wrote {args.output} ({len(uf2)} bytes, "
        f"{len(uf2) // 512} blocks, RP2040 family)"
    )


if __name__ == "__main__":
    main()
