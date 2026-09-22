#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "panel.h"
#include "pico/stdlib.h"

#define VERSION "1.3.0-status-map-sw"
#define LINE_SIZE 96u

static bool online;

static void identify_panel(void) {
    panel_bus_init();
    sleep_ms(2u);
    if (!panel_bus_lines_high()) {
        printf("BUS LOW: SDA/GP17=%u SCL/GP16=%u; trying recover.\r\n",
               (unsigned)gpio_get(PANEL_SDA_GPIO),
               (unsigned)gpio_get(PANEL_SCL_GPIO));
        if (!panel_bus_recover() || !panel_bus_lines_high()) {
            online = false;
            printf("RECOVERY FAILED: check panel power, ground, HV/LV, SDA/SCL.\r\n");
            return;
        }
    }
    panel_info_t info;
    if (!panel_identify(&info) || !panel_configure_runtime()) {
        online = false;
        printf("IDENTIFY FAILED: panel did not return C1 11 02/ready.\r\n");
        return;
    }
    online = true;
    printf("PANEL ONLINE: ID=%02X %02X %02X ready=%02X\r\n",
           info.identity[0], info.identity[1], info.identity[2], info.ready);
}

static void help(void) {
    printf("Commands:\r\n"
           "  help                         this help\r\n"
           "  info                         show bus/panel state\r\n"
           "  recover                      recover and identify panel\r\n"
           "  off                          all status/ring outputs off\r\n"
           "  led <0-5|all> <0-6>          one/all status channels\r\n"
           "  ledtest [brightness] [ms]    channels 0..5 then off\r\n");
}

static void info(void) {
    printf("STATUS online=%u SDA/GP17=%u SCL/GP16=%u\r\n",
           (unsigned)online, (unsigned)gpio_get(PANEL_SDA_GPIO),
           (unsigned)gpio_get(PANEL_SCL_GPIO));
}

static bool parse_long(const char *text, long min, long max, long *value) {
    char *end = NULL;
    long parsed = strtol(text, &end, 0);
    if (end == text || *end != '\0' || parsed < min || parsed > max) return false;
    *value = parsed;
    return true;
}

static void command(char *line) {
    char *argv[4] = {0};
    unsigned argc = 0u;
    char *p = strtok(line, " \t");
    while (p != NULL && argc < 4u) {
        argv[argc++] = p;
        p = strtok(NULL, " \t");
    }
    if (argc == 0u) return;
    if (strcmp(argv[0], "help") == 0) { help(); return; }
    if (strcmp(argv[0], "info") == 0) { info(); return; }
    if (strcmp(argv[0], "recover") == 0) { identify_panel(); return; }
    if (strcmp(argv[0], "off") == 0) {
        if (!online || !panel_outputs_off()) printf("OFF FAILED: panel offline or write failed.\r\n");
        else printf("OFF OK\r\n");
        return;
    }
    if (strcmp(argv[0], "led") == 0) {
        if (argc != 3u || !online) { printf("Usage: led <0-5|all> <brightness 0-7 (7 only for channel 5)>\r\n"); return; }
        long level;
        uint8_t mask = 0u;
        if (strcmp(argv[1], "all") == 0) {
            mask = 0x3fu;
        } else {
            long channel;
            if (!parse_long(argv[1], 0, 5, &channel)) { printf("Bad channel\r\n"); return; }
            if (!parse_long(argv[2], 0, channel == 5 ? 7 : 6, &level)) { printf("Bad brightness\r\n"); return; }
            mask = (uint8_t)(1u << channel);
        }
        if (strcmp(argv[1], "all") == 0 && !parse_long(argv[2], 0, 6, &level)) { printf("Bad brightness\r\n"); return; }
        if (panel_status_steady(mask, (uint8_t)level)) printf("LED OK mask=0x%02X brightness=%ld\r\n", mask, level);
        else printf("LED FAILED\r\n");
        return;
    }
    if (strcmp(argv[0], "ledtest") == 0) {
        if (!online) { printf("LEDTEST FAILED: panel offline\r\n"); return; }
        long level = 2;
        long step = 700;
        if (argc >= 2u && !parse_long(argv[1], 1, 6, &level)) { printf("Bad brightness\r\n"); return; }
        if (argc >= 3u && !parse_long(argv[2], 50, 5000, &step)) { printf("Bad step time\r\n"); return; }
        for (unsigned channel = 0u; channel < 6u; ++channel) {
            if (!panel_status_steady((uint8_t)(1u << channel), (uint8_t)level)) {
                printf("LEDTEST FAILED channel=%u\r\n", channel);
                return;
            }
            printf("LEDTEST channel=%u mask=0x%02X\r\n", channel, 1u << channel);
            sleep_ms((uint32_t)step);
        }
        (void)panel_outputs_off();
        printf("LEDTEST complete; outputs off.\r\n");
        return;
    }
    printf("Unknown command; type help.\r\n");
}

int main(void) {
    stdio_init_all();
    sleep_ms(1500u);
    printf("\r\nDRX280 status mapping tester v%s\r\n", VERSION);
    printf("Orange/SDA=GP17, Green/SCL=GP16; GP9 unused.\r\n");
    identify_panel();
    help();
    char line[LINE_SIZE];
    size_t length = 0u;
    for (;;) {
        int ch = getchar_timeout_us(1000u);
        if (ch == PICO_ERROR_TIMEOUT) continue;
        if (ch == '\r' || ch == '\n') {
            line[length] = '\0';
            command(line);
            length = 0u;
        } else if (ch == 8 || ch == 127) {
            if (length != 0u) --length;
        } else if (isprint((unsigned char)ch) && length + 1u < sizeof(line)) {
            line[length++] = (char)ch;
        }
    }
}
