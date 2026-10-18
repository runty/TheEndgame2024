#!/usr/bin/env python3
"""Grid router for the few new nets on the nice!nano + Cirque PCB.

Reads the obstacle JSON written by `build_nice_nano_cirque_pcb.py dump` and
routes each net in NETS on F.Cu/B.Cu with A* on a 0.05 mm grid. Copper of
other nets is inflated by the clearance plus half the track width; the board
outline, cutouts and rule-area keep-outs are blocked; vias keep clearance on
both layers and from every drilled hole. Each routed net becomes an obstacle
for the next. Writes routes JSON for `build_nice_nano_cirque_pcb.py apply`.
Needs NumPy, SciPy and Matplotlib (for polygon rasterisation).
"""

import argparse
import heapq
import json
import math

import numpy as np
from matplotlib.path import Path as MPath
from scipy import ndimage
from shapely.geometry import LineString

RES = 0.05
CLEARANCE = 0.2
MARGIN = 0.1              # covers grid rounding of obstacles and paths
EDGE_CLEARANCE = 0.5
VIA = (0.6, 0.3)          # diameter, drill
HOLE_CLEARANCE = 0.3      # via drill to any other drill, edge to edge
VIA_COST = 80.0           # in grid steps
# Straight fan-out stubs (dx, dy) on the pad's layer, all laid before any
# routing so each 0.5 mm-pitch FFC pin owns a lane clear of the pad row.
STUB = {"J2.4": (0.9, 0), "J2.9": (0.9, 0), "J2.10": (0.9, 0), "J2.12": (0.9, 0)}
# Ground pads drop through a via into the F.Cu ground pour at the end of a
# stub; J2's ground stub reaches past the other stubs so its via clears them.
GND_VIA_STUBS = {"J2.11": (2.0, 0), "C2.2": (0, 1.3)}
LAYERS = ("F", "B")

# Net -> (track width, pads in routing order). The first pad seeds the tree.
NETS = [
    # Battery path first: J1 (front) -> SW38 (back edge, under the nice!nano)
    # -> RAW. The long LED data route along the back edge would box it in.
    ("VBAT_SW", 0.4, ["U2.24", "SW38.1"]),
    ("VBAT", 0.4, ["J1.1", "SW38.2"]),
    # J2 pins leave towards U2 (-Y); route them in pin order from the -Y end
    # (12 VCC, 11 GND, 10 SDA, 9 SCL, 4 DR) so none is boxed in.
    ("VCC_SW", 0.25, ["U2.21", "J2.12", "R3.1", "R4.1", "C2.1", "C1.1", "LED1.1"]),
    ("SDA", 0.2, ["U2.15", "J2.10", "R3.2"]),
    ("SCL", 0.2, ["U2.14", "J2.9", "R4.2"]),
    ("DR", 0.2, ["U2.13", "J2.4"]),
    ("LED_DIN", 0.2, ["R1.2", "LED1.4", "R2.1"]),
    ("LED_DATA", 0.2, ["U2.1", "R1.1"]),
]


class Grid:
    def __init__(self, data):
        xs = [x for x, _ in data["outline"]]
        ys = [y for _, y in data["outline"]]
        self.x0, self.y0 = min(xs) - 1, min(ys) - 1
        self.nx = int((max(xs) + 1 - self.x0) / RES) + 1
        self.ny = int((max(ys) + 1 - self.y0) / RES) + 1
        self.data = data

    def cell(self, x, y):
        return int(round((y - self.y0) / RES)), int(round((x - self.x0) / RES))

    def xy(self, r, c):
        return (round(self.x0 + c * RES, 4), round(self.y0 + r * RES, 4))

    def raster(self, poly):
        """Boolean mask of a polygon (list of (x, y))."""
        mask = np.zeros((self.ny, self.nx), bool)
        pts = np.asarray(poly)
        r0, c0 = self.cell(pts[:, 0].min(), pts[:, 1].min())
        r1, c1 = self.cell(pts[:, 0].max(), pts[:, 1].max())
        r0, c0 = max(r0 - 1, 0), max(c0 - 1, 0)
        r1, c1 = min(r1 + 2, self.ny), min(c1 + 2, self.nx)
        if r1 <= r0 or c1 <= c0:
            return mask
        rr, cc = np.mgrid[r0:r1, c0:c1]
        px = self.x0 + cc * RES
        py = self.y0 + rr * RES
        inside = MPath(pts).contains_points(np.c_[px.ravel(), py.ravel()], radius=1e-9).reshape(px.shape)
        mask[r0:r1, c0:c1] = inside
        return mask


