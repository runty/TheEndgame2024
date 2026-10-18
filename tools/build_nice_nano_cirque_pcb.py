"""Place the Cirque-variant parts on the widened nice!nano PCB.

Run with KiCad's bundled Python (pcbnew), one subcommand per process:

  place  --input widened.kicad_pcb --netlist cirque.net --output placed.kicad_pcb
      Removes the centre LED circuit's copper, replaces axial R1/R2 with 0603
      parts, moves LED1/C1/R1/R2 to the right thumb gap, adds J2 (bottom-side
      FFC), R3/R4/C2, cuts the FFC notch and assigns nets and LCSC fields.
  dump   --input placed.kicad_pcb --obstacles obstacles.json
      Writes copper, keep-out and outline geometry for the router.
  apply  --input placed.kicad_pcb --routes routes.json --output final.kicad_pcb
      Adds the routed tracks and vias, refills zones and saves.

Coordinates are KiCad PCB millimetres; case frame = (X - 150, 140 - Y).
"""
import argparse
import json
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
    'C1': (LED_XY[0], LED_XY[1] - 3.9, 0, 'F'),
    'R1': (LED_XY[0] + 5.2, LED_XY[1] - 3.3, 90, 'F'),
    'R2': (LED_XY[0] + 5.2, LED_XY[1] + 0.4, 90, 'F'),
    'J2': (169.6, 123.0, None, 'B'),
    'R3': (168.6, 114.0, 90, 'B'),
    'R4': (170.6, 114.0, 90, 'B'),
    'C2': (166.0, 114.0, 0, 'B'),
}
# The pad's 4.1 mm-tall FFC connector and cable drop into this notch on the
# right side of the battery opening (case X 11..14.8, Y 12..22).
NOTCH = (161.0, 118.0, 164.8, 128.0)
NOTCH_RADIUS = 0.6
NEW_NETS = ('SDA', 'SCL', 'DR', 'VCC_SW', 'LED_DATA', 'LED_DIN')
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
    old_copper = [t for t in b.GetTracks() if t.GetNetname() in NEW_NETS or old_led_ground(t)]
    old_parts = [fp for fp in footprints if fp.GetReference() in ('R1', 'R2')]
    drawings = [d for d in b.GetDrawings() if isinstance(d, p.PCB_SHAPE)]
    artwork = [d for d in drawings if d.GetShape() == p.SHAPE_T_POLY and d.GetLayer() in (p.F_SilkS, p.B_SilkS)]
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
    clear_artwork(artwork, by_ref)
    # Remove the centre LED circuit's copper (VCC_SW is rerouted in full)
    # and the axial resistors last.
    for item in old_copper + old_parts:
        b.Remove(item)
    add_notch(b, edge_cuts)
    p.SaveBoard(args.output, b)
    assert os.path.exists(args.output), args.output
    print('placed', args.output)


def dump(args):
    b = p.LoadBoard(args.input)
    dump_obstacles(b, args.obstacles)
    print('obstacles', args.obstacles)


def clear_artwork(artwork, by_ref):
    """Cut windows in the board-wide silkscreen artwork over the new parts."""
    groups = ((p.F_SilkS, ('LED1', 'C1', 'R1', 'R2')), (p.B_SilkS, ('J2', 'R3', 'R4', 'C2')))
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
    data = {'items': [], 'keepouts': [], 'outline': [], 'holes': [], 'pads': {}}
    layers = {'F': p.F_Cu, 'B': p.B_Cu}
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            for side, layer in layers.items():
                if pad.IsOnLayer(layer):
                    poly = p.SHAPE_POLY_SET()
                    pad.TransformShapeToPolygon(poly, layer, 0, p.FromMM(0.005), p.ERROR_INSIDE)
                    data['items'].append({'layer': side, 'net': pad.GetNetname(), 'poly': poly_points(poly)})
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
    a = sub.add_parser('apply'); a.add_argument('--input', required=True); a.add_argument('--routes', required=True)
    a.add_argument('--output', required=True)
    args = ap.parse_args()
    {'place': place, 'dump': dump, 'apply': apply}[args.cmd](args)
    sys.stdout.flush()
    os._exit(0)
