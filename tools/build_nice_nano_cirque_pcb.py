"""Place the Cirque-variant parts on the widened nice!nano PCB.

Run with KiCad's bundled Python (pcbnew), one subcommand per process:

  place  --input widened.kicad_pcb --netlist cirque.net --output placed.kicad_pcb
      Removes the centre LED circuit's copper, replaces axial R1/R2 with 0603
      parts, moves LED1/C1/R1/R2 to the right thumb gap, adds J2 (bottom-side
      FFC), R3/R4/C2, cuts the FFC notch and assigns nets and LCSC fields.
  dump   --input placed.kicad_pcb --obstacles obstacles.json
      Writes copper, keep-out and outline geometry for the router.
  apply  --input placed.kicad_pcb --routes routes.json --output final.kicad_pcb
      Adds the routed tracks and vias, sets the edge/hole clearance rules and saves.
  fill   --input final.kicad_pcb
      Refills the ground pour in a fresh process, so the new rules take effect.
  photo-keepouts --input final.kicad_pcb --output keepouts.json
      Writes the underside mask openings, part silkscreen, holes, vias and J2's courtyard that
      add_cirque_photo_silkscreen.py keeps its ink away from.

Coordinates are KiCad PCB millimetres; case frame = (X - 150, 140 - Y).
"""
import argparse
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

import wx
app = wx.App(False)
import pcbnew as p

KICAD_FP = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_FP = os.path.join(HERE, '..', '001 PCB', 'KICAD', 'NICE NANO CIRQUE', 'NanoWireless.pretty')

# PCB placements (x, y, rotation, side). LED midway between SW27 and SW37
# caps on the line through their centres: case (79.39, 1.74).
LED_XY = (229.39, 138.26)
PLACE = {
    'LED1': (LED_XY[0], LED_XY[1], 0, 'F'),
    # The LED's passives sit on the underside so its case pocket stays small.
    'C1': (LED_XY[0], LED_XY[1] + 2.5, 0, 'B'),
    'R1': (LED_XY[0] + 5.0, LED_XY[1] - 2.5, 90, 'B'),
    'R2': (LED_XY[0] + 5.0, LED_XY[1] + 1.3, 90, 'B'),
    # Power switch under the nice!nano at the back edge: the slider faces out
    # through the case's USB opening, so the case needs no separate hole. Its
    # tip stays 0.5 mm inside the PCB edge, where the board protects it.
    'SW38': (150.0, 66.3, 0, 'B'),
    # J2's body reaches 5.75 mm from its pad row towards the notch. With the
    # row at X 176.0 its cable entry (X 170.25) is ~4 mm from where the FFC
    # drops (X ~166.0), room for the bend and stiffener; SW22's socket pad
    # (from X 177.5) stops it moving further out.
    'J2': (176.0, 123.0, None, 'B'),
    'R3': (168.6, 114.0, 90, 'B'),
    'R4': (170.6, 114.0, 90, 'B'),
    'C2': (166.0, 114.0, 0, 'B'),
}
# The pad's 4.1 mm-tall FFC connector and cable drop into this notch on the
# right side of the battery opening. Cirque's drawing and photo put the
# connector 12.5-18.4 mm out from the pad centre (PCB X 162.5-168.4, Y 118.6-
# 127.4) with its slot at 15.7-16.4 mm, so the notch runs to X 168.9 (case 18.9).
NOTCH = (161.0, 117.0, 168.9, 129.0)
# Existing underside copper in J2's new area is removed and re-joined by the
# router (anchors written next to the placed board as <output>.rejoin.json).
REROUTE_BOX = (165.5, 116.0, 178.0, 131.5)
# JLCPCB-realistic clearances applied before the ground pour is refilled.
EDGE_CLEARANCE_MM, HOLE_CLEARANCE_MM = 0.2, 0.25
NOTCH_RADIUS = 0.6
NEW_NETS = ('SDA', 'SCL', 'DR', 'VCC_SW', 'LED_DATA', 'LED_DIN', 'VBAT', 'VBAT_SW')
# Ground stubs and vias that only served the old centre LED1/C1/R2 pads.
OLD_LED_GND_BOX = (151.0, 100.5, 155.5, 108.0)
FOOTPRINTS = {
    'R1': (os.path.join(KICAD_FP, 'Resistor_SMD.pretty'), 'R_0603_1608Metric'),
    'R2': (os.path.join(KICAD_FP, 'Resistor_SMD.pretty'), 'R_0603_1608Metric'),
    'R3': (os.path.join(KICAD_FP, 'Resistor_SMD.pretty'), 'R_0603_1608Metric'),
    'R4': (os.path.join(KICAD_FP, 'Resistor_SMD.pretty'), 'R_0603_1608Metric'),
    'C2': (os.path.join(KICAD_FP, 'Capacitor_SMD.pretty'), 'C_0603_1608Metric'),
    'J2': (LOCAL_FP, 'JUSHUO_AFC01-S12FCA-00_1x12-1MP_P0.50mm_Horizontal'),
}

