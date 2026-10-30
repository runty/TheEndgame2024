#!/usr/bin/env python3
"""Build the nice!nano + Cirque case, battery tray and touchpad carrier.

The original Endgame case is split at X=+-7 mm (inside the solid waist, so no
key opening crosses a split) and each half moves outward 10 mm to match the
239 mm Cirque PCB. Central features (controller, USB, battery, J1 and tray
mounts) are re-cut at their fixed positions. The power switch is on the PCB
underside at the USB opening, so the case has no switch hole. The roof stays
the original's single 2-degree plane, with nothing above it, so the case prints
upside down on its top face. A Cirque TM040040 with the curved overlay
50-000090-00 drops into a counterbore from below; its flange seats under a
ledge at least LEDGE_MIN thick, the overlay stands proud of the roof, and a
printed C-ring clamps it from below. The battery stays under the pad in the
PCB opening, lowered 0.5 mm into the tray. The status LED pocket sits in the
right thumb gap.

Coordinates use the case frame (PCB X - 150, 140 - PCB Y, Z); PCB Z=0..1.6.
Needs OCP, trimesh, NumPy and Matplotlib.
Run: python tools/build_nice_nano_cirque_case.py
"""

import json
import math
import re

import build_nice_nano_case as base
from build_nice_nano_case import (
    BRepAlgoAPI_Common, BRepBuilderAPI_Transform, BRepCheck_Analyzer, BRepExtrema_DistShapeShape,
    BRepPrimAPI_MakePrism, BRep_Tool, IntCurvesFace_ShapeIntersector, ROOT, SOURCE, SOURCE_PCB,
    STEPControl_Reader, TopAbs_FACE, TopAbs_VERTEX, TopExp_Explorer, TopoDS, USB_BEVEL_START_Y,
    USB_HALF_WIDTH, USB_MOUTH_TOP, USB_REAR_Y, box, conical_recess, cut, cylinder, fuse, gp_Ax1,
    gp_Dir, gp_Lin, gp_Pnt, gp_Trsf, gp_Vec, rounded_prism, solids, translated, volume, write_step,
    write_stl, yz_prism,
)
from verify_choc_compatibility import blocks, coords

PCB = ROOT / "001 PCB/KICAD/NICE NANO CIRQUE/TheEndgame2024_NiceNanoCirque.kicad_pcb"
OUTPUT = ROOT / "002 CASE/NICE NANO CIRQUE"
VALIDATION = ROOT / "docs/validation/nice-nano-cirque-case"
SPLIT, SHIFT = 7.0, 10.0          # original case -> Cirque case, per half

# Cirque TM040040 + curved ABS overlay 50-000090-00 (Cirque spec v1.1).
PAD_CENTRE = (0.0, 17.0)
PAD_R, KEEPOUT_R = 20.0, 18.0      # module; component area inside Ø36.01
PAD_PCB, PAD_COMPONENTS, PAD_CONNECTOR_H = 0.74, 1.0, 4.10
FLANGE_R, STEP_R = 46.13 / 2, 43.86 / 2
# Curved overlay, scaled from Cirque's drawing (spec Fig. 7) until measured: a
# cup OVERLAY_HEIGHT from flange bottom to rim, its flange FLANGE_T thick, with
# the pad's PCB glued into a pocket OVERLAY_POCKET deep and POCKET_R across.
OVERLAY_HEIGHT, FLANGE_T, OVERLAY_POCKET, POCKET_R = 5.0, 1.6, 3.0, 20.2
PAD_PCB_AND_ADHESIVE = 0.99        # spec Fig. 2
LEDGE_MIN = 1.0                    # case above the flange where the roof is lowest
# 12-pin vertical FFC connector, facing +X: envelope of Cirque's land pattern
# (spec Fig. 2) and the module photo; the cable leaves its slot at X 15.7-16.4.
PAD_CONNECTOR = (12.5, 12.6, 18.4, 21.4)
FFC_SLOT_X, FFC_WIDTH = (15.7, 16.4), 6.5
OPENING_R = STEP_R + 0.17          # through the roof for the overlay step
COUNTERBORE_R = FLANGE_R + 0.18    # flange seat, open from below
CARRIER_R = COUNTERBORE_R - 0.2    # carrier locates on the counterbore wall
CARRIER_GIVE = 0.2                 # carrier prints short; foam tape takes it up
BATTERY = (-9.25, -3.0, -0.5, 9.25, 30.0, 4.5)   # 401730 envelope, 0.5 mm lower
LED_POCKET = (75.89, -1.26, 82.89, 4.74, 3.55)   # LED1 and its pads; passives are underneath
# SW38 sits under the nice!nano on the PCB underside, slider towards the back
# edge but about 0.5 mm inside it (case Y 76.99 vs edge 77.44); it is operated
# through the USB opening, which runs below the board.
SW38_BODY = (-3.35, 72.7, -1.4, 3.35, 75.3, 0.0)
SW38_SLIDER = (-1.4, 75.3, -1.4, -0.1, 76.99, 0.0)
CENTRAL_MOUNTS = [(-9.804941, -14.168516), (9.804965, -14.170142)]
# The tray's back end hooks over the battery opening's back edge (Y 31): a
# riser through the 1 mm gap behind the battery, then a lip resting on the
# board's top face. Fit it before the board goes into the case: lift the hook
# through the opening with the tray HOOK_SLIDE towards the front, slide it back,
# then the front screws stop it sliding out again.
OPENING_BACK_Y = 31.0
HOOK_HALF_W = 6.0
HOOK_RISER = (30.2, 30.8)          # 0.2 mm to the battery envelope and to the edge
HOOK_LIP = 4.0                     # overlap on the board's top face
HOOK_LIP_GAP, HOOK_LIP_T = 0.2, 1.0
HOOK_SLIDE = HOOK_LIP + 0.2       # lip end clears the opening edge by 0.2 mm
PCB_POCKET_CLEARANCE = 0.4   # case pocket around the PCB outline
PCB_MIN_CLEARANCE = 0.3      # checked between PCB outline and case


