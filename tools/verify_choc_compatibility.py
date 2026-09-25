#!/usr/bin/env python3
"""Check the Endgame switch geometry and fixed mechanical interfaces.

Standard-library only. Run from any directory; --baseline defaults to the
upstream commit used for this revision. KiCad DRC is a separate required check.
"""
import argparse
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def blocks(text, name, depth=1):
    """Read KiCad's canonical indented forms without rewriting unrelated data."""
    pattern = r'(?m)^' + r'\t' * depth + r'\(' + name + r'(?=\s)'
    for match in re.finditer(pattern, text):
        end = text.index('\n' + '\t' * depth + ')', match.start()) + depth + 2
        yield text[match.start():end]


def field(text, name, depth):
    match = re.search(r'(?m)^' + '\t' * depth + r'\(' + name + r' ([^\n]*)\)', text)
    return match.group(1) if match else None


def coords(text, name, depth):
    return tuple(float(x) for x in field(text, name, depth).split())


def uuid(text, depth):
    return field(text, 'uuid', depth).strip('"')


def footprints(text):
    return {uuid(f, 2): f for f in blocks(text, 'footprint')}


def pads(fp):
    return {uuid(p, 3): p for p in blocks(fp, 'pad', 2)}


def close(a, b, tolerance=1e-6):
    return len(a) == len(b) and all(abs(x-y) < tolerance for x, y in zip(a, b))


def check(board, old):
    assert field(board, 'version', 1) == field(old, 'version', 1), 'Unexpected format migration'
    assert list(blocks(board, 'general')) == list(blocks(old, 'general')), 'Board thickness changed'
    for name in ('gr_line', 'gr_arc', 'gr_circle', 'gr_rect', 'gr_poly'):
        before = [b for b in blocks(old, name) if '(layer "Edge.Cuts")' in b]
        after = [b for b in blocks(board, name) if '(layer "Edge.Cuts")' in b]
        assert before == after, 'Board outline/cutouts changed'
    before, after = footprints(old), footprints(board)
    assert before.keys() == after.keys(), 'Component set changed'
    switches = 0
    for ident, f in after.items():
        original = before[ident]
        if 'SW_choc_v1_v2_HS_' not in f.splitlines()[0]:
            assert f == original, 'Non-switch footprint changed'
            continue
        switches += 1
        assert field(f, 'at', 2) == field(original, 'at', 2), 'Switch moved/rotated'
        assert field(f, 'layer', 2) == field(original, 'layer', 2), 'Switch flipped'
        pp, op = pads(f), pads(original)
        assert len(pp) == len(op) + 1, 'Unexpected pad count'
        extra = [p for ident, p in pp.items() if ident not in op]
        assert len(extra) == 1 and 'np_thru_hole oval' in extra[0]
        slot = extra[0]
        assert close(coords(slot, 'at', 3)[:2], (-5, 5.15)), 'Slot position/handedness'
        assert close(coords(slot, 'size', 3), (1.5, 2)), 'Slot size'
        assert field(slot, 'drill', 3) == 'oval 1.5 2', 'Slot drill'
        angle = coords(f, 'at', 2)
        angle = angle[2] if len(angle) == 3 else 0
        slot_angle = coords(slot, 'at', 3)[2]
        assert abs(math.remainder(slot_angle-angle, 180)) < 1e-6, 'Slot rotation'
        centers = vias = 0
        for ident, p in op.items():
            q = pp[ident]
            if 'np_thru_hole circle' in p and close(coords(p, 'at', 3)[:2], (0, 0)):
                centers += 1
                assert field(q, 'drill', 3) == '5'
                assert coords(q, 'size', 3) == (5, 5)
            elif '(pad "2" thru_hole circle' in p and field(p, 'drill', 3) == '1.27':
                vias += 1
                assert close(coords(q, 'at', 3)[:2], (-5, 3.5))
                assert field(q, 'drill', 3) == '0.3'
                assert coords(q, 'size', 3) == (0.6, 0.6)
                assert field(q, 'net', 3) == field(p, 'net', 3), 'Via net changed'
            else:
                assert p == q, 'Existing socket or V1 locating pad changed'
        assert centers == vias == 1
    assert switches == 36, f'Expected 36 switches, found {switches}'
    return switches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', default='b66038b')
    args = parser.parse_args()
    for path in sorted(ROOT.glob('001 PCB/KICAD/*/*.kicad_pcb')):
        relative = path.relative_to(ROOT).as_posix()
        old = subprocess.check_output(['git', 'show', f'{args.baseline}:{relative}'], cwd=ROOT, text=True)
        count = check(path.read_text(), old)
        print(f'{path.name}: {count} V1/V2 footprints; mechanical interfaces and other components unchanged')
    case = ROOT / '002 CASE/TheENDGAME2024_CASE001.step'
    old = subprocess.check_output(['git', 'show', f'{args.baseline}:{case.relative_to(ROOT).as_posix()}'], cwd=ROOT)
    assert old == case.read_bytes(), 'Case model changed'
    print('Existing case STEP unchanged')


if __name__ == '__main__':
    main()
