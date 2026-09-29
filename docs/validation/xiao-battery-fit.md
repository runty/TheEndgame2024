# XIAO nRF52840 battery fit study (2026-09-28)

Historical study: the [implemented wireless prototype](../xiao-wireless.md) supersedes these provisional assembly details. The final design removes BZ2, moves the battery pads and relief holes 0.5 mm toward the opening, rounds its corners, and provides a separate revised case and tray. Use the current [case notes](../xiao-case.md) and [electrical notes](../xiao-electrical.md) for assembly.

This is a measured **candidate for the next PCB and case revision**, not a fabricated layout or a physical battery fit. The source PCB and STEP case remain unchanged. Coordinates below use the KiCad board system in millimetres; the registered case coordinates are `(board X − 150, 140 − board Y, Z)`, with the board bottom at `Z=0` and top at `Z=1.6`. The XIAO nRF52840 is intended for the existing top-centre controller region; its new footprint, USB cutout, charger, and electrical routing are outside this geometric check.

## Recommended opening and wire landing

Reserve a **22.0 × 28.0 mm rectangular PCB opening**, `X=139.0…161.0`, `Y=116.0…144.0`, centred at `(150,130)`. The corresponding case window is `X=−11.0…11.0`, `Y=−4.0…24.0`. Its long axis runs front to back. This is sized around [Adafruit 1317](https://www.adafruit.com/product/1317), a protected 150 mAh LiPo nominally **19.75 × 26.02 × 3.8 mm**, using a conservative **22 × 28 × 5 mm** pack/tape envelope. Nominal in-plane margin is 1.125 mm per side and 0.99 mm at each end. **The pack sits through the PCB plane**, with a candidate vertical envelope of `Z=0.2…5.2`; the PCB itself occupies `Z=0…1.6`. Measure the actual purchased pouch, protection circuit, tabs, and taped lead exit before finalizing a board slot.

Keep BZ2 in its current location. Orient the pack so its leads leave the opening at the `Y=144` end. For **direct soldering, without a JST connector**, provision labelled B+ and B− pads centred provisionally at `(148,148)` and `(152,148)`, each approximately 2 mm in diameter, with two 1 mm wire strain-relief holes centred at `(148,151)` and `(152,151)`. Add a shallow wire bend/channel in the revised case at the lower end of the pouch; the lead and its insulation must not be pinched by the case. These pad and relief coordinates are geometric reservations only. Final pad size, polarity, trace route to the XIAO charging circuit, hole plating, insulation, and strain-relief method need electrical and manufacturing review.

## Measured clearances on the current board

| Check | Result for proposed opening | Basis |
| --- | ---: | --- |
| Existing 36 switch centres/angles | Unchanged | Original PCB, including Choc V1/V2 hot-swap footprints |
| Nearest switch-body envelope | **6.61 mm** to SW18/SW22 | Conservative 15 × 15 mm square rotated with each switch |
| BZ2 courtyard | **3.05 mm** | Bottom-side courtyard reaches `Y=112.95`; opening begins at `Y=116` |
| Two lower mounting features | **5.17 mm** from assumed 5 mm radius | Centres `(140.195,154.17)` and `(159.805,154.17)` |
| PCB outline | **12.67 mm** minimum | KiCad board polygon; all 616 mm² of opening lies in existing laminate |
| Discrete pads, routed tracks, vias | **0 intersect** | KiCad geometry intersected with the exact opening |
| Ground zone | Spans area | Must be repoured around the new opening, with manufacturing edge clearance |
| Proposed wire pad / relief locations | No existing pads or tracks within 1 mm | All four provisional centres lie within board outline |

The switch figure concerns body envelopes, not solder pads alone. The opening is also clear of the original hot-swap socket pads and drilled holes. It leaves room for the 36 original switch positions and their V1/V2 compatibility to be carried into a new revision, subject to a complete PCB DRC after routing.

## Case comparison and vertical stack

The current STEP case is **solid from `Z=1.6…5.2`** throughout the proposed window. Its intersection with the inset 22 × 28 × 5 mm battery box at `Z=0.2…5.2` is **2,217.6 mm³**, exactly the overlapping 3.6 mm of height. The case needs a **3.6 mm deep pocket from its board-facing surface**, alongside the PCB through-hole. A Boolean check finds full case material across the entire 22 × 28 mm rectangle through `Z=6.70`; the outer surface first appears within `Z=6.70…6.75`. Thus the nominal inset pocket leaves **at least 1.50 mm of case roof** over the complete rectangle. The earlier above-PCB stack (`Z=1.6…6.6`) would have left only about 0.2 mm locally and is not the selected design.

For the case revision, cut the pocket to at least `Z=5.2` plus verified assembly clearance and provide a separate lead channel. The 1.50 mm roof result applies to the **nominal 22 × 28 mm rectangle only**; expanding the case cavity for printing tolerance or increasing its depth can reduce the minimum, so rerun the Boolean and wall-thickness check on the finished STEP model. A raised top cover is **not required by this nominal inset stack**. An insulating, load-bearing **bottom tray or cover beneath the PCB opening** is still needed to retain and protect the pouch. No case material supports the centre opening below the board. The tray and its fasteners must clear the desk or enclosure base, avoid the pouch and nearby mount features, and preserve battery service access. A 0.5 mm tray extending below `Z=0` would reach `Z=−0.5`; the STEP case has a global minimum `Z≈−1.4`, but that alone does not establish a safe desk clearance or support stiffness. Check the revised case and tray together, then print and assemble a battery dummy before committing hardware. Keep the pouch free of screw and switch loading, and allow for normal swelling and tape.

## Method and remaining gates

The board was read with KiCad 10 `pcbnew`; its outline, pads, tracks, vias, and zone were evaluated in the candidate rectangle. Switch body squares and clearance distances were calculated with Shapely. The original STEP case was read with OpenCascade (`cadquery-ocp` 8.0.1.0.0); [the case check script](../../tools/assess_xiao_battery_fit.py) reproduces the battery intersection and roof bound (`python tools/assess_xiao_battery_fit.py` in an environment with OCP). See [the plan view](xiao-battery-fit.svg) for the local layout. None of these checks accounts for conductor bend radius, battery swelling, a built-up tape seam, charger routing, assembly access, case print tolerance, or real enclosure stiffness. Before fabrication, make the new PCB opening/case pocket and lower tray, add battery protection/charge wiring and marked polarity, run KiCad DRC, recheck STEP clearance and minimum wall, then prototype with the actual pack.
