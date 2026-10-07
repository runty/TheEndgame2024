#!/usr/bin/env python3
"""Generate left/right Choc V2 switch plates that drop into the Endgame case wells.

The case is a top frame whose underside rests on the PCB top (case Z = 1.6).
A Choc V2 top housing sits 2.20 mm above the PCB (Kailh CPG135301D02), so a
1.2 mm plate occupies case Z 2.6..3.8, inside the case's switch wells. Each
plate piece is the well outline (narrowest over that Z range) inset by a
clearance, with a 14.0 mm square cutout per switch (13.95 +/- 0.05 housing).

Requires cadquery, shapely and ezdxf. Switch centres come from the KiCad board
via tools/export_switches.py (run with KiCad's bundled Python).

Coordinates: case frame, case = (PCB X - 150, 140 - PCB Y), millimetres.
"""
import argparse
import json
import math
from pathlib import Path

import cadquery as cq
import ezdxf
from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / '002 CASE/TheENDGAME2024_CASE001.step'

PCB_TOP = 1.6
PLATE_TOP_ABOVE_PCB = 2.2   # Choc V2 bottom-housing height
CUTOUT = 14.0               # housing 13.95 +/- 0.05
DOGBONE_R = 0.5             # lets a 1.0 mm router bit clear square corners


def well_polygons(case, z_values):
    """Openings in the case section, intersected over all sampled heights."""
    result = None
    for z in z_values:
        holes = []
        for face in case.section(z).faces().vals():
            for wire in face.innerWires():
                # Sample the wire as one composite curve so edges join exactly;
                # chords only cut inside corners, which shrinks the plate safely.
                n = max(64, int(wire.Length() / 0.05))
                pts = [wire.positionAt(i / n) for i in range(n)]
                holes.append(Polygon([(p.x, p.y) for p in pts]).buffer(0))
        layer = unary_union(holes)
        result = layer if result is None else result.intersection(layer)
    return result


def cutout(sw, size=CUTOUT):
    half = size / 2
    shape = box(-half, -half, half, half)
    d = DOGBONE_R / math.sqrt(2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            shape = shape.union(Point(sx * (half - d), sy * (half - d)).buffer(DOGBONE_R, 8))
    shape = affinity.rotate(shape, sw['angle'], origin=(0, 0))
    return affinity.translate(shape, sw['x'], sw['y'])


def housing(sw, size):
    return square(sw, size)


def square(sw, size):
    shape = box(-size / 2, -size / 2, size / 2, size / 2)
    shape = affinity.rotate(shape, sw['angle'], origin=(0, 0))
    return affinity.translate(shape, sw['x'], sw['y'])


def to_workplane(poly, z0, thickness):
    def ring(coords):
        return [(x, y) for x, y in list(coords)[:-1]]
    solid = cq.Workplane('XY', origin=(0, 0, z0)).polyline(ring(poly.exterior.coords)).close().extrude(thickness)
    for interior in poly.interiors:
        hole = cq.Workplane('XY', origin=(0, 0, z0 - 1)).polyline(ring(interior.coords)).close().extrude(thickness + 2)
        solid = solid.cut(hole)
    return solid


def write_dxf(pieces, path):
    doc = ezdxf.new('R2010', setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    for poly in pieces:
        for ring in [poly.exterior, *poly.interiors]:
            msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={'layer': 'OUTLINE'})
    doc.saveas(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--switches', type=Path, required=True, help='JSON from export_switches.py')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--thickness', type=float, default=1.2)
    ap.add_argument('--clearance', type=float, default=0.3, help='gap to case well walls')
    args = ap.parse_args()

    switches = json.loads(args.switches.read_text())
    assert len(switches) == 36
    case = cq.importers.importStep(str(CASE))

    plate_top = PCB_TOP + PLATE_TOP_ABOVE_PCB
    plate_bottom = plate_top - args.thickness
    zs = [plate_bottom + 0.05 + i * (args.thickness - 0.1) / 12 for i in range(13)]
    wells = well_polygons(case, zs)
    wells = [wells] if wells.geom_type == 'Polygon' else list(wells.geoms)

    pieces = {'left': [], 'right': []}
    report = {'thickness_mm': args.thickness, 'clearance_mm': args.clearance,
              'plate_z_case': [plate_bottom, plate_top], 'pieces': []}
    for well in wells:
        inside = [s for s in switches if well.contains(Point(s['x'], s['y']))]
        if not inside:
            continue
        outline = well.buffer(-args.clearance, join_style='mitre').simplify(0.002)
        plate = outline.difference(unary_union([cutout(s) for s in inside]))
        assert plate.geom_type == 'Polygon', 'cutout splits a plate piece'
        # Every 13.95 housing (plus tolerance) must lie fully within its cutout.
        for s in inside:
            assert not plate.intersects(housing(s, 14.0).buffer(-1e-6)), s['ref']
        side = 'left' if well.centroid.x < 0 else 'right'
        pieces[side].append(plate)
        web = min(outline.exterior.distance(cutout(s)) for s in inside)
        pair = [cutout(a).distance(cutout(b)) for a in inside for b in inside if a['ref'] < b['ref']]
        report['pieces'].append({'side': side, 'switches': sorted(s['ref'] for s in inside),
                                 'outline_mm': [round(v, 2) for v in outline.bounds],
                                 'min_edge_web_mm': round(web, 3),
                                 'min_between_cutouts_mm': round(min(pair), 3) if pair else None})

    assert sum(len(r['switches']) for r in report['pieces']) == 36

    # Right must be the mirror of left about X = 0.
    mirrored = unary_union([affinity.scale(p, -1, 1, origin=(0, 0)) for p in pieces['left']])
    report['mirror_symmetric_diff_mm2'] = round(mirrored.symmetric_difference(unary_union(pieces['right'])).area, 4)

    args.output.mkdir(parents=True, exist_ok=True)
    for side, polys in pieces.items():
        polys.sort(key=lambda p: -p.area)
        write_dxf(polys, args.output / f'endgame_choc_v2_plate_{side}.dxf')
        rings = [[list(r.coords)[:-1] for r in (p.exterior, *p.interiors)] for p in polys]
        (args.output / f'endgame_choc_v2_plate_{side}.json').write_text(json.dumps(rings) + '\n')
        solid = None
        for p in polys:
            s = to_workplane(p, plate_bottom, args.thickness)
            solid = s if solid is None else solid.union(s)
        cq.exporters.export(solid, str(args.output / f'endgame_choc_v2_plate_{side}.step'))
        flat = solid.translate((0, 0, -plate_bottom))
        cq.exporters.export(flat, str(args.output / f'endgame_choc_v2_plate_{side}.stl'), tolerance=0.01)
        # 3-D check against the unmodified case.
        common = case.intersect(solid)
        vol = sum(v.Volume() for v in common.solids().vals()) if common.solids().vals() else 0.0
        dist = case.val().distance(solid.val())
        report[f'{side}_case_intersection_mm3'] = round(vol, 6)
        report[f'{side}_case_min_distance_mm'] = round(dist, 3)
        assert vol < 1e-6, f'{side} plate intersects the case'
    (args.output / 'plate-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
