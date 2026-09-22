#include "panel.h"

#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include "hardware/gpio.h"
#include "pico/error.h"
#include "pico/stdlib.h"

#define PANEL_ADDRESS             0x40u
#define PANEL_TIMEOUT_US          20000u
#define SOFT_I2C_HALF_PERIOD_US   3u
#define PANEL_STOP_SETTLE_US      2000u
#define PANEL_TRANSACTION_GAP_US  1000u
#define PANEL_LAST_REGISTER       0x40u
#define LINE_RELEASE_TIMEOUT_US   2000u

static bool soft_i2c_timed_out;
static uint64_t soft_i2c_deadline_us;

_Static_assert(PANEL_SCL_GPIO == 16u,
               "Green panel clock wire must remain on GP16");
_Static_assert(PANEL_SDA_GPIO == 17u,
               "Orange panel data wire must remain on GP17");
_Static_assert(PANEL_SDA_GPIO != 9u && PANEL_SCL_GPIO != 9u,
               "GP9 is physically shorted to ground and is forbidden");

static bool valid_range(uint8_t reg, size_t length) {
    return length > 0u && length <= 8u && reg <= PANEL_LAST_REGISTER &&
           length <= (size_t)(PANEL_LAST_REGISTER + 1u - reg);
}

static bool writable_register(uint8_t reg) {
    return (reg >= 0x0cu && reg <= 0x11u) ||
           reg == 0x14u || reg == 0x15u ||
           reg == 0x18u || reg == 0x19u ||
           (reg >= 0x20u && reg <= 0x24u);
}

/* Open-drain signalling: drive low for zero and switch to input for high. */
static void release_line(uint pin) {
    gpio_set_dir(pin, GPIO_IN);
}

static void drive_line_low(uint pin) {
    gpio_put(pin, false);
    gpio_set_dir(pin, GPIO_OUT);
}

static void prepare_bus_pins(void) {
    gpio_init(PANEL_SDA_GPIO);
    gpio_init(PANEL_SCL_GPIO);
    gpio_put(PANEL_SDA_GPIO, false);
    gpio_put(PANEL_SCL_GPIO, false);
    gpio_disable_pulls(PANEL_SDA_GPIO);
    gpio_disable_pulls(PANEL_SCL_GPIO);
    release_line(PANEL_SDA_GPIO);
    release_line(PANEL_SCL_GPIO);
}

static bool wait_line_high(uint pin, uint32_t timeout_us) {
    while (timeout_us > 0u) {
        if (gpio_get(pin)) {
            return true;
        }
        busy_wait_us_32(10u);
        timeout_us = timeout_us > 10u ? timeout_us - 10u : 0u;
    }
    return gpio_get(pin);
}

static bool soft_i2c_wait_line_high(uint pin) {
    while (!gpio_get(pin)) {
        if ((int64_t)(soft_i2c_deadline_us - time_us_64()) <= 0) {
            soft_i2c_timed_out = true;
            return false;
        }
        tight_loop_contents();
    }
    return true;
}

static bool soft_i2c_clock_high(void) {
    release_line(PANEL_SCL_GPIO);
    if (!soft_i2c_wait_line_high(PANEL_SCL_GPIO)) {
        return false;
    }
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    return true;
}

static bool soft_i2c_start(void) {
    release_line(PANEL_SDA_GPIO);
    release_line(PANEL_SCL_GPIO);
    if (!soft_i2c_wait_line_high(PANEL_SCL_GPIO) ||
        !soft_i2c_wait_line_high(PANEL_SDA_GPIO)) {
        return false;
    }
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    drive_line_low(PANEL_SDA_GPIO);
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    drive_line_low(PANEL_SCL_GPIO);
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    return true;
}

static bool soft_i2c_stop(void) {
    drive_line_low(PANEL_SDA_GPIO);
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    bool clock_ok = soft_i2c_clock_high();
    release_line(PANEL_SDA_GPIO);
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    if (!clock_ok || !gpio_get(PANEL_SDA_GPIO)) {
        soft_i2c_timed_out = true;
        return false;
    }
    return true;
}

