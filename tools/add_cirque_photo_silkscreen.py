#!/usr/bin/env python3
"""Put a dithered photo on both silkscreen layers of the Cirque PCB.

The photo is cropped to the board's aspect ratio, contrast-stretched and
Floyd-Steinberg dithered at PIXEL mm, then written as filled silkscreen
rectangles (horizontal runs merged vertically). The bottom layer is mirrored
so it reads correctly when the board is turned over. Ink is kept EDGE_MARGIN
from the outline and cutouts and clear of the mounting-hole ring artwork.
Rerunning replaces the previous photo. Needs Pillow and NumPy.
Run: python tools/add_cirque_photo_silkscreen.py --board X.kicad_pcb --photo art.jpg
"""
import argparse
import re
import uuid
from pathlib import Path

import numpy as np
from matplotlib.path import Path as MPath
from PIL import Image, ImageOps

PIXEL = 0.25          # mm; isolated dots stay above JLCPCB's ~0.15 mm silkscreen minimum
EDGE_MARGIN = 0.4     # mm from board outline and cutouts
RING_CLEAR = 4.6      # mm radius kept clear around each mounting-hole footprint
TAG = "c1c1c1c1"      # uuid prefix marking the photo's rectangles


def outline_from_board(text):
    """Board outline polygon and cutouts, from Edge.Cuts lines and arcs."""
    import math
    segs = []
    for kind in ("gr_line", "gr_arc"):
        for m in re.finditer(rf'\(\s*{kind}\s*\(start ([-\d.]+) ([-\d.]+)\)(?:\s*\(mid ([-\d.]+) ([-\d.]+)\))?\s*\(end ([-\d.]+) ([-\d.]+)\)(.*?)\(layer "Edge\.Cuts"\)', text, re.S):
            sx, sy, mx, my, ex, ey = m.group(1, 2, 3, 4, 5, 6)
            a, b = (float(sx), float(sy)), (float(ex), float(ey))
            if mx is None:
                segs.append([a, b])
            else:
                segs.append(arc(a, (float(mx), float(my)), b))
    # Chain segments into closed loops.
    loops = []
    pool = [list(s) for s in segs]
    key = lambda p: (round(p[0], 3), round(p[1], 3))
    while pool:
        loop = pool.pop()
        while key(loop[-1]) != key(loop[0]):
            for i, s in enumerate(pool):
                if key(s[0]) == key(loop[-1]):
                    loop += s[1:]; pool.pop(i); break
                if key(s[-1]) == key(loop[-1]):
                    loop += s[::-1][1:]; pool.pop(i); break
            else:
                raise AssertionError('open Edge.Cuts loop')
        loops.append(np.array(loop))
    loops.sort(key=lambda l: -np.ptp(l[:, 0]) * np.ptp(l[:, 1]))
    return loops[0], loops[1:]


def arc(a, m, b, n=24):
    import math
    (x1, y1), (x2, y2), (x3, y3) = a, m, b
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    t1, t2, t3 = (math.atan2(y - uy, x - ux) for x, y in (a, m, b))
    ccw = lambda t0, t: (t - t0) % (2 * math.pi)
    sweep = ccw(t1, t3)
    if ccw(t1, t2) > sweep:
        sweep -= 2 * math.pi
    return [(ux + r * math.cos(t1 + sweep * i / n), uy + r * math.sin(t1 + sweep * i / n)) for i in range(n + 1)]


def mounting_holes(text):
    """Centres of the mounting-hole footprints (their silkscreen rings stay)."""
    out = []
    for m in re.finditer(r'\(footprint "TheEndgame2024:(?:OM MOUNTING|MOUNTING HOLE)[^"]*"\s.*?\(at ([-\d.]+) ([-\d.]+)', text, re.S):
        out.append((float(m.group(1)), float(m.group(2))))
    return out


