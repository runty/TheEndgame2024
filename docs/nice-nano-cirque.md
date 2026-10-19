# nice!nano Choc V2 + Cirque touchpad

A third Endgame build: the wireless nice!nano Choc V2 board with a 40 mm **Cirque TM040040** touchpad between the thumb clusters. Each key half sits a further 8 mm outward, so the PCB is **239 mm** wide and the case **247 mm**. The case keeps the original Endgame height and sloped top. This is a **digital design**: DRC, ERC and CAD fit checks pass, but no board, case or firmware has been built or tested.

![Top view of the PCB](../001%20PCB/GERBER/NICE%20NANO%20CIRQUE/top-preview.png)

## Downloads

| File | Download |
| --- | --- |
| JLCPCB PCB + assembly | [Gerber ZIP](../001%20PCB/GERBER/NICE%20NANO%20CIRQUE/TheEndgame2024_NiceNanoCirque_239mm_JLCPCB.zip) · [BOM](../001%20PCB/GERBER/NICE%20NANO%20CIRQUE/TheEndgame2024_NiceNanoCirque_BOM.csv) · [CPL](../001%20PCB/GERBER/NICE%20NANO%20CIRQUE/TheEndgame2024_NiceNanoCirque_CPL.csv) · [top](../001%20PCB/GERBER/NICE%20NANO%20CIRQUE/top-preview.png) / [bottom](../001%20PCB/GERBER/NICE%20NANO%20CIRQUE/bottom-preview.png) previews |
| Case | [STL](../002%20CASE/NICE%20NANO%20CIRQUE/TheENDGAME2024_NICE_NANO_CIRQUE_CASE.stl) · [STEP](../002%20CASE/NICE%20NANO%20CIRQUE/TheENDGAME2024_NICE_NANO_CIRQUE_CASE.step) · [preview](../002%20CASE/NICE%20NANO%20CIRQUE/case-preview.png) |
| Case with clear LED logo (two filaments) | [Bambu 3MF](../002%20CASE/NICE%20NANO%20CIRQUE/LED%20LOGO/TheENDGAME2024_NICE_NANO_CIRQUE_CASE_LED_LOGO.3mf) · [folder](../002%20CASE/NICE%20NANO%20CIRQUE/LED%20LOGO/) |
| Touchpad carrier (C-ring) | [STL](../002%20CASE/NICE%20NANO%20CIRQUE/TheENDGAME2024_NICE_NANO_CIRQUE_PAD_CARRIER.stl) · [STEP](../002%20CASE/NICE%20NANO%20CIRQUE/TheENDGAME2024_NICE_NANO_CIRQUE_PAD_CARRIER.step) |
| Battery tray | [STL](../002%20CASE/NICE%20NANO%20CIRQUE/TheENDGAME2024_NICE_NANO_CIRQUE_BATTERY_TRAY.stl) · [STEP](../002%20CASE/NICE%20NANO%20CIRQUE/TheENDGAME2024_NICE_NANO_CIRQUE_BATTERY_TRAY.step) |
| Choc V2 switch plates | [3-D print](../001%20PCB/PLATE%20CHOC%20V2/NICE%20NANO%20CIRQUE/3D%20PRINT/) · [1.2 mm FR-4/metal](../001%20PCB/PLATE%20CHOC%20V2/NICE%20NANO%20CIRQUE/) · [preview](../001%20PCB/PLATE%20CHOC%20V2/NICE%20NANO%20CIRQUE/plate_preview.png) |
| Firmware | [UF2](../003%20FIRMWARE/zmk-endgame-nice-nano-cirque/firmware/endgame-nice-nano-cirque.uf2) · [settings reset](../003%20FIRMWARE/zmk-endgame-nice-nano-cirque/firmware/settings-reset-nice-nano.uf2) · [ZMK config, pins and power notes](../003%20FIRMWARE/zmk-endgame-nice-nano-cirque/) |
| KiCad project | [`001 PCB/KICAD/NICE NANO CIRQUE/`](../001%20PCB/KICAD/NICE%20NANO%20CIRQUE/) |

## Ordering the PCB

| Setting | Value |
| --- | --- |
| Size | **239.00 × 96.11 mm**, 2 layers, 1.6 mm FR-4, 1 oz |
| Solder mask / silkscreen | **Black / white** (the underside photo depends on it) |
| Order number | Choose JLCPCB's "remove order number" option (or specify a location on the underside), or it lands in the artwork |
| Assembly | **Both sides** (top: LED1; bottom: the 36 diodes, C1, C2, R1–R4, J2). Two-sided PCBA costs more; see below |
| Assembly files | Gerber ZIP (includes paste layers), BOM and CPL above; every assembled part carries its LCSC number |