def pcb_outline():
    """Outer board outline in the case frame, from the Cirque PCB's Edge.Cuts."""
    return pcb_board()[0]


def pcb_board():
    """Outer outline and the cutouts (battery opening + FFC notch), case frame."""
    from shapely.geometry import Polygon
    from add_cirque_photo_silkscreen import outline_from_board
    outline, cutouts = outline_from_board(PCB.read_text())
    frame = lambda loop: Polygon([(x - 150, 140 - y) for x, y in loop]).buffer(0)
    return frame(outline), [frame(c) for c in cutouts]


def j2_courtyard():
    """J2's courtyard (underside FFC connector) in the case frame, from the PCB."""
    fp = next(f for f in blocks(PCB.read_text(), "footprint") if "JUSHUO_AFC01" in f.splitlines()[0])
    xs, ys = [], []
    for m in re.finditer(r'\(fp_(?:line|rect)\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)(?:(?!\(fp_).)*?\(layer "B\.CrtYd"\)', fp, re.S):
        a, b, c, d = map(float, m.groups())
        xs += [a, c]; ys += [b, d]
    at = coords(fp, "at", 2)
    x, y, t = at[0], at[1], math.radians(at[2] if len(at) == 3 else 0.0)
    # Local courtyard corners (already mirrored for the B side), rotated as KiCad does (Y down).
    pts = [(u, v) for u in (min(xs), max(xs)) for v in (min(ys), max(ys))]
    pts = [(x + u * math.cos(t) + v * math.sin(t), y - u * math.sin(t) + v * math.cos(t)) for u, v in pts]
    px = [q[0] - 150 for q in pts]; py = [140 - q[1] for q in pts]
    return min(px), min(py), max(px), max(py)


def polygon_prism(polygon, z0, z1):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    wire = BRepBuilderAPI_MakePolygon()
    for x, y in list(polygon.exterior.coords)[:-1]:
        wire.Add(gp_Pnt(x, y, z0))
    wire.Close()
    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, z1 - z0)).Shape()