def segment_poly(a, b, half):
    """Outline of a track segment (round ends)."""
    return list(LineString([a, b]).buffer(half, quad_segs=6).exterior.coords)


def draw_disk(mask, r, c, rad):
    """Set cells within rad cells of (r, c), clipped to the array."""
    n = int(math.ceil(rad))
    r0, r1 = max(r - n, 0), min(r + n + 1, mask.shape[0])
    c0, c1 = max(c - n, 0), min(c + n + 1, mask.shape[1])
    rr, cc = np.ogrid[r0:r1, c0:c1]
    mask[r0:r1, c0:c1] |= (rr - r) ** 2 + (cc - c) ** 2 <= rad * rad


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--obstacles", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    data = json.load(open(args.obstacles))
    g = Grid(data)

    # Per-layer copper occupancy, tagged by net. Multiple nets -> "*".
    copper = {L: [] for L in LAYERS}
    for item in data["items"]:
        for poly in item["poly"]:
            copper[item["layer"]].append((item["net"], poly))
    net_masks = {L: {} for L in LAYERS}
    for L in LAYERS:
        for net, poly in copper[L]:
            m = g.raster(poly)
            if net in net_masks[L]:
                net_masks[L][net] |= m
            else:
                net_masks[L][net] = m

    outside = ~g.raster(data["outline"])
    for hole in data["cutouts"]:
        outside |= g.raster(hole)
    edge = ndimage.distance_transform_edt(~outside) * RES < EDGE_CLEARANCE
    keepout = np.zeros_like(edge)
    for ko in data["keepouts"]:
        for poly in ko:
            keepout |= g.raster(poly)
    holes = np.zeros_like(edge)
    for h in data["holes"]:
        draw_disk(holes, *g.cell(*h["xy"]), h["r"] / RES)
    hole_dist = ndimage.distance_transform_edt(~holes) * RES
    keepout_dist = ndimage.distance_transform_edt(~keepout) * RES
    # Drilled holes also block tracks on both layers (NPTH holes carry no copper).

    tracks, vias = [], []
    stub_end = {}
    for net, width, pads in NETS:
        for pad in pads:
            if pad in STUB:
                info = data["pads"][pad]
                a = tuple(info["xy"])
                end = (round(a[0] + STUB[pad][0], 4), round(a[1] + STUB[pad][1], 4))
                L = info["layers"][0]
                tracks.append({"net": net, "layer": L, "width": width, "a": a, "b": end})
                m = g.raster(segment_poly(a, end, width / 2))
                net_masks[L][net] = net_masks[L].get(net, np.zeros_like(edge)) | m
                stub_end[pad] = end
    for pad, (dx, dy) in GND_VIA_STUBS.items():
        info = data["pads"][pad]
        a = tuple(info["xy"])
        end = (round(a[0] + dx, 4), round(a[1] + dy, 4))
        L = info["layers"][0]
        tracks.append({"net": "gnd", "layer": L, "width": 0.25, "a": a, "b": end})
        vias.append({"net": "gnd", "xy": end, "size": VIA[0], "drill": VIA[1]})
        for layer in LAYERS:
            m = np.zeros_like(edge)
            draw_disk(m, *g.cell(*end), VIA[0] / 2 / RES)
            if layer == L:
                m |= g.raster(segment_poly(a, end, 0.125))
            net_masks[layer]["gnd"] = net_masks[layer].get("gnd", np.zeros_like(edge)) | m
        draw_disk(holes, *g.cell(*end), VIA[1] / 2 / RES)
    hole_dist = ndimage.distance_transform_edt(~holes) * RES
    for net, width, pads in NETS:
        half = width / 2
        # Drilled holes of other nets block this net; its own (e.g. a pin
        # post it starts from) must not wall in its pad.
        foreign = np.zeros_like(edge)
        for h in data["holes"]:
            if h["net"] != net:
                draw_disk(foreign, *g.cell(*h["xy"]), h["r"] / RES)
        for v in vias:
            if v["net"] != net:
                draw_disk(foreign, *g.cell(*v["xy"]), v["drill"] / 2 / RES)
        foreign_dist = ndimage.distance_transform_edt(~foreign) * RES
        blocked, via_ok = {}, None
        for L in LAYERS:
            others = np.zeros_like(edge)
            for n, m in net_masks[L].items():
                if n != net:
                    others |= m
            dist = ndimage.distance_transform_edt(~others) * RES
            blocked[L] = (dist < CLEARANCE + MARGIN + half) | edge | (keepout_dist < MARGIN + half) | (foreign_dist < 0.25 + MARGIN + half)
            via_block = dist < CLEARANCE + MARGIN + VIA[0] / 2
            via_ok = ~via_block if via_ok is None else via_ok & ~via_block
        via_ok &= ~edge & (keepout_dist > MARGIN + VIA[0] / 2) & (hole_dist > HOLE_CLEARANCE + VIA[1] / 2)

        tree = {L: np.zeros_like(edge) for L in LAYERS}
        own = {L: net_masks[L].get(net, np.zeros_like(edge)) for L in LAYERS}
        if pads[0] is None:
            # Any existing copper of the net may be joined, except the
            # pieces (pads and stubs) that this step still has to connect.
            tree = {L: own[L].copy() for L in LAYERS}
            for L in LAYERS:
                labels, _ = ndimage.label(own[L], structure=np.ones((3, 3)))
                for pad in pads[1:]:
                    for xy in (data["pads"][pad]["xy"], stub_end.get(pad, data["pads"][pad]["xy"])):
                        lab = labels[g.cell(*xy)]
                        if lab:
                            tree[L][labels == lab] = False
        else:
            first = data["pads"][pads[0]]
            for L in first["layers"]:
                tree[L] |= own[L] & g.raster(pad_poly(data, pads[0], L))
                r, c = g.cell(*first["xy"])
                tree[L][r, c] = True
        for pad in pads[1:]:
            info = data["pads"][pad]
            start_xy = stub_end.get(pad, info["xy"])
            start = [(L, *g.cell(*start_xy)) for L in info["layers"]]
            path = astar(g, blocked, via_ok, start, tree, own, pad, data)
            assert path, f"No route for {net} to {pad}"
            for L in LAYERS:
                for (l, r, c) in path:
                    if l == L:
                        tree[L][r, c] = True
            path = straighten(path, blocked)
            t, v = to_segments(g, path, net, width)
            tracks += t
            vias += v
            # Rasterise the new copper so the rest of this net can join it and
            # later nets keep clear of it.
            for seg in t:
                m = g.raster(segment_poly(seg["a"], seg["b"], half))
                net_masks[seg["layer"]][net] = net_masks[seg["layer"]].get(net, np.zeros_like(edge)) | m
                own[seg["layer"]] = net_masks[seg["layer"]][net]
            for via in v:
                r, c = g.cell(*via["xy"])
                for L in LAYERS:
                    sl = net_masks[L].setdefault(net, np.zeros_like(edge))
                    draw_disk(sl, r, c, VIA[0] / 2 / RES)
                    own[L] = sl
                holes_new = np.zeros_like(edge)
                draw_disk(holes_new, r, c, VIA[1] / 2 / RES)
                hole_dist = np.minimum(hole_dist, ndimage.distance_transform_edt(~holes_new) * RES)
            print(f"{net}: {pad} routed, {len(t)} segments, {len(v)} vias, {sum(math.dist(s['a'], s['b']) for s in t):.1f} mm")
    json.dump({"tracks": tracks, "vias": vias}, open(args.output, "w"), indent=1)
    print(f"{len(tracks)} tracks, {len(vias)} vias -> {args.output}")


