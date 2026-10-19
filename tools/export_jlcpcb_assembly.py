#!/usr/bin/env python3
"""Write JLCPCB assembly BOM and CPL files for parts carrying an LCSC field.

Only footprints with an LCSC number are listed; hand-soldered parts are left
out. Coordinates are absolute (matching the Gerbers from export_jlcpcb.py),
with Y negated as in KiCad's position files. Two JLCPCB conventions are
applied, as in the widely used KiCad-to-JLCPCB exporters (Bouni's
kicad-jlcpcb-tools, bennymeg's Fabrication Toolkit):

- Position is the centre of the part's soldered pads, not the footprint
  origin (J2's origin is its pad row, 1.4 mm from its pad centre).
- Bottom-side rotation is 180 - KiCad's angle: JLCPCB reads it as seen
  looking at the bottom side. KiCad's raw angle would turn most of the
  bottom-side diodes round.

Run with KiCad's Python: $KPY tools/export_jlcpcb_assembly.py --board X.kicad_pcb --output DIR
"""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

import wx
app = wx.App(False)
import pcbnew as p


def lcsc(fp):
    for field in fp.GetFields():
        if field.GetName() == 'LCSC':
            return field.GetText()
    return ''


def pad_centre(fp):
    """Centre of the bounding box of the footprint's soldered pads, in mm."""
    box = None
    for pad in fp.Pads():
        if pad.GetAttribute() == p.PAD_ATTRIB_NPTH:
            continue
        bb = pad.GetBoundingBox()
        if box is None:
            box = bb
        else:
            box.Merge(bb)
    c = box.GetCenter() if box is not None else fp.GetPosition()
    return c.x / 1e6, c.y / 1e6


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--board', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--name', default=None, help='file stem; defaults to the board name')
    args = ap.parse_args()
    stem = args.name or args.board.stem
    args.output.mkdir(parents=True, exist_ok=True)
    board = p.LoadBoard(str(args.board))
    assembled = {fp.GetReference(): fp for fp in board.GetFootprints() if lcsc(fp)}
    assert assembled, 'No footprints carry an LCSC field'

    with (args.output / f'{stem}_CPL.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for ref in sorted(assembled, key=natural):
            fp = assembled[ref]
            x, y = pad_centre(fp)
            angle = fp.GetOrientationDegrees() % 360
            bottom = fp.IsFlipped()
            if bottom:
                angle = (180 - angle) % 360
            w.writerow([ref, f'{x:.4f}mm', f'{-y:.4f}mm', 'Bottom' if bottom else 'Top', f'{angle:.1f}'])

    groups = defaultdict(list)
    for ref, fp in assembled.items():
        groups[(fp.GetValue(), str(fp.GetFPID().GetLibItemName()), lcsc(fp))].append(ref)
    with (args.output / f'{stem}_BOM.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (value, footprint, part), refs in sorted(groups.items(), key=lambda g: natural(g[1][0])):
            w.writerow([value, ','.join(sorted(refs, key=natural)), footprint, part])
    print(f'{len(assembled)} assembled parts ({len(groups)} BOM lines) -> {args.output}')


def natural(ref):
    m = re.match(r'([A-Za-z]+)(\d+)', ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


if __name__ == '__main__':
    main()