| Ref | Part | LCSC | Side |
| --- | --- | --- | --- |
| LED1 | WS2812B-V6 5050 | C52917433 (extended) | Top |
| D5–D47 (36) | 1N4148W SOD-123 matrix diodes | C81598 | Bottom |
| C1, C2 | 100 nF 0603 | C14663 | Bottom |
| R1 | 330 Ω 0603 (LED data) | C23138 | Bottom |
| R2 | 100 kΩ 0603 (LED data pull-down) | C25803 | Bottom |
| R3, R4 | 4.7 kΩ 0603 (I2C pull-ups) | C23162 | Bottom |
| J2 | Jushuo AFC01-S12FCA-00, 12-pin 0.5 mm FFC, bottom contact, flip lock | C262661 (extended) | Bottom |

**Check JLCPCB's placement preview before confirming:**
- **LED1:** the body's pin-1 corner on the VCC pad, top-left at PCB (226.94, 136.61); DIN at (231.84, 136.61).
- **J2:** pad row on X 173.3, flip latch facing the battery-opening notch (−X), pin 1 at the high-Y end (125.75). Its footprint origin is the pad row, not the body centre, so expect JLCPCB to shift it about 2 mm.
- **Diodes:** cathode bands on the footprints' cathode marks, as on the nice!nano board.

LED1 is the only top-side part, and it makes the order two-sided assembly. Hand-soldering LED1 instead (a large 5050 part) keeps it one-sided and cheaper.

Hand-solder the 36 Choc hot-swap sockets, the nice!nano on short posts, the battery wires (J1) and the power switch SW38, as for the [nice!nano build](nice-nano-wireless.md). SW38 (C&K PCM12) now sits on the **underside, under the nice!nano at the back edge**, slider facing the edge but recessed 0.46 mm inside it so the board protects it; reach it through the case's USB opening with a fingernail or a toothpick. The case has no switch hole. The yellow key outlines in the previews are KiCad reference drawings, not silkscreen; they are not in the Gerbers.

## Board artwork

The underside carries a dithered black-and-white photo as white silkscreen on the black mask: 0.25 mm dots, mirrored so it reads correctly when the board is turned over. The top side keeps only the normal markings. The ink stays 0.4 mm from the edges and clear of the mounting-hole ring artwork, and the Gerber export removes it from every exposed pad. Source: [`art/silkscreen-photo.jpg`](../001%20PCB/KICAD/NICE%20NANO%20CIRQUE/art/silkscreen-photo.jpg); [preview as seen from below](../001%20PCB/GERBER/NICE%20NANO%20CIRQUE/photo-bottom-preview.png). KiCad's 3-D render does not show this artwork.

## Touchpad

**Part:** Cirque **TM040040-2024-303** (Pinnacle ASIC, curved ABS overlay 50-000090-00). It ships in **SPI** mode: remove resistor **R1** on the pad to switch it to I2C.

**Wiring:** a 12-pin, 0.5 mm-pitch FFC runs from the pad's vertical connector to J2 on the PCB underside. Pad pins 4 DR, 9 SCL, 10 SDA, 11 GND and 12 VDD (3.3 V) are used; the SPI and button pins are left open. The cable keeps each conductor's position along the row through its 90° bend, so **pad pin N arrives on J2 pin 13 − N**. J2 is wired that way: DR on 9, SCL on 4, SDA on 3, GND on 2, 3.3 V on 1.

| Signal | nice!nano | Notes |
| --- | --- | --- |
| SDA | D14 / P1.11 | 4.7 kΩ pull-up (R3) |
| SCL | D16 / P0.10 | 4.7 kΩ pull-up (R4); NFC pin |
| DR | D10 / P0.09 | NFC pin |
| VDD | VCC (switched) | shared with the LED; C2 at J2 |

