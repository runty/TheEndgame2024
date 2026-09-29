#!/usr/bin/env python3
"""Create a scratch nice!nano layout, preserving the validated XIAO key field.

Run with KiCad 10's pcbnew Python. This is a placement/retained-routing tool,
not a generator for the final hand-finished manufacturing PCB. Always supply
a scratch --output. The committed PCB is the authoritative final layout.
"""
import argparse
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import wx
APP = wx.App(False)
import pcbnew as p

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '001 PCB/KICAD/XIAO WIRELESS/TheEndgame2024_XIAO.kicad_pcb'
PROJECT = ROOT / '001 PCB/KICAD/NICE NANO WIRELESS'
LIBS = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
PLACEMENT = {'U2': (150,80,0), 'LED1': (150,103.5,0),
             'C1': (154.5,102,90), 'R1': (137.77,99.4,0), 'R2': (162.23,107.6,180)}

def vec(x,y):
    return p.VECTOR2I(p.FromMM(x),p.FromMM(y))

def mm(v):
    return (v.x/1e6,v.y/1e6)

def intersects(a,b,box):
    x0,y0,x1,y1=box
    dx,dy=b[0]-a[0],b[1]-a[1]
    lo,hi=0.,1.
    for d,q in ((-dx,a[0]-x0),(dx,x1-a[0]),(-dy,a[1]-y0),(dy,y1-a[1])):
        if abs(d)<1e-12:
            if q<0:return False
        elif d<0:lo=max(lo,q/d)
        else:hi=min(hi,q/d)
        if lo>hi:return False
    return True

def edge(board,a,b,mid=None):
    s=p.PCB_SHAPE(board);s.SetLayer(p.Edge_Cuts);s.SetWidth(p.FromMM(.05))
    if mid is None:
        s.SetShape(p.SHAPE_T_SEGMENT);s.SetStart(vec(*a));s.SetEnd(vec(*b))
    else:
        s.SetShape(p.SHAPE_T_ARC);s.SetArcGeometry(vec(*a),vec(*mid),vec(*b))
    board.Add(s)

