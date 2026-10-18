#!/usr/bin/env python3
"""Create the nice!nano + Cirque KiCad project from the nice!nano project.

Copies the project, library tables, symbol and footprint libraries into
"001 PCB/KICAD/NICE NANO CIRQUE", then edits the schematic:
  * U2 pads 15/14/13 (D14/P1.11, D16/P0.10, D10/P0.09) become SDA/SCL/DR;
  * J2, a 12-pin 0.5 mm FFC connector for the Cirque TM040040 (pin 4 DR,
    9 SCL, 10 SDA, 11 GND, 12 VDD 3.3 V; the SPI and button pins are NC);
  * R3/R4 4.7 kOhm I2C pull-ups and C2 100 nF pad decoupling on VCC_SW;
  * R1/R2 move to 0603 SMD and every assembled part gets an LCSC number.
Run with any Python 3: python tools/build_nice_nano_cirque_sch.py
"""

import re
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "001 PCB/KICAD/NICE NANO WIRELESS"
TARGET = ROOT / "001 PCB/KICAD/NICE NANO CIRQUE"
OLD, NEW = "TheEndgame2024_NiceNano", "TheEndgame2024_NiceNanoCirque"
SHEET_UUID = "1a30e4b6-03d7-4c78-8024-353d1219867a"
FFC_FOOTPRINT = "NanoWireless:JUSHUO_AFC01-S12FCA-00_1x12-1MP_P0.50mm_Horizontal"

LCSC = {  # JLCPCB-assembled parts
    "R1": ("C23138", "Resistor_SMD:R_0603_1608Metric"),   # 330 Ohm 0603
    "R2": ("C25803", "Resistor_SMD:R_0603_1608Metric"),   # 100 kOhm 0603
    "C1": ("C14663", None),                               # 100 nF 0603
    "LED1": ("C52917433", None),                          # WS2812B-V6 5050
}
NEW_LCSC = {"J2": "C262661", "R3": "C23162", "R4": "C23162", "C2": "C14663"}

# KiCad 8-format generic 1x12 connector (pins on the left, 2.54 mm pitch).
CONN_SYMBOL = '(symbol "Connector_Generic:Conn_01x12" (pin_names (offset 1.016) hide) (exclude_from_sim no) (in_bom yes) (on_board yes)\n' \
    ' (property "Reference" "J" (at 0 15.24 0) (effects (font (size 1.27 1.27))))\n' \
    ' (property "Value" "Conn_01x12" (at 0 -17.78 0) (effects (font (size 1.27 1.27))))\n' \
    ' (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n' \
    ' (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n' \
    ' (property "Description" "Generic connector, single row, 01x12" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n' \
    ' (symbol "Conn_01x12_1_1" (rectangle (start -1.27 13.97) (end 1.27 -16.51) (stroke (width 0.254) (type default)) (fill (type background)))\n' + \
    "".join(
        f'  (pin passive line (at -5.08 {12.7 - 2.54 * i:.2f} 0) (length 3.81) (name "Pin_{i + 1}" (effects (font (size 1.27 1.27)))) (number "{i + 1}" (effects (font (size 1.27 1.27)))))\n'
        for i in range(12)) + ' )\n)\n'


def uid():
    return str(uuid.uuid4())


def label(name, x, y, angle):
    justify = "left" if angle == 0 else "right"
    return (f'(global_label "{name}" (shape passive) (at {x:.4f} {y:.4f} {angle}) (effects (font (size 1.27 1.27)) (justify {justify})) '
            f'(uuid "{uid()}") (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x:.4f} {y:.4f} 0) (effects (font (size 1.27 1.27)) (hide yes))))\n')


