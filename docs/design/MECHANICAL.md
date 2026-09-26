# Counterframe mechanical guide

**Master:** `hardware/counterframe/counterframe.scad`.

**Construction guide:** `hardware/counterframe/BUILD_GUIDE.html` (illustrated HTML with adjacent render assets) and its Markdown `README.md`.

## Constraints carried forward

Structural parts are PLA only. No screws, threaded inserts, glue, metal ballast or elastomer feet are part of the delivered design. The screen is portrait and the object freestands on a kitchen counter. One external power cable goes directly to Pi PWR IN. A slim visible edge is achieved by tapering the back, not by forcing connectors into an unrealistically thin uniform housing.

The front bezel seats inactive glass borders without intentional preload. The carrier locates each PCB on four tapered-tip posts; the rear's annular collars prevent lift-off at the mounting-hole lands without wedging the PCB. Service face-down: with the cover removed, those collars no longer retain the boards axially.

## Delivered objects

| Category | Files |
|---|---|
| Structural prints | `stl/front.stl`, `carrier.stl`, `rear.stl`, `stand.stl` |
| Fit tests | `coupon_pins.stl`, `coupon_holes.stl`, `coupon_latch.stl`, `coupon_socket.stl` |
| Optional tool | `release_key.stl` |
| Non-printing references | Nine simplified glass/board/component/flex/wire/power-envelope meshes in `reference/` |
| Render tooling | `render.py`, `checks/export_render_meshes.py`, `checks/package.py` |
| Geometry checks | Intersection `.scad` files, `checks/run_collision.sh`, `checks/validate.py`, original `validation.json` |

All print dimensions are millimetres. Four structural prints, not one assembled STL; do not print the reference electronics or scale the parts to fit a smaller printer.

## Nominal geometry and unresolved assumptions

The body is 134 × 188 mm, maximum thickness 34 mm, visible perimeter depth 9 mm. The stand footprint is 142 × 108 mm; backward inclination 10 degrees. Those are source-CAD values, not measured dimensions of the assembled device.

The design assumes the **dedicated Waveshare HAT (E)** with its separate 45 × 21 mm adapter. It uses a matched **50 mm overall, 50-way FFC** between the boards, correct pitch and contact orientation to be checked on the actual kit. A large supplied ribbon cannot simply be creased into that route. The modelled bonded-tail and FFC bend radii are design assumptions, not vendor-certified bending limits. Keep stiffeners/bonded transitions straight.

The internal USB model assumes a slim straight micro-USB plug (9.6 × 14 × 5.6 mm moulding) and 3.4 mm jacket. The split saddle captures the flexible jacket, not a pulling load through the connector. Keep external slack. A right-angle or bulky plug is not a claimed fit.

The pin/hole coupons, glass pocket, PCB-height capture and cable-groove settings all depend on print calibration. Change all mating parts together. Do not press-fit glass or compensate for a tight assembly by pushing through the panel.

## Project wiring

Power down before changing connections. Physical pin numbers are not BCM numbers.

| HAT label | BCM/function | Physical Pi header pin |
|---|---|---:|
| BUSY | GPIO24 | 18 |
| RST | GPIO17 | 11 |
| DC | GPIO25 | 22 |
| CS | GPIO8 / SPI0 CE0 | 24 |
| SCLK | GPIO11 / SPI0 SCLK | 23 |
| DIN | GPIO10 / SPI0 MOSI | 19 |
| GND | Ground | 20 |
| VCC | 3.3 V in this working arrangement | 17 |

HAT switch: **0 = 4-line SPI**. External 5 V supply goes into **Pi PWR IN**, the right-hand micro-USB socket in the Pi board layout. Do not infer pin positions from the early, vertically drawn ASCII header or from cable colours in the CAD render. Read physical numbering/orientation on the actual board/vendor drawing.

This describes the confirmed project setup, not a universal voltage/pin guide for every Waveshare product. Use the dedicated (E) documentation linked in the construction guide and the current driver. GPIO8 chip select is owned by hardware SPI; GPIO18 is not a separate display-power connection in this eight-wire harness.

## Regeneration

Use a separate development output copy if you need to preserve the supplied final renders/STLs as a baseline:

```bash
cd hardware/counterframe
bash export.sh
python checks/export_render_meshes.py
python render.py
bash checks/run_collision.sh
python checks/validate.py
# After render.py has produced renders/internal_anchors.json:
python checks/package.py
```

`export.sh` needs OpenSCAD. Python rendering needs VTK, NumPy and Pillow; packaging the guide needs Mistune; mesh validation needs Trimesh. An off-screen OpenGL-capable environment may be needed for VTK. Optional workstation requirements are listed at the repository root. The existing rendered PNGs and offline guide require no regeneration to view.

`checks/run_collision.sh` intentionally continues after an empty CSG result; **its exit status alone is not proof of passing**. Run `checks/validate.py` afterwards and inspect the report. `checks/package.py` writes ZIPs beside the model folder; read it before running. Its input `internal_anchors.json` is generated by the internal render and was not part of the source tree.

## Qualification status

The original CAD report says engineering prototype, not physically fit-tested by its author. The project photograph shows a real white printed housing holding a working screen. That is useful evidence, but it does not establish exact model revision, internal retention tolerances, flex stress, safe temperature, tip/slip resistance or repeated latch life.

Record the actual printer/filament/layer settings, part version, modifications, cable length/contact orientation, plug dimensions and fitting feedback as the next mechanical task. The case is vented and not splash-proof; original material and placement warnings remain relevant. A local mesh or CSG pass does not certify the assembled appliance.
