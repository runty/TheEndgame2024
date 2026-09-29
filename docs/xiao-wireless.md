# Endgame XIAO wireless prototype handoff

This branch contains a completed **digital wireless prototype** for the Endgame using the standard Seeed XIAO nRF52840 and a protected central LiPo cell. The schematic/ERC, routed PCB/KiCad 10 DRC, case and battery-tray CAD, ZMK firmware build, and Gerber/drill export are complete. The fabrication package was checked independently, but it has not been uploaded to the JLCPCB portal or previewed there. No physical wireless PCB/case assembly, battery charging, RF performance, or USB/cable fit has been tested. The older wired RP2040 Gerber ZIP is not for this design.

The original 36 Choc switch positions, diode circuits, 4-row × 10-column COL2ROW matrix, and Choc V1/V2 hot-swap compatibility are retained. The buzzer was removed from the wireless revision. The wired RP2040 design and its existing manufacturing files remain independent.

## Prototype status

| Area | Current state | Handoff |
| --- | --- | --- |
| Electrical design | Schematic/ERC and routed board/KiCad 10 DRC are complete. The Gerber/drill package is independently validated; JLCPCB upload and portal preview have not been performed. | [Electrical design notes](xiao-electrical.md), [schematic](../001%20PCB/KICAD/XIAO%20WIRELESS/TheEndgame2024_XIAO.kicad_sch), [PCB layout](../001%20PCB/KICAD/XIAO%20WIRELESS/TheEndgame2024_XIAO.kicad_pcb), [wireless Gerber ZIP](../001%20PCB/GERBER/XIAO%20WIRELESS/TheEndgame2024_XIAO_Choc_V1_V2_JLCPCB.zip), [Gerber front preview](../001%20PCB/GERBER/XIAO%20WIRELESS/front-preview.png), [KiCad DRC report](validation/xiao-pcb/drc.json), [geometry report](validation/xiao-pcb/geometry.json), [Gerber inspection report](validation/xiao-pcb/gerbers.json) |
| Case and tray | Printable CAD files and mesh checks are complete, but physical fit against the board, cell, and USB cable is untested. | [Case prototype notes](xiao-case.md), [case STL](../002%20CASE/XIAO%20WIRELESS/TheENDGAME2024_XIAO_CASE.stl), [battery tray STL](../002%20CASE/XIAO%20WIRELESS/TheENDGAME2024_XIAO_BATTERY_TRAY.stl), [case STEP](../002%20CASE/XIAO%20WIRELESS/TheENDGAME2024_XIAO_CASE.step), [battery tray STEP](../002%20CASE/XIAO%20WIRELESS/TheENDGAME2024_XIAO_BATTERY_TRAY.step) |
| Firmware | Pinned ZMK config and locally built UF2 are ready for prototype bring-up; firmware behavior and matrix wake need assembled-board tests. | [Firmware notes](xiao-firmware.md), [build configuration](../003%20FIRMWARE/zmk-endgame/), [prototype UF2](../003%20FIRMWARE/zmk-endgame/firmware/endgame-xiao-nrf52840.uf2) |
| Assembly and battery | Direct-wire 150 mAh protected cell, switched battery path, and XIAO underside jumpers are specified. Charge current, sensing, battery safety, RF behavior, USB/cable access, and assembled mechanical fit have not been tested. | [Battery options](xiao-battery-options.md), [electrical assembly details](xiao-electrical.md#battery-and-charging) |

KiCad 10 ERC and DRC both report zero violations; the DRC report also records zero unconnected items and zero schematic-parity violations. The board uses a 2-layer, 1.6 mm FR-4 stackup. The final Gerber outline measures 219.000032 × 96.106071 mm, so order dimensions are **219 × 96.11 mm**. The internal battery opening is 22 × 28 mm and the XIAO underside-pad access opening is 3.7 × 4.15 mm. The [geometry report](validation/xiao-pcb/geometry.json) records these openings and retained switch/diode counts. The [Gerber report](validation/xiao-pcb/gerbers.json) records seven graphic layers, 215 plated drills, 148 non-plated holes/slots, all drill positions registered to the PCB within 0.002 mm, and three closed outline contours. The archive SHA-256 is `21442495bcce91add5d830b43f0e740c89e97c63afcf3fc9f35ef46fb2c5e6da`. Physical hardware build, charge current, RF performance, and USB/cable fit remain untested.

## Wireless-specific component BOM

This is the prototype BOM for a complete 36-key assembly. Existing keyboard parts are listed because the wireless PCB retains their positions and circuitry.

| Qty | Part | Notes |
| ---: | --- | --- |
| 1 | Standard Seeed XIAO nRF52840 | Use the non-Plus, non-Sense module; D0–D3 are rows, D4–D5 direct columns, D8/D9/D10 drive the register. |
| 1 | SN74HC595, SOIC-16 | 3.3 V HC logic, not a 5 V-only HCT variant; QA–QH drive matrix columns 0–7. Tie OE to GND and SRCLR to 3V3. |
| 1 each | 100 nF and 1 µF, 0603 capacitors | Local 74HC595 bypass capacitors. |
| 3 | 100 kΩ, 0603 resistors | Pulldowns on shift clock, latch, and serial data. |
| 1 | PCM12SMTR SPDT slide switch | Used as the positive battery disconnect; third contact is unused. |
| 1 | Adafruit 1317 protected LiPo, 3.7 V, nominal 150 mAh | Use the protected cell. Remove/omit its JST-PH plug and solder the two leads directly to the PCB's labeled B+/B− pads. There is no JST battery connector in this design. |
| 2 | Short insulated jumper wires | Connect host-side PCB lands to the XIAO's underside BAT and GND pads. Route both around the **left side** of the antenna keepout through the access opening; they are hand-soldered wires, not PCB copper tracks. |
| 36 | Choc V1 or V2 switches | Original physical switch positions and hot-swap geometry are retained. |
| 36 | Choc hot-swap sockets | Existing hot-swap design; do not substitute a direct-solder-only footprint. |
| 36 | 1N4148W SOD-123 diodes | One diode per existing matrix switch circuit. |
| 6 | M3 D4.6 × 3 mm heat-set inserts and six M3 case screws | Four existing case mounts plus two new battery-tray mounts. Use two M3 × 6 mm 90° countersunk screws for the tray ears; use the original four case-mount screws for the remaining points. |
| 4 or more | Rubber feet or bumpons | Choose enough installed height to clear the tray-ear screw heads; case notes specify at least 1 mm projection below its support plane. |

There is **no buzzer** in the wireless BOM. Keep the cell's protection circuit; do not compress, puncture, or trap the pouch or its leads.

## Battery and jumper assembly

Solder the protected cell directly to B+ and B−, observing polarity, and use the switch in the positive lead. The supplied Adafruit connector is not used. If removing it, cut and insulate one lead before cutting the other so the live battery leads cannot short together. Secure the leads through the PCB strain-relief holes and route them through the case channel without pressure against the cell.

The slide switch must be **ON while charging over USB** so the XIAO's onboard charger remains connected to the cell. The intended XIAO charger setting is its low, approximately **50 mA** selection: leave P0.13 as an unpulled, high-impedance input. Confirm the exact XIAO board revision and measure charge current on the first assembled board.

Connect the PCB host lands to the module's underside VBAT and GND pads with two short insulated flywires through the access slot. Route them around the left of the antenna clearance; do not cross the antenna keepout or substitute a straight route through it. Secure and insulate the wires on the PCB underside before closing the case. See the [electrical routing dimensions](xiao-electrical.md#battery-and-charging) and [case wire-clearance notes](xiao-case.md#assembly-path-and-access).

## Prototype bring-up gates

Before calling this a working wireless keyboard, review the Gerber package in the fabricator's portal and physically verify switch fit, both XIAO jumpers, USB/cable access, tray and pack fit, and strain relief. On the assembled board, test all 36 keys and rollover, Bluetooth pairing and slot changes, battery reporting against a meter, the approximately 50 mA charge setting with the switch on, idle current, and wake from both ordinary idle and deep sleep. Record measured results before treating the design as a proven hardware build.
