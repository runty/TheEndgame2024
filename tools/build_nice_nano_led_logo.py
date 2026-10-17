#!/usr/bin/env python3
"""Split the nice!nano case into an opaque body and a clear logo over the LED.

The logo is cut as a vertical column from the top surface down to the LED
pocket ceiling (Z=3.55). The clear part is exactly the removed case material,
so case + logo reproduce the published case; only the filament changes. Where
the column crosses the LED, battery or R1 pocket it simply forms that pocket's
ceiling. Coordinates use the case frame (PCB X - 150, 140 - PCB Y, Z).

Needs OCP, trimesh, NumPy, Matplotlib, shapely and svgelements.
Run: python tools/build_nice_nano_led_logo.py [--width 14]
"""

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import svgelements
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.STEPControl import STEPControl_Reader
from OCP.gp import gp_Pnt, gp_Vec

from build_nice_nano_case import OUTPUT, box, cut, solids, volume, write_step, write_stl


LOGO_DIR = OUTPUT / "LED LOGO"
SVG = LOGO_DIR / "runty.svg"
CASE = OUTPUT / "TheENDGAME2024_NICE_NANO_CASE.step"
VALIDATION = OUTPUT.parents[1] / "docs/validation/nice-nano-case/led-logo.json"
LED_CENTER = (0.0, 36.5)  # WS2812B-V6 at PCB (150,103.5)
LED_POCKET_TOP = 3.55
LED_BODY = (-2.5, 34.0, 2.5, 39.0)


def svg_outline(path):
    """Filled region of the SVG under the nonzero rule.

    Each logo path is an open band plus its inner edge, wound oppositely;
    the larger loop is the outside and the smaller one is removed.
    """
    shapes = []
    for element in svgelements.SVG.parse(str(path)).elements():
        if not isinstance(element, svgelements.Path):
            continue
        loops = []
        for sub in element.as_subpaths():
            sub = svgelements.Path(sub)
            points = np.array([sub.point(t) for t in np.linspace(0, 1, 3000)], dtype=float)
            loop = Polygon(points).buffer(0)
            loops.append((loop.area, loop))
        loops.sort(key=lambda item: -item[0])
        shape = loops[0][1]
        for _, inner in loops[1:]:
            shape = shape.difference(inner)
        shapes.append(shape)
    outline = unary_union(shapes)
    assert outline.geom_type == "Polygon", outline.geom_type
    # Implicit subpath closures leave a zero-width seam that splits the
    # ring interior in two; rendered, it is one open region. Merge it.
    islands = unary_union([Polygon(ring).buffer(1e-3) for ring in outline.interiors]).buffer(-1e-3)
    outline = Polygon(outline.exterior).difference(islands)
    assert outline.geom_type == "Polygon", outline.geom_type
    return outline


def placed_outline(width):
    outline = svg_outline(SVG)
    x0, y0, x1, y1 = outline.bounds
    scale = width / (x1 - x0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # SVG Y points down; the case frame viewed from above has Y pointing up.

    def place(ring):
        return [(LED_CENTER[0] + (x - cx) * scale, LED_CENTER[1] - (y - cy) * scale) for x, y in ring.coords]

    placed = Polygon(place(outline.exterior), [place(ring) for ring in outline.interiors])
    placed = placed.simplify(0.01).buffer(0)
    assert placed.geom_type == "Polygon" and len(placed.interiors) == 1
    return placed


def ring_prism(coords, z0, z1):
    wire = BRepBuilderAPI_MakePolygon()
    for x, y in list(coords)[:-1]:
        wire.Add(gp_Pnt(x, y, z0))
    wire.Close()
    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, z1 - z0)).Shape()


def prism(polygon, z0, z1):
    # The interlocked rings enclose islands of case material.
    shape = ring_prism(polygon.exterior.coords, z0, z1)
    for ring in polygon.interiors:
        shape = cut(shape, ring_prism(ring.coords, z0 - 1, z1 + 1))
    return shape


def min_band_width(polygon):
    """Largest inward offset that keeps the logo in one piece, doubled."""
    width = 0.0
    for r in np.arange(0.05, 2.0, 0.05):
        eroded = polygon.buffer(-r)
        if eroded.is_empty or eroded.geom_type != "Polygon":
            break
        width = 2 * r
    return round(width, 2)


def write_3mf(parts, path):
    """One object with two parts so Bambu Studio keeps them aligned."""
    objects, components = [], []
    for index, (name, mesh_path) in enumerate(parts, start=1):
        mesh = trimesh.load(mesh_path)
        vertices = "".join(f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in mesh.vertices)
        triangles = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.faces)
        objects.append(
            f'<object id="{index}" name="{name}" type="model"><mesh>'
            f"<vertices>{vertices}</vertices><triangles>{triangles}</triangles></mesh></object>"
        )
        components.append(f'<component objectid="{index}"/>')
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f"<resources>{''.join(objects)}"
        f'<object id="{len(parts) + 1}" name="Endgame nice!nano case with LED logo" type="model">'
        f"<components>{''.join(components)}</components></object></resources>"
        f'<build><item objectid="{len(parts) + 1}"/></build></model>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("3D/3dmodel.model", model)


