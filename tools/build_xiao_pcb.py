#!/usr/bin/env python3
"""Create the wireless layout from the preserved wired board and XML netlist.

Run with KiCad 10's pcbnew Python. This creates placement and retained routing;
it does not reproduce the final hand-finished routing. Use a scratch --output
path, import a Specctra session with --session if desired, finish routing,
refill zones, and run the separate release checks afterward. The committed
KiCad PCB is the authoritative fabrication source.
"""
import argparse
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import wx
APP = wx.App(False)
import pcbnew as p

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / '001 PCB/KICAD/XIAO WIRELESS'
BASE = ROOT / '001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb'
BOARD = PROJECT / 'TheEndgame2024_XIAO.kicad_pcb'
LIBS = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
PLACEMENT = {
    'U2': (150, 74, 0), 'U3': (150, 101, 0),
    'C1': (155.5, 96, 90), 'C2': (155.5, 99, 90),
    'R1': (143, 96, 90), 'R2': (143, 99, 90), 'R3': (143, 102, 90),
    'J1': (148, 147.5, 0), 'SW38': (150, 154, 0),
}


def vec(x, y):
    return p.VECTOR2I(p.FromMM(x), p.FromMM(y))


def mm(v):
    return (v.x / 1e6, v.y / 1e6)


def intersects(a, b, box):
    """Closed segment/rectangle intersection (Liang–Barsky)."""
    x0, y0, x1, y1 = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    lo, hi = 0.0, 1.0
    for d, q in ((-dx, a[0]-x0), (dx, x1-a[0]),
                 (-dy, a[1]-y0), (dy, y1-a[1])):
        if abs(d) < 1e-12:
            if q < 0:
                return False
        elif d < 0:
            lo = max(lo, q/d)
        else:
            hi = min(hi, q/d)
        if lo > hi:
            return False
    return True


def edge(board, start, end, mid=None):
    shape = p.PCB_SHAPE(board)
    shape.SetLayer(p.Edge_Cuts)
    shape.SetWidth(p.FromMM(0.05))
    if mid is None:
        shape.SetShape(p.SHAPE_T_SEGMENT)
        shape.SetStart(vec(*start))
        shape.SetEnd(vec(*end))
    else:
        shape.SetShape(p.SHAPE_T_ARC)
        shape.SetArcGeometry(vec(*start), vec(*mid), vec(*end))
    board.Add(shape)


