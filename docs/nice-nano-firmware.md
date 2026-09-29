# Endgame nice!nano v2 firmware

The buildable ZMK configuration is in [`003 FIRMWARE/zmk-endgame-nice-nano`](../003%20FIRMWARE/zmk-endgame-nice-nano). It targets **nice!nano v2** (`nice_nano//zmk`, board revision 2.0.0) and the revised Endgame PCB with 36 Choc V1/V2 switch positions, one WS2812B-V6 status LED, and no 74HC595. The original XIAO configuration remains separate.

## Matrix and keymap

The shield uses ZMK's stock `zmk,kscan-gpio-matrix` with COL2ROW diodes, four direct rows, ten direct columns, and the existing 36-position transform. The keymap file is byte-for-byte identical to the old ZMK keymap. No key binding is reassigned to the LED; automatic status indications run independently of the keymap.

| Matrix signal | nice!nano D pin | nRF52840 pin |
| --- | ---: | --- |
| Row 0 | D6 | P1.00 |
| Row 1 | D7 | P0.11 |
| Row 2 | D8 | P1.04 |
| Row 3 | D9 | P1.06 |
| Col 0 | D0 | P0.08 |
| Col 1 | D2 | P0.17 |
| Col 2 | D3 | P0.20 |
| Col 3 | D4 | P0.22 |
| Col 4 | D5 | P0.24 |
| Col 5 | D21 | P0.31 |
| Col 6 | D20 | P0.29 |
| Col 7 | D19 | P0.02 |
| Col 8 | D18 | P1.15 |
| Col 9 | D15 | P1.13 |

The bottom row has positions `RC(3,0)`, `RC(3,3)`, `RC(3,4)`, `RC(3,5)`, `RC(3,6)`, and `RC(3,9)`; these retain Left Shift, Lower/Escape, Return, Space, Raise/Delete, and Right Shift.

## Status pixel

The PCB has one WS2812B-V6 behind the translucent case; no dedicated case opening is needed. Its DIN is on **D1/P0.06** through 330 Ω, with a 100 kΩ pulldown on DIN. Its VDD is on nice!nano v2 switched VCC, decoupled with 100 nF next to the LED. **P0.13 high enables that rail; low disables it.** Firmware disables ZMK's stock persistent `EXT_POWER` node and drives P0.13 low at startup. DIN is also driven low when the LED is unpowered to avoid phantom power through the input pin.

SPI3 is used only to send the WS2812 data on P0.06. A dedicated V6 encoder packs twenty samples per bit at 16 MHz: zero is 312.5 ns high / 937.5 ns low, one is 625 ns high / 625 ns low, and every bit lasts 1.25 µs. It waits 300 µs after each frame and 1 ms after enabling power, then initializes the pixel to black before a pulse. These values match the selected V6 datasheet; the generic four-megahertz WS2812 example is not used. A host test decodes 258 encoded frames and verifies GRB order, high/low pulse widths, and final data-low state. Its stock 74HC595 SPI IRQ patch is neither copied nor applied. ZMK RGB underglow is disabled, so there is no animation, stored on-state, or persistent LED supply.

[`status_pulse.h`](../003%20FIRMWARE/zmk-endgame-nice-nano/status-pulse/include/endgame/status_pulse.h) exposes `endgame_status_pulse(red, green, blue, duration_ms)` and `endgame_status_cancel()` for the widget output adapter and explicit test pulses. Each RGB channel is capped at 25/255 (under 10%); a zero duration uses 100 ms and any requested duration is capped at 500 ms. A fresh voltage reading below 3.6 V suppresses a pulse; sensor failure also suppresses it. The pulse is rejected during sleep, canceled on sleep or device suspend, and cut off after errors or explicit cancellation. This 3.6 V threshold is provisional headroom for the LED's 3.3 V minimum. The battery sensor reads nice!nano VDDH, **not the switched LED rail**; measure LED VDD on the assembled board before treating the threshold as electrically validated.

The behavior node `&status_pulse` is compiled but intentionally unbound. To test it on hardware, temporarily replace an expendable Raise-layer binding such as `&kp F12` in `config/endgame.keymap` with `&status_pulse`, rebuild, press that key while holding Raise, and then restore the keymap. It sends a dim amber 100 ms pulse. Automatic status meanings are supplied by the widget described below.

## Status indications

This revision uses [caksoylar/zmk-rgbled-widget](https://github.com/caksoylar/zmk-rgbled-widget), adapted for the board's single addressable pixel. Upstream normally drives three separate GPIO LED channels; the Endgame adapter routes its colour requests through the existing WS2812B-V6 pulse driver. The widget supplies the battery and connection event logic. This requires no PCB changes.

| Event | Flash meaning |
| --- | --- |
| Boot: battery indication | Green at ≥80%, yellow at 20–79%, red below 20%; magenta if the battery percentage is unavailable |
| Boot, Bluetooth profile change, or selected endpoint change | Blue for connected Bluetooth, yellow for an open advertising profile, red for no connection, cyan when USB is selected |
| Battery state update at 1–5% | Requests a red critical-battery flash, subject to the voltage cutoff below |

**The 3.6 V cutoff applies to every colour and every event.** Red low/critical-battery flashes, and the missing-battery indication, can therefore be suppressed. Do not rely on the pixel as an empty-battery warning. This is intentional until the assembled LED supply is measured; it is not a change to the widget's battery-percentage thresholds.

Battery and connection flashes last **120 ms**, with a **150 ms** gap between queued indications. There is no continuous lighting. Automatic layer indications and persistent layer colours are disabled. The existing keymap is retained. To add an on-demand check later, include `<behaviors/rgbled_widget.dtsi>` in `config/endgame.keymap` and assign `&ind_bat` or `&ind_con` to a chosen position; those checks use the same power and voltage limits.

## Build and flash

Run `003 FIRMWARE/zmk-endgame-nice-nano/build.sh` from the repository or any working directory. The script uses the existing `/tmp/endgame-zmk-workspace` dependency tree and pinned ZMK commit `5b51501fead672c41b5cfb396f3dafe0894bf4e9`. It extracts a clean archive of that commit into a separate temporary source tree and builds in `/tmp/endgame-zmk-workspace/build/endgame-nice-nano`. This isolates the build from the XIAO source's local IRQ patch. The widget is vendored with its MIT licence at upstream commit `e6b467792a1dabef8cfa5c9fd26bfefc9c16662b`, with a local WS2812 output adapter; it is not downloaded from a moving branch during builds. The script stages the config and both modules under a path without spaces because ZMK's devicetree overlay list splits a path containing `003 FIRMWARE`.

The output is [`endgame-nice-nano-v2.uf2`](../003%20FIRMWARE/zmk-endgame-nice-nano/firmware/endgame-nice-nano-v2.uf2). Double-tap reset on nice!nano v2 and copy the UF2 to its bootloader drive. A successful clean compile is recorded in [`build.log`](../003%20FIRMWARE/zmk-endgame-nice-nano/firmware/build.log). The UF2 SHA-256 is:

```text
f5662f0993dc97762743c5ac36d98072a58d338cdeca31086cd5abc1d131457a
```

Host tests also verify the adapter maps all eight widget colours to the intended dim RGB channels. The build proves that the pinned source, devicetree, keymap, widget, pulse module, and target link together. Board-level validation remains: check that P0.13 and LED VDD return low after the boot indication sequence and each pulse, DIN is low while VDD is off, all 36 matrix positions register once, BLE/USB work, and the LED is visible through the case. Measure the LED rail at low battery and during USB charging before choosing a final cutoff.
