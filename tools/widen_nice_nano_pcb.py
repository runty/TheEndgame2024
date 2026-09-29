"""Insert two 2 mm strips next to the centered tray of the nice!nano PCB.

The script preserves the X=138..162 mm center and translates each original
wing with its switches, diodes, mounts, copper, and reference geometry.
"""
import argparse
import math,os,sys,collections
import wx
app=wx.App(False)
import pcbnew as p
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input',required=True,help='Pre-widening nice!nano PCB source')
parser.add_argument('--output',required=True,help='Scratch widened PCB destination')
args=parser.parse_args()
assert os.path.realpath(args.input)!=os.path.realpath(args.output), 'Use a separate output'
SOURCE=args.input
OUTPUT=args.output
b=p.LoadBoard(SOURCE)
original_outline=p.SHAPE_POLY_SET()
assert b.GetBoardPolygonOutlines(original_outline,False)
original_bounds=original_outline.BBox()
assert abs(original_bounds.GetLeft()/1e6-40.5)<.1 and abs(original_bounds.GetRight()/1e6-259.5)<.1, 'Expected original 219 mm-wide board; refuse double widening'
P=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
mm=lambda q:(q.x/1e6,q.y/1e6)
shift=lambda x:(-2.0 if x<138-1e-7 else 2.0 if x>162+1e-7 else 0.0)
FIXED_CENTRAL_REFS={'U2','LED1','C1','R1','R2','J1','SW38'}
detached=[]
counts=collections.Counter()

for fp in b.GetFootprints():
 # The final electronics placements can extend beyond the split planes.
 # Their coordinates are deliberate and remain fixed with the center tray.
 if fp.GetReference() in FIXED_CENTRAL_REFS:continue
 x,y=mm(fp.GetPosition());dx=shift(x)
 if dx:
  fp.Move(P(dx,0));counts['footprints_'+('left' if dx<0 else 'right')]+=1

for tr in list(b.GetTracks()):
 if isinstance(tr,p.PCB_VIA):
  x,y=mm(tr.GetPosition());dx=shift(x)
  if dx:tr.Move(P(dx,0));counts['vias']+=1
 else:
  a=mm(tr.GetStart());z=mm(tr.GetEnd());da=shift(a[0]);dz=shift(z[0])
  if isinstance(tr,p.PCB_ARC):
   dm=shift(mm(tr.GetMid())[0]);assert da==dz==dm,(tr.GetNetname(),a,z,mm(tr.GetMid()))
  if da==dz:
   if da:tr.Move(P(da,0));counts['tracks_shifted']+=1
  else:
   cuts=[c for c in (138,162) if min(a[0],z[0])<c<max(a[0],z[0])]
   assert len(cuts)==1,(tr.GetNetname(),a,z,cuts)
   cut=cuts[0];u=(cut-a[0])/(z[0]-a[0]);at=(cut,a[1]+u*(z[1]-a[1]))
   def piece(x,y,old_uuid=False):
    item=p.PCB_TRACK(b);item.SetStart(P(*x));item.SetEnd(P(*y));item.SetWidth(tr.GetWidth());item.SetLayer(tr.GetLayer());item.SetNet(tr.GetNet());item.SetLocked(tr.IsLocked())
    if old_uuid:item.SetUuid(p.KIID(tr.m_Uuid.AsString()))
    b.Add(item)
   b.Remove(tr);detached.append(tr)
   aa=(a[0]+da,a[1]);bb=(z[0]+dz,z[1]);pa=(cut+da,at[1]);pb=(cut+dz,at[1])
   piece(aa,pa,True);piece(pa,pb);piece(pb,bb)
   counts['tracks_bridged']+=1

