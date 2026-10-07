#!/usr/bin/env python3
"""Generate 3-D-printable left/right Choc V2 plates for the Endgame case wells.

Unlike the 1.2 mm sheet plate from make_choc_v2_plate.py, the printed plate
fills the well from the PCB top (case Z 1.6) to the switch flange (Z 3.8), so
it rests on the bare PCB at the right height. A pocket under each cutout leaves
a lip of the clip thickness for the switch clips to latch under.

Defaults allow for FDM shrinkage: 14.1 mm cutouts and 0.4 mm wall clearance.
Print top face down; the STLs are already oriented that way.

Requires cadquery, shapely and ezdxf.
"""
import argparse
import json
from pathlib import Path

import cadquery as cq
from shapely import affinity
from shapely.geometry import Point
from shapely.ops import unary_union

from make_choc_v2_plate import CASE, PCB_TOP, PLATE_TOP_ABOVE_PCB, cutout, plate_regions, polys, square, to_workplane


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--switches', type=Path, required=True, help='JSON from export_switches.py')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--case', type=Path, default=CASE, help='case STEP the plates must fit')
    ap.add_argument('--keepouts', type=Path, help='top-side component outlines from export_switches.py --keepouts')
    ap.add_argument('--cutout', type=float, default=14.1, help='square switch cutout')
    ap.add_argument('--clearance', type=float, default=0.4, help='gap to case well walls')
    ap.add_argument('--lip', type=float, default=1.2, help='plate thickness the clips latch on')
    ap.add_argument('--pocket', type=float, default=16.0, help='square relief under each cutout for the clips')
    ap.add_argument('--min-rib', type=float, default=0.8, help='drop under-lip ribs thinner than this')
    args = ap.parse_args()

    switches = json.loads(args.switches.read_text())
    assert len(switches) == 36
    case = cq.importers.importStep(str(args.case))

    top = PCB_TOP + PLATE_TOP_ABOVE_PCB
    lip_bottom = top - args.lip
    zs = [PCB_TOP + 0.05 + i * (top - PCB_TOP - 0.1) / 16 for i in range(17)]
    keepouts = json.loads(args.keepouts.read_text()) if args.keepouts else []
    regions = plate_regions(case, zs, switches, args.clearance, keepouts=[k['pts'] for k in keepouts])

    pieces = {'left': [], 'right': []}
    report = {'cutout_mm': args.cutout, 'clearance_mm': args.clearance, 'lip_mm': args.lip,
              'pocket_mm': args.pocket, 'body_z_case': [PCB_TOP, top],
              'keepouts': [k['ref'] for k in keepouts], 'pieces': []}
    for r in regions:
        inside, outline, side = r['switches'], r['outline'], r['side']
        lip = outline.difference(unary_union([cutout(s, args.cutout) for s in inside]))
        assert lip.geom_type == 'Polygon', 'cutout splits a plate piece'
        base = outline.difference(unary_union([square(s, args.pocket) for s in inside]))
        base = base.buffer(-args.min_rib / 2, join_style='mitre').buffer(args.min_rib / 2, join_style='mitre')
        base = base.intersection(lip)
        for s in inside:
            # Housing must clear the lip; housing plus latched clips must clear the base.
            assert not lip.intersects(square(s, 14.0).buffer(-1e-6)), s['ref']
            assert not base.intersects(square(s, args.pocket - 0.2).buffer(-1e-6)), s['ref']
        pieces[side].append((lip, base, inside))
        report['pieces'].append({'side': side, 'switches': sorted(s['ref'] for s in inside),
                                 'open_sided_well': r['open_sided'],
                                 'lip_area_mm2': round(lip.area, 1), 'base_area_mm2': round(base.area, 1)})
    assert sum(len(p['switches']) for p in report['pieces']) == 36

    args.output.mkdir(parents=True, exist_ok=True)
    flip = lambda w: w.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, top))  # top face on the bed
    for side, items in pieces.items():
        items.sort(key=lambda it: -it[0].area)
        solid = None
        for lip, base, inside in items:
            body = to_workplane(lip, lip_bottom, args.lip)
            for b in polys(base):
                body = body.union(to_workplane(b, PCB_TOP, lip_bottom - PCB_TOP))
            solid = body if solid is None else solid.union(body)
            if len(inside) == 1 and side == 'left':
                cq.exporters.export(flip(body), str(args.output / 'endgame_choc_v2_print_plate_test_1key.stl'), tolerance=0.01)
        common = case.intersect(solid)
        vol = sum(v.Volume() for v in common.solids().vals()) if common.solids().vals() else 0.0
        report[f'{side}_case_intersection_mm3'] = round(vol, 6)
        report[f'{side}_case_min_distance_mm'] = round(case.val().distance(solid.val()), 3)
        assert vol < 1e-6, f'{side} plate intersects the case'
        report[f'{side}_volume_mm3'] = round(solid.val().Volume(), 1)
        cq.exporters.export(solid, str(args.output / f'endgame_choc_v2_print_plate_{side}.step'))
        cq.exporters.export(flip(solid), str(args.output / f'endgame_choc_v2_print_plate_{side}.stl'), tolerance=0.01)

    left = unary_union([affinity.scale(it[0], -1, 1, origin=(0, 0)) for it in pieces['left']])
    report['mirror_symmetric_diff_mm2'] = round(left.symmetric_difference(unary_union([it[0] for it in pieces['right']])).area, 4)
    (args.output / 'print-plate-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