P = lambda x, y: p.VECTOR2I(p.FromMM(x), p.FromMM(y))
mm = lambda q: (q.x / 1e6, q.y / 1e6)


def netlist(path):
    comps, nets = {}, {}
    root = ET.parse(path).getroot()
    for c in root.iter('comp'):
        fields = {f.get('name'): f.text for f in c.iter('field')}
        comps[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'),
                               'lcsc': fields.get('LCSC'), 'path': c.find('sheetpath').get('tstamps') + c.findtext('tstamps')}
    for n in root.iter('net'):
        name = n.get('name').lstrip('/')
        for node in n.iter('node'):
            nets[(node.get('ref'), node.get('pin'))] = name
    return comps, nets


def net(board, name):
    item = board.FindNet(name)
    if item is None:
        item = p.NETINFO_ITEM(board, name)
        board.Add(item)
    return item


def load_footprints():
    # PCB_IO_MGR.FindPlugin confuses KiCad 10's SWIG types for later board
    # objects; the S-expression reader class can be used directly.
    io = p.PCB_IO_KICAD_SEXPR()
    loaded = {}
    for ref, (lib, name) in FOOTPRINTS.items():
        fp = io.FootprintLoad(lib, name)
        assert fp, (lib, name)
        nickname = 'NanoWireless' if lib == LOCAL_FP else os.path.basename(lib).rsplit('.', 1)[0]
        fp.SetFPID(p.LIB_ID(nickname, name))
        fp.SetReference(ref)
        loaded[ref] = fp
    return loaded


