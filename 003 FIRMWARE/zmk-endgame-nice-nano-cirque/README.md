# Endgame nice!nano + Cirque ZMK firmware

ZMK firmware for the wireless nice!nano v2 Endgame with a 40 mm Cirque
TM040040 (Pinnacle ASIC) touchpad between the thumb clusters. It is the
[`zmk-endgame-nice-nano`](../zmk-endgame-nice-nano) build plus the touchpad:
same 4x10 matrix, same WS2812B-V6 status LED, same sample QWERTY keymap, and
the same pinned ZMK revision (`5b51501fead672c41b5cfb396f3dafe0894bf4e9`).

The keymap is a generic sample. Replace `config/endgame.keymap` with your own.

## Firmware files

| File | Use |
| --- | --- |
| `firmware/endgame-nice-nano-cirque.uf2` | The keyboard |
| `firmware/settings-reset-nice-nano.uf2` | Clears stored Bluetooth bonds and settings |

## Touchpad pins

The matrix uses the same pins as the non-Cirque build (columns D0, D2, D3, D4,
D5, D21, D20, D19, D18, D15; rows D6-D9; LED data on D1/P0.06). The touchpad
uses the three pins that build left free:

| Signal | nice!nano pin | nRF52840 | Notes |
| --- | --- | --- | --- |
| SDA | D14 | P1.11 | 4.7 kOhm pull-up to VCC on the PCB |
| SCL | D16 | P0.10 | 4.7 kOhm pull-up to VCC on the PCB; NFC pad |
| DR (data ready) | D10 | P0.09 | Active high; NFC pad |
| VDD | VCC | P0.13-switched 3.3 V | Shared with the status LED |
| GND | GND | | |

P0.09 and P0.10 are the nRF52840 NFC pads. The nice!nano board files do not
release them, so the shield overlay sets `nfct-pins-as-gpios` in the UICR. The
first boot after flashing writes the UICR and resets once.

`&pro_micro_i2c` cannot be used as-is because its default pins (D2/D3) are
matrix columns. The overlay keeps the TWIM0 instance (`&i2c0`) and gives it its
own pinctrl on D14/D16, at 100 kHz. The pad is at I2C address `0x2A`.

## Preparing the TM040040

The pad ships in SPI mode. Remove resistor **R1** on the back of the pad to
put it in I2C mode (R1 populated = SPI, R1 empty = I2C). Nothing else changes;
do not remove R7/R8 (those are only for 5 V logic).

## FFC wiring

The pad connects through a 12-pin, 0.5 mm pitch FFC to the connector on the
PCB. Pad-side pin numbering (Cirque TM040040 spec) and where each signal
arrives on the Endgame's J2: the cable's 90-degree path keeps conductor order,
so pad pin N lands on J2 pin 13 - N.

| Pad pin | Pad signal | J2 pin | Endgame |
| --- | --- | --- | --- |
| 1 | SCK | 12 | not connected (SPI only) |
| 2 | SO / MISO | 11 | not connected (SPI only) |
| 3 | SS | 10 | not connected (SPI only) |
| 4 | DR | 9 | D10 / P0.09 |
| 5 | SI / MOSI | 8 | not connected (SPI only) |
| 6 | B2 | 7 | not connected |
| 7 | B3 | 6 | not connected |
| 8 | B1 | 5 | not connected |
| 9 | SCL | 4 | D16 / P0.10 |
| 10 | SDA | 3 | D14 / P1.11 |
| 11 | GND | 2 | GND |
| 12 | VDD | 1 | switched VCC (3.3 V) |

