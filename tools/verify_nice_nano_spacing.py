#!/usr/bin/env python3
"""Verify the widened nice!nano PCB's key field and external profile.

The input is a pcbnew-extracted JSON manifest with these fields (all geometry
in millimetres):

    source_outer_vertices_mm, final_outer_vertices_mm: [[x, y], ...]
    source_switches, final_switches:
        [{"ref": "SW2", "x_mm": 51.25, "y_mm": 80.67,
          "angle_deg": 180, "footprint": "...SW_choc_v1_v2_HS_1u"}, ...]
    source_central, final_central:
        {"u2_center_mm": [150, 80], "led1_center_mm": [150, 103.5],
         "battery_opening_bounds_mm": [139, 109, 161, 144]}

The source profile should be the pre-widening XIAO exterior, not a case or
Gerber contour. Inner holes are intentionally outside this profile check.
Requires Shapely; for this project use /tmp/endgame-fit-env/bin/python.
"""

import argparse
import json
import math
from pathlib import Path

from shapely.affinity import rotate, scale, translate
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union


AXIS_X = 150.0
SPLIT_LEFT_X = 138.0
SPLIT_RIGHT_X = 162.0
HALF_SHIFT_MM = 2.0
CAP_HEIGHT_MM = 16.5
MCU_ENVELOPE_MM = (18.0, 33.0)
MCU_ENVELOPE_Y_OFFSETS_MM = (-17.0, 16.0)
NOMINAL_MCU_BODY_MM = (17.78, 30.48)
OUTLINE_TOL_MM = 0.015
PLACEMENT_TOL_MM = 0.001
CLEARANCE_TOL_MM = 0.01


def require(condition, description):
    if not condition:
        raise AssertionError(description)


def polygon(vertices, name):
    shape = Polygon(vertices)
    require(shape.is_valid and not shape.is_empty and shape.area > 0,
            f"{name}: invalid exterior polygon")
    return shape


def vertical_section(polygon_, x):
    section = polygon_.intersection(LineString([(x, -10000), (x, 10000)]))
    require(section.geom_type == "LineString" and section.length > 0,
            f"Source exterior at X={x} is not one continuous segment")
    return section.bounds[1], section.bounds[3]


def expected_widened_outline(source):
    """Move each outside slice 2 mm outward and bridge the two cut faces."""
    left = translate(source.intersection(box(-10000, -10000, SPLIT_LEFT_X, 10000)),
                     xoff=-HALF_SHIFT_MM)
    middle = source.intersection(box(SPLIT_LEFT_X, -10000, SPLIT_RIGHT_X, 10000))
    right = translate(source.intersection(box(SPLIT_RIGHT_X, -10000, 10000, 10000)),
                      xoff=HALF_SHIFT_MM)
    left_top, left_bottom = vertical_section(source, SPLIT_LEFT_X)
    right_top, right_bottom = vertical_section(source, SPLIT_RIGHT_X)
    bridges = [box(SPLIT_LEFT_X - HALF_SHIFT_MM, left_top,
                   SPLIT_LEFT_X, left_bottom),
               box(SPLIT_RIGHT_X, right_top,
                   SPLIT_RIGHT_X + HALF_SHIFT_MM, right_bottom)]
    expected = unary_union([left, middle, right, *bridges])
    require(expected.geom_type == "Polygon" and expected.is_valid,
            "Constructed widened outline is invalid")
    return expected


def switch_map(items, description):
    switches = {item["ref"]: item for item in items}
    require(len(items) == len(switches) == 36,
            f"{description}: expected 36 unique switch references")
    return switches


def cap_shape(switch):
    width = 27.0 if "1.5u" in switch["footprint"] else 17.5
    x, y = switch["x_mm"], switch["y_mm"]
    cap = box(x - width / 2, y - CAP_HEIGHT_MM / 2,
              x + width / 2, y + CAP_HEIGHT_MM / 2)
    return rotate(cap, -switch["angle_deg"], origin=(x, y))


def mirror(shape):
    return scale(shape, xfact=-1, yfact=1, origin=(AXIS_X, 0))


def paired_switches(switches):
    left = [s for s in switches.values() if s["x_mm"] < AXIS_X]
    right = [s for s in switches.values() if s["x_mm"] > AXIS_X]
    require(len(left) == len(right) == 18, "Expected 18 switches on each half")
    unmatched = {s["ref"]: s for s in right}
    pairs = []
    for a in sorted(left, key=lambda s: s["ref"]):
        b = min(unmatched.values(),
                key=lambda s: math.hypot(s["x_mm"] + a["x_mm"] - 2 * AXIS_X,
                                         s["y_mm"] - a["y_mm"]))
        unmatched.pop(b["ref"])
        pairs.append((a, b))
    return pairs