def place(args):
    loaded = load_footprints()
    b = p.LoadBoard(args.input)
    comps, nets = netlist(args.netlist)
    # Collect every proxy first: after b.Remove() KiCad 10's SWIG wrapper
    # returns untyped objects from later GetFootprints()/GetTracks() calls.
    footprints = list(b.GetFootprints())
    def old_led_ground(t):
        x0, y0, x1, y1 = OLD_LED_GND_BOX
        return t.GetNetname() == 'gnd' and all(x0 < q.x / 1e6 < x1 and y0 < q.y / 1e6 < y1
                                               for q in (t.GetStart(), t.GetEnd()))
    tracks = list(b.GetTracks())
    old_copper = [t for t in tracks if t.GetNetname() in NEW_NETS or old_led_ground(t)]
    in_the_way = [t for t in tracks if t not in old_copper and t.GetNetname() and in_reroute_box(t)]
    rejoin = rejoin_anchors(b, tracks, in_the_way, footprints)
    old_parts = [fp for fp in footprints if fp.GetReference() in ('R1', 'R2')]
    drawings = [d for d in b.GetDrawings() if isinstance(d, p.PCB_SHAPE)]
    artwork = [d for d in drawings if d.GetShape() == p.SHAPE_T_POLY and d.GetLayer() in (p.F_SilkS, p.B_SilkS)]
    # The imported artwork carries a 300 x 200 mm page frame (both sides) and
    # an empty sliver polygon outside the board; drop them.
    board_box = b.GetBoardEdgesBoundingBox()
    frames = [d for d in artwork if not board_box.Contains(d.GetBoundingBox())]
    assert all(d.GetBoundingBox().GetWidth() > p.FromMM(250) or d.GetPolyShape().Area() < 1e6
               for d in frames), [d.GetBoundingBox().GetWidth() for d in frames]
    artwork = [d for d in artwork if all(d is not f for f in frames)]
    edge_cuts = [d for d in drawings if d.GetLayer() == p.Edge_Cuts]
    by_ref = {fp.GetReference(): fp for fp in footprints if fp not in old_parts}
    for fp in loaded.values():
        b.Add(fp)
    by_ref.update(loaded)
    for ref, fp in by_ref.items():
        if ref not in comps:
            continue
        c = comps[ref]
        fp.SetValue(c['value'])
        if c['lcsc']:
            fp.SetField('LCSC', c['lcsc'])
            for field in fp.GetFields():
                if field.GetName() == 'LCSC':
                    field.SetVisible(False)
                    field.SetLayer(p.F_Fab)
        if ref in PLACE:
            # Densely placed assembled parts: no silkscreen designators,
            # matching LED1 on the existing board.
            fp.Reference().SetVisible(False)
        fp.SetPath(p.KIID_PATH(c['path']))
        for pad in fp.Pads():
            # FFC fitting nails are mechanical only and stay unconnected.
            name = nets.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(net(b, name))
    for ref, (x, y, rot, side) in PLACE.items():
        fp = by_ref[ref]
        if side == 'B' and not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), p.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPosition(P(x, y))
        if rot is not None:
            fp.SetOrientationDegrees(rot)
    orient_ffc(by_ref['J2'])
    # Hot-swap sockets and SW38 are soldered by hand: no stencil paste, so
    # their pads don't come back from assembly with reflowed solder bumps.
    for ref, fp in by_ref.items():
        if ref.startswith('SW'):
            for pad in fp.Pads():
                if pad.GetAttribute() == p.PAD_ATTRIB_SMD:
                    layers = p.LSET(pad.GetLayerSet())
                    layers.RemoveLayer(p.F_Paste)
                    layers.RemoveLayer(p.B_Paste)
                    pad.SetLayerSet(layers)
    clear_artwork(artwork, by_ref)
    # Remove the centre LED circuit's copper (VCC_SW is rerouted in full)
    # and the axial resistors last.
    for item in old_copper + old_parts + in_the_way + frames:
        b.Remove(item)
    with open(args.output + '.rejoin.json', 'w') as f:
        json.dump(rejoin, f, indent=1)
    add_notch(b, edge_cuts)
    # Copper that stays (everything but the rerouted nets) must clear the notch.
    x0, y0, x1, y1 = NOTCH
    g = EDGE_CLEARANCE_MM
    keep = p.BOX2I(P(x0 - g, y0 - g), p.VECTOR2L(p.FromMM(x1 - x0 + 2 * g), p.FromMM(y1 - y0 + 2 * g)))
    removed = {id(t) for t in old_copper + in_the_way}
    near = [t.GetNetname() for t in tracks if id(t) not in removed and t.HitTest(keep, False)]
    near += [f'{fp.GetReference()}.{pd.GetNumber()}' for fp in by_ref.values() for pd in fp.Pads() if pd.HitTest(keep, False)]
    assert not near, near
    p.SaveBoard(args.output, b)
    assert os.path.exists(args.output), args.output
    print('placed', args.output)


def in_reroute_box(t):
    """True for B.Cu tracks/vias touching REROUTE_BOX (Liang-Barsky clip)."""
    x0, y0, x1, y1 = REROUTE_BOX
    if not t.IsOnLayer(p.B_Cu):
        return False
    (ax, ay), (bx, by) = mm(t.GetStart()), mm(t.GetEnd())
    dx, dy = bx - ax, by - ay
    lo, hi = 0.0, 1.0
    for pp, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if pp == 0:
            if q < 0:
                return False
            continue
        r = q / pp
        if pp < 0:
            lo = max(lo, r)
        else:
            hi = min(hi, r)
        if lo > hi:
            return False
    return True