def rounded_opening(board, x0, y0, x1, y1, r=1):
    edge(board, (x0+r,y0), (x1-r,y0))
    edge(board, (x1,y0+r), (x1,y1-r))
    edge(board, (x1-r,y1), (x0+r,y1))
    edge(board, (x0,y1-r), (x0,y0+r))
    q = r / math.sqrt(2)
    edge(board, (x1-r,y0), (x1,y0+r), (x1-r+q,y0+r-q))
    edge(board, (x1,y1-r), (x1-r,y1), (x1-r+q,y1-r+q))
    edge(board, (x0+r,y1), (x0,y1-r), (x0+r-q,y1-r+q))
    edge(board, (x0,y0+r), (x0+r,y0), (x0+r-q,y0+r-q))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist', type=Path, required=True)
    parser.add_argument('--session', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='Scratch PCB destination')
    parser.add_argument('--dsn', type=Path)
    args = parser.parse_args()
    netlist = ET.parse(args.netlist).getroot()
    components = {c.attrib['ref']: c for c in netlist.findall('components/comp')}
    connections = {}
    for net in netlist.findall('nets/net'):
        for node in net.findall('node'):
            connections[(node.attrib['ref'], node.attrib['pin'])] = net.attrib['name']

    board = p.LoadBoard(str(BASE))
    # Retain detached SWIG objects until after saving. KiCad 10's bindings
    # otherwise discard type wrappers during garbage collection mid-edit.
    detached = []
    for fp in list(board.GetFootprints()):
        if fp.GetReference() in ('U2', 'BZ2'):
            detached.append(fp)
            board.Remove(fp)
    # Reroute the controller area, including both cross-board row branches.
    # Leave switch/diode routing elsewhere intact for independent comparison.
    removed = 0
    for track in list(board.GetTracks()):
        if track.GetNetname() == 'Sound' or intersects(
                mm(track.GetStart()), mm(track.GetEnd()), (138.8,62,161.2,94)):
            detached.append(track)
            board.Remove(track)
            removed += 1
        else:
            track.SetLocked(True)

    # Fill the obsolete RP2040 carrier notch with laminate. Its external end
    # points are retained exactly; the new USB opening is in the case.
    notch = []
    for shape in list(board.GetDrawings()):
        if shape.GetLayer() != p.Edge_Cuts:
            continue
        a, b = mm(shape.GetStart()), mm(shape.GetEnd())
        if all(143.49 <= v[0] <= 156.51 and v[1] < 84 for v in (a,b)):
            notch.append(shape)
    assert len(notch) == 15, len(notch)
    for shape in notch:
        detached.append(shape)
        board.Remove(shape)
    edge(board, (144.499997,62.562600), (155.500001,62.562601))
    rounded_opening(board, 139,116,161,144)

    # Trim the existing centre artwork around the new milled opening.
    silk_window = p.SHAPE_POLY_SET()
    silk_window.NewOutline()
    for x,y in ((138.75,115.75),(161.25,115.75),(161.25,144.25),(138.75,144.25)):
        silk_window.Append(vec(x,y))
    for shape in list(board.GetDrawings()):
        if not isinstance(shape,p.PCB_SHAPE) or shape.GetShape()!=p.SHAPE_T_POLY:
            continue
        if shape.GetLayer() not in (p.F_SilkS,p.B_SilkS):
            continue
        box = shape.GetBoundingBox()
        if box.GetRight()<p.FromMM(138.75) or box.GetLeft()>p.FromMM(161.25):
            continue
        if box.GetBottom()<p.FromMM(115.75) or box.GetTop()>p.FromMM(144.25):
            continue
        artwork = p.SHAPE_POLY_SET(shape.GetPolyShape())
        artwork.BooleanSubtract(silk_window)
        shape.SetPolyShape(artwork)

    # Engineering keepout around the Seeed module's ceramic antenna. Its
    # location comes from Seeed's PCB; these host margins are conservative,
    # not a manufacturer-qualified RF performance guarantee.
    radio = p.ZONE(board)
    radio.SetIsRuleArea(True)
    copper_layers = p.LSET()
    copper_layers.AddLayer(p.F_Cu)
    copper_layers.AddLayer(p.B_Cu)
    radio.SetLayerSet(copper_layers)
    radio.SetDoNotAllowTracks(True)
    radio.SetDoNotAllowVias(True)
    radio.SetDoNotAllowZoneFills(True)
    radio.SetDoNotAllowPads(False)
    radio.SetDoNotAllowFootprints(False)
    radio.SetZoneName('XIAO antenna: no host copper')
    polygon = radio.Outline()
    polygon.NewOutline()
    for x,y in ((143,78.5),(157,78.5),(157,85.2),(143,85.2)):
        polygon.Append(vec(x,y))
    board.Add(radio)

    nets = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}
    for name in sorted(set(connections.values())):
        if name not in nets:
            net = p.NETINFO_ITEM(board, name)
            board.Add(net)
            nets[name] = net
    for ref, (x,y,angle) in PLACEMENT.items():
        comp = components[ref]
        ident = comp.findtext('footprint')
        nick, name = ident.split(':',1)
        lib = PROJECT / (nick+'.pretty') if nick == 'Wireless' else LIBS / (nick+'.pretty')
        fp = p.FootprintLoad(str(lib), name)
        assert fp, f'Missing footprint {ident}'
        fp.SetReference(ref)
        fp.SetValue(comp.findtext('value'))
        fp.SetFPIDAsString(ident)
        board.Add(fp)
        fp.SetPosition(vec(x,y))
        fp.SetOrientationDegrees(angle)
        # KiCad XML gives hierarchical sheet UUID plus symbol UUID.
        path = p.KIID_PATH()
        ids = comp.find('sheetpath').attrib['tstamps'].strip('/').split('/')
        ids += comp.findtext('tstamps').split()
        for ident in ids:
            if ident:
                path.push_back(p.KIID(ident))
        fp.SetPath(path)
        fp.Value().SetVisible(False)
        if ref.startswith(('C','R')):
            fp.Reference().SetPosition(vec(x + (2.1 if x > 150 else -2.1),y))
            fp.Reference().SetTextAngle(p.EDA_ANGLE(90,p.DEGREES_T))
        elif ref == 'SW38':
            fp.Reference().SetPosition(vec(158,151))
        elif ref == 'U2':
            fp.Reference().SetVisible(False)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            name = connections.get((fp.GetReference(),pad.GetNumber()))
            if name is not None:
                pad.SetNet(nets[name])
    board.BuildConnectivity()
    if args.session:
        placements = {f.m_Uuid.AsString(): (p.VECTOR2I(f.GetPosition()), f.GetOrientationDegrees())
                      for f in board.GetFootprints()}
        assert p.ImportSpecctraSES(board, str(args.session)), 'Failed to import routing'
        # Specctra rounds placement to its 0.1 um grid. Restore the native
        # positions so switch and mounting geometry remain exactly unchanged.
        for fp in board.GetFootprints():
            position, angle = placements[fp.m_Uuid.AsString()]
            fp.SetPosition(position)
            fp.SetOrientationDegrees(angle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    p.SaveBoard(str(args.output), board)
    if args.dsn:
        assert p.ExportSpecctraDSN(board, str(args.dsn)), 'Failed to export routing input'
    print(f'Created {args.output}; removed {removed} old controller-area tracks/vias')


if __name__ == '__main__':
    main()
