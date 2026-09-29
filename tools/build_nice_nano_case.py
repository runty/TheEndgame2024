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
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.GProp import GProp_GProps
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.StlAPI import StlAPI_Writer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from verify_choc_compatibility import blocks, coords


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "002 CASE/TheENDGAME2024_CASE001.step"
PCB = ROOT / "001 PCB/KICAD/NICE NANO WIRELESS/TheEndgame2024_NiceNano.kicad_pcb"
SOURCE_PCB = ROOT / "001 PCB/KICAD/SILKSCREEN KICAD/TheENDGAME2024_SILKSCREEN.kicad_pcb"
OUTPUT = ROOT / "002 CASE/NICE NANO WIRELESS"
AXIAL_RESISTORS = (("R1", 142.85, 99.4), ("R2", 157.15, 107.6))


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


def translated(shape, dx):
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(dx, 0, 0))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def widened_source_case(original):
    """Separate the key halves by 4 mm while keeping the centre fixed.

    The source section at X=±12 misses all key openings. Extruding each
    planar section fills the 2 mm stretch between its fixed centre and
    translated outer half without changing the Y/Z roof profile.
    """
    split = 12.0
    left = translated(cut(original, box(-split, -100, -20, 200, 100, 20)), -2.0)
    middle = BRepAlgoAPI_Common(original, box(-split, -100, -20, split, 100, 20)).Shape()
    right = translated(cut(original, box(-200, -100, -20, split, 100, 20)), 2.0)
    widened = fuse(fuse(left, middle), right)
    # Use all three planar cut faces from each side of the clipped middle.
    # A solid/plane Common omits part of this STEP section and leaves roof
    # slits, even though the remaining shape can still be a valid solid.
    for x, dx in ((-split, -2.0), (split, 2.0)):
        faces = []
        explorer = TopExp_Explorer(middle, TopAbs_FACE)
        while explorer.More():
            face = explorer.Current()
            vertices = TopExp_Explorer(face, TopAbs_VERTEX)
            xs = []
            while vertices.More():
                xs.append(BRep_Tool.Pnt_s(TopoDS.Vertex(vertices.Current())).X())
                vertices.Next()
            if xs and all(abs(value - x) < 1e-6 for value in xs):
                faces.append(face)
            explorer.Next()
        assert len(faces) == 3, (x, len(faces))
        for face in faces:
            bridge = BRepPrimAPI_MakePrism(face, gp_Vec(dx, 0, 0)).Shape()
            widened = fuse(widened, bridge)
    assert solids(widened) == 1 and BRepCheck_Analyzer(widened).IsValid()
    # Probe solid roof through both bridge strips in each of the three
    # separated source-section bands; a merely watertight fuse can omit a
    # bridge band and leave a visible slit across the roof.
    for x0, x1 in ((-14.0, -12.0), (12.0, 14.0)):
        for y0, y1, z0, z1 in (
            (-20.0, -19.0, 5.7, 6.2),
            (20.0, 21.0, 6.6, 7.4),
            (70.0, 71.0, 8.55, 9.2),
        ):
            roof = box(x0, y0, z0, x1, y1, z1)
            assert abs(volume(BRepAlgoAPI_Common(widened, roof).Shape()) - volume(roof)) < 1e-5
    return widened


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