def widened_case(original):
    """Split at X=+-SPLIT, move each half SHIFT outward, bridge the sections."""
    left = translated(cut(original, box(-SPLIT, -100, -20, 200, 100, 20)), -SHIFT)
    middle = BRepAlgoAPI_Common(original, box(-SPLIT, -100, -20, SPLIT, 100, 20)).Shape()
    right = translated(cut(original, box(-200, -100, -20, SPLIT, 100, 20)), SHIFT)
    widened = fuse(fuse(left, middle), right)
    for x, dx in ((-SPLIT, -SHIFT), (SPLIT, SHIFT)):
        faces = []
        explorer = TopExp_Explorer(middle, TopAbs_FACE)
        while explorer.More():
            face = explorer.Current()
            vertices = TopExp_Explorer(face, TopAbs_VERTEX)
            xs = []
            while vertices.More():
                xs.append(BRep_Tool.Pnt_s(TopoDS.Vertex(vertices.Current())).X())
                vertices.Next()
            if xs and all(abs(v - x) < 1e-6 for v in xs):
                faces.append(face)
            explorer.Next()
        assert faces, x
        for face in faces:
            widened = fuse(widened, BRepPrimAPI_MakePrism(face, gp_Vec(dx, 0, 0)).Shape())
    assert solids(widened) == 1 and BRepCheck_Analyzer(widened).IsValid()
    # The roof must be solid across both bridge strips over its full length.
    for x0, x1 in ((-SPLIT - SHIFT, -SPLIT), (SPLIT, SPLIT + SHIFT)):
        for y in (-18.0, 0.0, 20.0, 40.0, 60.0, 75.0):
            probe = box(x0, y, roof_z(widened, (x0 + x1) / 2, y) - 0.3, x1, y + 1, roof_z(widened, (x0 + x1) / 2, y) - 0.1)
            assert abs(volume(BRepAlgoAPI_Common(widened, probe).Shape()) - volume(probe)) < 1e-4, (x0, y)
    return widened


def roof_z(shape, x, y):
    hit = IntCurvesFace_ShapeIntersector()
    hit.Load(shape, 1e-7)
    hit.Perform(gp_Lin(gp_Pnt(x, y, 40), gp_Dir(0, 0, -1)), 0, 60)
    zs = [hit.Pnt(i).Z() for i in range(1, hit.NbPnt() + 1)]
    assert zs, (x, y)
    return max(zs)


def overlay_levels(seat):
    """Overlay bottom, overlay rim and pad PCB underside, from the flange-top seat."""
    bottom = seat - FLANGE_T
    return bottom, bottom + OVERLAY_HEIGHT, bottom + OVERLAY_POCKET - PAD_PCB_AND_ADHESIVE


def pad_stack(seat):
    """Proxy solids for the installed touchpad, keyed by name."""
    x, y = PAD_CENTRE
    bottom, rim, pcb_bottom = overlay_levels(seat)
    cx0, cy0, cx1, cy1 = PAD_CONNECTOR
    overlay = cut(fuse(cylinder(x, y, FLANGE_R, bottom, seat), cylinder(x, y, STEP_R, seat, rim)),
                  cylinder(x, y, POCKET_R, bottom - 0.1, bottom + OVERLAY_POCKET))
    return {
        "overlay": overlay,
        "pad PCB": cylinder(x, y, PAD_R, pcb_bottom, pcb_bottom + PAD_PCB),
        "pad components": cylinder(x, y, KEEPOUT_R, pcb_bottom - PAD_COMPONENTS, pcb_bottom),
        "pad FFC connector": box(cx0, cy0, pcb_bottom - PAD_CONNECTOR_H, cx1, cy1, pcb_bottom),
    }


def carrier(seat):
    """C-ring pressing the overlay's underside (and so the pad) up against the ledge.

    Its outside runs to 0.2 mm inside the counterbore wall, which centres it.
    It prints CARRIER_GIVE short of the gap; thin foam tape on its top takes
    that up, so print-height error never lifts the board or lets the pad rattle.
    """
    x, y = PAD_CENTRE
    top = overlay_levels(seat)[0] - CARRIER_GIVE
    ring = cut(cylinder(x, y, CARRIER_R, 1.6, top), cylinder(x, y, KEEPOUT_R + 0.3, 1.5, top + 0.1))
    # Open over the battery and the opening below the pad's front half.
    ring = cut(ring, box(-12.5, y - 30, 1.0, 12.5, y, top + 1))
    # Stand only on board material: clear of the cutouts (the FFC notch, where
    # the pad's connector and cable drop through) by 0.3 mm.
    for hole in pcb_board()[1]:
        ring = cut(ring, polygon_prism(hole.buffer(0.3, join_style=2).simplify(0.02), 1.0, top + 1))
    # Slot under the back of the ring for the tray hook's lip (0.4 mm round it,
    # 0.2 mm above it); the ring bridges over the slot.
    lip_top = 1.6 + HOOK_LIP_GAP + HOOK_LIP_T
    ring = cut(ring, box(-HOOK_HALF_W - 0.4, HOOK_RISER[0], 1.0,
                         HOOK_HALF_W + 0.4, OPENING_BACK_Y + HOOK_LIP + 0.4, lip_top + 0.2))
    assert solids(ring) == 1 and BRepCheck_Analyzer(ring).IsValid()
    return ring