def symbol(lib_id, ref, value, footprint, x, y, pins, lcsc):
    props = (f' (property "Reference" "{ref}" (at {x + 6.35:.4f} {y - 1.27:.4f} 0) (effects (font (size 1.27 1.27))))'
             f' (property "Value" "{value}" (at {x + 6.35:.4f} {y + 1.27:.4f} 0) (effects (font (size 1.27 1.27))))'
             f' (property "Footprint" "{footprint}" (at {x:.4f} {y:.4f} 0) (effects (font (size 1.27 1.27)) (hide yes)))'
             f' (property "Datasheet" "" (at {x:.4f} {y:.4f} 0) (effects (font (size 1.27 1.27)) (hide yes)))'
             f' (property "LCSC" "{lcsc}" (at {x:.4f} {y:.4f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n')
    pin_text = "".join(f'(pin "{p}" (uuid "{uid()}"))\n' for p in pins)
    return (f'(symbol (lib_id "{lib_id}") (at {x:.4f} {y:.4f} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid()}")\n'
            f'{props}{pin_text} (instances (project "{NEW}" (path "/{SHEET_UUID}" (reference "{ref}") (unit 1)))))\n')


def two_pin(lib_id, ref, value, footprint, x, y, top, bottom, lcsc):
    # Device:R / Device:C are vertical: pin 1 at y-3.81, pin 2 at y+3.81.
    return (symbol(lib_id, ref, value, footprint, x, y, ("1", "2"), lcsc)
            + label(top, x, y - 3.81, 180) + label(bottom, x, y + 3.81, 180))


def set_property(text, ref, name, value):
    """Set or add a property on the placed symbol whose Reference is ref."""
    start = text.index(f'(property "Reference" "{ref}"')
    head = text.rindex("(symbol (lib_id", 0, start)
    end = text.index("(instances", start)
    block = text[head:end]
    at = re.search(r'\(symbol \(lib_id "[^"]+"\) \(at ([\d.]+) ([\d.]+)', block)
    pattern = re.compile(rf'\(property "{name}" "[^"]*"')
    if pattern.search(block):
        block = pattern.sub(f'(property "{name}" "{value}"', block, count=1)
    else:
        x, y = at.groups()
        prop = f' (property "{name}" "{value}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))'
        block = block.replace('(property "Datasheet"', prop.strip() + ' (property "Datasheet"', 1)
    return text[:head] + block + text[end:]


def main():
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True)
    for name in ("NanoWireless.kicad_sym", "fp-lib-table", "sym-lib-table"):
        shutil.copy2(SOURCE / name, TARGET / name)
    shutil.copytree(SOURCE / "NanoWireless.pretty", TARGET / "NanoWireless.pretty")
    (TARGET / "NanoWireless.pretty" / "JUSHUO_AFC01-S12FCA-00_1x12-1MP_P0.50mm_Horizontal.kicad_mod").write_text(ffc_footprint())
    pro = (SOURCE / f"{OLD}.kicad_pro").read_text().replace(OLD, NEW)
    (TARGET / f"{NEW}.kicad_pro").write_text(pro)

    sch = (SOURCE / f"{OLD}.kicad_sch").read_text()
    sch = sch.replace(f'(project "{OLD}"', f'(project "{NEW}"')
    sch = sch.replace("(lib_symbols\n", "(lib_symbols\n" + CONN_SYMBOL, 1)
    for ref, (lcsc, footprint) in LCSC.items():
        sch = set_property(sch, ref, "LCSC", lcsc)
        if footprint:
            sch = set_property(sch, ref, "Footprint", footprint)

    # U2 pads 15/14/13 sit at x=62.23 on the right-hand pin column.
    for name, y in (("SDA", 76.2), ("SCL", 78.74), ("DR", 81.28)):
        nc = re.compile(rf'\(no_connect \(at 62\.2300 {y:.4f}\) \(uuid "[^"]+"\)\)\n')
        assert len(nc.findall(sch)) == 1, (name, y)
        sch = nc.sub(label(name, 62.23, y, 0), sch, count=1)

    parts = []
    jx, jy = 105.41, 63.5        # J2 symbol origin; pins at x-5.08
    parts.append(symbol("Connector_Generic:Conn_01x12", "J2", "Cirque FFC 12P 0.5mm", FFC_FOOTPRINT, jx, jy,
                        [str(i) for i in range(1, 13)], NEW_LCSC["J2"]))
    nets = {4: "DR", 9: "SCL", 10: "SDA", 11: "gnd", 12: "VCC_SW"}
    for pin in range(1, 13):
        px, py = jx - 5.08, jy - (12.7 - 2.54 * (pin - 1))
        if pin in nets:
            parts.append(label(nets[pin], px, py, 180))
        else:
            parts.append(f'(no_connect (at {px:.4f} {py:.4f}) (uuid "{uid()}"))\n')
    parts.append(two_pin("Device:R", "R3", "4.7k", "Resistor_SMD:R_0603_1608Metric", 91.44, 99.06, "VCC_SW", "SDA", NEW_LCSC["R3"]))
    parts.append(two_pin("Device:R", "R4", "4.7k", "Resistor_SMD:R_0603_1608Metric", 104.14, 99.06, "VCC_SW", "SCL", NEW_LCSC["R4"]))
    parts.append(two_pin("Device:C", "C2", "100nF", "Capacitor_SMD:C_0603_1608Metric", 116.84, 99.06, "VCC_SW", "gnd", NEW_LCSC["C2"]))
    parts.append(f'(text "Cirque TM040040 (Pinnacle) in I2C mode: remove R1 on the pad module.\\nFFC pins: 4 DR, 9 SCL, 10 SDA, 11 GND, 12 VDD 3.3 V." '
                 f'(exclude_from_sim no) (at 86.36 114.3 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{uid()}"))\n')
    body = sch.rstrip()
    assert body.endswith(")")
    sch = body[:-1] + "".join(parts) + ")\n"
    (TARGET / f"{NEW}.kicad_sch").write_text(sch)
    print(f"Written to {TARGET}")