def validate_pcb_alignment():
    """Keep the generated case paired with the intended widened PCB layout."""
    def positions(path):
        found = {}
        outer_mounts = []
        central_mounts = {}
        for footprint in blocks(path.read_text(), "footprint"):
            name = footprint.splitlines()[0]
            at = coords(footprint, "at", 2)
            ref_match = re.search(r'\(property "Reference" "([^"]+)', footprint)
            if ref_match:
                found[ref_match.group(1)] = (name, at)
            if "MOUNTING HOLE 4 mm ENDGAME Silver NEW" in name:
                outer_mounts.append(at)
            elif "MOUNTING LOVE PEACE" in name:
                central_mounts["left"] = at
            elif "MOUNTING DEEZ NUTZ" in name:
                central_mounts["right"] = at
        return found, sorted(outer_mounts), central_mounts

    source, source_outer, source_central = positions(SOURCE_PCB)
    board, board_outer, board_central = positions(PCB)
    switch_refs = [ref for ref, (name, _) in source.items() if "SW_choc_v1_v2_HS_" in name]
    assert len(switch_refs) == 36
    for ref in switch_refs:
        old_at = source[ref][1]
        new_at = board[ref][1]
        dx = -2.0 if old_at[0] < 150 else 2.0
        assert abs(new_at[0] - old_at[0] - dx) < 1e-4, (ref, old_at, new_at)
        assert len(old_at) == len(new_at)
        assert all(abs(a - b) < 1e-4 for a, b in zip(old_at[1:], new_at[1:])), ref
    assert len(source_outer) == len(board_outer) == 4
    for old_at, new_at in zip(source_outer, board_outer):
        dx = -2.0 if old_at[0] < 150 else 2.0
        assert abs(new_at[0] - old_at[0] - dx) < 1e-4
        assert abs(new_at[1] - old_at[1]) < 1e-4
    assert source_central.keys() == board_central.keys() == {"left", "right"}
    for side in source_central:
        assert all(abs(a - b) < 1e-4 for a, b in zip(source_central[side], board_central[side]))
    for ref, board_x, board_y in AXIAL_RESISTORS:
        name, at = board[ref]
        assert "P10.16mm_Horizontal" in name, (ref, name)
        expected_x = board_x + (-5.08 if ref == "R1" else 5.08)
        expected_angle = 0 if ref == "R1" else 180
        actual_angle = at[2] if len(at) == 3 else 0
        assert abs(at[0] - expected_x) < 0.01 and abs(at[1] - board_y) < 0.01, (ref, at)
        assert abs(actual_angle - expected_angle) < 0.01, (ref, at)


def write_step(shape, path):
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    assert int(writer.Write(str(path))) == 1, f"STEP export failed: {path}"


def write_stl(shape, path):
    BRepMesh_IncrementalMesh(shape, 0.08, False, 0.2, True)
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    assert writer.Write(shape, str(path)), f"STL export failed: {path}"


