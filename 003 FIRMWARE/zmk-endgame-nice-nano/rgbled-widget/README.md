# Endgame RGB LED widget adapter

This directory vendors the event and behavior code from
[caksoylar/zmk-rgbled-widget](https://github.com/caksoylar/zmk-rgbled-widget)
at commit `e6b467792a1dabef8cfa5c9fd26bfefc9c16662b` (MIT; see `LICENSE`).
The upstream shield and its GPIO LED definitions are omitted because Endgame
uses one switched-supply WS2812B-V6 pixel.

The local patch in `src/widget.c` replaces the three-channel GPIO LED backend
with `endgame_status_pulse()` and `endgame_status_cancel()`. The original event
listeners, status selection, message queue, threads, and on-demand behaviors are
retained. Durations are capped at 500 ms before the API call; the pulse API also
caps each color channel at 25/255 and rejects flashes while sleeping or when
the measured supply is below 3600 mV. The adapter rejects persistent layer
colors at compile time. `Kconfig` no longer enables the unused GPIO LED driver.

To update upstream, compare this directory against the pinned commit before
reapplying the backend adaptation. The build copies this directory into its
staging workspace and passes it to ZMK as an extra module.

The host color mapping check is:

```sh
cc -std=c11 -Wall -Wextra -Werror -I rgbled-widget/include \
  rgbled-widget/tests/color_test.c -o /tmp/endgame-color-test
/tmp/endgame-color-test
```
