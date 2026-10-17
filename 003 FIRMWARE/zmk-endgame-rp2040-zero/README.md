# ZMK firmware — RP2040-Zero Choc V2 Endgame (wired)

ZMK config for the wired RP2040-Zero Choc V2 board. It ships with a **sample QWERTY keymap** (base, lower and raise layers) as a starting point; edit [`config/endgame.keymap`](config/endgame.keymap) for your own layout.

| | |
| --- | --- |
| Controller | Waveshare RP2040-Zero, ZMK board `rp2040_zero//zmk` (board definition in [`config/boards/waveshare`](config/boards/waveshare/rp2040_zero/)) |
| Shield | `endgame`: 4 rows × 10 columns, `col2row` |
| Columns | GP27, GP29, GP28, GP26, GP15, GP4, GP3, GP0, GP1, GP2 |
| Rows | GP14, GP13, GP12, GP11 |
| LED | Onboard WS2812 on GP16, as ZMK RGB underglow (off at start; toggle on the raise layer) |
| ZMK | pinned at `5b51501fead672c41b5cfb396f3dafe0894bf4e9` |

## Flashing

Hold BOOT while plugging in the RP2040-Zero (or press the raise-layer bottom-left key), then copy [`firmware/endgame-rp2040-zero.uf2`](firmware/endgame-rp2040-zero.uf2) to the `RPI-RP2` drive. [`endgame-rp2040-zero-settings-reset.uf2`](firmware/endgame-rp2040-zero-settings-reset.uf2) clears stored settings.

## Sample keymap

- **Base:** QWERTY; thumbs are Shift, Esc/Lower (hold), Enter, Space, Backspace/Raise (hold), Shift.
- **Lower:** numbers, shifted symbols, brackets and quotes; Ctrl, Tab, Delete and Alt on the thumbs.
- **Raise:** F1–F12, navigation, RGB and media controls; bootloader and reset on the outer thumbs.

The original QMK firmware's buzzer on GP10 is not supported by ZMK and stays inactive.

## Building

`build.sh` builds both UF2s into `firmware/`. It needs an initialized ZMK west workspace pinned at the revision above (`ENDGAME_ZMK_WORKSPACE`), `west` (`WEST_BIN`) and `arm-none-eabi-gcc` (`GNUARMEMB_TOOLCHAIN_PATH`, default `/opt/homebrew`). With a bare toolchain that lacks newlib, the script supplies a stand-in `nosys.specs` for the RP2040 boot stage. GitHub Actions users can instead build from `build.yaml` with the standard ZMK user-config workflow.
