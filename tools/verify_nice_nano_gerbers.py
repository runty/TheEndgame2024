#!/usr/bin/env python3
"""Independently check the wireless ZIP against the source drill inventory.

Requires gerbonara 1.6.3. The manifest is produced by verify_nice_nano_pcb.py from
the final, refilled PCB. A matching checksum prevents use of a stale manifest.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import tempfile
import zipfile
from gerbonara.layers import LayerStack
from gerbonara.graphic_objects import Flash, Line, Arc

ROOT=Path(__file__).resolve().parents[1]


def near(a,b):
    return math.dist(a,b)<0.002


def contour_bounds(objects):
    vertices=[]; adjacency=defaultdict(list)
    def index(point):
        for i,p in enumerate(vertices):
            if near(p,point):
                return i
        vertices.append(point)
        return len(vertices)-1
    for item in objects:
        assert isinstance(item,(Line,Arc)), type(item).__name__
        a=index((item.x1,item.y1)); b=index((item.x2,item.y2))
        assert a!=b, 'Degenerate outline segment'
        adjacency[a].append(b); adjacency[b].append(a)
    assert all(len(v)==2 for v in adjacency.values()), 'Open or branched outline'
    remaining=set(adjacency); bounds=[]
    while remaining:
        pending=[remaining.pop()]; component=[]; member_ids=set()
        while pending:
            v=pending.pop(); component.append(vertices[v]); member_ids.add(v)
            for nxt in adjacency[v]:
                if nxt in remaining:
                    remaining.remove(nxt); pending.append(nxt)
        # Arc extrema can lie between their endpoints. Remove each plotted
        # stroke's radius to measure the routed profile centreline, not ink.
        boxes=[]
        for item in objects:
            if index((item.x1,item.y1)) not in member_ids:
                continue
            (x0,y0),(x1,y1)=item.bounding_box()
            radius=item.aperture.diameter/2
            boxes.append((x0+radius,y0+radius,x1-radius,y1-radius))
        bounds.append([min(b[0] for b in boxes),min(b[1] for b in boxes),
                       max(b[2] for b in boxes),max(b[3] for b in boxes)])
    return bounds


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--render',type=Path)
    args=ap.parse_args()
    manifest=json.loads(args.manifest.read_text())
    board=ROOT / manifest['source_board']
    assert hashlib.sha256(board.read_bytes()).hexdigest()==manifest['source_sha256']
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(args.archive) as archive:
            assert archive.testzip() is None
            assert len(archive.namelist())==10
            assert all(Path(n).name==n for n in archive.namelist())
            archive.extractall(tmp)
        stack=LayerStack.open(tmp)
        assert set(stack.graphic_layers)=={('top','copper'),('bottom','copper'),('top','mask'),
               ('bottom','mask'),('top','silk'),('bottom','silk'),('mechanical','outline')}
        drills={True:list(stack.drill_pth.objects),False:list(stack.drill_npth.objects)}
        counts={k:len(v) for k,v in drills.items()}
        for expected in manifest['drills']:
            candidates=drills[expected['plated']]
            def matches(item):
                if abs(item.aperture.diameter-expected['diameter_mm'])>1e-6:
                    return False
                if 'ends_mm' not in expected:
                    return isinstance(item,Flash) and near((item.x,item.y),expected['center_mm'])
                if not isinstance(item,Line):
                    return False
                a,b=expected['ends_mm']; x=(item.x1,item.y1); y=(item.x2,item.y2)
                return (near(x,a) and near(y,b)) or (near(x,b) and near(y,a))
            hits=[i for i,item in enumerate(candidates) if matches(item)]
            assert len(hits)==1, (expected,len(hits),'drill mismatch')
            candidates.pop(hits[0])
        assert not drills[True] and not drills[False], 'Unexpected exported drills'
        bounds=contour_bounds(stack.graphic_layers['mechanical','outline'].objects)
        assert len(bounds)==2, ('Expected perimeter plus one closed cutout',bounds)
        for expected in ([139,-144,161,-109],):
            assert any(max(abs(a-b) for a,b in zip(expected,v))<0.01 for v in bounds), expected
        switches=[d for d in manifest['drills'] if d['ref'].startswith('SW') and d['diameter_mm']>=1.5 and not d['plated']]
        counts_switch=Counter(round(d['diameter_mm'],3) for d in switches)
        assert counts_switch=={5.0:36,1.7:72,1.5:36}
        outer=max(bounds,key=lambda b:(b[2]-b[0])*(b[3]-b[1]))
        result={'archive':args.archive.name,'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
                'source_sha256':manifest['source_sha256'],'graphic_layers':7,
                'plated_drills':counts[True],'nonplated_drills_and_slots':counts[False],
                'all_drills_registered_to_source':True,'registration_tolerance_mm':0.002,
                'closed_outline_contours':2,'outline_contour_bounds_mm':bounds,
                'board_dimensions_mm':[outer[2]-outer[0],outer[3]-outer[1]],
                'switch_center_holes_5mm':36,'v1_locators_1_7mm':72,'v2_slots_1_5_by_2mm':36,
                'parser':'Gerbonara 1.6.3'}
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        if args.render:
            args.render.write_text(str(stack.to_pretty_svg(side='top')))
        print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
