#!/usr/bin/env python3
"""Export switch centres and angles in case coordinates for make_choc_v2_plate.py.

Run with KiCad's bundled Python (it needs pcbnew), e.g. on macOS:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      tools/export_switches.py switches.json

Centres and angles come from each switch's two 1.7 mm locating holes, which
sit on the switch's horizontal axis at +/-5.5 mm. Case = (PCB X - 150, 140 - PCB Y).
"""
import json
import math
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / '001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb'


def main():
    board = pcbnew.LoadBoard(str(BOARD))
    mm = pcbnew.ToMM
    out = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if not ref.startswith('SW'):
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
    Path(sys.argv[1]).write_text(json.dumps(sorted(out, key=lambda s: s['ref']), indent=1) + '\n')


if __name__ == '__main__':
    main()
