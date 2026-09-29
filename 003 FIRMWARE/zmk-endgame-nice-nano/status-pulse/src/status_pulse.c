/*
 * Explicit, bounded status pulse for one WS2812B on nice!nano v2 switched VCC.
 * No ZMK RGB underglow state, animation timer, or persistent power setting.
 * SPDX-License-Identifier: MIT
 */

#define DT_DRV_COMPAT zmk_behavior_endgame_status_pulse

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/led_strip.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/pm/device.h>
#include <zephyr/sys/util.h>

#include <drivers/behavior.h>
#include <zmk/activity.h>
#include <zmk/event_manager.h>
#include <zmk/events/activity_state_changed.h>

#include <endgame/status_pulse.h>

#define PIXEL_NODE DT_NODELABEL(status_pixel)
#define BATTERY_NODE DT_CHOSEN(zmk_battery)

/* P0.13 is the nice!nano v2 VCC enable; P0.06 is SPI3 MOSI / LED DIN.
 * They are intentionally not shared with the matrix. */
static const struct gpio_dt_spec power = {
    .port = DEVICE_DT_GET(DT_NODELABEL(gpio0)), .pin = 13, .dt_flags = GPIO_ACTIVE_HIGH};
static const struct gpio_dt_spec din = {
    .port = DEVICE_DT_GET(DT_NODELABEL(gpio0)), .pin = 6, .dt_flags = GPIO_ACTIVE_HIGH};
static const struct device *const pixel = DEVICE_DT_GET(PIXEL_NODE);
static const struct device *const battery = DEVICE_DT_GET(BATTERY_NODE);

enum {
    PULSE_DEFAULT_MS = 100,
    PULSE_MAX_MS = 500,
    PULSE_MAX_CHANNEL = 25, /* at most 9.8% of each PWM channel */
    PULSE_MIN_BATTERY_MV = 3600,
};

static K_MUTEX_DEFINE(pulse_lock);
static K_MUTEX_DEFINE(api_lock);
static struct k_work_delayable end_work;
static struct k_work_sync end_sync;
static bool powered;

static int power_off_locked(void) {
    int rc = 0;

    if (powered && device_is_ready(pixel)) {
        struct led_rgb black = {0};
        rc = led_strip_update_rgb(pixel, &black, 1);
    }

    /* The last WS2812 SPI frame is zero-ended. Explicitly drive DIN low
     * before removing VCC; the PCB also has a 100 kOhm DIN pulldown. */
    int din_rc = gpio_pin_configure_dt(&din, GPIO_OUTPUT_INACTIVE);
    int power_rc = gpio_pin_set_dt(&power, 0);
    powered = false;

    if (rc != 0) {
        return rc;
    }
    return din_rc != 0 ? din_rc : power_rc;
}

static void end_work_handler(struct k_work *work) {
    ARG_UNUSED(work);
    k_mutex_lock(&pulse_lock, K_FOREVER);
    (void)power_off_locked();
    k_mutex_unlock(&pulse_lock);
}

int endgame_status_cancel(void) {
    k_mutex_lock(&api_lock, K_FOREVER);
    k_work_cancel_delayable_sync(&end_work, &end_sync);
    k_mutex_lock(&pulse_lock, K_FOREVER);
    int rc = power_off_locked();
    k_mutex_unlock(&pulse_lock);
    k_mutex_unlock(&api_lock);
    return rc;
}

static int battery_millivolts(void) {
    if (!device_is_ready(battery)) {
        return -ENODEV;
    }
    int rc = sensor_sample_fetch_chan(battery, SENSOR_CHAN_GAUGE_VOLTAGE);
    if (rc != 0) {
        return rc;
    }
    struct sensor_value voltage;
    rc = sensor_channel_get(battery, SENSOR_CHAN_GAUGE_VOLTAGE, &voltage);
    if (rc != 0) {
        return rc;
    }
    return voltage.val1 * 1000 + voltage.val2 / 1000;
}

