# Endgame XIAO nRF52840 electrical revision

This is the editable electrical design for `001 PCB/KICAD/XIAO WIRELESS/TheEndgame2024_XIAO.kicad_sch`. It targets the **standard**, 14-side-pad Seeed XIAO nRF52840, not the Plus or Sense variant. The separate wireless project preserves the 36 existing Choc V1/V2 switch and diode circuits, their UUIDs, and the 4-row × 10-column COL2ROW matrix. The wired RP2040 project remains independent.

## Controller and register

| Host part | Pin(s) | Net and purpose |
| --- | --- | --- |
| U2 XIAO | 1–4 (D0–D3) | `row0`–`row3`, four direct row inputs |
| U2 XIAO | 5–6 (D4–D5) | `col8`–`col9`, direct outputs |
| U2 XIAO | 7–8 (D6–D7) | Unused and marked no-connect |
| U2 XIAO | 9 (D8) | `shift_clk`, U3 pin 11 SRCLK |
| U2 XIAO | 10 (D9) | `latch`, U3 pin 12 RCLK; D9 is the XIAO's MISO-capable pin, but is used as GPIO here |
| U2 XIAO | 11 (D10) | `ser_data`, U3 pin 14 SER |
| U2 XIAO | 12 / 13 | `3V3` output / `gnd` |
| U2 XIAO | 14 VBUS | Unused; USB-C on the module supplies it |
| U2 XIAO | 19 / 20 | `VBAT_SW` / `gnd`, host solder lands for flywires to the module's underside VBAT/GND pads |
| U3 SN74HC595 | 15, 1–7 (QA–QH) | `col0`–`col7` in order |
| U3 SN74HC595 | 13 / 10 | OE held low on `gnd`; SRCLR held high on `3V3` |
| U3 SN74HC595 | 16 / 8 | `3V3` / `gnd`; C1 100 nF and C2 1 µF local bypass |
| U3 SN74HC595 | 9 | QH' unused and marked no-connect |

R1, R2, and R3 are 100 kΩ pulldowns on `shift_clk`, `latch`, and `ser_data`, respectively. They hold the shift-register inputs low while the controller resets. OE is tied low as agreed, so the 595 output register can still contain an undefined value at initial power-up; firmware must shift eight zero bits and latch them before matrix scanning. Firmware also needs to verify row interrupt wake with the selected ZMK driver. Use a 3.3 V compatible **HC** register, such as SN74HC595 in SOIC-16; a 5 V-only HCT variant is inappropriate.

The original buzzer and `Sound` net are deliberately absent. The original polarized buzzer was wired directly to RP2040 GPIO and ground; this revision does not assume the XIAO GPIO can safely drive that acoustic load, and leaving it off saves battery energy. The original SW37 remains the last matrix key. **SW38** is the new battery switch.

## Battery and charging

J1 is the direct-wire protected LiPo landing, with 2.2 mm copper pads and 1.0 mm plated holes at 4.0 mm pitch. Two separate 1.0 mm non-plated holes 3 mm downstream provide lead strain relief. The preferred protected Adafruit 1317 pack is nominally 150 mAh / 3.7 V. Solder its positive lead to J1 pad 1 (`VBAT`, marked B+) and negative lead to J1 pad 2 (`gnd`, marked B−). Do not place solder joints or wire loops where they can press into the pouch.

SW38 is a PCM12-type SPDT slide switch used as an SPST battery disconnect: common pad 2 receives `VBAT`, throw pad 1 carries `VBAT_SW`, and throw pad 3 is unconnected. From U2 host lands 19 and 20, solder **short insulated flying leads** through the access window to the actual underside VBAT and GND pads on the XIAO. Host footprint pads 19/20 are accessible wire lands at board (146,89)/(149,89) when U2 is placed at (150,74); they are *not* in physical contact with the XIAO until those two bridge wires are installed. Verify polarity and continuity before connecting the pack.

Route the two underside jumpers from host lands (146,89) and (149,89) **around the left side of the antenna clearance**. A provisional path is from the lands to an insulated wire corridor near X141–142, Y87, then toward Y76, then into the access window at X143.7–147.4, Y70.7–74.85. Do not take the short straight path through the host antenna exclusion X143–157, Y78.5–85.2. Keep the conductors separate, pre-tin them, solder to the exposed module pads through the aperture, and secure the flat runs to the PCB underside with polyimide tape or a case feature. Check the printed case for wire clearance and strain relief. This is an assembly routing guide; the wires are not PCB copper tracks.

