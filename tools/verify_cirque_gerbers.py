#!/usr/bin/env python3
"""Fabrication checks on the exported nice!nano + Cirque Gerber ZIP.

Measures what JLCPCB will actually build, after KiCad's export has refilled
the zones with the project's rules:

- copper (both layers) at least MIN_EDGE from the outline and every cutout;
- no stencil paste over any drilled hole (via-in-pad wicking);
- no silkscreen inside a solder-mask opening, and no silkscreen fragment
  narrower than MIN_SILK (KiCad clipping ink at an opening leaves slivers).

Writes a JSON report and exits non-zero when a check fails. Needs gerbonara
and Shapely.
Run: python tools/verify_cirque_gerbers.py --zip X_JLCPCB.zip --report out.json
"""
import argparse
import json
import math
from pathlib import Path
import sys
import tempfile
import zipfile

import shapely
from gerbonara import ExcellonFile, GerberFile
from gerbonara import graphic_objects as go
from gerbonara import graphic_primitives as gp
from gerbonara.utils import MM
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box

MIN_EDGE = 0.2      # mm, copper to board edge (JLCPCB minimum)
ARC_TOLERANCE = 0.005  # mm, KiCad's max_error when it turns arcs into polygons
MIN_SILK = 0.1      # mm, narrowest silkscreen fragment allowed
Q = 16


def arc_points(x1, y1, x2, y2, cx, cy, cw, max_err=0.002):
    r = math.hypot(x1 - cx, y1 - cy)
    a1, a2 = math.atan2(y1 - cy, x1 - cx), math.atan2(y2 - cy, x2 - cx)
    full = math.isclose(x1, x2, abs_tol=1e-7) and math.isclose(y1, y2, abs_tol=1e-7)
    sweep = (a1 - a2 if cw else a2 - a1) % (2 * math.pi) or (2 * math.pi if full else 0)
    sweep = -sweep if cw else sweep
    if r < 1e-9:
        return [(x1, y1)]
    step = 2 * math.acos(max(-1.0, 1 - max_err / r)) if r > max_err else math.pi / 4
    n = max(2, int(abs(sweep) / max(step, 1e-3)) + 1)
    return [(cx + r * math.cos(a1 + sweep * i / n), cy + r * math.sin(a1 + sweep * i / n)) for i in range(n + 1)]


def to_geometry(p):
    if isinstance(p, gp.Circle):
        return Point(p.x, p.y).buffer(p.r, quad_segs=Q)
    if isinstance(p, gp.Line):
        if p.width <= 0:
            return None
        return LineString([(p.x1, p.y1), (p.x2, p.y2)]).buffer(p.width / 2, quad_segs=Q)
    if isinstance(p, gp.Arc):
        if p.width <= 0:
            return None
        return LineString(arc_points(p.x1, p.y1, p.x2, p.y2, p.cx, p.cy, p.clockwise)).buffer(p.width / 2, quad_segs=Q)
    if isinstance(p, gp.Rectangle):
        g = box(p.x - p.w / 2, p.y - p.h / 2, p.x + p.w / 2, p.y + p.h / 2)
        return affinity.rotate(g, p.rotation, origin=(p.x, p.y), use_radians=True) if p.rotation else g
    if isinstance(p, gp.ArcPoly):
        pts = []
        for (x1, y1), (x2, y2), (cw, centre) in p.segments:
            pts += [(x1, y1)] if cw is None else arc_points(x1, y1, x2, y2, *centre, cw)[:-1]
        return shapely.make_valid(Polygon(pts)) if len(pts) >= 3 else None
    raise TypeError(type(p))


def layer(path):
    """Dark-minus-clear geometry of one Gerber layer, in mm."""
    result, batch, dark = Polygon(), [], True
    for obj in GerberFile.open(path).objects:
        for prim in obj.to_primitives(MM):
            g = to_geometry(prim)
            if g is None or g.is_empty:
                continue
            if prim.polarity_dark != dark:
                result = shapely.union(result, shapely.union_all(batch)) if dark else shapely.difference(result, shapely.union_all(batch))
                batch, dark = [], prim.polarity_dark
            batch.append(g)
    if batch:
        result = shapely.union(result, shapely.union_all(batch)) if dark else shapely.difference(result, shapely.union_all(batch))
    return result


def drills(path):
    holes = []
    for obj in ExcellonFile.open(path).objects:
        d = obj.tool.diameter
        if isinstance(obj, go.Flash):
            holes.append(Point(obj.x, obj.y).buffer(d / 2, quad_segs=Q))
        else:
            holes.append(LineString([(obj.x1, obj.y1), (obj.x2, obj.y2)]).buffer(d / 2, quad_segs=Q))
    return holes


def edge_lines(path):
    """Centre lines of the Edge.Cuts strokes: the outline and every cutout."""
    lines = []
    for obj in GerberFile.open(path).objects:
        for prim in obj.to_primitives(MM):
            if isinstance(prim, gp.Line):
                lines.append(LineString([(prim.x1, prim.y1), (prim.x2, prim.y2)]))
            elif isinstance(prim, gp.Arc):
                lines.append(LineString(arc_points(prim.x1, prim.y1, prim.x2, prim.y2, prim.cx, prim.cy, prim.clockwise)))
    return shapely.union_all(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--zip', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(args.zip) as z:
            z.extractall(tmp)
        files = {p.name.split('-')[-1]: p for p in Path(tmp).iterdir()}
        edge = edge_lines(files['Edge_Cuts.gm1'])
        holes = drills(files['PTH.drl']) + drills(files['NPTH.drl'])
        report, ok = {'zip': args.zip.name}, True
        for name in ('F_Cu.gtl', 'B_Cu.gbl'):
            gap = round(layer(files[name]).distance(edge), 4)
            report[f'{name[:4]}_copper_to_edge_mm'] = gap
            ok &= gap >= MIN_EDGE - ARC_TOLERANCE
        for side, paste in (('F', 'F_Paste.gtp'), ('B', 'B_Paste.gbp')):
            if paste in files:
                over = shapely.union_all(holes).intersection(layer(files[paste])).area
                report[f'{side}_paste_over_holes_mm2'] = round(over, 5)
                ok &= over < 1e-6
        for side, silk, mask in (('F', 'F_Silkscreen.gto', 'F_Mask.gts'), ('B', 'B_Silkscreen.gbo', 'B_Mask.gbs')):
            ink, openings = layer(files[silk]), layer(files[mask])
            inside = ink.intersection(openings).area
            thin = [g for g in getattr(ink, 'geoms', [ink]) if g.buffer(-MIN_SILK / 2).is_empty]
            report[f'{side}_silk_in_mask_openings_mm2'] = round(inside, 5)
            report[f'{side}_silk_fragments_under_{MIN_SILK}mm'] = len(thin)
            ok &= inside < 1e-4 and not thin
    report['pass'] = bool(ok)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
