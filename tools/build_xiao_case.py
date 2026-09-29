#!/usr/bin/env python3
"""Build the separate prototype XIAO battery case and serviceable lower tray.

Requires cadquery-ocp 8.0.1.0.0. Source STEP is read only. All coordinates are
in the case frame: (PCB X - 150, 140 - PCB Y, Z). The PCB occupies Z=0..1.6.
Run from any directory: python tools/build_xiao_case.py
"""

from pathlib import Path
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
OUTPUT = ROOT / "002 CASE/XIAO WIRELESS"


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


def main():
    reader = STEPControl_Reader()
    assert int(reader.ReadFile(str(SOURCE))) == 1
    reader.TransferRoots()
    original = reader.OneShape()
    assert solids(original) == 1 and BRepCheck_Analyzer(original).IsValid()

    # Inset pack Z=0.2..5.2. Case recess adds 0.10 mm per edge and 0.15 mm
    # vertical headroom. R1 corners avoid sharp internal stress risers.
    pocket = rounded_prism(-11.1, -4.1, 11.1, 24.1, 1.0, 0.0, 5.35)
    revised = cut(original, pocket)

    # J1 direct-solder B+/B- on PCB at (148,147.5), (152,147.5), with two
    # strain holes at Y=150.5. No connector. The recess allows battery
    # leads above F.Cu and terminates before the M3 mounts.
    wire_channel = rounded_prism(-3.4, -11.1, 3.4, -3.6, 0.8, 0.0, 3.0)
    revised = cut(revised, wire_channel)

    # F.Cu logic components: U3 SOIC-16, C1/C2 and R1/R2/R3 0603. These
    # local pockets are independent of the still-to-be-verified XIAO cut.
    revised = cut(revised, rounded_prism(-4.0, 32.5, 4.0, 44.8, 0.7, 0.0, 3.75))
    revised = cut(revised, rounded_prism(4.5, 38.0, 7.7, 45.0, 0.5, 0.0, 3.0))
    revised = cut(revised, rounded_prism(-8.2, 36.5, -5.8, 45.5, 0.5, 0.0, 3.0))

    # Standard non-Sense XIAO nRF52840, PCB centre (150,74). Seeed's
    # 17.8×21 mm module spans case X=-8.9..8.9, Y=55.5..76.5; its USB-C
    # shell extends toward the upper edge to about Y=78.0. The exact
    # assembled module/shell Z heights are unavailable, so 6.4/7.2 mm are
    # generous prototype envelope tops, subject to a real module fit.
    # This plastic-only cavity also clears the antenna end near case Y=56.6.
    revised = cut(revised, rounded_prism(-9.5, 54.8, 9.5, 77.2, 1.0, 0.0, 6.4))
    # Cable entry opens through the exterior edge at Y≈80.44. It is wider
    # than the ~9 mm connector footprint to allow plug-head clearance.
    revised = cut(revised, rounded_prism(-6.4, 69.8, 6.4, 82.0, 0.8, 0.0, 7.2))

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
    tray = rounded_prism(-12.0, -5.0, 12.0, 25.0, 1.5, -1.0, 0.0)
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

    # Validate installed-part envelope clearances. The nominal pouch has
    # square proxy corners here, a stricter check than its rounded real pouch.
    proxies = {
        "Adafruit 1317 pouch": box(-9.875, -3.01, 0.2, 9.875, 23.01, 5.2),
        "XIAO board/components (assumed height)": box(-8.9, 55.5, 1.6, 8.9, 76.5, 6.4),
        "USB shell/cable corridor (assumed height)": box(-4.5, 70.65, 1.6, 4.5, 78.0, 7.2),
        "USB plug entry to exterior": box(-5.5, 78.0, 1.6, 5.5, 81.8, 7.1),
        "U3 SOIC-16": box(-3.5, 33.75, 1.6, 3.5, 44.25, 3.35),
        "power switch body and slider": box(-3.35, -17.15, 1.6, 3.35, -13.0, 3.1),
    }
    for label, solid in proxies.items():
        overlap = volume(BRepAlgoAPI_Common(revised, solid).Shape())
        assert overlap < 1e-5, f"Case intersects {label}: {overlap} mm³"

    # Case roof over the complete enlarged rectangular cutter is at least
    # 1.25 mm in the source STEP. The rounded corners only preserve more roof.
    source_roof = BRepAlgoAPI_Common(
        original, box(-11.1, -4.1, 5.35, 11.1, 24.1, 6.6)
    ).Shape()
    assert abs(volume(source_roof) - 22.2 * 28.2 * 1.25) < 1e-5
    final_roof = BRepAlgoAPI_Common(
        revised, box(-11.1, -4.1, 5.35, 11.1, 24.1, 6.6)
    ).Shape()
    assert abs(volume(final_roof) - 22.2 * 28.2 * 1.25) < 1e-5
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

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_step(revised, OUTPUT / "TheENDGAME2024_XIAO_CASE.step")
    write_stl(revised, OUTPUT / "TheENDGAME2024_XIAO_CASE.stl")
    write_step(tray, OUTPUT / "TheENDGAME2024_XIAO_BATTERY_TRAY.step")
    write_stl(tray, OUTPUT / "TheENDGAME2024_XIAO_BATTERY_TRAY.stl")

    print(f"Original case: {volume(original):.1f} mm³")
    print(f"Revised case: {volume(revised):.1f} mm³; valid single solid")
    print(f"Lower tray: {volume(tray):.1f} mm³; valid single solid")
    print("Nominal roof over enlarged battery pocket: >=1.25 mm")
    print("Two added D4.6×4 mm heat-set bores have >=1.0 mm local top roof")
    print("Recessed M3×6 DIN965 heads: >=0.6 mm desk clearance with 1 mm feet")
    print(f"36 switch-body envelopes clear case; minimum {switch_clearance:.4f} mm")
    print(f"Written to {OUTPUT}")


if __name__ == "__main__":
    main()
