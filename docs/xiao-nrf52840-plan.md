# Endgame XIAO nRF52840 development branch

Status: initial electrical and mechanical design study, not a manufacturing release.

The `codex/xiao-nrf52840-battery` branch starts from Choc V1/V2 commit `503635fe0c49a6c597ee685ef395d58eaf00e6dd`. It targets the standard Seeed Studio XIAO nRF52840, a central battery opening, and a modified case. The previous wired RP2040 Gerbers remain the last completed manufacturing release; they do not implement this controller or battery opening.

## Agreed constraints

- Retain all 36 switch positions and Choc V1/V2 hot-swap support.
- Case changes around the battery and USB port are allowed.
- Use a thin rechargeable battery with nominal capacity **200 mAh or less**.
- Solder battery leads directly to labeled B+/B− PCB pads; no JST connector footprint.
- Preserve the existing perimeter and mounting points where possible; the new internal cutout is an intentional change.
- Use lower-cost agents for sourcing and bounded CAD analysis.

## Battery target

The preferred obtainable part is the **Adafruit 1317 protected 150 mAh, 3.7 V LiPo**, listed at **19.75 × 26.02 × 3.8 mm**. Reserve a preliminary **22 × 28 mm** battery envelope and **5 mm** of vertical space, plus a lead channel and strain relief. Those allowances are design assumptions, not a vendor maximum-size or lifetime expansion specification. The final pocket must not press against the pouch. The supplied JST-PH plug is not part of the design: the insulated battery leads terminate directly at clearly marked **B+ and B− solder pads** on the PCB. Preserve the pack's protection circuit.

The thinner alternative is a **LiPol LP302030, 130 mAh**, with protected-pack dimensions **20 × 31 × 3.0 ±0.3 mm**, but one-off Canadian sourcing is less attractive. See [battery sources, pricing, and charge specifications](xiao-battery-options.md).

Use the XIAO's low approximately **50 mA** charge setting. Verify the exact board revision's charger configuration and measure the charge current on the first assembled prototype. Connect the protected pack through the PCB's B+/B− pads to the XIAO battery pads, with a small physical disconnect switch in the positive lead. With this simple switched-battery circuit, the switch must be on for USB charging. Place the solder joints beside the pouch, where they cannot press into it, and provide wire strain relief. This is a proposed power circuit; none of it exists in the released RP2040 PCB.

## Controller and matrix

The current schematic and QMK configuration agree on a **4-row × 10-column COL2ROW matrix**, requiring 14 signals. The standard XIAO exposes 11 main GPIOs. It is not a pin-compatible substitute for the existing RP2040 Zero.

The preferred starting architecture preserves the existing matrix and uses **one 74HC595 serial output register for eight columns**, two direct GPIO columns, and four direct GPIO row inputs. This consumes **nine XIAO GPIOs**: three for the register plus two columns and four rows. Two pins remain available. Keeping row inputs on the MCU permits interrupt-based key wake-up. ZMK documents this output-expansion approach; its regular matrix driver accepts GPIO references per row/column.

Proposed allocation, subject to routing and firmware validation:

| XIAO pin | Proposed function |
| --- | --- |
| D0–D3 | row0–row3 inputs |
| D4–D5 | col8–col9 outputs |
| D8 | Register shift clock / SPI SCK |
| D9 | Register latch clock / SPI chip-select; not MISO |
| D10 | Register serial data / SPI MOSI |
| D6–D7 | Reserved until buzzer/power-control decisions are finalized |
| 3V3 / GND | Register supply, local decoupling, and logic reference |

The register's QA–QH outputs supply col0–col7. Do not use a 5 V-only HCT device in place of a suitable 3.3 V HC part. Final design must establish output-enable/reset behavior during power-up, avoid floating inputs, and verify both normal scanning and interrupt wake-up on the selected ZMK revision. The current RP2040 QMK/Vial firmware cannot be flashed onto the XIAO; a ZMK shield, matrix transform, and keymap are required.

## Mechanical integration to resolve

The existing controller is at PCB coordinates approximately (150, 72.871) mm. Keep the replacement near the center USB opening, checking the XIAO body, soldering access, USB connector height, antenna copper keepout, and battery-pad access from the actual module drawing. Do not place the battery or a metal holder over its antenna.

The existing bottom-side buzzer is at (150, 105) mm. The battery study must account for its pads and body, the two lower center grommet features, switch sockets and locating slots, and copper crossing the proposed cutout. An apparently blank area of solder mask is not necessarily free of copper or case material.

The first measured candidate is a **22 × 28 mm** opening centered at **PCB (150, 130) mm**, spanning **X=139–161, Y=116–144 mm**. It clears the conservative rotated 15 × 15 mm switch bodies by approximately **6.61 mm**, the existing buzzer courtyard by **3.05 mm**, and the lower center mount envelopes (assumed 5 mm radius) by approximately **5.17 mm**. No existing discrete track, via, or pad crosses this rectangle. The existing ground fill does, so the zone must be refilled after adding an actual Edge.Cuts opening.

The selected vertical arrangement places the battery through the PCB plane: its preliminary 5 mm envelope spans **Z=0.2–5.2 mm**, where the PCB occupies Z=0–1.6 mm. Removing the intersecting 3.6 mm of case material leaves **at least 1.50 mm of nominal roof** across the full rectangle. A raised top cover is therefore not required by this nominal arrangement. The pocket's final printing clearance and depth must be checked again because either can reduce that roof thickness. See the [measured fit study](validation/xiao-battery-fit.md) and [plan-view diagram](validation/xiao-battery-fit.svg). No cutout or case modification has yet been applied.

An opening alone does not retain or insulate a pouch cell. The modified case needs an insulating, load-bearing bottom tray beneath the PCB opening, a smooth pocket, lead strain relief, and access to the battery disconnect. Verify the tray's desk clearance and fasteners in the revised assembly. Keep the external footprint compact and avoid weakening the narrow ligaments that support the switch halves.

## Completion checks before generating new Gerbers

1. Select the battery pocket and verify its full pack, solder-pad, wire, and case envelope.
2. Implement and match the controller, register, and power circuit in the schematic and PCB.
3. Route around the cutout, refill zones, run ERC/DRC, and verify all 36 keys against the firmware matrix.
4. Build ZMK for the actual XIAO revision and test register initialization, every key, wake-up, battery sensing, and charge-current configuration.
5. Export updated case CAD and inspect controller, socket, battery, cable, and switch fit in assembly.
6. Generate a distinctly named wireless Gerber/drill ZIP and independently check the internal cutout and all V1/V2 drills. The existing wired ZIP must remain identifiable.

## Primary references

- [Seeed XIAO nRF52840 hardware and charging documentation](https://wiki.seeedstudio.com/XIAO_BLE/).
- [ZMK shift-register integration](https://zmk.dev/docs/hardware-integration/shift-registers).
- [ZMK matrix driver configuration](https://zmk.dev/docs/config/kscan).
- [TI SN74HC595 datasheet](https://www.ti.com/lit/ds/symlink/sn74hc595.pdf).
- [Adafruit 1317 dimensions and protection](https://www.adafruit.com/product/1317).