def build_case(original):
    widened = widened_case(original)
    case = widened
    x, y = PAD_CENTRE
    # Nothing is added above the roof: the overlay just passes through it. The
    # 2-degree roof is lowest at the front of the counterbore, so the flange
    # seat sits LEDGE_MIN below that point.
    seat = roof_z(widened, x, y - COUNTERBORE_R) - LEDGE_MIN
    case = cut(case, cylinder(x, y, OPENING_R, seat - 0.01, 20))
    case = cut(case, cylinder(x, y, COUNTERBORE_R, -2, seat))
    # Battery pocket corners reach just beyond the counterbore.
    case = cut(case, rounded_prism(-11.1, -4.1, 11.1, 31.1, 1.0, -2, BATTERY[5] + 0.2))

    # The PCB and case were widened at different split lines (|x| 12 and 7),
    # so re-cut the pocket from the real board outline: the front tabs around
    # the central mounts would otherwise hit the case's inner front wall.
    pocket = pcb_outline().buffer(PCB_POCKET_CLEARANCE, join_style=2).simplify(0.05)
    # Cut faces must not meet the case's Z=1.6 seating faces (slivers break
    # the STL): the whole pocket to Z 1.55, then a band along the board edge
    # to Z 1.65 so no wall is left inside the board's thickness.
    # Only the front strips (|x| 6..23) are affected: the PCB's centre tabs
    # stayed put while the case wall behind them was extruded from X=+-7.
    from shapely.geometry import box as sbox
    for x0, x1 in ((-23.0, -6.0), (6.0, 23.0)):
        strip = pocket.intersection(sbox(x0, -22.0, x1, -15.0))
        case = cut(case, polygon_prism(strip, -3.0, 1.65))

    # Fixed central features carried over from the nice!nano case.
    case = cut(case, rounded_prism(-3.4, -11.1, 3.4, -3.6, 0.8, 0.0, 3.0))        # J1 wires
    case = cut(case, base.controller_pocket())
    case = fuse(case, rounded_prism(-7.4, 69.6, 7.4, 79.7, 1.0, 7.2, 8.55))       # USB crown
    case = cut(case, rounded_prism(-6.4, 70.0, 6.4, 82.0, 0.8, 0.0, 7.3))
    case = cut(case, rounded_prism(-USB_HALF_WIDTH, 70, USB_HALF_WIDTH, 82, 0.8, -2.0, 7.3))
    slope = (USB_MOUTH_TOP - 7.3) / (USB_REAR_Y - USB_BEVEL_START_Y)
    case = cut(case, yz_prism([(USB_BEVEL_START_Y, 7.3), (82, 7.3), (82, 7.3 + slope * (82 - USB_BEVEL_START_Y))]))
    for mx, my in CENTRAL_MOUNTS:
        case = fuse(case, cylinder(mx, my, 4.5, 1.6, 2.9))
        case = cut(case, cylinder(mx, my, 2.3, 1.5, 5.6))
    x0, y0, x1, y1, ztop = LED_POCKET
    case = cut(case, rounded_prism(x0, y0, x1, y1, 0.6, 0.0, ztop))
    assert solids(case) == 1 and BRepCheck_Analyzer(case).IsValid()
    return widened, case, seat


def hook():
    """The tray's back hook: riser plus the lip over the board's top face."""
    lip_z = 1.6 + HOOK_LIP_GAP
    riser = box(-HOOK_HALF_W, HOOK_RISER[0], -1.0, HOOK_HALF_W, HOOK_RISER[1], lip_z + HOOK_LIP_T)
    lip = box(-HOOK_HALF_W, HOOK_RISER[0], lip_z, HOOK_HALF_W, OPENING_BACK_Y + HOOK_LIP, lip_z + HOOK_LIP_T)
    return fuse(riser, lip)


