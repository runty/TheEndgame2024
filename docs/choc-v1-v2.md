# Endgame Choc V1/V2 revision

This fork adds Kailh Choc V2 (PG1353) hot-swap support while retaining Choc V1 hot-swap support and the original Endgame case geometry. It targets the supplied **CPG135301D02** drawing. It does not change the key matrix or firmware.

## Mechanical changes

All 36 switch positions in both the SILKSCREEN and COPPER PCB variants receive:

- A **5.00 mm non-plated center hole**, replacing the 3.40 mm hole.
- A **1.50 × 2.00 mm non-plated relief slot**, oriented with the switch and located according to the manufacturer drawing.
- Both original **1.70 mm Choc V1 locating holes** retained at ±5.50 mm.
- The existing hot-swap socket pads and electrical pin positions retained.

The V2 relief slot overlaps an optional direct-solder pad in the upstream HSxSolder footprint. This revision replaces that auxiliary pad with a **0.60 mm routing land / 0.30 mm plated hole**, moves it 0.30 mm, and reconnects the traces. The original direct-solder option is no longer supported; **use Choc hot-swap sockets with either switch family**. The remaining auxiliary holes are part of the routing, not an alternative switch pattern.

The new `SW_choc_v1_v2_HS_1u` and `SW_choc_v1_v2_HS_1.5u` footprints are stored in the project library and assigned in both schematics. The upstream V1 footprints remain available for reference.

## Existing case and keycaps

The PCB perimeter, cutouts, four screw mounting holes, other mounting features, component locations, all switch centers/angles, and **1.6 mm board thickness** are preserved. Do not change the thickness when ordering a replacement PCB.

The included `002 CASE/TheENDGAME2024_CASE001.step` was registered to the PCB using its four mounting holes: case coordinates are `(PCB X - 150, 140 - PCB Y)`. A conservative 15 × 15 mm switch-body envelope from Z=1.6 to 8.0 mm at each switch position has zero intersection with the case. The minimum computed separation is approximately **1.60 mm**. This is a CAD clearance check, not a physical prototype test; it does not assess printing tolerances, switch retention, or the keycaps' moving envelope.

The original alpha spacing is approximately **18 × 17 mm**. Choc V2 uses an MX-style stem, but that does not make every MX keycap suitable for this spacing. Select caps with skirts and thumb-key dimensions that clear neighbouring keys and the original case. Choc V1 MBK caps do not fit the V2 stem. The old library's external V1/MBK 3D-model paths are not a V2 assembly model.

## Sources

