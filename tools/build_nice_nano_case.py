#!/usr/bin/env python3
"""Build the nice!nano / 401730 prototype case and serviceable lower tray.

Requires cadquery-ocp 8.0.1.0.0. Source STEP is read only. All coordinates are
in the case frame: (PCB X - 150, 140 - PCB Y, Z). The PCB occupies Z=0..1.6.
Run from any directory: python tools/build_nice_nano_case.py
"""

from pathlib import Path
import json
import math
import re
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder
from OCP.GProp import GProp_GProps
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.StlAPI import StlAPI_Writer
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from verify_choc_compatibility import blocks, coords


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "002 CASE/TheENDGAME2024_CASE001.step"
OUTPUT = ROOT / "002 CASE/NICE NANO WIRELESS"


def box(x0, y0, z0, x1, y1, z1):
    assert x0 < x1 and y0 < y1 and z0 < z1
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), x1 - x0, y1 - y0, z1 - z0).Shape()


def cylinder(x, y, radius, z0, z1):
    return BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(x, y, z0), gp_Dir(0, 0, 1)), radius, z1 - z0
    ).Shape()


def conical_recess(x, y, lower_radius, upper_radius, z0, z1):
    return BRepPrimAPI_MakeCone(
        gp_Ax2(gp_Pnt(x, y, z0), gp_Dir(0, 0, 1)),
        lower_radius, upper_radius, z1 - z0,
    ).Shape()


def fuse(a, b):
    operation = BRepAlgoAPI_Fuse(a, b)
    operation.Build()
    assert operation.IsDone(), "Fuse failed"
    return operation.Shape()


def cut(a, b):
    operation = BRepAlgoAPI_Cut(a, b)
    operation.Build()
    assert operation.IsDone(), "Cut failed"
    return operation.Shape()


def rounded_prism(x0, y0, x1, y1, radius, z0, z1):
    """An extruded rectangle with constant-radius vertical corners."""
    assert 2 * radius < min(x1 - x0, y1 - y0)
    shape = fuse(
        box(x0 + radius, y0, z0, x1 - radius, y1, z1),
        box(x0, y0 + radius, z0, x1, y1 - radius, z1),
    )
    for x in (x0 + radius, x1 - radius):
        for y in (y0 + radius, y1 - radius):
            shape = fuse(shape, cylinder(x, y, radius, z0, z1))
    return shape


def volume(shape):
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties)
    return properties.Mass()


def solids(shape):
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def write_step(shape, path):
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    assert int(writer.Write(str(path))) == 1, f"STEP export failed: {path}"


def write_stl(shape, path):
    BRepMesh_IncrementalMesh(shape, 0.08, False, 0.2, True)
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    assert writer.Write(shape, str(path)), f"STL export failed: {path}"