def tray():
    plate = rounded_prism(-12.0, -5.0, 12.0, 32.0, 1.5, -1.5, -0.5)
    plate = fuse(plate, hook())
    for x, y in CENTRAL_MOUNTS:
        # Ears stop 0.3 mm short of the case's inner front wall at Y=-18.19.
        plate = fuse(plate, rounded_prism(x - 4.1, -17.9, x + 4.1, -4.0, 3.5, -1.8, 0.0))
    for x, y in CENTRAL_MOUNTS:
        plate = cut(plate, cylinder(x, y, 3.1, -1.9, -1.6))
        plate = cut(plate, conical_recess(x, y, 3.1, 1.65, -1.6, -0.15))
        plate = cut(plate, cylinder(x, y, 1.65, -0.15, 0.1))
    assert solids(plate) == 1 and BRepCheck_Analyzer(plate).IsValid()
    return plate


def keycaps(pcb_path, shift):
    """Nominal 17.5 x 16.5 CS 1U envelopes (1.5u keys use the 1U box, as before)."""
    out = {}
    for fp in blocks(pcb_path.read_text(), "footprint"):
        if "SW_choc_v1_v2_HS_" not in fp.splitlines()[0]:
            continue
        at = coords(fp, "at", 2)
        angle = at[2] if len(at) == 3 else 0.0
        ref = re.search(r'\(property "Reference" "([^"]+)', fp).group(1)
        proxy = box(-8.75, -8.25, 1.6, 8.75, 8.25, 20)
        t = gp_Trsf(); t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(angle))
        proxy = BRepBuilderAPI_Transform(proxy, t, True).Shape()
        t = gp_Trsf(); t.SetTranslation(gp_Vec(at[0] - 150, 140 - at[1], 0))
        out[ref] = BRepBuilderAPI_Transform(proxy, t, True).Shape()
    assert len(out) == 36
    return out


def clearance(a, b):
    d = BRepExtrema_DistShapeShape(a, b)
    d.Perform()
    assert d.IsDone()
    return d.Value()


