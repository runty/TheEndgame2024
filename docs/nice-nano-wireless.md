# Endgame nice!nano / 401730 prototype handoff

The nice!nano v2 revision retains all **36 Choc V1/V2 hot-swap keys**, uses a central **22 × 35 mm battery opening** for the user's generic 401730 pack, and adds one **WS2812B-V6 status pixel**. The battery wires solder directly to J1; SW38 remains at the preferred location. The case is 4 mm wider to match the shifted keys, while retaining the original sloped profile and overall height, with deeper internal pockets. The controller hood and side shoulders were removed after a full-height cap-envelope check found interference with adjacent keycap envelopes.

The schematic, routed PCB, fabrication export, printable case/tray, and ZMK firmware are complete as a **digital prototype**. Physical assembly, charging, RF, and LED operation have not been tested. This archive has not been uploaded to or previewed by JLCPCB.

## Files

| Deliverable | File |
| --- | --- |
| JLCPCB fabrication archive | [TheEndgame2024_NiceNano_223mm_THT_JLCPCB.zip](../001%20PCB/GERBER/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano_223mm_THT_JLCPCB.zip) |
| Editable circuit and layout | [Schematic](../001%20PCB/KICAD/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano.kicad_sch), [PCB](../001%20PCB/KICAD/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano.kicad_pcb), project-local NanoWireless libraries |
| Printable case | [STL](../002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_CASE.stl), [STEP](../002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_CASE.step) |
| Removable battery tray | [STL](../002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_BATTERY_TRAY.stl), [STEP](../002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_BATTERY_TRAY.step) |
| Case inspection views | [Side profile against original](../002%20CASE/NICE%20NANO%20WIRELESS/case-side-profile.png), [case and tray](../002%20CASE/NICE%20NANO%20WIRELESS/case-and-tray-preview.png) |
| Prototype nice!nano v2 firmware | [UF2](../003%20FIRMWARE/zmk-endgame-nice-nano/firmware/endgame-nice-nano-v2.uf2), [source and build script](../003%20FIRMWARE/zmk-endgame-nice-nano/) |
| Manufacturing previews | [Front](../001%20PCB/GERBER/NICE%20NANO%20WIRELESS/front-preview.png), [back](../001%20PCB/GERBER/NICE%20NANO%20WIRELESS/back-preview.png) |

