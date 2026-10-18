/* Endgame adaptation: upstream widget's 0-7 RGB bitmask to safe PWM values. */
/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>

static inline void endgame_widget_color(uint8_t color, uint8_t rgb[3]) {
    rgb[0] = (color & 1U) ? 25U : 0U;
    rgb[1] = (color & 2U) ? 25U : 0U;
    rgb[2] = (color & 4U) ? 25U : 0U;
}