- [Upstream Endgame](https://github.com/OldMan6955/TheEndgame2024), starting commit `b66038b`.
- [Kailh CPG135301D02 drawing supplied for this conversion](https://cdn.shopify.com/s/files/1/0657/6075/5954/files/SPEC-CPG135301D02_Kailh_Choc_V2_Low_Profile_Brown_Switch.pdf?v=1666690472), revision A, 2020-04-15. The PCB recommendation uses a relief slot; an older PG1353 drawing with a circular relief hole was not used for the final geometry.
- [JLCPCB KiCad Gerber/drill instructions](https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9).

The original CERN-OHL-S-2.0 license and upstream attribution continue to apply. Modified 2026-09-25 for the Choc V1/V2 fork.

## Source checks

Run `python3 tools/verify_choc_compatibility.py` to verify all switch holes and compare the board's mechanical interfaces with the recorded upstream commit. This check does not replace KiCad DRC. The final manufacturing export must use refilled copper zones and the unchanged 1.6 mm stackup.

## Manufacturing download and order settings

Use **[TheEndgame2024_Choc_V1_V2_JLCPCB.zip](../001%20PCB/GERBER/CHOC%20V1%20V2/TheEndgame2024_Choc_V1_V2_JLCPCB.zip)**. This is the updated SILKSCREEN variant. The older `SILKSCREEN GERBER` and `COPPER GERBER` folders are upstream V1-only archives and are not the output of this conversion.

The new ZIP contains seven RS-274X Gerber layers (front/back copper, front/back mask, front/back silkscreen, and outline), separate metric Excellon PTH and NPTH drill files, and a Gerber job file. Drill slots use G85. No assembly order or stencil is included.

| JLCPCB option | Setting |
| --- | --- |
| Material | FR-4 |
| Copper layers | 2 |
| Thickness | **1.6 mm** |
| Outer copper | 1 oz |
| Board size | Approximately 219 × 96.1 mm; use the outline in the ZIP |
| Solder mask / silkscreen | Your preference; preview colors are illustrative |
| Surface finish | HASL or ENIG as preferred |
| Assembly | Bare PCB; solder components and Choc sockets separately |

The slot tooling is 1.5 mm wide with 0.5 mm centerline travel, producing a 1.5 × 2.0 mm slot. Confirm that the manufacturer's preview recognises all 36 slots and 36 large center holes. A prototype of this revision has been built, and all 36 keys work with the RP2040-Zero and ZMK firmware. A [ZMK config with a sample keymap](../003%20FIRMWARE/zmk-endgame-rp2040-zero/) is included. Keycap clearance has not been checked on assembled hardware.

Build notes from the prototype:

- The RP2040-Zero's 5V and GND pads are 0.84 mm apart. A solder bridge between them leaves the controller unpowered; it then won't even enter its ROM bootloader. Check 5V–GND for a short before plugging in.
- Each column passes from the back copper to the front through a 0.3 mm plated hole beside its top-row switch. If a whole column is dead, beep GP-pin → column socket tab to find the break.

## Validation record

- KiCad **10.0.6**: zero errors, zero warnings, zero unconnected items for both variants, using the upstream rule settings. No DRC rules were relaxed or exclusions added. The silkscreen board also passes schematic parity.
- Project-local footprint tables resolve the upstream library configuration warnings.
- All 36 switch centers and rotations, the board outline/cutouts, thickness, and every non-switch footprint remain identical to upstream. Firmware is unchanged.
- 17 trace sections were rerouted and eight 0.60/0.30 mm vias were added. One upper bus segment uses 0.20 mm trace width; other rerouted segments retain 0.25 mm. The final routing was checked by KiCad; no Freerouting session was imported into the released board.
- Copper zones were refilled. The large PCB text diff is predominantly regenerated fill polygons; the source remains in the original KiCad 8 file format.
- Independent Gerbonara **1.6.3** parsing of the ZIP verifies seven graphic layers, **181 plated holes**, and **144 non-plated holes/slots**. All 36 sets of new/retained switch drills are registered against the source within the 0.002 mm check tolerance, including rotated slots.
- Top/bottom previews were rendered from the exported Gerbers and drill data and inspected. They show illustrative green solder mask and gold pads, not an order selection.
- The case check uses OpenCascade through `cadquery-ocp 8.0.1.0.0`; 36 conservative switch envelopes clear the supplied case model, minimum separation approximately 1.60 mm.

Machine-readable reports and source/archive hashes are in [validation](validation/). Optional reproducibility commands:

```sh
python3 tools/verify_choc_compatibility.py
# Requires cadquery-ocp:
python3 tools/check_case_fit.py --output docs/validation/case-fit.json
# Requires gerbonara:
python3 tools/verify_gerbers.py
# Requires kicad-cli; choose a new directory:
python3 tools/export_jlcpcb.py --output /tmp/endgame-export
```

The standalone PDF linked above is the dimensional source; it is not redistributed in this repository.

## Choc V2 switch plates

Optional plates hold Choc V2 switches more securely in the original case. They drop into the case's switch wells; the case and PCB are unchanged. The case rests directly on the PCB, so there is no room for a plate under it. Instead, each side has three pieces, one per well: the 15 alphas, the two inner thumbs, and the outer thumb. Left and right are exact mirror images. Clips latch at 2.2 mm above the PCB (the Choc V2 bottom-housing height), case Z 3.8.

Both versions are generated from the KiCad switch positions and the case STEP. A 3-D check against the unmodified case shows zero intersection. Kailh does not publish a Choc V2 plate cutout; the 14 mm cutouts come from the drawing's 13.95 ± 0.05 mm housing.

### 3-D printed plate (recommended, test-fitted)

Files: [`001 PCB/PLATE CHOC V2/3D PRINT/`](../001%20PCB/PLATE%20CHOC%20V2/3D%20PRINT/)

- 2.2 mm thick, filling the well from the PCB top to the switch flange, so it rests on the bare PCB at the correct height. All PCB components are on the back.
- A 16 mm pocket under each cutout leaves a 1.2 mm lip for the switch clips.
- 14.1 mm cutouts and 0.4 mm clearance to the case walls, allowing for FDM shrinkage.
- The STLs are oriented top face down and need no supports. Each side's STL holds its three pieces.

Print `endgame_choc_v2_print_plate_test_1key.stl` (the outer thumb piece) first. If a switch is too tight or too loose, regenerate with a different `--cutout`; adjust `--clearance` if the piece doesn't drop into the case well.

Suggested settings: PETG, 0.2 mm layers (matching the 1.2 mm lip and 2.2 mm body), solid infill, and elephant's-foot compensation. The top face prints first, so a squished first layer narrows the switch openings.

Assembly: screw the PCB into the case, drop the plates into the wells, then press the switches through the plate into the hot-swap sockets.

### 1.2 mm sheet plate (FR-4 or metal, untested)

Files: [`001 PCB/PLATE CHOC V2/`](../001%20PCB/PLATE%20CHOC%20V2/)

- 1.2 mm thick, case Z 2.6–3.8; it floats on the switch clips.
- 14.0 mm cutouts with 0.5 mm corner reliefs for a 1.0 mm router bit.
- 0.3 mm clearance to the case walls; the narrowest web is 1.65 mm.
- `*_JLCPCB.zip`: copper-free Gerbers. Order 1.2 mm FR-4. Each ZIP has three separate outlines, so JLCPCB may count it as multiple designs.
- `.dxf` for laser/CNC, `.step` in case coordinates, and `.stl`.

Assembly: clip the switches into the plate first, then press the plate and switches into the sockets through the case wells. A loose sheet plate dropped in first falls onto the PCB, below the clip height.

### Regenerating

```sh
# KiCad's bundled Python provides pcbnew:
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
$KPY tools/export_switches.py /tmp/switches.json
# Requires cadquery, shapely, ezdxf:
python3 tools/make_choc_v2_print_plate.py --switches /tmp/switches.json --output /tmp/print-plate
python3 tools/make_choc_v2_plate.py --switches /tmp/switches.json --output /tmp/plate
$KPY tools/export_plate_gerbers.py /tmp/plate
```

Each generator writes a JSON report with the case-intersection, clearance and mirror checks. `--case` and `export_switches.py --board/--keepouts` target other variants; see the [nice!nano plates](nice-nano-case.md#choc-v2-switch-plates). Regenerating these original-case plates with the current tools reproduces the committed outlines to within 0.001 mm².
