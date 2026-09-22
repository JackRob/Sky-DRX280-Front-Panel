#include "gamepad.h"

#include <stdbool.h>
#include <string.h>

#include "tusb.h"
#include "usb_descriptors.h"

/* Raw button bits from the panel, measured on this exact board. */
#define BUTTON_RECORD    (1u << 6)
#define BUTTON_INFO      (1u << 4)
#define BUTTON_SELECT    (1u << 2)
#define BUTTON_LEFT      (1u << 1)
#define BUTTON_UP        (1u << 0)
#define BUTTON_RIGHT     (1u << 9)
#define BUTTON_DOWN      (1u << 8)
#define BUTTON_TV_GUIDE  (1u << 12)
#define BUTTON_BACK_UP   (1u << 10)

static hid_gamepad_report_t last_report;
static bool last_report_valid;

static uint8_t make_hat(uint16_t state) {
    const bool up = (state & BUTTON_UP) != 0u;
    const bool down = (state & BUTTON_DOWN) != 0u;
    const bool left = (state & BUTTON_LEFT) != 0u;
    const bool right = (state & BUTTON_RIGHT) != 0u;

    if (up && right) {
        return GAMEPAD_HAT_UP_RIGHT;
    }
    if (up && left) {
        return GAMEPAD_HAT_UP_LEFT;
    }
    if (down && right) {
        return GAMEPAD_HAT_DOWN_RIGHT;
    }
    if (down && left) {
        return GAMEPAD_HAT_DOWN_LEFT;
    }
    if (up) {
        return GAMEPAD_HAT_UP;
    }
    if (down) {
        return GAMEPAD_HAT_DOWN;
    }
    if (left) {
        return GAMEPAD_HAT_LEFT;
    }
    if (right) {
        return GAMEPAD_HAT_RIGHT;
    }
    return GAMEPAD_HAT_CENTERED;
}

static hid_gamepad_report_t make_report(uint16_t state) {
    hid_gamepad_report_t report;
    memset(&report, 0, sizeof(report));
    report.hat = make_hat(state);

    if ((state & BUTTON_SELECT) != 0u) {
        report.buttons |= GAMEPAD_BUTTON_A;
    }
    if ((state & BUTTON_BACK_UP) != 0u) {
        report.buttons |= GAMEPAD_BUTTON_B;
    }
    if ((state & BUTTON_TV_GUIDE) != 0u) {
        report.buttons |= GAMEPAD_BUTTON_X;
    }
    if ((state & BUTTON_INFO) != 0u) {
        report.buttons |= GAMEPAD_BUTTON_Y;
    }
    if ((state & BUTTON_RECORD) != 0u) {
        /* The generic HID gamepad's MODE button is the Xbox/Home analogue. */
        report.buttons |= GAMEPAD_BUTTON_MODE;
    }
    return report;
}

void gamepad_init(void) {
    memset(&last_report, 0, sizeof(last_report));
    last_report.hat = GAMEPAD_HAT_CENTERED;
    last_report_valid = false;
}

void gamepad_update(uint16_t sky_button_state) {
    hid_gamepad_report_t report = make_report(sky_button_state);
    if (last_report_valid && memcmp(&report, &last_report, sizeof(report)) == 0) {
        return;
    }

    if (!tud_hid_ready()) {
        last_report_valid = false;
        return;
    }

    if (tud_hid_report(REPORT_ID_GAMEPAD, &report, sizeof(report))) {
        last_report = report;
        last_report_valid = true;
    }
}

void gamepad_release(void) {
    gamepad_update(0u);
}

/* TinyUSB requires these callbacks whenever a HID interface is enabled. */
uint16_t tud_hid_get_report_cb(uint8_t instance, uint8_t report_id,
                               hid_report_type_t report_type,
                               uint8_t *buffer, uint16_t reqlen) {
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)reqlen;
    return 0u;
}

void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id,
                           hid_report_type_t report_type,
                           uint8_t const *buffer, uint16_t bufsize) {
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)bufsize;
}