def pad_poly(data, key, layer):
    x, y = data["pads"][key]["xy"]
    return [(x - 0.1, y - 0.1), (x + 0.1, y - 0.1), (x + 0.1, y + 0.1), (x - 0.1, y + 0.1)]


def astar(g, blocked, via_ok, starts, tree, own, pad, data):
    """A* from a pad to any cell already in the net's tree (or its copper)."""
    targets = {L: tree[L] for L in LAYERS}
    tr = {L: np.argwhere(targets[L]) for L in LAYERS}
    allt = np.vstack([t for t in tr.values() if len(t)])
    centre = allt.mean(axis=0)

    def h(r, c):
        d = np.abs(allt - (r, c))
        return float(np.min(np.maximum(d[:, 0], d[:, 1]) + 0.414 * np.minimum(d[:, 0], d[:, 1]))) if len(allt) < 400 else \
            math.hypot(r - centre[0], c - centre[1]) * 0.5
    moves = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
    # The pad itself and its own-net copper are always enterable near the ends.
    free = {L: ~blocked[L] | own[L] for L in LAYERS}
    openq, best, came = [], {}, {}
    for s in starts:
        best[s] = 0.0
        heapq.heappush(openq, (h(s[1], s[2]), 0.0, s))
    while openq:
        f, cost, node = heapq.heappop(openq)
        if cost > best.get(node, 1e18):
            continue
        L, r, c = node
        if targets[L][r, c] and node not in starts:
            path = [node]
            while path[-1] in came:
                path.append(came[path[-1]])
            return path[::-1]
        for dr, dc, w in moves:
            nr, nc = r + dr, c + dc
            if 0 <= nr < g.ny and 0 <= nc < g.nx and free[L][nr, nc]:
                nxt = (L, nr, nc)
                ncost = cost + w
                if ncost < best.get(nxt, 1e18):
                    best[nxt] = ncost
                    came[nxt] = node
                    heapq.heappush(openq, (ncost + h(nr, nc), ncost, nxt))
        if via_ok[r, c]:
            other = "B" if L == "F" else "F"
            if free[other][r, c]:
                nxt = (other, r, c)
                ncost = cost + VIA_COST
                if ncost < best.get(nxt, 1e18):
                    best[nxt] = ncost
                    came[nxt] = node
                    heapq.heappush(openq, (ncost + h(r, c), ncost, nxt))
    return None


