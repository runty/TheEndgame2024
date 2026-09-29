#!/usr/bin/env python3
"""Recheck the proposed battery inset against the unchanged Endgame STEP case.

Requires cadquery-ocp 8.0.1.0.0 (OCP). This checks only case solids and the
nominal rectangular envelope; see docs/validation/xiao-battery-fit.md for PCB
and assembly checks. Run: python tools/assess_xiao_battery_fit.py
"""

from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.GProp import GProp_GProps
from OCP.STEPControl import STEPControl_Reader
from OCP.gp import gp_Pnt


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "002 CASE/TheENDGAME2024_CASE001.step"
WIDTH = 22.0
LENGTH = 28.0
X0, Y0 = -11.0, -4.0  # PCB x=139..161, y=116..144, case y=140-PCB y
AREA = WIDTH * LENGTH


def intersection_volume(case, z0, z1):
    envelope = BRepPrimAPI_MakeBox(
        gp_Pnt(X0, Y0, z0), WIDTH, LENGTH, z1 - z0
    ).Shape()
    common = BRepAlgoAPI_Common(case, envelope).Shape()
    mass = GProp_GProps()
    BRepGProp.VolumeProperties_s(common, mass)
    return mass.Mass()


def main():
    reader = STEPControl_Reader()
    assert int(reader.ReadFile(str(CASE))) == 1, f"Cannot read {CASE}"
    reader.TransferRoots()
    case = reader.OneShape()

    # Board bottom/top are Z=0/1.6. The 5 mm pack is inset at Z=0.2..5.2.
    pack_intersection = intersection_volume(case, 0.2, 5.2)
    pocket_intersection = intersection_volume(case, 1.6, 5.2)
    roof_to_6_7 = intersection_volume(case, 5.2, 6.7)
    roof_next_slice = intersection_volume(case, 6.7, 6.75)

    assert abs(pack_intersection - AREA * 3.6) < 1e-5
    assert abs(pocket_intersection - AREA * 3.6) < 1e-5
    assert abs(roof_to_6_7 - AREA * 1.5) < 1e-5
    assert roof_next_slice < AREA * 0.05 - 1e-5

    print(f"Pack-case intersection: {pack_intersection:.4f} mm³ (Z=0.2..5.2)")
    print(f"Required case pocket: {pocket_intersection:.4f} mm³ (Z=1.6..5.2)")
    print("Nominal roof over the complete 22×28 mm window: at least 1.50 mm")
    print("Existing outside surface begins within Z=6.70..6.75 mm")
    print("Bottom support, expanded pocket tolerance, and physical fit remain to check")


if __name__ == "__main__":
    main()