def rounded_opening(board,x0,y0,x1,y1,r=1):
    edge(board,(x0+r,y0),(x1-r,y0));edge(board,(x1,y0+r),(x1,y1-r))
    edge(board,(x1-r,y1),(x0+r,y1));edge(board,(x0,y1-r),(x0,y0+r))
    q=r/math.sqrt(2)
    edge(board,(x1-r,y0),(x1,y0+r),(x1-r+q,y0+r-q))
    edge(board,(x1,y1-r),(x1-r,y1),(x1-r+q,y1-r+q))
    edge(board,(x0+r,y1),(x0,y1-r),(x0+r-q,y1-r+q))
    edge(board,(x0,y0+r),(x0+r,y0),(x0+r-q,y0+r-q))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--netlist',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--dsn',type=Path)
    args=ap.parse_args()
    assert args.output.resolve() != (PROJECT / 'TheEndgame2024_NiceNano.kicad_pcb').resolve(), 'Use a scratch output, not the final board'
    xml=ET.parse(args.netlist).getroot()
    comps={c.attrib['ref']:c for c in xml.findall('components/comp')}
    pins={(n.attrib['ref'],n.attrib['pin']):(net.attrib['name'].replace('/', '{slash}')
          if net.attrib['name'].startswith('unconnected-(') else net.attrib['name'])
          for net in xml.findall('nets/net') for n in net.findall('node')}
    names=set(pins.values())
    board=p.LoadBoard(str(BASE));detached=[]
    for fp in list(board.GetFootprints()):
        if fp.GetReference() in ('U2','U3','C1','C2','R1','R2','R3'):
            detached.append(fp);board.Remove(fp)
    removed=0
    for t in list(board.GetTracks()):
        if t.GetNetname() not in names or intersects(mm(t.GetStart()),mm(t.GetEnd()),(138.3,62,161.7,116.5)):
            detached.append(t);board.Remove(t);removed+=1
        else:t.SetLocked(True)
    for z in list(board.Zones()):
        if z.GetIsRuleArea():detached.append(z);board.Remove(z)
    # Both obsolete internal openings are entirely inside this rectangle.
    # The external USB-side edge at Y=62.5626 remains untouched.
    for d in list(board.GetDrawings()):
        if d.GetLayer()==p.Edge_Cuts and all(138.9<=x<=161.1 and 70<=y<=144.1 for x,y in (mm(d.GetStart()),mm(d.GetEnd()))):
            detached.append(d);board.Remove(d)
    rounded_opening(board,139,109,161,144)
    # Clear artwork at the controller, indicator, and new cutout.
    for bounds in ((139.8,62,160.2,108.75),(138.75,108.75,161.25,144.25)):
        x0,y0,x1,y1=bounds;window=p.SHAPE_POLY_SET();window.NewOutline()
        for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):window.Append(vec(x,y))
        for d in board.GetDrawings():
            if not isinstance(d,p.PCB_SHAPE) or d.GetShape()!=p.SHAPE_T_POLY or d.GetLayer() not in (p.F_SilkS,p.B_SilkS):continue
            b=d.GetBoundingBox()
            if b.GetRight()<p.FromMM(x0) or b.GetLeft()>p.FromMM(x1) or b.GetBottom()<p.FromMM(y0) or b.GetTop()>p.FromMM(y1):continue
            artwork=p.SHAPE_POLY_SET(d.GetPolyShape());artwork.BooleanSubtract(window);d.SetPolyShape(artwork)
    radio=p.ZONE(board);radio.SetIsRuleArea(True)
    layers=p.LSET();layers.AddLayer(p.F_Cu);layers.AddLayer(p.B_Cu);radio.SetLayerSet(layers)
    radio.SetDoNotAllowTracks(True);radio.SetDoNotAllowVias(True);radio.SetDoNotAllowZoneFills(True)
    radio.SetDoNotAllowPads(True);radio.SetDoNotAllowFootprints(False)
    radio.SetZoneName('nice!nano antenna: no host copper')
    poly=radio.Outline();poly.NewOutline()
    for x,y in ((144,86),(156,86),(156,98),(144,98)):poly.Append(vec(x,y))
    board.Add(radio)
    nets={n.GetNetname():n for n in board.GetNetInfo().NetsByNetcode().values()}
    for name in sorted(names):
        if name not in nets:
            n=p.NETINFO_ITEM(board,name);board.Add(n);nets[name]=n
    for ref,(x,y,angle) in PLACEMENT.items():
        comp=comps[ref];ident=comp.findtext('footprint');nick,name=ident.split(':',1)
        local=PROJECT/(nick+'.pretty');lib=local if local.exists() else LIBS/(nick+'.pretty')
        fp=p.FootprintLoad(str(lib),name);assert fp,ident
        fp.SetReference(ref);fp.SetValue(comp.findtext('value'));fp.SetFPIDAsString(ident)
        fp.GetField(p.FIELD_T_DATASHEET).SetText(comp.findtext('datasheet') or '')
        board.Add(fp);fp.SetPosition(vec(x,y));fp.SetOrientationDegrees(angle)
        fp.Value().SetVisible(False);fp.Reference().SetVisible(False)
    for fp in board.GetFootprints():
        ref=fp.GetReference()
        if ref in comps:
            comp=comps[ref];path=p.KIID_PATH()
            fp.SetFPIDAsString(comp.findtext('footprint'))
            ids=comp.find('sheetpath').attrib['tstamps'].strip('/').split('/')+comp.findtext('tstamps').split()
            for ident in ids:
                if ident:path.push_back(p.KIID(ident))
            fp.SetPath(path)
        for pad in fp.Pads():
            key=(ref,pad.GetNumber())
            if key in pins:pad.SetNet(nets[pins[key]])
        fp.SetLocked(True)
    board.BuildConnectivity()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    p.SaveBoard(str(args.output),board)
    if args.dsn:assert p.ExportSpecctraDSN(board,str(args.dsn))
    print(f'Created {args.output}; removed {removed} central or obsolete tracks/vias')

if __name__=='__main__':main()