static bool soft_i2c_write_bit(bool high) {
    if (high) {
        release_line(PANEL_SDA_GPIO);
    } else {
        drive_line_low(PANEL_SDA_GPIO);
    }
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    if (!soft_i2c_clock_high()) {
        return false;
    }
    bool line_ok = !high || gpio_get(PANEL_SDA_GPIO);
    drive_line_low(PANEL_SCL_GPIO);
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    return line_ok;
}

static bool soft_i2c_read_bit(bool *high) {
    release_line(PANEL_SDA_GPIO);
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    if (!soft_i2c_clock_high()) {
        return false;
    }
    *high = gpio_get(PANEL_SDA_GPIO);
    drive_line_low(PANEL_SCL_GPIO);
    busy_wait_us_32(SOFT_I2C_HALF_PERIOD_US);
    return true;
}

static bool soft_i2c_write_byte(uint8_t value) {
    for (unsigned bit = 0u; bit < 8u; ++bit) {
        if (!soft_i2c_write_bit((value & 0x80u) != 0u)) {
            return false;
        }
        value <<= 1;
    }
    bool nack = true;
    return soft_i2c_read_bit(&nack) && !nack;
}

static bool soft_i2c_read_byte(uint8_t *value) {
    uint8_t result = 0u;
    for (unsigned bit = 0u; bit < 8u; ++bit) {
        bool high;
        if (!soft_i2c_read_bit(&high)) {
            return false;
        }
        result = (uint8_t)((result << 1) | (high ? 1u : 0u));
    }
    *value = result;
    return true;
}

static int soft_i2c_error(void) {
    return soft_i2c_timed_out ? PICO_ERROR_TIMEOUT : PICO_ERROR_GENERIC;
}

static int soft_i2c_write(uint8_t address, const uint8_t *source,
                          size_t length) {
    soft_i2c_timed_out = false;
    soft_i2c_deadline_us = time_us_64() + PANEL_TIMEOUT_US;
    bool ok = source != NULL && length != 0u && soft_i2c_start() &&
              soft_i2c_write_byte((uint8_t)(address << 1));
    for (size_t index = 0u; ok && index < length; ++index) {
        ok = soft_i2c_write_byte(source[index]);
    }
    bool stopped = soft_i2c_stop();
    release_line(PANEL_SDA_GPIO);
    release_line(PANEL_SCL_GPIO);
    return ok && stopped ? (int)length : soft_i2c_error();
}

static int soft_i2c_read(uint8_t address, uint8_t *destination,
                         size_t length) {
    soft_i2c_timed_out = false;
    soft_i2c_deadline_us = time_us_64() + PANEL_TIMEOUT_US;
    bool ok = destination != NULL && length != 0u && soft_i2c_start() &&
              soft_i2c_write_byte((uint8_t)((address << 1) | 1u));
    for (size_t index = 0u; ok && index < length; ++index) {
        ok = soft_i2c_read_byte(&destination[index]);
        if (ok) {
            /* ACK intermediate bytes and NACK the final byte. */
            ok = soft_i2c_write_bit(index + 1u == length);
        }
    }
    bool stopped = soft_i2c_stop();
    release_line(PANEL_SDA_GPIO);
    release_line(PANEL_SCL_GPIO);
    return ok && stopped ? (int)length : soft_i2c_error();
}

static bool panel_read(uint8_t reg, uint8_t *destination, size_t length) {
    if (destination == NULL || !valid_range(reg, length)) {
        return false;
    }

    /*
     * The panel AVR requires a STOP after the register-pointer byte. It does
     * not accept the usual repeated-START memory-read transaction.
     */
    int result = soft_i2c_write(PANEL_ADDRESS, &reg, 1u);
    busy_wait_us_32(PANEL_TRANSACTION_GAP_US);
    if (result != 1) {
        return false;
    }

    sleep_us(PANEL_STOP_SETTLE_US);

    result = soft_i2c_read(PANEL_ADDRESS, destination, length);
    busy_wait_us_32(PANEL_TRANSACTION_GAP_US);
    return result == (int)length;
}