def centered_feature(data, name):
    u2 = data["u2_center_mm"]
    led = data["led1_center_mm"]
    bounds = data["battery_opening_bounds_mm"]
    for key, x in (("U2", u2[0]), ("LED1", led[0]),
                   ("battery opening", (bounds[0] + bounds[2]) / 2)):
        require(abs(x - AXIS_X) <= PLACEMENT_TOL_MM,
                f"{name}: {key} is not on X={AXIS_X}")
    require(abs(bounds[0] - 139) <= PLACEMENT_TOL_MM and
            abs(bounds[2] - 161) <= PLACEMENT_TOL_MM,
            f"{name}: battery opening width or lateral position changed")
    return u2, led, bounds


def verify(data):
    source = polygon(data["source_outer_vertices_mm"], "source exterior")
    final = polygon(data["final_outer_vertices_mm"], "final exterior")
    expected = expected_widened_outline(source)
    outline_error = expected.hausdorff_distance(final)
    require(outline_error <= OUTLINE_TOL_MM,
            f"Exterior profile differs from the 2 mm split-and-bridge model by {outline_error:.4f} mm")
    require(abs(final.bounds[0] - 38.5) <= OUTLINE_TOL_MM and
            abs(final.bounds[2] - 261.5) <= OUTLINE_TOL_MM,
            f"Final exterior X bounds are {final.bounds[0]:.4f}..{final.bounds[2]:.4f}, expected 38.5..261.5")
    final_mirror_error = final.hausdorff_distance(mirror(final))
    require(final_mirror_error <= OUTLINE_TOL_MM,
            f"Final exterior mirror error is {final_mirror_error:.4f} mm")

    before = switch_map(data["source_switches"], "source")
    after = switch_map(data["final_switches"], "final")
    require(before.keys() == after.keys(), "Switch references changed")
    for ref, old in before.items():
        new = after[ref]
        shift = -HALF_SHIFT_MM if old["x_mm"] < AXIS_X else HALF_SHIFT_MM
        require(abs(new["x_mm"] - old["x_mm"] - shift) <= PLACEMENT_TOL_MM,
                f"{ref}: X shift is not {shift:+.1f} mm")
        require(abs(new["y_mm"] - old["y_mm"]) <= PLACEMENT_TOL_MM,
                f"{ref}: Y changed")
        require(abs(math.remainder(new["angle_deg"] - old["angle_deg"], 360)) <= PLACEMENT_TOL_MM,
                f"{ref}: rotation changed")
        require(new["footprint"] == old["footprint"],
                f"{ref}: footprint changed")

    pairs = []
    for a, b in paired_switches(after):
        center_error = math.hypot(a["x_mm"] + b["x_mm"] - 2 * AXIS_X,
                                  a["y_mm"] - b["y_mm"])
        cap_a, cap_b = cap_shape(a), cap_shape(b)
        cap_mirror_error = cap_a.hausdorff_distance(mirror(cap_b))
        require(final.covers(cap_a) and final.covers(cap_b),
                f"{a['ref']}/{b['ref']}: nominal cap extends beyond exterior")
        gap_a = cap_a.distance(final.exterior)
        gap_b = cap_b.distance(final.exterior)
        require(center_error <= PLACEMENT_TOL_MM,
                f"{a['ref']}/{b['ref']}: centers are not mirrored")
        require(cap_mirror_error <= PLACEMENT_TOL_MM,
                f"{a['ref']}/{b['ref']}: nominal caps are not mirrored")
        require(abs(gap_a - gap_b) <= CLEARANCE_TOL_MM,
                f"{a['ref']}/{b['ref']}: border clearance differs")
        pairs.append({"left": a["ref"], "right": b["ref"],
                      "center_mirror_error_mm": center_error,
                      "cap_mirror_error_mm": cap_mirror_error,
                      "left_cap_to_exterior_mm": gap_a,
                      "right_cap_to_exterior_mm": gap_b})

    for ref, s in before.items():
        require(source.covers(cap_shape(s)),
                f"{ref}: source nominal cap extends beyond exterior")
    source_gap = {ref: cap_shape(s).distance(source.exterior)
                  for ref, s in before.items()}
    final_gap = {ref: cap_shape(s).distance(final.exterior)
                 for ref, s in after.items()}
    for ref, prior in source_gap.items():
        require(abs(final_gap[ref] - prior) <= CLEARANCE_TOL_MM,
                f"{ref}: cap-to-exterior border changed from {prior:.4f} to {final_gap[ref]:.4f} mm")
    for ref in ("SW2", "SW3", "SW4", "SW34", "SW35", "SW36"):
        require(abs(final_gap[ref] - 2.0) <= CLEARANCE_TOL_MM,
                f"{ref}: outer 1u key border is not 2.00 mm")

    source_u2, source_led, source_opening = centered_feature(data["source_central"], "source")
    final_u2, final_led, final_opening = centered_feature(data["final_central"], "final")
    for label, old, new in (("U2", source_u2, final_u2),
                            ("LED1", source_led, final_led),
                            ("battery opening", source_opening, final_opening)):
        require(len(old) == len(new) and
                all(abs(a - b) <= PLACEMENT_TOL_MM for a, b in zip(old, new)),
                f"{label}: central feature moved")

    u2x, u2y = final_u2
    mcu = box(u2x - MCU_ENVELOPE_MM[0] / 2,
              u2y + MCU_ENVELOPE_Y_OFFSETS_MM[0],
              u2x + MCU_ENVELOPE_MM[0] / 2,
              u2y + MCU_ENVELOPE_Y_OFFSETS_MM[1])
    nominal_body = box(u2x - NOMINAL_MCU_BODY_MM[0] / 2,
                       u2y - NOMINAL_MCU_BODY_MM[1] / 2,
                       u2x + NOMINAL_MCU_BODY_MM[0] / 2,
                       u2y + NOMINAL_MCU_BODY_MM[1] / 2)
    mcu_clearances = {ref: cap_shape(s).distance(mcu) for ref, s in after.items()}
    old_mcu_clearances = {ref: cap_shape(s).distance(mcu) for ref, s in before.items()}
    nominal_body_clearances = {ref: cap_shape(s).distance(nominal_body)
                               for ref, s in after.items()}
    min_mcu_gap = min(mcu_clearances.values())
    require(min_mcu_gap >= 2.15,
            f"18 x 33 mm MCU envelope gap is only {min_mcu_gap:.4f} mm")
    limiting = sorted(ref for ref, value in mcu_clearances.items()
                      if value <= min_mcu_gap + 0.001)

    return {
        "source_before_widening_sha256": data.get("source_before_widening_sha256"),
        "final_sha256": data.get("final_sha256", data.get("source_sha256")),
        "external_profile": {
            "final_x_bounds_mm": [final.bounds[0], final.bounds[2]],
            "final_width_mm": final.bounds[2] - final.bounds[0],
            "expected_profile_hausdorff_mm": outline_error,
            "mirror_hausdorff_mm": final_mirror_error,
            "expected_symmetric_difference_area_mm2": expected.symmetric_difference(final).area,
            "split_x_mm": [SPLIT_LEFT_X, SPLIT_RIGHT_X],
            "outer_half_shift_mm": HALF_SHIFT_MM,
        },
        "switches_checked": len(after),
        "mirror_pairs_checked": len(pairs),
        "maximum_pair_center_error_mm": max(p["center_mirror_error_mm"] for p in pairs),
        "maximum_pair_cap_border_difference_mm": max(abs(p["left_cap_to_exterior_mm"] - p["right_cap_to_exterior_mm"]) for p in pairs),
        "maximum_old_to_new_cap_border_change_mm": max(abs(final_gap[ref] - source_gap[ref]) for ref in before),
        "outer_1u_cap_border_mm": {ref: final_gap[ref] for ref in ("SW2", "SW3", "SW4", "SW34", "SW35", "SW36")},
        "mcu_envelope": {
            "width_mm": MCU_ENVELOPE_MM[0], "height_mm": MCU_ENVELOPE_MM[1],
            "center_mm": final_u2,
            "bounds_mm": list(mcu.bounds),
            "xy_clearance_is_full_travel_conservative": True,
            "minimum_source_gap_mm": min(old_mcu_clearances.values()),
            "minimum_final_gap_mm": min_mcu_gap,
            "limiting_switches": limiting,
            "nominal_body_bounds_mm": list(nominal_body.bounds),
            "minimum_nominal_body_to_cap_gap_mm": min(nominal_body_clearances.values()),
        },
        "central_alignment_x_mm": AXIS_X,
        "pairs": pairs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(json.loads(args.manifest.read_text()))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"223 mm mirrored exterior; {result['switches_checked']} switches shifted 2 mm; "
          f"18 pairs retain cap borders; 18 x 33 mm MCU gap "
          f"{result['mcu_envelope']['minimum_final_gap_mm']:.4f} mm")


if __name__ == "__main__":
    main()
