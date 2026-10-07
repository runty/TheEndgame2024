#!/usr/bin/env python3
"""Build KiCad boards and JLCPCB Gerber ZIPs from make_choc_v2_plate.py outlines.

Run with KiCad's bundled Python (it needs pcbnew), e.g. on macOS:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      tools/export_plate_gerbers.py <plate output dir>

Outlines are placed in PCB coordinates (PCB = case X + 150, 140 - case Y) on
Edge.Cuts of a copper-free 1.2 mm board.
"""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pcbnew

KICAD_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
LAYERS = 'F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts'


def build(rings_path, board_path, thickness):
    board = pcbnew.BOARD()
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(thickness))
    for piece in json.loads(rings_path.read_text()):
        for ring in piece:
            pts = [pcbnew.VECTOR2I(pcbnew.FromMM(x + 150), pcbnew.FromMM(140 - y)) for x, y in ring]
            for a, b in zip(pts, pts[1:] + pts[:1]):
                seg = pcbnew.PCB_SHAPE(board)
                seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
                seg.SetLayer(pcbnew.Edge_Cuts)
                seg.SetWidth(pcbnew.FromMM(0.05))
                seg.SetStart(a)
                seg.SetEnd(b)
                board.Add(seg)
    board.Save(str(board_path))


def main():
    out = Path(sys.argv[1]).resolve()
    thickness = json.loads((out / 'plate-report.json').read_text())['thickness_mm']
    for side in ('left', 'right'):
        name = f'endgame_choc_v2_plate_{side}'
        board_path = out / f'{name}.kicad_pcb'
        build(out / f'{name}.json', board_path, thickness)
        gerbers = out / f'{name}_gerbers'
        shutil.rmtree(gerbers, ignore_errors=True)
        gerbers.mkdir()
        subprocess.run([KICAD_CLI, 'pcb', 'export', 'gerbers', '--layers', LAYERS,
                        '--output', str(gerbers), str(board_path)], check=True)
        subprocess.run([KICAD_CLI, 'pcb', 'export', 'drill', '--format', 'excellon',
                        '--excellon-separate-th', '--output', str(gerbers) + '/', str(board_path)], check=True)
        with zipfile.ZipFile(out / f'{name}_JLCPCB.zip', 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(gerbers.iterdir()):
                z.write(f, f.name)
        print(f'wrote {name}_JLCPCB.zip')


if __name__ == '__main__':
    main()
