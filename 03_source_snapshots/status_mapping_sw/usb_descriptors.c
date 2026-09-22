#include <string.h>

#include "pico/unique_id.h"
#include "tusb.h"
#include "usb_descriptors.h"

#define USB_VID 0x2e8au
#define USB_PID 0x105au
#define USB_BCD 0x0200u

enum {
    ITF_NUM_CDC = 0,
    ITF_NUM_CDC_DATA,
    ITF_NUM_HID,
    ITF_NUM_TOTAL
};

enum {
    STRID_LANGID = 0,
    STRID_MANUFACTURER,
    STRID_PRODUCT,
    STRID_SERIAL,
    STRID_CDC,
    STRID_HID
};

#define EPNUM_CDC_NOTIF 0x81u
#define EPNUM_CDC_OUT   0x02u
#define EPNUM_CDC_IN    0x82u
#define EPNUM_HID_IN    0x83u
#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN + \
                          TUD_HID_DESC_LEN)

static tusb_desc_device_t const device_descriptor = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = USB_BCD,
    .bDeviceClass = TUSB_CLASS_MISC,
    .bDeviceSubClass = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = USB_VID,
    .idProduct = USB_PID,
    .bcdDevice = 0x0100u,
    .iManufacturer = STRID_MANUFACTURER,
    .iProduct = STRID_PRODUCT,
    .iSerialNumber = STRID_SERIAL,
    .bNumConfigurations = 1u
};

uint8_t const hid_report_descriptor[] = {
    TUD_HID_REPORT_DESC_GAMEPAD(HID_REPORT_ID(REPORT_ID_GAMEPAD))
};

static uint8_t const configuration_descriptor[] = {
    TUD_CONFIG_DESCRIPTOR(1u, ITF_NUM_TOTAL, 0u, CONFIG_TOTAL_LEN,
                          TUSB_DESC_CONFIG_ATT_SELF_POWERED, 1u),
    TUD_CDC_DESCRIPTOR(ITF_NUM_CDC, STRID_CDC, EPNUM_CDC_NOTIF, 8u,
                       EPNUM_CDC_OUT, EPNUM_CDC_IN, 64u),
    TUD_HID_DESCRIPTOR(ITF_NUM_HID, STRID_HID, HID_ITF_PROTOCOL_NONE,
                       sizeof(hid_report_descriptor), EPNUM_HID_IN,
                       CFG_TUD_HID_EP_BUFSIZE, 5u)
};

uint8_t const *tud_descriptor_device_cb(void) {
    return (uint8_t const *)&device_descriptor;
}

uint8_t const *tud_hid_descriptor_report_cb(uint8_t instance) {
    (void)instance;
    return hid_report_descriptor;
}

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
    (void)index;
    return configuration_descriptor;
}

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    static uint16_t descriptor_string[32u];
    static char serial[PICO_UNIQUE_BOARD_ID_SIZE_BYTES * 2u + 1u];

    if (index == STRID_LANGID) {
        descriptor_string[1] = 0x0409u;
        descriptor_string[0] = (uint16_t)((TUSB_DESC_STRING << 8) | 4u);
        return descriptor_string;
    }

    const char *text = NULL;
    switch (index) {
        case STRID_MANUFACTURER:
            text = "Sky+";
            break;
        case STRID_PRODUCT:
            text = "Box";
            break;
        case STRID_CDC:
            text = "Sky+ Box diagnostics";
            break;
        case STRID_HID:
            text = "Sky+ Box gamepad";
            break;
        case STRID_SERIAL:
            if (serial[0] == '\0') {
                pico_get_unique_board_id_string(serial, sizeof(serial));
            }
            text = serial;
            break;
        default:
            return NULL;
    }

    size_t count = strlen(text);
    if (count > 31u) {
        count = 31u;
    }
    for (size_t i = 0u; i < count; ++i) {
        descriptor_string[i + 1u] = (uint16_t)text[i];
    }
    descriptor_string[0] =
        (uint16_t)((TUSB_DESC_STRING << 8) | (2u * count + 2u));
    return descriptor_string;
}