def ffc_footprint():
    """Jushuo AFC01-S12FCA-00 from its recommended land pattern (drawing rev A).

    Signal pads 0.30 x 1.30 mm at 0.50 mm pitch; fitting nails 2.00 x 1.60 mm,
    outer edge 2.70 mm beyond pin 1's outer edge, lower edge 4.13 mm from the
    signal pads' top edge. Origin at the signal-pad row centre; the FFC enters
    from the side opposite the signal pads (+Y).
    """
    pads = []
    for i in range(12):
        x = -2.75 + 0.5 * i
        pads.append(f'\t(pad "{i + 1}" smd rect (at {x:.2f} 0) (size 0.3 1.3) (layers "F.Cu" "F.Mask" "F.Paste"))')
    for x in (-4.60, 4.60):
        pads.append(f'\t(pad "MP" smd rect (at {x:.2f} 2.68) (size 2.0 1.6) (layers "F.Cu" "F.Mask" "F.Paste"))')
    body = "\n".join(pads)
    return f'''(footprint "JUSHUO_AFC01-S12FCA-00_1x12-1MP_P0.50mm_Horizontal"
\t(version 20240108)
\t(generator "build_nice_nano_cirque_sch")
\t(layer "F.Cu")
\t(descr "Jushuo AFC01-S12FCA-00, 12-pin 0.5 mm FFC/FPC, bottom contact, flip lock, H2.0 (LCSC C262661)")
\t(tags "FFC FPC 0.5mm 12P Cirque")
\t(attr smd)
\t(property "Reference" "REF**" (at 0 -2.2 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
\t(property "Value" "AFC01-S12FCA-00" (at 0 5.4 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
\t(fp_rect (start -5.2 0.5) (end 5.2 4.1) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
\t(fp_rect (start -5.85 -1.0) (end 5.85 4.6) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
\t(fp_line (start -3.3 -0.5) (end -3.3 -1.0) (stroke (width 0.12) (type default)) (layer "F.SilkS"))
\t(fp_text user "FFC" (at 0 3.0 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.1))))
{body}
)
'''


if __name__ == "__main__":
    main()