def verify(original, widened, case, plate, ring, seat):
    report = {"split_x_mm": SPLIT, "half_shift_from_original_mm": SHIFT}
    # Switch positions: stock PCB + 10 mm per half.
    stock = {r: s for r, s in keycaps(SOURCE_PCB, 0).items()}
    caps = keycaps(PCB, SHIFT)
    rows = []
    for ref, cap in caps.items():
        stock_gap = clearance(original, stock[ref])
        gap = clearance(case, cap)
        assert volume(BRepAlgoAPI_Common(case, cap).Shape()) < 1e-6, ref
        assert gap >= stock_gap - 1e-4, (ref, gap, stock_gap)
        rows.append({"reference": ref, "stock_case_clearance_mm": round(stock_gap, 4), "clearance_mm": round(gap, 4)})
    report["keycaps"] = {"minimum_clearance_mm": min(r["clearance_mm"] for r in rows),
                         "stock_minimum_clearance_mm": min(r["stock_case_clearance_mm"] for r in rows),
                         "every_key_at_least_stock": True, "positions": rows}
    base.PCB = PCB
    report["minimum_switch_body_clearance_mm"] = round(base.switch_body_clearance(case), 4)

    stack = pad_stack(seat)
    j2 = j2_courtyard()
    bottom, rim, pcb_bottom = overlay_levels(seat)
    stack_conn_bottom = pcb_bottom - PAD_CONNECTOR_H
    proxies = dict(stack)
    proxies.update({
        "401730 battery envelope": box(*BATTERY),
        "nice!nano assembled envelope": box(-9.0, 44.0, 2.6, 9.0, 77.0, 6.0),
        "USB shell/cable corridor": box(-4.8, 70.5, 1.6, 4.8, 78.0, 7.2),
        "WS2812B-V6": box(76.89, -0.76, 1.6, 81.89, 4.24, 3.2),
        "WS2812B-V6 pads and fillets": box(76.19, -0.41, 1.6, 82.59, 3.89, 1.9),
        "J2 FFC connector (PCB underside)": box(*j2[:2], -2.0, *j2[2:], 0.0),
        "FFC drop through the notch": box(FFC_SLOT_X[0] - 0.3, PAD_CENTRE[1] - FFC_WIDTH / 2, -1.6,
                                          FFC_SLOT_X[1] + 0.3, PAD_CENTRE[1] + FFC_WIDTH / 2, stack_conn_bottom),
        "FFC run under the board to J2": box(FFC_SLOT_X[0] - 0.3, PAD_CENTRE[1] - FFC_WIDTH / 2, -1.6,
                                             j2[0], PAD_CENTRE[1] + FFC_WIDTH / 2, 0.0),
        "power switch body (PCB underside)": box(*SW38_BODY),
        "power switch slider (PCB underside)": box(*SW38_SLIDER),
    })
    for name, solid in proxies.items():
        assert volume(BRepAlgoAPI_Common(case, solid).Shape()) < 1e-5, name
        assert volume(BRepAlgoAPI_Common(ring, solid).Shape()) < 1e-5, ("carrier", name)
        assert volume(BRepAlgoAPI_Common(plate, solid).Shape()) < 1e-5, ("tray", name)
    assert volume(BRepAlgoAPI_Common(stack["pad components"], box(*BATTERY)).Shape()) < 1e-6
    assert volume(BRepAlgoAPI_Common(case, ring).Shape()) < 1e-5
    # PCB outline (grown by the minimum clearance) never meets the case.
    board = polygon_prism(pcb_outline().buffer(PCB_MIN_CLEARANCE, join_style=2).simplify(0.01), 0.0, 1.6)
    assert volume(BRepAlgoAPI_Common(case, board).Shape()) < 1e-5, "PCB outline within 0.3 mm of the case"
    report["pcb_to_case_min_clearance_mm"] = PCB_MIN_CLEARANCE
    # The pad's connector and its cable drop into the PCB's FFC notch: both
    # must sit inside it with room to spare.
    from shapely.geometry import box as sbox
    outer, cutouts = pcb_board()
    connector = sbox(*PAD_CONNECTOR)
    notch = next(c for c in cutouts if c.intersects(connector))
    cable = sbox(FFC_SLOT_X[0] - 0.15, PAD_CENTRE[1] - FFC_WIDTH / 2, FFC_SLOT_X[1] + 0.15, PAD_CENTRE[1] + FFC_WIDTH / 2)
    for key, shape in (("pad_connector_to_notch_edge_mm", connector), ("ffc_to_notch_edge_mm", cable)):
        assert shape.within(notch), key
        report[key] = round(notch.exterior.distance(shape), 3)
    assert report["pad_connector_to_notch_edge_mm"] >= 0.4, report["pad_connector_to_notch_edge_mm"]
    # The carrier stands on board material only.
    slab = BRepAlgoAPI_Common(ring, box(-60, -60, 1.6, 60, 90, 1.7)).Shape()
    support = polygon_prism(outer, 1.6, 1.7)
    for hole in cutouts:
        support = cut(support, polygon_prism(hole, 1.5, 1.8))
    off_board = (volume(slab) - volume(BRepAlgoAPI_Common(slab, support).Shape())) / 0.1
    assert off_board < 1e-3, off_board
    report["carrier_footprint_off_board_mm2"] = round(off_board, 4)
    assert volume(BRepAlgoAPI_Common(case, plate).Shape()) < 1e-5
    # Tray hook: clear of the board itself, the carrier and the case, and able
    # to pass up through the opening when the tray is HOOK_SLIDE further forward.
    board_solid = polygon_prism(outer, 0.0, 1.6)
    for hole in cutouts:
        board_solid = cut(board_solid, polygon_prism(hole, -0.1, 1.7))
    assert volume(BRepAlgoAPI_Common(plate, board_solid).Shape()) < 1e-5, "tray meets the PCB"
    assert volume(BRepAlgoAPI_Common(plate, ring).Shape()) < 1e-5, "tray meets the carrier"
    opening = next(c for c in cutouts if c.contains(sbox(-1, 0, 1, 1)))
    lip_top = 1.6 + HOOK_LIP_GAP + HOOK_LIP_T
    sliding = sbox(-HOOK_HALF_W, HOOK_RISER[0] - HOOK_SLIDE, HOOK_HALF_W, OPENING_BACK_Y + HOOK_LIP - HOOK_SLIDE)
    assert sliding.within(opening), "hook cannot pass up through the opening"
    report["tray_hook"] = {
        "lip_overlap_on_board_mm": HOOK_LIP,
        "lip_above_board_mm": HOOK_LIP_GAP,
        "lip_thickness_mm": HOOK_LIP_T,
        "riser_thickness_mm": round(HOOK_RISER[1] - HOOK_RISER[0], 3),
        "riser_to_battery_envelope_mm": round(HOOK_RISER[0] - BATTERY[4], 3),
        "riser_to_opening_edge_mm": round(OPENING_BACK_Y - HOOK_RISER[1], 3),
        "width_mm": 2 * HOOK_HALF_W,
        "insert_slide_mm": round(HOOK_SLIDE, 3),
        "insert_clearance_to_opening_mm": round(opening.exterior.distance(sliding), 3),
        "lip_to_carrier_mm": round(clearance(plate, ring), 3),
        "lip_top_z_mm": round(lip_top, 3),
    }
    # Overlay flange is held: at least LEDGE_MIN of case material above it all round.
    x, y = PAD_CENTRE
    ledge = cut(cylinder(x, y, COUNTERBORE_R - 0.05, seat, seat + LEDGE_MIN - 0.05),
                cylinder(x, y, OPENING_R + 0.05, seat - 1, seat + 2))
    report["flange_ledge_fill_fraction"] = round(volume(BRepAlgoAPI_Common(case, ledge).Shape()) / volume(ledge), 4)
    assert report["flange_ledge_fill_fraction"] > 0.98
    # The overlay stands proud of the 2-degree roof: most at the front of the opening.
    proud = [round(rim - roof_z(widened, x, y + d), 2) for d in (-OPENING_R - 0.5, OPENING_R + 0.5)]
    assert BATTERY[5] < pcb_bottom - PAD_COMPONENTS and stack_conn_bottom > 1.6
    # Carrier top sits CARRIER_GIVE below the overlay's underside (foam tape).
    report.update({
        "flange_seat_z_mm": round(seat, 3),
        "ledge_min_mm": LEDGE_MIN,
        "overlay_rim_z_mm": round(rim, 3),
        "overlay_rim_above_roof_front_back_mm": proud,
        "overlay_from_cirque_drawing_mm": {"height": OVERLAY_HEIGHT, "flange": FLANGE_T, "pcb_pocket": OVERLAY_POCKET},
        "overlay_bottom_z_mm": round(bottom, 3),
        "pad_pcb_bottom_z_mm": round(pcb_bottom, 3),
        "pad_components_assumed_max_mm": PAD_COMPONENTS,
        "battery_envelope_z_mm": [BATTERY[2], BATTERY[5]],
        "battery_to_pad_components_mm": round(pcb_bottom - PAD_COMPONENTS - BATTERY[5], 3),
        "pad_connector_bottom_z_mm": round(stack_conn_bottom, 3),
        "carrier_print_short_by_mm": CARRIER_GIVE,
        "carrier_radial_play_mm": round(COUNTERBORE_R - CARRIER_R, 3),
        "j2_courtyard_case_xy_mm": [round(v, 3) for v in j2],
        "ffc_drop_to_j2_entry_mm": round(j2[0] - FFC_SLOT_X[1], 3),
        "case_volume_mm3": round(volume(case), 2),
        "tray_volume_mm3": round(volume(plate), 2),
        "carrier_volume_mm3": round(volume(ring), 2),
    })
    return report


