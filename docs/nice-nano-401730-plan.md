# Endgame nice!nano / 401730 revision requirements

Status: implemented as a complete digital prototype on `codex/nice-nano-401730`, based on XIAO revision `266837a`. See the [prototype handoff](nice-nano-wireless.md) for fabrication files, assembly requirements, and validation. The older wired and XIAO outputs remain separate. Physical hardware has not been tested.

## Accepted choices

- nice!nano **v2**, with the 4-row × 10-column matrix connected directly to GPIOs. Remove the XIAO shift register and its supporting parts.
- Retain all 36 Choc V1/V2 hot-swap switch positions and PCB mounting locations.
- Target the user's generic AliExpress **401730** battery, with direct soldered leads and strain relief, without a JST connector. The earlier preference is 200 mAh or less; the pack's actual capacity, protection, complete dimensions, and charging limit are unverified.
- Enlarge the central PCB opening to **22 × 35 mm**, with a matching case pocket and removable insulating tray. Use an 18.5 × 33 × 5 mm complete-pack planning proxy, not a claimed vendor maximum.
- Keep SW38 at PCB `(150,154)` and retain its case access position. J1 stays at `(148,147.5)` and `(152,147.5)`.
- Keep the original overall case thickness, permitting a local controller bump only if needed. The finished CAD retains the original sloped roof and maximum height. Internal recesses and small shoulders beside the controller provide clearance for the specified short-post assembly.
- Add a central **Worldsemi WS2812B-V6** 5050 status pixel behind the intact translucent PLA roof. This selected revision supports 3.3 V; older or unidentified WS2812B revisions are not assumed interchangeable.
- Keep the pixel off between brief flashes, including cutting its VCC supply. Leave event/colour meanings unassigned. Provide a compiled, unbound test behavior and API for later work.
- Deliver an independently checked JLCPCB Gerber/drill ZIP, editable PCB/schematic, printable case and tray, and prototype firmware.

## Remaining physical verification

The battery size code does not establish the maximum taped-pack envelope or allowed charge current. Keep the nice!nano charge-boost jumper open; its ordinary setting is nominally 100 mA. The selected pack, controller installation height, USB cable, switch/keycap travel, case print tolerances, charging, radio performance, and LED waveform/rail voltage require first-assembly measurements. See the detailed [case](nice-nano-case.md), [electrical](nice-nano-electrical.md), and [firmware](nice-nano-firmware.md) notes.