def clear_line(mask, a, b):
    """True when every grid cell on the straight line a->b is unblocked."""
    (r0, c0), (r1, c1) = a, b
    n = max(abs(r1 - r0), abs(c1 - c0))
    for i in range(n + 1):
        r = round(r0 + (r1 - r0) * i / n) if n else r0
        c = round(c0 + (c1 - c0) * i / n) if n else c0
        if mask[r, c]:
            return False
    return True


def straighten(path, blocked):
    """Replace grid staircases with the longest clear 0/45/90-degree runs."""
    out = [path[0]]
    i = 0
    while i < len(path) - 1:
        L = path[i][0]
        best = i + 1
        for j in range(len(path) - 1, i, -1):
            if path[j][0] != L or any(path[k][0] != L for k in range(i, j + 1)):
                continue
            dr, dc = path[j][1] - path[i][1], path[j][2] - path[i][2]
            if (dr == 0 or dc == 0 or abs(dr) == abs(dc)) and clear_line(blocked[L], path[i][1:], path[j][1:]):
                best = j
                break
        out.append(path[best])
        i = best
    return out


def to_segments(g, path, net, width):
    tracks, vias = [], []
    run = [path[0]]
    def flush(run):
        if len(run) < 2:
            return
        pts = [run[0]]
        for i in range(1, len(run) - 1):
            a, b, c = run[i - 1], run[i], run[i + 1]
            if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
                pts.append(b)
        pts.append(run[-1])
        for a, b in zip(pts, pts[1:]):
            tracks.append({"net": net, "layer": a[0], "width": width, "a": g.xy(a[1], a[2]), "b": g.xy(b[1], b[2])})
    for node in path[1:]:
        if node[0] != run[-1][0]:
            flush(run)
            vias.append({"net": net, "xy": g.xy(node[1], node[2]), "size": VIA[0], "drill": VIA[1]})
            run = [node]
        else:
            run.append(node)
    flush(run)
    return tracks, vias


if __name__ == "__main__":
    main()
