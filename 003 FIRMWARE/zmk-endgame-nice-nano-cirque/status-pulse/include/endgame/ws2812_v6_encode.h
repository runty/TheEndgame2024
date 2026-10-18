/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <string.h>

/* 16 MHz SPI: twenty samples per WS2812 bit, exactly 1.25 us.
 * 0 = 312.5 ns high + 937.5 ns low; 1 = 625 ns high + 625 ns low.
 * Both satisfy the V6 datasheet rather than the generic 8-sample example.
 */
#define ENDGAME_PIXEL_BYTES 60
static inline void endgame_encode_pixel(uint8_t out[ENDGAME_PIXEL_BYTES],
                                        uint8_t red, uint8_t green, uint8_t blue) {
    const uint8_t grb[] = {green, red, blue};
    memset(out, 0, ENDGAME_PIXEL_BYTES);
    unsigned offset = 0;
    for (unsigned channel = 0; channel < 3; ++channel) {
        for (int bit = 7; bit >= 0; --bit) {
            unsigned high = (grb[channel] & (1u << bit)) ? 10 : 5;
            for (unsigned sample = 0; sample < high; ++sample) {
                unsigned at = offset + sample;
                out[at / 8] |= 0x80u >> (at % 8);
            }
            offset += 20;
        }
    }
}
