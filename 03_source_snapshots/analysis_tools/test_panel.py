import sys
import unittest

sys.path.insert(0, "work")
from panel import Panel


class FakeI2C:
    def __init__(self):
        self.mem = bytearray(0x41)
        self.mem[1:4] = b"\xc1\x11\x02"
        self.mem[6] = 1
        self.mem[0x24] = 0x21
        self.pointer = 0x41
        self.calls = []
        self.reg31_loads = 0
        self.ir_queue = []

    def writeto(self, address, payload, stop=True):
        payload = bytes(payload)
        self.calls.append(("w", address, payload, stop))
        if address != 0x40 or not payload:
            return 0
        self.pointer = payload[0] if payload[0] <= 0x40 else 0x41
        for value in payload[1:]:
            if self.pointer <= 0x40:
                self.mem[self.pointer] = value
                self.pointer += 1
        return len(payload)

    def readfrom(self, address, length, stop=True):
        self.calls.append(("r", address, length, stop))
        result = bytearray()
        for _ in range(length):
            index = self.pointer
            result.append(self.mem[index] if index <= 0x40 else self.mem[0])
            if index == 0x31:
                self.reg31_loads += 1
                if self.reg31_loads > 5 and self.ir_queue:
                    word = self.ir_queue.pop(0)
                    self.mem[0x2e] = word & 255
                    self.mem[0x2f] = word >> 8
            if self.pointer <= 0x40:
                self.pointer += 1
        return bytes(result)


class PanelTests(unittest.TestCase):
    def ready(self):
        bus = FakeI2C()
        panel = Panel(bus)
        self.assertEqual(panel.identify(), b"\xc1\x11\x02")
        return bus, panel

    def test_read_uses_stop_separated_transactions(self):
        bus, panel = self.ready()
        bus.calls.clear()
        self.assertEqual(panel.read(1, 3), b"\xc1\x11\x02")
        self.assertEqual(bus.calls, [("w", 0x40, b"\x01", True),
                                     ("r", 0x40, 3, True)])

    def test_allowlist_blocks_boot_and_crossing_writes(self):
        _bus, panel = self.ready()
        for reg, payload in ((0x28, b"\x14"), (0x24, b"\x01\x01"),
                             (0x0b, b"\x00\x00")):
            with self.assertRaises(ValueError):
                panel.write(reg, payload)

    def test_direct_button_mode_and_coherent_read(self):
        bus, panel = self.ready()
        panel.direct_button_mode(1)
        self.assertEqual(bus.mem[0x24], 0x01)
        bus.mem[0x26] = 0x34
        bus.mem[0x27] = 0x12
        self.assertEqual(panel.buttons(), 0x1234)

    def test_indicator_and_ring_helpers(self):
        bus, panel = self.ready()
        panel.steady_leds(0x21, (1, 2, 3, 4, 5, 6))
        self.assertEqual(bus.mem[0x10], 0x21)
        self.assertEqual(bus.mem[0x11], 0)
        self.assertEqual(bus.mem[0x20:0x24], bytes((0x21, 0x43, 0x65, 1)))
        panel.ring(intensity=4, speed=10, reverse=True, trail=4, style=1)
        self.assertEqual(bus.mem[0x14], 0x64)
        self.assertEqual(bus.mem[0x15], 0x31)
        self.assertEqual(bus.mem[0x18], 0x8a)
        self.assertEqual(bus.mem[0x19], 0)

    def test_blink_rejects_firmware_low_byte_truncation(self):
        _bus, panel = self.ready()
        panel.blink_leds(1, 1, 1000, 50)
        with self.assertRaises(ValueError):
            panel.blink_leds(1, 1, 10000, 50)

    def test_experimental_ir_empty_sentinel(self):
        bus, panel = self.ready()
        panel.prime_ir_service_experimental()
        self.assertEqual(panel.poll_ir_experimental(), None)
        bus.ir_queue.append(0xA5D3)
        event = panel.poll_ir_experimental()
        self.assertEqual(event["raw"], 0xA5D3)
        self.assertTrue(event["pressed"])
        self.assertEqual(event["field_020b"], 0xA5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
