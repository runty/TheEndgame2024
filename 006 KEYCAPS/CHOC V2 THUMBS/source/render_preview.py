"""Orthographic software rendering of the actual STL triangles (no illustrative geometry)."""
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
def render(mesh, width=1200, height=650, underside=False):
    view=np.array([.20,-.75,-.85 if underside else .85]);view/=np.linalg.norm(view)
    right=np.cross([0,0,1],view);right/=np.linalg.norm(right);up=np.cross(view,right)
    basis=np.array([right,up,view]).T
    vertices=mesh.vertices@basis
    lo=vertices.min(0);hi=vertices.max(0);mid=(hi+lo)/2
    scale=min((width-100)/(hi[0]-lo[0]),(height-70)/(hi[1]-lo[1]))
    vertices=(vertices-mid)*scale;vertices[:,0]+=width/2;vertices[:,1]=height/2-vertices[:,1]
    pts=vertices[mesh.faces]; normals=mesh.face_normals
    visible=np.flatnonzero(normals@view>1e-8)
    light=np.array([-.4,-.5,.8 if not underside else -.8]);light/=np.linalg.norm(light)
    lighting=np.clip(.42+.58*np.maximum(normals@light,0),0,1)
    buffer=np.full((height,width),-np.inf)
    picture=np.full((height,width,3),[246,244,238],dtype=np.uint8)
    base=np.array([85,163,183])
    for i in visible:
        t=pts[i]; xmin,ymin=np.maximum(np.floor(t[:,:2].min(0)).astype(int),[0,0]);xmax,ymax=np.minimum(np.ceil(t[:,:2].max(0)).astype(int),[width-1,height-1])
        if xmin>xmax or ymin>ymax:continue
        a=t[1,:2]-t[0,:2];b=t[2,:2]-t[0,:2];den=a[0]*b[1]-a[1]*b[0]
        if abs(den)<1e-10:continue
        xx,yy=np.meshgrid(np.arange(xmin,xmax+1)+.5,np.arange(ymin,ymax+1)+.5)
        px=xx-t[0,0];py=yy-t[0,1];u=(px*b[1]-py*b[0])/den;v=(a[0]*py-a[1]*px)/den
        depth=t[0,2]+u*(t[1,2]-t[0,2])+v*(t[2,2]-t[0,2])
        region=buffer[ymin:ymax+1,xmin:xmax+1]
        mask=(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)&(depth>region)
        region[mask]=depth[mask];picture[ymin:ymax+1,xmin:xmax+1][mask]=np.clip(base*lighting[i],0,255).astype(np.uint8)
    return Image.fromarray(picture)
if __name__=='__main__':
    canvas=Image.new('RGB',(1200,1450),(246,244,238));draw=ImageDraw.Draw(canvas)
    try:font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',30)
    except OSError:font=ImageFont.load_default(size=30)
    for i,profile in enumerate(['sculpted','convex']):
        m=trimesh.load(ROOT/'upload'/f'Endgame-{profile}-thumbs-4long-2small-grid.stl')
        canvas.paste(render(m),(0,75+i*700))
        draw.text((50,30+i*700),f'{profile.title()} — 4 long + 2 small — Choc V2 / MX stem',font=font,fill=(30,50,60))
    canvas.save(ROOT/'connected-sets-preview.png')
    render(trimesh.load(ROOT/'upload'/'Endgame-sculpted-thumbs-4long-2small-grid.stl'),underside=True).save(ROOT/'underside-preview.png')