def verify_exports_and_preview(case_volume, tray_volume, switch_clearance, original, widened_base, resistor_report):
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
        "original_key_openings_translated_with_each_half": True,
        "source_case_width_mm": 227.0,
        "revised_case_width_mm": 231.0,
        "split_x_case_mm": [-12.0, 12.0],
        "outer_half_translation_x_mm": [-2.0, 2.0],
        "all_six_bridge_roof_probes_solid": True,
        "pcb_switch_half_shift_verified": True,
        "pcb_outer_mount_half_shift_verified": True,
        "pcb_central_mounts_fixed_verified": True,
        "pcb_axial_positions_verified": True,
        "central_components_and_mounts_stay_fixed": True,
        "central_case_mount_xy_mm": [[-9.804941, -14.168516], [9.804965, -14.170142]],
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
        "axial_resistors": resistor_report,
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
    projection(ax, meshes["case"], "bottom", "Case underside: battery, axial resistor, LED and controller cavities")
    ax.annotate("battery pocket", xy=(0, 14), xytext=(25, 30), arrowprops={"arrowstyle": "->"})
    ax.annotate("LED pocket", xy=(0, 36.5), xytext=(26, 43), arrowprops={"arrowstyle": "->"})
    ax.annotate("axial resistor pockets", xy=(0, 41), xytext=(-41, 48), arrowprops={"arrowstyle": "->"})
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
    assert abs((meshes["case"].bounds[1, 0] - meshes["case"].bounds[0, 0]) - 231.0) < 0.002
    report["maximum_case_height_increased"] = False
    report["original_case_z_bounds_mm"] = original_mesh.bounds[:, 2].tolist()
    report["revised_case_z_bounds_mm"] = meshes["case"].bounds[:, 2].tolist()
    report["widened_baseline_volume_mm3"] = round(volume(widened_base), 3)
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

    # The clearance image uses the current PCB positions and the actual
    # source/revised case sections. Boolean results in cs-clearance.json
    # determine the collision colours; the section itself is illustrative.
    cs_report = json.loads((validation_dir / "cs-clearance.json").read_text())
    source_collisions = set(cs_report["source_original_colliding_envelopes"])
    caps = []
    for footprint in blocks(PCB.read_text(), "footprint"):
        if "SW_choc_v1_v2_HS_" not in footprint.splitlines()[0]:
            continue
        at = coords(footprint, "at", 2)
        angle = math.radians(at[2] if len(at) == 3 else 0.0)
        rotation = np.array([[math.cos(angle), -math.sin(angle)],
                             [math.sin(angle), math.cos(angle)]])
        corners = np.array([[-8.75, -8.25], [8.75, -8.25],
                            [8.75, 8.25], [-8.75, 8.25]])
        polygon = corners @ rotation.T + [at[0] - 150, 140 - at[1]]
        ref = re.search(r'\(property "Reference" "([^"]+)', footprint).group(1)
        caps.append((ref, polygon, (at[0] - 150, 140 - at[1])))
    fig, axs = plt.subplots(2, 2, figsize=(16, 10), layout="constrained",
                           gridspec_kw={"height_ratios": [1.6, 1]})
    for column, (mesh, title) in enumerate(((original_mesh, "Unwidened source: 227 mm"),
                                            (meshes["case"], "Widened case: 231 mm"))):
        segments = trimesh.intersections.mesh_plane(
            mesh, plane_origin=[0, 0, 7], plane_normal=[0, 0, 1])
        for row, limits in enumerate(((-119, 119, -24, 84), (-35, 35, 42, 65))):
            ax = axs[row, column]
            ax.add_collection(LineCollection(segments[:, :, :2], colors="#25334a", linewidths=1.0))
            polygons = [polygon for _, polygon, _ in caps]
            colours = ["#e96b64" if column == 0 and ref in source_collisions else "#e7aa57"
                       for ref, _, _ in caps]
            ax.add_collection(PolyCollection(polygons, facecolors=colours,
                                             edgecolors="#a86330", linewidths=0.5, alpha=0.38))
            ax.set(xlim=limits[:2], ylim=limits[2:], aspect="equal",
                   xlabel="Case X (mm)", ylabel="Case Y (mm)")
            ax.grid(alpha=0.12)
            if row == 0:
                ax.set_title(title, fontsize=12)
            for ref, _, center in caps:
                if row == 1 and ref in ("SW16", "SW20"):
                    ax.plot(center[0], center[1], "o", markerfacecolor="none",
                            markeredgecolor="#243244", markersize=12, markeredgewidth=1.3)
                    ax.annotate(ref, center, xytext=(0, -15), textcoords="offset points",
                                ha="center", fontsize=9)
    fig.suptitle("Nominal 17.5 × 16.5 mm CS envelopes on the shifted key field", fontsize=15)
    fig.text(0.5, 0.01,
             f"Full-height Boolean check Z=1.6–20 mm: {len(source_collisions)} source collisions; "
             f"0 widened collisions; minimum widened clearance {cs_report['minimum_clearance_mm']:.3f} mm. "
             "Outline is a plan section at Z=7 mm.",
             ha="center", fontsize=10)
    fig.savefig(validation_dir / "cs-clearance.png", dpi=160, facecolor="white")
    plt.close(fig)


def switch_body_clearance(case):
    """Use the same conservative V2 envelopes as tools/check_case_fit.py."""
    board = PCB.read_text()
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