**Fitting:**
- **Orientation:** the pad's connector faces **+X** (towards the right-hand keys), over the notch on the right of the battery opening.
- **Cable path:** the FFC drops straight down through the notch, bends 90° under the board and runs about 4.5 mm into J2's entry, which faces the notch. Insert it before the board goes into the case: J2's latch flips open downwards.
- **Cable:** 12 conductors, 0.5 mm pitch, 0.3 mm thick, about **15–20 mm** long (the path is roughly 15 mm including both insertions) with short (~4 mm) stiffeners. A longer standard cable leaves slack to fold into a 2.4 mm gap under the board. Contact side: J2 is bottom-contact, so it touches the conductors on the face that points +X while the cable hangs down. Cirque's drawing puts the pad connector's pin 1 on the outer (+X) side, which needs a **same-side (Type A)** cable. **Check the contact side on your pad's connector before ordering the cable**; if its contacts are on the inner side, use Type B.
- **Clamping:** the overlay flange sits under a ledge in the case's flat bezel. The printed C-ring stands on the PCB around the battery and presses the pad's PCB edge up into the bezel, outside its component area. The ring is open over the battery.

**Cross-section at the pad centre** (Z from the PCB bottom):

| Layer | Z (mm) |
| --- | --- |
| Battery envelope (lowered 0.5 mm into the tray) | −0.5 – 4.5 |
| Pad components (≤ 1.0 mm assumed) | 4.71 – 5.71 |
| Pad PCB | 5.71 – 6.45 |
| Curved overlay rim (1.5 mm high assumed) | 7.95 |

The case roof slopes 2° front to back. The bezel is a flat landing at the rim's height: a chamfered collar of up to about 0.8 mm rises at the front, and a countersink blends the rim into the higher roof at the back.

**Before the first power-up**, with the cable fitted, check continuity: pad VDD (its connector pin 12) to J2 pin 1, and pad GND (pin 11) to J2 pin 2. A reversed or wrong-type cable would put 3.3 V on the pad's SCK line.

**Still to measure on a real pad:** the overlay height (flange bottom to rim top) and the tallest back-side component other than the connector. The case assumes 1.5 mm and 1.0 mm, leaving 0.21 mm above the battery. If either is larger, adjust `OVERLAY_HEIGHT`, `FLANGE_T` or `PAD_COMPONENTS` in [`tools/build_nice_nano_cirque_case.py`](../tools/build_nice_nano_cirque_case.py) and lower the battery further (up to about 1 mm in total).

## Case and fit

| Feature | Design |
| --- | --- |
| Width | Original case split at X = ±7 mm (inside the solid waist) and each half moved 10 mm; every key opening matches the original's shape. |
| Keycaps | Each nominal 17.5 × 16.5 mm cap keeps at least the clearance the original case gives it on the original PCB (0.704 mm minimum). Switch bodies clear by 1.6 mm. |
| Pad margin | 4.0 mm from the 46.13 mm overlay flange to the nearest keycap. |
| Status LED | Moved to the right thumb gap, midway between SW27 and SW37 on the line through their centres (case X 79.4, Y 1.7). Its capacitor and resistors are on the PCB underside, so the case pocket is just the 5 × 5 mm LED plus 0.5 mm, open to Z 3.55. |
| LED logo | The clear-logo version is 10 mm wide here. A 1 mm wall is kept around the heat-insert bore 7 mm away. |
| Battery tray | Pack support plate at Z −1.5 … −0.5, with a cut-out for the FFC; same countersunk M3×6 ears and 1 mm feet as the nice!nano build. |
| Controller, USB, J1 | Same positions and pockets as the nice!nano case. |
| Power switch | SW38 on the PCB underside at the back edge, slider recessed 0.46 mm inside the PCB edge (case X 0.1–1.4 mm) and reached through the 15 mm USB opening, which already runs below the board. No front switch channel. |

See the [geometry report](validation/nice-nano-cirque-case/geometry.json) for per-key clearances and the pad-stack checks. The [switch plates](../001%20PCB/PLATE%20CHOC%20V2/NICE%20NANO%20CIRQUE/) were regenerated for this case: zero case intersection and at least 0.3 mm clearance.

## Power and battery life

The pad runs from the nice!nano's switched VCC, the only 3.3 V pin, shared with the LED. The firmware keeps that rail on while the keyboard is awake and switches it off in sleep. Estimated awake idle current is **1.5–4 mA**, so a ≤200 mAh 401730 pack lasts roughly two to five days of awake time; sleep current is unchanged. These are datasheet estimates. See the [firmware notes](../003%20FIRMWARE/zmk-endgame-nice-nano-cirque/README.md#power).

## Validation

