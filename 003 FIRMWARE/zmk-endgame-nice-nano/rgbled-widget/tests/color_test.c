/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#include <zmk_rgbled_widget/endgame_color.h>

int main(void) {
    static const uint8_t expected[8][3] = {
        {0, 0, 0}, {25, 0, 0}, {0, 25, 0}, {25, 25, 0},
        {0, 0, 25}, {25, 0, 25}, {0, 25, 25}, {25, 25, 25},
    };
    for (uint8_t color = 0; color < 8; color++) {
        uint8_t rgb[3] = {0};
        endgame_widget_color(color, rgb);
        for (int channel = 0; channel < 3; channel++) {
            assert(rgb[channel] == expected[color][channel]);
        }
    }
    puts("8 widget colors map to capped RGB channels");
}