def rejoin_anchors(b, tracks, removed, footprints):
    """Points where removed copper met copper that stays: {net: [[x, y, layers]]}."""
    out = {}
    removed_ids = {id(t) for t in removed}
    for t in removed:
        net = t.GetNetname()
        for q in {mm(t.GetStart()), mm(t.GetEnd())}:
            layers = None
            for o in tracks:
                if id(o) in removed_ids or o.GetNetname() != net:
                    continue
                if isinstance(o, p.PCB_VIA):
                    if math.dist(mm(o.GetPosition()), q) < 1e-3:
                        layers = ['F', 'B']
                elif any(math.dist(mm(e), q) < 1e-3 for e in (o.GetStart(), o.GetEnd())):
                    layers = layers or ['F' if o.GetLayer() == p.F_Cu else 'B']
            for fp in footprints:
                for pad in fp.Pads():
                    if pad.GetNetname() == net and pad.HitTest(P(*q)):
                        layers = ['F', 'B'] if pad.GetDrillSize().x > 0 else (layers or ['B'])
            if layers:
                anchors = out.setdefault(net, [])
                if not any(math.dist(a[:2], q) < 1e-3 for a in anchors):
                    anchors.append([round(q[0], 4), round(q[1], 4), layers])
    for net, anchors in out.items():
        assert len(anchors) >= 2, (net, anchors)
    return out


def fill(args):
    """Refill zones in a fresh process so the saved clearance rules apply."""
    b = p.LoadBoard(args.input)
    ds = b.GetDesignSettings()
    assert abs(ds.m_CopperEdgeClearance - p.FromMM(EDGE_CLEARANCE_MM)) < 10, ds.m_CopperEdgeClearance
    b.BuildConnectivity()
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(args.input, b)
    print('filled', args.input)


def dump(args):
    b = p.LoadBoard(args.input)
    dump_obstacles(b, args.obstacles)
    rejoin_path = args.input + '.rejoin.json'
    if os.path.exists(rejoin_path):
        data = json.load(open(args.obstacles))
        data['rejoin'] = {}
        for net, anchors in json.load(open(rejoin_path)).items():
            names = []
            for i, (x, y, layers) in enumerate(anchors):
                name = f'{net}@{i}'
                data['pads'][name] = {'xy': [x, y], 'net': net, 'layers': layers}
                names.append(name)
            data['rejoin'][net] = names
        json.dump(data, open(args.obstacles, 'w'))
    print('obstacles', args.obstacles)


def clear_artwork(artwork, by_ref):
    """Cut windows in the board-wide silkscreen artwork over the new parts."""
    groups = ((p.F_SilkS, ('LED1',)), (p.B_SilkS, ('C1', 'R1', 'R2')),
              (p.B_SilkS, ('J2', 'R3', 'R4', 'C2')), (p.B_SilkS, ('SW38',)))
    for layer, refs in groups:
        boxes = [by_ref[r].GetBoundingBox(False) for r in refs]
        x0 = min(bb.GetLeft() for bb in boxes) / 1e6 - 0.8
        y0 = min(bb.GetTop() for bb in boxes) / 1e6 - 0.8
        x1 = max(bb.GetRight() for bb in boxes) / 1e6 + 0.8
        y1 = max(bb.GetBottom() for bb in boxes) / 1e6 + 0.8
        window = p.SHAPE_POLY_SET(); window.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            window.Append(P(x, y))
        for d in artwork:
            if d.GetLayer() == layer:
                shape = p.SHAPE_POLY_SET(d.GetPolyShape())
                shape.BooleanSubtract(window)
                d.SetPolyShape(shape)


def orient_ffc(fp):
    """Point J2's FFC entry (the side away from its signal pads) at the notch."""
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        sig = [mm(pd.GetPosition())[0] for pd in fp.Pads() if pd.GetNumber() != 'MP']
        mp = [mm(pd.GetPosition())[0] for pd in fp.Pads() if pd.GetNumber() == 'MP']
        if sum(mp) / len(mp) < sum(sig) / len(sig) - 2:
            return
    raise AssertionError('No J2 orientation faces the notch')


