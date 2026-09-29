# Endgame nice!nano / 401730 prototype handoff

The nice!nano v2 revision retains all **36 Choc V1/V2 hot-swap keys**, uses a central **22 × 35 mm battery opening** for the user's generic 401730 pack, and adds one **WS2812B-V6 status pixel**. The battery wires solder directly to J1; SW38 remains at the preferred location. The original case's sloped exterior and overall height are retained, with deeper internal pockets and small local shoulders beside the controller. No uniformly thicker case is required.

The schematic, routed PCB, fabrication export, printable case/tray, and ZMK firmware are complete as a **digital prototype**. Physical assembly, charging, RF, and LED operation have not been tested. This archive has not been uploaded to or previewed by JLCPCB.

## Files

| Deliverable | File |
| --- | --- |
| JLCPCB fabrication archive | [TheEndgame2024_NiceNano_Choc_V1_V2_JLCPCB.zip](../001%20PCB/GERBER/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano_Choc_V1_V2_JLCPCB.zip) |
| Editable circuit and layout | [Schematic](../001%20PCB/KICAD/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano.kicad_sch), [PCB](../001%20PCB/KICAD/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano.kicad_pcb), project-local NanoWireless libraries |
| Printable case | [STL](../002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_CASE.stl), [STEP](../002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_CASE.step) |
| Removable battery tray | [STL](../002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_BATTERY_TRAY.stl), [STEP](../002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_BATTERY_TRAY.step) |
| Case inspection views | [Side profile against original](../002%20CASE/NICE%20NANO%20WIRELESS/case-side-profile.png), [case and tray](../002%20CASE/NICE%20NANO%20WIRELESS/case-and-tray-preview.png) |
| Prototype nice!nano v2 firmware | [UF2](../003%20FIRMWARE/zmk-endgame-nice-nano/firmware/endgame-nice-nano-v2.uf2), [source and build script](../003%20FIRMWARE/zmk-endgame-nice-nano/) |
| Manufacturing previews | [Front](../001%20PCB/GERBER/NICE%20NANO%20WIRELESS/front-preview.png), [back](../001%20PCB/GERBER/NICE%20NANO%20WIRELESS/back-preview.png) |

Order the PCB as **2 layers, 1.6 mm FR-4**, **219 × 96.11 mm**. The ZIP contains one board: seven graphic layers, separate plated and non-plated Excellon drills, and a Gerber job file. The centre battery opening is a routed internal contour. Upload the ZIP intact; inspect the outer shape, battery opening, and holes in the manufacturer's preview before ordering. The older wired RP2040 and XIAO archives are different designs.

## Validation

KiCad **10.0.6** reports **zero ERC violations, zero DRC violations, zero unconnected items, and zero schematic-parity issues**, under the inherited rule settings recorded in the reports. The manufacturing export uses the [JLCPCB KiCad guide](https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9): RS-274X layers with a shared absolute origin, separate drill types, and silkscreen clipped against solder-mask openings.

- [Source geometry/netlist report](validation/nice-nano-pcb/geometry.json): all 36 switches and diodes retain their original positions, rotations, footprints, pad geometry, and nets; the exterior profile matches the XIAO baseline; 183 terminals match the schematic XML.
- [Independent Gerber report](validation/nice-nano-pcb/gerbers.json): Gerbonara 1.6.3 parses all seven graphic layers and **218 plated + 148 non-plated holes/slots**, registered to source within 0.002 mm. Both contours are closed. Measured exterior: 219.000032 × 96.106071 mm.
- [DRC](validation/nice-nano-pcb/drc.json), [ERC](validation/nice-nano-schematic/erc.json), and [schematic PDF](validation/nice-nano-schematic/schematic.pdf).
- [Case report](validation/nice-nano-case/geometry.json): valid single-solid STEP parts and watertight STL meshes; the case's maximum height matches the original. All 36 conservative switch-body envelopes clear it, with a 0.5385 mm minimum gap. Actual keycap profiles and travel remain untested.
- [Firmware build log](../003%20FIRMWARE/zmk-endgame-nice-nano/firmware/build.log): pinned ZMK commit `5b51501fead672c41b5cfb396f3dafe0894bf4e9`, nice!nano v2. The original keymap is retained; the V6 encoder's host test verifies 258 frames. Hardware pulse timing still needs measurement.

