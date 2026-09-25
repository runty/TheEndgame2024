#!/usr/bin/env python3
"""Check conservative V2 switch envelopes against the unmodified Endgame case.

Requires cadquery-ocp (validated with 8.0.1.0.0). This checks CAD geometry;
printing tolerances, retention, and keycaps require a physical fit check.
"""
import argparse
import json
import math
import re
from pathlib import Path
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt, gp_Trsf, gp_Ax1, gp_Dir, gp_Vec
from verify_choc_compatibility import ROOT, blocks, coords


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    reader = STEPControl_Reader()
    assert int(reader.ReadFile(str(ROOT / '002 CASE/TheENDGAME2024_CASE001.step'))) == 1
    reader.TransferRoots()
    case = reader.OneShape()
    board = (ROOT / '001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb').read_text()
    out = []
    for fp in blocks(board, 'footprint'):
        if 'SW_choc_v1_v2_HS_' not in fp.splitlines()[0]:
            continue
        position = coords(fp, 'at', 2)
        angle = position[2] if len(position) == 3 else 0
        # Properties span lines, unlike coordinates.
        ref = re.search(r'\(property "Reference" "([^"]+)"', fp).group(1)
        envelope = BRepPrimAPI_MakeBox(gp_Pnt(-7.5, -7.5, 1.6), 15, 15, 6.4).Shape()
        transform = gp_Trsf()
        transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(angle))
        envelope = BRepBuilderAPI_Transform(envelope, transform, True).Shape()
        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(position[0]-150, 140-position[1], 0))
        envelope = BRepBuilderAPI_Transform(envelope, transform, True).Shape()
        common = BRepAlgoAPI_Common(case, envelope).Shape()
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(common, properties)
        distance = BRepExtrema_DistShapeShape(case, envelope)
        distance.Perform()
        out.append({'ref': ref, 'intersection_mm3': properties.Mass(), 'clearance_mm': distance.Value()})
    assert len(out) == 36
    assert all(v['intersection_mm3'] < 1e-6 for v in out), 'Switch envelope intersects the case'
    assert all(v['clearance_mm'] > 0 for v in out), 'Switch envelope touches the case'
    if args.output:
        args.output.write_text(json.dumps(out, indent=2) + '\n')
    print(f"36 switch envelopes clear the case; minimum separation {min(v['clearance_mm'] for v in out):.4f} mm")


if __name__ == '__main__':
    main()