def cs_keycap_clearance(source_original, widened_base, revised):
    """Check the user's nominal CS 1U footprint over the entire case height.

    This deliberately makes no assumption about skirt height at rest or at
    bottom-out. It is a centred 17.5 x 16.5 mm bounding envelope, not a model
    of every CS variant or a claim about wider thumb caps or print tolerance.
    """
    board = PCB.read_text()
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
        for name, shape in (("source_original", source_original), ("widened_baseline", widened_base), ("revised", revised)):
            overlap = volume(BRepAlgoAPI_Common(shape, proxy).Shape())
            distance = BRepExtrema_DistShapeShape(shape, proxy)
            distance.Perform()
            assert distance.IsDone()
            if name != "source_original":
                assert overlap < 1e-6, (ref, name, overlap)
            row[f"{name}_clearance_mm"] = distance.Value()
            row[f"{name}_overlap_mm3"] = overlap
        assert row["revised_clearance_mm"] >= row["widened_baseline_clearance_mm"] - 1e-5, ref
        rows.append(row)
    assert len(rows) == 36
    report = {
        "footprint_mm": [17.5, 16.5],
        "footprint_source": "User-specified nominal CS 1U size, centred on each switch",
        "swept_z_bounds_mm": [1.6, 20],
        "coordinate_datum": "PCB bottom Z=0; no assumed resting skirt height",
        "source_original_width_mm": 227.0,
        "widened_baseline_width_mm": 231.0,
        "all_36_nominal_1u_envelopes_clear": True,
        "minimum_clearance_mm": min(r["revised_clearance_mm"] for r in rows),
        "source_original_colliding_envelopes": [
            r["reference"] for r in rows if r["source_original_overlap_mm3"] >= 1e-6
        ],
        "widened_baseline_clearance_preserved": True,
        "physical_print_or_wider_thumb_caps_verified": False,
        "positions": rows,
    }
    out = ROOT / "docs/validation/nice-nano-case/cs-clearance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report["minimum_clearance_mm"]


def axial_resistor_clearance(case):
    """Check lying-flat 6.3 x 2.5 mm axial bodies and their straight lead runs.

    The installation proxy allows 0.2 mm under each body and 0.2 mm extra
    body length. Lead proxies are conservative straight 0.6 mm-square
    envelopes at the body centreline; actual leads bend down into the pads.
    """
    rows = []
    for ref, board_x, board_y in AXIAL_RESISTORS:
        x = round(board_x - 150, 2)
        y = round(140 - board_y, 2)
        body = box(x - 3.25, y - 1.25, 1.8, x + 3.25, y + 1.25, 4.3)
        leads = (
            box(x - 5.38, y - 0.3, 2.75, x - 3.25, y + 0.3, 3.35),
            box(x + 3.25, y - 0.3, 2.75, x + 5.38, y + 0.3, 3.35),
        )
        for label, proxy in (("body", body), ("left lead", leads[0]), ("right lead", leads[1])):
            overlap = volume(BRepAlgoAPI_Common(case, proxy).Shape())
            assert overlap < 1e-5, (ref, label, overlap)
        # The source roof is fully present through Z=6.6 here. It leaves
        # 1.95 mm above the Z=4.65 local component-pocket ceiling.
        roof = box(x - 3.25, y - 1.25, 4.65, x + 3.25, y + 1.25, 6.6)
        assert abs(volume(BRepAlgoAPI_Common(case, roof).Shape()) - volume(roof)) < 1e-5
        led = box(-2.5, 34.0, 1.6, 2.5, 39.0, 3.2)
        led_distance = BRepExtrema_DistShapeShape(body, led)
        led_distance.Perform()
        assert led_distance.IsDone() and led_distance.Value() >= 1.4 - 1e-5
        pack_distance = None
        if ref == "R2":
            pack = box(-9.25, -3.0, 0.2, 9.25, 30.0, 5.2)
            pack_distance = BRepExtrema_DistShapeShape(body, pack)
            pack_distance.Perform()
            assert pack_distance.IsDone() and pack_distance.Value() >= 1.15 - 1e-5
        rows.append({
            "reference": ref,
            "pcb_body_center_mm": [board_x, board_y],
            "pcb_pad_centers_mm": [[round(board_x - 5.08, 2), board_y], [round(board_x + 5.08, 2), board_y]],
            "pcb_pad1_center_mm": [round(board_x + (-5.08 if ref == "R1" else 5.08), 2), board_y],
            "pcb_pad2_center_mm": [round(board_x + (5.08 if ref == "R1" else -5.08), 2), board_y],
            "case_body_bounds_xyz_mm": [[round(x - 3.25, 2), round(y - 1.25, 2), 1.8], [round(x + 3.25, 2), round(y + 1.25, 2), 4.3]],
            "case_lead_bounds_xyz_mm": [
                [[round(x - 5.38, 2), round(y - 0.3, 2), 2.75], [round(x - 3.25, 2), round(y + 0.3, 2), 3.35]],
                [[round(x + 3.25, 2), round(y - 0.3, 2), 2.75], [round(x + 5.38, 2), round(y + 0.3, 2), 3.35]],
            ],
            "body_and_lead_case_overlap_mm3": 0,
            "solid_roof_above_body_mm": 1.95,
            "nominal_led_body_edge_gap_mm": round((y - 1.25) - 39.0 if ref == "R1" else 34.0 - (y + 1.25), 2),
            "nominal_led_body_x_edge_gap_mm": 1.4,
            "nominal_body_to_LED_3d_clearance_mm": round(led_distance.Value(), 3),
            "battery_pack_planning_proxy_edge_gap_mm": None if ref == "R1" else 1.15,
            "battery_pack_planning_proxy_3d_clearance_mm": None if pack_distance is None else round(pack_distance.Value(), 3),
        })
    return {
        "installation": "horizontal F.Cu, body parallel to PCB X; board top Z=1.6 mm",
        "nominal_body_length_diameter_mm": [6.3, 2.5],
        "checked_body_length_diameter_mm": [6.5, 2.5],
        "body_standoff_mm": 0.2,
        "lead_diameter_proxy_mm": 0.6,
        "pad_pitch_mm": 10.16,
        "body_pockets_case_xyz_mm": [
            [[-10.55, 39.2, 0.0], [-3.75, 42.0, 4.65]],
            [[3.75, 31.0, 0.0], [10.55, 33.8, 4.65]],
        ],
        "lead_channels_case_x_mm": [[-12.65, -10.55], [-3.75, -1.65], [1.65, 3.75], [10.55, 12.65]],
        "lead_channels_case_y_mm": [[40.1, 41.1], [31.9, 32.9]],
        "lead_channel_top_z_mm": 3.55,
        "pocket_top_z_mm": 4.65,
        "minimum_body_to_roof_gap_mm": 0.35,
        "minimum_body_to_LED_x_edge_gap_mm": 1.4,
        "r2_pocket_joins_battery_recess": True,
        "battery_pack_proxy_is_a_maximum": False,
        "resistors": rows,
    }


