# XIAO wireless firmware

This directory contains the Endgame ZMK shield for the proposed standard Seeed XIAO nRF52840 wireless revision. It preserves the original 4-row × 10-column COL2ROW matrix and 36-key physical layout. The existing RP2040/QMK images and configuration remain for the wired board.

## Pin allocation

| XIAO pin | Use |
| --- | --- |
| D0–D3 | Matrix rows 0–3, direct active-high inputs with pull-downs |
| D4–D5 | Matrix columns 8–9, direct active-high outputs |
| D8 | 74HC595 serial clock / SPI SCK |
| D9 | 74HC595 storage-register clock / SPI chip select |
| D10 | 74HC595 serial data / SPI MOSI |
| 74HC595 QA–QH | Matrix columns 0–7, in that order |
| P0.13 | Charger current select, high-impedance input for the approximately 50 mA setting |
| D6–D7 | Reserved |

The shield uses the board's `xiao_spi` and `xiao_d` aliases. The 595 is configured as the eight-output GPIO provider described in the [ZMK shift-register guide](https://zmk.dev/docs/hardware-integration/shift-registers). With OE tied to GND and SRCLR tied to 3V3 as specified in the hardware plan, outputs are enabled continuously and firmware initializes them low as part of matrix setup. The 595 outputs must connect QA through QH to columns 0 through 7 in the listed order. Keep the row inputs directly connected to the MCU so a row transition can wake scanning.

## Keymap behavior

The base layer preserves the source QWERTY layout and both outer Shift keys. Holding the left inner thumb enters the number/symbol layer while tapping it sends Escape; holding the right inner thumb enters the navigation/editing layer while tapping it sends Delete. The raise layer also selects Bluetooth slots 0–2, advances to the next slot, and clears the active bond. Battery level reporting uses ZMK's XIAO BLE board sensor and the standard BLE Battery Service.

ZMK's upstream XIAO board definition provides a voltage-divider sensor on ADC channel 7, controlled by P0.14; the charger-current GPIO hog in this shield configures P0.13 as an unpulled input, which Seeed documents as the lower-current charge setting. The firmware build proves these definitions are accepted by the pinned ZMK/Zephyr source. Confirm the sensing path and charge current on the exact production XIAO revision with a meter before relying on its reported percentage or charging behavior; firmware configuration does not replace those hardware checks. See the [XIAO nRF52840 hardware documentation](https://wiki.seeedstudio.com/XIAO_BLE/) and ZMK's [battery configuration guide](https://zmk.dev/docs/hardware-integration/battery).

## Shift-register interrupt fix

The selected upstream revision still has the behavior reported in [ZMK issue #2945](https://github.com/zmkfirmware/zmk/issues/2945): the [GPIO matrix interrupt callback](https://github.com/zmkfirmware/zmk/blob/5b51501fead672c41b5cfb396f3dafe0894bf4e9/app/module/drivers/kscan/kscan_gpio_matrix.c) disables row interrupts and writes every output low immediately, while the [595 GPIO driver](https://github.com/zmkfirmware/zmk/blob/5b51501fead672c41b5cfb396f3dafe0894bf4e9/app/module/drivers/gpio/gpio_595.c) returns `-EWOULDBLOCK` for SPI writes from interrupt context. The bundled patch changes the callback to disable only the direct row interrupts, then reset 595-backed columns in the matrix workqueue before scanning. This preserves interrupt wake-up and avoids SPI transactions in the GPIO ISR. `patches/zmk-kscan-spi-irq.patch` is applied by the build script to the exact pinned source revision.

The keyboard uses the GPIO matrix driver's normal interrupt mode, not polling. In idle, all columns are high so a pressed key raises a directly connected row; the GPIO ISR masks row interrupts and schedules the scan worker. The worker sets columns low, scans one column at a time, and restores the all-high wake state after debounce completes. SPI errors retry with bounded backoff, then attempt to restore row wake interrupts; a persistent error is retried at one-second intervals without a tight loop or repeated log flood. Errors from the final all-high wake transition are propagated into this recovery path. ZMK deep sleep is enabled with its 15-minute default idle-sleep timeout. First-board testing must verify row wake from actual system-off/deep sleep as well as ordinary idle scans.

## Reproducible build

The manifest pins ZMK to commit `5b51501fead672c41b5cfb396f3dafe0894bf4e9` (2026-09-28 upstream main snapshot) and imports that revision's pinned Zephyr and module revisions. Install the [ZMK local build prerequisites](https://zmk.dev/docs/development/local-toolchain/installation), including `west`, CMake, Ninja, the Zephyr SDK and device-tree compiler. From the repository root, run:

```sh
cd '003 FIRMWARE/zmk-endgame'
./build.sh
```

The script initializes and updates the West workspace, applies the ISR-safe scan patch, builds board `xiao_ble/nrf52840/zmk` with shield `endgame`, enables sleep, and copies the UF2 to `firmware/endgame-xiao-nrf52840.uf2`. To enter the bootloader, double-tap the XIAO reset button and copy the UF2 to the mounted XIAO BLE volume, as described in the [Zephyr XIAO BLE board guide](https://docs.zephyrproject.org/latest/boards/seeed/xiao_ble/doc/index.html).

No hardware test has been performed. Before treating this branch as a working wireless keyboard, check all 36 switches, rollover, Bluetooth pairing and slot changes, battery reporting against a meter, approximately 50 mA charging, wake from both idle and deep sleep, and idle current on the assembled board.
