#!/usr/bin/env python3
"""Independently parse the manufacturing ZIP and check its V1/V2 drills.

Requires gerbonara (validated with 1.6.3). Checks the ZIP itself, not loose files.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import tempfile
import zipfile
from gerbonara.layers import LayerStack
from gerbonara.graphic_objects import Flash, Line
from verify_choc_compatibility import ROOT, blocks, coords

OUTPUT = ROOT / '001 PCB/GERBER/CHOC V1 V2'
ARCHIVE = OUTPUT / 'TheEndgame2024_Choc_V1_V2_JLCPCB.zip'
BOARD = ROOT / '001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb'


def same(a, b):
    return math.dist(a, b) <= 0.002


def main():
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(ARCHIVE) as z:
            assert z.testzip() is None
            assert len(z.namelist()) == 10
            assert all(Path(n).name == n for n in z.namelist()), 'Unexpected nested files'
            z.extractall(tmp)
        stack = LayerStack.open(tmp)
        expected_layers = {('top', 'copper'), ('bottom', 'copper'), ('top', 'mask'),
                           ('bottom', 'mask'), ('top', 'silk'), ('bottom', 'silk'),
                           ('mechanical', 'outline')}
        assert set(stack.graphic_layers) == expected_layers
        npth = stack.drill_npth.objects
        assert Counter((type(o).__name__, round(o.aperture.diameter, 3)) for o in npth) == {
            ('Flash', 1.7): 72, ('Flash', 5.0): 36, ('Line', 1.5): 36}
        assert len(stack.drill_pth.objects) == 181
        checked = 0
        for fp in blocks(BOARD.read_text(), 'footprint'):
            if 'SW_choc_v1_v2_HS_' not in fp.splitlines()[0]:
                continue
            placement = coords(fp, 'at', 2)
            angle = math.radians(placement[2] if len(placement) == 3 else 0)
            c, s = math.cos(angle), math.sin(angle)
            def world(x, y):
                return (placement[0] + x*c + y*s, -(placement[1] - x*s + y*c))
            for x, y, diameter in ((0, 0, 5), (-5.5, 0, 1.7), (5.5, 0, 1.7)):
                matches = [o for o in npth if isinstance(o, Flash) and
                           abs(o.aperture.diameter-diameter) < 1e-6 and same((o.x, o.y), world(x, y))]
                assert len(matches) == 1, (placement, x, y, 'round drill not registered')
            start, end = world(-5, 4.9), world(-5, 5.4)
            slots = [o for o in npth if isinstance(o, Line) and
                     ((same((o.x1, o.y1), start) and same((o.x2, o.y2), end)) or
                      (same((o.x2, o.y2), start) and same((o.x1, o.y1), end)))]
            assert len(slots) == 1, (placement, 'slot position/orientation')
            assert abs(math.dist((slots[0].x1, slots[0].y1), (slots[0].x2, slots[0].y2)) - 0.5) < 0.002
            checked += 1
        assert checked == 36
        result = {
            'archive': ARCHIVE.name,
            'archive_sha256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
            'source_sha256': hashlib.sha256(BOARD.read_bytes()).hexdigest(),
            'parser': 'Gerbonara 1.6.3',
            'graphic_layers': len(stack.graphic_layers),
            'pth_holes': len(stack.drill_pth.objects),
            'npth_holes_and_slots': len(npth),
            'switch_positions_registered_to_source': checked,
            'center_holes_5mm': 36,
            'v1_locating_holes_1_7mm': 72,
            'v2_slots_1_5_by_2mm': 36,
            'position_tolerance_mm': 0.002,
            'gerber_outline_bounds_including_stroke_mm': stack.board_bounds(),
        }
        (ROOT / 'docs/validation/manufacturing.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