def preview(case_mesh, logo_mesh, outline, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    fig, (top, side) = plt.subplots(1, 2, figsize=(13, 5.5), gridspec_kw={"width_ratios": [1, 1.25]})
    for mesh, colour in ((case_mesh, "#3b3f46"), (logo_mesh, "#cfeef5")):
        up = mesh.face_normals[:, 2] > 0.2
        tris = mesh.triangles[up][:, :, :2]
        top.add_collection(PolyCollection(tris, facecolors=colour, edgecolors=colour, linewidths=0.3))
    top.add_patch(plt.Rectangle((LED_BODY[0], LED_BODY[1]), 5, 5, fill=False, ec="#ff7a00", lw=1.2, ls="--"))
    top.add_patch(plt.Rectangle((-6.7, 33.0), 12.9, 7.2, fill=False, ec="#ffb15c", lw=0.8, ls=":"))
    top.set_xlim(-16, 16)
    top.set_ylim(24, 50)
    top.set_aspect("equal")
    top.set_title("Top view: clear logo (light) in case; LED body dashed, pocket dotted")

    section = trimesh.intersections.mesh_plane
    for mesh, colour in ((case_mesh, "#3b3f46"), (logo_mesh, "#7cc6d9")):
        lines = section(mesh, [0, 1, 0], [0, LED_CENTER[1], 0])
        for a, b in lines:
            side.plot([a[0], b[0]], [a[2], b[2]], color=colour, lw=1.2)
    side.add_patch(plt.Rectangle((-2.5, 1.6), 5, 1.6, color="#ff7a00", alpha=0.6, label="WS2812B body"))
    side.axhline(1.6, color="#2e8b57", lw=0.8, label="PCB top Z=1.6")
    side.set_xlim(-16, 16)
    side.set_ylim(-0.5, 10)
    side.set_aspect("equal")
    side.legend(loc="lower right", fontsize=8)
    side.set_title(f"Section at Y={LED_CENTER[1]}: clear column from Z={LED_POCKET_TOP} to the roof")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=float, default=14.0, help="logo width in mm")
    args = parser.parse_args()

    reader = STEPControl_Reader()
    assert int(reader.ReadFile(str(CASE))) == 1
    reader.TransferRoots()
    case = reader.OneShape()
    assert solids(case) == 1 and BRepCheck_Analyzer(case).IsValid()

    outline = placed_outline(args.width)
    column = prism(outline, LED_POCKET_TOP, 12.0)
    logo = BRepAlgoAPI_Common(case, column).Shape()
    body = cut(case, column)
    assert BRepCheck_Analyzer(body).IsValid() and solids(body) == 1
    assert BRepCheck_Analyzer(logo).IsValid() and solids(logo) == 1
    # Two parts reproduce the case and do not overlap. Curved-surface Boolean
    # integration of the 62 cm3 case differs by ~0.005 mm3.
    assert abs(volume(body) + volume(logo) - volume(case)) < 0.02, (volume(body), volume(logo), volume(case))
    assert volume(BRepAlgoAPI_Common(body, logo).Shape()) < 1e-5
    # Clear material forms the pocket ceiling directly above the LED body.
    led_ceiling = box(LED_BODY[0], LED_BODY[1], LED_POCKET_TOP, LED_BODY[2], LED_BODY[3], LED_POCKET_TOP + 0.2)
    lit_area = volume(BRepAlgoAPI_Common(logo, led_ceiling).Shape()) / 0.2

    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    stem = "TheENDGAME2024_NICE_NANO_CASE_LED_LOGO"
    body_stl, logo_stl = LOGO_DIR / f"{stem}_BODY.stl", LOGO_DIR / f"{stem}_CLEAR.stl"
    write_step(body, LOGO_DIR / f"{stem}_BODY.step")
    write_step(logo, LOGO_DIR / f"{stem}_CLEAR.step")
    write_stl(body, body_stl)
    write_stl(logo, logo_stl)
    write_3mf([("case body (opaque)", body_stl), ("LED logo (transparent)", logo_stl)], LOGO_DIR / f"{stem}.3mf")

    body_mesh, logo_mesh = trimesh.load(body_stl), trimesh.load(logo_stl)
    assert body_mesh.is_watertight and logo_mesh.is_watertight
    preview(body_mesh, logo_mesh, outline, LOGO_DIR / "led-logo-preview.png")

    x0, y0, x1, y1 = outline.bounds
    report = {
        "svg": str(SVG.relative_to(OUTPUT.parents[1])),
        "logo_width_mm": round(x1 - x0, 2),
        "logo_height_mm": round(y1 - y0, 2),
        "logo_bounds_case_frame_mm": [round(v, 2) for v in outline.bounds],
        "centre_case_frame_mm": list(LED_CENTER),
        "column_bottom_z_mm": LED_POCKET_TOP,
        "roof_top_z_at_led_mm": round(float(logo_mesh.vertices[:, 2].max()), 2),
        "minimum_band_width_mm": min_band_width(outline),
        "clear_area_over_led_body_mm2": round(lit_area, 2),
        "led_body_area_mm2": 25.0,
        "case_volume_mm3": round(volume(case), 2),
        "body_volume_mm3": round(volume(body), 2),
        "clear_volume_mm3": round(volume(logo), 2),
        "body_and_clear_watertight": True,
    }
    VALIDATION.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print(f"Written to {LOGO_DIR}")


if __name__ == "__main__":
    main()