static bool panel_write(uint8_t reg, const uint8_t *source, size_t length) {
    if (source == NULL || !valid_range(reg, length)) {
        return false;
    }
    for (size_t index = 0u; index < length; ++index) {
        if (!writable_register((uint8_t)(reg + index))) {
            return false;
        }
    }

    uint8_t frame[9];
    frame[0] = reg;
    memcpy(&frame[1], source, length);
    int result = soft_i2c_write(PANEL_ADDRESS, frame, length + 1u);
    busy_wait_us_32(PANEL_TRANSACTION_GAP_US);
    return result == (int)(length + 1u);
}

static bool panel_write_u8(uint8_t reg, uint8_t value) {
    return panel_write(reg, &value, 1u);
}

void panel_bus_init(void) {
    prepare_bus_pins();
}

bool panel_bus_lines_high(void) {
    return gpio_get(PANEL_SDA_GPIO) && gpio_get(PANEL_SCL_GPIO);
}

bool panel_bus_recover(void) {
    prepare_bus_pins();
    sleep_ms(1u);

    bool released = wait_line_high(PANEL_SCL_GPIO, LINE_RELEASE_TIMEOUT_US);
    if (released && !gpio_get(PANEL_SDA_GPIO)) {
        for (unsigned pulse = 0u;
             pulse < 9u && !gpio_get(PANEL_SDA_GPIO); ++pulse) {
            drive_line_low(PANEL_SCL_GPIO);
            busy_wait_us_32(10u);
            release_line(PANEL_SCL_GPIO);
            if (!wait_line_high(PANEL_SCL_GPIO, LINE_RELEASE_TIMEOUT_US)) {
                released = false;
                break;
            }
            busy_wait_us_32(10u);
        }
    }

    if (released) {
        /* Generate STOP while only ever actively driving a line low. */
        drive_line_low(PANEL_SDA_GPIO);
        drive_line_low(PANEL_SCL_GPIO);
        busy_wait_us_32(10u);
        release_line(PANEL_SCL_GPIO);
        released = wait_line_high(PANEL_SCL_GPIO, LINE_RELEASE_TIMEOUT_US);
        if (released) {
            busy_wait_us_32(10u);
            release_line(PANEL_SDA_GPIO);
            busy_wait_us_32(10u);
            released = gpio_get(PANEL_SDA_GPIO);
        }
    }

    panel_bus_init();
    sleep_ms(2u);
    return released;
}

bool panel_identify(panel_info_t *info) {
    static const uint8_t expected_identity[3] = {0xc1u, 0x11u, 0x02u};
    if (info == NULL) {
        return false;
    }
    memset(info, 0, sizeof(*info));
    return panel_read(0x01u, info->identity, sizeof(info->identity)) &&
           memcmp(info->identity, expected_identity,
                  sizeof(expected_identity)) == 0 &&
           panel_read(0x06u, &info->ready, 1u) &&
           (info->ready & 0x01u) != 0u;
}

bool panel_outputs_off(void) {
    static const uint8_t status_disabled[2] = {0x00u, 0x00u};
    bool status_ok = panel_write(0x10u, status_disabled,
                                 sizeof(status_disabled));
    bool ring_ok = panel_write_u8(0x19u, 0x10u);
    return status_ok && ring_ok;
}