Order the PCB as **2 layers, 1 oz copper, 1.6 mm FR-4**, **223 × 96.11 mm**. The ZIP contains one board: seven graphic layers, separate plated and non-plated Excellon drills, and a Gerber job file. The centre battery opening is a routed internal contour. A short 0.127 mm matrix trace beside R2 is within the [JLCPCB 1 oz capability](https://jlcpcb.com/capabilities/pcb-capabilities) of 0.10 mm minimum width; select 1 oz copper for this export. Upload the ZIP intact; inspect the outer shape, battery opening, and holes in the manufacturer's preview before ordering. The older wired RP2040 and XIAO archives are different designs.

The nice!nano body and header rows, battery opening, and LED body share **PCB X=150.00 mm**, the left/right centreline of the board. Their front/back positions remain separate. The PCB is 4 mm wider, and each key half moves 2 mm outward: the outer left and right 1U keycap borders both measure **2.00 mm** using centred 17.5 × 16.5 mm caps. Choc's offset locating slot makes the drill artwork look asymmetric; the slot is not the key centre. See the [measured border comparison](validation/nice-nano-pcb/outer-key-symmetry.png).

## Validation

KiCad **10.0.6** reports **zero ERC violations, zero DRC violations, zero unconnected items, and zero schematic-parity issues**, under the rule settings recorded in the reports, including a 0.10 mm minimum track width for 1 oz manufacturing. The manufacturing export uses the [JLCPCB KiCad guide](https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9): RS-274X layers with a shared absolute origin, separate drill types, and silkscreen clipped against solder-mask openings.

- [Source geometry/netlist report](validation/nice-nano-pcb/geometry.json): all 36 switches and diodes move exactly 2 mm outward by half, retaining their rotations, footprints, relative pad geometry, and nets; the exterior profile is widened by 4 mm around the fixed centre section; 183 terminals match the schematic XML.
- [Independent Gerber report](validation/nice-nano-pcb/gerbers.json): Gerbonara 1.6.3 parses all seven graphic layers and **226 plated + 148 non-plated holes/slots**, registered to source within 0.002 mm. Both contours are closed. Measured exterior: 223.000032 × 96.106067 mm.
- [DRC](validation/nice-nano-pcb/drc.json), [ERC](validation/nice-nano-schematic/erc.json), and [schematic PDF](validation/nice-nano-schematic/schematic.pdf).
- [Case report](validation/nice-nano-case/geometry.json): valid single-solid STEP parts and watertight STL meshes; the case's maximum height matches the original. All 36 conservative switch-body envelopes clear it, with a 1.6 mm minimum gap. A nominal 17.5 × 16.5 mm CS envelope swept from PCB top through Z=20 clears all 36 locations, with a 0.70 mm minimum gap; this is a rectangular CAD envelope check, not physical print proof or a check of larger thumb caps. See the [CS clearance preview](validation/nice-nano-case/cs-clearance.png), [clearance data](validation/nice-nano-case/cs-clearance.json), and [case notes](nice-nano-case.md). Choc V2 needs MX-stem CS caps; the linked [Asymplex CS Choc page](https://www.asymplex.xyz/product/cs-chicago-stenographer-profile) describes Choc V1 stems.
- [Firmware build log](../003%20FIRMWARE/zmk-endgame-nice-nano/firmware/build.log): pinned ZMK commit `5b51501fead672c41b5cfb396f3dafe0894bf4e9`, nice!nano v2. The original keymap is retained; the V6 encoder's host test verifies 258 frames. Hardware pulse timing still needs measurement.

The [spacing report](validation/nice-nano-pcb/spacing.json) checks the widened perimeter, retained key borders, central alignment, and clearance between the inner keys and the controller.

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
| 1 each | 330 Ω and 100 kΩ resistors, ¼ W axial through-hole | R1 series DIN resistor; R2 DIN pulldown. Nominal body 6.3 × 2.5 mm, horizontal 10.16 mm lead pitch, 0.8 mm plated holes. |
| 36 each | Choc V1/V2 switches, Choc hot-swap sockets, 1N4148W SOD-123 diodes | Retained key field. |
| 6 | M3 D4.6 × 3 mm heat-set inserts | Four original case mounts plus two tray mounts. |
| 2 | M3 × 6 mm, 90° countersunk tray screws | Recessed tray-ear heads; retain the four original outer case screws. |
| 4 or more | Feet/bumpons | Installed projection ≥1 mm below the original case support plane, to clear tray and screw heads. |

The insulating tray and internal battery recess use an **18.5 × 33 × 5 mm pack proxy**, not a measured maximum for the user's pack. Measure the complete pack and lead exit before printing/ordering. Mount the nice!nano level, keep its lowest underside projection at least 1 mm above the host PCB top, and measure the entire installed module envelope before closing the case. The [case notes](nice-nano-case.md) detail the assembly datum, recesses, USB access, fasteners, and fit assumptions.

Install R1 and R2 lying flat on the top side, with bodies no larger than 6.5 mm long × 2.5 mm diameter and no more than 0.2 mm above the PCB. Trim their soldered leads to at most 0.8 mm below the PCB underside. The revised case has internal pockets for their bodies and leads and retains its original exterior height. C1 remains a 0603 capacitor.

Leave the nice!nano charge-boost jumper open for its ordinary nominal **100 mA** charging setting, and verify suitability for the actual cell. There is no external charger or matrix-expander chip. The pixel uses nice!nano v2 switched VCC and P0.06 through R1; firmware keeps its power off between events. The shipped keymap has no LED bindings. An adapted zmk-rgbled-widget supplies automatic battery and Bluetooth/USB status flashes; see [firmware notes](nice-nano-firmware.md). Electrical pin mapping and component orientation are in the [electrical notes](nice-nano-electrical.md).

Before treating this as proven hardware, verify controller/USB/pack fit, keycap travel, all 36 keys, BLE and USB, idle/sleep wake, charging current, and LED DIN/VCC behavior on the first assembly. This is the remaining prototype validation, not work established by CAD or compilation.

## Checksums

Gerber ZIP SHA-256: `25c72831301f0641045401afa0cec08d2440b7e30919f5c405f65c11e87c0e7b`

PCB source SHA-256: `e5223e848921047923474be2aa05235f5087fc120c3f9a9fd1052ff5834562f4`

UF2 SHA-256: `f5662f0993dc97762743c5ac36d98072a58d338cdeca31086cd5abc1d131457a`

The [artifact manifest](validation/nice-nano-artifacts.json) records all source/output checksums and the baseline revision.