def main():
    reader = STEPControl_Reader()
    assert int(reader.ReadFile(str(SOURCE))) == 1
    reader.TransferRoots()
    original = reader.OneShape()
    widened, case, seat = build_case(original)
    plate = tray()
    ring = carrier(seat)
    report = verify(original, widened, case, plate, ring, seat)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    stem = "TheENDGAME2024_NICE_NANO_CIRQUE"
    for shape, name in ((case, "CASE"), (plate, "BATTERY_TRAY"), (ring, "PAD_CARRIER")):
        write_step(shape, OUTPUT / f"{stem}_{name}.step")
        write_stl(shape, OUTPUT / f"{stem}_{name}.stl")
    import trimesh
    for name in ("CASE", "BATTERY_TRAY", "PAD_CARRIER"):
        mesh = trimesh.load(OUTPUT / f"{stem}_{name}.stl")
        assert mesh.is_watertight and mesh.is_winding_consistent, name
        report.setdefault("stl_watertight", []).append(name)
    report["top_max_above_roof_plane_mm"] = top_flatness(OUTPUT / f"{stem}_CASE.stl")
    assert report["top_max_above_roof_plane_mm"] < 0.05
    (VALIDATION / "geometry.json").write_text(json.dumps(report, indent=2) + "\n")
    preview(OUTPUT / f"{stem}_CASE.stl", OUTPUT / f"{stem}_PAD_CARRIER.stl", seat, OUTPUT / "case-preview.png")
    print(json.dumps({k: v for k, v in report.items() if k != "keycaps"}, indent=2))
    print("keycaps:", {k: v for k, v in report["keycaps"].items() if k != "positions"})
    print(f"Written to {OUTPUT}")