The cable's contact side must suit both connectors (see
[the build notes](../../docs/nice-nano-cirque.md#touchpad)); check pad VDD to
J2 pin 1 for continuity before first power-up. The pad has no I2C pull-ups of
its own; R3/R4 on the PCB provide them.

## Touchpad behaviour

The Pinnacle settings match a known-good Cirque build on a nice!nano:

```dts
glidepoint: trackpad@2a {
    compatible = "cirque,pinnacle";
    reg = <0x2a>;
    data-mode = "relative";
    sensitivity = "1x";
    data-ready-gpios = <&gpio0 9 GPIO_ACTIVE_HIGH>;
    primary-tap-enable;
};
```

- `sensitivity = "1x"` is the most sensitive ADC setting on this driver. Pointer
  speed comes from `zip_xy_scaler 3 1` instead; Y is inverted so up is up.
- Tap to click is on (`primary-tap-enable`).
- Holding **Raise** (right inner thumb) turns the pad into a scroll surface,
  scaled with `zip_xy_scaler 1 20`.
- The Raise layer has left, middle and right click on the left bottom row
  (`&mkp LCLK`, `&mkp MCLK`, `&mkp RCLK`), so you can hold Raise and click or
  scroll without moving hands.
- `sleep-mode-enable` is deliberately **not** set. With the Pinnacle's own
  low-power mode on, the pad could stop responding until the keyboard was power
  cycled; the Zephyr driver does not recover the ASIC from that state.

### Zephyr driver patch

`patches/zephyr/input-pinnacle-cirque.patch` is applied by `build.sh` to the
workspace's Zephyr checkout (it is a no-op if already applied). It is the
same patch the known-good build uses:

- only read a packet when `STATUS1.SW_DR` is set;
- report the tap button only when it changes, so motion packets do not release
  a held mouse button;
- submit the data-ready work once at init, to catch a DR line that was already
  high before the interrupt was installed;
- log the ASIC firmware ID at init.

Even with this patch, the earlier build sometimes needed one manual reset after
flashing before the pad reported movement. This build switches the pad's power
on and waits 50 ms before the driver probes it, which should remove that
power-up race, but this is not yet verified on hardware.

## Power

The pad and the status LED share the nice!nano VCC rail, which is switched by
P0.13. In the non-Cirque build that rail is off except during a ~100 ms LED
flash. Here it has to stay on:

- `status-pulse` switches the rail on at boot (`POST_KERNEL`, priority 60,
  before the input drivers at 90) and waits 50 ms for the pad to come out of
  power-on reset.
- The rail stays on while the keyboard is awake, including ZMK's idle state.
- It is switched off when ZMK goes to sleep (soft off after 15 minutes without
  key presses or touchpad movement, unless USB power is present). A key press
  wakes the keyboard through a reset, which powers the pad again.
- ZMK's own `EXT_POWER` node stays disabled, so no `&ext_power` binding or saved
  setting can turn the touchpad off.
- The LED still only shows brief status flashes. Between flashes its data line
  (P0.06) is driven low and the pixel is sent black; it is powered but dark.
  Flashes are still suppressed below 3.6 V battery.

**Idle current.** Awake idle current rises from tens of microamps to roughly
**1.5-4 mA**: the Pinnacle ASIC running without its sleep mode (about 1-3 mA)
plus the WS2812B-V6's quiescent current while powered and dark (about
0.5-1 mA). These are datasheet-range estimates, not measurements. As a rough
guide, 3 mA continuous drains a 110 mAh cell in about 36 hours of awake time,
or a 1000 mAh cell in about two weeks. Sleep current is unchanged from the
non-Cirque build because the rail is cut. If battery life matters more than
an always-ready pad, shorten `CONFIG_ZMK_IDLE_SLEEP_TIMEOUT` in
`config/endgame.conf`.

## Changes from `zmk-endgame-nice-nano`

- `config/boards/shields/endgame/endgame.overlay`: TWIM0 on D14/D16 with custom
  pinctrl, the `trackpad@2a` node, NFC pins released, input listener with the
  Raise-layer scroll mode; the P0.13 "LED VCC off" GPIO hog is removed.
- `config/endgame.conf`: `CONFIG_ZMK_POINTING=y`, `CONFIG_I2C=y`.
- `config/endgame.keymap`: mouse buttons on the Raise layer, replacing the
  duplicated `[` `]` and `Del` keys there.
- `status-pulse/src/status_pulse.c`: rail on at boot and kept on while awake;
  `endgame_status_cancel()` now only blanks the LED; the rail is cut only on
  ZMK sleep or device suspend.
- `patches/zephyr/input-pinnacle-cirque.patch`: new, applied by `build.sh`.
- `build.sh`/`build.yaml`: build both the keyboard and `settings_reset`; the
  build has its own staging directory.

## Building

`build.sh` needs a west workspace with ZMK pinned at the revision above, its
Zephyr and modules, and a `.west/config` whose manifest is `config/west.yml`
from this folder. It uses Homebrew's `arm-none-eabi-gcc`:

```bash
ENDGAME_ZMK_WORKSPACE=/path/to/workspace WEST_BIN=/path/to/venv/bin/west ./build.sh
```

The workspace's Zephyr checkout is patched in place by the step above. Build
logs go to `firmware/*.log`; they contain local paths and are ignored by git.

`build.yaml` lists the same two targets for a GitHub Actions ZMK user-config
build, but that workflow would also need to apply the Zephyr patch.

## Flashing

1. Double-tap reset on the nice!nano; a `NICENANO` drive appears.
2. If the board previously ran other firmware or has stale Bluetooth bonds,
   copy `settings-reset-nice-nano.uf2` first, then double-tap reset again.
3. Copy `endgame-nice-nano-cirque.uf2`.
4. Remove the old Endgame bond on the host and pair again.

If the pad does not move after flashing, press reset once. If it still does
not respond, check R1, the FFC orientation, and continuity from D14/D16/D10 to
pad pins 10/9/4.