With this positive-lead disconnect, the switch must be **on** to charge the battery by USB. The XIAO's onboard charger remains the only charger in the design. Seeed's current instructions describe approximately 50 mA charging when P0.13 is high-impedance; software must not drive P0.13 low, which selects approximately 100 mA. Measure charge current and verify the exact purchased board revision during prototype bring-up.

## Module footprint and assembly

The local U2 footprint is centered on the standard module's 17.8 × 21.0 mm board. USB-C faces negative PCB Y; at nominal board placement (150,74), the module is X141.1–158.9 and Y63.5–84.5. Its fourteen 2.54 mm-pitch side pads reproduce Seeed's January 2026 `XIAO-nRF52840-SMD` host footprint centers and 2.75 × 2.0 mm solder lands. It intentionally omits hidden underside host pads 15–18 and 21–22. An Edge.Cuts access opening, local X −6.3 to −2.6 and Y −3.3 to +0.85, exposes the two underside battery contacts after the module is mounted. Check that the fabricator routes this enclosed opening and that the remaining castellated joints can be inspected and reworked.

Seeed's August 2026 v1.2 KiCad board locates the antenna chip close to the far end, opposite USB: about 1.1 mm in from that edge and 1.8 mm left of board center. At the nominal host placement, that is approximately (148.2,83.4). The host board should have no copper fill, traces, or vias under a conservative antenna region X143–157, Y78.5–85.2 on both copper layers, while side castellated pads and their outward escapes remain available. This rectangle is a design margin derived from the module drawing; Seeed does not specify it as an RF clearance dimension. Keep the battery pouch and metal parts away from the antenna. Confirm RF performance on the assembled prototype.

## Digital validation and sources

The digital electrical prototype is complete. The KiCad 10.0.6 schematic ERC reports **0 errors and 0 warnings**. The routed PCB passes full KiCad 10 DRC with **0 violations, 0 unconnected items, and 0 schematic-parity violations**. The exported XML netlist was checked for all 36 switches, all 36 diodes, all 14 matrix nets, and the allocation above. See the [DRC report](validation/xiao-pcb/drc.json) and [geometry/parity report](validation/xiao-pcb/geometry.json).

The board is designed for **2 layers, 1.6 mm FR-4**. The exported outline measures **219.000032 × 96.106071 mm**, giving order dimensions of **219 × 96.11 mm**. The internal openings are **22 × 28 mm** for the battery and **3.7 × 4.15 mm** for access to the XIAO underside battery pads. The [wireless Gerber/drill ZIP](../001%20PCB/GERBER/XIAO%20WIRELESS/TheEndgame2024_XIAO_Choc_V1_V2_JLCPCB.zip) has been independently validated: seven graphic layers, 215 plated drills, 148 non-plated holes/slots, all drill positions match the source within 0.002 mm, and three closed outline contours. Its SHA-256 is `21442495bcce91add5d830b43f0e740c89e97c63afcf3fc9f35ef46fb2c5e6da`. The validation report is [gerbers.json](validation/xiao-pcb/gerbers.json). No JLCPCB upload or portal preview has been performed. Digital ERC/DRC and Gerber checks do not verify a physical assembly: charge current, battery sensing against a meter, RF range, USB/cable fit, wire clearance, and actual mechanical fit remain untested.

Primary references: [Seeed XIAO nRF52840 guide and charging behavior](https://wiki.seeedstudio.com/XIAO_BLE/), [Seeed XIAO KiCad footprint library](https://files.seeedstudio.com/wiki/XIAO-KiCad-Library/New_XIAO_Series_Footprints.zip), [Seeed underside pad drawing](https://files.seeedstudio.com/wiki/XIAO-BLE/Bottom-pad-positioning.zip), [Seeed v1.2 KiCad board](https://files.seeedstudio.com/wiki/XIAO-BLE/Res/260828_Seeed_Studio_XIAO_nRF52840_v1.2.zip), [TI SN74HC595 datasheet](https://www.ti.com/lit/ds/symlink/sn74hc595.pdf), and [Adafruit protected 150 mAh cell](https://www.adafruit.com/product/1317).