# Solve a KiCad arc exactly from its stored three points, then split at X=cut.
def circle(a,m,z):
 ax,ay=a;bx,by=m;cx,cy=z
 D=2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
 assert abs(D)>1e-9,(a,m,z)
 ux=((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/D
 uy=((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/D
 r=math.hypot(ax-ux,ay-uy)
 return ux,uy,r

def split_arc(a,m,z,cut):
 cx,cy,r=circle(a,m,z)
 ang=lambda q:math.atan2(q[1]-cy,q[0]-cx)
 aa,am,az=map(ang,(a,m,z));ccw=(az-aa)%(2*math.pi);cm=(am-aa)%(2*math.pi)
 sweep=ccw if cm<=ccw+1e-8 else ccw-2*math.pi
 assert abs(sweep)<2*math.pi-1e-6
 cand=[];v=(cut-cx)/r
 assert abs(v)<=1.000001,(a,m,z,cut,cx,r)
 for q in (math.acos(max(-1,min(1,v))),-math.acos(max(-1,min(1,v)))):
  u=((q-aa)%(2*math.pi))/sweep if sweep>0 else -((aa-q)%(2*math.pi))/sweep
  if 1e-6<u<1-1e-6:cand.append(u)
 assert len(cand)==1,(a,m,z,cut,cand,ccw,cm,sweep)
 u=cand[0]
 point=lambda t:(cx+r*math.cos(aa+sweep*t),cy+r*math.sin(aa+sweep*t))
 at=point(u)
 return ((a,point(u/2),at),(at,point((u+1)/2),z),at)

def add_line(layer,width,a,z):
 sh=p.PCB_SHAPE(b);sh.SetShape(p.SHAPE_T_SEGMENT);sh.SetLayer(layer);sh.SetWidth(width);sh.SetStart(P(*a));sh.SetEnd(P(*z));b.Add(sh)

def add_arc(layer,width,a,m,z):
 sh=p.PCB_SHAPE(b);sh.SetShape(p.SHAPE_T_ARC);sh.SetLayer(layer);sh.SetWidth(width);sh.SetArcGeometry(P(*a),P(*m),P(*z));b.Add(sh)

def reshape_crossing(dr,cut):
 a=mm(dr.GetStart());z=mm(dr.GetEnd());layer=dr.GetLayer();width=dr.GetWidth()
 if dr.GetShape()==p.SHAPE_T_SEGMENT:
  u=(cut-a[0])/(z[0]-a[0]);at=(cut,a[1]+u*(z[1]-a[1]));parts=((a,at),(at,z))
 elif dr.GetShape()==p.SHAPE_T_ARC:
  arc1,arc2,at=split_arc(a,mm(dr.GetArcMid()),z,cut);parts=(arc1,arc2)
 else:raise AssertionError((dr.GetShape(),a,z))
 for part in parts:
  dx=shift(sum(q[0] for q in part)/len(part))
  moved=[(q[0]+dx,q[1]) for q in part]
  if len(part)==2:add_line(layer,width,*moved)
  else:add_arc(layer,width,*moved)
 # Horizontal bridge between the translated and fixed sections.
 side=-2 if cut==138 else 2
 add_line(layer,width,(cut,at[1]),(cut+side,at[1]))
 detached.append(dr);b.Remove(dr)
 counts['split_'+p.LayerName(layer)]+=1

for dr in list(b.GetDrawings()):
 lay=dr.GetLayer()
 if lay not in (p.Edge_Cuts,p.User_8,p.Cmts_User):continue
 if lay==p.User_8 and dr.GetBoundingBox().GetWidth()/1e6>290:continue
 if lay==p.Cmts_User:
  x,y=mm(dr.GetPosition());dx=shift(x)
  if dx:dr.Move(P(dx,0));counts['comment_text']+=1
  continue
 if not isinstance(dr,p.PCB_SHAPE):continue
 # The battery opening and the two center mounting symbols remain fixed.
 if dr.GetShape() in (p.SHAPE_T_SEGMENT,p.SHAPE_T_ARC):
  a=mm(dr.GetStart());z=mm(dr.GetEnd())
  da=shift(a[0]);dz=shift(z[0])
  if da!=dz:
   cuts=[c for c in (138,162) if min(a[0],z[0])<c<max(a[0],z[0])]
   assert len(cuts)==1,(p.LayerName(lay),a,z,cuts)
   reshape_crossing(dr,cuts[0]);continue
  if da:dr.Move(P(da,0));counts['draw_'+p.LayerName(lay)]+=1
 elif dr.GetShape()==p.SHAPE_T_CIRCLE:
  x,y=mm(dr.GetCenter());dx=shift(x)
  if dx:dr.Move(P(dx,0));counts['draw_circle']+=1
 else:
  bb=dr.GetBoundingBox();x=(bb.GetLeft()+bb.GetRight())/2e6;dx=shift(x)
  if dx:dr.Move(P(dx,0));counts['draw_other']+=1

# The GND pour already encloses the expanded board; the antenna keepout stays centered.
outline=p.SHAPE_POLY_SET();ok=b.GetBoardPolygonOutlines(outline,False)
print('outline valid',ok,'outlines',outline.OutlineCount(),'holes',outline.HoleCount(0) if ok else None)
assert ok and outline.OutlineCount()==1 and outline.HoleCount(0)==1
bb=outline.BBox();print('bounds',mm(bb.GetOrigin()),mm(bb.GetEnd()))
assert abs(bb.GetLeft()/1e6-38.5)<.1 and abs(bb.GetRight()/1e6-261.5)<.1
print('counts',dict(counts))
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(OUTPUT,b)
print('saved',OUTPUT)
sys.stdout.flush();os._exit(0)
