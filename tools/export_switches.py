#!/usr/bin/env python3
"""Export switch centres and angles in case coordinates for make_choc_v2_plate.py.

Run with KiCad's bundled Python (it needs pcbnew), e.g. on macOS:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      tools/export_switches.py switches.json [--board path/to/board.kicad_pcb]

Centres and angles come from each switch's two 1.7 mm locating holes, which
sit on the switch's horizontal axis at +/-5.5 mm. Case = (PCB X - 150, 140 - PCB Y).
"""
import argparse
import json
import math
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / '001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output', type=Path)
    ap.add_argument('--board', type=Path, default=BOARD)
    ap.add_argument('--keepouts', type=Path, help='also write top-side component outlines (courtyard, else footprint bounds)')
    args = ap.parse_args()
    board = pcbnew.LoadBoard(str(args.board))
    mm = pcbnew.ToMM
    out = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if 'choc' not in fp.GetFPIDAsString().lower():
            continue
        holes = [p for p in fp.Pads()
                 if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH and abs(mm(p.GetDrillSize().x) - 1.7) < 0.01]
        assert len(holes) == 2, ref
        a, b = [(mm(p.GetPosition().x) - 150, 140 - mm(p.GetPosition().y)) for p in holes]
        angle = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 90
        if angle > 45:
            angle -= 90
        out.append({'ref': ref, 'x': (a[0] + b[0]) / 2, 'y': (a[1] + b[1]) / 2, 'angle': angle})
    assert len(out) == 36
    if args.keepouts:
        keep = []
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            if 'choc' in fp.GetFPIDAsString().lower() or ref.startswith('REF') or not fp.Pads():
                continue
            yard = fp.GetCourtyard(pcbnew.F_CrtYd)
            if not yard.OutlineCount() and not any(p.IsOnLayer(pcbnew.F_Cu) for p in fp.Pads()):
                continue  # nothing on the top side, e.g. the back-mounted RP2040-Zero
            if yard.OutlineCount():
                rings = [yard.Outline(i) for i in range(yard.OutlineCount())]
                outlines = [[(mm(r.CPoint(k).x) - 150, 140 - mm(r.CPoint(k).y)) for k in range(r.PointCount())] for r in rings]
            else:
                b = fp.GetBoundingBox(False)
                x0, x1, y0, y1 = mm(b.GetLeft()) - 150, mm(b.GetRight()) - 150, 140 - mm(b.GetBottom()), 140 - mm(b.GetTop())
                outlines = [[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
            keep += [{'ref': ref, 'pts': pts} for pts in outlines]
        args.keepouts.write_text(json.dumps(keep, indent=1) + '\n')
    args.output.write_text(json.dumps(sorted(out, key=lambda s: s['ref']), indent=1) + '\n')


if __name__ == '__main__':
    main()