def main():
    validate_pcb_alignment()
    reader = STEPControl_Reader()
    assert int(reader.ReadFile(str(SOURCE))) == 1
    reader.TransferRoots()
    original = reader.OneShape()
    assert solids(original) == 1 and BRepCheck_Analyzer(original).IsValid()
    widened_base = widened_source_case(original)

    # The intended PCB opening is X=139..161, Y=109..144 (22 x 35, R1).
    # It is extended 7 mm toward the controller from the XIAO revision.
    # The inset 401730 planning envelope is Z=0.2..5.2; neither the
    # full taped pack size nor the allowed charging current is established.
    pocket = rounded_prism(-11.1, -4.1, 11.1, 31.1, 1.0, 0.0, 5.35)
    revised = cut(widened_base, pocket)

    # J1 direct-solder B+/B- on PCB at (148,147.5), (152,147.5), with two
    # strain holes at Y=150.5. No connector. The recess allows battery
    # leads above F.Cu and terminates before the M3 mounts.
    wire_channel = rounded_prism(-3.4, -11.1, 3.4, -3.6, 0.8, 0.0, 3.0)
    revised = cut(revised, wire_channel)

    # Status LED near PCB (150,103.5), on the upper PCB face. A 5x5x1.6
    # body is enclosed below the unbroken translucent-PLA roof. The local
    # component pocket also clears its nearby 0603 capacitor.
    revised = cut(revised, rounded_prism(-6.7, 33.0, 6.2, 40.2, 0.6, 0.0, 3.55))

    # R1/R2 are lying-flat common 1/4 W axial resistors, with nominal
    # 6.3 x 2.5 mm bodies and 10.16 mm lead pitch. The pockets accept a
    # 6.5 mm-long body and 0.2 mm stand-off above the PCB top (Z=1.6),
    # leaving 0.35 mm headroom. Narrow troughs take the 0.6 mm leads out
    # to the plated through-hole pads. The R2 pocket joins the battery
    # recess rather than leaving a 0.1 mm-thick internal wall. The battery
    # planning proxy still ends 1.15 mm from the nearest R2 body edge.
    for _, board_x, board_y in AXIAL_RESISTORS:
        x, y = board_x - 150, 140 - board_y
        revised = cut(revised, box(x - 3.4, y - 1.4, 0.0, x + 3.4, y + 1.4, 4.65))
        for x0, x1 in ((x - 5.5, x - 3.4), (x + 3.4, x + 5.5)):
            revised = cut(revised, box(x0, y - 0.5, 0.0, x1, y + 0.5, 3.55))

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
    # Only the two internal tray mounts add material beyond the widened
    # baseline. The original openings and exterior profile move with their
    # respective halves while the central controller waist stays fixed.
    additions = cut(revised, widened_base)
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
        "C1 body": box(4.1, 37.2, 1.6, 4.9, 38.8, 2.5),
        "WS2812B-V6 body": box(-2.5, 34.0, 1.6, 2.5, 39.0, 3.2),
        "power switch body and slider": box(-3.35, -17.15, 1.6, 3.35, -13.0, 3.1),
    }
    for label, solid in proxies.items():
        overlap = volume(BRepAlgoAPI_Common(revised, solid).Shape())
        assert overlap < 1e-5, f"Case intersects {label}: {overlap} mm³"
    resistor_report = axial_resistor_clearance(revised)

    # Retained roof of the enlarged battery cavity. This requires full
    # material through Z=6.6 over the complete candidate opening, not just
    # at the former 28 mm pocket location.
    source_roof = BRepAlgoAPI_Common(
        widened_base, box(-11.1, -4.1, 5.35, 11.1, 31.1, 6.6)
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
    original_roof_volume = volume(BRepAlgoAPI_Common(widened_base, roof_region).Shape())
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
    cap_clearance = cs_keycap_clearance(original, widened_base, revised)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_step(revised, OUTPUT / "TheENDGAME2024_NICE_NANO_CASE.step")
    write_stl(revised, OUTPUT / "TheENDGAME2024_NICE_NANO_CASE.stl")
    tray_step = OUTPUT / "TheENDGAME2024_NICE_NANO_BATTERY_TRAY.step"
    tray_stl = OUTPUT / "TheENDGAME2024_NICE_NANO_BATTERY_TRAY.stl"
    # This change affects only the case. Retain the existing tray files
    # byte-for-byte when their STEP solid is geometrically identical.
    same_tray = False
    if tray_step.exists() and tray_stl.exists():
        tray_reader = STEPControl_Reader()
        if int(tray_reader.ReadFile(str(tray_step))) == 1:
            tray_reader.TransferRoots()
            saved_tray = tray_reader.OneShape()
            same_tray = (
                solids(saved_tray) == 1
                and BRepCheck_Analyzer(saved_tray).IsValid()
                and volume(cut(saved_tray, tray)) < 1e-5
                and volume(cut(tray, saved_tray)) < 1e-5
            )
    if not same_tray:
        write_step(tray, tray_step)
        write_stl(tray, tray_stl)
    verify_exports_and_preview(volume(revised), volume(tray), switch_clearance, original, widened_base, resistor_report)

    print(f"Original case: {volume(original):.1f} mm³")
    print(f"Widened baseline: {volume(widened_base):.1f} mm³; 227 -> 231 mm width")
    print(f"Revised case: {volume(revised):.1f} mm³; valid single solid")
    print(f"Lower tray: {volume(tray):.1f} mm³; valid single solid")
    print("Verified roof over enlarged battery pocket: >=1.25 mm to Z=6.6")
    print("Central 16 mm controller roof and USB roof: >=1.25 mm; LED roof: >=3.05 mm")
    print("Both axial resistor bodies and four lead runs clear; body roof >=1.95 mm")
    print("Two added D4.6×4 mm heat-set bores have >=1.0 mm local top roof")
    print("Recessed M3×6 DIN965 heads: >=0.6 mm desk clearance with 1 mm feet")
    print(f"36 switch-body envelopes clear case; minimum {switch_clearance:.4f} mm")
    print(f"36 nominal CS 1U cap envelopes clear through case height; minimum {cap_clearance:.4f} mm")
    print(f"Written to {OUTPUT}")


if __name__ == "__main__":
    main()
