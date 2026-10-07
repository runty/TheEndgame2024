#!/usr/bin/env python3
"""Generate left/right Choc V2 switch plates that drop into the Endgame case wells.

The case is a top frame whose underside rests on the PCB top (case Z = 1.6).
A Choc V2 top housing sits 2.20 mm above the PCB (Kailh CPG135301D02), so a
1.2 mm plate occupies case Z 2.6..3.8, inside the case's switch wells. Each
plate piece is the well outline (narrowest over that Z range) inset by a
clearance, with a 14.0 mm square cutout per switch (13.95 +/- 0.05 housing).
A well that opens into another cavity (as in the nice!nano case) is also
bounded 2 mm beyond its switch housings, and top-side components given with
--keepouts are cleared by the same clearance.

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


def sample_wire(wire):
    # Sample the wire as one composite curve so edges join exactly; chords
    # only cut inside corners, which shrinks the plate safely.
    n = max(64, int(wire.Length() / 0.05))
    pts = [wire.positionAt(i / n) for i in range(n)]
    return [(p.x, p.y) for p in pts]


def well_polygons(case, z_values):
    """Open space in the case section within its XY frame, intersected over all
    sampled heights. Closed switch wells come out as separate polygons; a well
    that opens into another cavity or the outside merges with that space."""
    bb = case.val().BoundingBox()
    frame = box(bb.xmin - 5, bb.ymin - 5, bb.xmax + 5, bb.ymax + 5)
    result = None
    for z in z_values:
        material = unary_union([
            Polygon(sample_wire(face.outerWire()), [sample_wire(w) for w in face.innerWires()]).buffer(0)
            for face in case.section(z).faces().vals()])
        layer = frame.difference(material)
        result = layer if result is None else result.intersection(layer)
    return result, frame


def polys(geom):
    if geom.is_empty:
        return []
    return [geom] if geom.geom_type == 'Polygon' else [g for g in geom.geoms if g.geom_type == 'Polygon']


def plate_regions(case, z_values, switches, clearance, margin=2.0, keepouts=()):
    """Plate outline per switch group, inset from the case by `clearance`.

    A well that is a closed hole keeps the case outline. A well that is open to
    another cavity or the outside is also bounded by the convex hull of its
    switches' 15 mm housings grown by `margin`. Top-side component keepouts are
    removed with the same clearance.
    """
    space, frame = well_polygons(case, z_values)
    blocked = unary_union([Polygon(k).buffer(clearance) for k in keepouts]) if keepouts else None
    regions = []
    for region in polys(space):
        inside = [s for s in switches if region.contains(Point(s['x'], s['y']))]
        if not inside:
            continue
        open_sided = region.intersects(frame.exterior.buffer(1))
        for side, group in (('left', [s for s in inside if s['x'] < 0]), ('right', [s for s in inside if s['x'] >= 0])):
            if not group:
                continue
            outline = region.buffer(-clearance, join_style='mitre')
            if open_sided:
                hull = unary_union([square(s, 15 + 2 * margin) for s in group]).convex_hull
                outline = outline.intersection(hull)
            if blocked is not None:
                outline = outline.difference(blocked)
            parts = [p for p in polys(outline) if any(p.contains(Point(s['x'], s['y'])) for s in group)]
            assert len(parts) == 1, f'{side} switch group split across {len(parts)} pieces'
            regions.append({'side': side, 'outline': parts[0].simplify(0.002), 'switches': group,
                            'open_sided': open_sided})
    assert sum(len(r['switches']) for r in regions) == len(switches), 'switch outside every well'
    return regions


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
    ap.add_argument('--case', type=Path, default=CASE, help='case STEP the plates must fit')
    ap.add_argument('--keepouts', type=Path, help='top-side component outlines from export_switches.py --keepouts')
    ap.add_argument('--thickness', type=float, default=1.2)
    ap.add_argument('--clearance', type=float, default=0.3, help='gap to case well walls')
    args = ap.parse_args()

    switches = json.loads(args.switches.read_text())
    assert len(switches) == 36
    case = cq.importers.importStep(str(args.case))

    plate_top = PCB_TOP + PLATE_TOP_ABOVE_PCB
    plate_bottom = plate_top - args.thickness
    zs = [plate_bottom + 0.05 + i * (args.thickness - 0.1) / 12 for i in range(13)]
    keepouts = json.loads(args.keepouts.read_text()) if args.keepouts else []
    regions = plate_regions(case, zs, switches, args.clearance, keepouts=[k['pts'] for k in keepouts])

    pieces = {'left': [], 'right': []}
    report = {'thickness_mm': args.thickness, 'clearance_mm': args.clearance,
              'plate_z_case': [plate_bottom, plate_top], 'keepouts': [k['ref'] for k in keepouts], 'pieces': []}
    for r in regions:
        inside, outline, side = r['switches'], r['outline'], r['side']
        plate = outline.difference(unary_union([cutout(s) for s in inside]))
        assert plate.geom_type == 'Polygon', 'cutout splits a plate piece'
        # Every 13.95 housing (plus tolerance) must lie fully within its cutout.
        for s in inside:
            assert not plate.intersects(housing(s, 14.0).buffer(-1e-6)), s['ref']
        pieces[side].append(plate)
        web = min(outline.exterior.distance(cutout(s)) for s in inside)
        pair = [cutout(a).distance(cutout(b)) for a in inside for b in inside if a['ref'] < b['ref']]
        report['pieces'].append({'side': side, 'switches': sorted(s['ref'] for s in inside),
                                 'open_sided_well': r['open_sided'],
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
