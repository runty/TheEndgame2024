#!/usr/bin/env python3
"""Check nice!nano PCB geometry/netlist and export its expected drill inventory.

Use KiCad 10's pcbnew Python. ERC/DRC and Gerber parsing are separate checks.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import wx
APP = wx.App(False)
import pcbnew as p

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb'
BOARD = ROOT / '001 PCB/KICAD/NICE NANO WIRELESS/TheEndgame2024_NiceNano.kicad_pcb'


def xy(v):
    return [v.x/1e6,v.y/1e6]


def native_net_name(name):
    # XML unescapes the slash in these pin labels; PCB storage does not.
    return name.replace('/', '{slash}') if name.startswith('unconnected-(') else name


def pad_geometry(pad):
    return (pad.GetNumber(), pad.GetAttribute(), xy(pad.GetPosition()),
            xy(pad.GetSize()), xy(pad.GetDrillSize()), pad.GetShape(),
            pad.GetDrillShape(), round(pad.GetOrientationDegrees(),6),pad.GetNetname())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--netlist',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    old=p.LoadBoard(str(BASE)); board=p.LoadBoard(str(BOARD))
    before={f.m_Uuid.AsString():f for f in old.GetFootprints()}
    after={f.GetReference():f for f in board.GetFootprints()}
    by_uuid={f.m_Uuid.AsString():f for f in board.GetFootprints()}
    switch_refs=[f.GetReference() for f in before.values() if 'SW_choc_v1_v2_HS_' in f.GetFPIDAsString()]
    assert len(switch_refs)==36
    for ident,fp in before.items():
        ref=fp.GetReference()
        if ref in ('U2','BZ2'):
            continue
        new=by_uuid[ident]
        assert xy(fp.GetPosition())==xy(new.GetPosition()), (ref,'position changed')
        assert abs(fp.GetOrientationDegrees()-new.GetOrientationDegrees())<1e-6
        assert fp.GetLayer()==new.GetLayer()
        assert fp.GetFPIDAsString()==new.GetFPIDAsString()
        assert sorted(map(pad_geometry,fp.Pads()))==sorted(map(pad_geometry,new.Pads())), (ref,'pad changed')
    assert all(ref not in after for ref in ('BZ2','U3','C2','R3'))
    assert xy(after['SW38'].GetPosition())==[150.,154.]
    assert xy(after['J1'].GetPosition())==[148.,147.5]
    assert xy(after['LED1'].GetPosition())==[150.,103.5]
    assert after['U2'].GetFPIDAsString()=='NanoWireless:NiceNano_v2_PinPosts'
    assert board.GetDesignSettings().GetBoardThickness()==p.FromMM(1.6)
    netlist=ET.parse(args.netlist).getroot()
    # Upstream mechanical artwork uses repeated REF** placeholders; every
    # electrically annotated component must still have exactly one instance.
    for comp in netlist.findall('components/comp'):
        ref=comp.attrib['ref']
        assert sum(f.GetReference()==ref for f in board.GetFootprints())==1, (ref,'duplicate/missing')
    expected={(n.attrib['ref'],n.attrib['pin']):native_net_name(net.attrib['name'])
              for net in netlist.findall('nets/net') for n in net.findall('node')}
    actual={(f.GetReference(),a.GetNumber()):a.GetNetname()
            for f in board.GetFootprints() for a in f.Pads() if a.GetNumber()}
    for pin,net in expected.items():
        assert actual.get(pin)==net, (pin,net,actual.get(pin))
    for ref,pin,net in [('J1','1','VBAT'),('J1','2','gnd'),('SW38','2','VBAT'),
                        ('SW38','1','VBAT_SW'),('U2','24','VBAT_SW'),('U2','23','gnd'),('U2','21','VCC_SW'),('LED1','1','VCC_SW'),('LED1','3','gnd'),('LED1','4','LED_DIN')]:
        assert actual[ref,pin]==net
    outlines=p.SHAPE_POLY_SET()
    assert board.GetBoardPolygonOutlines(outlines,False)
    assert outlines.OutlineCount()==1 and outlines.HoleCount(0)==1
    host=p.LoadBoard(str(ROOT / '001 PCB/KICAD/XIAO WIRELESS/TheEndgame2024_XIAO.kicad_pcb'))
    host_outline=p.SHAPE_POLY_SET()
    assert host.GetBoardPolygonOutlines(host_outline,False)
    def vertices(chain):
        return sorted(tuple(xy(chain.CPoint(i))) for i in range(chain.PointCount()))
    assert vertices(outlines.COutline(0))==vertices(host_outline.COutline(0)), 'External profile changed'
    holes=[]
    for k in range(outlines.HoleCount(0)):
        h=outlines.CHole(0,k)
        pts=[xy(h.CPoint(i)) for i in range(h.PointCount())]
        bounds=[min(a[0] for a in pts),min(a[1] for a in pts),max(a[0] for a in pts),max(a[1] for a in pts)]
        holes.append(bounds)
    assert any(max(abs(a-b) for a,b in zip(h,[139,109,161,144]))<0.01 for h in holes)
    radio=[z for z in board.Zones() if z.GetIsRuleArea() and z.GetZoneName().startswith('nice!nano antenna')]
    assert len(radio)==1 and radio[0].GetDoNotAllowTracks() and radio[0].GetDoNotAllowVias() and radio[0].GetDoNotAllowZoneFills()
    assert radio[0].IsOnLayer(p.F_Cu) and radio[0].IsOnLayer(p.B_Cu)
    drills=[]
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            dx,dy=xy(pad.GetDrillSize())
            if dx==0:
                continue
            x,y=xy(pad.GetPosition()); angle=math.radians(pad.GetOrientationDegrees())
            item={'ref':fp.GetReference(),'pad':pad.GetNumber(),'plated':pad.GetAttribute()!=p.PAD_ATTRIB_NPTH,
                  'diameter_mm':min(dx,dy),'center_mm':[x,-y]}
            if abs(dx-dy)>1e-6:
                ax,ay=max(0,dx-dy)/2,max(0,dy-dx)/2
                vx,vy=ax*math.cos(angle)+ay*math.sin(angle),-ax*math.sin(angle)+ay*math.cos(angle)
                item['ends_mm']=[[x-vx,-y+vy],[x+vx,-y-vy]]
            drills.append(item)
    for via in board.GetTracks():
        if isinstance(via,p.PCB_VIA):
            x,y=xy(via.GetPosition())
            drills.append({'ref':'via','pad':'','plated':True,'diameter_mm':via.GetDrillValue()/1e6,'center_mm':[x,-y]})
    result={'source_board':str(BOARD.relative_to(ROOT)),
            'source_sha256':hashlib.sha256(BOARD.read_bytes()).hexdigest(),
            'baseline_sha256':hashlib.sha256(BASE.read_bytes()).hexdigest(),
            'switches_preserved':36,'matrix_diodes_preserved':36,
            'external_profile_matches_xiao_baseline':True,
            'netlist_terminals_matched':len(expected),'board_thickness_mm':1.6,
            'internal_cutout_bounds_mm':holes,'antenna_keepout_both_layers':True,
            'drills':drills}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(f'36 switches and diodes preserved; {len(expected)} terminals match XML; one internal cutout; {len(drills)} drills')


if __name__=='__main__':
    main()
