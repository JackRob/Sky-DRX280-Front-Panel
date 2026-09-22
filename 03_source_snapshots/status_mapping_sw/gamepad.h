#ifndef SKY_PANEL_GAMEPAD_H
#define SKY_PANEL_GAMEPAD_H

#include <stdint.h>

void gamepad_init(void);
void gamepad_update(uint16_t sky_button_state);
void gamepad_release(void);

#endif
