#ifndef SKY_PANEL_H
#define SKY_PANEL_H

#include <stdbool.h>
#include <stdint.h>

/*
 * Verified panel signals in the installed wiring:
 *   panel green  (SCL) -> GP16
 *   panel orange (SDA) -> GP17
 *
 * This pin pair cannot be routed to one RP2040/RP2350 hardware-I2C instance,
 * so panel.c deliberately uses open-drain software I2C.
 */
#define PANEL_SCL_GPIO 16u
#define PANEL_SDA_GPIO 17u

typedef struct {
    uint8_t identity[3];
    uint8_t ready;
} panel_info_t;

void panel_bus_init(void);
bool panel_bus_lines_high(void);
bool panel_bus_recover(void);

bool panel_identify(panel_info_t *info);
bool panel_configure_runtime(void);
bool panel_read_buttons(uint16_t *state);

bool panel_outputs_off(void);
bool panel_status_steady(uint8_t mask, uint8_t brightness);
bool panel_ring_position(uint8_t position, uint8_t intensity);
bool panel_ring_solid(uint8_t intensity);
bool panel_ring_spin(uint8_t speed, uint8_t intensity,
                     uint8_t trail, bool reverse);

#endif
