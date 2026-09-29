/* SPDX-License-Identifier: MIT */
#define DT_DRV_COMPAT endgame_ws2812_v6_spi
#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/led_strip.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/kernel.h>
#include <endgame/ws2812_v6_encode.h>

static const struct spi_dt_spec bus = SPI_DT_SPEC_INST_GET(
    0, SPI_OP_MODE_MASTER | SPI_TRANSFER_MSB | SPI_WORD_SET(8), 0);

static int update(const struct device *dev, struct led_rgb *pixels, size_t count) {
    ARG_UNUSED(dev);
    if (count != 1) { return -EINVAL; }
    uint8_t encoded[ENDGAME_PIXEL_BYTES];
    endgame_encode_pixel(encoded, pixels[0].r, pixels[0].g, pixels[0].b);
    const struct spi_buf buffer = {.buf = encoded, .len = sizeof(encoded)};
    const struct spi_buf_set tx = {.buffers = &buffer, .count = 1};
    int rc = spi_write_dt(&bus, &tx);
    /* Last encoded bit is zero; keep MOSI low for the V6 latch interval. */
    k_usleep(300);
    return rc;
}

static size_t length(const struct device *dev) { ARG_UNUSED(dev); return 1; }
static int init(const struct device *dev) {
    ARG_UNUSED(dev);
    return spi_is_ready_dt(&bus) ? 0 : -ENODEV;
}
static DEVICE_API(led_strip, api) = {.update_rgb = update, .length = length};
DEVICE_DT_INST_DEFINE(0, init, NULL, NULL, NULL, POST_KERNEL,
                      CONFIG_LED_STRIP_INIT_PRIORITY, &api);