bool panel_status_steady(uint8_t mask, uint8_t brightness) {
    if ((mask & 0xc0u) != 0u || brightness > 7u) {
        return false;
    }

    /* Registers 0x20..0x22 hold two 4-bit channel levels each.  Register
     * 0x23 selects per-channel levels; the low bit is the observed enable
     * for the final channel pair on this panel revision. */
    const uint8_t packed = (uint8_t)(brightness | (brightness << 4));
    const uint8_t levels[4] = {packed, packed, packed, 0x01u};
    const uint8_t enable[2] = {(uint8_t)(mask & 0x3fu), 0x00u};

    return panel_write(0x10u, (const uint8_t[2]){0x00u, 0x00u}, 2u) &&
           panel_write_u8(0x19u, 0x10u) &&
           panel_write(0x20u, levels, sizeof(levels)) &&
           panel_write(0x10u, enable, sizeof(enable));
}

static bool panel_ring_prepare(uint8_t intensity, uint8_t style_length) {
    if (intensity > 7u) {
        return false;
    }
    const uint8_t status_disabled[2] = {0x00u, 0x00u};
    const uint8_t shape[2] = {
        (uint8_t)(0x60u | intensity), style_length
    };
    return panel_write(0x10u, status_disabled, sizeof(status_disabled)) &&
           panel_write_u8(0x19u, 0x10u) &&
           panel_write(0x14u, shape, sizeof(shape));
}

bool panel_ring_position(uint8_t position, uint8_t intensity) {
    if (position > 7u || !panel_ring_prepare(intensity, 0x00u) ||
        !panel_write_u8(0x18u, 0x00u)) {
        return false;
    }
    /* bit 3 commits the requested phase; bit 4 is the blank flag. */
    return panel_write_u8(0x19u, (uint8_t)(0x08u | position));
}

bool panel_ring_solid(uint8_t intensity) {
    if (!panel_ring_prepare(intensity, 0x70u) ||
        !panel_write_u8(0x18u, 0x00u)) {
        return false;
    }
    return panel_write_u8(0x19u, 0x00u);
}

bool panel_configure_runtime(void) {
    uint8_t config;
    if (!panel_outputs_off() || !panel_read(0x24u, &config, 1u)) {
        return false;
    }
    config = (uint8_t)((config & 0xc0u) | 0x01u);
    if (!panel_write_u8(0x24u, config)) {
        return false;
    }
    sleep_ms(36u);
    return true;
}

bool panel_read_buttons(uint16_t *state) {
    if (state == NULL) {
        return false;
    }

    uint8_t bytes[2];
    if (!panel_read(0x26u, bytes, sizeof(bytes))) {
        return false;
    }
    uint16_t previous = (uint16_t)(bytes[0] | ((uint16_t)bytes[1] << 8));

    for (unsigned attempt = 0u; attempt < 3u; ++attempt) {
        if (!panel_read(0x26u, bytes, sizeof(bytes))) {
            return false;
        }
        uint16_t current = (uint16_t)(bytes[0] |
                                      ((uint16_t)bytes[1] << 8));
        if (current == previous) {
            *state = (uint16_t)(current & 0x7fffu);
            return true;
        }
        previous = current;
    }
    return false;
}

bool panel_ring_spin(uint8_t speed, uint8_t intensity,
                     uint8_t trail, bool reverse) {
    if (speed < 1u || speed > 127u || intensity > 7u ||
        trail < 1u || trail > 8u) {
        return false;
    }

    static const uint8_t status_disabled[2] = {0x00u, 0x00u};
    const uint8_t shape[2] = {
        (uint8_t)(0x60u | intensity),
        (uint8_t)(((trail - 1u) << 4) | 0x01u)
    };
    uint8_t speed_direction = (uint8_t)(speed |
                                         (reverse ? 0x80u : 0x00u));

    return panel_write(0x10u, status_disabled, sizeof(status_disabled)) &&
           panel_write_u8(0x19u, 0x10u) &&
           panel_write(0x14u, shape, sizeof(shape)) &&
           panel_write_u8(0x18u, speed_direction) &&
           (sleep_ms(20u), panel_write_u8(0x19u, 0x00u));
}
