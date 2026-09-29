# Endgame nice!nano v2 electrical revision

The editable project is [`TheEndgame2024_NiceNano.kicad_sch`](../001%20PCB/KICAD/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano.kicad_sch). It retains the original 36 Choc V1/V2 hot-swap switches and 36 matrix diodes, with four rows and ten columns in **COL2ROW** direction. All ten columns and four rows connect directly to nice!nano v2 GPIO; the XIAO and 74HC595 circuit are absent. `U2` is a nice!nano v2 mounted on short soldered pin posts with USB facing the top of the board. `SW38` remains the physical battery disconnect in its original location; `J1` is a direct-wire battery landing, without a JST connector.

The module pin functions below follow [Nice Keyboards' v2 pinout](https://nicekeyboards.com/docs/nice-nano/pinout-schematic/). The pin-post footprint uses the 24 standard Pro Micro side positions; its pad numbering and 2.54 mm pitch were cross-checked against the [open hardware nice!nano KiCad footprint](https://github.com/bstiq/nice-nano-kicad/blob/master/nice_nano.kicad_mod). The module's separate B+ and B− top solder pads are intentionally **not** populated with posts. [Nice Keyboards instructs](https://nicekeyboards.com/docs/nice-nano/getting-started/) builders to use RAW and GND as their equivalents when those rails are required through a keyboard PCB.

| Net | U2 PCB pad | nice!nano label / nRF pin |
| --- | ---: | --- |
| `col0` | 2 | D0 / P0.08 |
| `col1` | 5 | D2 / P0.17 |
| `col2` | 6 | D3 / P0.20 |
| `col3` | 7 | D4 / P0.22 |
| `col4` | 8 | D5 / P0.24 |
| `col5` | 20 | D21 / P0.31 |
| `col6` | 19 | D20 / P0.29 |
| `col7` | 18 | D19 / P0.02 |
| `col8` | 17 | D18 / P1.15 |
| `col9` | 16 | D15 / P1.13 |
| `row0` | 9 | D6 / P1.00 |
| `row1` | 10 | D7 / P0.11 |
| `row2` | 11 | D8 / P1.04 |
| `row3` | 12 | D9 / P1.06 |
| `LED_DATA` | 1 | D1 / P0.06, high-frequency GPIO |
| `VBAT_SW` | 24 | RAW |
| `VCC_SW` | 21 | VCC, software-switched 3.3 V output |
| `gnd` | 3, 4, 23 | GND |

U2 pads 13–15 (D10, D16, D14) and pad 22 (RST) are marked no-connect. The remaining exposed nRF and control pads on the underside of the module are not used. The original matrix connections are preserved: each switch connects a column to its diode, and each diode cathode is on a row. The netlist contains all 36 such switch and diode paths.

## Battery and LED

`J1.1` receives battery positive on `VBAT`; `J1.2` receives battery negative on `gnd`. `SW38.2` is the positive common and `SW38.1` feeds `VBAT_SW` to U2 RAW. `SW38.3` is unconnected. The slide switch must be on for USB charging of the attached cell. The nice!nano's own charger is the only charger in the design; its charge-boost jumper must remain open for the nominal 100 mA ordinary setting described by [Nice Keyboards](https://nicekeyboards.com/docs/nice-nano/). The user's generic 401730 battery pack has no identified datasheet. Its exact dimensions, protection circuitry, capacity, and allowed charge rate remain **unverified**. Physical and electrical pack verification is required before manufacturing or sustained charging.

`LED1` is one [Worldsemi WS2812B-V6](https://www.world-semi.com/downloads/datasheets/en/ws2812b-v6-1.0.pdf) in the 5050 four-pad package. This specific revision states a 3.3–5.3 V operating range; older WS2812B revisions are not assumed interchangeable. `U2.21` powers only LED1 VDD and its local 100 nF `C1`; LED1 VSS and C1 return to ground. `U2.1` (P0.06) drives LED1 DIN through 330 Ω `R1`. A 100 kΩ `R2` from DIN to ground holds the data input low when the switched VCC is disabled. LED1 DOUT is unconnected. On nice!nano **v2**, [the official pinout](https://nicekeyboards.com/docs/nice-nano/pinout-schematic/) states that P0.13 low cuts VCC off; the firmware must explicitly control that rail and keep DIN low between brief status flashes. The LED's behaviour near battery depletion needs prototype measurement; do not claim normal operation below its published 3.3 V minimum.

## Physical footprint and verification

The local `NanoWireless:NiceNano_v2_PinPosts` footprint has two rows of twelve 1.8 mm OD / 1.0 mm drill plated holes for individually soldered straight posts. Hold the module level on a jig while soldering, with at least 1.0 mm gap between the host PCB and the *lowest actual module projection*; insulate the underside of the host PCB from the battery. The mechanical planning stack is host top Z=1.6 mm, module low point at or above Z=2.6 mm, and a maximum nominal module envelope of 3.4 mm (the official 3.2 mm plus 0.2 mm allowance), giving a planned top no higher than Z=6.0 mm. The case cavity ceiling is planned at Z=6.5 mm, with the original sloped roof retained above it. Its central 16 mm span has at least 1.25 mm of roof; the edges follow the original key-opening contours. No shoulders project into the adjacent keycap footprints. These are controlled assembly targets, not measured fit of the purchased module. Row centers are 15.24 mm apart; pitch along each row is 2.54 mm. At nominal U2 placement `(150,80)` with USB facing negative Y, pad centers are X=142.38 and 157.62, and Y=66.03 through 93.97. Its F.Fab board outline is 17.78 × 30.48 mm, with a provisional USB protrusion to Y=62.22. This outline comes from the open hardware Pro Micro-compatible reference and the official pinout image, **not a vendor dimensioned nice!nano v2 mechanical drawing**; confirm the purchased module, USB shell, pin-post assembly height, and antenna clearance on a physical assembly. A conservative host-copper antenna keepout is X=144–156, Y=86–98, excluding the side pad holes. That keepout is an engineering allowance and not a vendor RF specification.

The symbol and footprints are in project-local `NanoWireless.kicad_sym` and `NanoWireless.pretty`, referenced by project-local library tables. The LED footprint uses the selected V6 datasheet's 1.5 × 1.0 mm lands and pin assignment. KiCad 10 ERC reports **0 errors and 0 warnings**. The exported XML netlist was checked for 36 switches, 36 matrix diodes, the 14 direct matrix connections, battery-switch path, and LED data and power paths. ERC and netlist checks do not establish board routing, 401730 pack safety, RF performance, USB access, or case and pin-post fit.

Short individual soldered posts are the specified assembly for this height-constrained case. Standard low-profile sockets have not been qualified: their above-board height refers to the module-board plane, while the module's overall thickness includes projections on both sides. Any socket assembly must independently meet the complete-envelope limits above. Verify the module low point, USB clearance, and installed height with a real nice!nano v2 and printed case before production.
