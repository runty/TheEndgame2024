#!/usr/bin/env python3
"""Build and verify Endgame Choc V2 thumb caps. Requires OpenSCAD and trimesh/numpy."""
import argparse, hashlib, json, os, subprocess
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]

def verify():
    results={}
    for path in sorted(list((ROOT/'single-caps').glob('*.stl'))+list((ROOT/'upload').glob('*.stl'))):
        mesh=trimesh.load(path,force='mesh')
        count=len(mesh.split(only_watertight=False,repair=False))
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0 and count==1, path
        assert mesh.euler_number==(2 if path.parent.name=='single-caps' else -10), path
        results[str(path.relative_to(ROOT))]={
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'watertight':bool(mesh.is_watertight),'consistent_winding':bool(mesh.is_winding_consistent),
            'connected_components':count,'euler_number':int(mesh.euler_number),'triangles':len(mesh.faces),
            'bounds_mm':mesh.bounds.tolist(),'size_mm':mesh.extents.tolist(),'volume_mm3':float(mesh.volume)}
    assert len(results)==8, 'Expected six single-cap variants and two six-cap grids'
    (ROOT/'validation').mkdir(exist_ok=True)
    (ROOT/'validation'/'meshes.json').write_text(json.dumps(results,indent=2)+'\n')
    print('PASS: six single-cap variants and two grids, each one watertight solid.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--openscad',default='openscad');ap.add_argument('--x86-64',action='store_true');ap.add_argument('--verify-only',action='store_true');a=ap.parse_args()
    if not a.verify_only:
        env=os.environ.copy();env['OPENSCADPATH']=str(ROOT/'source'/'vendor'/'libraries')
        base=(['arch','-x86_64'] if a.x86_64 else [])+[a.openscad]
        logs=ROOT/'validation'/'build-logs';logs.mkdir(parents=True,exist_ok=True)
        def export(name,source,backend,fmt,defines):
            command=base+[f'--backend={backend}','--export-format',fmt,'-o',str(name)]
            for define in defines:command+=['-D',define]
            command+=[str(ROOT/'source'/source)]
            with (logs/(name.stem+'.log')).open('w') as log:subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        for profile in ['sculpted','convex']:
            for size in ['long','small']:
                name=f'{profile}-{size}'+('-left' if profile=='sculpted' else '')+'.stl'
                path=ROOT/'single-caps'/name
                export(path,'single.scad','CGAL','binstl',[f'profile="{profile}"',f'long={str(size=="long").lower()}'])
                if profile=='sculpted':
                    mesh=trimesh.load(path);mesh.apply_transform(np.diag([-1.,1,1,1]));mesh.export(path.with_name(name.replace('-left','-right')))
        for profile in ['sculpted','convex']:
            path=ROOT/'upload'/f'Endgame-{profile}-thumbs-4long-2small-grid.stl'
            export(path,'grid.scad','Manifold','binstl',[f'profile="{profile}"'])
            # Binary precision can collapse tiny facets into isolated zero-area sheets.
            # Remove only complete components with exactly zero surface area.
            mesh=trimesh.load(path)
            components=mesh.split(only_watertight=False,repair=False)
            solids=[c for c in components if c.area>0]
            assert len(solids)==1 and solids[0].is_watertight, path
            if len(components)>1:
                assert all(c.area==0 for c in components if c is not solids[0]), path
                solids[0].export(path)
    verify()
