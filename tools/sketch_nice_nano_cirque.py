#!/usr/bin/env python3
"""Layout preview for the nice!nano Endgame with a 40 mm Cirque touchpad.

Draws the committed nice!nano PCB widened by a further HALF_SHIFT per half
(outline, keycaps and switch bodies), the touchpad with its curved-overlay
flange and mounting margin, the battery, controller, relocated status LED,
FFC slot and connector, plus a section through the pad centre. Coordinates
use the case frame (PCB X - 150, 140 - PCB Y). Needs Shapely and Matplotlib.
Run: python tools/sketch_nice_nano_cirque.py [--output path.png]
"""

import argparse
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely import affinity
from shapely.geometry import LineString, Point, box

from verify_choc_compatibility import blocks, coords

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "001 PCB/KICAD/NICE NANO WIRELESS/TheEndgame2024_NiceNano.kicad_pcb"
OUTPUT = ROOT / "002 CASE/NICE NANO CIRQUE/cirque-layout-preview.png"

HALF_SHIFT = 8.0                 # extra per half beyond the current nice!nano
SPLIT_X = 12.0                   # PCB X 138/162 in the case frame
PAD_CENTRE = (0.0, 17.0)
PAD_D = 40.0                     # TM040040 module
FLANGE_D = 46.13                 # curved overlay 50-000090-00 flange
MARGIN = 4.0                     # flange to nearest keycap
BATTERY_OPENING = (-11.0, -4.0, 11.0, 31.0)
BATTERY_PACK = (-9.25, -3.0, 9.25, 30.0)
NICE_NANO = (-9.0, 44.0, 9.0, 77.0)
PAD_CONNECTOR = (11.6, 12.5, 14.6, 21.5)   # 12-pin vertical, beside the pack
FFC_SLOT = (12.0, 12.5, 14.2, 21.5)
FFC_J2 = (15.5, 11.5, 21.5, 22.5)          # bottom-side 12-pin 0.5 mm
J1, SW38 = (-2.0, -7.5), (0.0, -14.0)
LED_GAP = ("SW27", "SW37")                 # LED midway between these caps
CASE_TOP_AT_PAD = 8.35                     # current case roof near Y=17
PCB_TOP = 1.6
OVERLAY_HEIGHT = 1.5                       # assumed; to be measured
PAD_PCB, PAD_COMPONENTS, PAD_CONNECTOR_H = 0.74, 1.0, 4.10


def shift(x):
    return x - HALF_SHIFT if x < -SPLIT_X else x + HALF_SHIFT if x > SPLIT_X else x


def edge_cuts(pcb):
    """Edge.Cuts polylines, each half moved outward by HALF_SHIFT."""
    paths = []
    for kind in ("gr_line", "gr_arc"):
        for item in blocks(pcb, kind):
            if '"Edge.Cuts"' not in item:
                continue
            start, end = coords(item, "start", 2), coords(item, "end", 2)
            if kind == "gr_line":
                pts = [start, end]
            else:
                mid = coords(item, "mid", 2)
                pts = arc_points(start, mid, end)
            pts = [(x - 150, 140 - y) for x, y in pts]
            # A segment crossing a split stretches; points move with their side.
            paths.append([(shift(x), y) for x, y in pts])
    return paths


def arc_points(a, m, b, n=24):
    (x1, y1), (x2, y2), (x3, y3) = a, m, b
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    t1, t2, t3 = (math.atan2(y - uy, x - ux) for x, y in (a, m, b))
    # Sweep from a to b through m.
    def ccw(t0, t):
        return (t - t0) % (2 * math.pi)
    sweep = ccw(t1, t3)
    if ccw(t1, t2) > sweep:
        sweep -= 2 * math.pi
    return [(ux + r * math.cos(t1 + sweep * i / n), uy + r * math.sin(t1 + sweep * i / n)) for i in range(n + 1)]


def keys(pcb):
    out = {}
    for item in blocks(pcb, "footprint"):
        if "SW_choc_v1_v2_HS_" not in item.splitlines()[0]:
            continue
        at = coords(item, "at", 2)
        angle = at[2] if len(at) == 3 else 0.0
        ref = re.search(r'\(property "Reference" "([^"]+)', item).group(1)
        half = 26.25 / 2 if "1.5u" in item.splitlines()[0] else 8.75
        x, y = shift(at[0] - 150), 140 - at[1]
        place = lambda s: affinity.translate(affinity.rotate(s, angle, origin=(0, 0)), x, y)
        out[ref] = {"centre": (x, y), "cap": place(box(-half, -8.25, half, 8.25)),
                    "body": place(box(-7.5, -7.5, 7.5, 7.5))}
    return out


