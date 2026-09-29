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


def wing_offset(x):
    return -2. if x<138. else 2. if x>162. else 0.


def pad_geometry(pad, dx=0.):
    point=xy(pad.GetPosition());point[0]=round(point[0]+dx,6)
    return (pad.GetNumber(), pad.GetAttribute(), point,
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
        position=xy(fp.GetPosition());dx=wing_offset(position[0])
        position[0]=round(position[0]+dx,6)
        assert position==xy(new.GetPosition()), (ref,'unexpected position change')
        assert abs(fp.GetOrientationDegrees()-new.GetOrientationDegrees())<1e-6
        assert fp.GetLayer()==new.GetLayer()
        assert fp.GetFPIDAsString()==new.GetFPIDAsString()
        assert sorted(pad_geometry(a,dx) for a in fp.Pads())==sorted(map(pad_geometry,new.Pads())), (ref,'pad changed')
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
    # The exact split/translate/bridge profile is independently checked by
    # verify_nice_nano_spacing.py against the captured pre-widening geometry.
    spacing_baseline=json.loads((ROOT/'docs/validation/nice-nano-pcb/spacing-baseline.json').read_text())
    assert vertices(host_outline.COutline(0))==sorted(map(tuple,spacing_baseline['source_outer_vertices_mm']))
    holes=[]
    for k in range(outlines.HoleCount(0)):
        h=outlines.CHole(0,k)
        pts=[xy(h.CPoint(i)) for i in range(h.PointCount())]
        bounds=[min(a[0] for a in pts),min(a[1] for a in pts),max(a[0] for a in pts),max(a[1] for a in pts)]
        holes.append(bounds)
    assert any(max(abs(a-b) for a,b in zip(h,[139,109,161,144]))<0.01 for h in holes)
    # Compare body centres, not the asymmetric pad/lead artwork.  X=150 is
    # the board's left/right symmetry axis; Y remains the front/back layout.
    outer_points=vertices(outlines.COutline(0))
    outer_x=[min(v[0] for v in outer_points),max(v[0] for v in outer_points)]
    board_center_x=sum(outer_x)/2
    assert abs(board_center_x-150.)<0.001
    assert max(abs(a-b) for a,b in zip(outer_x,[38.5,261.5]))<0.001
    def fab_center_x(fp):
        points=[xy(pos)[0] for g in fp.GraphicalItems()
                if g.GetLayer()==p.F_Fab and isinstance(g,p.PCB_SHAPE)
                for pos in (g.GetStart(),g.GetEnd())]
        assert points, (fp.GetReference(),'missing fabrication body')
        return (min(points)+max(points))/2
    header_x=sorted({xy(a.GetPosition())[0] for a in after['U2'].Pads()})
    assert header_x==[142.38,157.62]
    centres={'nice_nano_body':fab_center_x(after['U2']),
             'nice_nano_headers':sum(header_x)/2,
             'battery_opening':(holes[0][0]+holes[0][2])/2,
             'led_body':fab_center_x(after['LED1'])}
    for name,centre in centres.items():
        assert abs(centre-board_center_x)<0.001, (name,'off centre',centre,board_center_x)
    left=[after[ref] for ref in switch_refs if xy(after[ref].GetPosition())[0]<board_center_x]
    right=[after[ref] for ref in switch_refs if xy(after[ref].GetPosition())[0]>board_center_x]
    pairs=[]
    for fp in left:
        x,y=xy(fp.GetPosition())
        reflected=[2*board_center_x-x,y]
        mate=min(right,key=lambda f:math.dist(reflected,xy(f.GetPosition())))
        error=math.dist(reflected,xy(mate.GetPosition()))
        # A 180-degree switch turn leaves the rectangular cap envelope equal.
        angle_error=abs((fp.GetOrientationDegrees()+mate.GetOrientationDegrees()+90)%180-90)
        assert error<0.001 and angle_error<0.001, (fp.GetReference(),mate.GetReference(),error,angle_error)
        right.remove(mate)
        pairs.append({'left':fp.GetReference(),'right':mate.GetReference(),'center_mirror_error_mm':error})
    assert len(pairs)==18 and not right
    resistors={}
    for ref,locations in {'R1':{'1':[137.77,99.4],'2':[147.93,99.4]},
                          'R2':{'1':[162.23,107.6],'2':[152.07,107.6]}}.items():
        fp=after[ref]
        assert 'R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal' in fp.GetFPIDAsString()
        assert fp.GetLayer()==p.F_Cu
        pads=list(fp.Pads())
        assert len(pads)==2
        for pad in pads:
            assert pad.GetAttribute()==p.PAD_ATTRIB_PTH
            assert xy(pad.GetPosition())==locations[pad.GetNumber()]
            assert xy(pad.GetDrillSize())==[0.8,0.8]
        resistors[ref]={'footprint':fp.GetFPIDAsString(),'pad_centres_mm':locations,
                        'pitch_mm':10.16,'drill_mm':0.8,'body_nominal_mm':[6.3,2.5]}
    radio=[z for z in board.Zones() if z.GetIsRuleArea() and z.GetZoneName().startswith('nice!nano antenna')]
    assert len(radio)==1 and radio[0].GetDoNotAllowTracks() and radio[0].GetDoNotAllowVias() and radio[0].GetDoNotAllowZoneFills()
    assert radio[0].IsOnLayer(p.F_Cu) and radio[0].IsOnLayer(p.B_Cu)
    drills=[]
    track_widths=[t.GetWidth()/1e6 for t in board.GetTracks() if not isinstance(t,p.PCB_VIA)]
    assert min(track_widths)>=0.10, 'Track is below the 1 oz JLCPCB manufacturing floor'
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
            'key_half_translation_mm':{'left':-2.,'right':2.},
            'central_strip_preserved_x_mm':[138.,162.],
            'outer_width_increase_mm':4.,
            'minimum_track_width_mm':min(track_widths),'specified_copper_weight_oz':1,
            'netlist_terminals_matched':len(expected),'board_thickness_mm':1.6,
            'internal_cutout_bounds_mm':holes,'antenna_keepout_both_layers':True,
            'centering':{'board_outer_x_bounds_mm':outer_x,'board_center_x_mm':board_center_x,
                         'feature_center_x_mm':centres,'tolerance_mm':0.001},
            'axial_resistors':resistors,
            'mirrored_key_pairs':pairs,
            **spacing_baseline,
            'final_outer_vertices_mm':[xy(outlines.COutline(0).CPoint(i)) for i in range(outlines.COutline(0).PointCount())],
            'final_switches':[{'ref':ref,'x_mm':xy(after[ref].GetPosition())[0],
                              'y_mm':xy(after[ref].GetPosition())[1],
                              'angle_deg':after[ref].GetOrientationDegrees(),
                              'footprint':after[ref].GetFPIDAsString()} for ref in switch_refs],
            'final_central':{'u2_center_mm':xy(after['U2'].GetPosition()),
                             'led1_center_mm':xy(after['LED1'].GetPosition()),
                             'battery_opening_bounds_mm':holes[0]},
            'drills':drills}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(f'36 switches and diodes preserved; {len(expected)} terminals match XML; one internal cutout; {len(drills)} drills')


if __name__=='__main__':
    main()