def ink_mask(photo, outline, cutouts, holes, mirror):
    x0, y0 = outline.min(0)
    x1, y1 = outline.max(0)
    nx, ny = int((x1 - x0) / PIXEL), int((y1 - y0) / PIXEL)
    img = Image.open(photo).convert('L')
    iw, ih = img.size
    target = (x1 - x0) / (y1 - y0)
    if iw / ih > target:
        cw = int(ih * target); img = img.crop(((iw - cw) // 2, 0, (iw - cw) // 2 + cw, ih))
    else:
        ch = int(iw / target); img = img.crop((0, (ih - ch) // 2, iw, (ih - ch) // 2 + ch))
    img = ImageOps.autocontrast(img.resize((nx, ny), Image.LANCZOS), cutoff=1)
    if mirror:
        img = ImageOps.mirror(img)
    ink = np.array(img.convert('1'))
    xs = x0 + (np.arange(nx) + 0.5) * PIXEL
    ys = y0 + (np.arange(ny) + 0.5) * PIXEL
    X, Y = np.meshgrid(xs, ys)
    pts = np.c_[X.ravel(), Y.ravel()]
    keep = MPath(outline).contains_points(pts, radius=-2 * EDGE_MARGIN)
    if not keep.any():
        keep = MPath(outline).contains_points(pts, radius=2 * EDGE_MARGIN)
    keep = keep.reshape(ny, nx)
    inside = MPath(outline).contains_points(pts).reshape(ny, nx)
    from scipy import ndimage
    edge = ndimage.distance_transform_edt(inside) * PIXEL >= EDGE_MARGIN
    for c in cutouts:
        hole = MPath(c).contains_points(pts).reshape(ny, nx)
        edge &= ndimage.distance_transform_edt(~hole) * PIXEL >= EDGE_MARGIN
    for hx, hy in holes:
        edge &= (X - hx) ** 2 + (Y - hy) ** 2 >= RING_CLEAR ** 2
    return ink & edge, (x0, y0)


def rectangles(mask):
    """Horizontal runs, extended downwards while the run repeats exactly."""
    rects, open_runs = [], {}
    for r in range(mask.shape[0] + 1):
        row = mask[r] if r < mask.shape[0] else np.zeros(mask.shape[1], bool)
        padded = np.concatenate(([False], row, [False]))
        d = np.diff(padded.astype(int))
        runs = set(zip(np.where(d == 1)[0], np.where(d == -1)[0]))
        for run in list(open_runs):
            if run not in runs:
                rects.append((run[0], open_runs.pop(run), run[1], r))
        for run in runs:
            open_runs.setdefault(run, r)
    return rects


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--board', type=Path, required=True)
    ap.add_argument('--photo', type=Path, required=True)
    ap.add_argument('--preview', type=Path, help='write a PNG of both layers')
    args = ap.parse_args()
    text = args.board.read_text()
    # Remove any earlier photo rectangles.
    text = re.sub(rf'\n\t\(gr_rect\n(?:(?!\n\t\)).)*?\(uuid "{TAG}[^"]*"\)\n\t\)', '', text, flags=re.S)
    outline, cutouts = outline_from_board(text)
    holes = mounting_holes(text)
    parts, previews = [], {}
    for layer, mirror in (('F.SilkS', False), ('B.SilkS', True)):
        mask, (x0, y0) = ink_mask(args.photo, outline, cutouts, holes, mirror)
        previews[layer] = mask
        for c0, r0, c1, r1 in rectangles(mask):
            parts.append(
                f'\n\t(gr_rect\n\t\t(start {x0 + c0 * PIXEL:.3f} {y0 + r0 * PIXEL:.3f})\n\t\t(end {x0 + c1 * PIXEL:.3f} {y0 + r1 * PIXEL:.3f})'
                f'\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill yes)\n\t\t(layer "{layer}")'
                f'\n\t\t(uuid "{TAG}-{uuid.uuid4().hex[8:12]}-{uuid.uuid4().hex[12:16]}-{uuid.uuid4().hex[16:20]}-{uuid.uuid4().hex[20:32]}")\n\t)')
        print(f'{layer}: {int(mask.sum())} ink pixels')
    body = text.rstrip()
    assert body.endswith(')')
    args.board.write_text(body[:-1] + ''.join(parts) + '\n)\n')
    print(f'{len(parts)} silkscreen rectangles written to {args.board}')
    if args.preview:
        top = np.where(previews['F.SilkS'], 240, 18).astype(np.uint8)
        bottom = np.where(previews['B.SilkS'], 240, 18).astype(np.uint8)
        gap = np.full((20, top.shape[1]), 255, np.uint8)
        Image.fromarray(np.vstack([top, gap, bottom])).save(args.preview)


if __name__ == '__main__':
    main()