def verify_exports_and_preview(case_volume, tray_volume, switch_clearance, original):
    """Reimport neutral CAD and mesh exports, then render projected mesh views."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection, LineCollection
    import numpy as np
    import trimesh
    import tempfile

    report = {"coordinate_frame": "(PCB X - 150, 140 - PCB Y, Z)", "parts": {}}
    parts = (
        ("case", "TheENDGAME2024_NICE_NANO_CASE", case_volume),
        ("tray", "TheENDGAME2024_NICE_NANO_BATTERY_TRAY", tray_volume),
    )
    meshes = {}
    for label, stem, expected_volume in parts:
        step_path = OUTPUT / f"{stem}.step"
        stl_path = OUTPUT / f"{stem}.stl"
        reader = STEPControl_Reader()
        assert int(reader.ReadFile(str(step_path))) == 1
        reader.TransferRoots()
        imported = reader.OneShape()
        assert solids(imported) == 1 and BRepCheck_Analyzer(imported).IsValid()
        # STEP healing at narrow cavity edges changes the case volume
        # by about 1.24 mm3 (0.0021%) without changing its solid validity.
        assert abs(volume(imported) - expected_volume) < 2.0, (
            label, volume(imported), expected_volume
        )
        mesh = trimesh.load_mesh(stl_path, process=True)
        assert mesh.is_watertight and mesh.is_winding_consistent
        assert abs(mesh.volume - expected_volume) < 2.0
        meshes[label] = mesh
        report["parts"][label] = {
            "step_valid_single_solid": True,
            "step_volume_mm3": round(volume(imported), 3),
            "stl_watertight": True,
            "stl_winding_consistent": True,
            "stl_faces": len(mesh.faces),
            "stl_volume_mm3": round(mesh.volume, 3),
        }
    report.update({
        "original_case_exterior_and_key_openings_retained": True,
        "added_controller_shoulders": False,
        "usb_local_cover_min_top_z_mm": 8.55,
        "battery_pocket_pcb_xy_mm": [139, 109, 161, 144],
        "battery_pack_proxy_xyz_mm": [18.5, 33.0, 5.0],
        "battery_pack_proxy_is_a_maximum": False,
        "battery_roof_minimum_mm": 1.25,
        "controller_cavity_top_z_mm": 6.5,
        "controller_complete_assembly_max_z_mm": 6.0,
        "controller_central_16mm_roof_minimum_mm": 1.25,
        "usb_passage_top_z_mm": 7.3,
        "usb_crown_roof_mm": 1.25,
        "all_36_switch_body_proxies_clear": True,
        "minimum_switch_body_proxy_clearance_mm": round(switch_clearance, 4),
        "nominal_cs_1u_envelope_checked": True,
        "physical_keycap_fit_verified": False,
    })
    validation_dir = ROOT / "docs/validation/nice-nano-case"
    validation_dir.mkdir(parents=True, exist_ok=True)
    (validation_dir / "geometry.json").write_text(json.dumps(report, indent=2) + "\n")

    def projection(ax, mesh, side, title, xlim=None, ylim=None):
        faces = mesh.faces
        normals = mesh.face_normals
        z = mesh.triangles_center[:, 2]
        ids = np.flatnonzero(normals[:, 2] > 0.25 if side == "top" else normals[:, 2] < -0.25)
        ids = ids[np.argsort(z[ids] if side == "top" else -z[ids])]
        tris = mesh.vertices[faces[ids], :2]
        palette = plt.cm.Blues if side == "top" else plt.cm.Greys
        z0, z1 = mesh.bounds[:, 2]
        scale = (z[ids] - z0) / max(z1 - z0, 1e-9)
        colors = palette(0.28 + 0.52 * scale)
        ax.add_collection(PolyCollection(tris, facecolors=colors, edgecolors="none", rasterized=True))
        ax.set_xlim(*(xlim if xlim else mesh.bounds[:, 0] + [-2, 2]))
        ax.set_ylim(*(ylim if ylim else mesh.bounds[:, 1] + [-2, 2]))
        ax.set_aspect("equal")
        ax.grid(alpha=0.15)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Case X (mm)")
        ax.set_ylabel("Case Y (mm)")

    fig = plt.figure(figsize=(15, 10), layout="constrained")
    grid = fig.add_gridspec(2, 2, height_ratios=[1.15, 1])
    ax = fig.add_subplot(grid[0, :])
    projection(ax, meshes["case"], "bottom", "Case underside: enlarged battery pocket, LED and controller cavities")
    ax.annotate("battery pocket", xy=(0, 14), xytext=(25, 30), arrowprops={"arrowstyle": "->"})
    ax.annotate("LED pocket", xy=(0, 36.5), xytext=(26, 43), arrowprops={"arrowstyle": "->"})
    ax.annotate("nice!nano cavity", xy=(0, 57), xytext=(25, 66), arrowprops={"arrowstyle": "->"})
    ax = fig.add_subplot(grid[1, 0])
    projection(ax, meshes["case"], "top", "Top: original sloped roof and key-opening edges", (-35, 35), (15, 84))
    ax = fig.add_subplot(grid[1, 1])
    projection(ax, meshes["tray"], "top", "Removable insulating battery tray", (-18, 18), (-20, 34))
    fig.suptitle("Endgame nice!nano / 401730 case prototype", fontsize=17)
    fig.savefig(OUTPUT / "case-and-tray-preview.png", dpi=170, facecolor="white")
    plt.close(fig)

    # Centreline section makes the small local height change visible.
    with tempfile.TemporaryDirectory() as tmp:
        original_path = Path(tmp) / "original.stl"
        write_stl(original, original_path)
        original_mesh = trimesh.load_mesh(original_path, process=True)
    assert abs(meshes["case"].bounds[1, 2] - original_mesh.bounds[1, 2]) < 0.002
    report["maximum_case_height_increased"] = False
    report["original_case_z_bounds_mm"] = original_mesh.bounds[:, 2].tolist()
    report["revised_case_z_bounds_mm"] = meshes["case"].bounds[:, 2].tolist()
    (validation_dir / "geometry.json").write_text(json.dumps(report, indent=2) + "\n")
    fig, ax = plt.subplots(figsize=(14, 3.5), layout="constrained")
    for mesh, color, label, style in (
        (meshes["case"], "#2563a6", "Revised case", "-"),
        (original_mesh, "#555555", "Original case", "--"),
    ):
        segments = trimesh.intersections.mesh_plane(
            mesh, plane_origin=[0, 0, 0], plane_normal=[1, 0, 0])
        assert len(segments) > 0
        ax.add_collection(LineCollection(segments[:, :, 1:3], colors=color,
                          linestyles=style, linewidths=1.8, label=label))
    ax.annotate("nice!nano recess", xy=(53, 6.5), xytext=(39, 12),
                arrowprops={"arrowstyle": "->"}, color="#2563a6")
    ax.annotate("USB recess", xy=(76, 7.3), xytext=(65, 12),
                arrowprops={"arrowstyle": "->"}, color="#2563a6")
    ax.annotate("Original roof retained over battery", xy=(12, 7.6),
                xytext=(-17, 12), arrowprops={"arrowstyle": "->"})
    ax.set(xlim=(-24, 84), ylim=(-3, 15), xlabel="Case Y (mm)", ylabel="Z (mm)",
           title="Centreline section: original exterior height retained, deeper internal pockets")
    ax.set_aspect("equal")
    ax.grid(alpha=0.15)
    ax.legend(loc="lower left", ncol=2)
    fig.savefig(OUTPUT / "case-side-profile.png", dpi=170, facecolor="white")
    plt.close(fig)


def switch_body_clearance(case):
    """Use the same conservative V2 envelopes as tools/check_case_fit.py."""
    board = (ROOT / "001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb").read_text()
    distances = []
    for footprint in blocks(board, "footprint"):
        if "SW_choc_v1_v2_HS_" not in footprint.splitlines()[0]:
            continue
        at = coords(footprint, "at", 2)
        angle = at[2] if len(at) == 3 else 0.0
        ref = re.search(r'\(property "Reference" "([^"]+)', footprint).group(1)
        body = box(-7.5, -7.5, 1.6, 7.5, 7.5, 8.0)
        transform = gp_Trsf()
        transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(angle))
        body = BRepBuilderAPI_Transform(body, transform, True).Shape()
        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(at[0] - 150, 140 - at[1], 0))
        body = BRepBuilderAPI_Transform(body, transform, True).Shape()
        distance = BRepExtrema_DistShapeShape(case, body)
        distance.Perform()
        assert distance.IsDone()
        overlap = volume(BRepAlgoAPI_Common(case, body).Shape())
        assert overlap < 1e-6, f"Case collides with {ref}: {overlap} mm³"
        distances.append(distance.Value())
    assert len(distances) == 36, f"Found {len(distances)} Choc footprints"
    assert min(distances) > 0
    return min(distances)


def cs_keycap_clearance(original, revised):
    """Check the user's nominal CS 1U footprint over the entire case height.

    This deliberately makes no assumption about skirt height at rest or at
    bottom-out. It is a centred 17.5 x 16.5 mm bounding envelope, not a model
    of every CS variant or a claim about wider thumb caps or print tolerance.
    """
    board = (ROOT / "001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb").read_text()
    rows = []
    for footprint in blocks(board, "footprint"):
        if "SW_choc_v1_v2_HS_" not in footprint.splitlines()[0]:
            continue
        at = coords(footprint, "at", 2)
        angle = at[2] if len(at) == 3 else 0.0
        ref = re.search(r'\(property "Reference" "([^"]+)', footprint).group(1)
        proxy = box(-8.75, -8.25, 1.6, 8.75, 8.25, 20)
        transform = gp_Trsf()
        transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(angle))
        proxy = BRepBuilderAPI_Transform(proxy, transform, True).Shape()
        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(at[0] - 150, 140 - at[1], 0))
        proxy = BRepBuilderAPI_Transform(proxy, transform, True).Shape()
        row = {"reference": ref}
        for name, shape in (("original", original), ("revised", revised)):
            overlap = volume(BRepAlgoAPI_Common(shape, proxy).Shape())
            distance = BRepExtrema_DistShapeShape(shape, proxy)
            distance.Perform()
            assert distance.IsDone() and overlap < 1e-6, (ref, name, overlap)
            row[f"{name}_clearance_mm"] = distance.Value()
        assert row["revised_clearance_mm"] >= row["original_clearance_mm"] - 1e-5, ref
        rows.append(row)
    assert len(rows) == 36
    report = {
        "footprint_mm": [17.5, 16.5],
        "footprint_source": "User-specified nominal CS 1U size, centred on each switch",
        "swept_z_bounds_mm": [1.6, 20],
        "coordinate_datum": "PCB bottom Z=0; no assumed resting skirt height",
        "all_36_nominal_1u_envelopes_clear": True,
        "minimum_clearance_mm": min(r["revised_clearance_mm"] for r in rows),
        "original_clearance_preserved": True,
        "physical_print_or_wider_thumb_caps_verified": False,
        "positions": rows,
    }
    out = ROOT / "docs/validation/nice-nano-case/cs-clearance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report["minimum_clearance_mm"]


def main():
    reader = STEPControl_Reader()
    assert int(reader.ReadFile(str(SOURCE))) == 1
    reader.TransferRoots()
    original = reader.OneShape()
    assert solids(original) == 1 and BRepCheck_Analyzer(original).IsValid()

    # The intended PCB opening is X=139..161, Y=109..144 (22 x 35, R1).
    # It is extended 7 mm toward the controller from the XIAO revision.
    # The inset 401730 planning envelope is Z=0.2..5.2; neither the
    # full taped pack size nor the allowed charging current is established.
    pocket = rounded_prism(-11.1, -4.1, 11.1, 31.1, 1.0, 0.0, 5.35)
    revised = cut(original, pocket)

    # J1 direct-solder B+/B- on PCB at (148,147.5), (152,147.5), with two
    # strain holes at Y=150.5. No connector. The recess allows battery
    # leads above F.Cu and terminates before the M3 mounts.
    wire_channel = rounded_prism(-3.4, -11.1, 3.4, -3.6, 0.8, 0.0, 3.0)
    revised = cut(revised, wire_channel)

    # Status LED near PCB (150,103.5), on the upper PCB face. A 5x5x1.6
    # body is enclosed below the unbroken translucent-PLA roof. The local
    # component pocket also clears its nearby 0603 capacitor and resistors.
    revised = cut(revised, rounded_prism(-6.7, 33.0, 6.2, 40.2, 0.6, 0.0, 3.55))

    # Low-post soldered nice!nano v2: assumed body X=141..159, Y=63..96 on
    # the host PCB. The module's entire assembled vertical envelope (USB
    # included) must be within Z=2.6..6.0. This assumes its lowest underside
    # projection stands 1.0 mm above host PCB top Z=1.6 and its full module
    # envelope is no more than 3.4 mm high. A jig/spacer must control this
    # before short individual posts are soldered. Socket height alone does
    # not establish the complete module envelope. The 6.5 mm cavity gives
    # 0.5 mm headroom. Preserve the stock key-opening edges: an added 20 mm
    # hood cleared switch bodies but intruded into the moving cap footprint.
    # The original roof covers the recess; its edges follow the stock profile.
    revised = cut(revised, rounded_prism(-9.2, 43.2, 9.2, 77.8, 1.0, 0.0, 6.5))
    # USB-C at negative PCB Y (positive case Y). Entry reaches beyond the
    # old case edge at Y≈80.44 and is open through the original case end wall.
    # The source sloped roof already encloses this cover envelope. Retain
    # at least 1.25 mm over the Z=7.3 passage without increasing case height.
    usb_crown = rounded_prism(-7.4, 69.6, 7.4, 79.7, 1.0, 7.2, 8.55)
    revised = fuse(revised, usb_crown)
    revised = cut(revised, rounded_prism(-6.4, 70.0, 6.4, 82.0, 0.8, 0.0, 7.3))

    # PCM12 at PCB (150,154): body to board Y=155.6, actuator to 157.15.
    # The case front is near Y=-21.57 in this frame; this channel exposes
    # the recessed slider. A printed/fitted actuator cap may still be needed.
    revised = cut(revised, rounded_prism(-4.1, -22.3, 4.1, -12.4, 0.7, 0.0, 4.2))

    # The two central 4 mm PCB holes were used for rubber grommets in the
    # original. Unlike the four outer M3 mount holes, they have no case heat-
    # insert bores. Fill the original 1.2 mm gap with standoffs down to the
    # board top Z=1.6, then add D4.6×4.0 mm bores matching the original M3
    # D4.6 L3 inserts. The exterior stays at the source-case height.
    mounts = [(-9.804941, -14.168516), (9.804965, -14.170142)]
    for x, y in mounts:
        revised = fuse(revised, cylinder(x, y, 4.5, 1.6, 2.9))
        revised = cut(revised, cylinder(x, y, 2.3, 1.5, 5.6))

    # Insulating lower tray: 1.0 mm plate under the opening, with 1.8 mm
    # thick ears at the existing PCB holes. A 90-degree D6.2 countersink
    # seats M3×6 DIN965 heads flush at Z=-1.8. Feet projecting >=1.0 mm
    # below the source case perimeter Z=-1.4 put desk at <=Z=-2.4, leaving
    # >=0.6 mm for the screw heads and ear bottoms.
    tray = rounded_prism(-12.0, -5.0, 12.0, 32.0, 1.5, -1.0, 0.0)
    for x, y in mounts:
        ear = rounded_prism(x - 4.1, y - 4.1, x + 4.1, -4.0, 3.5, -1.8, 0.0)
        tray = fuse(tray, ear)
    for x, y in mounts:
        tray = cut(tray, cylinder(x, y, 3.1, -1.9, -1.6))
        tray = cut(tray, conical_recess(x, y, 3.1, 1.65, -1.6, -0.15))
        tray = cut(tray, cylinder(x, y, 1.65, -0.15, 0.1))

    assert BRepCheck_Analyzer(revised).IsValid() and solids(revised) == 1
    assert BRepCheck_Analyzer(tray).IsValid() and solids(tray) == 1
    assert volume(BRepAlgoAPI_Common(revised, tray).Shape()) < 1e-5
    # Only the two internal tray mounts add material. Keep the original
    # exterior and key-opening edges, including the controller's narrow waist.
    additions = cut(revised, original)
    for x, y in mounts:
        additions = cut(additions, cylinder(x, y, 4.51, 1.59, 2.91))
    assert abs(volume(additions)) < 1e-5

    # Validate installed-part envelope clearances. The nominal pouch has
    # square proxy corners here, a stricter check than its rounded real pouch.
    proxies = {
        "assumed complete 401730 pack": box(-9.25, -3.0, 0.2, 9.25, 30.0, 5.2),
        "short-post nice!nano full assembled envelope": box(-9.0, 44.0, 2.6, 9.0, 77.0, 6.0),
        "USB shell/cable corridor": box(-4.8, 70.5, 1.6, 4.8, 78.0, 7.2),
        "USB plug entry to exterior": box(-5.5, 78.0, 1.6, 5.5, 81.8, 7.2),
        "R1 body": box(-4.9, 37.2, 1.6, -4.1, 38.8, 2.5),
        "R2 body": box(-6.3, 35.1, 1.6, -4.7, 35.9, 2.5),
        "C1 body": box(4.1, 37.2, 1.6, 4.9, 38.8, 2.5),
        "WS2812B-V6 body": box(-2.5, 34.0, 1.6, 2.5, 39.0, 3.2),
        "power switch body and slider": box(-3.35, -17.15, 1.6, 3.35, -13.0, 3.1),
    }
    for label, solid in proxies.items():
        overlap = volume(BRepAlgoAPI_Common(revised, solid).Shape())
        assert overlap < 1e-5, f"Case intersects {label}: {overlap} mm³"

    # Retained roof of the enlarged battery cavity. This requires full
    # material through Z=6.6 over the complete candidate opening, not just
    # at the former 28 mm pocket location.
    source_roof = BRepAlgoAPI_Common(
        original, box(-11.1, -4.1, 5.35, 11.1, 31.1, 6.6)
    ).Shape()
    assert abs(volume(source_roof) - 22.2 * 35.2 * 1.25) < 1e-5
    final_roof = BRepAlgoAPI_Common(
        revised, box(-11.1, -4.1, 5.35, 11.1, 31.1, 6.6)
    ).Shape()
    assert abs(volume(final_roof) - 22.2 * 35.2 * 1.25) < 1e-5
    led_roof = box(-2.5, 34.0, 3.55, 2.5, 39.0, 6.6)
    assert abs(volume(BRepAlgoAPI_Common(revised, led_roof).Shape()) - volume(led_roof)) < 1e-5
    # Check the central roof; its narrow side edges retain the original
    # key-opening contour rather than extending into the keycap footprint.
    nano_roof = box(-8.0, 44.0, 6.5, 8.0, 69.0, 7.75)
    assert abs(volume(BRepAlgoAPI_Common(revised, nano_roof).Shape()) - volume(nano_roof)) < 1e-5
    roof_region = box(-10, 43.2, 6.5, 10, 69.6, 12)
    original_roof_volume = volume(BRepAlgoAPI_Common(original, roof_region).Shape())
    revised_roof_volume = volume(BRepAlgoAPI_Common(revised, roof_region).Shape())
    # Repeated curved-surface Boolean integration differs by ~0.00055 mm3.
    # The independent additions check above also forbids new roof material.
    assert abs(original_roof_volume - revised_roof_volume) < 0.002, (original_roof_volume, revised_roof_volume)
    usb_roof = box(-5.5, 71.0, 7.3, 5.5, 77.0, 8.55)
    assert abs(volume(BRepAlgoAPI_Common(revised, usb_roof).Shape()) - volume(usb_roof)) < 1e-5
    for x, y in mounts:
        insert_bore = cylinder(x, y, 2.3, 1.6, 5.6)
        assert volume(BRepAlgoAPI_Common(revised, insert_bore).Shape()) < 1e-5
        insert_roof = cylinder(x, y, 2.3, 5.6, 6.6)
        assert abs(volume(BRepAlgoAPI_Common(revised, insert_roof).Shape()) - volume(insert_roof)) < 1e-5
        screw_head = fuse(
            cylinder(x, y, 3.1, -1.8, -1.6),
            conical_recess(x, y, 3.1, 1.65, -1.6, -0.15),
        )
        assert volume(BRepAlgoAPI_Common(tray, screw_head).Shape()) < 1e-5
    assert -1.8 - (-2.4) >= 0.6 - 1e-9
    switch_clearance = switch_body_clearance(revised)
    cap_clearance = cs_keycap_clearance(original, revised)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_step(revised, OUTPUT / "TheENDGAME2024_NICE_NANO_CASE.step")
    write_stl(revised, OUTPUT / "TheENDGAME2024_NICE_NANO_CASE.stl")
    write_step(tray, OUTPUT / "TheENDGAME2024_NICE_NANO_BATTERY_TRAY.step")
    write_stl(tray, OUTPUT / "TheENDGAME2024_NICE_NANO_BATTERY_TRAY.stl")
    verify_exports_and_preview(volume(revised), volume(tray), switch_clearance, original)

    print(f"Original case: {volume(original):.1f} mm³")
    print(f"Revised case: {volume(revised):.1f} mm³; valid single solid")
    print(f"Lower tray: {volume(tray):.1f} mm³; valid single solid")
    print("Verified roof over enlarged battery pocket: >=1.25 mm to Z=6.6")
    print("Central 16 mm controller roof and USB roof: >=1.25 mm; LED roof: >=3.05 mm")
    print("Two added D4.6×4 mm heat-set bores have >=1.0 mm local top roof")
    print("Recessed M3×6 DIN965 heads: >=0.6 mm desk clearance with 1 mm feet")
    print(f"36 switch-body envelopes clear case; minimum {switch_clearance:.4f} mm")
    print(f"36 nominal CS 1U cap envelopes clear through case height; minimum {cap_clearance:.4f} mm")
    print(f"Written to {OUTPUT}")


if __name__ == "__main__":
    main()
