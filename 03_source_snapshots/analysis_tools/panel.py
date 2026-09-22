"""ATmega16L panel host driver for MicroPython on RP2040.

Static-analysis reference implementation; not yet tested on physical hardware.
This talks to the original application over I2C. It does not program the AVR.
"""
try:
    from time import sleep_ms
except ImportError:  # Allows host-side tests under ordinary CPython.
    from time import sleep

    def sleep_ms(milliseconds):
        sleep(milliseconds / 1000)


class Panel:
    ADDRESS = 0x40
    ID = b'\xc1\x11\x02'
    # Only configuration registers used by this reference driver are writable.
    WRITABLE = frozenset((0x0c, 0x0d, 0x0e, 0x0f, 0x10, 0x11,
                          0x14, 0x15, 0x18, 0x19, 0x20, 0x21,
                          0x22, 0x23, 0x24))

    def __init__(self, i2c):
        self.i2c = i2c
        self.identified = False
        self._ir_service_primed = False

    @staticmethod
    def _range(reg, length):
        if not isinstance(reg, int) or not isinstance(length, int):
            raise ValueError('integer register and length required')
        if length < 1 or reg < 0 or reg + length > 0x41:
            raise ValueError('register range must fit 0x00..0x40')

    def read(self, reg, length=1, allow_event_service=False):
        self._range(reg, length)
        if reg <= 0x31 < reg + length and not allow_event_service:
            raise ValueError('reading 0x31 has event-service side effects')
        # This AVR firmware requires STOP after the pointer byte.  Its TWI
        # state machine does not accept the usual repeated-START memory read.
        acked = self.i2c.writeto(self.ADDRESS, bytes((reg,)), True)
        if acked != 1:
            raise OSError('register pointer was not acknowledged')
        data = self.i2c.readfrom(self.ADDRESS, length, True)
        if len(data) != length:
            raise OSError('short panel read')
        return data

    def identify(self):
        self.identified = False
        ident = self.read(0x01, 3)
        if ident != self.ID:
            raise OSError('unexpected panel identity: ' + repr(ident))
        if not (self.read(0x06)[0] & 1):
            raise OSError('panel is not ready')
        self.identified = True
        return ident

    def write(self, reg, data):
        data = bytes(data)
        self._range(reg, len(data))
        if not self.identified:
            raise RuntimeError('call identify() successfully before configuration')
        if any(r not in self.WRITABLE for r in range(reg, reg + len(data))):
            raise ValueError('write outside the driver configuration allowlist')
        payload = bytes((reg,)) + data
        acked = self.i2c.writeto(self.ADDRESS, payload, True)
        if acked != len(payload):
            raise OSError('panel configuration was not fully acknowledged')

    def _write_mirrors(self, reg, data):
        """Narrow internal write for the experimental IR empty sentinel."""
        data = bytes(data)
        if reg != 0x2e or data != b'\x00\x00':
            raise ValueError('only zeroing the two IR mirrors is allowed')
        payload = bytes((reg,)) + data
        acked = self.i2c.writeto(self.ADDRESS, payload, True)
        if acked != len(payload):
            raise OSError('IR mirror clear was not fully acknowledged')

    def direct_button_mode(self, scan_multiplier=1):
        if not 1 <= scan_multiplier <= 15:
            raise ValueError('scan multiplier must be 1..15')
        # Keep bits 6..7; bits 4..5 = 0 selects direct sampled state.
        config = (self.read(0x24)[0] & 0xc0) | scan_multiplier
        self.write(0x24, (config,))
        # Nominal report interval is (multiplier + 1) * 10ms.
        sleep_ms((scan_multiplier + 2) * 12)

    def buttons(self):
        # Two matching reads reduce tearing; the firmware has no atomic snapshot.
        previous = self.read(0x26, 2)
        for _ in range(3):
            current = self.read(0x26, 2)
            if current == previous:
                return (current[0] | (current[1] << 8)) & 0x7fff
            previous = current
        raise OSError('button state changed throughout repeated reads')

    def steady_leds(self, mask, brightness=(1, 1, 1, 1, 1, 1)):
        if not 0 <= mask <= 0x3f:
            raise ValueError('LED mask must be 0..0x3f')
        if len(brightness) != 6 or any(not 0 <= b <= 7 for b in brightness):
            raise ValueError('six brightness values, each 0..7, required')
        self.write(0x10, (0, 0))  # Disable status channels and their blink mask.
        packed = tuple(brightness[i] | (brightness[i + 1] << 4)
                       for i in (0, 2, 4))
        self.write(0x20, packed + (1,))
        sleep_ms(20)
        self.write(0x10, (mask,))

    def blink_leds(self, enable_mask, blink_mask, period_ms=1000, duty=50):
        if not 0 <= enable_mask <= 0x3f or not 0 <= blink_mask <= 0x3f:
            raise ValueError('LED masks must be 0..0x3f')
        # Firmware stores phase durations as 8-bit counts of nominal 10ms.
        if not 1 <= period_ms <= 65535 or not 1 <= duty <= 99:
            raise ValueError('nonzero period; duty 1..99 required')
        on = period_ms * duty // 1000
        off = period_ms // 10 - on
        if not 1 <= on <= 255 or not 1 <= off <= 255:
            raise ValueError('each blink phase must fit 1..255 firmware frames')
        self.write(0x11, (0,))
        self.write(0x0d, (duty, period_ms & 255, period_ms >> 8))
        sleep_ms(20)
        self.write(0x10, (enable_mask, blink_mask & enable_mask))

    def ring_off(self):
        self.write(0x19, (self.read(0x19)[0] | 0x10,))

    def ring(self, intensity=1, speed=8, reverse=False,
             trail=4, style=1, phase=0):
        if not 0 <= intensity <= 7 or not 0 <= speed <= 127:
            raise ValueError('intensity 0..7 and speed 0..127 required')
        if not 1 <= trail <= 8 or style not in (0, 1) or not 0 <= phase <= 7:
            raise ValueError('trail 1..8, style 0/1, phase 0..7 required')
        self.ring_off()
        sleep_ms(20)
        self.write(0x14, (0x60 | intensity, ((trail - 1) << 4) | style))
        self.write(0x18, (speed | (0x80 if reverse else 0),))
        sleep_ms(20)
        self.write(0x19, ((0x08 | phase) if speed == 0 else 0,))

    def prime_ir_service_experimental(self):
        """Pass the firmware's five-load suppression counter after boot.

        Call before relying on IR.  If another host has already primed this
        counter, these reads can consume queued events, so use only on a Pico-
        controlled standalone panel during initialization.
        """
        if not self.identified:
            raise RuntimeError('identify the panel before priming IR service')
        for _ in range(5):
            self.read(0x31, 1, allow_event_service=True)
        self._ir_service_primed = True

    def poll_ir_experimental(self):
        """Return one decoded raw event dictionary or None if the queue is empty.

        This procedure follows the static firmware model but needs live-panel
        validation.  Every real packed event has marker bit 0 set.
        """
        if not self._ir_service_primed:
            raise RuntimeError('prime IR service once after panel initialization')
        self._write_mirrors(0x2e, b'\x00\x00')
        self.read(0x31, 1, allow_event_service=True)
        raw = self.read(0x2e, 2)
        word = raw[0] | (raw[1] << 8)
        if word == 0:
            return None
        if not (word & 1):
            raise OSError('malformed IR event without marker bit')
        return {'raw': word,
                'pressed': bool(word & 0x0002),
                'field_020d': (word >> 2) & 0x03,
                'field_020c': (word >> 4) & 0x03,
                'field_020a': (word >> 6) & 0x03,
                'field_020b': (word >> 8) & 0xff}

    def event_probe(self):
        # Diagnostic only: low IR pair is read before the 0x31 preload updates it.
        # The IR word can be stale, including its bit 0. Do not emit HID from it.
        data = self.read(0x2e, 4, allow_event_service=True)
        return {'ir_previous': data[0] | (data[1] << 8),
                'button_mirror': (data[2] | (data[3] << 8)) & 0x7fff}
