/*
 * Explicit, bounded status pulse for one WS2812B on nice!nano v2 switched VCC.
 * No ZMK RGB underglow state, animation timer, or persistent power setting.
 *
 * Cirque variant: the same switched VCC also powers the Cirque touchpad, so
 * the rail is switched on before the input drivers initialise and stays on
 * while the keyboard is awake. It is only cut on ZMK sleep (soft off). The
 * LED stays dark between pulses because its data line is held low.
 * SPDX-License-Identifier: MIT
 */

#define DT_DRV_COMPAT zmk_behavior_endgame_status_pulse

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/led_strip.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/init.h>
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
/* Must run after GPIO hogs and before the Cirque driver probes the pad. */
#define RAIL_INIT_PRIORITY 60
#define RAIL_SETTLE_MS 50
BUILD_ASSERT(RAIL_INIT_PRIORITY < CONFIG_INPUT_INIT_PRIORITY,
             "VCC rail must be on before the touchpad driver initialises");
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
static bool rail_on;
static bool lit;
/* Guard against an expiry work item already dequeued when a new pulse starts. */
static int64_t end_due_ms;

static int led_off_locked(void) {
    int rc = 0;
    end_due_ms = 0;

    if (lit && rail_on && device_is_ready(pixel)) {
        struct led_rgb black = {0};
        rc = led_strip_update_rgb(pixel, &black, 1);
    }
    lit = false;

    /* The last WS2812 SPI frame is zero-ended. Explicitly drive DIN low
     * between pulses; the PCB also has a 100 kOhm DIN pulldown. */
    int din_rc = gpio_pin_configure_dt(&din, GPIO_OUTPUT_INACTIVE);
    return rc != 0 ? rc : din_rc;
}

static int rail_off_locked(void) {
    int rc = led_off_locked();
    int power_rc = gpio_pin_set_dt(&power, 0);
    rail_on = false;
    return rc != 0 ? rc : power_rc;
}

static void end_work_handler(struct k_work *work) {
    ARG_UNUSED(work);
    k_mutex_lock(&pulse_lock, K_FOREVER);
    int64_t remaining = end_due_ms - k_uptime_get();
    if (end_due_ms != 0 && remaining > 0) {
        if (k_work_reschedule(&end_work, K_MSEC(remaining)) < 0) {
            (void)led_off_locked();
        }
    } else if (end_due_ms != 0) {
        (void)led_off_locked();
    }
    k_mutex_unlock(&pulse_lock);
}

static int cancel_with(int (*off)(void)) {
    k_mutex_lock(&api_lock, K_FOREVER);
    /* This may run on Zephyr's system work queue during ZMK sleep. Waiting
     * for end_work here would deadlock that queue. The mutex and deadline
     * keep cancellation ordered with a possibly running expiry handler. */
    (void)k_work_cancel_delayable(&end_work);
    k_mutex_lock(&pulse_lock, K_FOREVER);
    int rc = off();
    k_mutex_unlock(&pulse_lock);
    k_mutex_unlock(&api_lock);
    return rc;
}

int endgame_status_cancel(void) { return cancel_with(led_off_locked); }

static int rail_shutdown(void) { return cancel_with(rail_off_locked); }

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
    (void)k_work_cancel_delayable(&end_work);
    k_mutex_lock(&pulse_lock, K_FOREVER);
    int rc;
    if (zmk_activity_get_state() == ZMK_ACTIVITY_SLEEP || !rail_on) {
        rc = -EAGAIN;
        goto done;
    }
    rc = led_off_locked();
    if (rc != 0) {
        goto done;
    }
    lit = true;
    k_msleep(1); /* More than the V6's 280 us reset time. */
    struct led_rgb black = {0};
    rc = led_strip_update_rgb(pixel, &black, 1);
    if (rc != 0) {
        goto fail;
    }
    rc = led_strip_update_rgb(pixel, &color, 1);
    if (rc != 0) {
        goto fail;
    }
    end_due_ms = k_uptime_get() + bounded_ms;
    rc = k_work_reschedule(&end_work, K_MSEC(bounded_ms));
    if (rc < 0) {
        goto fail;
    }
    rc = 0;
    goto done;

fail:
    (void)led_off_locked();
done:
    k_mutex_unlock(&pulse_lock);
    k_mutex_unlock(&api_lock);
    return rc;
}

static int rail_power_on(void) {
    /* DIN low first so the pixel powers up without seeing a stray edge. */
    int rc = gpio_pin_configure_dt(&din, GPIO_OUTPUT_INACTIVE);
    if (rc != 0) {
        return rc;
    }
    rc = gpio_pin_configure_dt(&power, GPIO_OUTPUT_ACTIVE);
    if (rc != 0) {
        return rc;
    }
    rail_on = true;
    return 0;
}

static int rail_init(void) {
    if (!gpio_is_ready_dt(&power) || !gpio_is_ready_dt(&din)) {
        return -ENODEV;
    }
    int rc = rail_power_on();
    if (rc != 0) {
        return rc;
    }
    /* Give the Cirque ASIC time to leave power-on reset before its driver
     * reads the firmware ID, like ZMK's ext-power init-delay-ms. */
    k_msleep(RAIL_SETTLE_MS);
    return 0;
}

SYS_INIT(rail_init, POST_KERNEL, RAIL_INIT_PRIORITY);

static int pulse_init(const struct device *dev) {
    ARG_UNUSED(dev);
    k_work_init_delayable(&end_work, end_work_handler);
    return 0;
}

static int pulse_pm_action(const struct device *dev, enum pm_device_action action) {
    ARG_UNUSED(dev);
    if (action == PM_DEVICE_ACTION_SUSPEND) {
        return rail_shutdown();
    }
    if (action == PM_DEVICE_ACTION_RESUME) {
        /* Only reached when ZMK aborts sleep before powering off. The pad
         * re-runs power-on reset; reset the keyboard if it stops tracking. */
        k_mutex_lock(&pulse_lock, K_FOREVER);
        int rc = rail_power_on();
        k_mutex_unlock(&pulse_lock);
        return rc;
    }
    return -ENOTSUP;
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
        return rail_shutdown();
    }
    return 0;
}

ZMK_LISTENER(endgame_status, pulse_activity_listener);
ZMK_SUBSCRIPTION(endgame_status, zmk_activity_state_changed);