def add_notch(b, edge_cuts):
    """Extend the battery opening's right edge (X=161) with a rectangular notch."""
    x0, y0, x1, y1 = NOTCH
    r = NOTCH_RADIUS
    edge = [d for d in edge_cuts if d.GetShape() == p.SHAPE_T_SEGMENT
            and abs(mm(d.GetStart())[0] - x0) < 1e-3 and abs(mm(d.GetEnd())[0] - x0) < 1e-3]
    assert len(edge) == 1, len(edge)
    edge = edge[0]
    ya, yb = sorted((mm(edge.GetStart())[1], mm(edge.GetEnd())[1]))
    assert ya < y0 and y1 < yb, (ya, yb)
    edge.SetStart(P(x0, ya)); edge.SetEnd(P(x0, y0))
    def seg(a, z):
        s = p.PCB_SHAPE(b); s.SetShape(p.SHAPE_T_SEGMENT); s.SetLayer(p.Edge_Cuts); s.SetWidth(edge.GetWidth())
        s.SetStart(P(*a)); s.SetEnd(P(*z)); b.Add(s)
    def arc(a, m, z):
        s = p.PCB_SHAPE(b); s.SetShape(p.SHAPE_T_ARC); s.SetLayer(p.Edge_Cuts); s.SetWidth(edge.GetWidth())
        s.SetArcGeometry(P(*a), P(*m), P(*z)); b.Add(s)
    k = r * (1 - 2 ** -0.5)
    seg((x0, y1), (x0, yb))
    seg((x0, y0), (x1 - r, y0))
    arc((x1 - r, y0), (x1 - k, y0 + k), (x1, y0 + r))
    seg((x1, y0 + r), (x1, y1 - r))
    arc((x1, y1 - r), (x1 - k, y1 - k), (x1 - r, y1))
    seg((x1 - r, y1), (x0, y1))


def poly_points(poly):
    out = []
    for i in range(poly.OutlineCount()):
        o = poly.Outline(i)
        out.append([mm(o.CPoint(k)) for k in range(o.PointCount())])
    return out


def dump_obstacles(b, path):
    """Copper of every net (with its name), keep-outs and the board outline."""
    data = {'items': [], 'keepouts': [], 'outline': [], 'holes': [], 'pads': {}, 'smd': []}
    layers = {'F': p.F_Cu, 'B': p.B_Cu}
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            for side, layer in layers.items():
                if pad.IsOnLayer(layer):
                    poly = p.SHAPE_POLY_SET()
                    pad.TransformShapeToPolygon(poly, layer, 0, p.FromMM(0.005), p.ERROR_INSIDE)
                    data['items'].append({'layer': side, 'net': pad.GetNetname(), 'poly': poly_points(poly)})
                    if pad.GetDrillSize().x == 0:
                        # Vias must stay out of solder pads of any net.
                        data['smd'].append({'layer': side, 'poly': poly_points(poly)})
            if pad.GetDrillSize().x > 0:
                data['holes'].append({'xy': mm(pad.GetPosition()), 'r': pad.GetDrillSize().x / 2e6,
                                      'net': pad.GetNetname()})
            key = f'{fp.GetReference()}.{pad.GetNumber()}'
            data['pads'][key] = {'xy': mm(pad.GetPosition()), 'net': pad.GetNetname(),
                                 'layers': [s for s, l in layers.items() if pad.IsOnLayer(l)]}
    for t in b.GetTracks():
        for side, layer in layers.items():
            if t.IsOnLayer(layer):
                poly = p.SHAPE_POLY_SET()
                t.TransformShapeToPolygon(poly, layer, 0, p.FromMM(0.005), p.ERROR_INSIDE)
                data['items'].append({'layer': side, 'net': t.GetNetname(), 'poly': poly_points(poly)})
        if isinstance(t, p.PCB_VIA):
            data['holes'].append({'xy': mm(t.GetPosition()), 'r': t.GetDrill() / 2e6, 'net': t.GetNetname()})
    for z in b.Zones():
        if z.GetIsRuleArea():
            poly = z.Outline()
            data['keepouts'].append(poly_points(poly))
    outline = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline, False)
    o = outline.Outline(0)
    data['outline'] = [mm(o.CPoint(k)) for k in range(o.PointCount())]
    data['cutouts'] = [[mm(outline.Hole(0, h).CPoint(k)) for k in range(outline.Hole(0, h).PointCount())]
                       for h in range(outline.HoleCount(0))]
    with open(path, 'w') as f:
        json.dump(data, f)


