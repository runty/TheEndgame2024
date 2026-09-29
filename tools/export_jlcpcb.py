#!/usr/bin/env python3
"""Export the final silkscreen PCB to a single JLCPCB Gerber/drill ZIP.

Requires KiCad CLI. Run KiCad DRC and verify_choc_compatibility.py first.
The output is regenerated from source; existing export folders are rejected.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / '001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--kicad-cli', default=shutil.which('kicad-cli') or '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
    ap.add_argument('--output', type=Path, required=True, help='New output directory')
    ap.add_argument('--board', type=Path, default=BOARD, help='Verified source PCB')
    ap.add_argument('--archive-name', default='TheEndgame2024_Choc_V1_V2_JLCPCB.zip')
    args = ap.parse_args()
    assert Path(args.archive_name).name == args.archive_name and args.archive_name.endswith('.zip')
    args.output.mkdir(parents=True, exist_ok=False)
    gerbers = args.output / 'gerbers'
    gerbers.mkdir()
    cli = args.kicad_cli
    subprocess.run([cli, 'pcb', 'export', 'gerbers', '--output', str(gerbers), '--layers',
                    'F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts',
                    '--no-x2', '--no-netlist', '--subtract-soldermask', '--disable-aperture-macros',
                    '--check-zones', str(args.board)], check=True)
    subprocess.run([cli, 'pcb', 'export', 'drill', '--output', str(gerbers),
                    '--format', 'excellon', '--drill-origin', 'absolute',
                    '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal',
                    '--excellon-oval-format', 'alternate', '--excellon-separate-th',
                    '--generate-report', '--report-path', str(args.output / 'drill-report.txt'),
                    str(args.board)], check=True)
    suffixes = {p.suffix.lower() for p in gerbers.iterdir()}
    assert {'.gtl', '.gbl', '.gts', '.gbs', '.gto', '.gbo', '.gm1', '.drl'} <= suffixes, suffixes
    drills = list(gerbers.glob('*.drl'))
    assert len(drills) == 2 and any('NPTH' in p.name for p in drills), 'Missing separate drill files'
    archive = args.output / args.archive_name
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(gerbers.iterdir()):
            if p.suffix.lower() in {'.gtl', '.gbl', '.gts', '.gbs', '.gto', '.gbo', '.gm1', '.drl', '.gbrjob'}:
                z.write(p, p.name)
    print(archive)


if __name__ == '__main__':
    main()
