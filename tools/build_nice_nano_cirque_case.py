#!/usr/bin/env python3
"""Build the nice!nano + Cirque case, battery tray and touchpad carrier.

The original Endgame case is split at X=+-7 mm (inside the solid waist, so no
key opening crosses a split) and each half moves outward 10 mm to match the
239 mm Cirque PCB. Central features (controller, USB, battery, J1 and tray
mounts) are re-cut at their fixed positions. The power switch is on the PCB
underside at the USB opening, so the case has no switch hole. A flat bezel holds a Cirque
TM040040 with the curved overlay 50-000090-00, clamped from below by a
printed C-ring; the battery stays under the pad in the PCB opening, lowered
0.5 mm into the tray. The status LED pocket sits in the right thumb gap.

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
OVERLAY_HEIGHT, FLANGE_T = 1.5, 0.6     # assumed until measured
PAD_CONNECTOR = (11.6, 12.5, 14.6, 21.5)  # 12-pin vertical FFC, faces +X
OPENING_R = STEP_R + 0.17          # through the roof for the overlay step
COUNTERBORE_R = FLANGE_R + 0.18    # flange seat, open from below
LANDING_R, COLLAR_BASE_R, COLLAR_DROP = 24.6, 25.8, 1.2
COUNTERSINK_R, COUNTERSINK_H = 23.6, 1.5
BATTERY = (-9.25, -3.0, -0.5, 9.25, 30.0, 4.5)   # 401730 envelope, 0.5 mm lower
LED_POCKET = (76.39, -1.26, 82.39, 4.74, 3.55)   # LED1 only; its passives are underneath
# SW38 sits under the nice!nano on the PCB underside; its slider reaches out
# through the USB opening at the back edge (case X 0.1..1.4, Y to 78.7).
SW38_BODY = (-3.35, 74.9, -1.4, 3.35, 77.5, 0.0)
SW38_SLIDER = (-0.1, 77.0, -1.4, 1.6, 78.8, 0.0)
CENTRAL_MOUNTS = [(-9.804941, -14.168516), (9.804965, -14.170142)]


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


def frustum(x, y, r0, z0, r1, z1):
    return conical_recess(x, y, r0, r1, z0, z1)


def pad_stack(rim):
    """Proxy solids for the installed touchpad, keyed by name."""
    x, y = PAD_CENTRE
    over = rim - OVERLAY_HEIGHT
    pcb_bottom = over - PAD_PCB
    cx0, cy0, cx1, cy1 = PAD_CONNECTOR
    return {
        "overlay step": cylinder(x, y, STEP_R, over + FLANGE_T, rim),
        "overlay flange": cylinder(x, y, FLANGE_R, over, over + FLANGE_T),
        "pad PCB": cylinder(x, y, PAD_R, pcb_bottom, over),
        "pad components": cylinder(x, y, KEEPOUT_R, pcb_bottom - PAD_COMPONENTS, pcb_bottom),
        "pad FFC connector": box(cx0, cy0, pcb_bottom - PAD_CONNECTOR_H, cx1, cy1, pcb_bottom),
    }


def carrier(rim):
    """C-ring clamping the pad PCB rim (outside its component area) up to the bezel."""
    x, y = PAD_CENTRE
    top = rim - OVERLAY_HEIGHT - PAD_PCB
    ring = cut(cylinder(x, y, PAD_R - 0.2, 1.6, top), cylinder(x, y, KEEPOUT_R + 0.3, 1.5, top + 0.1))
    # Open over the battery and the opening below the pad's front half.
    return cut(ring, box(-12.5, y - 30, 1.0, 12.5, y, top + 1))


def build_case(original):
    widened = widened_case(original)
    case = widened
    rim = roof_z(original, *PAD_CENTRE)
    flange_top = rim - OVERLAY_HEIGHT + FLANGE_T
    x, y = PAD_CENTRE
    # Collar: flat landing at rim height with a chamfer down to the roof; it
    # only shows where the 2-degree roof falls below the rim (front half).
    case = fuse(case, fuse(cylinder(x, y, LANDING_R, rim - COLLAR_DROP, rim),
                           frustum(x, y, COLLAR_BASE_R, rim - COLLAR_DROP, LANDING_R, rim)))
    # Countersink blending the rim into the higher back half of the roof.
    case = cut(case, fuse(frustum(x, y, OPENING_R, rim, COUNTERSINK_R, rim + COUNTERSINK_H),
                          cylinder(x, y, COUNTERSINK_R, rim + COUNTERSINK_H, 20)))
    case = cut(case, cylinder(x, y, OPENING_R, flange_top - 0.01, 20))
    case = cut(case, cylinder(x, y, COUNTERBORE_R, -2, flange_top))
    # Battery pocket corners reach just beyond the counterbore.
    case = cut(case, rounded_prism(-11.1, -4.1, 11.1, 31.1, 1.0, -2, BATTERY[5] + 0.2))

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
    return widened, case, rim


def tray():
    plate = rounded_prism(-12.0, -5.0, 12.0, 32.0, 1.5, -1.5, -0.5)
    for x, y in CENTRAL_MOUNTS:
        # Ears stop 0.3 mm short of the case's inner front wall at Y=-18.19.
        plate = fuse(plate, rounded_prism(x - 4.1, -17.9, x + 4.1, -4.0, 3.5, -1.8, 0.0))
    for x, y in CENTRAL_MOUNTS:
        plate = cut(plate, cylinder(x, y, 3.1, -1.9, -1.6))
        plate = cut(plate, conical_recess(x, y, 3.1, 1.65, -1.6, -0.15))
        plate = cut(plate, cylinder(x, y, 1.65, -0.15, 0.1))
    # FFC path from the PCB notch to J2 on the underside.
    plate = cut(plate, box(10.5, 10.5, -2.5, 13.0, 23.5, 0.5))
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


def verify(original, case, plate, ring, rim):
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

    stack = pad_stack(rim)
    proxies = dict(stack)
    proxies.update({
        "401730 battery envelope": box(*BATTERY),
        "nice!nano assembled envelope": box(-9.0, 44.0, 2.6, 9.0, 77.0, 6.0),
        "USB shell/cable corridor": box(-4.8, 70.5, 1.6, 4.8, 78.0, 7.2),
        "WS2812B-V6": box(76.89, -0.76, 1.6, 81.89, 4.24, 3.2),
        "power switch body (PCB underside)": box(*SW38_BODY),
        "power switch slider (PCB underside)": box(*SW38_SLIDER),
    })
    for name, solid in proxies.items():
        assert volume(BRepAlgoAPI_Common(case, solid).Shape()) < 1e-5, name
        assert volume(BRepAlgoAPI_Common(ring, solid).Shape()) < 1e-5, ("carrier", name)
        assert volume(BRepAlgoAPI_Common(plate, solid).Shape()) < 1e-5, ("tray", name)
    assert volume(BRepAlgoAPI_Common(stack["pad components"], box(*BATTERY)).Shape()) < 1e-6
    assert volume(BRepAlgoAPI_Common(case, ring).Shape()) < 1e-5
    assert volume(BRepAlgoAPI_Common(case, plate).Shape()) < 1e-5
    # Overlay flange is held: case material directly above it all round.
    over = rim - OVERLAY_HEIGHT
    ledge = cut(cylinder(*PAD_CENTRE, COUNTERBORE_R - 0.05, over + FLANGE_T, over + FLANGE_T + 0.6),
                cylinder(*PAD_CENTRE, OPENING_R + 0.05, over, over + 2))
    report["flange_ledge_fill_fraction"] = round(volume(BRepAlgoAPI_Common(case, ledge).Shape()) / volume(ledge), 4)
    assert report["flange_ledge_fill_fraction"] > 0.98
    # Carrier touches the pad PCB underside: ring top = pad PCB bottom.
    report.update({
        "rim_z_mm": round(rim, 3),
        "overlay_height_assumed_mm": OVERLAY_HEIGHT,
        "flange_thickness_assumed_mm": FLANGE_T,
        "pad_pcb_bottom_z_mm": round(over - PAD_PCB, 3),
        "pad_components_assumed_max_mm": PAD_COMPONENTS,
        "battery_envelope_z_mm": [BATTERY[2], BATTERY[5]],
        "battery_to_pad_components_mm": round(over - PAD_PCB - PAD_COMPONENTS - BATTERY[5], 3),
        "pad_connector_bottom_z_mm": round(over - PAD_PCB - PAD_CONNECTOR_H, 3),
        "pad_connector_drops_into_pcb_notch": True,
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
    widened, case, rim = build_case(original)
    plate = tray()
    ring = carrier(rim)
    report = verify(original, case, plate, ring, rim)

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
    xs = []
    reader = STEPControl_Reader()
    (VALIDATION / "geometry.json").write_text(json.dumps(report, indent=2) + "\n")
    preview(OUTPUT / f"{stem}_CASE.stl", OUTPUT / f"{stem}_PAD_CARRIER.stl", rim, OUTPUT / "case-preview.png")
    print(json.dumps({k: v for k, v in report.items() if k != "keycaps"}, indent=2))
    print("keycaps:", {k: v for k, v in report["keycaps"].items() if k != "positions"})
    print(f"Written to {OUTPUT}")


def preview(case_stl, ring_stl, rim, path):
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
    for mesh, colour, label in ((case, "#555", "case"), (ring, "#2a9d8f", "pad carrier")):
        for a, b in trimesh.intersections.mesh_plane(mesh, [1, 0, 0], [0, 0, 0]):
            sec.plot([a[1], b[1]], [a[2], b[2]], color=colour, lw=1.2)
        sec.plot([], [], color=colour, label=label)
    for name, solid_box, colour in (("battery", (BATTERY[1], BATTERY[2], BATTERY[4], BATTERY[5]), "#f4c430"),):
        sec.add_patch(plt.Rectangle((solid_box[0], solid_box[1]), solid_box[2] - solid_box[0], solid_box[3] - solid_box[1], color=colour, alpha=0.5, label=name))
    over = rim - OVERLAY_HEIGHT
    y = PAD_CENTRE[1]
    sec.add_patch(plt.Rectangle((y - PAD_R, over - PAD_PCB), 2 * PAD_R, PAD_PCB, color="#4cb391", label="pad PCB"))
    sec.add_patch(plt.Rectangle((y - FLANGE_R, over), 2 * FLANGE_R, FLANGE_T, color="#222", alpha=0.6, label="overlay"))
    sec.add_patch(plt.Rectangle((y - STEP_R, over + FLANGE_T), 2 * STEP_R, OVERLAY_HEIGHT - FLANGE_T, color="#222", alpha=0.6))
    sec.axhline(0, color="#2e7d32", lw=0.6); sec.axhline(1.6, color="#2e7d32", lw=0.6)
    sec.set_xlim(-25, 85); sec.set_ylim(-3, 11); sec.set_aspect("equal"); sec.legend(fontsize=8, loc="upper right")
    sec.set_title("Section at X=0 (Y across): pad clamped between bezel ledge and carrier; battery below")
    sec.set_xlabel("Y (mm)")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