int endgame_status_pulse(uint8_t red, uint8_t green, uint8_t blue,
                         uint16_t duration_ms) {
    /* Fail closed when the LED supply may be below its minimum rating. The
     * built-in VDDH sensor measures supply voltage, not switched VCC. */
    int mv = battery_millivolts();
    if (mv < 0) {
        return mv;
    }
    if (mv < PULSE_MIN_BATTERY_MV) {
        return -EAGAIN;
    }
    if (!device_is_ready(pixel)) {
        return -ENODEV;
    }

    uint16_t bounded_ms = duration_ms == 0 ? PULSE_DEFAULT_MS :
                          MIN(duration_ms, PULSE_MAX_MS);
    struct led_rgb color = {
        .r = MIN(red, PULSE_MAX_CHANNEL),
        .g = MIN(green, PULSE_MAX_CHANNEL),
        .b = MIN(blue, PULSE_MAX_CHANNEL),
    };

    k_mutex_lock(&api_lock, K_FOREVER);
    k_work_cancel_delayable_sync(&end_work, &end_sync);
    k_mutex_lock(&pulse_lock, K_FOREVER);
    int rc;
    if (zmk_activity_get_state() == ZMK_ACTIVITY_SLEEP) {
        rc = -EAGAIN;
        goto done;
    }
    rc = power_off_locked();
    if (rc != 0) {
        goto done;
    }
    rc = gpio_pin_set_dt(&power, 1);
    if (rc != 0) {
        goto fail;
    }
    powered = true;
    k_msleep(1); /* Rail settling and more than the V6's 280 us reset time. */
    struct led_rgb black = {0};
    rc = led_strip_update_rgb(pixel, &black, 1);
    if (rc != 0) {
        goto fail;
    }
    rc = led_strip_update_rgb(pixel, &color, 1);
    if (rc != 0) {
        goto fail;
    }
    rc = k_work_reschedule(&end_work, K_MSEC(bounded_ms));
    if (rc < 0) {
        goto fail;
    }
    rc = 0;
    goto done;

fail:
    (void)power_off_locked();
done:
    k_mutex_unlock(&pulse_lock);
    k_mutex_unlock(&api_lock);
    return rc;
}

static int pulse_init(const struct device *dev) {
    ARG_UNUSED(dev);
    if (!gpio_is_ready_dt(&power) || !gpio_is_ready_dt(&din)) {
        return -ENODEV;
    }
    int rc = gpio_pin_configure_dt(&din, GPIO_OUTPUT_INACTIVE);
    if (rc != 0) {
        return rc;
    }
    rc = gpio_pin_configure_dt(&power, GPIO_OUTPUT_INACTIVE);
    if (rc != 0) {
        return rc;
    }
    k_work_init_delayable(&end_work, end_work_handler);
    return 0;
}

static int pulse_pm_action(const struct device *dev, enum pm_device_action action) {
    ARG_UNUSED(dev);
    if (action == PM_DEVICE_ACTION_SUSPEND) {
        return endgame_status_cancel();
    }
    return action == PM_DEVICE_ACTION_RESUME ? 0 : -ENOTSUP;
}

static int pulse_pressed(struct zmk_behavior_binding *binding,
                         struct zmk_behavior_binding_event event) {
    ARG_UNUSED(binding);
    ARG_UNUSED(event);
    return endgame_status_pulse(25, 10, 0, PULSE_DEFAULT_MS);
}

static int pulse_released(struct zmk_behavior_binding *binding,
                          struct zmk_behavior_binding_event event) {
    ARG_UNUSED(binding);
    ARG_UNUSED(event);
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api pulse_api = {
    .binding_pressed = pulse_pressed,
    .binding_released = pulse_released,
    .locality = BEHAVIOR_LOCALITY_GLOBAL,
};

PM_DEVICE_DT_INST_DEFINE(0, pulse_pm_action);
BEHAVIOR_DT_INST_DEFINE(0, pulse_init, PM_DEVICE_DT_INST_GET(0), NULL, NULL,
                        POST_KERNEL, 95, &pulse_api);

static int pulse_activity_listener(const zmk_event_t *event) {
    const struct zmk_activity_state_changed *activity =
        as_zmk_activity_state_changed(event);
    if (activity != NULL && activity->state == ZMK_ACTIVITY_SLEEP) {
        return endgame_status_cancel();
    }
    return 0;
}

ZMK_LISTENER(endgame_status, pulse_activity_listener);
ZMK_SUBSCRIPTION(endgame_status, zmk_activity_state_changed);