- **Independent pre-order review:** netlist and pinouts, J2's pin order and footprint (checked against LCSC's model of C262661), fabrication rules and case fit. Fixes from it: J2's pin order reversed for the cable, J2 moved 3.7 mm from the notch for the cable's bend, J2 footprint corrected (fitting nails at ±4.45 mm, 5.75 mm body), notch widened to 4.3 mm, copper kept 0.2 mm from edges and 0.25 mm from holes, the case's front pocket re-cut to the board's real outline (it had overlapped the board's front tabs by 0.48 mm), paste layers added, diodes added to assembly.
- **PCB:** KiCad 10.0.6 DRC has 0 errors, 0 unconnected items and 0 schematic-parity issues ([report](validation/nice-nano-cirque-pcb/drc.json)); ERC is clean ([report](validation/nice-nano-cirque-pcb/erc.json)). The remaining warnings are all silkscreen: the underside photo overlapping pads, holes and footprint outlines.
- **Case:** valid single solids with watertight STLs. The board outline (grown by 0.3 mm) clears the case everywhere. The case, tray and carrier don't overlap each other or the proxies for the battery, pad, overlay, connector, nice!nano, USB, LED and power switch.
- **Firmware:** both UF2s build at the pinned ZMK revision.
- **Not tested:** physical fit, the FFC path and cable type, touchpad behaviour, JLCPCB assembly and battery life.

## Regenerating

```sh
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$KPY tools/widen_nice_nano_pcb.py --input "001 PCB/KICAD/NICE NANO WIRELESS/TheEndgame2024_NiceNano.kicad_pcb" \
    --output /tmp/cirque_widened.kicad_pcb --shift 8 --input-bounds 38.5 261.5
python3 tools/build_nice_nano_cirque_sch.py
$KC sch export netlist --format kicadxml -o /tmp/cirque.net "001 PCB/KICAD/NICE NANO CIRQUE/TheEndgame2024_NiceNanoCirque.kicad_sch"
$KPY tools/build_nice_nano_cirque_pcb.py place --input /tmp/cirque_widened.kicad_pcb --netlist /tmp/cirque.net --output /tmp/cirque_placed.kicad_pcb
$KPY tools/build_nice_nano_cirque_pcb.py dump --input /tmp/cirque_placed.kicad_pcb --obstacles /tmp/obstacles.json
python3 tools/route_nice_nano_cirque.py --obstacles /tmp/obstacles.json --output /tmp/routes.json   # NumPy, SciPy, Shapely, Matplotlib
$KPY tools/build_nice_nano_cirque_pcb.py apply --input /tmp/cirque_placed.kicad_pcb --routes /tmp/routes.json \
    --output "001 PCB/KICAD/NICE NANO CIRQUE/TheEndgame2024_NiceNanoCirque.kicad_pcb"
$KPY tools/build_nice_nano_cirque_pcb.py fill --input "001 PCB/KICAD/NICE NANO CIRQUE/TheEndgame2024_NiceNanoCirque.kicad_pcb"
python3 tools/add_cirque_photo_silkscreen.py --board "001 PCB/KICAD/NICE NANO CIRQUE/TheEndgame2024_NiceNanoCirque.kicad_pcb" \
    --photo "001 PCB/KICAD/NICE NANO CIRQUE/art/silkscreen-photo.jpg"   # Pillow, NumPy, SciPy
python3 tools/export_jlcpcb.py --board "001 PCB/KICAD/NICE NANO CIRQUE/TheEndgame2024_NiceNanoCirque.kicad_pcb" \
    --output /tmp/cirque-gerbers --archive-name TheEndgame2024_NiceNanoCirque_239mm_JLCPCB.zip --paste
python3 tools/export_jlcpcb_assembly.py --board "001 PCB/KICAD/NICE NANO CIRQUE/TheEndgame2024_NiceNanoCirque.kicad_pcb" \
    --output "001 PCB/GERBER/NICE NANO CIRQUE" --name TheEndgame2024_NiceNanoCirque
python3 tools/build_nice_nano_cirque_case.py          # OCP, trimesh, NumPy, Matplotlib
python3 tools/build_nice_nano_led_logo.py --variant cirque
```

The switch plates use the commands in [the nice!nano case notes](nice-nano-case.md#choc-v2-switch-plates), with the Cirque board and case. [`tools/sketch_nice_nano_cirque.py`](../tools/sketch_nice_nano_cirque.py) draws the [layout sketch](../002%20CASE/NICE%20NANO%20CIRQUE/cirque-layout-preview.png) used to plan this variant.