def top_flatness(case_stl):
    """Highest point of the case top above the plane fitted to the roof (1 mm grid)."""
    import numpy as np
    import trimesh
    mesh = trimesh.load(case_stl)
    (x0, y0, _), (x1, y1, _) = mesh.bounds
    xs, ys = np.meshgrid(np.arange(x0 + 1, x1 - 1, 1.0), np.arange(y0 + 1, y1 - 1, 1.0))
    pts = np.c_[xs.ravel(), ys.ravel()]
    hits, rays, _ = mesh.ray.intersects_location(np.c_[pts, np.full(len(pts), 40.0)],
                                                 np.tile([0.0, 0.0, -1.0], (len(pts), 1)), multiple_hits=False)
    a = np.c_[pts[rays], np.ones(len(rays))]
    z = hits[:, 2]
    fit, *_ = np.linalg.lstsq(a, z, rcond=None)
    on_roof = np.abs(z - a @ fit) < 0.3        # ignore openings and recesses
    fit, *_ = np.linalg.lstsq(a[on_roof], z[on_roof], rcond=None)
    return round(float((z - a @ fit).max()), 3)


def preview(case_stl, ring_stl, seat, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import trimesh
    from matplotlib.collections import PolyCollection
    case = trimesh.load(case_stl)
    ring = trimesh.load(ring_stl)
    fig, (top, sec) = plt.subplots(2, 1, figsize=(15, 10), gridspec_kw={"height_ratios": [2.2, 1]})
    up = case.face_normals[:, 2] > 0.3
    shade = 0.45 + 0.5 * case.face_normals[up][:, 1].clip(-1, 1) * 0 + 0.4 * case.triangles_center[up][:, 2] / 10
    top.add_collection(PolyCollection(case.triangles[up][:, :, :2], facecolors=plt.cm.Greys(shade.clip(0.2, 0.9)), edgecolors="none"))
    top.add_patch(plt.Circle(PAD_CENTRE, STEP_R, color="#333", alpha=0.85))
    top.add_patch(plt.Rectangle((LED_POCKET[0] + 0.5, LED_POCKET[1] + 1.5), 5, 5, color="#ff8c1a"))
    top.set_xlim(-125, 125); top.set_ylim(-24, 82); top.set_aspect("equal")
    top.set_title("nice!nano + Cirque case: top view (pad overlay dark, LED orange)")
    plate = trimesh.load(str(case_stl).replace("_CASE.stl", "_BATTERY_TRAY.stl"))
    for mesh, colour, label in ((case, "#555", "case"), (ring, "#2a9d8f", "pad carrier"), (plate, "#3a0ca3", "battery tray")):
        for a, b in trimesh.intersections.mesh_plane(mesh, [1, 0, 0], [0, 0, 0]):
            sec.plot([a[1], b[1]], [a[2], b[2]], color=colour, lw=1.2)
        sec.plot([], [], color=colour, label=label)
    for name, solid_box, colour in (("battery", (BATTERY[1], BATTERY[2], BATTERY[4], BATTERY[5]), "#f4c430"),):
        sec.add_patch(plt.Rectangle((solid_box[0], solid_box[1]), solid_box[2] - solid_box[0], solid_box[3] - solid_box[1], color=colour, alpha=0.5, label=name))
    bottom, rim, pcb_bottom = overlay_levels(seat)
    y = PAD_CENTRE[1]
    sec.add_patch(plt.Rectangle((y - PAD_R, pcb_bottom), 2 * PAD_R, PAD_PCB, color="#4cb391", label="pad PCB"))
    for y0, y1 in ((y - FLANGE_R, y - POCKET_R), (y + POCKET_R, y + FLANGE_R)):
        sec.add_patch(plt.Rectangle((y0, bottom), y1 - y0, FLANGE_T, color="#222", alpha=0.6))
    sec.add_patch(plt.Rectangle((y - STEP_R, seat), 2 * STEP_R, rim - seat, color="#222", alpha=0.6, label="overlay (from Cirque drawing)"))
    sec.axhline(0, color="#2e7d32", lw=0.6); sec.axhline(1.6, color="#2e7d32", lw=0.6)
    sec.set_xlim(-25, 85); sec.set_ylim(-3, 11); sec.set_aspect("equal"); sec.legend(fontsize=8, loc="upper right")
    sec.set_title("Section at X=0 (Y across): flat roof; overlay held between the ledge and the carrier; battery below")
    sec.set_xlabel("Y (mm)")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
