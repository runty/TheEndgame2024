# Endgame — nice!nano wireless / Choc V1 & V2

A 36-key wireless adaptation of [OldMan6955's Endgame](https://github.com/OldMan6955/TheEndgame2024), using **nice!nano v2**, Choc V1/V2 hot-swap switches, a directly soldered **401730 battery**, and one **WS2812B-V6 status LED**.

The current revision is **4 mm wider than the original PCB**. Each key half moves outward 2 mm, giving the inner keys more clearance from the controller while preserving the original outer borders. The controller, battery opening, and LED remain on the board's centreline. The matching case is wider but retains the original height and sloped profile.

**Status:** verified digital prototype. Electrical, manufacturing-file, and CAD checks pass; physical assembly and electrical operation have not been tested. The current Gerber package has not been verified in JLCPCB's upload preview.

![Current PCB, front](001%20PCB/GERBER/NICE%20NANO%20WIRELESS/front-preview.png)

## Downloads

Use the PCB, case, and firmware from this table together. The original case and the older XIAO/wired files are separate revisions.

| File | Download |
| --- | --- |
| JLCPCB manufacturing package | [223 mm through-hole-resistor Gerber ZIP](001%20PCB/GERBER/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano_223mm_THT_JLCPCB.zip) |
| Widened case | [STL](002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_CASE.stl) · [STEP](002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_CASE.step) |
| Removable battery tray | [STL](002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_BATTERY_TRAY.stl) · [STEP](002%20CASE/NICE%20NANO%20WIRELESS/TheENDGAME2024_NICE_NANO_BATTERY_TRAY.step) |
| Editable KiCad project | [PCB](001%20PCB/KICAD/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano.kicad_pcb) · [schematic](001%20PCB/KICAD/NICE%20NANO%20WIRELESS/TheEndgame2024_NiceNano.kicad_sch) · [project and local libraries](001%20PCB/KICAD/NICE%20NANO%20WIRELESS/) |
| nice!nano v2 firmware | [UF2](003%20FIRMWARE/zmk-endgame-nice-nano/firmware/endgame-nice-nano-v2.uf2) · [ZMK source](003%20FIRMWARE/zmk-endgame-nice-nano/) |
| Build details | [Full BOM and assembly notes](docs/nice-nano-wireless.md) · [electrical](docs/nice-nano-electrical.md) · [case](docs/nice-nano-case.md) · [firmware](docs/nice-nano-firmware.md) |

## JLCPCB order settings

| Setting | Value |
| --- | --- |
| Dimensions to enter | **223.00 × 96.11 mm** |
| Layers | **2** |
| Material | **FR-4** |
| Board thickness | **1.6 mm** |
| Copper weight | **1 oz** |

The measured Gerber outline is **223.000032 × 96.106067 mm**. Upload the ZIP intact: it contains the seven board layers, separate plated/non-plated drill files, and the Gerber job file. The **22 × 35 mm battery opening** is included as an internal routed contour. If dimensions need to be entered manually, use the rounded values above and check the board outline and battery opening in the preview.

## Fit and clearance

| Feature | Current design |
| --- | --- |
| Key field | 36 Choc V1/V2 hot-swap positions; each half moved outward 2 mm |
| Outer left/right 1U cap borders | **2.00 mm**, matching the original PCB with 17.5 × 16.5 mm caps |
| Keycap-to-controller clearance | **2.16 mm minimum** to the conservative 18 × 33 mm nice!nano envelope in CAD |
| Printed case width | **231 mm**, with the original overall height retained |
| Battery opening | **22 × 35 mm**, with 1 mm corner radii |
| Battery allowance checked | **18.5 × 33 × 5 mm** complete-pack envelope |

A centred **17 × 30 mm** battery leaves **2.5 mm on each side of the PCB opening**. The larger checked pack envelope leaves **1.75 mm per side and 1.0 mm at each end**, with **0.15 mm above the 5 mm-thick envelope** inside the case after the planned 0.2 mm support allowance. The actual wrapped battery and its lead exit still need measurement.

All 36 nominal **17.5 × 16.5 mm Chicago Steno 1U keycap envelopes** clear the case throughout a full-height CAD sweep, with a **0.70 mm minimum gap**. Choc V2 requires **MX-stem** keycaps. Larger thumb caps and actual print tolerances are not established by this rectangular-envelope check.

See the [measured layout and centreline](docs/validation/nice-nano-pcb/outer-key-symmetry.png), [keycap clearance comparison](docs/validation/nice-nano-case/cs-clearance.png), and [case preview](002%20CASE/NICE%20NANO%20WIRELESS/case-and-tray-preview.png).

## Electronics and assembly

- **nice!nano v2:** mount on short soldered posts, with USB facing the upper edge. Follow the [assembly-height limits](docs/nice-nano-case.md); standard sockets have not been qualified for this case.
- **Battery:** generic 401730 single-cell LiPo, target capacity ≤200 mAh. Solder its wires directly to **J1: pad 1 B+, pad 2 B−**. No JST connector is used. SW38 remains the physical battery disconnect.
- **Resistors:** R1 **330 Ω** and R2 **100 kΩ**, ordinary **¼ W axial through-hole** parts. Use nominal 6.3 × 2.5 mm bodies at **10.16 mm lead pitch**, mounted flat on the PCB's top side. The case accommodates bodies up to 6.5 × 2.5 mm; installation and lead-trimming limits are in the [BOM](docs/nice-nano-wireless.md#parts-and-assembly).
- **Status LED:** one **Worldsemi WS2812B-V6**, powered through nice!nano v2 switched VCC. The translucent case roof acts as the diffuser. The firmware adapts [zmk-rgbled-widget](https://github.com/caksoylar/zmk-rgbled-widget) for brief battery and Bluetooth/USB status flashes, then switches LED power off. See [LED meanings and limits](docs/nice-nano-firmware.md#status-indications).
- **Other parts:** C1 remains a **100 nF 0603 capacitor**, and the matrix retains **36 SOD-123 diodes and 36 Choc hot-swap sockets**. This is a hot-swap switch design; the original optional direct-solder switch pattern is not retained.

The [full parts list](docs/nice-nano-wireless.md#parts-and-assembly) includes controller posts, inserts, tray screws, feet, battery-fit assumptions, and charging requirements. Firmware is **ZMK for nice!nano v2**; the original wired QMK/Vial firmware does not apply to this revision.

## Verification

- **KiCad ERC, DRC, and schematic parity:** zero reported violations or unconnected items under the recorded rules. [ERC](docs/validation/nice-nano-schematic/erc.json) · [DRC](docs/validation/nice-nano-pcb/drc.json)
- **Independent Gerber parsing:** seven board layers, **226 plated and 148 non-plated holes/slots**, both contours closed, and drill registration checked against the PCB source. [Report](docs/validation/nice-nano-pcb/gerbers.json)
- **Mechanical checks:** mirrored key placement, preserved outer borders, centred electronics, valid single-solid STEP parts, watertight STL files, and component/keycap clearance checks. [Spacing](docs/validation/nice-nano-pcb/spacing.json) · [case](docs/validation/nice-nano-case/geometry.json)
- **Firmware:** pinned ZMK build and LED encoder host checks pass. Hardware timing, charging, RF, and full keyboard operation remain untested. [Build and bring-up notes](docs/nice-nano-firmware.md)

The committed PCB is the authoritative manufacturing source. The scratch PCB generator is not a replacement for the finished routing. The [artifact manifest](docs/validation/nice-nano-artifacts.json) records source and output checksums.

## Earlier revisions

| Revision | Details |
| --- | --- |
| XIAO nRF52840 wireless prototype | [Handoff, files, and assembly notes](docs/xiao-wireless.md); 219 × 96.11 mm PCB with a different controller and case |
| Wired Choc V1/V2 conversion | [Compatibility and manufacturing notes](docs/choc-v1-v2.md); original mounting geometry and case |
| Original Endgame | [Upstream project](https://github.com/OldMan6955/TheEndgame2024); original author documentation preserved below |

<details>
<summary>Original upstream README — wired Endgame, parts, credits, and photos</summary>

The following is the original project's documentation. Its controller, firmware, parts lists, manufacturing comments, and physical-test statements refer to the original wired design, not the nice!nano revision above.

<img src="https://github.com/OldMan6955/TheEndgame2024/blob/main/004%20IMAGES/TheEndgameBillboard.jpg" alt="TheEndgameBillboard">





## Who the F... is Alice ##


Inspired by the legendary TGR Alice, the ENDGAME pays homage to a true classic. While it might not claim the top spot for ergonomics, it's design speaks for itself an iconic piece you’ll want to show off, even if it takes a bit of time for your fingers to adjust.

This low profile keyboard is built for high performance typing. Its slightly staggered layout works beautifully for both ergonomic beginners and experienced users. The unique bottomless top mount design makes it incredibly slim, lightweight, and perfect for those on the move.



## Everything You Need, All In One Place ##

Get the entire kit from KeebSupply, a trusted vendor with affordable international shipping. It’s your one stop shop for everything you need highly recommended! [Buy here](https://keeb.supply/products/endgame) 

For an excellent build guide, check out this fantastic resource from KeebSupply. I haven’t had the time to create my own guide (and honestly, I couldn’t top this one). Big thanks to @KeebSupply! [Build Guide and Supplies](https://docs.keeb.supply/endgame/) 



## PARTS LIST PCB ##

- 1x The Endgame PCB             [Gerber Files](https://github.com/OldMan6955/TheEndgame2024/tree/main/001%20PCB) 

There are now two versions of the PCB:
1.	COPPER Version:
In this version, all design elements are on the copper and mask layers. I used this version to create my prototypes. However, this version has longer loading times, and the Gerber files currently don’t work with JLCPCB. (I’d greatly appreciate any help with troubleshooting this issue.)
2.	SILKSCREEN Version:
This version is untested. All design elements have been moved to the silkscreen layer, making it much more performant on less powerful PCs. The Gerber files display correctly on JLCPCB but have not yet been tested.
Please always test the files yourself to rule out potential errors. Thank you!

- 36x Choc v1 Hotswap Sockets    [buy here](https://www.aliexpress.com/item/1005004916925259.html?) 
- 36x Diodes SOD123 / 1N4148W T4 [buy here](https://de.aliexpress.com/item/1005004309686841.html?) 
- 1x Waveshare RP2040 UGLY AF    [buy here](https://de.aliexpress.com/item/1005006354505058.html?) 

or get the better looking thingy, highly recommended

- | 01 | 0xCB Gemini             [buy here](https://keeb.supply/products/0xcb-gemini) |



## PARTS LIST FDM CASE ##

- 4x M3 6mm countersunk          [buy here](https://de.aliexpress.com/item/4001199728978.html) 
- 4x M3 5mm flathead             [buy here](https://de.aliexpress.com/item/1005005069968742.html) 

You can choose either countersunk or flathead screws both work well. Countersunk screws automatically align the PCB, while flathead screws allow you to manually align and adjust as needed.
The hole for the heat inserts is 4mm deep, and the PCB is 1.6mm thick, so 5mm screws are a perfect fit. Just double-check how the screw length is measured, as this can vary.

- 4x M3 D4.6mm L3mm Heatinsert   [buy here](https://de.aliexpress.com/item/4000232858343.html) 
- 12x M3 D6.6mm grommet black     [buy here](https://de.aliexpress.com/item/4000712868621.html) 

You’ll need 4 grommets if you’re aiming for a bit of flex or bounce, but you can use up to 12 depending on your preference. They work perfectly as feet and provide excellent grip on my desk. Alternatively, bumpons are a great option too.

## SWITCHES AND KEYCAPS ##

Switches

I highly recommend the Choc v1 Silent switches, such as [Nocturnal](https://keeb.supply/products/nocturnal-low-profile-switches) or [Twilights](https://keeb.supply/products/twilight-low-profile-switches). If you prefer heavier springs and a bit of tactile feedback but don’t need silence, [Sunset](https://keeb.supply/products/sunset-low-profile-switches) switches are an excellent choice. As for the rest of the Choc v1 lineup, I wouldn’t bother—they’re not worth considering.

Keycaps

My go-to choice is standard [MBK](https://keeb.supply/products/mbk-keycaps) keycaps, but personal preference always plays a role. For your setup, you’ll need:

- 30x 1U keycaps for the alpha keys (or 28x 1U and 2x 1U homing keycaps)
- 4x 1.5U and 2x 1U convex keycaps for the bottom row

Check with your local vendor, they’re in stock almost everywhere these days. A great way to test switches and keycaps is by attending meetups, there might be an active community near you.


## FIRMWARE - QMK AND VIAL ##

The firmware, expertly created by [dreipunkteinsvier](https://github.com/dreipunkteinsvier), is available for download: [Get it here](https://github.com/OldMan6955/TheEndgame2024/tree/main/003%20FIRMWARE) 
Huge thanks to him, I’d have been completely lost without his help!

## DISCLAIMER ##

This keyboard is an open-source project, and all files are provided free of charge for personal use. While these files have been tested and worked for me, they are provided without any guarantees or warranties of any kind.

By using these files, you agree to take full responsibility for verifying their suitability for your needs. Any orders, modifications, or reproductions made based on these files are done at your own risk. I am not liable for any issues, damages, or losses that may arise from the use of these files or the assembly of the keyboard.

Please ensure you carefully review all files and specifications before proceeding. Thank you for understanding!

## RANDOM PEOPLE I KNOW ##

After three years of development and collaboration with contributors from around the world, the ENDGAME is more than just a keyboard it’s the result of a shared journey, a community driven effort that reflects the passion and creativity of everyone involved.

- [Marco "Bob"](https://github.com/GroooveBob) - for answering all my dumb questions 24/7
- [dreipunkteinsvier](https://github.com/dreipunkteinsvier) - firmware and stupid github
- [bubbleology](https://github.com/bubbleology) - inspiration, CAD and emotional support
- [GEIST](https://github.com/GEIGEIGEIST) - can't remember what, but we talked about stuff back in the days RIP
- MY WIFE - for reasons
- and many more

To all who contributed thank you. Enjoy the journey, and have fun exploring what this keyboard can do!

## PICTURES ##

<img src="https://github.com/OldMan6955/TheEndgame2024/blob/main/004%20IMAGES/TheEndgameMood.jpg" alt="TheEndgameMood">
<img src="https://github.com/OldMan6955/TheEndgame2024/blob/main/004%20IMAGES/TheENDGAME%20front.png" alt="TheENDGAME front">
<img src="https://github.com/OldMan6955/TheEndgame2024/blob/main/004%20IMAGES/TheENDGAME%20back.png" alt="TheENDGAME back">


## ONLY FANS ##

While this project is free and open source, I truly appreciate your support. If you'd like to contribute, feel free to leave a tip via Ko-fi to help support future projects. Thank you!

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/T6T218HXN9) 

## SHARE YOUR BUILDS ##

Do you love your ENDGAME? I’d love to see your builds! Join the Discord community to share pictures of your keyboards and chat with fellow enthusiasts.
Just a heads-up: I can’t help with technical issues or soldering nightmares because I’m still learning myself. So, please don’t ask me for help with that!

[![Join My Discord](https://img.shields.io/badge/Join%20Me-On%20Discord-7289da?logo=discord&style=for-the-badge)](https://discord.gg/NQmW8mduXG)

## FINAL WISDOM ##

    "The worst thing that can happen is someone calling me a keyboard designer."
    -OLDMAN6955

</details>