def photo_keepouts(args):
    """Underside mask openings, part silkscreen, holes, vias and J2 for the photo."""
    b = p.LoadBoard(args.input)
    out = {'openings': [], 'holes': [], 'blank': []}
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.IsOnLayer(p.B_Mask):
                poly = p.SHAPE_POLY_SET()
                pad.TransformShapeToPolygon(poly, p.B_Mask, pad.GetSolderMaskExpansion(p.B_Mask),
                                            p.FromMM(0.005), p.ERROR_OUTSIDE)
                out['openings'] += poly_points(poly)
            if pad.GetDrillSize().x > 0:
                out['holes'].append([*mm(pad.GetPosition()), max(pad.GetDrillSize().x, pad.GetDrillSize().y) / 2e6])
        # Part outlines and markings stay readable: the photo keeps off them too.
        for item in list(fp.GraphicalItems()) + [fp.Reference(), fp.Value()]:
            if item.GetLayer() != p.B_SilkS or (isinstance(item, p.PCB_TEXT) and not item.IsVisible()):
                continue
            poly = p.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(poly, p.B_SilkS, 0, p.FromMM(0.005), p.ERROR_OUTSIDE)
            out['openings'] += poly_points(poly)
        if fp.GetReference() == 'J2':
            # Fine-pitch FFC: no ink anywhere near the stencil or its 0.2 mm mask webs.
            out['blank'] += poly_points(fp.GetCourtyard(p.B_CrtYd))
    for t in b.GetTracks():
        if isinstance(t, p.PCB_VIA):
            # Tented, but ink over the via's bump prints badly.
            out['holes'].append([*mm(t.GetPosition()), t.GetWidth(p.B_Cu) / 2e6])
    with open(args.output, 'w') as f:
        json.dump(out, f)
    print('photo keep-outs', args.output, {k: len(v) for k, v in out.items()})


def apply(args):
    b = p.LoadBoard(args.input)
    routes = json.load(open(args.routes))
    layer = {'F': p.F_Cu, 'B': p.B_Cu}
    for r in routes['tracks']:
        t = p.PCB_TRACK(b); t.SetStart(P(*r['a'])); t.SetEnd(P(*r['b'])); t.SetWidth(p.FromMM(r['width']))
        t.SetLayer(layer[r['layer']]); t.SetNet(b.FindNet(r['net'])); b.Add(t)
    for v in routes['vias']:
        via = p.PCB_VIA(b); via.SetPosition(P(*v['xy'])); via.SetWidth(p.FromMM(v['size'])); via.SetDrill(p.FromMM(v['drill']))
        via.SetNet(b.FindNet(v['net'])); b.Add(via)
    ds = b.GetDesignSettings()
    ds.m_CopperEdgeClearance = p.FromMM(EDGE_CLEARANCE_MM)
    ds.m_HoleClearance = p.FromMM(HOLE_CLEARANCE_MM)
    b.BuildConnectivity()
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(args.output, b)
    assert os.path.exists(args.output), args.output
    print('routed', args.output, len(routes['tracks']), 'tracks', len(routes['vias']), 'vias')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('place'); a.add_argument('--input', required=True); a.add_argument('--netlist', required=True)
    a.add_argument('--output', required=True)
    a = sub.add_parser('dump'); a.add_argument('--input', required=True); a.add_argument('--obstacles', required=True)
    a = sub.add_parser('fill'); a.add_argument('--input', required=True)
    a = sub.add_parser('photo-keepouts'); a.add_argument('--input', required=True); a.add_argument('--output', required=True)
    a = sub.add_parser('apply'); a.add_argument('--input', required=True); a.add_argument('--routes', required=True)
    a.add_argument('--output', required=True)
    args = ap.parse_args()
    {'place': place, 'dump': dump, 'apply': apply, 'fill': fill, 'photo-keepouts': photo_keepouts}[args.cmd](args)
    sys.stdout.flush()
    os._exit(0)
