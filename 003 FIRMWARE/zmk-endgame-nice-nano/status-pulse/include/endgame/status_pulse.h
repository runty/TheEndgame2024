#pragma once

#include <stdint.h>

/* Call from thread context. RGB values are independently capped at 25/255.
 * duration_ms=0 uses 100 ms; all durations are capped at 500 ms.
 * Returns -EAGAIN at low battery or while sleeping. */
int endgame_status_pulse(uint8_t red, uint8_t green, uint8_t blue,
                         uint16_t duration_ms);

/* Synchronously turns the LED off, then cuts its switched power rail. */
int endgame_status_cancel(void);
