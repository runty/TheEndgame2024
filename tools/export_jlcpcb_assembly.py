#!/usr/bin/env python3
"""Write JLCPCB assembly BOM and CPL files for parts carrying an LCSC field.

Uses kicad-cli's position export (absolute origin, matching the Gerbers from
export_jlcpcb.py) and the board's footprint fields. Only footprints with an
LCSC number are listed; hand-soldered parts are left out.
Run with any Python 3: python tools/export_jlcpcb_assembly.py --board X.kicad_pcb --output DIR
"""
import argparse
import csv
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path


def footprint_fields(board_text):
    """Reference -> {Value, Footprint, LCSC} from the .kicad_pcb text."""
    fields = {}
    for block in re.split(r'\n\t\(footprint ', board_text)[1:]:
        lib = block.split('"')[1]
        props = dict(re.findall(r'\(property "([^"]+)" "([^"]*)"', block))
        ref = props.get('Reference')
        if ref:
            fields[ref] = {'Value': props.get('Value', ''), 'Footprint': lib.split(':')[-1], 'LCSC': props.get('LCSC', '')}
    return fields


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--board', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--name', default=None, help='file stem; defaults to the board name')
    ap.add_argument('--kicad-cli', default=shutil.which('kicad-cli') or '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
    args = ap.parse_args()
    stem = args.name or args.board.stem
    args.output.mkdir(parents=True, exist_ok=True)
    fields = footprint_fields(args.board.read_text())
    assembled = {ref: f for ref, f in fields.items() if f['LCSC']}
    assert assembled, 'No footprints carry an LCSC field'

    with tempfile.TemporaryDirectory() as tmp:
        pos = Path(tmp) / 'pos.csv'
        subprocess.run([args.kicad_cli, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm',
                        '--side', 'both', '--output', str(pos), str(args.board)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        rows = list(csv.DictReader(pos.open()))
    placed = {r['Ref']: r for r in rows}
    missing = sorted(set(assembled) - set(placed))
    assert not missing, f'LCSC parts without a position: {missing}'

    with (args.output / f'{stem}_CPL.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for ref in sorted(assembled, key=natural):
            r = placed[ref]
            w.writerow([ref, f"{float(r['PosX']):.4f}mm", f"{float(r['PosY']):.4f}mm",
                        'Top' if r['Side'] == 'top' else 'Bottom', f"{float(r['Rot']):.1f}"])

    groups = defaultdict(list)
    for ref, f in assembled.items():
        groups[(f['Value'], f['Footprint'], f['LCSC'])].append(ref)
    with (args.output / f'{stem}_BOM.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (value, footprint, lcsc), refs in sorted(groups.items(), key=lambda g: natural(g[1][0])):
            w.writerow([value, ','.join(sorted(refs, key=natural)), footprint, lcsc])
    print(f'{len(assembled)} assembled parts ({len(groups)} BOM lines) -> {args.output}')


def natural(ref):
    m = re.match(r'([A-Za-z]+)(\d+)', ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


if __name__ == '__main__':
    main()