The final PCB is authoritative. `tools/build_nice_nano_pcb.py` creates only a scratch placement with retained routes, and deliberately refuses to overwrite the finished PCB. `tools/build_nice_nano_case.py` regenerates and verifies the case outputs.

## Parts and assembly

| Qty | Part | Assembly note |
| ---: | --- | --- |
| 1 | nice!nano **v2** | USB faces the top edge; mount on short individually soldered posts with a height-setting jig. |
| 24 | Straight solder posts | Complete module, including USB shell and underside projections, must fit within Z=2.6…6.0 mm, relative to PCB bottom Z=0. Standard sockets have not been qualified. |
| 1 | Generic 401730 single-cell LiPo | User-supplied pack, nominal target ≤200 mAh. Full taped-pack size and allowed charge rate remain unverified. Direct-wire J1: pad 1 B+, pad 2 B−; retain strain relief. |
| 1 | PCM12SMTR slide switch | SW38; must be on to connect the battery to the nice!nano for charging. |
| 1 | **Worldsemi WS2812B-V6**, 5050 four-pad | LED1, top side, with pin 1 aligned to the PCB marker. Select this 3.3 V-capable revision. |
| 1 | 100 nF ceramic capacitor, 0603 | C1, ≥6.3 V rating; local LED supply bypass. |
| 1 each | 330 Ω and 100 kΩ resistors, 0603 | R1 series DIN resistor; R2 DIN pulldown. |
| 36 each | Choc V1/V2 switches, Choc hot-swap sockets, 1N4148W SOD-123 diodes | Retained key field. |
| 6 | M3 D4.6 × 3 mm heat-set inserts | Four original case mounts plus two tray mounts. |
| 2 | M3 × 6 mm, 90° countersunk tray screws | Recessed tray-ear heads; retain the four original outer case screws. |
| 4 or more | Feet/bumpons | Installed projection ≥1 mm below the original case support plane, to clear tray and screw heads. |

The insulating tray and internal battery recess use an **18.5 × 33 × 5 mm pack proxy**, not a measured maximum for the user's pack. Measure the complete pack and lead exit before printing/ordering. Mount the nice!nano level, keep its lowest underside projection at least 1 mm above the host PCB top, and measure the entire installed module envelope before closing the case. The [case notes](nice-nano-case.md) detail the assembly datum, recesses, USB access, fasteners, and fit assumptions.

Leave the nice!nano charge-boost jumper open for its ordinary nominal **100 mA** charging setting, and verify suitability for the actual cell. There is no external charger or matrix-expander chip. The pixel uses nice!nano v2 switched VCC and P0.06 through R1; firmware keeps its power off between events. The shipped keymap has no LED bindings. The compiled test behavior/API is ready for later status meanings; see [firmware notes](nice-nano-firmware.md). Electrical pin mapping and component orientation are in the [electrical notes](nice-nano-electrical.md).

Before treating this as proven hardware, verify controller/USB/pack fit, keycap travel, all 36 keys, BLE and USB, idle/sleep wake, charging current, and LED DIN/VCC behavior on the first assembly. This is the remaining prototype validation, not work established by CAD or compilation.

## Checksums

Gerber ZIP SHA-256: `38e40b6a6d573aae45d99548bf262564769d062702ccbc1766b2d89740687457`

PCB source SHA-256: `1d4d96c9efb6e6973a54d4c306bff2627ea1e06086c7c1779a54965a278054cf`

UF2 SHA-256: `dd09dd839af2fcc30e750b2b8cfd9ea6b40a9c6e78241b1ceba5eac6654ca5ae`

The [artifact manifest](validation/nice-nano-artifacts.json) records all source/output checksums and the baseline revision.