def rect(ax, r, **kw):
    x0, y0, x1, y1 = r
    ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, **kw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    pcb = PCB.read_text()
    outline = edge_cuts(pcb)
    caps = keys(pcb)

    a, b = (caps[r] for r in LED_GAP)
    gap = LineString([a["centre"], b["centre"]]).difference(a["cap"].union(b["cap"]))
    led = gap.interpolate(0.5, normalized=True)
    pad = Point(PAD_CENTRE)
    margin = min(pad.buffer(FLANGE_D / 2).distance(k["cap"]) for k in caps.values())
    led_clear = min(led.distance(k["cap"]) for k in caps.values())
    xs = [x for path in outline for x, _ in path]
    width = max(xs) - min(xs)

    fig = plt.figure(figsize=(16, 10.5))
    top = fig.add_axes([0.03, 0.30, 0.94, 0.66])
    sec = fig.add_axes([0.20, 0.04, 0.60, 0.22])

    for path in outline:
        top.plot(*zip(*path), color="#2e7d32", lw=1.4)
    for ref, k in caps.items():
        top.fill(*k["cap"].exterior.xy, color="#d9dbe6", ec="#8a8fa8", lw=0.8)
        top.plot(*k["body"].exterior.xy, color="#b0b4c8", lw=0.5)
        top.text(*k["centre"], ref, ha="center", va="center", fontsize=6, color="#6a6f88")
    rect(top, BATTERY_OPENING, fill=False, ec="#c98a00", lw=1, ls="--")
    rect(top, BATTERY_PACK, color="#ffd27a", alpha=0.55)
    top.text(0, 3, "401730 battery\n(under pad)", ha="center", fontsize=7, color="#8a5a00")
    for d, kw, label in ((PAD_D + 2 * MARGIN + FLANGE_D - PAD_D, dict(ls=":", color="#777"), "flange + 4 mm margin"),
                         (FLANGE_D, dict(ls="--", color="#1b7f5a"), "46.13 mm overlay flange")):
        top.plot(*pad.buffer(d / 2).exterior.xy, lw=1, label=label, **kw)
    top.fill(*pad.buffer(PAD_D / 2).exterior.xy, color="#4cb391", alpha=0.35, label="40 mm Cirque TM040040")
    rect(top, NICE_NANO, color="#f58fc0", alpha=0.6)
    top.text(0, 60, "nice!nano", ha="center", fontsize=8)
    rect(top, PAD_CONNECTOR, color="#3d6fb6", alpha=0.8)
    rect(top, FFC_J2, fill=False, ec="#3d6fb6", lw=1, ls="--")
    top.annotate("pad FFC connector → slot →\nJ2 on PCB underside", xy=(18, 17), xytext=(22, 36),
                 fontsize=7, color="#3d6fb6", arrowprops={"arrowstyle": "->", "color": "#3d6fb6"})
    top.plot(*J1, "s", color="#c0392b", ms=4)
    top.plot(*SW38, "s", color="#555", ms=5)
    top.text(SW38[0] + 2, SW38[1] - 3, "power switch", fontsize=7)
    top.add_patch(plt.Rectangle((led.x - 2.5, led.y - 2.5), 5, 5, color="#ff8c1a"))
    top.plot(*led.buffer(7).exterior.xy, color="#ff8c1a", lw=0.8, ls=":")
    top.annotate("status LED", xy=(led.x, led.y), xytext=(led.x - 4, led.y - 22), fontsize=8,
                 color="#c25e00", arrowprops={"arrowstyle": "->", "color": "#c25e00"})
    top.set_aspect("equal")
    top.set_xlim(min(xs) - 4, max(xs) + 4)
    top.set_ylim(-28, 88)
    top.legend(loc="upper left", fontsize=8)
    top.set_title(f"nice!nano Endgame + Cirque: each half +{HALF_SHIFT:g} mm, PCB ≈ {width:.1f} mm wide; "
                  f"flange-to-keycap {margin:.1f} mm; LED at ({led.x:.1f}, {led.y:.1f}), {led_clear:.1f} mm clear",
                  fontsize=11)

    # Section through the pad centre (X axis across the board).
    def layer(x0, x1, z0, z1, colour, label=None, **kw):
        sec.add_patch(plt.Rectangle((x0, z0), x1 - x0, z1 - z0, color=colour, label=label, **kw))
    r = FLANGE_D / 2
    layer(-40, -11, 0, PCB_TOP, "#2e7d32", "PCB (battery opening in centre)")
    layer(11, 40, 0, PCB_TOP, "#2e7d32")
    layer(-9.25, 9.25, 0.2, 5.2, "#ffd27a", "battery envelope")
    pad_bottom = 0.2 + 5.0 + PAD_COMPONENTS
    layer(-20, 20, pad_bottom, pad_bottom + PAD_PCB, "#4cb391", "pad PCB")
    layer(-12, 9, pad_bottom - PAD_COMPONENTS, pad_bottom, "#7fbfa8", "pad components (≤1 mm, assumed)")
    layer(11.6, 14.6, pad_bottom - PAD_CONNECTOR_H, pad_bottom, "#3d6fb6", "pad FFC connector")
    layer(15.5, 21.5, -1.2, 0, "#9db4dc", "J2 (PCB underside)")
    over = pad_bottom + PAD_PCB
    layer(-r, r, over, over + OVERLAY_HEIGHT, "#555", "curved overlay (height assumed)", alpha=0.6)
    sec.axhline(CASE_TOP_AT_PAD, color="#c0392b", ls="--", lw=1)
    sec.text(24, CASE_TOP_AT_PAD + 0.25, f"current case top ≈ {CASE_TOP_AT_PAD} mm", color="#c0392b", fontsize=8)
    sec.set_xlim(-40, 40)
    sec.set_ylim(-2, 11)
    sec.set_aspect("equal")
    sec.set_xlabel("X through pad centre (mm)")
    sec.set_ylabel("Z (mm)")
    sec.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=7)
    sec.set_title(f"Section at Y={PAD_CENTRE[1]:g}: overlay top ≈ {over + OVERLAY_HEIGHT:.2f} mm", fontsize=10)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=110)
    print(f"width {width:.2f} mm; flange-to-keycap {margin:.2f} mm; LED ({led.x:.2f}, {led.y:.2f}) clear {led_clear:.2f} mm")
    print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
